# Day 02：Run 状态机

## 今日目标

给 `Run` 增加状态流转规则，让一次任务不能随意改变状态。

Day 01 的 `Run` 只是一个数据容器。Day 02 要让它具备 Runtime 规则：

- 新任务从 `created` 开始
- 任务可以从 `created` 进入 `running`
- 运行中的任务可以 `completed`、`failed` 或 `cancelled`
- 已经结束的任务不能再次运行

## 为什么重要

Coding Agent 会执行文件修改、命令运行、人工确认等步骤。如果状态不受控，就可能出现：

- 已完成任务又继续调用工具
- 已取消任务还在执行命令
- 失败任务没有明确重试规则
- trace 记录和真实执行状态对不上

状态机就是 Runtime 的安全底座。

## 你要修改的文件

```text
minicode/
  src/
    minicode/
      models.py
  tests/
    test_models.py
```

如果你的测试文件现在叫 `test_modles.py`，建议先重命名为 `test_models.py`。

## 建议你手写的结构

在 `models.py` 里：

1. 新增一个异常类：

```python
class InvalidRunStatusTransition(Exception):
    ...
```

2. 在 `Run` 里新增方法：

```python
def start(self) -> None:
    ...

def complete(self) -> None:
    ...

def fail(self) -> None:
    ...

def cancel(self) -> None:
    ...
```

3. 每次状态变化时更新 `updated_at`。

## 状态流转规则

允许：

```text
created -> running
running -> completed
running -> failed
running -> cancelled
created -> cancelled
```

禁止：

```text
completed -> running
failed -> running
cancelled -> running
created -> completed
created -> failed
```

## 测试提示

新增这些测试：

- `test_run_can_start_from_created`
- `test_run_can_complete_from_running`
- `test_run_cannot_complete_before_start`
- `test_completed_run_cannot_start_again`
- `test_cancel_created_run`

测试异常可以这样写：

```python
import pytest

with pytest.raises(models.InvalidRunStatusTransition):
    run.complete()
```

## 验收标准

1. `Run().start()` 后状态变成 `running`。
2. `Run().start(); run.complete()` 后状态变成 `completed`。
3. `created` 状态不能直接 `complete()`。
4. `completed` 状态不能再次 `start()`。
5. 每次状态变化都会更新 `updated_at`。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 `created -> cancelled` 是允许的，但 `created -> failed` 不建议允许？

提示：取消通常来自用户主动中断；失败通常表示执行过程中发生了错误。
