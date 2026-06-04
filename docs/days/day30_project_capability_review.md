# Day 30：Project Capability Review

## 今日目标

系统盘点 MiniCode 已经完成的能力，以及下一阶段还缺什么。

前面 29 天已经把一个最小 coding agent 的主干跑通了。Day 30 不急着继续堆功能，而是先回头看清楚：

- Runtime 是否稳定
- Agent loop 是否清晰
- 工具能力是否够用
- Trace 是否方便复盘
- 下一阶段应该优先补什么

## 为什么做

项目学习到这个阶段，很容易只记得“我写了很多文件”，但不清楚它们拼起来是什么系统。

这章的重点是把 MiniCode 从“章节代码”重新看成一个完整产品雏形。

## 建议阅读顺序

```text
models.py
trace.py
workspace.py
file_tools.py
shell_tools.py
permissions.py
agent.py
cli.py
persistence.py
```

## 你要完成的事

1. 阅读 `docs/stage1/README.md` 和 `docs/stage2/README.md`。
2. 对照源码确认每个功能现在在哪里。
3. 按优先级选择下一阶段要补的能力。

## 做了什么

- 整理 `docs/README.md`，把总路线、每日章节、Stage 复盘和 Stage 2 规划分清楚。
- 把 Day 01-Day 31 章节文档统一放进 `docs/days/`。
- 新增 `docs/stage1/README.md`，复盘 Stage 1 已完成能力和遗留问题。
- 新增 `docs/stage2/README.md`、`roadmap.md`、`rules.md`，明确 Day 31 之后按 Stage 2 规则继续。
- 明确下一阶段先做 Tool Registry、工具 trace 契约和只读 Git Tool，再进入 Skill、Memory、Context、多 Agent、安全和 MCP。

## 思考题

MiniCode 现在更像一个“可测试的 agent runtime”，还是一个“可实际日常使用的 coding agent”？

提示：能跑通闭环是一回事，能稳定处理复杂工程任务是另一回事。
