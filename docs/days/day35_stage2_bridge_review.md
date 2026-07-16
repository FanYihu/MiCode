# Day 35：Stage 2 Bridge Review

## 今日目标

复盘 Day 31-Day 34，确认 Micode 已经从基础 Agent Loop 平滑过渡到可扩展工具 Runtime。

Day 31 到 Day 34 做了四件关键事：

- 结构化文件编辑。
- Tool Registry。
- Tool Trace Contract。
- 只读 Git Tool。

Day 35 不急着进入 Skill 主线，先检查这个过渡层是否稳定。

## 为什么做

如果过渡层没有整理清楚，后面 Skill、Memory、Context、SubAgent、MCP 都会挂在不稳定的工具接口上。

Day 35 的重点是确认：

- Agent 是否已经不关心具体工具实现。
- 新增工具是否只需要注册。
- Trace metadata 是否稳定。
- 权限是否可以进入工具生命周期。
- Git 是否提供了基本项目级观察能力。

## 承接已有能力

本章承接：

- Day 31：`FileTools.replace_text`。
- Day 32：`ToolRegistry`。
- Day 33：统一 metadata 和工具权限生命周期；当前权限实现已升级为 PermissionHook。
- Day 34：`GitTools`。

## 参考项目学到了什么

参考：

```text
references/MiniCode-Python/minicode/tooling.py
references/MiniCode-Python/minicode/tools/git.py
references/MiniCode-Python/minicode/agent_loop.py
```

参考项目的工具系统是后续 Skill、MCP、审计和上下文管理的基础。

本章不新增复杂能力，只做架构检查和文档复盘。

## 要完成的事

1. 阅读 Day 31-Day 34 的代码和测试。
2. 更新 `docs/stage1/README.md`，确认 Stage 1 遗留问题哪些已经缓解。
3. 更新 `docs/stage2/README.md`，记录当前工具 Runtime 的新边界。
4. 运行全量测试。

## 验收标准

1. 文档说明 Micode 当前工具 Runtime 的真实结构。
2. Stage 1 遗留问题中和工具分发、Git 观察相关的内容得到更新。
3. Stage 2 文档明确下一阶段进入 Skill 主线。
4. 全量测试通过。

## 做了什么

- 更新 Stage 1 文档，记录 Tool Registry、工具 metadata 契约、权限 Hook 和只读 Git Tool 已完成。
- 更新 Stage 1 遗留问题，把“硬编码工具分发、没有 Git 工具、没有工具契约”改成新的真实缺口。
- 更新 Stage 2 文档，明确后续 Skill、MCP、SubAgent 都应复用 Tool Registry。
- 更新 Stage 2 Roadmap，确认工具 metadata 顶层字段统一，工具特有信息进入 `details`。
- 确认 Day 31-Day 34 已经完成从基础 Agent Loop 到可扩展工具 Runtime 的过渡。

## 思考题

为什么先做 Tool Registry，再做 Skill？

提示：Skill 不是另一个工具分发系统，它应该复用 Tool Registry，把高层能力组织到稳定工具入口之上。
