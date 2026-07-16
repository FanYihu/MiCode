# Day 17：OpenAI-Compatible Client 与 config.toml

## 今日目标

把模型供应商配置从代码里拿出来，放进 `config.toml`。

现在市面上很多模型服务都兼容 OpenAI API，也就是它们通常都有：

```text
base_url
api_key
model
chat.completions.create(...)
```

所以我们不需要为每个供应商都写一个 client：

```text
OpenAITextClient
MimoTextClient
DeepSeekTextClient
QwenTextClient
...
```

更好的方式是写一个通用客户端：

```text
OpenAICompatibleTextClient
```

然后用配置决定它连接哪个供应商。

## 新结构

目标结构：

```text
config.toml
  -> load_config()
  -> OpenAICompatibleTextClient(config)
  -> TextLLM(client)
  -> MiniCodeAgent
```

Agent 仍然不关心模型供应商。

它只知道：

```python
llm.next_action(task, observations)
```

## config.toml 示例

建议在项目根目录创建：

```text
minicode/config.toml
```

内容：

```toml
[llm]
provider = "mimo"
model = "mimo-v2.5-pro"
base_url = "https://api.xiaomimimo.com/v1"
api_key = "your_key_here"
```

学习项目里先直接把 key 写在 `config.toml`，方便你观察完整链路。

如果你想临时用 OpenAI：

```toml
[llm]
provider = "openai"
model = "gpt-5.5"
base_url = "https://api.openai.com/v1"
api_key = "your_key_here"
```

## 为什么 provider 还要保留

如果大家都兼容 OpenAI API，理论上只要 `base_url / api_key / model` 就够了。

但保留 `provider` 有三个好处：

- trace 或日志里能看出本次用了哪个供应商
- 后面某个供应商有特殊参数时，可以按 provider 做小分支
- CLI 展示配置时更清楚

注意：`provider` 不再用来决定创建哪个 client 类。

它只是配置里的名字。

## 建议配置模型

可以先定义一个 dataclass：

```python
@dataclass
class LLMConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
```

它代表配置文件里的 `[llm]`。

## 读取 config.toml

Python 3.11 有内置 `tomllib`。

为了兼容 Python 3.9，可以写成：

```python
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
```

如果本地是 Python 3.9，需要安装 `tomli`；项目的 `pyproject.toml` 已经把它放进条件依赖。

读取函数：

```python
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
```

## 通用 Client

新增：

```python
class OpenAICompatibleTextClient:
    def __init__(self, config: LLMConfig) -> None:
        from openai import OpenAI

        self.provider = config.provider
        self.model = config.model
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
```

这就是通用层。

只要供应商兼容 OpenAI Chat Completions API，就能接进来。

## Factory

Factory 不再判断 provider：

```python
def create_llm_from_config(path: str = "config.toml") -> TextLLM:
    config = load_llm_config(path)
    client = OpenAICompatibleTextClient(config)
    return TextLLM(client)
```

关系变成：

```text
config.toml 决定 provider/model/base_url/key
OpenAICompatibleTextClient 负责真实请求
TextLLM 负责 prompt -> text -> AgentAction
MiniCodeAgent 负责执行 action
```

## 后续升级：原生 Tool Calls

当前真实模型调用已不再要求模型把工具调用伪装成正文 JSON，而是使用 OpenAI-compatible Chat Completions 的独立字段：

```python
response = client.chat.completions.create(
    model=self.model,
    messages=messages,
    tools=registry.openai_tools(),
    tool_choice="auto",
)
```

工具链路变为：

```text
ToolDefinition.parameters
  -> ToolRegistry.openai_tools()
  -> request.tools
  -> response.message.tool_calls
  -> AgentAction
  -> ToolRegistry.call()
```

每个 `ToolDefinition` 通过 `parameters` 保存 JSON Schema。真实 OpenAI-compatible client 优先使用原生 `tool_calls`；旧的正文 JSON action 解析仍保留，供 MockLLM、测试和不支持 tools 的 client 使用。

当前 Agent 仍按一轮一个工具调用执行。模型一次返回多个 `tool_calls` 时会明确报错，避免只执行第一个调用造成行为不完整；批量和并行执行将在独立执行策略中实现。

## 完整 OpenAI-compatible 消息协议

原生工具调用不能只解析第一次响应，还必须把模型调用和工具结果放回下一次请求：

```text
user message
  -> assistant message(tool_calls)
  -> tool message(tool_call_id + content)
  -> assistant message(final text or next tool_calls)
```

当前实现拆成三层：

```text
ToolRegistry
  负责工具名称、描述、JSON Schema 和执行

OpenAICompatibleTextClient
  负责 messages/tools 请求、ModelTurn 解析和供应商能力适配

TextLLM
  负责保存 assistant/tool 消息，并把 ModelTurn 转成 AgentAction
```

通用响应结构：

```python
ModelTurn(
    text="",
    tool_calls=[
        ModelToolCall(
            id="call_123",
            name="read_file",
            arguments={"path": "README.md"},
        )
    ],
    assistant_message={...},
)
```

Agent 执行工具后调用：

```python
llm.record_tool_result(action, result.output)
```

