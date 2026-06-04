# Day 39：Skill Router

## 今日目标

定义可升级的 Skill Router 策略入口。

Day 38 处理小规模情况：Skill 少时直接注入所有 Summary。Day 39 要把这个策略封装成 Router，让后续可以平滑升级到 LLM Router 或 Embedding Router。

## 为什么做

Skill 数量会逐步增长。

Router 不应该一开始就做复杂检索，但应该提前有一个清晰入口：

```text
task + skills -> selected skills
```

这样 Day 38 的小规模策略、未来中规模 LLM Router、大规模 Embedding Router 都能走同一个接口。

## 建议策略

- `len(skills) <= 20`：全部返回。
- `len(skills) > 20`：先用关键词兜底选 Top-K。
- 用户明确点名 Skill：直接命中。
- `deprecated` 之类状态字段后续再加。

## 建议接口

```python
def route_skills(task: str, skills: list[Skill], limit: int = 20) -> list[Skill]:
    ...
```

## 验收标准

1. 小规模 Skill 全部返回。
2. 超过阈值时按关键词选择候选。
3. `limit` 控制返回数量。
4. 路由不加载完整 Skill 之外的新内容。
5. 全量测试通过。

## 做了什么

- 新增 `route_skills(task, skills, limit=20)`。
- Skill 数量小于等于 20 时，直接返回全部候选并尊重 `limit`。
- Skill 数量超过 20 时，用 name、description、tags 做轻量关键词兜底排序。
- `limit <= 0` 或空 Skill 列表时返回空列表。
- 补充测试覆盖小规模全量返回、limit 限制、大规模关键词选择和非正 limit。

## 思考题

为什么 Router 不直接把 Skill 注入 prompt？

提示：Router 只负责选择候选，Prompt Injection 负责组织模型输入。
