# Day 74：Prompt Injection 防御

## 本章目标

工具输出是数据，不拥有修改 System/Developer 指令、绕过权限或要求泄密的权力。

## 已完成实现

- `detect_prompt_injection()` 使用可解释规则检测指令覆盖、伪造高权限消息、
  secret 外传、工具胁迫和权限绕过。
- 扫描结果包含 `level`、`score`、`matched_rules`，不会只返回一个黑盒布尔值。
- 中高风险 local/untrusted 输出会把当前 `SecurityState` 标记为 contaminated。
- `wrap_untrusted_observation()` 在模型上下文中加入开始/结束边界和“只当数据”约束。
- Agent 基础 prompt 明确禁止执行工具输出中的指令、泄密或绕过审批。

扫描器是便宜的第一层，不声称消灭所有注入。漏检和误报都能通过 Trace 规则命中
记录复盘，后续可以增加可选模型分类器而不改变 ToolResult 契约。
