# Day 55：Memory Review

## 为什么做

Day42-Day54 已经形成一条完整记忆链：

```text
Session
  -> Message History
  -> Working Memory
  -> Session Summary
  -> Episodic Memory
  -> Semantic / Procedural Memory
  -> Skill Candidate
  -> Entity / Relation Graph
  -> Temporal Facts
  -> Hybrid Retrieval
  -> Ranking / Injection
```

但系统越完整，越容易出现断链：

- Session 里有 run，但没有对应 Episode。
- Semantic Memory 指向不存在的来源 Episode。
- Skill Candidate 指向不存在的 Procedure / Episode。
- Skill Candidate 与正式 Skill 同名或高度相似，但没有 review 结论。
- Graph edge 指向缺失节点。
- Temporal Fact 状态非法。
- 召回器跑不出任何可注入记忆。

Day55 的目标是给记忆系统加一个可执行体检，而不是只写复盘文字。

## 做什么

新增 `memory/review.py`：

- `MemoryReviewIssue`：一条 review 问题。
- `MemoryReviewReport`：汇总计数、问题列表和检索预览。
- `review_memory_system(...)`：读取现有 session 和 memory 文件，执行完整性检查。
- `run_retrieval_preview(...)`：用 sample query 干跑 retrieve -> rank -> inject。

新增 CLI：

```bash
minicode memory-review \
  --session-dir .minicode/sessions \
  --memory-dir .minicode/memory \
  --sample-query "pytest"
```

## 检查内容

### Session 层

- Session 是否有 messages 文件。
- Session 是否有 working memory 文件。
- Session 是否有 summary 文件。
- Session.run_ids 是否都有对应 `episode:{run_id}`。

### Long-term Memory 层

- Episode 是否能找到 Session。
- Episode / Semantic / Procedure 是否进入 Graph。
- Semantic / Procedure 的 source episode 是否存在。
- Skill Candidate 的 source procedure / episode / run 是否存在。
- Skill Candidate 是否处于合法状态：`draft`、`approved`、`rejected`、`promoted`。
- `approved` candidate 是否尚未 promote，或者是否需要用户处理。
- `promoted` candidate 是否能找到对应正式 Skill。

### Skill Candidate 层

候选 Skill 不等于正式 Skill。Review 需要检查：

- 是否有清晰的 `name`、`description`、`content`、`tags`。
- `content` 是否是可复用流程，而不是某次 trace 的流水账。
- 是否和已有 `.minicode/skills` 或用户级 Skill 同名。
- 是否有足够来源支撑，避免单次偶然成功被误提升。
- `review_notes` 是否说明批准、拒绝或合并原因。

### Graph 层

- Edge 的 source / target node 是否存在。
- 磁盘上的 memory 是否进入 graph index。
- Temporal Fact 状态是否合法。
- `superseded` 是否记录替代事实。
- `conflicting` 是否记录冲突对象。

### Retrieval 层

如果传入 sample query，会执行：

```text
HybridMemoryRetriever.retrieve(...)
  -> MemoryRankingPolicy.rank(...)
  -> prepare_injection(...)
```

并输出：

- candidate_count
- selected_count
- selected_ids
- omitted_ids
- used_chars / budget_chars
- top_results

## 输出格式

```json
{
  "ok": true,
  "summary": {
    "sessions": 1,
    "episodes": 1,
    "semantic_memories": 1,
    "procedural_memories": 1,
    "graph_nodes": 7,
    "graph_edges": 7,
    "temporal_facts": {
      "active": 1,
      "superseded": 0,
      "conflicting": 0
    }
  },
  "issues": [],
  "retrieval_preview": {}
}
```

## 关键边界

- Review 只读现有记忆，不自动修复。
- Review 不自动把 Skill Candidate 提升为 Skill。
- error 表示明确断链或非法状态。
- warning 表示可运行但不完整。
- 空 memory 目录是合法状态。
- sample query 召回为空时是 warning，不是 error。

## 参考项目学到了什么

参考项目强调 Agent 过程必须可审计。MiniCode 把这个原则扩展到记忆系统：每一层记忆不仅要能写入，还要能被检查、追溯和解释。

## 验收标准

- 健康记忆链 review 通过。
- 缺失 source episode 会报 error。
- graph edge 指向缺失节点会报 error。
- temporal fact 非法状态会报 error。
- sample query 召回为空会报 warning。
- CLI 能输出 JSON-ready review report。

## 做了什么

新增 `memory/review.py`，实现记忆系统结构化体检。

新增 `memory-review` CLI 子命令，可以检查 session、长期记忆、graph、temporal facts 和 retrieval injection 的完整性。
