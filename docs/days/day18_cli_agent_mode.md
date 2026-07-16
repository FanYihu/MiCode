# Day 18：CLI Agent Mode

## 今日目标

让命令行可以启动真正的 Agent Loop。

前面的 CLI 只支持固定任务：

```bash
python3 -m micode.cli "list files" --workspace .
python3 -m micode.cli "run tests" --workspace .
```

这类逻辑是程序员写死的分支。

Day 18 要新增一个 agent 模式：

```bash
python3 -m micode.cli agent "读取 README 并总结" --workspace . --config config.toml
```

这时流程变成：

```text
CLI
  -> Workspace
  -> create_llm_from_config(config.toml)
  -> MicodeAgent
  -> trace JSON
```

## 为什么要做 CLI Agent Mode

现在你的项目已经有：

- `MicodeAgent`
- `TextLLM`
- `OpenAICompatibleTextClient`
- `config.toml`
- `create_llm_from_config()`

但它们还没有被 CLI 串起来。

CLI Agent Mode 的价值是：你可以在终端里用真实模型跑一次完整闭环。

## 建议命令格式

为了不破坏旧命令，建议新增子命令：

```bash
python3 -m micode.cli fixed "list files" --workspace .
python3 -m micode.cli fixed "run tests" --workspace .
python3 -m micode.cli agent "读取 README 并总结" --workspace . --config config.toml
```

旧的 `run_task()` 可以先保留。

`fixed` 子命令调用旧逻辑。

`agent` 子命令调用新逻辑。

## 新增函数

建议在 `cli.py` 里新增：

```python
from micode.agent import MicodeAgent, create_llm_from_config


def run_agent_task(task: str, workspace_path: str, config_path: str) -> dict:
    workspace = Workspace(workspace_path)
    llm = create_llm_from_config(config_path)
    agent = MicodeAgent(workspace, llm)
    return agent.run(task)
```

它只负责把已有模块接起来。

不要在这里写模型调用细节。

## argparse 结构

建议用 subparser：

```python
parser = argparse.ArgumentParser(description="Micode CLI")
subparsers = parser.add_subparsers(dest="mode", required=True)

fixed_parser = subparsers.add_parser("fixed")
fixed_parser.add_argument("task")
fixed_parser.add_argument("--workspace", default=".")

agent_parser = subparsers.add_parser("agent")
agent_parser.add_argument("task")
agent_parser.add_argument("--workspace", default=".")
agent_parser.add_argument("--config", default="config.toml")
```

然后：

```python
if args.mode == "fixed":
    trace = run_task(args.task, args.workspace)
elif args.mode == "agent":
    trace = run_agent_task(args.task, args.workspace, args.config)
```

最后统一：

```python
print(json.dumps(trace, ensure_ascii=False, indent=2))
```

## 兼容旧命令

如果你想保留旧用法：

```bash
python3 -m micode.cli "list files" --workspace .
```

可以先不强制上 subparser。

学习项目里更推荐你这章直接使用子命令，因为它更清楚地区分：

```text
fixed：固定任务
agent：模型驱动任务
```

## 配置文件

项目根目录 `config.toml`：

```toml
[llm]
provider = "mimo"
model = "mimo-v2.5-pro"
base_url = "https://api.xiaomimimo.com/v1"
api_key_env = "MIMO_API_KEY"
```

终端设置：

```bash
export MIMO_API_KEY="your_key_here"
```

## 测试策略

默认测试不要真实调用模型。

所以测试 `run_agent_task()` 时，monkeypatch `create_llm_from_config()`：

```python
class SequenceLLM:
    def __init__(self):
        self.actions = [
            AgentAction(tool="list_files", args={}),
            AgentAction(tool="", args={"answer": "完成"}, final=True),
        ]
        self.index = 0

    def next_action(self, task, observations):
        action = self.actions[self.index]
        self.index += 1
        return action
```

测试里：

```python
monkeypatch.setattr("micode.cli.create_llm_from_config", lambda path: SequenceLLM())
```

这样可以验证 CLI Agent Mode 的连接逻辑，不会访问真实 API。

## 你要手写的内容

建议改：

```text
micode/src/micode/cli.py
```

新增：

1. `run_agent_task(task, workspace_path, config_path)`
2. `agent` 子命令
3. `fixed` 子命令

建议改：

```text
micode/tests/test_cli.py
```

新增 agent mode 测试。

## 验收标准

1. CLI 有 `fixed` 和 `agent` 两种模式。
2. `fixed` 模式继续支持 `list files` 和 `run tests`。
3. `agent` 模式通过 `create_llm_from_config()` 创建 LLM。
4. 单元测试不调用真实模型。
5. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/micode
PYTHONPATH=src python3 -m pytest
```

## 手动真实运行

设置 key：

```bash
export MIMO_API_KEY="your_key_here"
```

运行：

```bash
cd /Users/fanyihu/Desktop/技能学习/micode
PYTHONPATH=src python3 -m micode.cli agent "列出文件并总结项目结构" --workspace . --config config.toml
```

## 思考题

为什么 CLI 不应该自己解析 `config.toml` 并手动创建 `OpenAICompatibleTextClient`？

提示：CLI 是入口层，只负责参数解析和输出；模型配置应该交给 `create_llm_from_config()`。
