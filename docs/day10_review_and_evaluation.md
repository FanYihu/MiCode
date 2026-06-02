# Day 10：综合测试与复盘

## 今日目标

对 MiniCode 第一阶段做一次收口：补综合测试、整理架构、复盘你真正掌握了什么。

这一天不急着加新功能，而是把已有能力变成一个稳定的小项目。

## 当前已经完成

- Runtime 数据模型：`Run / Step / Event`
- Run 状态机：`created -> running -> completed/failed/cancelled`
- Trace 记录器：记录 Step/Event 并导出 dict
- Workspace Context：列文件、读文件、搜索文本、路径保护
- File Tools：读写文件、diff 预览
- Shell Tools：执行命令、捕获输出、处理超时
- Permission Reviewer：允许、审核、拒绝
- CLI：`list files`、`run tests`
- Agent Loop：由 action 驱动工具调用和 final 结束

## 为什么要复盘

Agent 项目容易陷入“功能一直加，但结构没吃透”。

Day 10 要确认三件事：

1. 你能讲清楚每个模块负责什么。
2. 你能用测试证明核心链路没坏。
3. 你能知道下一阶段接真实 LLM 时应该替换哪里。

## 你要创建的文件

```text
minicode/
  docs/
    architecture.md
    stage1_review.md
  tests/
    test_agent_integration.py
```

## architecture.md 建议内容

保持短小，写清楚：

- MiniCode 第一阶段模块图
- 每个模块职责
- 一次任务的执行流程
- 后续接 LLM 时的替换点

建议结构：

```markdown
# MiniCode 架构说明

## 模块职责

## 执行流程

## Trace 结构

## 后续扩展点
```

## stage1_review.md 建议内容

写学习复盘，不要太长：

```markdown
# MiniCode 第一阶段复盘

## 我完成了什么

## 我理解了什么

## 还不稳的地方

## 下一阶段目标
```

## 综合测试建议

在 `test_agent_integration.py` 里写端到端测试。

建议测试 1：读取文件后 final

```text
Mock action:
1. read_file README.md
2. final

期望:
- run completed
- 有 tool step
- 有 final step
- event 里包含 README 内容
```

建议测试 2：危险 shell 被拒绝

```text
Mock action:
1. run_shell rm -rf /

期望:
- run failed
- event 里包含权限不足或危险原因
```

建议测试 3：超过最大步骤失败

```text
Mock action:
一直返回 list_files，不返回 final

期望:
- run failed
- event 里包含超过最大步骤数
```

## 推荐你手写一个测试用 LLM

因为 `MockLLM` 以后要留给真实 LLM 接口占位，你可以在测试里写：

```python
class SequenceLLM:
    def __init__(self, actions):
        self.actions = actions
        self.index = 0

    def next_action(self, task, observations):
        action = self.actions[self.index]
        self.index += 1
        return action
```

## 验收标准

1. 新增架构说明文档。
2. 新增第一阶段复盘文档。
3. 新增至少 3 个 Agent 综合测试。
4. 全量测试通过。
5. 你能口头解释：CLI、Agent Loop、Trace、Tools、Permission 之间如何协作。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

如果明天要接 OpenAI Responses API，应该替换哪个模块？

提示：不要重写 Runtime、Tools、Trace。优先替换“产生 AgentAction 的决策器”。
