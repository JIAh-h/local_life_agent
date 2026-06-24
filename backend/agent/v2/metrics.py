"""
监控指标收集模块

收集系统运行时的关键指标，包括：
1. 工具调用统计（成功/失败/延迟）
2. LLM调用统计（延迟/token使用）
3. 会话统计（活跃会话/消息数）
4. 系统健康指标
"""
import time
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """指标数据点"""
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Counter:
    """计数器指标"""
    name: str
    description: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    
    def inc(self, amount: float = 1.0):
        """增加计数"""
        self.value += amount
    
    def get(self) -> float:
        """获取当前值"""
        return self.value


@dataclass
class Histogram:
    """直方图指标"""
    name: str
    description: str
    buckets: list = field(default_factory=lambda: [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0])
    values: list = field(default_factory=list)
    sum: float = 0.0
    count: int = 0
    
    def observe(self, value: float):
        """观察一个值"""
        self.values.append(value)
        self.sum += value
        self.count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.values:
            return {
                "count": 0,
                "sum": 0,
                "avg": 0,
                "min": 0,
                "max": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0
            }
        
        sorted_values = sorted(self.values)
        count = len(sorted_values)
        
        return {
            "count": count,
            "sum": self.sum,
            "avg": self.sum / count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[int(count * 0.5)],
            "p95": sorted_values[int(count * 0.95)],
            "p99": sorted_values[int(count * 0.99)]
        }


class MetricsCollector:
    """
    指标收集器
    
    收集和管理系统运行时的关键指标。
    """
    
    def __init__(self):
        # 工具调用指标
        self.tool_calls_total = Counter(
            name="tool_calls_total",
            description="工具调用总数"
        )
        self.tool_calls_success = Counter(
            name="tool_calls_success",
            description="工具调用成功数"
        )
        self.tool_calls_failed = Counter(
            name="tool_calls_failed",
            description="工具调用失败数"
        )
        self.tool_call_duration = Histogram(
            name="tool_call_duration",
            description="工具调用延迟分布（秒）"
        )
        
        # LLM调用指标
        self.llm_calls_total = Counter(
            name="llm_calls_total",
            description="LLM调用总数"
        )
        self.llm_call_duration = Histogram(
            name="llm_call_duration",
            description="LLM调用延迟分布（秒）"
        )
        self.llm_tokens_used = Counter(
            name="llm_tokens_used",
            description="LLM token使用总数"
        )
        
        # 会话指标
        self.active_sessions = Counter(
            name="active_sessions",
            description="活跃会话数"
        )
        self.messages_processed = Counter(
            name="messages_processed",
            description="处理的消息总数"
        )
        
        # 技能路由指标
        self.skill_routes = Counter(
            name="skill_routes",
            description="技能路由总数"
        )
        self.skill_route_duration = Histogram(
            name="skill_route_duration",
            description="技能路由延迟分布（秒）"
        )
        
        # 错误指标
        self.errors_total = Counter(
            name="errors_total",
            description="错误总数"
        )
        self.errors_by_type: Dict[str, Counter] = defaultdict(
            lambda: Counter(name="", description="")
        )
        
        # 按工具名称统计
        self.tool_calls_by_name: Dict[str, Counter] = defaultdict(
            lambda: Counter(name="", description="")
        )
        
        logger.info("MetricsCollector initialized")
    
    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        duration: float,
        error: Optional[str] = None
    ):
        """记录工具调用"""
        self.tool_calls_total.inc()
        
        if success:
            self.tool_calls_success.inc()
        else:
            self.tool_calls_failed.inc()
            if error:
                error_type = self._classify_error(error)
                self.errors_by_type[error_type].inc()
        
        self.tool_call_duration.observe(duration)
        self.tool_calls_by_name[tool_name].inc()
    
    def record_llm_call(
        self,
        duration: float,
        tokens_used: Optional[int] = None
    ):
        """记录LLM调用"""
        self.llm_calls_total.inc()
        self.llm_call_duration.observe(duration)
        
        if tokens_used:
            self.llm_tokens_used.inc(tokens_used)
    
    def record_skill_route(
        self,
        skill_id: str,
        duration: float
    ):
        """记录技能路由"""
        self.skill_routes.inc()
        self.skill_route_duration.observe(duration)
    
    def record_error(
        self,
        error_type: str,
        error_message: str
    ):
        """记录错误"""
        self.errors_total.inc()
        self.errors_by_type[error_type].inc()
    
    def _classify_error(self, error: str) -> str:
        """分类错误类型"""
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            return "timeout"
        elif "connection" in error_lower:
            return "connection"
        elif "auth" in error_lower:
            return "authentication"
        elif "validation" in error_lower:
            return "validation"
        elif "not found" in error_lower:
            return "not_found"
        else:
            return "other"
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            "tool_calls": {
                "total": self.tool_calls_total.get(),
                "success": self.tool_calls_success.get(),
                "failed": self.tool_calls_failed.get(),
                "duration": self.tool_call_duration.get_stats(),
                "by_name": {
                    name: counter.get()
                    for name, counter in self.tool_calls_by_name.items()
                }
            },
            "llm_calls": {
                "total": self.llm_calls_total.get(),
                "duration": self.llm_call_duration.get_stats(),
                "tokens_used": self.llm_tokens_used.get()
            },
            "sessions": {
                "active": self.active_sessions.get(),
                "messages_processed": self.messages_processed.get()
            },
            "skill_routes": {
                "total": self.skill_routes.get(),
                "duration": self.skill_route_duration.get_stats()
            },
            "errors": {
                "total": self.errors_total.get(),
                "by_type": {
                    error_type: counter.get()
                    for error_type, counter in self.errors_by_type.items()
                }
            }
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        tool_stats = self.tool_call_duration.get_stats()
        llm_stats = self.llm_call_duration.get_stats()
        
        # 判断健康状态
        is_healthy = True
        issues = []
        
        # 检查错误率
        if self.tool_calls_total.get() > 0:
            error_rate = self.tool_calls_failed.get() / self.tool_calls_total.get()
            if error_rate > 0.1:  # 错误率超过10%
                is_healthy = False
                issues.append(f"High tool error rate: {error_rate:.2%}")
        
        # 检查延迟
        if tool_stats["p95"] > 10.0:  # P95延迟超过10秒
            is_healthy = False
            issues.append(f"High tool latency P95: {tool_stats['p95']:.2f}s")
        
        if llm_stats["p95"] > 30.0:  # P95延迟超过30秒
            is_healthy = False
            issues.append(f"High LLM latency P95: {llm_stats['p95']:.2f}s")
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "issues": issues,
            "timestamp": time.time(),
            "metrics": {
                "tool_calls_total": self.tool_calls_total.get(),
                "llm_calls_total": self.llm_calls_total.get(),
                "active_sessions": self.active_sessions.get(),
                "errors_total": self.errors_total.get()
            }
        }
    
    def reset(self):
        """重置所有指标"""
        self.tool_calls_total.value = 0
        self.tool_calls_success.value = 0
        self.tool_calls_failed.value = 0
        self.tool_call_duration.values.clear()
        self.tool_call_duration.sum = 0
        self.tool_call_duration.count = 0
        
        self.llm_calls_total.value = 0
        self.llm_call_duration.values.clear()
        self.llm_call_duration.sum = 0
        self.llm_call_duration.count = 0
        self.llm_tokens_used.value = 0
        
        self.active_sessions.value = 0
        self.messages_processed.value = 0
        
        self.skill_routes.value = 0
        self.skill_route_duration.values.clear()
        self.skill_route_duration.sum = 0
        self.skill_route_duration.count = 0
        
        self.errors_total.value = 0
        self.errors_by_type.clear()
        self.tool_calls_by_name.clear()
        
        logger.info("MetricsCollector reset")


