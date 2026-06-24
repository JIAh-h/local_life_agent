"""
对话历史服务公共模块
提供对话消息的保存、加载、会话管理等功能
"""
import json
import logging
import uuid
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Redis键前缀
_CHAT_KEY_PREFIX = "chat:assistant"
_INDEX_KEY_PREFIX = "chat:assistant:index"


def _ensure_user_id(user_id: Optional[str] = None) -> str:
    """校验 user_id，处理未登录或缺失的边界情况，生成UUID作为唯一标识符"""
    if user_id is None or user_id == "" or user_id == 0:
        # 生成一个新的UUID作为匿名用户标识
        new_uuid = str(uuid.uuid4())
        logger.warning(f"user_id 缺失，生成新的UUID: {new_uuid}")
        return new_uuid
    
    # 如果已经是有效的UUID格式，直接返回
    if isinstance(user_id, str):
        try:
            # 验证是否为有效的UUID格式
            uuid.UUID(user_id)
            return user_id
        except ValueError:
            # 不是有效的UUID格式，生成新的UUID
            new_uuid = str(uuid.uuid4())
            logger.warning(f"user_id 格式无效: {user_id}，生成新的UUID: {new_uuid}")
            return new_uuid
    
    # 如果是整数，转换为字符串（兼容旧数据）
    if isinstance(user_id, int) and user_id != 0:
        return str(user_id)
    
    # 其他情况，生成新的UUID
    new_uuid = str(uuid.uuid4())
    logger.warning(f"user_id 类型异常: {type(user_id)}，生成新的UUID: {new_uuid}")
    return new_uuid


def _chat_key(user_id: str, session_id: str) -> str:
    """生成绑定用户标识的 Redis key"""
    return f"{_CHAT_KEY_PREFIX}:{_ensure_user_id(user_id)}:{session_id}"


def _index_key(user_id: str) -> str:
    """生成用户会话索引 Redis key"""
    return f"{_INDEX_KEY_PREFIX}:{_ensure_user_id(user_id)}"


async def save_chat_message(
    user_id: str,
    session_id: str,
    message_type: str,
    content: str,
    message_metadata: dict = None,
    round_id: str = None,
    version: int = 1,
    db_session=None,
    redis_client=None
) -> str:
    """
    保存对话消息到 MySQL 和 Redis
    
    Args:
        user_id: 用户ID
        session_id: 会话ID
        message_type: 消息类型（user/ai）
        content: 消息内容
        message_metadata: 消息元数据
        round_id: 轮次ID（同一轮问答共享），如果未提供则自动生成
        version: 版本号，默认为1
        db_session: 数据库会话
        redis_client: Redis客户端
    
    Returns:
        round_id: 生成的轮次ID
    """
    from app.models.chat import ChatHistory
    
    user_id = _ensure_user_id(user_id)
    
    # 如果未提供 round_id，则生成新的
    if not round_id:
        round_id = f"{session_id}_{uuid.uuid4().hex[:12]}"
    
    # 1. 保存到 MySQL
    if db_session:
        try:
            chat_msg = ChatHistory(
                user_id=user_id,
                session_id=session_id,
                message_type=message_type,
                content=content,
                message_metadata=message_metadata,
                round_id=round_id,
                is_latest=1,
                version=version
            )
            db_session.add(chat_msg)
            db_session.commit()
        except Exception as e:
            logger.error(f"保存对话到MySQL失败: {e}")
            db_session.rollback()
    
    # 2. 更新 Redis 缓存
    if redis_client:
        try:
            cache_key = _chat_key(user_id, session_id)
            # 获取现有缓存
            cached = redis_client.get(cache_key)
            messages = json.loads(cached) if cached else []
            
            # 添加新消息
            messages.append({
                "id": int(datetime.now().timestamp() * 1000),
                "user_id": user_id,
                "session_id": session_id,
                "message_type": message_type,
                "content": content,
                "message_metadata": message_metadata,
                "round_id": round_id,
                "version": version,
                "created_at": datetime.now().isoformat()
            })
            
            # 保持最近100条消息
            if len(messages) > 100:
                messages = messages[-100:]
            
            # 更新缓存，TTL 24小时
            redis_client.setex(cache_key, 86400, json.dumps(messages, ensure_ascii=False))
            
            # 更新会话索引
            index_key = _index_key(user_id)
            session_index = redis_client.get(index_key)
            sessions = json.loads(session_index) if session_index else {}
            
            # 保留已存在的 first_question，如果是首次用户消息则记录
            existing = sessions.get(session_id, {})
            first_question = existing.get("first_question", "")
            if not first_question and message_type == "user":
                first_question = content[:100]
            
            sessions[session_id] = {
                "last_message": content[:100],
                "last_message_time": datetime.now().isoformat(),
                "message_count": len(messages),
                "first_question": first_question,
            }
            redis_client.setex(index_key, 86400, json.dumps(sessions, ensure_ascii=False))
        except Exception as e:
            logger.error(f"更新Redis缓存失败: {e}")
    
    return round_id


