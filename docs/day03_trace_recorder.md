# Day 03：Trace 记录器

## 今日目标

实现一个内存版 `TraceRecorder`，用来记录一次 Run 里发生过的 Step 和 Event。

前两章我们已经有：

- `Run`：一次任务
- `Step`：任务中的步骤
- `Event`：步骤里的事件
- Run 状态机：保护任务生命周期

今天要把它们串起来：

```text
Run
  Step 1
    Event 1
    Event 2
  Step 2
    Event 3
```

## 为什么重要

Coding Agent 不能只给最终答案。它必须能回答：

- 这次任务创建了哪些步骤？
- 每一步发生了哪些事件？
- 哪一步调用了工具？
- 哪一步失败了？
- 最终 trace 能不能保存、展示、测试？

Trace 是后续调试、评估、可观测性和恢复任务的基础。

## 你要创建的文件

```text
minicode/
  src/
    minicode/
      trace.py
  tests/
    test_trace.py
```

## 建议你手写的结构

在 `trace.py` 中定义：

```python
class TraceRecorder:
    ...
```

建议它内部维护：

```python
self.run: Run
self.steps: list[Step]
self.events: list[Event]
```

## 建议方法

### 1. 初始化

```python
def __init__(self, run: Run) -> None:
    ...
```

要求：

- 保存传入的 `run`
- 初始化空的 `steps`
- 初始化空的 `events`

### 2. 新增 Step

```python
def add_step(self, step_type: StepType, metadata: dict | None = None) -> Step:
    ...
```

要求：

- 自动使用 `self.run.id` 作为 `run_id`
- 创建 `Step`
- 保存到 `self.steps`
- 返回创建的 `Step`

### 3. 新增 Event

```python
def add_event(
    self,
    step: Step,
    event_type: EventType,
    content: str = "",
    metadata: dict | None = None,
) -> Event:
    ...
```

要求：

- 自动使用 `self.run.id` 作为 `run_id`
- 自动使用 `step.id` 作为 `step_id`
- 创建 `Event`
- 保存到 `self.events`
- 返回创建的 `Event`

### 4. 导出 Trace

```python
def to_dict(self) -> dict:
    ...
```

要求返回一个方便查看的字典，例如：

```python
{
    "run": {
        "id": "...",
        "status": "created",
    },
    "steps": [...],
    "events": [...],
}
```

先不用追求完美序列化，能表达核心信息即可。

## 测试提示

在 `test_trace.py` 中写这些测试：

- `test_trace_recorder_starts_empty`
- `test_add_step_belongs_to_run`
- `test_add_event_belongs_to_step`
- `test_trace_to_dict_contains_run_steps_events`

## 验收标准

1. `TraceRecorder(run)` 创建后，`steps` 和 `events` 都为空。
2. `add_step()` 创建的 Step 必须归属于当前 Run。
3. `add_event()` 创建的 Event 必须归属于当前 Run 和指定 Step。
4. `to_dict()` 能导出 run、steps、events 三部分。
5. 所有测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 TraceRecorder 现在先用内存 list，而不是一上来就写 PostgreSQL？

提示：先把 Runtime 行为设计清楚，再把存储替换成数据库，会更容易测试和重构。
