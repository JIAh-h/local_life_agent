from sqlalchemy import Column, BigInteger, String, DateTime, func, ForeignKey, JSON, Text, DECIMAL, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class ChatHistory(Base):
    """对话历史表"""
    __tablename__ = "chat_history"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, comment="用户ID（支持UUID格式）")
    session_id = Column(String(64), nullable=False, comment="会话ID")
    message_type = Column(String(10), nullable=False, comment="消息类型（user/ai）")
    content = Column(Text, nullable=False, comment="消息内容")
    message_metadata = Column(JSON, comment="消息元数据（如推荐结果）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    round_id = Column(String(64), nullable=False, comment="轮次ID，同一轮问答共享")
    is_latest = Column(Boolean, server_default='1', comment="是否为最新版本")
    version = Column(BigInteger, server_default='1', comment="版本号，从1开始")

class ChatContext(Base):
    """对话上下文表"""
    __tablename__ = "chat_context"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, comment="用户ID（支持UUID格式）")
    session_id = Column(String(64), nullable=False, comment="会话ID")
    context_key = Column(String(64), nullable=False, comment="上下文键")
    context_value = Column(Text, nullable=False, comment="上下文值")
    expire_time = Column(DateTime, comment="过期时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

class IntentLog(Base):
    """意图识别日志表"""
    __tablename__ = "intent_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, comment="用户ID（支持UUID格式）")
    session_id = Column(String(64), nullable=False, comment="会话ID")
    query = Column(Text, nullable=False, comment="用户查询")
    intent = Column(String(64), nullable=False, comment="识别意图")
    entities = Column(JSON, comment="提取实体")
    confidence = Column(DECIMAL(5, 4), comment="置信度")
    response_time = Column(BigInteger, comment="响应时间（毫秒）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
