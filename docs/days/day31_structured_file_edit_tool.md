# Day 31：Structured File Edit Tool

## 今日目标

给 MiniCode 增加结构化文件编辑工具。

现在 `FileTools` 已经能读文件、写文件和生成 diff，但这还不够适合 Agent 自动改代码。直接整文件写入风险比较高，也不方便在 trace 里看清楚“具体改了哪一段”。

Day 31 要先做一个很小但可靠的编辑能力：按旧文本替换成新文本。

## 为什么做

Coding agent 最核心的能力不是“读代码”，而是“安全地改代码”。

结构化编辑的好处：

- 修改范围更小
- 失败原因更清楚
- 更适合写测试
- 后面更容易接入人工确认和 diff trace

## 参考项目学到了什么

参考：

```text
references/MiniCode-Python/minicode/tools/edit_file.py
references/MiniCode-Python/minicode/tools/patch_file.py
```

参考项目的编辑工具不是直接整文件覆盖，而是强调：

- 搜索文本必须精确匹配。
- 找不到文本时要给明确失败原因。
- 默认控制修改范围，避免一次误伤多个位置。
- 修改结果应该能形成 diff，方便后续人工确认和 trace 审计。

本章只吸收其中最小的一点：先实现“精确 old -> new 替换一次”。

## 建议接口

放在：

```text
minicode/src/minicode/file_tools.py
```

新增：

```python
def replace_text(self, path: str, old: str, new: str) -> str:
    ...
```

建议规则：

- `old` 必须非空。
- 文件中必须能找到 `old`。
- 默认只替换一次，避免误伤多个相同片段。
- 返回修改后的 diff 文本，方便用户确认。

## 建议异常

可以新增两个轻量异常：

```python
class EmptySearchText(ValueError):
    ...

class SearchTextNotFound(ValueError):
    ...
```

异常不用复杂，重点是让测试能明确区分失败原因。

## 要修改的文件

```text
minicode/src/minicode/file_tools.py
minicode/tests/test_file_tools.py
```

## 验收标准

1. `replace_text` 能把文件中的旧文本替换成新文本。
2. 每次只替换第一个匹配项。
3. 替换后返回 diff。
4. `old == ""` 时抛出明确异常。
5. 找不到旧文本时抛出明确异常。
6. 支持通过 `new == ""` 删除文本。
7. 支持把旧文本替换为更长文本来完成插入。
8. 仍然沿用 Workspace 路径边界保护。
9. 全量测试通过。

## 做了什么

- 新增 `EmptySearchText` 和 `SearchTextNotFound`，让失败原因可测试。
- 给 `FileTools` 新增 `replace_text(path, old, new)`。
- 默认只替换第一处匹配，并返回 diff。
- 补充替换、插入、删除、找不到文本、空搜索文本和路径越界测试。

## 思考题

为什么第一版只替换一次，而不是把所有匹配都替换掉？

提示：Agent 自动编辑时，范围越可控，越容易确认，也越不容易误伤。
