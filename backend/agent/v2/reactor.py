"""
Thin Harness - 精简的调度器核心

设计原则（Fat Skills架构）：
1. 代码量控制在200行左右
2. 只负责：状态机驱动、上下文管理、边界与安全控制
3. 不承载复杂业务逻辑
4. 业务逻辑下沉到Skills（Markdown文档）

职责：
- 运行ReAct循环状态机
- 管理上下文Token窗口
- 执行工具调用
- 守住安全边界
"""
import uuid
import time
import asyncio
import logging
from typing import Optional, AsyncGenerator, Union, Dict, Any

from .skills_loader import SkillLoader, get_skill_loader
from .resolver import Resolver, RouteResult, get_resolver
from .deterministic import ToolRegistry, get_tool_registry
from .memory import ContextAssembler
from .utils import retry
from .metrics import get_metrics_collector, track_tool_call, track_llm_call, track_skill_route
from .mcp_log import log_mcp_invocation
from ..llm_client import llm_client

logger = logging.getLogger(__name__)


class ReactorConfig:
    """Reactor配置"""
    max_turns: int = 10
    max_tokens: int = 4096
    temperature: float = 0.7
    enable_streaming: bool = True
    enable_memory: bool = True
    enable_skills: bool = True


class Reactor:
    """
    Thin Harness 核心
    
    极简调度器，只做三件事：
    1. 路由：Resolver选择Skill
    2. 执行：ReAct循环调用工具
    3. 返回：组装响应
    """
    
    def __init__(
        self,
        resolver: Resolver = None,
        memory_manager=None,
        tool_registry: ToolRegistry = None,
        context_assembler: ContextAssembler = None,
        config: ReactorConfig = None
    ):
        self.resolver = resolver or get_resolver()
        self.memory = memory_manager
        self.tool_registry = tool_registry or get_tool_registry()
        self.context_assembler = context_assembler or ContextAssembler()
        self.config = config or ReactorConfig()
        self.llm = llm_client
        self._llm_provider = None  # 用户选择的provider（覆盖默认值）
        self._llm_model = None     # 用户选择的model（覆盖默认值）
    
    async def process_message(
        self,
        user_message: str,
        session_id: str = None,
        user_id: str = None,
        location: dict = None,
        stream: bool = False,
        provider: str = None,
        model: str = None,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[dict, None]]:
        """
        处理用户消息（主入口）
        
        流程：
        1. 路由到合适的Skill
        2. 加载Skill上下文
        3. 执行ReAct循环
        4. 返回结果
        """
        # 记录本次使用的模型配置（将传递到所有LLM调用）
        self._llm_provider = provider
        self._llm_model = model

        session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        start_time = time.time()
        
        # 1. 路由：选择Skill
        route_result = await self.resolver.resolve(user_message)
        
        # 记录 skill 使用日志
        if route_result:
            logger.info(
                f"[Skill使用] 用户消息路由到技能: "
                f"skill_id={route_result.skill_id}, "
                f"skill_name={route_result.skill.name}, "
                f"confidence={route_result.confidence:.2f}, "
                f"strategy={route_result.strategy}, "
                f"reason={route_result.reason}, "
                f"session_id={session_id}, "
                f"user_id={user_id}"
            )
        else:
            logger.info(f"[Skill使用] 未匹配到任何技能, session_id={session_id}, user_id={user_id}")
        
        # 2. 加载Skill上下文
        skill_context = await self._load_skill_context(route_result)
        
        # 3. 注入当前位置信息到系统提示词（让AI知道用户在哪里）
        if location and location.get("latitude") and location.get("longitude"):
            loc_parts = [f"用户当前定位坐标: ({location['latitude']}, {location['longitude']})"]
            if location.get("address"):
                loc_parts.append(f"用户当前地址: {location['address']}")
            if location.get("city"):
                loc_parts.append(f"用户所在城市: {location['city']}")
            if location.get("district"):
                loc_parts.append(f"用户所在区: {location['district']}")
            loc_text = "\n".join(loc_parts)
            skill_context += f"\n\n## 当前用户位置\n{loc_text}"
        
        # 4. 执行处理
        if stream:
            return self._process_stream(
                user_message, session_id, skill_context, route_result, start_time
            )
        else:
            return await self._process_sync(
                user_message, session_id, skill_context, route_result, start_time
            )
    
    async def _load_skill_context(self, route_result: RouteResult) -> str:
        """加载Skill上下文"""
        if not route_result:
            return ""
        
        # 获取Skill的完整Markdown内容作为上下文
        skill_content = self.resolver.get_skill_full_content(route_result.skill_id)
        if skill_content:
            return f"\n\n## 当前技能: {route_result.skill.name}\n{skill_content}"
        return ""
    
    async def _process_sync(
        self,
        user_message: str,
        session_id: str,
        skill_context: str,
        route_result: RouteResult,
        start_time: float
    ) -> Dict[str, Any]:
        """同步处理"""
        metrics = get_metrics_collector()
        metrics.messages_processed.inc()
        
        try:
            # 获取历史上下文（异步方法）
            history = await self._get_history(session_id)
            
            # 构建消息
            messages = self._build_messages(user_message, skill_context, history)
            
            # ReAct循环
            reply = await self._react_loop(messages, session_id)
            
            # 保存对话（异步方法）
            await self._save_conversation(session_id, user_message, reply)
            
            return {
                "session_id": session_id,
                "reply": reply,
                "skill": route_result.skill.name if route_result else None,
                "confidence": route_result.confidence if route_result else 0,
                "meta": {
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "stream": False
                }
            }
        except Exception as e:
            logger.error(f"处理失败: {e}", exc_info=True)
            metrics.record_error("processing_error", str(e))
            return self._error_response(session_id, str(e), start_time)
    
    async def _process_stream(
        self,
        user_message: str,
        session_id: str,
        skill_context: str,
        route_result: RouteResult,
        start_time: float
    ) -> AsyncGenerator[dict, None]:
        """流式处理"""
        metrics = get_metrics_collector()
        metrics.messages_processed.inc()
        
        try:
            yield {"event": "start", "data": {"session_id": session_id}}
            
            # 获取历史上下文（异步方法）
            history = await self._get_history(session_id)
            
            # 构建消息
            messages = self._build_messages(user_message, skill_context, history)
            
            # ReAct循环（流式）
            full_reply = ""
            async for event in self._react_loop_stream(messages, session_id):
                yield event
                if event.get("event") == "content":
                    full_reply += event.get("data", {}).get("text", "")
            
            # 保存对话（异步方法）
            await self._save_conversation(session_id, user_message, full_reply)
            
            yield {
                "event": "done",
                "data": {
                    "session_id": session_id,
                    "skill": route_result.skill.name if route_result else None,
                    "meta": {"latency_ms": int((time.time() - start_time) * 1000)}
                }
            }
        except Exception as e:
            logger.error(f"流式处理失败: {e}", exc_info=True)
            metrics.record_error("streaming_error", str(e))
            yield {"event": "error", "data": {"message": str(e)}}
    
    def _build_messages(
        self,
        user_message: str,
        skill_context: str,
        history: list
    ) -> list:
        """构建消息列表（使用ContextAssembler智能管理token）"""
        system_prompt = self._build_system_prompt(skill_context)
        
        # 准备历史消息（包含用户当前输入）
        all_messages = history.copy() if history else []
        all_messages.append({"role": "user", "content": user_message})
        
        # 使用ContextAssembler智能组装上下文
        messages = self.context_assembler.assemble(
            system_prompt=system_prompt,
            messages=all_messages,
            context_info=skill_context
        )
        
        return messages
    
    def _build_system_prompt(self, skill_context: str) -> str:
        """构建系统提示词"""
        base_prompt = """你是一个生活探索家与本地生活好物推荐官，风格参考小红书（Xiaohongshu）。

## 📍 用户位置推断规则（重要！）
处理位置相关请求时，你需要**自主判断**应该使用哪个位置作为参考点。请按以下优先级顺序推理：

**优先级 1：从对话历史中提取地址**
- 首先仔细检查**整个对话历史**，查找之前是否已提到过用户的位置信息
- 位置线索包括：明确的地址、城市/区名称、地标名称（如"莲花山公园"）、GPS定位回复等
- 如果历史对话中已有地址信息（无论是以"我在XX"提问还是系统回复中给出），则**直接使用该地址作为参考位置**
- 不要重复询问用户已经告诉过你的位置信息

**优先级 2：使用系统提供的当前位置**
- 如果对话历史中**完全未涉及**任何位置信息（新对话的第一轮），则查找系统注入的 `## 当前用户位置` 区块
- 该区块包含：经纬度坐标、地址、城市、区
- 使用坐标调用 `amap.place_around` 等工具，地址名称用于自然地描述位置

**优先级 3：主动询问**
- 仅当对话历史中无位置信息、且系统中也未注入 `## 当前用户位置` 区块时，才向用户询问位置
- 询问时语气友好，给出选项引导（如"你在哪个城市/区域呢？"）

**⚠️ 关键：判断权完全在你。不要写死规则，根据实际对话上下文灵活决定使用哪个位置。**

## 🌟 回复格式要求（必须使用 Markdown）
请严格使用 **Markdown 格式** 输出回复，前端会渲染 Markdown 为富文本。

**📌 Markdown 排版规范**
- 使用 `##` 或 `###` 作为小标题（如：## 🔥 推荐理由、### 📍 地址信息）
- 用 `**加粗**` 突出关键信息（店名、价格、评分等）
- 用列表 `- xxx` 或 `1. xxx` 展示要点
- 适当使用引用块 `>` 来强调重要内容
- 如果有多个推荐，用分隔线 `---` 分隔

**✨ 小红书文案风格**
- 全文使用短句，每1-2句后换行，形成呼吸感
- 善用 Emoji 做段落点缀：🌟📌✨🔥💡🎯👀🍜🏛️🌊💖等
- 核心关键词用 Emoji 包裹或 **加粗** 提示
- 语气亲切自然，像朋友在分享一样
- 适当使用问句或感叹句增强互动感
- 最后可以加一句互动引导

**⚠️ 注意事项**
- 保持信息准确、内容真实、推荐可信
- 不能虚构店铺/价格/地址等关键信息
- 工具调用返回的数据必须如实呈现
- 不要改变回复内容的实质信息，仅调整呈现方式

## 🕐 日期时间回答规则（重要！）
- **你绝不能使用自己的知识回答日期、时间、星期几等问题**，因为你的训练数据可能已过时
- 当用户询问"今天几号"、"现在什么时间"、"星期几"等日期时间问题时：
  - **必须调用 `system.get_time` 工具**获取当前实际时间
  - 根据工具返回的真实数据来回答
  - 禁止回复任何你知识库中记住的日期

## 🌐 联网搜索智能路由规则
你需要智能判断用户问题是否需要联网搜索最新信息。请遵循以下规则：

**需要联网搜索的情况：**
1. 用户询问实时信息：天气、新闻、股票、汇率、赛事比分等
2. 用户询问最新事件：近期发生的新闻、活动、发布会等
3. 用户询问时效性内容：最新优惠、限时活动、当前营业状态等
4. 用户询问你不确定或可能已过时的信息：新开业的店铺、最新政策等
5. 用户明确要求"最新"、"现在"、"今天"、"最近"等时效性信息

**不需要联网搜索的情况：**
1. 用户询问本地生活推荐（餐厅、景点、商场等）→ 使用高德地图工具
2. 用户询问你的知识库中已有的信息（常识、历史、文化等）
3. 用户询问与时间无关的通用问题
4. 用户询问对话历史中已提到的信息
5. 用户询问日期时间 → 使用 `system.get_time` 工具（不要用联网搜索）

**联网搜索工具使用说明：**
- 使用 `web.search` 工具进行搜索，参数包括：
  - `query`: 搜索查询词，应简洁明确（必填）
  - `search_depth`: 搜索深度，"basic"（快速）或 "advanced"（深入），默认 "basic"
  - `max_results`: 最大返回结果数，默认 5
  - `include_answer`: 是否包含AI生成的答案摘要，默认 true
- 搜索结果会包含 `answer`（AI摘要）和 `results`（详细结果列表）
- 请基于搜索结果回答用户问题，确保信息准确、时效性强

**搜索结果整合规范：**
1. 优先使用搜索结果中的 `answer` 作为回复核心
2. 引用具体来源时，使用 `来源: [网站名](URL)` 格式
3. 如果搜索结果不相关或质量低，可以告知用户"根据最新搜索..."
4. 搜索结果应与你的回复风格（小红书风格）结合，保持亲切自然

## 🔧 工具自主调用规则（重要！）
你拥有以下工具，应根据用户意图和对话上下文**自主决定**是否调用：
- **自主判断**：不要等待用户明确要求"使用工具"，而是根据问题性质主动调用
- **组合调用**：复杂问题可连续调用多个工具（如先搜索POI再规划路线）
- **工具优先**：涉及实时数据、地理位置、天气等问题时，必须优先调用工具而非凭记忆回答
- **如实呈现**：工具返回的数据必须如实呈现，不得虚构或篡改

## 💬 对话上下文记忆（重要！）
- **位置记忆**：记住历史对话中用户提到或系统回复过的所有地点/地址/城市/区县信息
- **上下文关联**：当用户说"附近有什么"、"帮我看看周边"、"推荐美食"等，优先从历史对话中提取之前确认过的地址作为搜索中心点
- **连续性**：如果用户先说"我在XX"，接着说"附近有什么好玩的"，你必须将"XX"作为搜索位置，而不是重新问"你在哪"或使用系统注入的新坐标
- 保持对话的延续性和对历史上下文的完整记忆"""

        if skill_context:
            return base_prompt + skill_context
        return base_prompt

        if skill_context:
            return base_prompt + skill_context
        return base_prompt
    
    async def _react_loop(self, messages: list, session_id: str) -> str:
        """ReAct循环（非流式）"""
        metrics = get_metrics_collector()
        # 获取已注册的工具定义，让 LLM 能够基于上下文自主决定是否调用工具
        tools = self.tool_registry.get_definitions()
        
        for turn in range(self.config.max_turns):
            logger.debug(f"ReAct循环: turn={turn + 1}")
            
            start_time = time.time()
            try:
                response = await self._call_llm_with_retry(
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    tools=tools,
                    provider=self._llm_provider,
                    model=self._llm_model
                )
                
                # 记录LLM调用指标
                duration = time.time() - start_time
                metrics.record_llm_call(duration)
                
            except Exception as e:
                logger.error(f"LLM调用失败: {e}")
                # 记录失败的LLM调用
                duration = time.time() - start_time
                metrics.record_llm_call(duration)
                return "抱歉，AI服务暂时不可用，请稍后再试。"
            
            # 检查工具调用
            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                return response.get("content", "")
            
            # 执行工具并更新消息
            messages = await self._execute_tools(messages, response, tool_calls, session_id=session_id, turn=turn)
        
        return "抱歉，处理时间过长，请稍后再试。"
    
    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(RuntimeError, ConnectionError))
    async def _call_llm_with_retry(self, **kwargs) -> dict:
        """带重试的LLM调用"""
        return await self.llm.chat(**kwargs)
    
    async def _react_loop_stream(self, messages: list, session_id: str) -> AsyncGenerator[dict, None]:
        """
        ReAct循环（流式）- 思考过程过滤版
        
        策略：
        1. 中间轮次（有 tool_calls）：不流式输出 content，仅发送进度事件，
           LLM 的中间思考内容被积累在 messages 中供后续轮次使用，但不会暴露给前端。
        2. 最终轮次（无 tool_calls）：将完整的最终回答流式输出到前端。
        3. 大模型生成期间不中断其思考与计算过程。
        """
        BUFFER_SIZE = 50      # 流式输出缓冲区大小（字符数）
        FLUSH_INTERVAL = 0.1  # 流式刷新间隔（秒）
        tools = self.tool_registry.get_definitions()
        
        intermediate_turns_count = 0
        
        for turn in range(self.config.max_turns):
            tool_calls = []
            content_buffer = []
            stream_buffer = []  # 仅在最终轮次才填充
            last_flush_time = time.time()
            
            async for chunk in self.llm.chat_stream(
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                tools=tools,
                provider=self._llm_provider,
                model=self._llm_model
            ):
                if chunk["type"] == "content":
                    content_buffer.append(chunk["text"])
                    stream_buffer.append(chunk["text"])
                    
                    # 仅在最终轮次（尚不确定是否是最终）才刷新流式缓冲区
                    # 稍后根据是否有 tool_calls 决定是否真正输出
                    current_time = time.time()
                    buffer_text = "".join(stream_buffer)
                    
                    if (len(buffer_text) >= BUFFER_SIZE or 
                        current_time - last_flush_time >= FLUSH_INTERVAL):
                        stream_buffer.clear()  # 先清空（中间轮次最终会丢弃这些内容）
                        last_flush_time = current_time
                        
                elif chunk["type"] == "tool_calls":
                    tool_calls = chunk["tool_calls"]
                    # 有工具调用 → 当前是中间轮次，丢弃已有的流式缓冲
                    stream_buffer.clear()
                    # 发送工具调用事件让前端感知进度
                    for tc in tool_calls:
                        yield {"event": "tool_call", "data": tc}
            
            if not tool_calls:
                # 最终轮次：重新流式输出最终回答
                # 因为中间轮次的内容已被丢弃，这里对 LLM 的最终回答流做一次完整的流式输出
                logger.info(f"[ReAct] 最终轮次 (turn {turn})，中间思考轮次: {intermediate_turns_count}，开始流式输出最终回答")
                
                # 此时 messages 中已包含完整的对话上下文（含工具调用结果），
                # LLM 已在当前轮次生成了完整回答，我们需要将其流式输出
                # 策略：对已累积在 content_buffer 中的最终回答文本做分块输出
                final_text = "".join(content_buffer)
                if final_text:
                    # 以流式方式分块输出最终回答
                    for i in range(0, len(final_text), BUFFER_SIZE):
                        chunk_text = final_text[i:i + BUFFER_SIZE]
                        yield {"event": "content", "data": {"text": chunk_text}}
                        await asyncio.sleep(0.01)  # 模拟流式输出的微延迟
                return
            
            # 中间轮次：积累 LLM 内容到 messages 但不输出给前端
            intermediate_turns_count += 1
            
            # 发送 thinking 事件让前端显示进度
            tool_names = [tc.get("function", {}).get("name", "unknown") for tc in tool_calls]
            yield {"event": "thinking", "data": {"message": f"正在调用工具: {', '.join(tool_names)}"}}
            
            # 执行工具并更新消息
            messages = await self._execute_tools(messages, {"content": "".join(content_buffer), "tool_calls": tool_calls}, tool_calls, session_id=session_id, turn=turn)
            
            # 发送工具结果事件让前端感知进展
            for tc in tool_calls:
                tc_name = tc.get("function", {}).get("name", "")
                yield {"event": "tool_result", "data": {"tool_name": tc_name, "status": "completed"}}
        
        # ↓↓↓ 兜底：ReAct 循环耗尽所有轮次后，尝试让 LLM 生成一个最终回复 ↓↓↓
        if intermediate_turns_count > 0:
            logger.warning(
                f"[ReAct] ReAct 循环达到最大轮次 ({self.config.max_turns})，"
                f"中间思考轮次: {intermediate_turns_count}，将向 LLM 请求兜底回复"
            )
            try:
                fallback_response = await self.llm.chat(
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    tools=None,  # 不再提供工具，强制 LLM 直接回复
                    provider=self._llm_provider,
                    model=self._llm_model
                )
                fallback_text = fallback_response.get("content", "")
                if fallback_text:
                    logger.info(f"[ReAct] 兜底回复已生成，长度: {len(fallback_text)} 字符")
                    for i in range(0, len(fallback_text), BUFFER_SIZE):
                        chunk_text = fallback_text[i:i + BUFFER_SIZE]
                        yield {"event": "content", "data": {"text": chunk_text}}
                        await asyncio.sleep(0.01)
                    return
                else:
                    logger.warning("[ReAct] 兜底回复为空，发送默认提示")
            except Exception as e:
                logger.error(f"[ReAct] 兜底回复生成失败: {e}")
            
            # 兜底消息
            fallback_msg = "抱歉，处理时间过长，请尝试简化问题或稍后再试。"
            for i in range(0, len(fallback_msg), BUFFER_SIZE):
                yield {"event": "content", "data": {"text": fallback_msg[i:i + BUFFER_SIZE]}}
                await asyncio.sleep(0.01)
    
    async def _execute_tools(
        self,
        messages: list,
        response: dict,
        tool_calls: list,
        session_id: Optional[str] = None,
        turn: Optional[int] = None,
    ) -> list:
        """执行工具调用"""
        import json
        
        metrics = get_metrics_collector()
        
        # 添加assistant消息
        messages.append({
            "role": "assistant",
            "content": response.get("content", ""),
            "tool_calls": tool_calls
        })
        
        # 执行每个工具调用
        for tc in tool_calls:
            tool_name = tc.get("function", {}).get("name", "")
            tool_args_str = tc.get("function", {}).get("arguments", "{}")
            
            start_time = time.time()
            success = False
            error_msg = None
            
            try:
                # 解析参数
                tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                
                # 调用ToolRegistry执行（传递真实的 session_id 和 turn 信息）
                result = await self.tool_registry.execute(
                    tool_name=tool_name,
                    parameters=tool_args,
                    context={"session_id": session_id, "turn": turn}
                )
                
                # 将结果添加到消息
                if result.success:
                    success = True
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps(result.data, ensure_ascii=False) if result.data else "执行成功"
                    })
                else:
                    error_msg = result.error
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": f"工具执行失败: {result.error}"
                    })
                    
            except json.JSONDecodeError as e:
                logger.error(f"工具参数解析失败: {tool_name} - {e}")
                error_msg = str(e)
                # 结构化日志：参数解析失败
                log_mcp_invocation(
                    tool_name=tool_name,
                    tool_args={"raw": tool_args_str},
                    status="failure",
                    error=f"参数解析错误: {str(e)}",
                    session_id=session_id,
                    turn=turn,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": f"参数解析错误: {str(e)}"
                })
            except Exception as e:
                logger.error(f"工具执行异常: {tool_name} - {e}", exc_info=True)
                error_msg = str(e)
                # 结构化日志：执行异常
                log_mcp_invocation(
                    tool_name=tool_name,
                    tool_args={},
                    status="failure",
                    error=str(e),
                    session_id=session_id,
                    turn=turn,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": f"工具执行异常: {str(e)}"
                })
            finally:
                # 记录指标
                duration = time.time() - start_time
                metrics.record_tool_call(tool_name, success, duration, error_msg)
        
        return messages
    
    async def _get_history(self, session_id: str) -> list:
        """获取历史消息（异步方法）"""
        if self.memory and self.config.enable_memory:
            try:
                return await self.memory.get_recent_messages(session_id)
            except Exception as e:
                logger.warning(f"获取历史失败: {e}")
        return []
    
    async def _save_conversation(self, session_id: str, user_msg: str, reply: str):
        """保存对话（异步方法）"""
        if self.memory and self.config.enable_memory:
            try:
                await self.memory.save_message(session_id, {"role": "user", "content": user_msg})
                await self.memory.save_message(session_id, {"role": "assistant", "content": reply})
            except Exception as e:
                logger.warning(f"保存对话失败: {e}")
    
    def _error_response(self, session_id: str, error: str, start_time: float) -> dict:
        """错误响应"""
        return {
            "session_id": session_id,
            "reply": "抱歉，处理您的请求时遇到了问题。请稍后再试。",
            "skill": None,
            "confidence": 0,
            "meta": {
                "latency_ms": int((time.time() - start_time) * 1000),
                "stream": False,
                "error": error
            }
        }


# 全局单例
_reactor: Optional[Reactor] = None


def get_reactor(
    resolver: Resolver = None,
    memory_manager=None,
    tool_registry: ToolRegistry = None,
    context_assembler: ContextAssembler = None,
    config: ReactorConfig = None
) -> Reactor:
    """获取Reactor单例"""
    global _reactor
    if _reactor is None:
        _reactor = Reactor(resolver, memory_manager, tool_registry, context_assembler, config)
    return _reactor


def reset_reactor():
    """重置Reactor单例"""
    global _reactor
    _reactor = None
