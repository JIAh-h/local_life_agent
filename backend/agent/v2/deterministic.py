"""
Deterministic Code - 确定性执行工具层

Fat Skills 架构的核心组件之一。
职责：
1. 提供确定性、可重复的执行能力
2. 将判断力交由大模型，将执行力交由传统代码
3. 根除幻觉，确保同样的输入产生同样的输出

设计原则：
- 确定性：同样输入 → 同样输出
- 可验证：所有操作可审计
- 安全性：限制危险操作
- 可观测：记录所有调用
"""
import json
import time
import logging
from typing import Any, Dict, List, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from .mcp_log import log_mcp_invocation

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: str = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> dict:
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class DeterministicTool(ABC):
    """
    确定性工具基类
    
    所有确定性工具必须继承此类，确保：
    1. 同样输入产生同样输出
    2. 无副作用或副作用可控
    3. 可审计、可回滚
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> dict:
        """参数定义（JSON Schema格式）"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            ToolResult
        """
        pass
    
    def validate_parameters(self, params: dict) -> tuple[bool, str]:
        """
        验证参数
        
        Args:
            params: 待验证参数
            
        Returns:
            (是否有效, 错误信息)
        """
        required = self.parameters.get("required", [])
        properties = self.parameters.get("properties", {})
        
        # 检查必填参数
        for field in required:
            if field not in params:
                return False, f"缺少必填参数: {field}"
        
        # 检查参数类型
        for key, value in params.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type and not self._check_type(value, expected_type):
                    return False, f"参数 {key} 类型错误，期望 {expected_type}"
        
        return True, ""
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查类型"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        expected = type_map.get(expected_type)
        if expected:
            return isinstance(value, expected)
        return True
    
    def to_definition(self) -> dict:
        """转换为工具定义（用于LLM function calling）"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class ToolRegistry:
    """
    确定性工具注册表
    
    管理所有确定性工具，提供：
    1. 工具注册和发现
    2. 工具执行和结果处理
    3. 调用日志和审计
    """
    
    def __init__(self):
        self._tools: Dict[str, DeterministicTool] = {}
        self._call_log: List[Dict] = []
    
    def register(self, tool: DeterministicTool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"注册确定性工具: {tool.name}")
    
    def register_many(self, tools: List[DeterministicTool]):
        """批量注册工具"""
        for tool in tools:
            self.register(tool)
    
    def get_tool(self, name: str) -> Optional[DeterministicTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[dict]:
        """列出所有工具"""
        return [tool.to_definition() for tool in self._tools.values()]
    
    def get_definitions(self) -> List[dict]:
        """获取所有工具定义（用于LLM）"""
        return self.list_tools()
    
    async def execute(
        self,
        tool_name: str,
        parameters: dict,
        context: dict = None
    ) -> ToolResult:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            context: 执行上下文
            
        Returns:
            ToolResult
        """
        tool = self._tools.get(tool_name)
        if not tool:
            # 未知工具 — 结构化日志
            log_mcp_invocation(
                tool_name=tool_name,
                tool_args=parameters,
                status="failure",
                error=f"未知工具: {tool_name}",
                session_id=context.get("session_id") if context else None,
            )
            return ToolResult(
                success=False,
                error=f"未知工具: {tool_name}"
            )
        
        # 验证参数
        valid, error = tool.validate_parameters(parameters)
        if not valid:
            # 参数校验失败 — 结构化日志
            log_mcp_invocation(
                tool_name=tool_name,
                tool_args=parameters,
                status="failure",
                error=error,
                session_id=context.get("session_id") if context else None,
            )
            return ToolResult(success=False, error=error)
        
        # 记录调用（内存日志，保持向后兼容）
        call_record = {
            "tool": tool_name,
            "parameters": parameters,
            "timestamp": datetime.now().isoformat(),
            "context": context
        }
        
        # 结构化日志：调用开始
        start_time = time.time()
        
        try:
            # 执行工具
            result = await tool.execute(**parameters)
            
            # 计算耗时
            duration_ms = (time.time() - start_time) * 1000
            
            # 记录结果（内存日志）
            call_record["success"] = result.success
            call_record["error"] = result.error
            self._call_log.append(call_record)
            
            # 结构化日志：调用结果
            log_mcp_invocation(
                tool_name=tool_name,
                tool_args=parameters,
                status="success" if result.success else "failure",
                result_data=result.data if result.success else None,
                error=result.error,
                duration_ms=duration_ms,
                session_id=context.get("session_id") if context else None,
            )
            
            return result
            
        except Exception as e:
            logger.error(f"工具执行异常: {tool_name} - {e}", exc_info=True)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # 内存日志
            call_record["success"] = False
            call_record["error"] = str(e)
            self._call_log.append(call_record)
            
            # 结构化日志：异常
            log_mcp_invocation(
                tool_name=tool_name,
                tool_args=parameters,
                status="failure",
                error=str(e),
                duration_ms=duration_ms,
                session_id=context.get("session_id") if context else None,
            )
            
            return ToolResult(
                success=False,
                error=f"工具执行异常: {str(e)}"
            )
    
    async def execute_batch(
        self,
        calls: List[Dict[str, Any]],
        context: dict = None
    ) -> List[ToolResult]:
        """
        批量执行工具
        
        Args:
            calls: 工具调用列表 [{"name": "...", "parameters": {...}}]
            context: 执行上下文
            
        Returns:
            结果列表
        """
        results = []
        for call in calls:
            result = await self.execute(
                tool_name=call.get("name", ""),
                parameters=call.get("parameters", {}),
                context=context
            )
            results.append(result)
        return results
    
    def get_call_log(self, limit: int = 100) -> List[Dict]:
        """获取调用日志"""
        return self._call_log[-limit:]


# ===== 示例确定性工具 =====

class DatabaseQueryTool(DeterministicTool):
    """数据库查询工具（示例）"""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
    
    @property
    def name(self) -> str:
        return "query_database"
    
    @property
    def description(self) -> str:
        return "执行SQL查询，获取数据"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL查询语句"
                },
                "params": {
                    "type": "object",
                    "description": "查询参数"
                }
            },
            "required": ["sql"]
        }
    
    async def execute(self, sql: str, params: dict = None) -> ToolResult:
        """执行SQL查询"""
        # 安全检查：只允许SELECT查询
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return ToolResult(
                success=False,
                error="只允许SELECT查询"
            )
        
        # 这里应该执行实际的数据库查询
        # 简化实现：返回模拟数据
        return ToolResult(
            success=True,
            data={"rows": [], "count": 0},
            metadata={"sql": sql, "params": params}
        )


class MathCalculationTool(DeterministicTool):
    """数学计算工具（示例）"""
    
    @property
    def name(self) -> str:
        return "calculate"
    
    @property
    def description(self) -> str:
        return "执行数学计算，支持基本运算和函数"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式"
                }
            },
            "required": ["expression"]
        }
    
    async def execute(self, expression: str) -> ToolResult:
        """执行数学计算"""
        try:
            # 安全的数学表达式求值
            # 只允许数字、运算符、基本函数
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in expression):
                return ToolResult(
                    success=False,
                    error="表达式包含非法字符"
                )
            
            # 使用eval（生产环境应使用更安全的方案）
            result = eval(expression)
            
            return ToolResult(
                success=True,
                data={"result": result}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"计算错误: {str(e)}"
            )


class DateTimeTool(DeterministicTool):
    """日期时间工具（示例）"""
    
    @property
    def name(self) -> str:
        return "get_datetime"
    
    @property
    def description(self) -> str:
        return "获取当前日期时间或进行日期计算"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["now", "add_days", "format"],
                    "description": "操作类型"
                },
                "date": {
                    "type": "string",
                    "description": "日期字符串（用于计算）"
                },
                "days": {
                    "type": "integer",
                    "description": "天数（用于add_days）"
                },
                "format": {
                    "type": "string",
                    "description": "输出格式"
                }
            },
            "required": ["operation"]
        }
    
    async def execute(self, operation: str, **kwargs) -> ToolResult:
        """执行日期时间操作"""
        from datetime import datetime, timedelta
        
        try:
            if operation == "now":
                return ToolResult(
                    success=True,
                    data={"datetime": datetime.now().isoformat()}
                )
            elif operation == "add_days":
                date_str = kwargs.get("date", datetime.now().isoformat())
                days = kwargs.get("days", 0)
                date = datetime.fromisoformat(date_str)
                new_date = date + timedelta(days=days)
                return ToolResult(
                    success=True,
                    data={"datetime": new_date.isoformat()}
                )
            elif operation == "format":
                date_str = kwargs.get("date", datetime.now().isoformat())
                fmt = kwargs.get("format", "%Y-%m-%d %H:%M:%S")
                date = datetime.fromisoformat(date_str)
                return ToolResult(
                    success=True,
                    data={"formatted": date.strftime(fmt)}
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"未知操作: {operation}"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )


# 全局单例
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        # 注册默认工具
        _tool_registry.register(DatabaseQueryTool())
        _tool_registry.register(MathCalculationTool())
        _tool_registry.register(DateTimeTool())
    return _tool_registry


def reset_tool_registry():
    """重置工具注册表"""
    global _tool_registry
    _tool_registry = None
