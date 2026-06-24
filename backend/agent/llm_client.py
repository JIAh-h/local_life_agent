"""
LLM Client —— 统一的大模型调用层
支持阿里百炼 (DashScope)、小米 MiMo 等 OpenAI 兼容接口
"""
import json
import logging
import asyncio
from typing import Optional, AsyncGenerator

logger = logging.getLogger(__name__)

# ─── 提供商配置 ───
PROVIDER_CONFIGS = {
    "aliyun": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key": "DASHSCOPE_API_KEY",
    },
    "xiaomi": {
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "env_key": "XIAOMI_API_KEY",
    },
}

# ─── 系统提示词 ───
AGENT_SYSTEM_PROMPT = """你是「小紫薯」，一个专注于本地生活服务的 AI 助手。

## 核心能力
- 搜索和推荐附近美食、景点
- 规划出行路线（步行、公交、自驾）
- 查询天气信息
- 回答本地生活相关问题

## 回复风格
- 语气自然、友好、有帮助
- 回复简洁，不要太长
- 使用中文
- 如果用户的问题属于你的专业领域（本地生活、出行、美食、景点），尽可能给出有用建议
- 如果问题超出专业领域（编程、写作、科学等），礼貌告知你主要帮助本地生活服务，但仍可简短回答"""

CHITCHAT_SYSTEM_PROMPT = """你是「小紫薯」，一个友好的本地生活 AI 助手。

## 回复要求
- 用自然、口语化的中文回复
- 回复简短友好（1-3句话）
- 如果用户的问题与本地生活服务相关，主动引导用户使用服务（"您可以试试问我附近有什么好吃的"）
- 如果用户问的问题完全超出范围（编程、写代码、学术等），简短回答后引导回本地生活服务"""


class LLMClient:
    """大模型统一调用客户端"""

    def __init__(self):
        self._api_keys: dict[str, str] = {}
        self._default_provider = "aliyun"
        self._default_model = "deepseek-v4-flash"
        self._http_client = None

    def configure(self, api_keys: dict[str, str], default_provider: str = "aliyun",
                  default_model: str = "deepseek-v4-flash"):
        """配置 API Keys 和默认模型"""
        self._api_keys = {k: v for k, v in api_keys.items() if v}
        self._default_provider = default_provider
        self._default_model = default_model

    async def chat(
        self,
        messages: list[dict],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: list[dict] = None,
        tool_choice: str = "auto",
    ) -> dict:
        """
        调用 LLM 生成回复（非流式）
        messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
        tools: [{"type": "function", "function": {...}}]
        
        返回: {"content": "...", "tool_calls": [...]}
        """
        provider = provider or self._default_provider
        model = model or self._default_model
        config = PROVIDER_CONFIGS.get(provider)
        if not config:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

        api_key = self._api_keys.get(config["env_key"])
        if not api_key:
            raise ValueError(f"缺少 API Key: {config['env_key']}")

        base_url = config["base_url"]
        url = f"{base_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # 添加 function calling 支持
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                data = resp.json()

                if resp.status_code != 200:
                    error_msg = data.get("error", {}).get("message", str(data))
                    raise RuntimeError(f"LLM API 错误: {error_msg}")

                message = data["choices"][0]["message"]
                result = {
                    "content": message.get("content", "").strip() if message.get("content") else "",
                    "tool_calls": message.get("tool_calls", [])
                }
                
                if result["content"]:
                    logger.debug(f"LLM 回复 [{provider}/{model}]: {result['content'][:80]}...")
                elif result["tool_calls"]:
                    logger.debug(f"LLM 工具调用 [{provider}/{model}]: {len(result['tool_calls'])} 个工具")
                
                return result

        except httpx.HTTPError as e:
            raise RuntimeError(f"LLM 请求失败: {e}")

    async def chat_stream(
        self,
        messages: list[dict],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: list[dict] = None,
        tool_choice: str = "auto",
    ) -> AsyncGenerator[dict, None]:
        """
        调用 LLM 流式生成（SSE）
        yield: {"type": "content", "text": "..."} 或 {"type": "tool_calls", "tool_calls": [...]}
        """
        provider = provider or self._default_provider
        model = model or self._default_model
        config = PROVIDER_CONFIGS.get(provider)
        if not config:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

        api_key = self._api_keys.get(config["env_key"])
        if not api_key:
            raise ValueError(f"缺少 API Key: {config['env_key']}")

        base_url = config["base_url"]
        url = f"{base_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        # 添加 function calling 支持
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise RuntimeError(f"LLM 流式 API 错误: {body.decode()[:200]}")

                    tool_calls_buffer = []
                    current_tool_call = None
                    
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            # 如果有缓存的工具调用，yield 出去
                            if tool_calls_buffer:
                                yield {"type": "tool_calls", "tool_calls": tool_calls_buffer}
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            
                            # 处理普通内容
                            content = delta.get("content")
                            if content:
                                yield {"type": "content", "text": content}
                            
                            # 处理工具调用
                            tool_calls = delta.get("tool_calls")
                            if tool_calls:
                                for tc in tool_calls:
                                    tc_index = tc.get("index", 0)
                                    
                                    # 确保 buffer 足够大
                                    while len(tool_calls_buffer) <= tc_index:
                                        tool_calls_buffer.append({
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""}
                                        })
                                    
                                    # 更新工具调用信息
                                    if tc.get("id"):
                                        tool_calls_buffer[tc_index]["id"] = tc["id"]
                                    if tc.get("function", {}).get("name"):
                                        tool_calls_buffer[tc_index]["function"]["name"] = tc["function"]["name"]
                                    if tc.get("function", {}).get("arguments"):
                                        tool_calls_buffer[tc_index]["function"]["arguments"] += tc["function"]["arguments"]
                                        
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

        except httpx.HTTPError as e:
            raise RuntimeError(f"LLM 流式请求失败: {e}")


# 全局单例
llm_client = LLMClient()