async def save_regenerate_version(
    user_id: str,
    session_id: str,
    round_id: str,
    content: str,
    message_metadata: dict = None,
    db_session=None,
    redis_client=None
) -> dict:
    """
    保存重新生成的AI回复版本
    
    流程：
    1. 查询该轮次的最大版本号
    2. 将旧版本的 is_latest 设为 0
    3. 保存新版本，is_latest = 1
    
    Returns:
        {"version": 新版本号, "round_id": 轮次ID}
    """
    from app.models.chat import ChatHistory
    
    user_id = _ensure_user_id(user_id)
    new_version = 1
    
    # 1. 更新 MySQL
    if db_session:
        try:
            # 查询该轮次的最大版本号
            max_version_result = db_session.query(
                ChatHistory.version
            ).filter(
                ChatHistory.round_id == round_id,
                ChatHistory.message_type == "ai"
            ).order_by(
                ChatHistory.version.desc()
            ).first()
            
            if max_version_result:
                new_version = max_version_result[0] + 1
            
            # 将旧版本的 is_latest 设为 0
            db_session.query(ChatHistory).filter(
                ChatHistory.round_id == round_id,
                ChatHistory.message_type == "ai",
                ChatHistory.is_latest == 1
            ).update({"is_latest": 0})
            
            # 保存新版本
            chat_msg = ChatHistory(
                user_id=user_id,
                session_id=session_id,
                message_type="ai",
                content=content,
                message_metadata=message_metadata,
                round_id=round_id,
                is_latest=1,
                version=new_version
            )
            db_session.add(chat_msg)
            db_session.commit()
            
            logger.info(f"保存重新生成版本: round_id={round_id}, version={new_version}")
        except Exception as e:
            logger.error(f"保存重新生成版本失败: {e}")
            db_session.rollback()
    
    # 2. 更新 Redis 缓存
    if redis_client:
        try:
            cache_key = _chat_key(user_id, session_id)
            cached = redis_client.get(cache_key)
            if cached:
                messages = json.loads(cached)
                
                # 找到旧版本并更新
                for msg in messages:
                    if msg.get("round_id") == round_id and msg.get("message_type") == "ai":
                        msg["is_latest"] = 0
                
                # 添加新版本
                messages.append({
                    "id": int(datetime.now().timestamp() * 1000),
                    "user_id": user_id,
                    "session_id": session_id,
                    "message_type": "ai",
                    "content": content,
                    "message_metadata": message_metadata,
                    "round_id": round_id,
                    "version": new_version,
                    "is_latest": 1,
                    "created_at": datetime.now().isoformat()
                })
                
                redis_client.setex(cache_key, 86400, json.dumps(messages, ensure_ascii=False))
        except Exception as e:
            logger.error(f"更新Redis缓存失败: {e}")
    
    return {"version": new_version, "round_id": round_id}


async def get_round_versions(
    user_id: str,
    round_id: str,
    db_session=None
) -> list:
    """
    获取指定轮次的所有AI回复版本
    
    Returns:
        [{"id": ..., "version": ..., "content": ..., "is_latest": ..., "created_at": ...}, ...]
    """
    from app.models.chat import ChatHistory
    
    versions = []
    
    if db_session:
        try:
            records = db_session.query(ChatHistory).filter(
                ChatHistory.round_id == round_id,
                ChatHistory.message_type == "ai"
            ).order_by(ChatHistory.version.asc()).all()
            
            versions = [
                {
                    "id": record.id,
                    "version": record.version,
                    "content": record.content,
                    "message_metadata": record.message_metadata,
                    "is_latest": bool(record.is_latest),
                    "created_at": record.created_at.isoformat() if record.created_at else None
                }
                for record in records
            ]
        except Exception as e:
            logger.error(f"获取轮次版本失败: {e}")
    
    return versions


async def get_round_id_by_message(
    user_id: str,
    message_id: int,
    db_session=None
) -> Optional[str]:
    """根据消息ID获取对应的 round_id"""
    from app.models.chat import ChatHistory
    
    if db_session:
        try:
            record = db_session.query(ChatHistory.round_id).filter(
                ChatHistory.id == message_id,
                ChatHistory.user_id == user_id
            ).first()
            return record[0] if record else None
        except Exception as e:
            logger.error(f"获取 round_id 失败: {e}")
    
    return None


