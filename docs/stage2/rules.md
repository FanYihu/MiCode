# Stage 2 Development Rules

## 每章固定流程

1. 先阅读 `references/MiniCode-Python` 对应模块。
2. 文档中写“参考项目学到了什么”。
3. 写章节 SDD：为什么做、做什么、怎么做、验收标准。
4. 必须说明本章承接当前项目哪部分已有能力。
5. 只实现当前章最小可测能力，不跨章大改。
6. 代码必须有关键注释。
7. 所有新增行为必须有测试。
8. 每章结束运行：

```bash
PYTHONPATH=src python3 -m pytest tests -q
```

9. 更新 `docs/SDD.md`。
10. 必要时更新 `docs/stage1/README.md` 或 `docs/stage2/README.md`。

## 参考项目规则

- 参考仓库路径固定为 `references/MiniCode-Python`。
- 参考仓库只读使用。
- 不复制参考项目源码。
- 不提交 `references/` 目录。
- 每章只吸收一个概念，重写成适合当前 MiniCode 的小版本。

## 架构规则

- 不推倒重来。
- 不重编号，从当前 Day 31 继续。
- 先做 Day 31-Day 35 过渡，再进入五大技术主线。
- Tool Registry 要承接现有 Agent 工具，不让 AgentAction 结构突然大改。
- Skill、Memory、Context、SubAgent、MCP 都要复用 Tool Registry 和 trace。
- 权限系统要逐步扩展现有 `PermissionDecision.ALLOW / REVIEW / DENY`。

## 配置规则

- 不擅自改变 `config.toml` 明文 `api_key` 方案。
- 新配置可以增加 section，但不要改掉现有 `[llm]` 读取方式。
- MCP 配置后续追加，不和 LLM key 混在一起。

## 测试规则

过渡阶段：

- Day 31：结构化文件编辑测试，包括替换、插入、删除、越界、路径保护。
- Day 32：Tool Registry 注册、查找、调用、未知工具错误。
- Day 33：工具 trace metadata 统一格式。
- Day 34：git status/diff 只读工具测试。
- Day 35：全量测试和功能盘点校验。

主线专项：

- Skill：数据结构、项目级加载、summary 注入、router 策略、load_skill 工具、trace metadata。
- Memory：trace 提炼、分类存储、索引更新、按需召回。
- Context：artifact 外置化、占位符、压缩、按需检索。
- Multi-Agent：子 Agent 调用、路径边界、权限约束、结果汇总。
- Security：规则过滤、工具自检、prompt injection 标记、人工确认。
- MCP：配置解析、tool discovery、mock server 调用、错误 trace、权限审核。

## 提交规则

学习项目不强制每章都提交，但重要阶段建议提交：

- Stage 1/Stage 2 文档边界整理后。
- Day 31-Day 35 过渡完成后。
- 每条技术主线完成后。
- Stage 2 总复盘后。
