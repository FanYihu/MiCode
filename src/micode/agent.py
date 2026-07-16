from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import json
from typing import Dict, Optional

from micode.context.artifacts import ArtifactStore, maybe_store_tool_result_artifact
from micode.context.decision import freeze_decision
from micode.context.tokens import estimate_text_parts
from micode.context.tool_results import summarize_tool_result
from micode.models import EventType, Run, StepType
from micode.skills import (
    LLMSkillRouter,
    Skill,
    format_skill_summaries_for_prompt,
    merge_project_and_external_skills,
    route_external_skills,
    route_skills,
)
from micode.subagents import SubAgentExecutor, SubAgentPolicy
from micode.tools.default import create_default_tool_registry
from micode.tools.registry import ToolRegistry
from micode.trace import TraceRecorder
from micode.workspace import Workspace
import tomli as tomllib


@dataclass
class ProviderCapabilities:
    """OpenAI-compatible 供应商可选能力，避免在业务代码里判断 provider 名称。"""

    native_tools: bool = True
    parallel_tool_calls: bool = False
    reasoning_content: bool = False
    strict_tool_schema: bool = False


@dataclass
class LLMConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    capabilities: ProviderCapabilities = field(
        default_factory=ProviderCapabilities
    )
     
def load_llm_config(path: str = "config.toml") -> LLMConfig:
    with open(path, "rb") as file:
        data = tomllib.load(file)

    llm = data["llm"]
    capabilities = llm.get("capabilities", {})
    return LLMConfig(
        provider=llm["provider"],
        model=llm["model"],
        base_url=llm["base_url"],
        api_key=llm["api_key"],
        capabilities=ProviderCapabilities(
            native_tools=bool(capabilities.get("native_tools", True)),
            parallel_tool_calls=bool(
                capabilities.get("parallel_tool_calls", False)
            ),
            reasoning_content=bool(
                capabilities.get("reasoning_content", False)
            ),
            strict_tool_schema=bool(
                capabilities.get("strict_tool_schema", False)
            ),
        ),
    )


@dataclass
class ModelToolCall:
    """供应商无关的模型工具调用。"""

    id: str
    name: str
    arguments: dict
    raw_arguments: str = ""


@dataclass
class ModelTurn:
    """一次模型响应，统一承载最终文本、工具调用和供应商扩展信息。"""

    text: str = ""
    tool_calls: list[ModelToolCall] = field(default_factory=list)
    assistant_message: dict = field(default_factory=dict)
    reasoning_content: str = ""
    finish_reason: str = ""
    provider_metadata: dict = field(default_factory=dict)

@dataclass
class AgentAction:
    # 工具名称，例如 list_files、read_file、run_shell
    tool: str
    # 工具参数，例如 {"path": "README.md"} 或 {"command": "python3 -m pytest"}
    args: Dict[str, str]
    # 是否为最终回答；True 表示 Agent Loop 可以结束
    final: bool = False
    # 原生 tool_calls 返回的调用 id，后续完整消息协议会用它关联工具结果。
    tool_call_id: str = ""


@dataclass
class AgentTurn:
    """Agent 一轮决策，可包含最终回答或一批工具调用。"""

    actions: list[AgentAction] = field(default_factory=list)
    final_answer: str = ""

    @property
    def final(self) -> bool:
        return bool(self.final_answer) and not self.actions

# 定义异常类用于处理无效的 AgentAction 和解析错误
class InvalidAgentAction(ValueError):
    pass
class InvalidActionText(ValueError):
    pass
class LLMError(RuntimeError):
    pass


#解析文本生成作为工具的入参：AgentAction 对象：tool、args、final
def parse_action(text: str) -> AgentAction:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise InvalidActionText("action text must be valid json") from error

    if not isinstance(data, dict):
        raise InvalidActionText("action json must be an object")

    action = AgentAction(
        tool=data.get("tool", ""),
        args=data.get("args", {}),
        final=data.get("final", False),
    )

    validate_action(action)
    return action

DEFAULT_TOOL_DESCRIPTIONS = [
    "- list_files: list workspace files, args={}",
    '- read_file: read a file, args={"path": "..."}',
    '- replace_text: replace exact text once, args={"path": "...", "old": "...", "new": "..."}',
    '- run_shell: run a shell command, args={"command": "..."}',
]


