"""
对话摘要压缩器 (Conversation Compressor)
使用 LLM 对过长的对话历史进行智能摘要压缩。

此模块为共享组件，供应用层（chat_history）使用，与已废弃的 v1 模块完全解耦。
"""
import json
import logging
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ConversationCompressor:
    """
    对话摘要压缩器
    
    设计思路：
    1. 滑动窗口：保留最近 N 轮对话原文
    2. 渐进式压缩：对较早的对话进行分批摘要
    3. LLM 智能压缩：使用大模型生成高质量摘要
    4. 结构化存储：摘要中保留关键信息（意图、实体、结论）
    """
    
    # 压缩配置
    MAX_MESSAGES = 50           # 最大消息数
    COMPRESS_THRESHOLD = 30     # 触发压缩的消息数阈值（向后兼容）
    TOKEN_COMPRESS_THRESHOLD = 128000  # 触发压缩的 token 阈值（128k，适配小米 MiMo 模型上下文窗口）
    KEEP_RECENT = 10            # 保留最近 N 条原文
    BATCH_SIZE = 5              # 每批压缩的消息数
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    @staticmethod
    def estimate_tokens(messages: List[dict]) -> int:
        """
        估算消息列表的 token 数量。
        
        采用保守估算策略（宁可多算不少算）：
        - 中文字符：约 1.5 token/字符
        - 英文/数字：约 0.25 token/字符（4 字符 ≈ 1 token）
        - 标点/空白：约 0.3 token/字符
        - 每条消息固定开销（role、metadata 等）：约 10 token
        """
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "") or ""
            total_chars += len(content)
        
        # 保守估算：中文约占 60%，英文数字约占 30%，标点空白约占 10%
        # 整体按 ~1 token/字符 估算（略偏高，保证安全）
        estimated_tokens = int(total_chars * 1.0)
        
        # 加上每条消息的固定开销（role token、分隔符等）
        estimated_tokens += len(messages) * 10
        
        return estimated_tokens
    
    def should_compress(self, messages: List[dict], use_token_threshold: bool = True) -> bool:
        """
        判断是否需要压缩
        
        Args:
            messages: 消息列表
            use_token_threshold: 是否使用 token 阈值（默认 True，适配小米 128k 窗口）
        """
        if use_token_threshold:
            estimated = self.estimate_tokens(messages)
            logger.debug(f"当前对话估算 token 数: {estimated}, 阈值: {self.TOKEN_COMPRESS_THRESHOLD}")
            return estimated > self.TOKEN_COMPRESS_THRESHOLD
        return len(messages) > self.COMPRESS_THRESHOLD
    
    async def compress(self, messages: List[dict], user_id: Optional[str] = None) -> List[dict]:
        """
        压缩对话历史
        
        策略：
        1. 最近 KEEP_RECENT 条消息保留原文
        2. 更早的消息分批进行 LLM 摘要
        3. 每个摘要作为一条特殊的 "summary" 消息
        
        Returns:
            压缩后的消息列表
        """
        if not self.should_compress(messages, use_token_threshold=True):
            return messages
        
        # 分割：保留原文的部分 + 需要压缩的部分
        recent_messages = messages[-self.KEEP_RECENT:]
        older_messages = messages[:-self.KEEP_RECENT]
        
        # 对较早的消息进行分批压缩
        compressed_messages = []
        
        if self.llm_client:
            # 使用 LLM 进行智能压缩
            summaries = await self._llm_compress(older_messages)
            compressed_messages.extend(summaries)
        else:
            # 降级：使用规则压缩
            compressed_messages = self._rule_compress(older_messages)
        
        # 合并：压缩摘要 + 最近原文
        result = compressed_messages + recent_messages
        
        logger.info(
            f"对话压缩完成: {len(messages)} -> {len(result)} 条 "
            f"(压缩了 {len(older_messages)} 条，保留 {len(recent_messages)} 条原文)"
        )
        
        return result
    
    async def _llm_compress(self, messages: List[dict]) -> List[dict]:
        """使用 LLM 进行智能压缩"""
        summaries = []
        
        # 分批处理
        for i in range(0, len(messages), self.BATCH_SIZE):
            batch = messages[i:i + self.BATCH_SIZE]
            
            # 构建压缩提示
            conversation_text = self._format_messages_for_compression(batch)
            
            prompt = f"""请对以下对话进行摘要压缩，要求：
1. 保留关键信息：用户的意图、需求、偏好
2. 保留重要的结论和决策
3. 保留提到的具体地点、美食、景点等实体
4. 使用简洁的第三人称描述
5. 控制在 100 字以内

对话内容：
{conversation_text}

请直接输出摘要内容，不要添加任何前缀或解释。"""
            
            try:
                # 调用 LLM 生成摘要
                llm_response = await self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": "你是一个专业的对话摘要助手，擅长提取对话中的关键信息。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=200,
                    temperature=0.3
                )
                
                # llm_client.chat() 返回 dict，需要提取 content 字段
                if isinstance(llm_response, dict):
                    summary_text = llm_response.get("content", "")
                else:
                    summary_text = str(llm_response)
                
                # 提取意图和实体
                intents = list(set(m.get("intent", "") for m in batch if m.get("intent")))
                entities = {}
                for m in batch:
                    if m.get("entities"):
                        entities.update(m["entities"])
                
                # 创建摘要消息
                summary_msg = {
                    "id": f"summary_{i}",
                    "role": "system",
                    "content": summary_text.strip(),
                    "message_type": "summary",
                    "timestamp": batch[0].get("timestamp", datetime.now().isoformat()),
                    "metadata": {
                        "compressed_from": len(batch),
                        "intents": intents,
                        "entities": entities,
                        "time_range": {
                            "start": batch[0].get("timestamp"),
                            "end": batch[-1].get("timestamp")
                        }
                    }
                }
                summaries.append(summary_msg)
                
            except Exception as e:
                logger.warning(f"LLM 压缩失败，降级到规则压缩: {e}")
                # 降级到规则压缩
                rule_summaries = self._rule_compress_batch(batch)
                summaries.extend(rule_summaries)
        
        return summaries
    
    def _rule_compress(self, messages: List[dict]) -> List[dict]:
        """规则压缩（降级方案）"""
        summaries = []
        
        for i in range(0, len(messages), self.BATCH_SIZE):
            batch = messages[i:i + self.BATCH_SIZE]
            rule_summaries = self._rule_compress_batch(batch)
            summaries.extend(rule_summaries)
        
        return summaries
    
    def _rule_compress_batch(self, batch: List[dict]) -> List[dict]:
        """规则压缩单批消息"""
        # 统计意图
        intents = []
        user_messages = []
        assistant_messages = []
        
        for m in batch:
            if m.get("intent"):
                intents.append(m["intent"])
            if m.get("role") == "user" or m.get("message_type") == "user":
                user_messages.append(m.get("content", "")[:50])
            elif m.get("role") == "assistant" or m.get("message_type") == "assistant":
                assistant_messages.append(m.get("content", "")[:50])
        
        # 生成摘要文本
        intent_str = "、".join(set(intents)) if intents else "一般对话"
        summary_parts = []
        
        if user_messages:
            summary_parts.append(f"用户询问了{len(user_messages)}个问题")
        if assistant_messages:
            summary_parts.append(f"助手提供了{len(assistant_messages)}次回复")
        
        summary_text = f"[对话摘要] {'，'.join(summary_parts)}（涉及：{intent_str}）"
        
        # 提取实体
        entities = {}
        for m in batch:
            if m.get("entities"):
                entities.update(m["entities"])
        
        return [{
            "id": f"summary_rule_{batch[0].get('id', 'unknown')}",
            "role": "system",
            "content": summary_text,
            "message_type": "summary",
            "timestamp": batch[0].get("timestamp", datetime.now().isoformat()),
            "metadata": {
                "compressed_from": len(batch),
                "intents": list(set(intents)),
                "entities": entities,
                "compression_method": "rule"
            }
        }]
    
    def _format_messages_for_compression(self, messages: List[dict]) -> str:
        """格式化消息用于压缩提示"""
        lines = []
        for m in messages:
            role = "用户" if m.get("role") == "user" or m.get("message_type") == "user" else "助手"
            content = m.get("content", "")
            # 截断过长的内容
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    async def compress_and_update(
        self,
        messages: List[dict],
        user_id: str,
        session_id: str,
        redis_client=None,
        db_session=None
    ) -> List[dict]:
        """
        压缩对话历史并更新存储
        
        完整流程：
        1. 检查是否需要压缩
        2. 执行压缩
        3. 更新 Redis 缓存
        4. （可选）将摘要写入 MySQL
        """
        estimated_tokens = self.estimate_tokens(messages)
        logger.info(f"对话 token 估算: {estimated_tokens}/{self.TOKEN_COMPRESS_THRESHOLD}, 消息数: {len(messages)}")
        
        if not self.should_compress(messages, use_token_threshold=True):
            return messages
        
        # 执行压缩
        compressed = await self.compress(messages, str(user_id))
        
        # 更新 Redis 缓存
        if redis_client:
            try:
                cache_key = f"chat:assistant:{user_id}:{session_id}"
                redis_client.setex(
                    cache_key,
                    86400,  # 24小时 TTL
                    json.dumps(compressed, ensure_ascii=False)
                )
                logger.info(f"已更新 Redis 缓存: {cache_key}")
            except Exception as e:
                logger.error(f"更新 Redis 缓存失败: {e}")
        
        return compressed


# 全局单例
conversation_compressor = ConversationCompressor()