它会追加：

```python
{
    "role": "tool",
    "tool_call_id": action.tool_call_id,
    "name": action.tool,
    "content": result.output,
}
```

## Provider Capabilities

OpenAI-compatible 只代表基础协议接近，不代表所有可选字段完全一致。供应商差异集中在配置中：

```toml
[llm.capabilities]
native_tools = true
parallel_tool_calls = false
reasoning_content = true
strict_tool_schema = false
```

- `native_tools`：是否使用独立 `tools/tool_calls`；关闭时退回正文 JSON action。
- `parallel_tool_calls`：供应商是否可能一次返回多个工具调用，执行层后续支持。
- `reasoning_content`：是否把思考模型返回的字段带回下一轮消息。
- `strict_tool_schema`：是否给 function tool 增加 `strict=true`。

这样接入其他 OpenAI-compatible 模型时，通常只需要修改 `config.toml`，不需要修改 Agent 和 Tool Registry。

## 批量 Tool Calls 执行策略

当供应商支持一轮返回多个 `tool_calls` 时，`TextLLM.next_turn()` 会返回：

```python
AgentTurn(
    actions=[
        AgentAction(tool="read_file", ...),
        AgentAction(tool="git_status", ...),
    ]
)
```

工具是否允许并行由 `ToolDefinition.parallel_safe` 声明，不在 Agent 中按名称判断：

```python
ToolDefinition(
    name="read_file",
    parallel_safe=True,
    ...
)
```

默认策略：

- `list_files`、`read_file`、`git_status`、`git_diff`、`load_skill` 是只读工具，可以并行。
- `replace_text`、`write_file`、`run_shell` 有副作用，必须串行。
- 连续出现的只读工具组成一个并行组。
- 写操作保持模型给出的顺序逐个执行。
- 写操作失败后，停止后续调用。
- 并行组中的调用会全部完成并分别记录结果。

混合批次示例：

```text
read_file A ┐
read_file B ┘ parallel
replace_text  sequential
run_shell     sequential
```

每个调用仍然拥有独立 Step 和 Event，并记录：

```text
batch_id
batch_index
batch_size
tool_call_id
execution_mode
```

所有工具结果按模型原始调用顺序追加为 `role=tool` 消息，再发起下一次模型请求。

### Python 线程池实现

MiniCode 的并行组通过 `concurrent.futures.ThreadPoolExecutor` 执行。

需要记住：

```text
ThreadPoolExecutor
    线程池管理器

executor.submit(fn, args...)
    把函数交给工作线程
    立即返回 Future

Future
    保存未来的结果或异常

future.result()
    等待并取得结果

with ThreadPoolExecutor(...)
    自动等待任务完成并关闭线程池
```

项目核心代码：

```python
with ThreadPoolExecutor(max_workers=len(indexed_actions)) as executor:
    futures = [
        executor.submit(
            self.tool_registry.call,
            action.tool,
            action.args,
        )
        for _, action in indexed_actions
    ]
    results = [
        future.result()
        for future in futures
    ]
```

`submit()` 连续提交任务后，多个 Worker 可以同时执行工具。主线程随后调用 `future.result()` 等待结果；等待某个 Future 时，其他工作线程仍在运行。

完整线程、GIL、Future、异常传播和 MiniCode 代码映射见：

```text
笔记/python多线程与线程池.md
```

## 你要手写的内容

建议改：

```text
minicode/src/minicode/agent.py
```

新增：

1. `LLMConfig`
2. `load_llm_config(path)`
3. `OpenAICompatibleTextClient`
4. `create_llm_from_config(path)`

建议创建：

```text
minicode/config.toml
```

但不要在里面写真实 key。

## 建议测试

新增：

```text
minicode/tests/test_llm_config.py
```

建议测试：

```text
1. load_llm_config 能读取 provider/model/base_url/api_key
2. create_llm_from_config 返回 TextLLM
3. OpenAICompatibleTextClient 不在测试中真实请求外部模型
```

测试配置可以写到临时目录：

```python
def test_load_llm_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '''
[llm]
provider = "mimo"
model = "mimo-v2.5-pro"
base_url = "https://api.xiaomimimo.com/v1"
api_key = "test-key"
''',
        encoding="utf-8",
    )

    config = load_llm_config(str(config_path))

    assert config.provider == "mimo"
    assert config.model == "mimo-v2.5-pro"
```

## 测试不要真实调用模型

默认单元测试不应该依赖：

- API key
- 网络
- 模型返回稳定性
- 调用费用

所以测试 `OpenAICompatibleTextClient` 时，可以 monkeypatch `openai.OpenAI`，或者先只测试配置读取和 factory 结构。

真实模型调用后面放到 CLI 手动运行里。

## 验收标准

1. 只有一个通用的 OpenAI-compatible client。
2. `provider / model / base_url / api_key` 来自 `config.toml`。
3. 源码里不写真实 API key。
4. `MiniCodeAgent` 不读取配置。
5. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 `provider` 不再适合用来决定创建哪个 client 类？

提示：当多个供应商都兼容同一种 API 时，差异主要是配置，不是代码结构。
