"""
记忆管理器和上下文组装器的单元测试
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# 导入被测试的模块
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent.v2.memory.memory_manager import EnhancedMemoryManager
from agent.v2.memory.context_assembler import ContextAssembler


class TestEnhancedMemoryManager:
    """测试增强版记忆管理器"""
    
    @pytest.fixture
    def mock_redis(self):
        """模拟Redis客户端"""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=True)
        redis.lrange = AsyncMock(return_value=[])
        redis.rpush = AsyncMock(return_value=1)
        redis.llen = AsyncMock(return_value=0)
        redis.lindex = AsyncMock(return_value=None)
        redis.ltrim = AsyncMock(return_value=True)
        redis.lpush = AsyncMock(return_value=1)
        redis.expire = AsyncMock(return_value=True)
        return redis
    
    @pytest.fixture
    def mock_llm(self):
        """模拟LLM客户端"""
        llm = AsyncMock()
        llm.chat = AsyncMock(return_value={"content": "测试摘要"})
        return llm
    
    @pytest.fixture
    def memory_manager(self, mock_redis, mock_llm):
        """创建记忆管理器实例"""
        return EnhancedMemoryManager(
            redis_client=mock_redis,
            llm_client=mock_llm,
            config={
                "max_messages": 50,
                "compress_threshold": 30,
                "keep_recent": 10,
                "ttl": 86400 * 7
            }
        )
    
    @pytest.mark.asyncio
    async def test_get_context(self, memory_manager, mock_redis):
        """测试获取上下文"""
        # 模拟Redis返回
        mock_redis.get = AsyncMock(return_value=json.dumps(["店1", "店2"]))
        mock_redis.lrange = AsyncMock(return_value=[
            json.dumps({"role": "user", "content": "你好"}),
            json.dumps({"role": "assistant", "content": "你好！"})
        ])
        mock_redis.llen = AsyncMock(return_value=2)
        
        # 执行测试
        context = await memory_manager.get_context("test_session", include_messages=True)
        
        # 验证结果
        assert context["session_id"] == "test_session"
        assert "already_recommended" in context
        assert "recent_messages" in context
        assert context["message_count"] == 2
    
    @pytest.mark.asyncio
    async def test_save_message(self, memory_manager, mock_redis):
        """测试保存消息"""
        # 模拟Redis返回
        mock_redis.rpush = AsyncMock(return_value=1)
        mock_redis.llen = AsyncMock(return_value=1)
        
        # 执行测试
        result = await memory_manager.save_message("test_session", {
            "role": "user",
            "content": "测试消息"
        })
        
        # 验证结果
        assert result is True
        mock_redis.rpush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sliding_window(self, memory_manager, mock_redis):
        """测试滑动窗口机制"""
        # 模拟Redis返回，超过最大消息数
        mock_redis.llen = AsyncMock(return_value=51)
        mock_redis.lindex = AsyncMock(return_value=json.dumps({
            "role": "user",
            "content": "第一条消息"
        }))
        
        # 执行测试
        await memory_manager.save_message("test_session", {
            "role": "user",
            "content": "新消息"
        })
        
        # 验证滑动窗口被触发
        mock_redis.ltrim.assert_called_once()
        mock_redis.lpush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_entities_with_jieba(self, memory_manager):
        """测试使用jieba提取实体"""
        messages = [
            {"role": "user", "content": "我想去北京路的小肥羊火锅店吃饭，人均100元左右"},
            {"role": "assistant", "content": "好的，我帮你推荐北京路附近的餐厅"}
        ]
        
        # 模拟jieba分词
        with patch.object(memory_manager, 'jieba', create=True) as mock_jieba:
            mock_jieba.cut.return_value = ["我", "想", "去", "北京路", "的", "小肥羊", "火锅店", "吃饭", "，", "人均", "100", "元", "左右"]
            
            entities = await memory_manager._extract_entities(messages)
            
            # 验证实体提取
            assert "locations" in entities
            assert "restaurants" in entities
            assert "prices" in entities
    
    @pytest.mark.asyncio
    async def test_extract_entities_without_jieba(self, memory_manager):
        """测试不使用jieba提取实体"""
        messages = [
            {"role": "user", "content": "我想去北京路的小肥羊火锅店吃饭，人均100元左右"},
            {"role": "assistant", "content": "好的，我帮你推荐北京路附近的餐厅"}
        ]
        
        # 模拟jieba不可用
        with patch.object(memory_manager, 'jieba', False):
            entities = await memory_manager._extract_entities(messages)
            
            # 验证实体提取
            assert "locations" in entities
            assert "restaurants" in entities
            assert "prices" in entities
    
    @pytest.mark.asyncio
    async def test_compress_conversation(self, memory_manager, mock_redis):
        """测试对话压缩"""
        # 模拟大量消息
        messages = []
        for i in range(35):
            messages.append(json.dumps({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"消息{i}",
                "timestamp": datetime.now().isoformat()
            }))
        
        mock_redis.lrange = AsyncMock(return_value=messages)
        mock_redis.delete = AsyncMock(return_value=True)
        mock_redis.rpush = AsyncMock(return_value=1)
        
        # 执行压缩
        await memory_manager._compress_conversation("test_session")
        
        # 验证压缩被触发
        mock_redis.delete.assert_called_once()
        mock_redis.rpush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rule_summary(self, memory_manager):
        """测试规则摘要生成"""
        messages = [
            {"role": "user", "content": "我想吃火锅"},
            {"role": "assistant", "content": "推荐小肥羊"},
            {"role": "user", "content": "人均多少？"},
            {"role": "assistant", "content": "人均100元"}
        ]
        
        entities = {
            "restaurants": ["小肥羊"],
            "cuisines": ["火锅"],
            "prices": ["100元"],
            "intents": ["找餐厅"],
            "locations": []
        }
        
        summary = memory_manager._rule_summary(messages, entities)
        
        # 验证摘要内容
        assert "历史摘要" in summary
        assert "4轮对话" in summary
        assert "小肥羊" in summary
        assert "火锅" in summary
    
    @pytest.mark.asyncio
    async def test_llm_summary(self, memory_manager, mock_llm):
        """测试LLM摘要生成"""
        messages = [
            {"role": "user", "content": "我想吃火锅"},
            {"role": "assistant", "content": "推荐小肥羊"}
        ]
        
        entities = {
            "restaurants": ["小肥羊"],
            "cuisines": ["火锅"],
            "prices": [],
            "intents": ["找餐厅"],
            "locations": []
        }
        
        summary = await memory_manager._llm_summary(messages, entities)
        
        # 验证摘要内容
        assert "历史摘要" in summary
        assert "测试摘要" in summary
        
        # 验证LLM被调用
        mock_llm.chat.assert_called_once()


class TestContextAssembler:
    """测试上下文组装器"""
    
    @pytest.fixture
    def context_assembler(self):
        """创建上下文组装器实例"""
        return ContextAssembler(max_tokens=8000)
    
    def test_estimate_tokens_with_tiktoken(self, context_assembler):
        """测试使用tiktoken估算token"""
        # 模拟tiktoken可用
        with patch.object(context_assembler, '_encoding', create=True) as mock_encoding:
            mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
            
            tokens = context_assembler._estimate_tokens("测试文本")
            
            # 验证token估算
            assert tokens == 5
            mock_encoding.encode.assert_called_once_with("测试文本")
    
    def test_estimate_tokens_without_tiktoken(self, context_assembler):
        """测试不使用tiktoken估算token"""
        # 模拟tiktoken不可用
        with patch.object(context_assembler, '_encoding', False):
            tokens = context_assembler._estimate_tokens("测试文本test")
            
            # 验证token估算（中文约1.5字/token，英文约4字符/token）
            assert tokens > 0
    
    def test_select_messages(self, context_assembler):
        """测试消息选择"""
        messages = [
            {"role": "user", "content": "第一条消息"},
            {"role": "assistant", "content": "回复1"},
            {"role": "user", "content": "第二条消息"},
            {"role": "assistant", "content": "回复2"},
            {"role": "user", "content": "当前消息"}
        ]
        
        # 模拟token估算
        with patch.object(context_assembler, '_estimate_tokens', return_value=100):
            selected = context_assembler._select_messages(messages, 1000)
            
            # 验证消息选择
            assert len(selected) > 0
            assert selected[-1]["content"] == "当前消息"  # 最后一条消息被保留
    
    def test_compress_messages(self, context_assembler):
        """测试消息压缩"""
        messages = [
            {"role": "user", "content": "我想吃火锅"},
            {"role": "assistant", "content": "推荐小肥羊"},
            {"role": "user", "content": "人均多少？"},
            {"role": "assistant", "content": "人均100元"}
        ]
        
        summary = context_assembler._compress_messages(messages)
        
        # 验证摘要内容
        assert "历史对话摘要" in summary
        assert "用户询问" in summary
        assert "AI回复" in summary
    
    def test_assemble(self, context_assembler):
        """测试上下文组装"""
        system_prompt = "你是一个助手"
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
            {"role": "user", "content": "今天天气怎么样？"}
        ]
        
        # 模拟token估算
        with patch.object(context_assembler, '_estimate_tokens', return_value=100):
            result = context_assembler.assemble(
                system_prompt=system_prompt,
                messages=messages,
                context_info="测试上下文"
            )
            
            # 验证组装结果
            assert len(result) > 0
            assert result[0]["role"] == "system"
            assert "你是一个助手" in result[0]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])