async def load_chat_history(
    user_id: str,
    session_id: str = None,
    limit: int = 50,
    db_session=None,
    redis_client=None,
    compress: bool = True
) -> List[dict]:
    """加载对话历史，优先从Redis获取，降级到MySQL，支持自动压缩"""
    messages = []
    user_id = _ensure_user_id(user_id)
    
    # 1. 尝试从 Redis 获取
    if redis_client:
        try:
            if session_id:
                cache_key = _chat_key(user_id, session_id)
                cached = redis_client.get(cache_key)
                if cached:
                    messages = json.loads(cached)
                    logger.info(f"从Redis加载对话历史: {len(messages)} 条")
            else:
                # 获取所有会话的最新会话
                index_key = _index_key(user_id)
                session_index = redis_client.get(index_key)
                if session_index:
                    sessions = json.loads(session_index)
                    if sessions:
                        # 获取最近的会话
                        latest_session_id = max(sessions.keys(), key=lambda k: sessions[k].get("last_message_time", ""))
                        cache_key = _chat_key(user_id, latest_session_id)
                        cached = redis_client.get(cache_key)
                        if cached:
                            messages = json.loads(cached)
                            logger.info(f"从Redis加载最新会话对话历史: {len(messages)} 条")
        except Exception as e:
            logger.warning(f"从Redis加载对话历史失败: {e}")
    
    # 2. 降级到 MySQL
    if not messages and db_session:
        from collections import defaultdict
        
        try:
            from app.models.chat import ChatHistory
            from sqlalchemy import asc
            
            # 第一步：先加载用户消息（确定哪些轮次有效，以及时间顺序）
            user_query = db_session.query(ChatHistory).filter(
                ChatHistory.user_id == user_id,
                ChatHistory.message_type == "user"
            )
            if session_id:
                user_query = user_query.filter(ChatHistory.session_id == session_id)
            
            user_records = user_query.order_by(asc(ChatHistory.created_at)).limit(limit).all()
            
            if not user_records:
                logger.info("从MySQL加载对话历史: 无用户消息记录")
            else:
                # 第二步：获取这些轮次 round_id 列表
                round_ids = [r.round_id for r in user_records]
                
                # 第三步：加载这些轮次中最新版本的 AI 回复
                ai_records = db_session.query(ChatHistory).filter(
                    ChatHistory.round_id.in_(round_ids),
                    ChatHistory.message_type == "ai",
                    ChatHistory.is_latest == 1
                ).order_by(asc(ChatHistory.version)).all()
                
                # 第四步：按 round_id 分组，确保每轮 user 在前、ai 在后
                round_map = defaultdict(list)
                for r in user_records:
                    round_map[r.round_id].append(r)
                for r in ai_records:
                    if r.round_id in round_map:  # 只附加到有用户消息的轮次
                        round_map[r.round_id].append(r)
                
                # 按用户消息时间排序轮次
                sorted_round_ids = sorted(
                    round_map.keys(),
                    key=lambda rid: round_map[rid][0].created_at or datetime.min
                )
                
                messages = []
                for rid in sorted_round_ids:
                    records = round_map[rid]
                    # 先 user 后 ai（确保排序正确）
                    user_msgs = [r for r in records if r.message_type == "user"]
                    ai_msgs = [r for r in records if r.message_type == "ai"]
                    for record in user_msgs + ai_msgs:
                        messages.append({
                            "id": record.id,
                            "user_id": record.user_id,
                            "session_id": record.session_id,
                            "message_type": record.message_type,
                            "content": record.content,
                            "message_metadata": record.message_metadata,
                            "round_id": record.round_id,
                            "version": record.version,
                            "is_latest": bool(record.is_latest),
                            "created_at": record.created_at.isoformat() if record.created_at else None
                        })
                
                logger.info(f"从MySQL加载对话历史: {len(messages)} 条（{len(sorted_round_ids)} 轮）")
            
            # 回写 Redis 缓存
            if redis_client and messages:
                try:
                    target_session = session_id or messages[-1].get("session_id", "latest")
                    cache_key = _chat_key(user_id, target_session)
                    redis_client.setex(cache_key, 86400, json.dumps(messages, ensure_ascii=False))
                except Exception as e:
                    logger.warning(f"回写Redis缓存失败: {e}")
        except Exception as e:
            logger.error(f"从MySQL加载对话历史失败: {e}")
    
    # 3. 检查是否需要压缩（基于 128k token 阈值，仅当对话历史实际超过时才触发）
    if compress and messages:
        try:
            from agent.conversation_compressor import conversation_compressor
            target_session = session_id or messages[-1].get("session_id", "latest")
            messages = await conversation_compressor.compress_and_update(
                messages=messages,
                user_id=user_id,
                session_id=target_session,
                redis_client=redis_client
            )
        except Exception as e:
            logger.warning(f"对话压缩失败: {e}")
    
    return messages[-limit:] if limit and len(messages) > limit else messages


