# Day 52：Temporal Facts / Conflict Resolution

## 为什么做

知识并不总是永久不变。

例如项目最初使用 `model-a`，后来改成 `model-b`。如果图里两条关系都无条件保持有效，Agent 就无法判断当前配置。

同时，`uses pytest` 和 `uses ruff` 可以同时成立，不能把所有不同目标都当成冲突。

## 做什么

给知识关系增加时序属性：

- `observed_at`：什么时候观察到事实。
- `valid_from` / `valid_to`：事实有效时间。
- `cardinality`：关系是单值还是多值。
- `fact_status`：`active`、`superseded` 或 `conflicting`。
- `superseded_by`：旧事实被哪条新事实替代。
- `conflicts_with`：无法自动裁决时的冲突事实。

新增 `temporal.py`，在 Memory Graph 持久化前统一解析历史事实和新事实。

## 怎么做

冲突分组键：

```text
source entity + predicate
```

处理规则：

1. `multi` 关系允许多个目标同时为 `active`。
2. `single` 关系优先选择 `observed_at` 更新的事实。
3. 时间相同时，优先选择置信度更高的事实。
4. 时间和置信度都相同但目标不同，双方标记为 `conflicting`。
5. 被替代的事实保留在图里，标记为 `superseded`，并记录 `valid_to` 和 `superseded_by`。

示例：

```text
MiniCode --uses_model--> model-a
observed_at: 2026-06-01
status: superseded
valid_to: 2026-06-09

MiniCode --uses_model--> model-b
observed_at: 2026-06-09
status: active
```

多值关系：

```text
MiniCode --uses--> pytest  active
MiniCode --uses--> ruff    active
```

## 关键边界

- 冲突解析发生在完整持久化图上，因此可以比较跨 run 的事实。
- 旧事实不会被物理删除，保证审计和历史查询。
- 同一事实被多次观察时，来源 memory 和 episode 会合并保留。
- 当前 cardinality 由 LLM 输出或确定性规则推断。
- Day53 检索时应默认优先返回 `active`，并按需展示冲突和历史事实。

## 参考项目学到了什么

参考项目强调事件和状态变化可审计。MiniCode 将这个原则应用到知识图谱：新事实不会悄悄覆盖旧事实，而是显式记录事实何时失效、被谁替代、依据来自哪里。

## 验收标准

- 新的单值事实可以替代旧事实。
- 多值事实可以同时保持 active。
- 同时间同置信度的矛盾事实会标记 conflicting。
- 图存储可以跨多次 run 解析冲突。
- 旧事实保留来源、有效时间和替代关系。
- CLI trace metadata 包含时序事实状态统计。

## 做了什么

新增 `memory/temporal.py`，实现时序事实排序、冲突解析和状态统计。

扩展 KnowledgeRelation、Memory Graph 和 CLI 记忆管线，为关系写入时间、基数、状态及来源，并在图持久化时自动解析跨 run 冲突。