#构建 LLM 输入提示语，包含任务描述和观察结果
def build_action_prompt(
    task: str,
    observations: list[str],
    tool_descriptions: Optional[list[str]] = None,
    skill_summaries: str = "",
    session_context: str = "",
    native_tools: bool = False,
) -> str:
    observation_text = "\n\n".join(observations) if observations else "None"
    tool_text = "\n".join(tool_descriptions or DEFAULT_TOOL_DESCRIPTIONS)
    skill_text = skill_summaries or "None"
    session_text = session_context or "None"

    output_instruction = (
        """
Use the provided function tools when a tool is needed.
When the task is complete, return the final answer as normal text.
Do not invent tool results.
""".strip()
        if native_tools
        else """
Return exactly one JSON object.
Do not return markdown.
Do not explain.

Tool action example:
{"tool":"read_file","args":{"path":"README.md"},"final":false}

Final answer example:
{"tool":"","args":{"answer":"任务完成"},"final":true}
""".strip()
    )

    return f"""
You are Micode's action generator.

Available tools:
{tool_text}

Available skill summaries:
{skill_text}

If a skill is useful, call load_skill with the skill name before following its full instructions.

Session context:
{session_text}

{output_instruction}

Task:
{task}

Observations:
{observation_text}
""".strip()
#验证 LLM 输出的指令
def validate_action(action: AgentAction) -> None:
    if not isinstance(action.args, dict):
        raise InvalidAgentAction("action args must be a dict")

    if action.final:
        return

    if not action.tool:
        raise InvalidAgentAction("action tool is required")

    # 工具是否存在、参数是否完整交给 ToolRegistry 和具体工具处理。
    return


def agent_turn_from_action(action: AgentAction) -> AgentTurn:
    """把旧的单 Action 契约适配成 AgentTurn。"""
    validate_action(action)
    if action.final:
        return AgentTurn(
            final_answer=action.args.get("answer", "任务完成")
        )
    return AgentTurn(actions=[action])
       
#模拟 LLMs 输出的指令，用于测试 Agent Loop 的执行逻辑
class MockLLM:
    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = actions
        self.index = 0

    def next_action(self, task: str, observations: list[str]) -> AgentAction:
        if self.index >= len(self.actions):
            return AgentAction(tool="", args={"answer": "任务完成"}, final=True)

        action = self.actions[self.index]
        self.index += 1
        return action
