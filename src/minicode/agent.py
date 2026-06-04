from dataclasses import dataclass
import json
import os
from typing import Dict, Optional

from minicode.models import EventType, Run, StepType
from minicode.trace import TraceRecorder
from minicode.tool_registry import ToolRegistry, create_default_tool_registry
from minicode.workspace import Workspace
import tomli as tomllib


@dataclass
class LLMConfig:
     provider: str
     model: str
     base_url: str
     api_key: str
     
def load_llm_config(path: str = "config.toml") -> LLMConfig:
     with open(path, "rb") as file:
        data = tomllib.load(file)

     llm = data["llm"]
     return LLMConfig(
        provider=llm["provider"],
        model=llm["model"],
        base_url=llm["base_url"],
        api_key=llm["api_key"],
      ) 

@dataclass
class AgentAction:
    # 工具名称，例如 list_files、read_file、run_shell
    tool: str
    # 工具参数，例如 {"path": "README.md"} 或 {"command": "python3 -m pytest"}
    args: Dict[str, str]
    # 是否为最终回答；True 表示 Agent Loop 可以结束
    final: bool = False

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
) -> str:
    observation_text = "\n\n".join(observations) if observations else "None"
    tool_text = "\n".join(tool_descriptions or DEFAULT_TOOL_DESCRIPTIONS)

    return f"""
You are MiniCode's action generator.

Available tools:
{tool_text}

Return exactly one JSON object.
Do not return markdown.
Do not explain.

Tool action example:
{{"tool":"read_file","args":{{"path":"README.md"}},"final":false}}

Final answer example:
{{"tool":"","args":{{"answer":"任务完成"}},"final":true}}

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

    def set_tool_descriptions(self, tool_descriptions: list[str]) -> None:
        self.tool_descriptions = tool_descriptions

    def next_action(self, task: str, observations: list[str]) -> AgentAction:
        prompt = build_action_prompt(task, observations, self.tool_descriptions)
        text = self.client.generate(prompt)
        return parse_action(text)         

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


def create_llm_from_config(path: str = "config.toml") -> TextLLM:
    config = load_llm_config(path)
    client = OpenAICompatibleTextClient(config)
    return TextLLM(client)


#创建一个模拟 LLM，用于测试
class FakeClient:
    def generate(self, prompt: str) -> str:
        return "{}".format(prompt)  



#主流程：MiniCodeAgent 类，负责执行任务并记录执行轨迹
class MiniCodeAgent:
    def __init__(
        self,
        workspace: Workspace,
        llm,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.workspace = workspace
        self.llm = llm
        self.tool_registry = tool_registry or create_default_tool_registry(workspace)
        if hasattr(self.llm, "set_tool_descriptions"):
            self.llm.set_tool_descriptions(self.tool_registry.describe_tools())

    def run(self, task: str) -> dict:
         # 创建运行实例和轨迹记录器
        run = Run()
        run.metadata["task"] = task
        run.metadata["mode"] = "agent"

        # provider/model 属于整次模型驱动运行的上下文，记录在 Run metadata 里方便复盘。
        client = getattr(self.llm, "client", None)
        provider = getattr(client, "provider", "")
        model = getattr(client, "model", "")
        if provider:
            run.metadata["provider"] = provider
        if model:
            run.metadata["model"] = model

        trace = TraceRecorder(run)
         
        # 标记任务开始执行
        run.start()
        observations = []
            # Agent Loop：不断调用 LLM 获取下一步指令，直到 final=True
        for a in range(1, 10):
          try:
            action = self.llm.next_action(task, observations)
            validate_action(action)
          except (LLMError, InvalidActionText, InvalidAgentAction) as error:
                step = trace.add_step(StepType.MODEL)
                trace.add_event(step, EventType.ERROR, content=str(error))
                run.fail()
                return trace.to_dict()
          if action.final:
            step = trace.add_step(StepType.FINAL)
            run.complete()
            trace.add_event(
                step,
                EventType.TEXT,
                content= action.args.get("answer", "任务完成"),
            )
            return trace.to_dict()
          
          step = trace.add_step(
              StepType.TOOL,
              metadata={"tool": action.tool, "args": action.args},
          )

          result = self.tool_registry.call(action.tool, action.args)
          observations.append(result.output)
          trace.add_event(
              step,
              EventType.TOOL_CALL if result.ok else EventType.ERROR,
              content=result.output,
              metadata=result.metadata,
          )
          if not result.ok:
            run.fail()
            return trace.to_dict()
        
        
        step = trace.add_step(StepType.FINAL)
        trace.add_event(step, EventType.ERROR, content="超过最大步骤数")
        run.fail()
        return trace.to_dict()  
        
        
           
     
    
