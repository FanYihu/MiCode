# Python 多线程与 ThreadPoolExecutor

## 先记住四个对象

```text
ThreadPoolExecutor
    线程池管理器

executor.submit(fn, args...)
    把函数交给工作线程
    立即返回 Future

Future
    保存未来的结果或异常

future.result()
    等待并取得结果

with ThreadPoolExecutor(...)
    自动等待任务完成并关闭线程池
```

MiniCode 的并行工具调用就是由这四部分组成的。

## 进程和线程

运行一个 Python 程序时，操作系统会创建一个进程：

```text
Python 进程
├── 主线程
├── 工作线程 1
├── 工作线程 2
└── 工作线程 3
```

进程负责资源隔离，拥有自己的虚拟地址空间、文件描述符和 Python 对象。

线程是进程内部的一条执行流。同一进程中的线程：

- 共享 Python 对象和全局变量。
- 共享文件描述符和工作目录等进程资源。
- 各自拥有调用栈、寄存器状态和程序计数器。
- 由操作系统调度。

线程共享内存，因此创建和通信成本通常低于进程，但也会产生竞态条件。

## 并发和并行

并发表示多个任务的生命周期重叠：

```text
Task A: 运行 -> 等待 I/O -> 运行
Task B:       运行 -> 等待 I/O -> 运行
```

并行表示多个任务在同一时刻由不同 CPU 核心执行。

MiniCode 使用线程处理文件读取、Git 子进程等待等 I/O 工作。线程在等待磁盘或子进程时，其他线程可以继续运行，因此等待时间能够重叠。

## GIL

标准 CPython 有 Global Interpreter Lock，简称 GIL。

它通常只允许一个线程在同一时刻执行 Python 字节码：

```text
Thread A 获得 GIL -> 执行 Python 字节码
Thread A 释放 GIL
Thread B 获得 GIL -> 执行 Python 字节码
```

因此大量纯 Python CPU 计算通常不适合使用线程提升速度。

但是阻塞 I/O 通常会释放 GIL，例如：

- 文件读取
- 网络请求
- 等待子进程
- `time.sleep()`

所以线程适合 MiniCode 当前的只读工具。

GIL 也不等于业务代码线程安全。多个步骤组成的操作仍可能被其他线程打断：

```python
if key not in mapping:
    mapping[key] = value
```

共享可变数据需要使用 `Lock` 等同步工具。

## ThreadPoolExecutor

导入：

```python
from concurrent.futures import ThreadPoolExecutor
```

最小示例：

```python
from concurrent.futures import ThreadPoolExecutor
import time


def work(name: str) -> str:
    print(f"{name} start")
    time.sleep(1)
    print(f"{name} done")
    return f"{name} result"


with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(work, "A"),
        executor.submit(work, "B"),
        executor.submit(work, "C"),
    ]
    results = [future.result() for future in futures]

print(results)
```

三个任务会被提交到线程池，最多由三个工作线程同时执行。

## `max_workers`

```python
ThreadPoolExecutor(max_workers=3)
```

表示线程池最多同时使用三个工作线程。

如果提交五个任务：

```text
Worker 1 -> Task A
Worker 2 -> Task B
Worker 3 -> Task C
Queue    -> Task D, Task E
```

某个 Worker 完成后，会继续从队列取下一个任务。

线程并非越多越好。过多线程会增加：

- 内存和线程栈开销
- 操作系统调度开销
- 上下文切换
- CPU cache 压力
- 文件系统或外部服务压力

## `executor.submit`

```python
future = executor.submit(work, "A")
```

它等价于要求工作线程将来执行：

```python
work("A")
```

`submit()` 不等待函数结束，而是立即返回 `Future`。

这使主线程可以连续提交多个任务：

```python
future_a = executor.submit(work, "A")
future_b = executor.submit(work, "B")
future_c = executor.submit(work, "C")
```

提交完成后，三个 Worker 才有机会同时处理这些任务。

## Future

`Future` 是一个保存未来结果的对象。

它可能经历：

```text
PENDING -> RUNNING -> FINISHED
```

常用方法：

```python
future.done()
```

检查任务是否完成。

```python
future.result()
```

等待并返回结果。

```python
future.exception()
```

读取任务异常。

如果工作线程抛出异常，异常会保存在 Future 中，调用 `future.result()` 时会在等待线程中重新抛出。

MiniCode 的 `ToolRegistry.call()` 会先把大多数工具异常转换成失败的 `ToolResult`，所以 Agent 通常通过 `result.ok` 处理失败。

## `future.result()`

```python
result = future.result()
```

有两种情况：

1. 任务已经完成：立即返回结果。
2. 任务尚未完成：当前线程阻塞等待。

主线程等待 Future 时，工作线程仍然继续执行。

假设三个任务同时开始：

```text
A 耗时 2.0 秒
B 耗时 1.0 秒
C 耗时 0.5 秒
```

虽然主线程按顺序调用：

```python
future_a.result()
future_b.result()
future_c.result()
```

