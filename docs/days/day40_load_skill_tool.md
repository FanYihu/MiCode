# Day 40：Load Skill Tool

## 今日目标

把 `load_skill` 做成 Tool Registry 中的一个工具。

Day 38 只注入 Skill Summary。模型知道有哪些 Skill 后，需要一种方式按名称加载完整 Skill 内容。

## 为什么做

完整 Skill 内容可能很长，不应该默认全部放进 prompt。

正确链路是：

```text
注入 Skill Summary
  -> LLM 判断需要某个 Skill
  -> AgentAction(tool="load_skill", args={"name": "python-test"})
  -> ToolRegistry.call("load_skill")
  -> 完整 Skill 内容进入 observations
```

## 承接已有能力

本章承接：

- Day 37 的 Skill Loader。
- Day 38 的 Skill Summary Injection。
- Tool Registry 的统一调用和 metadata 契约。

## 建议接口

在默认 Tool Registry 中注册：

```text
load_skill
```

参数：

```json
{"name": "python-test"}
```

返回内容包含：

```text
SKILL: python-test
DESCRIPTION: ...
CONTENT:
...
```

## 验收标准

1. 默认 Registry 注册 `load_skill`。
2. 能按 name 加载项目 `.minicode/skills/<name>/SKILL.md`。
3. 未知 Skill 返回 `ok=False`。
4. 返回 metadata 符合 Tool Trace Contract。
5. Agent 可以通过 `ToolRegistry.call("load_skill", ...)` 获取完整内容。
6. 全量测试通过。

## 做了什么

- 新增 `load_project_skill(workspace, name)`，按名称加载项目级 Skill。
- 默认 Tool Registry 注册 `load_skill`。
- `load_skill` 成功时返回 Skill 名称、描述和完整内容。
- 未知 Skill 返回 `ToolResult(ok=False, output="Unknown skill: ...")`。
- 返回 metadata 继续遵守 Tool Trace Contract，工具细节进入 `details`。
- 补充测试覆盖成功加载、未知 Skill 和 Registry 注册。
- 进一步重构目录边界：新增 `tools/` 子包，`tools/registry.py` 只保留契约和统一调用，默认工具装配放到 `tools/default.py`，`load_skill` 的具体适配放到 `tools/skill.py`。

## 思考题

为什么 `load_skill` 应该是工具，而不是 Agent 内部特判？

提示：Skill 系统必须复用 Tool Registry，不能重新开一条工具分发路径。
