"""
对话历史持久化功能测试

测试对话历史的保存、加载、会话管理和用户隔离功能
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.chat import ChatHistory
from app.models.user import User


class TestAgentHistoryAPI:
    """测试 Agent 对话历史 API"""

    def test_save_chat_message_success(self, client: TestClient, test_user: User, db_session: Session):
        """测试保存聊天消息成功"""
        # 准备数据
        user_id = test_user.id
        session_id = "test_session_001"
        message_type = "user"
        content = "你好，我想找一家火锅店"

        # 调用保存函数
        from app.api.v1.agent import save_chat_message
        
        # 使用mock的redis客户端
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # 执行保存
        asyncio.run(save_chat_message(
            user_id=user_id,
            session_id=session_id,
            message_type=message_type,
            content=content,
            db_session=db_session,
            redis_client=mock_redis
        ))

        # 验证MySQL中保存成功
        saved_msg = db_session.query(ChatHistory).filter(
            ChatHistory.user_id == user_id,
            ChatHistory.session_id == session_id
        ).first()
        
        assert saved_msg is not None
        assert saved_msg.message_type == message_type
        assert saved_msg.content == content

    def test_load_chat_history_from_redis(self, client: TestClient, test_user: User, db_session: Session):
        """测试从Redis加载对话历史"""
        user_id = test_user.id
        session_id = "test_session_002"
        
        # 准备Redis缓存数据
        cached_messages = [
            {
                "id": 1,
                "user_id": user_id,
                "session_id": session_id,
                "message_type": "user",
                "content": "你好",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 2,
                "user_id": user_id,
                "session_id": session_id,
                "message_type": "assistant",
                "content": "你好！有什么可以帮您的吗？",
                "created_at": datetime.now().isoformat()
            }
        ]
        
        # Mock Redis客户端
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_messages, ensure_ascii=False)
        
        # 调用加载函数
        from app.api.v1.agent import load_chat_history
        messages = asyncio.run(load_chat_history(
            user_id=user_id,
            session_id=session_id,
            db_session=db_session,
            redis_client=mock_redis,
            compress=False
        ))
        
        # 验证从Redis加载成功
        assert len(messages) == 2
        assert messages[0]["content"] == "你好"
        assert messages[1]["content"] == "你好！有什么可以帮您的吗？"

    def test_load_chat_history_fallback_to_mysql(self, client: TestClient, test_user: User, db_session: Session):
        """测试Redis无缓存时降级到MySQL"""
        user_id = test_user.id
        session_id = "test_session_003"
        
        # 先在MySQL中插入测试数据
        msg1 = ChatHistory(
            user_id=user_id,
            session_id=session_id,
            message_type="user",
            content="今天天气怎么样？"
        )
        msg2 = ChatHistory(
            user_id=user_id,
            session_id=session_id,
            message_type="assistant",
            content="今天天气晴朗，温度适宜。"
        )
        db_session.add_all([msg1, msg2])
        db_session.commit()
        
        # Mock Redis客户端返回None（缓存未命中）
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        
        # 调用加载函数
        from app.api.v1.agent import load_chat_history
        messages = asyncio.run(load_chat_history(
            user_id=user_id,
            session_id=session_id,
            db_session=db_session,
            redis_client=mock_redis,
            compress=False
        ))
        
        # 验证从MySQL加载成功
        assert len(messages) == 2
        assert messages[0]["content"] == "今天天气怎么样？"
        assert messages[1]["content"] == "今天天气晴朗，温度适宜。"

    def test_get_user_sessions(self, client: TestClient, test_user: User, db_session: Session):
        """测试获取用户会话列表"""
        user_id = test_user.id
        
        # 在MySQL中插入多个会话的数据
        for i in range(3):
            session_id = f"session_{i}"
            msg = ChatHistory(
                user_id=user_id,
                session_id=session_id,
                message_type="user",
                content=f"测试消息{i}"
            )
            db_session.add(msg)
        db_session.commit()
        
        # Mock Redis客户端返回None
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        
        # 调用获取会话列表函数
        from app.api.v1.agent import get_user_sessions
        sessions = asyncio.run(get_user_sessions(
            user_id=user_id,
            db_session=db_session,
            redis_client=mock_redis
        ))
        
        # 验证返回了3个会话
        assert len(sessions) == 3
        session_ids = [s["session_id"] for s in sessions]
        assert "session_0" in session_ids
        assert "session_1" in session_ids
        assert "session_2" in session_ids

    def test_delete_chat_history(self, client: TestClient, test_user: User, db_session: Session):
        """测试删除对话历史"""
        user_id = test_user.id
        session_id = "test_session_to_delete"
        
        # 先插入测试数据
        msg = ChatHistory(
            user_id=user_id,
            session_id=session_id,
            message_type="user",
            content="这条消息将被删除"
        )
        db_session.add(msg)
        db_session.commit()
        
        # Mock Redis客户端
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({
            session_id: {"last_message": "测试", "last_message_time": datetime.now().isoformat()}
        })
        mock_redis.delete.return_value = True
        mock_redis.setex.return_value = True
        
        # 调用删除函数
        from app.api.v1.agent import delete_chat_history
        result = asyncio.run(delete_chat_history(
            session_id=session_id,
            user_id=user_id,
            db_session=db_session,
            redis_client=mock_redis
        ))
        
        # 验证MySQL中的记录已删除
        remaining = db_session.query(ChatHistory).filter(
            ChatHistory.user_id == user_id,
            ChatHistory.session_id == session_id
        ).count()
        assert remaining == 0

    def test_user_isolation(self, client: TestClient, db_session: Session):
        """测试用户隔离功能"""
        # 创建两个测试用户
        user1 = User(
            openid="user1_openid",
            nickname="用户1",
            phone="13800138001"
        )
        user2 = User(
            openid="user2_openid",
            nickname="用户2",
            phone="13800138002"
        )
        db_session.add_all([user1, user2])
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)
        
        # 为用户1插入消息
        msg1 = ChatHistory(
            user_id=user1.id,
            session_id="user1_session",
            message_type="user",
            content="用户1的消息"
        )
        db_session.add(msg1)
        
        # 为用户2插入消息
        msg2 = ChatHistory(
            user_id=user2.id,
            session_id="user2_session",
            message_type="user",
            content="用户2的消息"
        )
        db_session.add(msg2)
        db_session.commit()
        
        # Mock Redis客户端
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        
        # 加载用户1的历史
        from app.api.v1.agent import load_chat_history
        user1_messages = asyncio.run(load_chat_history(
            user_id=user1.id,
            db_session=db_session,
            redis_client=mock_redis,
            compress=False
        ))
        
        # 加载用户2的历史
        user2_messages = asyncio.run(load_chat_history(
            user_id=user2.id,
            db_session=db_session,
            redis_client=mock_redis,
            compress=False
        ))
        
        # 验证用户隔离
        assert len(user1_messages) == 1
        assert user1_messages[0]["content"] == "用户1的消息"
        
        assert len(user2_messages) == 1
        assert user2_messages[0]["content"] == "用户2的消息"

    def test_conversation_compression(self, client: TestClient, test_user: User, db_session: Session):
        """测试对话压缩机制"""
        user_id = test_user.id
        session_id = "test_compression_session"
        
        # 创建超过压缩阈值的消息（30条）
        messages = []
        for i in range(35):
            msg_type = "user" if i % 2 == 0 else "assistant"
            content = f"消息{i}: {'用户问题' if msg_type == 'user' else 'AI回答'}"
            messages.append({
                "id": i,
                "user_id": user_id,
                "session_id": session_id,
                "message_type": msg_type,
                "content": content,
                "created_at": (datetime.now() - timedelta(minutes=35-i)).isoformat()
            })
        
        # Mock Redis客户端
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)
        mock_redis.setex.return_value = True
        
        # 调用加载函数，启用压缩
        from app.api.v1.agent import load_chat_history
        compressed_messages = asyncio.run(load_chat_history(
            user_id=user_id,
            session_id=session_id,
            db_session=db_session,
            redis_client=mock_redis,
            compress=True
        ))
        
        # 验证消息被压缩（应该少于35条）
        assert len(compressed_messages) < 35

    def test_api_endpoint_history(self, client: TestClient, test_user: User, authorized_headers: dict):
        """测试 /agent/history API端点"""
        # 准备测试数据
        from app.api.v1.agent import save_chat_message
        
        # Mock依赖
        with patch('app.api.v1.agent.get_db_session') as mock_db, \
             patch('app.api.v1.agent.get_redis_client') as mock_redis:
            
            mock_db.return_value = MagicMock()
            mock_redis.return_value = MagicMock()
            
            # 调用API
            response = client.get(
                f"/api/v1/agent/history?user_id={test_user.id}&limit=10",
                headers=authorized_headers
            )
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert "messages" in data

    def test_api_endpoint_sessions(self, client: TestClient, test_user: User, authorized_headers: dict):
        """测试 /agent/sessions API端点"""
        # Mock依赖
        with patch('app.api.v1.agent.get_db_session') as mock_db, \
             patch('app.api.v1.agent.get_redis_client') as mock_redis:
            
            mock_db.return_value = MagicMock()
            mock_redis.return_value = MagicMock()
            
            # 调用API
            response = client.get(
                f"/api/v1/agent/sessions?user_id={test_user.id}",
                headers=authorized_headers
            )
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data

    def test_api_endpoint_delete_history(self, client: TestClient, test_user: User, authorized_headers: dict):
        """测试 DELETE /agent/history/{session_id} API端点"""
        session_id = "test_session_delete_api"
        
        # Mock依赖
        with patch('app.api.v1.agent.get_db_session') as mock_db, \
             patch('app.api.v1.agent.get_redis_client') as mock_redis:
            
            mock_db.return_value = MagicMock()
            mock_redis.return_value = MagicMock()
            
            # 调用API
            response = client.delete(
                f"/api/v1/agent/history/{session_id}?user_id={test_user.id}",
                headers=authorized_headers
            )
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert "message" in data


class TestConversationCompressor:
    """测试对话压缩器"""

    def test_should_compress(self):
        """测试压缩判断逻辑"""
        from agent.conversation_compressor import ConversationCompressor
        
        compressor = ConversationCompressor()
        
        # 测试消息数量少于阈值
        short_messages = [{"content": f"消息{i}"} for i in range(10)]
        assert compressor.should_compress(short_messages) == False
        
        # 测试消息数量超过阈值
        long_messages = [{"content": f"消息{i}"} for i in range(35)]
        assert compressor.should_compress(long_messages) == True

    def test_rule_compress(self):
        """测试规则压缩"""
        from agent.conversation_compressor import ConversationCompressor
        
        compressor = ConversationCompressor()
        
        # 创建测试消息
        messages = []
        for i in range(20):
            msg_type = "user" if i % 2 == 0 else "assistant"
            messages.append({
                "message_type": msg_type,
                "content": f"消息{i}: 这是测试内容",
                "created_at": (datetime.now() - timedelta(minutes=20-i)).isoformat()
            })
        
        # 执行规则压缩
        compressed = compressor._rule_compress(messages)
        
        # 验证压缩结果
        assert len(compressed) <= len(messages)
        # 验证保留了最近的消息
        assert any("消息19" in msg.get("content", "") for msg in compressed)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])