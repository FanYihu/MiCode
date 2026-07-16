# Day 76：Security Trace Audit

## 本章目标

安全判断不能只发生在内存里，Trace 必须能证明一次工具调用经过了什么边界。

## 已完成实现

每个工具事件记录：

- `trust_level`、`source`、`content_sha256`、`injection_risk`。
- `capabilities`：只读、写工作区、执行命令、外部 I/O、强制审核、可回退。
- Hook 执行记录、权限 rule/layer、Human Review 请求或 consumed 记录。
- MCP server/tool/method、失败分类、recoverable 和 retry hint。

`review_security_trace()` 顺序扫描事件，检测缺失 provenance、注入风险，以及
contaminated 之后是否存在未审核却成功执行的副作用工具。
