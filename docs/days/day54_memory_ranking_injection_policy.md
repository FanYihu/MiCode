# Day 54：Memory Ranking / Injection Policy

## 为什么做

Day53 已经能从多个通道召回长期记忆，但“相关”不等于“应该优先进入 Prompt”。

例如：

- 当前有效的 Semantic Fact 通常比一次旧 Episode 更可靠。
- 同一个 Session 的经历更贴近当前上下文。
- 高置信度的新事实应优先于低置信度旧事实。
- conflicting 事实需要保留警告，但不能与确定事实同等排序。
- 即使召回很多内容，也不能无限占用模型上下文。

## 做什么

新增 `MemoryRankingPolicy`：

- 对 Day53 的召回结果进行业务精排。
- 记录每个排序因子的可解释分数。
- 对 conflicting 事实降权而不隐藏。
- 按字符预算、条目数量和类型数量选择最终注入内容。
- 把候选、注入项、省略项和预算使用情况写入 Trace。

## 怎么做

当前排序公式：

```text
ranking_score =
  retrieval_score * 0.55
  + memory_type * 0.15
  + confidence * 0.15
  + recency * 0.10
  + same_session * 0.05
```

如果事实是 `conflicting`：

```text
ranking_score *= 0.75
```

### 类型价值

```text
semantic   = 1.00
procedure  = 0.95
graph_fact = 0.90
episode    = 0.75
```

这不是说 Episode 没价值，而是稳定事实和成功流程通常更适合直接指导下一次任务。

### 时效性

采用平滑衰减：

```text
recency = 1 / (1 + age_days / 30)
```

- 刚产生的记忆接近 `1.0`。
- 约 30 天的记忆接近 `0.5`。
- 旧记忆不会直接归零，仍可被高相关性召回。

### 注入预算

默认长期记忆预算：

```text
1800 characters
8 items
3 items per memory type
```

执行顺序：

```text
Hybrid Retrieval candidates
  -> MemoryRankingPolicy.rank(...)
  -> prepare_injection(...)
  -> Relevant Long-Term Memory
  -> Agent Prompt
```

预算不足时：

- 保留排名更高的记忆。
- 单条内容会被截断。
- 超出数量或类型限制的结果进入 `omitted_ids`。
- 不会改变磁盘中的原始记忆。

## CLI

可以调整长期记忆字符预算：

```bash
micode agent "继续任务" --memory-budget-chars 1200
```

Trace metadata 新增：

- `ranking_score`
- `ranking_details`
- `memory_injection.candidate_count`
- `memory_injection.selected_ids`
- `memory_injection.omitted_ids`
- `memory_injection.used_chars`
- `memory_injection.budget_chars`

## 关键边界

- 排序策略不会重新生成或修改记忆内容。
- superseded 事实仍在 Day53 默认过滤。
- conflicting 事实参与排序，但会降权并在 Prompt 中显示状态。
- 当前使用字符预算，Day60 再实现统一 Token Estimate。
- 当前权重是明确、可测试的默认策略，后续可以通过配置或反馈数据调整。

## 参考项目学到了什么

参考项目把上下文当作有限资源管理。Micode 因此把“检索到什么”和“最终注入什么”拆开，让记忆的相关性、可信度、时效性和上下文成本都可以独立审计。

## 验收标准

- 同等相关性下，高置信度和更新更近的记忆优先。
- 同 Session 记忆获得小幅加成。
- Semantic / Procedure 优先于普通 Episode。
- conflicting 事实保留但降权。
- 最终注入文本不超过指定字符预算。
- 类型限制避免单一记忆类型占满上下文。
- Trace 能解释排序和省略原因。

## 做了什么

新增 `memory/ranking.py`，实现 MemoryRankingPolicy 和 MemoryInjection。

CLI 现在先宽召回候选，再根据类型、置信度、时效性、Session 和冲突状态精排，最后按预算选择真正进入 Agent Prompt 的长期记忆。
