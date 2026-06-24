"""
Skills Loader - Fat Skills 架构核心组件

从Markdown文件动态加载技能定义，支持热更新。
职责：
1. 扫描skills目录发现所有.md文件
2. 解析YAML Front Matter提取技能元数据
3. 解析Markdown正文提取执行逻辑
4. 提供技能查询和检索接口
"""
import os
import re
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SkillDefinition:
    """技能定义数据结构"""
    # 元数据
    name: str
    description: str
    version: str = "1.0"
    author: str = ""
    
    # 触发和路由
    triggers: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    
    # 输入输出规范
    input_schema: Dict[str, Any] = field(default_factory=dict)
    
    # 执行逻辑（原始Markdown）
    overview: str = ""
    preconditions: List[str] = field(default_factory=list)
    steps: List[Dict[str, str]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    output_format: str = ""
    error_handling: Dict[str, str] = field(default_factory=dict)
    examples: List[Dict[str, str]] = field(default_factory=list)
    
    # 完整内容（用于LLM参考）
    full_content: str = ""
    
    # 文件信息
    file_path: str = ""
    category: str = ""
    
    @property
    def skill_id(self) -> str:
        """技能唯一标识"""
        return f"{self.category}/{self.name}" if self.category else self.name
    
    def to_prompt(self) -> str:
        """转换为LLM可读的提示词格式"""
        parts = []
        
        # 标题
        parts.append(f"# 技能: {self.name}")
        parts.append(f"**描述**: {self.description}")
        parts.append("")
        
        # 输入规范
        if self.input_schema:
            parts.append("## 输入参数")
            for param_name, param_info in self.input_schema.items():
                required = "必填" if param_info.get("required", False) else "选填"
                parts.append(f"- **{param_name}** ({required}): {param_info.get('description', '')}")
            parts.append("")
        
        # 执行步骤
        if self.steps:
            parts.append("## 执行步骤")
            for i, step in enumerate(self.steps, 1):
                parts.append(f"### 步骤{i}: {step.get('title', '')}")
                parts.append(step.get('content', ''))
                parts.append("")
        
        # 输出格式
        if self.output_format:
            parts.append("## 输出格式")
            parts.append(self.output_format)
            parts.append("")
        
        return "\n".join(parts)
    
    def match_trigger(self, text: str) -> float:
        """计算文本与触发词的匹配分数"""
        text_lower = text.lower()
        max_score = 0.0
        
        for trigger in self.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower in text_lower:
                # 完全匹配得分更高
                score = len(trigger_lower) / len(text_lower)
                max_score = max(max_score, score)
        
        return max_score


class SkillLoader:
    """
    技能加载器
    
    负责从Markdown文件加载技能定义，支持热更新。
    """
    
    def __init__(self, skills_dir: Optional[str] = None):
        """
        初始化技能加载器
        
        Args:
            skills_dir: 技能目录路径，默认为当前文件同级的skills目录
        """
        if skills_dir is None:
            skills_dir = str(Path(__file__).parent / "skills")
        
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, SkillDefinition] = {}
        self._categories: Dict[str, List[str]] = {}
        
        # 初始加载
        self.load_all_skills()
    
    def load_all_skills(self):
        """加载所有技能文件"""
        self._skills.clear()
        self._categories.clear()
        
        if not self.skills_dir.exists():
            logger.warning(f"Skills目录不存在: {self.skills_dir}")
            return
        
        # 递归扫描所有.md文件
        for md_file in self.skills_dir.rglob("*.md"):
            # 跳过README和模板
            if md_file.name.startswith("README") or "_templates" in str(md_file):
                continue
            
            try:
                skill = self._parse_skill_file(md_file)
                if skill:
                    self._skills[skill.skill_id] = skill
                    
                    # 分类索引
                    category = skill.category or "uncategorized"
                    if category not in self._categories:
                        self._categories[category] = []
                    self._categories[category].append(skill.skill_id)
                    
                    logger.info(f"加载技能: {skill.skill_id}")
            except Exception as e:
                logger.error(f"加载技能文件失败 {md_file}: {e}")
        
        logger.info(f"共加载 {len(self._skills)} 个技能")
    
    def _parse_skill_file(self, file_path: Path) -> Optional[SkillDefinition]:
        """
        解析技能文件
        
        Args:
            file_path: Markdown文件路径
            
        Returns:
            SkillDefinition 或 None
        """
        content = file_path.read_text(encoding="utf-8")
        
        # 解析Front Matter
        front_matter, body = self._split_front_matter(content)
        if front_matter is None:
            logger.warning(f"文件缺少Front Matter: {file_path}")
            return None
        
        # 解析YAML
        try:
            metadata = yaml.safe_load(front_matter)
        except yaml.YAMLError as e:
            logger.error(f"YAML解析错误 {file_path}: {e}")
            return None
        
        if not isinstance(metadata, dict):
            return None
        
        # 计算分类（从目录结构）
        relative_path = file_path.relative_to(self.skills_dir)
        category = str(relative_path.parent) if relative_path.parent != Path(".") else ""
        
        # 构建技能定义
        skill = SkillDefinition(
            name=metadata.get("name", file_path.stem),
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0"),
            author=metadata.get("author", ""),
            triggers=metadata.get("triggers", []),
            required_tools=metadata.get("required_tools", []),
            input_schema=metadata.get("input_schema", {}),
            file_path=str(file_path),
            category=category,
            full_content=content
        )
        
        # 解析正文结构
        self._parse_body(skill, body)
        
        return skill
    
    def _split_front_matter(self, content: str) -> tuple[Optional[str], str]:
        """
        分离Front Matter和正文
        
        Returns:
            (front_matter, body) 元组
        """
        # 匹配 --- 包裹的YAML
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)
        
        if match:
            return match.group(1), match.group(2)
        return None, content
    
    def _parse_body(self, skill: SkillDefinition, body: str):
        """
        解析Markdown正文，提取各个部分
        
        Args:
            skill: 技能定义对象
            body: Markdown正文
        """
        # 提取概述
        overview_match = re.search(r"## 技能概述\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
        if overview_match:
            skill.overview = overview_match.group(1).strip()
        
        # 提取前置条件
        precond_match = re.search(r"## 前置条件\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
        if precond_match:
            precond_text = precond_match.group(1)
            skill.preconditions = [
                line.strip().lstrip("- [ ] ").lstrip("- [x] ")
                for line in precond_text.split("\n")
                if line.strip().startswith("- [")
            ]
        
        # 提取执行步骤
        steps_section = re.search(r"## 执行逻辑\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
        if steps_section:
            steps_text = steps_section.group(1)
            step_pattern = r"### (步骤\d+:\s*.*?)\n(.*?)(?=\n###|\Z)"
            for match in re.finditer(step_pattern, steps_text, re.DOTALL):
                skill.steps.append({
                    "title": match.group(1).strip(),
                    "content": match.group(2).strip()
                })
        
        # 提取约束条件
        constraint_match = re.search(r"## 约束条件\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
        if constraint_match:
            constraint_text = constraint_match.group(1)
            skill.constraints = [
                line.strip().lstrip("0123456789. ")
                for line in constraint_text.split("\n")
                if line.strip() and line.strip()[0].isdigit()
            ]
        
        # 提取输出格式
        output_match = re.search(r"## 输出格式\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
        if output_match:
            skill.output_format = output_match.group(1).strip()
        
        # 提取异常处理
        error_section = re.search(r"## 异常处理\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
        if error_section:
            error_text = error_section.group(1)
            # 解析表格
            for line in error_text.split("\n"):
                if "|" in line and "错误码" not in line and "---" not in line:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 3:
                        skill.error_handling[parts[0]] = f"{parts[1]}: {parts[2]}"
        
        # 提取示例
        example_pattern = r"## 对话示例\s*\n(.*?)(?=\n##|\Z)"
        example_match = re.search(example_pattern, body, re.DOTALL)
        if example_match:
            example_text = example_match.group(1)
            example_blocks = re.split(r"\n---\n", example_text)
            for block in example_blocks:
                example = {}
                user_match = re.search(r"\*\*用户\*\*:\s*(.*?)$", block, re.MULTILINE)
                output_match = re.search(r"\*\*输出\*\*:\s*(.*?)$", block, re.MULTILINE | re.DOTALL)
                if user_match:
                    example["input"] = user_match.group(1).strip()
                if output_match:
                    example["output"] = output_match.group(1).strip()
                if example:
                    skill.examples.append(example)
    
    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        """
        根据ID获取技能
        
        Args:
            skill_id: 技能ID
            
        Returns:
            SkillDefinition 或 None
        """
        return self._skills.get(skill_id)
    
    def get_skill_by_name(self, name: str) -> Optional[SkillDefinition]:
        """
        根据名称获取技能
        
        Args:
            name: 技能名称
            
        Returns:
            SkillDefinition 或 None
        """
        for skill in self._skills.values():
            if skill.name == name:
                return skill
        return None
    
    def list_skills(self) -> List[Dict[str, Any]]:
        """
        列出所有技能摘要
        
        Returns:
            技能摘要列表
        """
        return [
            {
                "id": skill.skill_id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "triggers": skill.triggers
            }
            for skill in self._skills.values()
        ]
    
    def get_skills_by_category(self, category: str) -> List[SkillDefinition]:
        """
        获取指定分类的技能
        
        Args:
            category: 技能分类
            
        Returns:
            技能列表
        """
        skill_ids = self._categories.get(category, [])
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]
    
    def search_skills(self, query: str, limit: int = 5) -> List[SkillDefinition]:
        """
        搜索匹配的技能
        
        Args:
            query: 搜索查询
            limit: 返回数量限制
            
        Returns:
            匹配的技能列表，按相关度排序
        """
        scored_skills = []
        
        for skill in self._skills.values():
            # 计算触发词匹配分数
            trigger_score = skill.match_trigger(query)
            
            # 计算描述匹配分数
            desc_score = 0.0
            query_lower = query.lower()
            desc_lower = skill.description.lower()
            for word in query_lower.split():
                if word in desc_lower:
                    desc_score += 0.1
            
            total_score = trigger_score + desc_score
            
            if total_score > 0:
                scored_skills.append((total_score, skill))
        
        # 按分数排序
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        
        return [skill for _, skill in scored_skills[:limit]]
    
    def reload_skill(self, skill_id: str) -> bool:
        """
        重新加载指定技能
        
        Args:
            skill_id: 技能ID
            
        Returns:
            是否成功
        """
        skill = self._skills.get(skill_id)
        if not skill:
            return False
        
        try:
            new_skill = self._parse_skill_file(Path(skill.file_path))
            if new_skill:
                self._skills[skill_id] = new_skill
                logger.info(f"重新加载技能: {skill_id}")
                return True
        except Exception as e:
            logger.error(f"重新加载技能失败 {skill_id}: {e}")
        
        return False
    
    def watch_changes(self, callback=None):
        """
        监控技能文件变化（热更新）
        
        Args:
            callback: 变化时的回调函数，接收 (event_type, file_path) 参数
        
        Returns:
            Observer实例，可用于停止监控
        """
        try:
            from watchdog.observers import Observer  # type: ignore
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent  # type: ignore
            
            loader = self
            
            class SkillFileHandler(FileSystemEventHandler):
                """技能文件变化处理器"""
                
                def __init__(self):
                    super().__init__()
                    self._callback = callback
                    self._last_reload = 0
                    self._reload_delay = 1.0  # 防抖延迟（秒）
                
                def on_modified(self, event):
                    if not event.is_directory and event.src_path.endswith('.md'):
                        self._schedule_reload("modified", event.src_path)
                
                def on_created(self, event):
                    if not event.is_directory and event.src_path.endswith('.md'):
                        self._schedule_reload("created", event.src_path)
                
                def on_deleted(self, event):
                    if not event.is_directory and event.src_path.endswith('.md'):
                        self._schedule_reload("deleted", event.src_path)
                
                def _schedule_reload(self, event_type: str, file_path: str):
                    """调度重新加载（带防抖）"""
                    import time
                    import threading
                    
                    current_time = time.time()
                    if current_time - self._last_reload < self._reload_delay:
                        return
                    
                    self._last_reload = current_time
                    
                    # 异步执行重新加载
                    def do_reload():
                        try:
                            logger.info(f"检测到技能文件变化: {event_type} - {file_path}")
                            loader.load_all_skills()
                            if self._callback:
                                self._callback(event_type, file_path)
                        except Exception as e:
                            logger.error(f"热重载失败: {e}")
                    
                    thread = threading.Thread(target=do_reload, daemon=True)
                    thread.start()
            
            # 创建观察者
            observer = Observer()
            handler = SkillFileHandler()
            observer.schedule(handler, str(self.skills_dir), recursive=True)
            observer.start()
            
            logger.info(f"开始监控技能目录: {self.skills_dir}")
            return observer
            
        except ImportError:
            logger.warning("watchdog 未安装，文件监控已禁用。安装: pip install watchdog")
            return None
        except Exception as e:
            logger.error(f"启动文件监控失败: {e}")
            return None


# 全局单例
_skill_loader: Optional[SkillLoader] = None


def get_skill_loader(skills_dir: Optional[str] = None) -> SkillLoader:
    """
    获取技能加载器单例
    
    Args:
        skills_dir: 技能目录路径
        
    Returns:
        SkillLoader实例
    """
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader(skills_dir)
    return _skill_loader


def reload_skills():
    """重新加载所有技能"""
    global _skill_loader
    if _skill_loader:
        _skill_loader.load_all_skills()
