"""
Resolver - 技能路由器

Fat Skills 架构的核心组件之一。
职责：
1. 接收用户输入，决策应加载哪个Skill
2. 支持多策略路由：触发词匹配、语义路由、LLM决策
3. 返回最匹配的技能定义

设计原则：
- 描述就是解析器：Skill的description字段用于语义匹配
- 极薄提示词：用最少的token完成路由决策
- 多级缓存：触发词 > 语义 > LLM
"""
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .skills_loader import SkillDefinition, SkillLoader, get_skill_loader

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """路由结果"""
    skill: SkillDefinition
    confidence: float  # 匹配置信度 0-1
    strategy: str  # 匹配策略：trigger/semantic/llm
    reason: str  # 匹配原因
    
    @property
    def skill_id(self) -> str:
        return self.skill.skill_id


class Resolver:
    """
    技能路由器
    
    负责根据用户输入选择最合适的技能。
    """
    
    def __init__(
        self,
        skill_loader: SkillLoader = None,
        llm_client=None,
        embedding_client=None,
        confidence_threshold: float = 0.6
    ):
        """
        初始化路由器
        
        Args:
            skill_loader: 技能加载器
            llm_client: LLM客户端（用于语义路由）
            embedding_client: 向量化客户端（用于语义匹配）
            confidence_threshold: 置信度阈值
        """
        self.skill_loader = skill_loader or get_skill_loader()
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.confidence_threshold = confidence_threshold
        
        # 技能描述索引（用于语义匹配）
        self._skill_descriptions: Dict[str, str] = {}
        self._build_description_index()
        
        logger.info(f"Resolver初始化完成，加载 {len(self._skill_descriptions)} 个技能描述")
    
    def _build_description_index(self):
        """构建技能描述索引"""
        for skill in self.skill_loader.list_skills():
            skill_def = self.skill_loader.get_skill(skill["id"])
            if skill_def:
                # 组合描述：description + triggers
                desc_parts = [skill_def.description]
                desc_parts.extend(skill_def.triggers)
                self._skill_descriptions[skill["id"]] = " ".join(desc_parts)
    
    async def resolve(
        self,
        user_input: str,
        context: Dict[str, Any] = None
    ) -> Optional[RouteResult]:
        """
        路由用户输入到合适的技能
        
        Args:
            user_input: 用户输入
            context: 上下文信息（可选）
            
        Returns:
            RouteResult 或 None（无匹配技能）
        """
        context = context or {}
        
        # 策略1: 触发词精确匹配（最快）
        result = self._match_by_trigger(user_input)
        if result and result.confidence >= self.confidence_threshold:
            logger.info(f"触发词匹配: {result.skill_id} (confidence={result.confidence:.2f})")
            return result
        
        # 策略2: 语义匹配（需要embedding）
        if self.embedding_client:
            result = await self._match_by_semantic(user_input)
            if result and result.confidence >= self.confidence_threshold:
                logger.info(f"语义匹配: {result.skill_id} (confidence={result.confidence:.2f})")
                return result
        
        # 策略3: LLM决策（最准但最慢）
        if self.llm_client:
            result = await self._match_by_llm(user_input, context)
            if result and result.confidence >= self.confidence_threshold:
                logger.info(f"LLM决策: {result.skill_id} (confidence={result.confidence:.2f})")
                return result
        
        # 无匹配，尝试默认技能
        default_skill = self._get_default_skill(user_input)
        if default_skill:
            logger.info(f"使用默认技能: {default_skill.skill_id}")
            return RouteResult(
                skill=default_skill,
                confidence=0.3,
                strategy="default",
                reason="无精确匹配，使用默认技能"
            )
        
        logger.warning(f"无法路由用户输入: {user_input[:50]}...")
        return None
    
    def _match_by_trigger(self, user_input: str) -> Optional[RouteResult]:
        """
        通过触发词匹配
        
        Args:
            user_input: 用户输入
            
        Returns:
            RouteResult 或 None
        """
        best_match = None
        best_score = 0.0
        
        for skill in self.skill_loader.list_skills():
            skill_def = self.skill_loader.get_skill(skill["id"])
            if not skill_def:
                continue
            
            score = skill_def.match_trigger(user_input)
            if score > best_score:
                best_score = score
                best_match = skill_def
        
        if best_match and best_score > 0:
            return RouteResult(
                skill=best_match,
                confidence=min(best_score * 2, 1.0),  # 放大触发词匹配的置信度
                strategy="trigger",
                reason=f"匹配触发词: {best_match.triggers}"
            )
        
        return None
    
    async def _match_by_semantic(self, user_input: str) -> Optional[RouteResult]:
        """
        通过语义相似度匹配
        
        Args:
            user_input: 用户输入
            
        Returns:
            RouteResult 或 None
        """
        if not self.embedding_client:
            return None
        
        try:
            # 获取用户输入的embedding
            user_embedding = await self.embedding_client.embed(user_input)
            
            best_match = None
            best_similarity = 0.0
            
            # 计算与每个技能描述的相似度
            for skill_id, description in self._skill_descriptions.items():
                desc_embedding = await self.embedding_client.embed(description)
                
                # 余弦相似度
                similarity = self._cosine_similarity(user_embedding, desc_embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    skill_def = self.skill_loader.get_skill(skill_id)
                    if skill_def:
                        best_match = skill_def
            
            if best_match and best_similarity > 0.5:
                return RouteResult(
                    skill=best_match,
                    confidence=best_similarity,
                    strategy="semantic",
                    reason=f"语义相似度: {best_similarity:.2f}"
                )
        
        except Exception as e:
            logger.error(f"语义匹配失败: {e}")
        
        return None
    
    async def _match_by_llm(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> Optional[RouteResult]:
        """
        通过LLM决策匹配
        
        Args:
            user_input: 用户输入
            context: 上下文信息
            
        Returns:
            RouteResult 或 None
        """
        if not self.llm_client:
            return None
        
        try:
            # 构建技能列表（极薄提示词）
            skills_summary = []
            for skill in self.skill_loader.list_skills():
                skills_summary.append(
                    f"- {skill['name']}: {skill['description']}"
                )
            
            skills_text = "\n".join(skills_summary)
            
            # 构建路由提示词
            prompt = f"""根据用户输入，选择最合适的技能。

可用技能：
{skills_text}

用户输入：{user_input}

请返回最匹配的技能名称（只返回名称，不要其他内容）。如果没有合适的技能，返回"none"。"""
            
            # 调用LLM（chat方法需要messages列表，返回dict）
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_client.chat(messages)
            skill_name = response.get("content", "").strip().lower()
            
            if skill_name == "none":
                return None
            
            # 查找匹配的技能
            for skill in self.skill_loader.list_skills():
                if skill["name"].lower() == skill_name:
                    skill_def = self.skill_loader.get_skill(skill["id"])
                    if skill_def:
                        return RouteResult(
                            skill=skill_def,
                            confidence=0.8,  # LLM决策的默认置信度
                            strategy="llm",
                            reason=f"LLM决策: {skill_name}"
                        )
        
        except Exception as e:
            logger.error(f"LLM路由失败: {e}")
        
        return None
    
    def _get_default_skill(self, user_input: str) -> Optional[SkillDefinition]:
        """
        获取默认技能
        
        Args:
            user_input: 用户输入
            
        Returns:
            默认技能定义
        """
        # 优先使用chitchat技能
        chitchat = self.skill_loader.get_skill_by_name("chitchat")
        if chitchat:
            return chitchat
        
        # 其次使用faq技能
        faq = self.skill_loader.get_skill_by_name("faq")
        if faq:
            return faq
        
        return None
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度分数
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_skill_prompt(self, skill_id: str) -> Optional[str]:
        """
        获取技能的提示词内容
        
        Args:
            skill_id: 技能ID
            
        Returns:
            技能提示词 或 None
        """
        skill = self.skill_loader.get_skill(skill_id)
        if skill:
            return skill.to_prompt()
        return None
    
    def get_skill_full_content(self, skill_id: str) -> Optional[str]:
        """
        获取技能的完整Markdown内容
        
        Args:
            skill_id: 技能ID
            
        Returns:
            完整Markdown内容 或 None
        """
        skill = self.skill_loader.get_skill(skill_id)
        if skill:
            return skill.full_content
        return None


# 全局单例
_resolver: Optional[Resolver] = None


def get_resolver(
    skill_loader: SkillLoader = None,
    llm_client=None,
    embedding_client=None
) -> Resolver:
    """
    获取路由器单例
    
    Args:
        skill_loader: 技能加载器
        llm_client: LLM客户端
        embedding_client: 向量化客户端
        
    Returns:
        Resolver实例
    """
    global _resolver
    if _resolver is None:
        _resolver = Resolver(
            skill_loader=skill_loader,
            llm_client=llm_client,
            embedding_client=embedding_client
        )
    return _resolver


def reset_resolver():
    """重置路由器（用于测试）"""
    global _resolver
    _resolver = None
