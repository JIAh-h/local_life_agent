"""
MCP 结构化日志模块

为 MCP 工具的注册和调用提供结构化、可追踪、易检索的日志记录。

日志事件类型：
- mcp_registration: 工具注册阶段日志
- mcp_invocation:   工具调用阶段日志
- mcp_error:        异常/错误日志

所有日志均以 JSON 格式输出，兼容标准 Python logging 体系。

使用方式：
    from agent.v2.mcp_log import log_mcp_registration, log_mcp_invocation

    # 注册阶段
    log_mcp_registration("amap.place_around", status="success")

    # 调用阶段
    log_mcp_invocation(
        tool_name="amap.place_around",
        tool_args={"keywords": "餐厅"},
        status="success",
        result_data={"pois": [...]},
        duration_ms=150
    )
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# 使用统一的 logger 名称，便于日志收集和过滤
_mcp_logger = logging.getLogger("mcp.structured")


def _now_iso() -> str:
    """返回 ISO 8601 格式的 UTC 时间戳"""
    return datetime.now(timezone.utc).isoformat()


def _generate_call_id() -> str:
    """生成唯一的调用追踪 ID"""
    return uuid.uuid4().hex[:16]


def _safe_json_serializable(obj: Any, max_length: int = 2000) -> Any:
    """
    确保对象可以 JSON 序列化，并对过长内容截断。
    
    Args:
        obj: 待序列化对象
        max_length: 字符串最大长度（超过则截断）
    
    Returns:
        可 JSON 序列化的对象
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, str) and len(obj) > max_length:
            return obj[:max_length] + "...[truncated]"
        return obj
    if isinstance(obj, dict):
        return {k: _safe_json_serializable(v, max_length) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json_serializable(item, max_length) for item in obj]
    try:
        return _safe_json_serializable(obj.__dict__, max_length)
    except Exception:
        return str(obj)[:max_length]


# ============================================================
#  注册阶段日志
# ============================================================

def log_mcp_registration(
    tool_name: str,
    status: str,
    tool_category: Optional[str] = None,
    error: Optional[str] = None,
    total_registered: Optional[int] = None,
    total_attempted: Optional[int] = None,
):
    """
    记录 MCP 工具注册状态。

    Args:
        tool_name:       工具名称（如 "amap.place_around"）
        status:          "success" | "failure"
        tool_category:   工具类别（如 "amap", "tavily", "system"）
        error:           失败时的错误详情
        total_registered: 当前已成功注册的工具总数
        total_attempted:  本次尝试注册的工具总数
    """
    log_entry = {
        "event": "mcp_registration",
        "timestamp": _now_iso(),
        "tool_name": tool_name,
        "status": status,
    }

    if tool_category:
        log_entry["tool_category"] = tool_category
    if error:
        log_entry["error"] = error
    if total_registered is not None:
        log_entry["total_registered"] = total_registered
    if total_attempted is not None:
        log_entry["total_attempted"] = total_attempted

    if status == "success":
        _mcp_logger.info(json.dumps(log_entry, ensure_ascii=False))
    else:
        _mcp_logger.error(json.dumps(log_entry, ensure_ascii=False))


def log_mcp_registration_summary(
    total_registered: int,
    total_attempted: int,
    config_valid: bool,
    config_errors: Optional[list] = None,
):
    """
    记录 MCP 工具注册汇总。

    Args:
        total_registered: 成功注册的工具数
        total_attempted:  尝试注册的工具总数
        config_valid:     配置是否有效
        config_errors:    配置错误列表
    """
    log_entry = {
        "event": "mcp_registration_summary",
        "timestamp": _now_iso(),
        "total_registered": total_registered,
        "total_attempted": total_attempted,
        "config_valid": config_valid,
        "status": "success" if total_registered == total_attempted else "partial",
    }

    if config_errors:
        log_entry["config_errors"] = config_errors

    _mcp_logger.info(json.dumps(log_entry, ensure_ascii=False))


# ============================================================
#  调用阶段日志
# ============================================================

