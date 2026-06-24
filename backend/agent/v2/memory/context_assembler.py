"""
智能上下文组装器 - 管理token限制，智能组装上下文

设计原则：
1. Token限制管理：确保不超过LLM上下文窗口
2. 优先级排序：最近消息 > 工具结果 > 历史摘要 > 用户画像
3. 动态调整：根据可用空间自动选择消息
4. 保持v2简洁性：不增加过多复杂度
5. 精确Token估算：使用tiktoken进行准确计算
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ContextAssembler:
    """
    智能上下文组装器
    
    职责：
    1. 管理token限制，确保不超过LLM上下文窗口
    2. 智能选择消息，优先保留最近和重要的信息
    3. 组装最终上下文，注入system prompt
    4. 使用tiktoken精确估算token数量
    """
    
    # Token限制配置
    MAX_TOKENS = 8000              # 总token限制
    SYSTEM_PROMPT_TOKENS = 1500    # 系统提示词预留
    TOOL_RESULTS_TOKENS = 1500     # 工具结果预留
    RESERVE_TOKENS = 500           # 预留空间
    
    # 消息选择策略
    ALWAYS_KEEP_FIRST = True       # 总是保留首条消息
    ALWAYS_KEEP_LAST = True        # 总是保留最后一条消息
    
    def __init__(self, max_tokens: int = None, encoding_name: str = "cl100k_base"):
        """
        初始化上下文组装器
        
        Args:
            max_tokens: 最大token数，默认8000
            encoding_name: tiktoken编码名称，默认cl100k_base（GPT-4/GPT-3.5-turbo使用）
        """
        self.max_tokens = max_tokens or self.MAX_TOKENS
        self.encoding_name = encoding_name
        self._encoding = None
    
    def assemble(
        self,
        system_prompt: str,
        messages: List[Dict],
        context_info: str = "",
        tool_results: List[Dict] = None,
        already_recommended: List[str] = None
    ) -> List[Dict]:
        """
        智能组装上下文
        
        Args:
            system_prompt: 系统提示词
            messages: 对话消息列表
            context_info: 额外上下文信息
            tool_results: 工具执行结果
            already_recommended: 已推荐POI列表
            
        Returns:
            组装后的消息列表，可直接传给LLM
        """
        # 1. 计算可用token
        available_tokens = self.max_tokens - self.SYSTEM_PROMPT_TOKENS
        
        # 2. 构建系统提示词（注入上下文信息）
        full_context = self._build_context_string(
            context_info=context_info,
            already_recommended=already_recommended
        )
        
        if full_context:
            system_prompt = f"{system_prompt}\n\n{full_context}"
        
        # 3. 计算消息可用token
        message_tokens = available_tokens - self.TOOL_RESULTS_TOKENS - self.RESERVE_TOKENS
        
        # 4. 选择消息（优先最近，保留首条）
        selected_messages = self._select_messages(messages, message_tokens)
        
        # 5. 构建最终上下文
        context = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 6. 添加工具结果（如果有）
        if tool_results:
            tool_context = self._format_tool_results(tool_results)
            if tool_context:
                context.append({"role": "system", "content": f"[工具结果]\n{tool_context}"})
        
        # 7. 添加消息
        context.extend(selected_messages)
        
        return context
    
    def _build_context_string(
        self,
        context_info: str = "",
        already_recommended: List[str] = None
    ) -> str:
        """构建上下文信息字符串"""
        parts = []
        
        if context_info:
            parts.append(context_info)
        
        if already_recommended:
            rec_list = ", ".join(already_recommended[-5:])
            parts.append(f"已推荐POI: {rec_list}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _select_messages(self, messages: List[Dict], token_limit: int) -> List[Dict]:
        """
        选择消息 - 优先最近，保留首条
        
        策略：
        1. 总是保留最后一条（当前用户输入）
        2. 从后往前选择，直到token限制
        3. 如果有空间，添加首条消息
        4. 如果空间不足，插入历史摘要
        """
        if not messages:
            return []
        
        # 估算每条消息的token
        message_tokens = []
        for msg in messages:
            tokens = self._estimate_tokens(msg.get("content", ""))
            message_tokens.append(tokens)
        
        # 从后往前选择
        selected = []
        total_tokens = 0
        
        # 总是保留最后一条
        if messages:
            last_msg = messages[-1]
            last_tokens = message_tokens[-1]
            selected.insert(0, last_msg)
            total_tokens += last_tokens
        
        # 从倒数第二条开始往前选
        for i in range(len(messages) - 2, 0, -1):
            msg = messages[i]
            tokens = message_tokens[i]
            
            if total_tokens + tokens > token_limit:
                # 超出限制，插入摘要
                summary = self._compress_messages(messages[:i+1])
                selected.insert(0, {"role": "system", "content": summary})
                break
            
            selected.insert(0, msg)
            total_tokens += tokens
        
        # 如果还有空间，添加首条消息
        if messages and len(selected) > 1 and self.ALWAYS_KEEP_FIRST:
            first_tokens = message_tokens[0]
            if total_tokens + first_tokens <= token_limit:
                selected.insert(0, messages[0])
        
        return selected
    
    @property
    def encoding(self):
        """延迟加载tiktoken编码器"""
        if self._encoding is None:
            try:
                import tiktoken
                self._encoding = tiktoken.get_encoding(self.encoding_name)
            except ImportError:
                logger.warning("tiktoken未安装，将使用简单估算方法")
                self._encoding = False
        return self._encoding
    
    def _estimate_tokens(self, text: str) -> int:
        """
        估算token数量
        
        优先使用tiktoken精确计算，降级到简单估算：
        - tiktoken: 精确计算，适用于GPT-4/GPT-3.5-turbo
        - 简单估算: 中文约1.5字/token，英文约4字符/token
        """
        if not text:
            return 0
        
        # 使用tiktoken精确计算
        if self.encoding and self.encoding is not False:
            try:
                return len(self.encoding.encode(text))
            except Exception as e:
                logger.warning(f"tiktoken编码失败，降级到简单估算: {e}")
        
        # 降级：简单估算
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + english_chars / 4)
    
    def _compress_messages(self, messages: List[Dict]) -> str:
        """
        压缩消息为摘要
        
        当消息超出token限制时，生成压缩摘要
        """
        # 提取关键信息
        user_queries = [m["content"][:50] for m in messages 
                       if m.get("role") == "user"][:3]
        ai_replies = [m["content"][:50] for m in messages 
                     if m.get("role") == "assistant"][:3]
        
        summary_parts = []
        if user_queries:
            summary_parts.append(f"用户询问: {'; '.join(user_queries)}")
        if ai_replies:
            summary_parts.append(f"AI回复: {'; '.join(ai_replies)}")
        
        # 提取实体
        entities = set()
        for msg in messages:
            msg_entities = msg.get("entities", {})
            if isinstance(msg_entities, dict):
                for v in msg_entities.values():
                    if v and isinstance(v, str):
                        entities.add(v)
        
        if entities:
            summary_parts.append(f"涉及实体: {', '.join(list(entities)[:5])}")
        
        return "[历史对话摘要] " + " | ".join(summary_parts)
    
    def _format_tool_results(self, tool_results: List[Dict]) -> str:
        """格式化工具结果"""
        if not tool_results:
            return ""
        
        parts = []
        for i, result in enumerate(tool_results[:5], 1):
            if isinstance(result, dict):
                tool_name = result.get("tool", f"工具{i}")
                status = result.get("status", "unknown")
                data = result.get("data", {})
                
                # 简化数据展示
                if isinstance(data, dict):
                    if "pois" in data:
                        pois = data["pois"]
                        parts.append(f"{tool_name}: 找到{len(pois)}个结果")
                    elif "items" in data:
                        items = data["items"]
                        parts.append(f"{tool_name}: {len(items)}条数据")
                    else:
                        parts.append(f"{tool_name}: {status}")
                else:
                    parts.append(f"{tool_name}: {status}")
        
        return "\n".join(parts)


# 全局单例
_context_assembler: Optional[ContextAssembler] = None


def get_context_assembler(max_tokens: int = None) -> ContextAssembler:
    """获取上下文组装器单例"""
    global _context_assembler
    
    if _context_assembler is None:
        _context_assembler = ContextAssembler(max_tokens)
    
    return _context_assembler


def reset_context_assembler():
    """重置上下文组装器单例（用于测试）"""
    global _context_assembler
    _context_assembler = None
