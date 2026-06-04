# Day 16：OpenAI Text Client

## 今日目标

实现一个真实 OpenAI 客户端适配层，让它能接到 Day 15 的 `TextLLM`。

前面已经有：

```text
TextLLM
  -> client.generate(prompt)
  -> parse_action(text)
  -> AgentAction
```

Day 16 要做的是把 `FakeTextClient` 换成真实客户端：

```text
OpenAITextClient.generate(prompt)
  -> OpenAI Responses API
  -> response.output_text
```

## 官方接口形状

当前 OpenAI Python SDK 的基础用法是：

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.5",
    input="Write a one-sentence bedtime story."
)

print(response.output_text)
```

SDK 会默认从环境变量读取 API key：

```bash
export OPENAI_API_KEY="your_api_key_here"
```

## 为什么还要包一层

不要让 `TextLLM` 直接依赖 OpenAI SDK。

我们希望 `TextLLM` 只知道：

```python
client.generate(prompt) -> str
```

这样：

- 测试时用 `FakeTextClient`
- 真实运行时用 `OpenAITextClient`
- 以后换模型或换供应商时，`MiniCodeAgent` 不需要改

## 建议新增类

先放在 `agent.py`：

```python
class OpenAITextClient:
    def __init__(self, model: str = "gpt-5.5") -> None:
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model

    def generate(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )
        return response.output_text
```

这里把 `from openai import OpenAI` 放在 `__init__` 里面，是为了让项目测试时不强制要求安装 OpenAI SDK。

## 使用方式

```python
workspace = Workspace("/path/to/project")
client = OpenAITextClient()
llm = TextLLM(client)
agent = MiniCodeAgent(workspace, llm)

trace = agent.run("读取 README 并总结")
```

执行链路：

```text
MiniCodeAgent
  -> TextLLM.next_action()
  -> build_action_prompt()
  -> OpenAITextClient.generate()
  -> response.output_text
  -> parse_action()
  -> AgentAction
  -> 执行工具
```

## 安装依赖

如果本地还没有安装：

```bash
pip install openai
```

如果要运行真实调用：

```bash
export OPENAI_API_KEY="your_api_key_here"
```

## 本章建议先不写真实 API 测试

真实 API 测试会受这些因素影响：

- 是否设置 API key
- 网络是否可用
- 模型输出是否稳定
- 调用是否产生费用

所以第一版只测试两件事：

1. `OpenAITextClient` 能保存 model。
2. `TextLLM` 仍然能用 `FakeTextClient` 跑通。

真实 API 可以后面通过一个手动脚本或 CLI 参数测试。

## 你要手写的内容

建议改：

```text
minicode/src/minicode/agent.py
```

新增：

```python
class OpenAITextClient:
    ...
```

建议新增测试：

```text
minicode/tests/test_openai_text_client.py
```

测试先不要真的请求 OpenAI。

## 验收标准

1. `OpenAITextClient` 提供 `generate(prompt) -> str`。
2. `TextLLM(OpenAITextClient())` 在结构上能成立。
3. 测试不依赖真实 API key。
4. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么真实 API 测试不应该直接放进默认单元测试？

提示：默认测试应该稳定、快速、低成本；真实模型调用更适合放到手动测试或集成测试里。

## 参考

- OpenAI Quickstart：Python SDK 使用 `OpenAI()`，通过 `client.responses.create(...)` 创建响应，并读取 `response.output_text`。
- OpenAI API Reference：Responses API 用于生成文本或 JSON 输出，也支持后续扩展到工具调用等 agentic workflow。
