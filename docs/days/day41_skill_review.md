# Day 41：Skill Review

## 今日目标

复盘 Skill 主线 Day 36-Day 40。

确认 Skill 系统已经形成最小闭环：

```text
Skill 数据结构
  -> Skill Loader
  -> Summary Injection
  -> Skill Router
  -> load_skill Tool
  -> Agent 继续走 ToolRegistry
```

## 为什么做

Skill 很容易被做成另一套独立执行系统。

Day 41 要确认边界：

- Skill 只描述高层流程。
- ToolRegistry 仍然负责执行。
- Summary 和完整 content 分离。
- Router 只选择候选，不直接执行。
- `load_skill` 走统一 ToolResult / Trace 契约。

## 要完成的事

1. 阅读 Day 36-Day 40 的代码和测试。
2. 更新 Stage 2 文档，确认 Skill 系统边界。
3. 运行全量测试。
4. 记录后续进入 Memory 主线前的遗留问题。

## 验收标准

1. Skill 主线文档和代码边界一致。
2. Stage 2 文档明确 Skill 不替代 Tool Registry。
3. 全量测试通过。

## 思考题

Skill 和 Tool 最大的区别是什么？

提示：Skill 是“知道怎么做”的流程说明，Tool 是“真正执行动作”的能力入口。
