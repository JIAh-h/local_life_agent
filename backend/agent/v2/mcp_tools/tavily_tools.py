"""
Tavily 联网搜索工具实现

使用 Tavily MCP Server（Streamable HTTP 方式），基于 JSON-RPC 2.0 协议。
文档：https://docs.tavily.com/documentation/mcp
"""

import json
import logging
import uuid

import httpx

from ..deterministic import DeterministicTool, ToolResult
from .config import get_mcp_tools_config

logger = logging.getLogger(__name__)


class TavilyBaseTool(DeterministicTool):
    """Tavily 工具基类 - 使用 MCP Server 协议"""
    
    def __init__(self):
        self.config = get_mcp_tools_config().tavily
    
    def _parse_sse_response(self, sse_text: str) -> dict:
        """
        解析 SSE (Server-Sent Events) 格式的响应
        
        Args:
            sse_text: SSE 响应文本
            
        Returns:
            解析后的 JSON 数据
        """
        result = None
        for line in sse_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                data_str = line[6:]
                try:
                    result = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
        
        if result is None:
            raise Exception(f"无法解析 SSE 响应: {sse_text[:200]}")
        
        return result
    
    async def _call_mcp_tool(self, tool_name: str, params: dict) -> dict:
        """
        调用 Tavily MCP Server 工具（标准 MCP tools/call 协议）
        
        Args:
            tool_name: MCP 工具名称（如 tavily-search）
            params: 工具参数
            
        Returns:
            MCP 响应结果
        """
        request_id = str(uuid.uuid4())
        
        # 构建标准 MCP JSON-RPC 2.0 请求（使用 tools/call）
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            },
            "id": request_id
        }
        
        endpoint = self.config.mcp_endpoint
        
        # MCP Streamable HTTP 协议要求的请求头
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        # 抑制 httpx/httpcore 的 DEBUG 日志，避免泄露 URL 中的 API Key
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                # 根据响应 Content-Type 解析
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    result = self._parse_sse_response(response.text)
                else:
                    result = response.json()
        except httpx.HTTPStatusError as e:
            # HTTP 错误不暴露完整 URL（含 API Key）
            raise Exception(f"Tavily MCP Server HTTP 错误: {e.response.status_code}")
        except Exception as e:
            # 其他错误也不暴露完整 URL
            raise Exception(f"Tavily MCP Server 请求失败: {type(e).__name__}")
        
        # 检查 JSON-RPC 错误
        if "error" in result:
            error = result["error"]
            raise Exception(f"Tavily MCP Server 错误: {error.get('message', str(error))}")
        
        # 提取结果数据（tools/call 返回 result 中包含 content）
        if "result" in result:
            inner = result["result"]
            # 标准 MCP 工具调用返回格式：{"content": [{"type": "text", "text": "..."}]}
            if isinstance(inner, dict) and "content" in inner:
                for item in inner["content"]:
                    if item.get("type") == "text":
                        try:
                            return json.loads(item["text"])
                        except (json.JSONDecodeError, KeyError):
                            return item["text"]
                return inner
            return inner
        
        raise Exception(f"Tavily MCP Server 返回无效响应: {result}")


class TavilySearchTool(TavilyBaseTool):
    """Tavily 联网搜索工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "web.search"
    
    @property
    def description(self) -> str:
        return "联网搜索最新信息。当用户询问需要实时数据、新闻、天气、股票、最新事件等时使用此工具。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询词，应简洁明确"
                },
                "search_depth": {
                    "type": "string",
                    "enum": ["basic", "advanced"],
                    "description": "搜索深度：basic（快速）或 advanced（深入）",
                    "default": "basic"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10
                },
                "include_answer": {
                    "type": "boolean",
                    "description": "是否包含AI生成的答案摘要",
                    "default": True
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行 Tavily 搜索"""
        if not self.config or not self.config.api_key:
            return ToolResult(
                success=False,
                error="Tavily API Key 未配置"
            )
        
        query = kwargs.get("query")
        search_depth = kwargs.get("search_depth", "basic")
        max_results = kwargs.get("max_results", 5)
        include_answer = kwargs.get("include_answer", True)
        
        # MCP Server 参数格式（官方名称: tavily-search）
        mcp_params = {
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_content": False,
        }
        
        try:
            data = await self._call_mcp_tool("tavily-search", mcp_params)
            
            # 解析搜索结果
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0)
                })
            
            # 构建返回数据
            result_data = {
                "query": data.get("query", query),
                "answer": data.get("answer", ""),
                "results": results,
                "total": len(results)
            }
            
            logger.info(f"Tavily搜索成功: query='{query}', results={len(results)}")
            return ToolResult(success=True, data=result_data)
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Tavily MCP Server HTTP错误: {e.response.status_code}"
            logger.error(error_msg)
            return ToolResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Tavily搜索失败: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, error=error_msg)


class TavilyExtractTool(TavilyBaseTool):
    """Tavily 网页内容提取工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "web.extract"
    
    @property
    def description(self) -> str:
        return "提取指定网页的内容。用于获取搜索结果中某个网页的详细信息。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要提取内容的URL列表"
                }
            },
            "required": ["urls"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行网页内容提取"""
        if not self.config or not self.config.api_key:
            return ToolResult(
                success=False,
                error="Tavily API Key 未配置"
            )
        
        urls = kwargs.get("urls", [])
        if not urls:
            return ToolResult(
                success=False,
                error="URL列表不能为空"
            )
        
        # MCP Server 参数格式（官方名称: tavily-extract）
        mcp_params = {
            "urls": urls[:5]  # 限制最多5个URL
        }
        
        try:
            data = await self._call_mcp_tool("tavily-extract", mcp_params)
            
            # 解析提取结果
            results = []
            for item in data.get("results", []):
                results.append({
                    "url": item.get("url", ""),
                    "raw_content": item.get("raw_content", ""),
                    "success": item.get("success", True)
                })
            
            # 构建返回数据
            result_data = {
                "results": results,
                "total": len(results)
            }
            
            logger.info(f"Tavily提取成功: urls={len(urls)}, results={len(results)}")
            return ToolResult(success=True, data=result_data)
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Tavily MCP Server HTTP错误: {e.response.status_code}"
            logger.error(error_msg)
            return ToolResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Tavily提取失败: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, error=error_msg)
