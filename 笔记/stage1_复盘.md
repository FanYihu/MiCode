# MiniCode 第一阶段复盘

## 我完成了什么

完成了 MiniCode 的 Runtime 骨架和最小 Agent Loop，建立了 Coding Agent 最基本的 Harness Engineering。

具体包括：

- `Run / Step / Event` 三个核心数据结构。
- Run 状态机，限制任务状态流转。
- `TraceRecorder`，记录每一步执行轨迹。
- `Workspace`，读取目录、文件和搜索文本。
- `FileTools`，读取、写入和预览文件修改。
- `ShellTools`，在工作区执行命令并捕获结果。
- `PermissionReviewer`，对文件和命令做安全判断。
- `CLI`，从命令行启动一次任务。
- `MiniCodeAgent`，根据 action 执行工具并记录观察。

## 我理解了什么

我理解了 `Run`、`Step`、`Event` 三个数据结构各自负责的内容和边界：

- `Run` 是一次完整任务。
- `Step` 是任务中的一个动作。
- `Event` 是动作产生的可观察记录。

我也理解了 Agent 运作的基本原理：Agent 不是一次性生成答案，而是不断观察、决定动作、执行工具、记录结果，直到最终完成。

这也让我理解了为什么 Trace 很重要。没有 Trace，就很难知道 Agent 为什么这样做、哪一步失败、工具返回了什么。

## 还不稳的地方

- `MockLLM` 目前还是占位，还没有真正接入模型。
- `AgentAction` 的 schema 还比较简单，后续需要更严格的参数校验。
- `PermissionReviewer` 现在主要靠字符串规则，安全性还比较粗。
- `ShellTools` 虽然有超时，但还没有更细的危险命令隔离。
- Agent Loop 还没有支持人工确认、暂停、恢复和重试。
- 代码风格还可以继续整理，例如 import、缩进、注释和测试命名。

## 下一阶段目标

下一阶段目标是把 MiniCode 完善成一个可以实际在项目中使用的 Coding Agent。

优先方向：

1. 接入真实 LLM，让模型生成 `AgentAction`。
2. 给工具参数增加 schema 校验，减少错误调用。
3. 增加 Human-in-the-loop，让高风险操作能暂停等待确认。
4. 增加更完整的 Agent 集成测试和评估任务集。
5. 把 Trace 持久化，后续支持查看历史任务和失败复盘。
