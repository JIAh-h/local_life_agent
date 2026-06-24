"""
Agent System v2 - Fat Skills 架构

设计原则：Thin Harness, Fat Skills
- Harness：精简的调度器，只负责路由、执行、返回
- Skills：业务逻辑下沉到Markdown文档
- Resolver：技能路由器，决策加载哪个Skill
- Deterministic：确定性工具层，根除幻觉

模块组成：
- reactor         : Thin Harness 核心（精简调度器）
- resolver        : 技能路由器
- skills_loader   : 技能加载器（从Markdown加载）
- deterministic   : 确定性工具层
- prompts         : 提示词管理器
- memory/         : 增强记忆系统

Skills 目录：
- skills/dining/  : 餐饮相关技能
- skills/general/ : 通用技能
"""
from .reactor import Reactor, ReactorConfig, get_reactor
from .resolver import Resolver, RouteResult, get_resolver
from .skills_loader import SkillLoader, SkillDefinition, get_skill_loader
from .deterministic import ToolRegistry, DeterministicTool, ToolResult, get_tool_registry
from .init_v2 import AgentSystemV2, init_agent_system
from .mcp_tools import get_mcp_tool_registry, MCPToolRegistry
from .memory import QdrantManager, get_qdrant_manager

__all__ = [
    # Reactor
    "Reactor", "ReactorConfig", "get_reactor",
    
    # Resolver
    "Resolver", "RouteResult", "get_resolver",
    
    # Skills
    "SkillLoader", "SkillDefinition", "get_skill_loader",
    
    # Deterministic
    "ToolRegistry", "DeterministicTool", "ToolResult", "get_tool_registry",
    
    # MCP Tools
    "MCPToolRegistry", "get_mcp_tool_registry",
    
    # Qdrant (v2 独立)
    "QdrantManager", "get_qdrant_manager",
    
    # System
    "AgentSystemV2", "init_agent_system",
]
__version__ = "2.4.0"
__architecture__ = "Thin Harness, Fat Skills"
