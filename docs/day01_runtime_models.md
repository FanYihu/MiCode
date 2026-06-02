# Day 01：Runtime 核心数据模型

## 今日目标

手写 MiniCode 的三个核心对象：

- `Run`：一次用户任务
- `Step`：任务执行过程中的一个步骤
- `Event`：步骤中产生的可观察事件

先不要接 OpenAI，也不要写文件工具。今天只练“运行时怎么记录一件事”。

## 你要创建的文件

```text
minicode/
  src/
    minicode/
      __init__.py
      models.py
  tests/
    test_models.py
```

## 建议你手写的结构

在 `models.py` 中定义：

- `RunStatus`：枚举，包含 `created`、`running`、`completed`、`failed`、`cancelled`
- `StepType`：枚举，包含 `model`、`tool`、`human`、`final`
- `EventType`：枚举，包含 `text`、`state`、`tool_call`、`error`
- `Run`：dataclass
- `Step`：dataclass
- `Event`：dataclass

每个对象建议有：

- `id`
- `created_at`
- 必要的业务字段

## 验收标准

你写完后，至少能通过这些行为：

1. 创建一个 `Run` 时，默认状态是 `created`。
2. 创建一个 `Step` 时，能关联到 `run_id`。
3. 创建一个 `Event` 时，能关联到 `run_id` 和 `step_id`。
4. `Run`、`Step`、`Event` 的 `id` 不为空。
5. 时间字段默认自动生成。

## 测试提示

在 `tests/test_models.py` 里写 3 个测试：

- `test_create_run_defaults`
- `test_create_step_belongs_to_run`
- `test_create_event_belongs_to_step`

## 手写要求

- 代码里要有简短注释，解释每个模型在 Runtime 中的职责。
- 不要复制完整答案；你先按理解写，我再帮你 review。
- 如果卡住，先告诉我你卡在哪个对象或哪个字段。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
python -m pytest
```