B 和 C 并不会等 A 完成后才运行。它们已经在线程池中同时执行。

总耗时接近最慢任务的两秒，而不是三者相加的 3.5 秒。

## `with ThreadPoolExecutor`

推荐使用：

```python
with ThreadPoolExecutor(max_workers=3) as executor:
    ...
```

退出 `with` 时会调用线程池的关闭逻辑：

- 不再接受新任务。
- 等待已提交任务结束。
- 回收工作线程相关资源。

它大致相当于：

```python
executor = ThreadPoolExecutor(max_workers=3)
try:
    ...
finally:
    executor.shutdown(wait=True)
```

## MiniCode 中的代码

代码位置：

```text
src/minicode/agent.py
MiniCodeAgent._execute_tool_group()
```

核心实现：

```python
with ThreadPoolExecutor(max_workers=len(indexed_actions)) as executor:
    futures = [
        executor.submit(
            self.tool_registry.call,
            action.tool,
            action.args,
        )
        for _, action in indexed_actions
    ]
    return [
        (index, action, future.result())
        for (index, action), future
        in zip(indexed_actions, futures)
    ]
```

执行过程：

```text
AgentAction[]
  -> 为每个 Action 调用 executor.submit()
  -> 每个 Worker 执行 ToolRegistry.call()
  -> Future 保存 ToolResult
  -> 主线程调用 future.result()
  -> 按模型原始顺序整理结果
```

## 为什么结果顺序仍然稳定

工具实际完成顺序可能是：

```text
call-2
call-3
call-1
```

但 `futures` 按提交顺序保存：

```text
future-1
future-2
future-3
```

MiniCode 也按这个顺序调用 `result()`，所以最终仍是：

```text
call-1 result
call-2 result
call-3 result
```

等待第一个 Future 不会让其他线程停止。其他任务仍在后台运行，只是结果最后按稳定顺序取出。

## 为什么 Trace 不在线程里写

工作线程只负责：

```text
ToolRegistry.call() -> ToolResult
```

它们不会直接修改：

- `TraceRecorder`
- `observations`
- LLM messages
- Run 状态

线程全部返回后，由主线程统一更新这些共享状态。

这样可以减少多个线程同时修改同一个对象产生的竞态。

## 为什么写工具不能并行

两个读取通常可以安全重叠：

```text
read_file("a.py")
read_file("b.py")
```

两个写操作可能发生丢失更新：

```text
Thread A 读取旧内容
Thread B 写入新内容
Thread A 根据旧内容再次覆盖
```

所以 MiniCode 采用保守策略：

```python
parallel_safe = True
```

只用于明确无副作用的工具。

当前并行工具：

- `list_files`
- `read_file`
- `git_status`
- `git_diff`
- `load_skill`

当前串行工具：

- `replace_text`
- `write_file`
- `run_shell`

## 分组规则

MiniCode 不会把整批所有只读工具移动到最前面，而是只合并连续的安全调用。

输入：

```text
read_file A
read_file B
replace_text A
git_status
git_diff
run_shell
```

分组：

```text
[read_file A, read_file B] parallel
[replace_text A]           sequential
[git_status, git_diff]     parallel
[run_shell]                sequential
```

这样可以保留模型给出的依赖顺序。

## 失败行为

并行组中某个工具失败：

1. 已经开始的线程继续运行。
2. 主线程等待并收集组内所有结果。
3. 所有结果写入 Trace。
4. Run 标记为失败。
5. 不继续执行后续组。

串行工具失败：

1. 记录失败结果。
2. 立即停止后续工具。

## 线程、协程和进程怎么选

线程：

- 适合同步 I/O。
- 共享内存。
- 接入普通 `def` 函数简单。
- 当前 MiniCode 使用它。

协程：

- 使用 `async def` 和 `await`。
- 适合大量原生异步网络 I/O。
- 由事件循环调度，不等于操作系统线程。

进程：

- 每个进程有独立 Python 解释器和 GIL。
- 适合 CPU 密集计算。
- 创建和数据传输成本更高。

快速选择：

```text
同步文件/网络/子进程等待 -> ThreadPoolExecutor
原生 async 网络接口      -> asyncio
纯 Python CPU 密集计算    -> ProcessPoolExecutor
```

## 后续可以改进

当前线程数等于并行组任务数。更稳妥的版本应增加上限：

```python
MAX_TOOL_WORKERS = 8

max_workers = min(
    len(indexed_actions),
    MAX_TOOL_WORKERS,
)
```

后续还可以加入：

- 线程池复用
- 工具超时
- 任务取消
- 单工具并发上限
- 文件路径级读写锁
- `async` Tool handler
- CPU 工具进程池

## 最后记忆

```text
ThreadPoolExecutor
    创建和管理工作线程

executor.submit(fn, args...)
    提交任务，不等待完成，立即返回 Future

Future
    保存任务未来的结果或异常

future.result()
    等待任务完成并取得结果

with ThreadPoolExecutor(...)
    自动等待并关闭线程池
```