def log_mcp_invocation(
    tool_name: str,
    tool_args: Dict[str, Any],
    status: str,
    call_id: Optional[str] = None,
    result_data: Any = None,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
    session_id: Optional[str] = None,
    turn: Optional[int] = None,
):
    """
    记录 MCP 工具调用详情。

    Args:
        tool_name:    工具名称
        tool_args:    调用参数
        status:       "success" | "failure"
        call_id:      调用追踪 ID（不传则自动生成）
        result_data:  成功时的返回数据
        error:        失败时的错误信息
        duration_ms:  执行耗时（毫秒）
        session_id:   会话 ID
        turn:         ReAct 循环轮次
    """
    log_entry = {
        "event": "mcp_invocation",
        "timestamp": _now_iso(),
        "call_id": call_id or _generate_call_id(),
        "tool_name": tool_name,
        "tool_args": _safe_json_serializable(tool_args),
        "status": status,
    }

    if status == "success":
        log_entry["result_data"] = _safe_json_serializable(result_data)
    if error:
        log_entry["error"] = error
    if duration_ms is not None:
        log_entry["duration_ms"] = round(duration_ms, 2)
    if session_id:
        log_entry["session_id"] = session_id
    if turn is not None:
        log_entry["turn"] = turn

    if status == "success":
        _mcp_logger.info(json.dumps(log_entry, ensure_ascii=False))
    else:
        _mcp_logger.error(json.dumps(log_entry, ensure_ascii=False))


def log_mcp_invocation_start(
    tool_name: str,
    tool_args: Dict[str, Any],
    call_id: Optional[str] = None,
    session_id: Optional[str] = None,
    turn: Optional[int] = None,
) -> str:
    """
    记录 MCP 工具调用开始（DEBUG 级别）。
    
    Returns:
        call_id: 用于后续关联调用结果
    """
    cid = call_id or _generate_call_id()
    log_entry = {
        "event": "mcp_invocation_start",
        "timestamp": _now_iso(),
        "call_id": cid,
        "tool_name": tool_name,
        "tool_args": _safe_json_serializable(tool_args),
    }

    if session_id:
        log_entry["session_id"] = session_id
    if turn is not None:
        log_entry["turn"] = turn

    _mcp_logger.debug(json.dumps(log_entry, ensure_ascii=False))
    return cid


# ============================================================
#  JSON 日志格式化器（可选，用于 logging 配置）
# ============================================================

class MCPJsonFormatter(logging.Formatter):
    """
    JSON 日志格式化器。
    
    将标准 logging.LogRecord 中的 message 解析为 JSON，
    并附加额外的上下文字段（logger 名称、级别、模块等）。
    
    使用方式：
        handler = logging.StreamHandler()
        handler.setFormatter(MCPJsonFormatter())
        logging.getLogger("mcp.structured").addHandler(handler)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # 尝试将 message 解析为 JSON（我们的日志已经是 JSON 字符串）
        try:
            log_data = json.loads(record.getMessage())
        except (json.JSONDecodeError, ValueError):
            # 如果不是 JSON，包装为标准结构
            log_data = {
                "event": "raw_log",
                "message": record.getMessage(),
            }
        
        # 附加标准日志上下文
        log_data.setdefault("timestamp", _now_iso())
        log_data["level"] = record.levelname
        log_data["logger"] = record.name
        log_data["module"] = record.module
        log_data["line"] = record.lineno
        
        # 如果有异常信息
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


# ============================================================
#  便捷配置函数
# ============================================================

def setup_mcp_logging(level: int = logging.INFO):
    """
    快速配置 MCP 结构化日志。
    
    为 "mcp.structured" logger 添加 JSON 格式的 StreamHandler。
    
    Args:
        level: 日志级别，默认 INFO
    """
    mcp_logger = logging.getLogger("mcp.structured")
    
    # 避免重复添加 handler
    if mcp_logger.handlers:
        return
    
    mcp_logger.setLevel(level)
    mcp_logger.propagate = False  # 不传播到 root logger，避免重复输出
    
    handler = logging.StreamHandler()
    handler.setFormatter(MCPJsonFormatter())
    mcp_logger.addHandler(handler)
