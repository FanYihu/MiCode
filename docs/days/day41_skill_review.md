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

## 做了什么

- 复盘 Day 36-Day 40 的 Skill 主线，确认 Skill 数据、加载、Summary 注入、Router 和 `load_skill` 已形成最小闭环。
- 明确 Skill 和 Tool 的边界：Skill 描述“怎么做”，Tool 执行“实际动作”。
- 更新 Stage 2 文档，补充当前 Skill 闭环流转图。
- 新增 Agent 集成测试，验证 `load_skill` 通过 Tool Registry 调用后，完整 Skill 内容会进入 observations 并继续驱动后续 final。
- 记录下一阶段边界：Skill 不负责经验沉淀，Day 42 开始进入 Memory 主线。

## 遗留问题

- `route_skills` 当前只是小规模全量返回和大规模关键词兜底。
- Skill 目前只从项目 `.minicode/skills` 加载，还没有全局 Skill、用户 Skill 或优先级合并。
- Skill 内容进入 observations 后还没有做压缩和 artifact 外置，这会留到 Context 主线处理。
- 成功/失败运行经验还没有沉淀为 Memory，这正是下一章要开始解决的问题。

## 思考题

Skill 和 Tool 最大的区别是什么？

提示：Skill 是“知道怎么做”的流程说明，Tool 是“真正执行动作”的能力入口。
