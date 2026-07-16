# Day 75：Human Review Flow

## 本章目标

把原来的 `REVIEW == 直接失败` 改成可持久化、可批准、可拒绝、可取消和可恢复的
状态流。

## 已完成实现

- Run 增加 `WAITING_TOOL`、`WAITING_HUMAN`、`PAUSED` 和对应状态流转。
- `HumanReviewStore` 把每次请求保存到 `.micode/human-reviews`。
- 审核记录保存 tool、args、args SHA-256、原因、run/session、状态和时间。
- 批准只能消费一次；恢复时 tool/args 哈希必须与原请求完全一致。
- deny 规则不可被人工批准绕过。
- contaminated 上下文后的写文件、Shell、外部写型 MCP tool 自动升级审核。

## CLI

```bash
micode human-review list
micode human-review approve --review-id review-xxx --note "verified"
micode human-review resume --review-id review-xxx --workspace .
```

`resume` 仍然经过同一个 ToolRegistry、Hook、权限和 provenance 流程。