async def get_user_sessions(
    user_id: str,
    db_session=None,
    redis_client=None
) -> List[dict]:
    """获取用户的会话列表"""
    sessions = []
    user_id = _ensure_user_id(user_id)
    
    # 1. 尝试从 Redis 获取
    if redis_client:
        try:
            index_key = _index_key(user_id)
            session_index = redis_client.get(index_key)
            if session_index:
                sessions_data = json.loads(session_index)
                sessions = [
                    {
                        "session_id": sid,
                        "last_message": data.get("last_message", ""),
                        "last_message_time": data.get("last_message_time", ""),
                        "message_count": data.get("message_count", 0),
                        "first_question": data.get("first_question", ""),
                    }
                    for sid, data in sessions_data.items()
                ]
                sessions.sort(key=lambda x: x["last_message_time"], reverse=True)
                logger.info(f"从Redis加载会话列表: {len(sessions)} 个")
                return sessions
        except Exception as e:
            logger.warning(f"从Redis加载会话列表失败: {e}")
    
    # 2. 降级到 MySQL
    if db_session:
        try:
            from app.models.chat import ChatHistory
            from sqlalchemy import func, desc
            
            # 按 session_id 分组统计
            results = db_session.query(
                ChatHistory.session_id,
                func.max(ChatHistory.created_at).label('last_time'),
                func.count(ChatHistory.id).label('msg_count')
            ).filter(
                ChatHistory.user_id == user_id
            ).group_by(
                ChatHistory.session_id
            ).order_by(
                desc('last_time')
            ).limit(20).all()
            
            for row in results:
                # 获取最后一条消息内容
                last_msg = db_session.query(ChatHistory.content).filter(
                    ChatHistory.user_id == user_id,
                    ChatHistory.session_id == row.session_id
                ).order_by(desc(ChatHistory.created_at)).first()
                
                # 获取用户第一个问题
                first_question_msg = db_session.query(ChatHistory.content).filter(
                    ChatHistory.user_id == user_id,
                    ChatHistory.session_id == row.session_id,
                    ChatHistory.message_type == "user"
                ).order_by(ChatHistory.created_at).first()
                
                sessions.append({
                    "session_id": row.session_id,
                    "last_message": last_msg.content[:100] if last_msg else "",
                    "last_message_time": row.last_time.isoformat() if row.last_time else "",
                    "message_count": row.msg_count,
                    "first_question": first_question_msg.content[:100] if first_question_msg else "",
                })
            
            logger.info(f"从MySQL加载会话列表: {len(sessions)} 个")
        except Exception as e:
            logger.error(f"从MySQL加载会话列表失败: {e}")
    
    return sessions


async def delete_chat_history(
    user_id: str,
    session_id: str,
    db_session=None,
    redis_client=None
) -> dict:
    """删除指定会话的对话历史"""
    user_id = _ensure_user_id(user_id)
    
    # 1. 删除 MySQL 中的记录
    deleted = 0
    if db_session:
        try:
            from app.models.chat import ChatHistory
            deleted = db_session.query(ChatHistory).filter(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id
            ).delete()
            db_session.commit()
            logger.info(f"从MySQL删除对话历史: {deleted} 条")
        except Exception as e:
            logger.error(f"从MySQL删除对话历史失败: {e}")
            db_session.rollback()
    
    # 2. 删除 Redis 缓存
    if redis_client:
        try:
            cache_key = _chat_key(user_id, session_id)
            redis_client.delete(cache_key)
            
            # 更新会话索引
            index_key = _index_key(user_id)
            session_index = redis_client.get(index_key)
            if session_index:
                sessions = json.loads(session_index)
                if session_id in sessions:
                    del sessions[session_id]
                    redis_client.setex(index_key, 86400, json.dumps(sessions, ensure_ascii=False))
        except Exception as e:
            logger.error(f"从Redis删除对话历史失败: {e}")
    
    return {"message": "删除成功", "deleted_count": deleted}


async def delete_session(
    user_id: str,
    session_id: str,
    redis_client=None
) -> dict:
    """删除会话（仅Redis）"""
    user_id = _ensure_user_id(user_id)
    
    try:
        # 删除Redis缓存
        cache_key = _chat_key(user_id, session_id)
        redis_client.delete(cache_key)
        
        # 更新会话索引
        index_key = _index_key(user_id)
        session_index = redis_client.get(index_key)
        if session_index:
            sessions = json.loads(session_index)
            if session_id in sessions:
                del sessions[session_id]
                redis_client.setex(index_key, 86400, json.dumps(sessions, ensure_ascii=False))
        
        return {"message": "会话已删除", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        return {"message": "删除会话失败", "error": str(e)}