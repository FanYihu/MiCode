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