#将llm输出的指令转换成 AgentAction 对象
class TextLLM:
    def __init__(self, client) -> None:
        self.client = client
        self.tool_descriptions = DEFAULT_TOOL_DESCRIPTIONS
        self.skill_summaries = ""
        self.session_context = ""
        self.tool_definitions = []
        self.messages = []

    def set_tool_descriptions(self, tool_descriptions: list[str]) -> None:
        self.tool_descriptions = tool_descriptions

    def set_skill_summaries(self, skill_summaries: str) -> None:
        self.skill_summaries = skill_summaries

    def set_session_context(self, session_context: str) -> None:
        self.session_context = session_context

    def set_tool_definitions(self, tool_definitions: list[dict]) -> None:
        """设置提供给模型 API 的原生 function tools。"""
        self.tool_definitions = tool_definitions

    def reset_conversation(self) -> None:
        """开始新 Run 时清空模型级消息，Session 上下文仍由 prompt 注入。"""
        self.messages = []

    def next_turn(self, task: str, observations: list[str]) -> AgentTurn:
        """获取一轮模型决策；原生协议允许一次返回多个 tool_calls。"""
        capabilities = getattr(self.client, "capabilities", None)
        native_tools_enabled = (
            capabilities is None
            or capabilities.native_tools
        )
        supports_complete = (
            hasattr(self.client, "complete")
            and native_tools_enabled
        )
        supports_native_tools = (
            supports_complete
            or hasattr(self.client, "generate_action")
        )
        prompt = build_action_prompt(
            task,
            observations,
            self.tool_descriptions,
            self.skill_summaries,
            self.session_context,
            native_tools=supports_native_tools,
        )
        if supports_complete:
            if not self.messages:
                self.messages.append({"role": "user", "content": prompt})
            turn = self.client.complete(
                self.messages,
                self.tool_definitions,
            )
            self.messages.append(turn.assistant_message)
            if turn.tool_calls:
                actions = [
                    AgentAction(
                        tool=tool_call.name,
                        args=tool_call.arguments,
                        final=False,
                        tool_call_id=tool_call.id,
                    )
                    for tool_call in turn.tool_calls
                ]
                for action in actions:
                    validate_action(action)
                return AgentTurn(actions=actions)
            if not turn.text.strip():
                raise InvalidActionText(
                    "model response must contain a tool call or final answer"
                )
            return AgentTurn(final_answer=turn.text)
        if hasattr(self.client, "generate_action"):
            action = self.client.generate_action(prompt, self.tool_definitions)
            return agent_turn_from_action(action)

        # 兼容旧 client：仍使用正文 JSON action，不要求实现消息协议。
        text = self.client.generate(prompt)
        return agent_turn_from_action(parse_action(text))

    def next_action(self, task: str, observations: list[str]) -> AgentAction:
        """兼容旧调用方；批量调用应使用 next_turn()。"""
        turn = self.next_turn(task, observations)
        if turn.final:
            return AgentAction(
                tool="",
                args={"answer": turn.final_answer},
                final=True,
            )
        if len(turn.actions) != 1:
            raise InvalidAgentAction(
                "next_action requires exactly one tool call"
            )
        return turn.actions[0]

    def record_tool_result(self, action: AgentAction, output: str) -> None:
        """按原生协议把工具结果关联到对应 tool_call_id。"""
        if not action.tool_call_id or not hasattr(self.client, "complete"):
            return
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": action.tool_call_id,
                "name": action.tool,
                "content": output,
            }
        )

    def record_tool_results(self, results: list[tuple[AgentAction, str]]) -> None:
        """按模型返回顺序追加一批 role=tool 消息。"""
        for action, output in results:
            self.record_tool_result(action, output)

#创建一个兼容 OpenAPI 的 LLM 客户端
class OpenAICompatibleTextClient:
    def __init__(self, config: LLMConfig) -> None:
        from openai import OpenAI

        if not config.api_key:
            raise LLMError("missing api key in config.toml")

        self.api_key = config.api_key
        self.provider = config.provider
        self.model = config.model
        self.base_url = config.base_url
        self.capabilities = config.capabilities

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as error:
            raise LLMError(f"llm request failed: {error}") from error

        return response.choices[0].message.content or ""

    def complete(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ModelTurn:
        """执行一次 OpenAI-compatible Chat Completions 请求。"""
        request = {
            "model": self.model,
            "messages": messages,
        }
        if tools and self.capabilities.native_tools:
            request["tools"] = self._prepare_tools(tools)
            request["tool_choice"] = "auto"
            if self.capabilities.parallel_tool_calls:
                request["parallel_tool_calls"] = True

        try:
            response = self.client.chat.completions.create(**request)
        except Exception as error:
            raise LLMError(f"llm request failed: {error}") from error

        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None) or []
        parsed_calls = []
        serialized_calls = []
        for tool_call in tool_calls:
            function = tool_call.function
            raw_arguments = function.arguments or "{}"
            try:
                args = json.loads(raw_arguments)
            except json.JSONDecodeError as error:
                raise InvalidActionText(
                    "tool call arguments must be valid json"
                ) from error
            if not isinstance(args, dict):
                raise InvalidActionText(
                    "tool call arguments must be a json object"
                )
            call_id = getattr(tool_call, "id", "") or ""
            parsed_calls.append(
                ModelToolCall(
                    id=call_id,
                    name=function.name,
                    arguments=args,
                    raw_arguments=raw_arguments,
                )
            )
            serialized_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": function.name,
                        "arguments": raw_arguments,
                    },
                }
            )

        content = getattr(message, "content", None) or ""
        reasoning_content = (
            getattr(message, "reasoning_content", None) or ""
        )
        assistant_message = {
            "role": "assistant",
            "content": content or None,
        }
        if serialized_calls:
            assistant_message["tool_calls"] = serialized_calls
        if (
            reasoning_content
            and self.capabilities.reasoning_content
        ):
            # 小米等思考模型要求后续请求带回 reasoning_content。
            assistant_message["reasoning_content"] = reasoning_content

        return ModelTurn(
            text=content,
            tool_calls=parsed_calls,
            assistant_message=assistant_message,
            reasoning_content=reasoning_content,
            finish_reason=getattr(choice, "finish_reason", "") or "",
        )

    def generate_action(self, prompt: str, tools: list[dict]) -> AgentAction:
        """兼容旧调用方；新 Agent 通过 complete() 使用完整消息协议。"""
        turn = self.complete(
            [{"role": "user", "content": prompt}],
            tools,
        )
        if len(turn.tool_calls) > 1:
            raise InvalidAgentAction(
                "multiple native tool calls are not supported yet"
            )
        if turn.tool_calls:
            call = turn.tool_calls[0]
            return AgentAction(
                tool=call.name,
                args=call.arguments,
                final=False,
                tool_call_id=call.id,
            )
        if not turn.text.strip():
            raise InvalidActionText(
                "model response must contain a tool call or final answer"
            )
        return AgentAction(
            tool="",
            args={"answer": turn.text},
            final=True,
        )

    def _prepare_tools(self, tools: list[dict]) -> list[dict]:
        """按 provider capability 增加可选 strict 字段。"""
        if not self.capabilities.strict_tool_schema:
            return tools

        prepared = []
        for tool in tools:
            function = dict(tool.get("function", {}))
            function["strict"] = True
            prepared.append({**tool, "function": function})
        return prepared


