from dataclasses import dataclass
import json
import os
from typing import Dict

from minicode.file_tools import FileTools
from minicode.models import EventType, Run, StepType
from minicode.permissions import PermissionDecision, PermissionReviewer
from minicode.shell_tools import CommandResult, ShellTools
from minicode.trace import TraceRecorder
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

#构建 LLM 输入提示语，包含任务描述和观察结果
def build_action_prompt(task: str, observations: list[str]) -> str:
    observation_text = "\n\n".join(observations) if observations else "None"

    return f"""
You are MiniCode's action generator.

Available tools:
- list_files: list workspace files, args={{}}
- read_file: read a file, args={{"path": "..."}}
- run_shell: run a shell command, args={{"command": "..."}}

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

    if action.tool == "list_files":
        return

    if action.tool == "read_file":
        if "path" not in action.args:
            raise InvalidAgentAction("read_file requires path")
        return

    if action.tool == "run_shell":
        if "command" not in action.args:
            raise InvalidAgentAction("run_shell requires command")
        return

    raise InvalidAgentAction(f"unknown tool: {action.tool}")     
       
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

    def next_action(self, task: str, observations: list[str]) -> AgentAction:
        prompt = build_action_prompt(task, observations)
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
    def __init__(self, workspace: Workspace, llm) -> None:
        self.workspace = workspace
        self.llm = llm

    def run(self, task: str) -> dict:
         # 创建运行实例和轨迹记录器
        run = Run()
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
          
          step = trace.add_step(StepType.TOOL,metadata={"tool": action.tool},)

          if action.tool == "list_files":
            result = self.workspace.list_files()
            observations.append("\n".join(result))
            trace.add_event(
               step,
               EventType.TEXT,
               content="\n".join(result),
               metadata={"files": result}, 
               )
                
          elif action.tool == "read_file":
            tool = FileTools(self.workspace)
            result = tool.read_file(action.args["path"])
            observations.append(result)
            trace.add_event(
                step,
                EventType.TEXT,
                content=result,
                metadata={"path": action.args["path"]},
                )
                
          elif action.tool == "run_shell":
            tool = ShellTools(self.workspace)
            review = PermissionReviewer().review_shell_command(action.args["command"])
            if review.decision == PermissionDecision.ALLOW:
                trace.add_event(
                    step,
                    EventType.TEXT,
                    content="开始运行命令..."
                )
            else:
                run.fail()
                trace.add_event(
                    step,
                    EventType.TEXT,
                    content="权限不足，无法运行命令"
                )
                return trace.to_dict()
            result : CommandResult = tool.run(action.args["command"])
            observations.append(result.stdout or result.stderr)
            trace.add_event(
                    step,
                    EventType.TEXT,
                    content=result.stdout,
                    metadata={
                        "command": action.args["command"],
                        "exit_code": result.exit_code,
                        "stderr": result.stderr,
                        "timed_out": result.timed_out
                    },
                )
          else:
            trace.add_event(step, EventType.ERROR, content=f"未知工具：{action.tool}")
            run.fail()
            return trace.to_dict()
        
        
        step = trace.add_step(StepType.FINAL)
        trace.add_event(step, EventType.ERROR, content="超过最大步骤数")
        run.fail()
        return trace.to_dict()  
        
        
           
     
    
