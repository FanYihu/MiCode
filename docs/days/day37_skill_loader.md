# Day 37：Skill Loader

## 今日目标

从项目目录加载本地 Skill。

Day 36 已经定义了 `Skill` 数据结构。Day 37 要让 Micode 能从约定目录读取 `SKILL.md`，转换成 `Skill` 对象。

## 为什么做

Skill 不应该只存在于代码里。

后续用户会把自己的操作流程写成文件，例如：

```text
.micode/skills/python-test/SKILL.md
```

Runtime 需要能扫描这些文件，把它们变成可注入、可路由、可加载的 Skill 对象。

## 承接已有能力

本章承接：

- Day 36 的 `Skill` 数据结构。
- `Workspace` 的项目根目录。
- Stage 2 里“Skill 不替代 Tool Registry”的边界。

## 参考项目学到了什么

参考：

```text
references/MiniCode-Python/minicode/skills.py
references/MiniCode-Python/minicode/tools/load_skill.py
```

参考项目会扫描项目级和用户级 Skill 目录，并从 `SKILL.md` 中提取 description。

本章先做项目级最小版本：

```text
.micode/skills/<skill-name>/SKILL.md
```

## 建议接口

在：

```text
micode/src/micode/skills.py
```

新增：

```python
def load_skill_from_file(path: str) -> Skill:
    ...

def discover_project_skills(workspace: Workspace) -> list[Skill]:
    ...
```

description 可以先取 Markdown 中第一段非标题文本。

## 要修改的文件

```text
micode/src/micode/skills.py
micode/tests/test_skills.py
docs/SDD.md
```

## 验收标准

1. 能从单个 `SKILL.md` 加载 Skill。
2. Skill name 默认来自父目录名。
3. description 能从 Markdown 第一段正文提取。
4. 能扫描 `.micode/skills/*/SKILL.md`。
5. 缺失目录时返回空列表。
6. 全量测试通过。

## 做了什么

- 新增 `extract_skill_description(markdown)`，从第一段非标题正文提取 Skill 描述。
- 新增 `load_skill_from_file(path)`，从单个 `SKILL.md` 加载 `Skill`，名称默认取父目录名。
- 新增 `discover_project_skills(workspace)`，扫描项目级 `.micode/skills/*/SKILL.md`。
- 缺失 `.micode/skills` 目录时返回空列表。
- 补充测试覆盖单文件加载、description 提取、项目级扫描和缺失目录。

## 思考题

为什么 Loader 只负责加载，不负责判断 Skill 是否相关？

提示：加载是数据层职责，是否注入或路由选择属于后面的 Summary Injection 和 Skill Router。