def create_llm_from_config(path: str = "config.toml") -> TextLLM:
    config = load_llm_config(path)
    client = OpenAICompatibleTextClient(config)
    return TextLLM(client)


#创建一个模拟 LLM，用于测试
class FakeClient:
    def generate(self, prompt: str) -> str:
        return "{}".format(prompt)  



#主流程：MicodeAgent 类，负责执行任务并记录执行轨迹
class MicodeAgent:
    def __init__(
        self,
        workspace: Workspace,
        llm,
        tool_registry: Optional[ToolRegistry] = None,
        skills: Optional[list[Skill]] = None,
        project_skills: Optional[list[Skill]] = None,
        skill_router: Optional[LLMSkillRouter] = None,
        session_id: str = "",
        tool_result_budget_chars: int = 1200,
        artifact_dir: str = ".micode/artifacts",
        artifact_threshold_chars: int = 8000,
        prompt_cache_key: str = "",
        subagent_executor: Optional[SubAgentExecutor] = None,
        subagent_policy: Optional[SubAgentPolicy] = None,
    ) -> None:
        self.workspace = workspace
        self.llm = llm
        self.skills = skills or []
        self.project_skills = project_skills or []
        self.session_id = session_id
        self.tool_result_budget_chars = max(0, tool_result_budget_chars)
        self.artifact_threshold_chars = max(0, artifact_threshold_chars)
        self.artifact_store = ArtifactStore(artifact_dir)
        self.prompt_cache_key = prompt_cache_key
        self._active_run_id = ""
        self.tool_registry = tool_registry or create_default_tool_registry(
            workspace,
            external_skills=self.skills,
            artifact_dir=artifact_dir,
            subagent_executor=subagent_executor,
            subagent_policy=subagent_policy,
            subagent_parent_run_id_provider=lambda: self._active_run_id,
        )
        self.skill_router = skill_router
        if hasattr(self.llm, "set_tool_descriptions"):
            self.llm.set_tool_descriptions(self.tool_registry.describe_tools())
        if hasattr(self.llm, "set_tool_definitions"):
            self.llm.set_tool_definitions(self.tool_registry.openai_tools())

    def run(self, task: str) -> dict:
         # 创建运行实例和轨迹记录器
        run = Run()
        self._active_run_id = run.id
        run.metadata["task"] = task
        run.metadata["mode"] = "agent"
        if self.session_id:
            run.metadata["session_id"] = self.session_id
        run.metadata["token_estimate_strategy"] = "chars_per_token"

        # provider/model 属于整次模型驱动运行的上下文，记录在 Run metadata 里方便复盘。
        client = getattr(self.llm, "client", None)
        provider = getattr(client, "provider", "")
        model = getattr(client, "model", "")
        if provider:
            run.metadata["provider"] = provider
        if model:
            run.metadata["model"] = model

        selected_skills = self._select_skills(task)
        if selected_skills:
            run.metadata["skills"] = [skill.name for skill in selected_skills]
            skill_summaries = format_skill_summaries_for_prompt(selected_skills)
            if hasattr(self.llm, "set_skill_summaries"):
                self.llm.set_skill_summaries(skill_summaries)

        trace = TraceRecorder(run)
         
        # 标记任务开始执行
        run.start()
        if hasattr(self.llm, "reset_conversation"):
            self.llm.reset_conversation()
        observations = []
        # Agent Loop：一次模型轮次可以返回一个或多个工具调用。
        for turn_index in range(1, 10):
          run.metadata.setdefault("token_estimates", []).append(
              self._estimate_turn_tokens(task, observations, turn_index)
          )
          decision_freeze = freeze_decision(
              task,
              observations,
              session_context=getattr(self.llm, "session_context", ""),
              turn_index=turn_index,
              prompt_cache_key=self.prompt_cache_key,
          )
          run.metadata.setdefault("decision_freezes", []).append(
              decision_freeze.to_dict()
          )
          try:
            turn = self._next_turn(task, observations)
          except (LLMError, InvalidActionText, InvalidAgentAction) as error:
                step = trace.add_step(StepType.MODEL)
                trace.add_event(step, EventType.ERROR, content=str(error))
                run.fail()
                return trace.to_dict()
          if turn.final:
            step = trace.add_step(StepType.FINAL)
            run.complete()
            trace.add_event(
                step,
                EventType.TEXT,
                content=turn.final_answer,
            )
            return trace.to_dict()

          if not turn.actions:
            step = trace.add_step(StepType.MODEL)
            trace.add_event(
                step,
                EventType.ERROR,
                content="model turn contains no tool calls or final answer",
            )
            run.fail()
            return trace.to_dict()

          batch_ok = self._execute_tool_batch(
              turn.actions,
              batch_id=f"batch-{turn_index}",
              trace=trace,
              observations=observations,
          )
          if not batch_ok:
              run.fail()
              return trace.to_dict()
        
        step = trace.add_step(StepType.FINAL)
        trace.add_event(step, EventType.ERROR, content="超过最大步骤数")
        run.fail()
        return trace.to_dict()

    def _next_turn(self, task: str, observations: list[str]) -> AgentTurn:
        """兼容新批量 LLM 和旧单 Action LLM。"""
        if hasattr(self.llm, "next_turn"):
            return self.llm.next_turn(task, observations)
        return agent_turn_from_action(
            self.llm.next_action(task, observations)
        )

    def _estimate_turn_tokens(
        self,
        task: str,
        observations: list[str],
        turn_index: int,
    ) -> dict:
        """估算本轮模型决策前会注入的主要文本成本。"""
        tool_descriptions = "\n".join(
            getattr(self.llm, "tool_descriptions", [])
        )
        skill_summaries = getattr(self.llm, "skill_summaries", "")
        session_context = getattr(self.llm, "session_context", "")
        estimate = estimate_text_parts(
            {
                "task": task,
                "observations": "\n\n".join(observations),
                "session_context": session_context,
                "tool_descriptions": tool_descriptions,
                "skill_summaries": skill_summaries,
            }
        )
        return {
            "turn_index": turn_index,
            **estimate,
        }

    def _execute_tool_batch(
        self,
        actions: list[AgentAction],
        batch_id: str,
        trace: TraceRecorder,
        observations: list[str],
    ) -> bool:
        """按连续只读并行组和单个串行工具执行一批调用。"""
        completed = []
        total = len(actions)

        for parallel, indexed_actions in self._execution_groups(actions):
            actual_parallel = parallel and len(indexed_actions) > 1
            group_results = self._execute_tool_group(
                indexed_actions,
                parallel=actual_parallel,
            )
            for index, action, result in group_results:
                execution_mode = (
                    "parallel" if actual_parallel else "sequential"
                )
                step = trace.add_step(
                    StepType.TOOL,
                    metadata={
                        "tool": action.tool,
                        "args": action.args,
                        "tool_call_id": action.tool_call_id,
                        "batch_id": batch_id,
                        "batch_index": index,
                        "batch_size": total,
                        "execution_mode": execution_mode,
                    },
                )
                result_summary = summarize_tool_result(
                    action.tool,
                    result,
                    max_chars=self.tool_result_budget_chars,
                )
                artifact = maybe_store_tool_result_artifact(
                    self.artifact_store,
                    action.tool,
                    result,
                    threshold_chars=self.artifact_threshold_chars,
                    metadata={
                        "tool": action.tool,
                        "args": action.args,
                        "tool_call_id": action.tool_call_id,
                        "batch_id": batch_id,
                    },
                )
                artifact_text = f"\n\n{artifact.placeholder}" if artifact else ""
                observation_content = result_summary.content + artifact_text
                trace_content = (
                    observation_content
                    if artifact
                    else result.output
                )
                # 小结果直接写 Trace；超大结果写 Artifact，Trace 和模型消息只保留摘要引用。
                observations.append(observation_content)
                completed.append((action, observation_content))
                trace.add_event(
                    step,
                    EventType.TOOL_CALL if result.ok else EventType.ERROR,
                    content=trace_content,
                    metadata={
                        **result.metadata,
                        **result_summary.to_metadata(),
                        "artifact": artifact.to_metadata() if artifact else {},
                        "batch_id": batch_id,
                        "batch_index": index,
                        "batch_size": total,
                        "execution_mode": execution_mode,
                    },
                )

            # 并行组会等待组内全部完成；串行写操作失败后不再执行后续调用。
            if any(not result.ok for _, _, result in group_results):
                self._record_tool_results(completed)
                return False

        self._record_tool_results(completed)
        return True

    def _execution_groups(
        self,
        actions: list[AgentAction],
    ) -> list[tuple[bool, list[tuple[int, AgentAction]]]]:
        """保持模型调用顺序，把连续 parallel-safe 工具合成并行组。"""
        groups = []
        parallel_group = []

        for index, action in enumerate(actions):
            indexed_action = (index, action)
            if self.tool_registry.is_parallel_safe(action.tool):
                parallel_group.append(indexed_action)
                continue

            if parallel_group:
                groups.append((True, parallel_group))
                parallel_group = []
            groups.append((False, [indexed_action]))

        if parallel_group:
            groups.append((True, parallel_group))
        return groups

    def _execute_tool_group(
        self,
        indexed_actions: list[tuple[int, AgentAction]],
        parallel: bool,
    ) -> list[tuple[int, AgentAction, object]]:
        """执行一个工具组，并按模型原始顺序返回结果。"""
        if not parallel or len(indexed_actions) == 1:
            return [
                (
                    index,
                    action,
                    self.tool_registry.call(action.tool, action.args),
                )
                for index, action in indexed_actions
            ]

        with ThreadPoolExecutor(max_workers=len(indexed_actions)) as executor:
            futures = [
                executor.submit(
                    self.tool_registry.call,
                    action.tool,
                    action.args,
                )
                for _, action in indexed_actions
            ]
            return [
                (index, action, future.result())
                for (index, action), future in zip(indexed_actions, futures)
            ]

    def _record_tool_results(
        self,
        completed: list[tuple[AgentAction, str]],
    ) -> None:
        """将批量结果按 tool_call 顺序回传给模型消息历史。"""
        if hasattr(self.llm, "record_tool_results"):
            self.llm.record_tool_results(completed)
            return
        if hasattr(self.llm, "record_tool_result"):
            for action, output in completed:
                self.llm.record_tool_result(action, output)

    def _select_skills(self, task: str) -> list[Skill]:
        """进入 Agent loop 前选择 Skill Summary；项目级直接保留，外部层参与筛选。"""
        project_skill_names = {skill.name for skill in self.project_skills}
        external_skills = [
            skill
            for skill in self.skills
            if skill.name not in project_skill_names
        ]
        if not self.project_skills and not external_skills:
            return []

        filtered_external = route_external_skills(
            task,
            external_skills,
            self.skill_router,
        )
        if self.project_skills:
            return merge_project_and_external_skills(
                self.project_skills,
                filtered_external,
            )
        return route_skills(task, filtered_external)
        
        
           
     
    
