# Day 38：Skill Summary Injection

## 今日目标

实现小规模 Skill 策略：把 Skill Summary 注入 prompt。

Day 37 已经能从项目目录加载 Skill。Day 38 不做粗召回，也不做精排。当前 MiniCode 的 Skill 数量会很少，直接注入所有 Skill Summary 更简单，也不容易漏掉有用 Skill。

## 为什么做

Skill 不是 RAG 文档库。

早期 Skill 通常是少量高价值操作流程。只注入 Summary，而不是完整 content，可以让模型知道有哪些能力，又不会把上下文塞满。

完整 Skill 内容后续通过 `load_skill` 工具按需加载。

## 承接已有能力

本章承接：

- Day 36 的 `Skill` 数据结构。
- Day 37 的项目级 Skill Loader。
- `TextLLM` 已经支持工具说明注入。

## 参考项目学到了什么

参考：

```text
references/MiniCode-Python/minicode/skills.py
references/MiniCode-Python/minicode/tools/load_skill.py
```

参考项目区分 summary 和 loaded skill。这个边界很重要：

- Summary 用于列表、路由和 prompt 提示。
- Loaded Skill 用于按需读取完整内容。

本章只注入 Summary，不注入完整 content。

## 建议接口

在：

```text
minicode/src/minicode/skills.py
```

新增：

```python
def format_skill_summary(skill: Skill) -> str:
    ...

def format_skill_summaries_for_prompt(skills: list[Skill]) -> str:
    ...
```

输出示例：

```text
Available Skills:
- python-test: Run Python tests safely. [tools: run_shell, read_file]
- docs-review: Review documentation changes.
```

## 要修改的文件

```text
minicode/src/minicode/skills.py
minicode/tests/test_skills.py
docs/SDD.md
```

## 验收标准

1. 能格式化单个 Skill Summary。
2. 能格式化多个 Skill Summary。
3. Summary 不包含完整 Skill content。
4. 空 Skill 列表返回空字符串或稳定提示。
5. 全量测试通过。

## 做了什么

- 新增 `format_skill_summary(skill)`，只输出 Skill 的名称、描述、tags 和 tools。
- 新增 `format_skill_summaries_for_prompt(skills)`，把多个 Skill Summary 组织成 `Available Skills:` prompt 区块。
- Summary 明确不包含完整 `content`，完整 Skill 后续通过 `load_skill` 按需加载。
- 空 Skill 列表返回空字符串，方便调用方决定是否插入 prompt。
- 补充测试覆盖单个 Summary、多个 Summary、空列表和 content 不泄漏。

## 思考题

为什么 Day 38 只注入 Summary，而不是注入完整 Skill？

提示：Summary 让模型知道“有哪些能力”，完整内容应该按需通过 `load_skill` 获取。