# 全局单例
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器单例"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector():
    """重置指标收集器单例"""
    global _metrics_collector
    _metrics_collector = None


# 装饰器：自动记录函数调用指标
def track_tool_call(tool_name: str):
    """
    装饰器：自动记录工具调用指标
    
    Usage:
        @track_tool_call("search_places")
        async def search_places(params):
            # tool implementation
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            metrics = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                metrics.record_tool_call(tool_name, True, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_tool_call(tool_name, False, duration, str(e))
                raise
        
        return wrapper
    return decorator


def track_llm_call(func):
    """
    装饰器：自动记录LLM调用指标
    
    Usage:
        @track_llm_call
        async def chat(messages, **kwargs):
            # LLM implementation
            pass
    """
    async def wrapper(*args, **kwargs):
        metrics = get_metrics_collector()
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            metrics.record_llm_call(duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            metrics.record_llm_call(duration)
            raise
    
    return wrapper


def track_skill_route(func):
    """
    装饰器：自动记录技能路由指标
    
    Usage:
        @track_skill_route
        async def resolve(message):
            # resolver implementation
            pass
    """
    async def wrapper(*args, **kwargs):
        metrics = get_metrics_collector()
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            # 假设result有skill_id属性
            skill_id = getattr(result, 'skill_id', 'unknown')
            metrics.record_skill_route(skill_id, duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            metrics.record_skill_route('error', duration)
            raise
    
    return wrapper