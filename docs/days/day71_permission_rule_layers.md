# Day 71：Permission Rule 分层

## 为什么做

之前权限判断写在 `PermissionReviewer` 的 if/else 里。

功能少时可以，但后续要做工具自检、untrusted content、prompt injection 防御和人工审查流，如果继续硬编码，很快会变成一团安全判断。

Day71 把权限判断拆成分层规则。

## 做什么

新增 `PermissionRule`：

- `name`：规则名，写入 trace metadata。
- `layer`：规则层，当前是 `deny`、`allow`、`review`。
- `kinds`：适用请求类型，例如 `file_write`、`shell_command`。
- `decision`：ALLOW / REVIEW / DENY。
- `suffixes`、`prefixes`、`contains`：轻量匹配条件。

`PermissionReviewer` 仍保留原来的外部 API：

```python
review_file_write(path)
review_shell_command(command)
```

但内部按层执行：

```text
deny -> allow -> review
```

deny 永远优先，所以 `python3 -c 'sudo reboot'` 不会因为 `python3` 前缀被误放行。

## 怎么做

```text
PermissionHook
  -> PermissionReviewer.review_*
  -> PermissionRule.evaluate(...)
  -> PermissionResult(decision + rule_name + layer)
  -> ToolResult.metadata.details
```

SubAgentApprovalHook 也复用同一个 `PermissionReviewer`，所以 implementer operations 的 path 审批和普通 `write_file` 保持一致。

## 做了什么

- 重构 `permissions.py`。
- 新增 `PermissionRule`。
- 新增 `default_permission_rules()`。
- `PermissionResult` 增加 `rule_name` 和 `layer`。
- `PermissionHook` metadata 增加 `permission_rule` 和 `permission_layer`。
- `SubAgentApprovalHook` 的每条 operation decision 增加 rule/layer。
- 补充 deny 优先、自定义规则注入和 review fallback 测试。

## 学习重点

权限系统最重要的是可解释：

```text
这次为什么允许？
是哪条规则允许？
属于哪一层？
如果拒绝，是 deny 层先拦住，还是 review 层要求人工确认？
```

后续安全主线会继续往这个规则体系上叠能力。
