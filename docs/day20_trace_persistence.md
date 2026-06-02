# Day 20：Trace Persistence

## 今日目标

把每次运行的 trace 保存到文件。

现在 MiniCode 已经能返回 trace dict：

```text
MiniCodeAgent.run(task) -> dict
run_task(task, workspace) -> dict
```

但真实模型调试时，只在终端里看 JSON 不够方便。

Day 20 要做的是：

```text
trace dict -> JSON 文件
```

这样每次运行后都能复盘：

- 模型决定了什么 action
- 工具返回了什么 observation
- 哪一步失败了
- 错误是否发生在 model / tool / permission 阶段

## 建议保存位置

项目根目录下：

```text
.minicode/
  traces/
    2026-06-02T12-30-00Z.json
```

`.minicode` 是运行产物目录。

后面如果你使用 git，可以把它放进 `.gitignore`。

## 新增函数

建议新增文件：

```text
minicode/src/minicode/persistence.py
```

写一个函数：

```python
def save_trace(trace: dict, output_dir: str = ".minicode/traces") -> str:
    ...
```

它负责：

1. 创建目录
2. 生成文件名
3. 写入 JSON
4. 返回文件路径

## 建议实现

```python
import json
from datetime import datetime, timezone
from pathlib import Path


def save_trace(trace: dict, output_dir: str = ".minicode/traces") -> str:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = directory / f"{timestamp}.json"

    path.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(path)
```

## 接入 CLI

给 CLI 增加一个参数：

```bash
--save-trace
```

示例：

```bash
python3 -m minicode.cli agent "读取 README" --workspace . --config config.toml --save-trace
```

当用户加了 `--save-trace`：

```python
if args.save_trace:
    save_trace(trace)
```

为了方便看保存位置，可以把保存路径放进输出 JSON：

```python
trace["saved_trace_path"] = save_trace(trace)
```

## fixed 和 agent 都支持

建议两个模式都支持：

```bash
python3 -m minicode.cli fixed "list files" --workspace . --save-trace
python3 -m minicode.cli agent "读取 README" --workspace . --config config.toml --save-trace
```

## 你要手写的内容

新增：

```text
minicode/src/minicode/persistence.py
```

修改：

```text
minicode/src/minicode/cli.py
```

新增测试：

```text
minicode/tests/test_persistence.py
```

修改测试：

```text
minicode/tests/test_cli.py
```

## 建议测试

```text
1. save_trace 会创建 JSON 文件
2. 保存后的 JSON 内容和 trace 一致
3. CLI fixed 模式加 --save-trace 后输出 saved_trace_path
4. CLI agent 模式加 --save-trace 后输出 saved_trace_path
```

## 验收标准

1. trace 可以保存为 JSON 文件。
2. 保存目录不存在时会自动创建。
3. CLI 支持 `--save-trace`。
4. 不加 `--save-trace` 时保持原输出行为。
5. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 trace 保存应该放在 CLI 层，而不是直接写死在 `MiniCodeAgent.run()` 里？

提示：Agent 负责产生 trace；是否保存、保存到哪里，是运行入口的策略。
