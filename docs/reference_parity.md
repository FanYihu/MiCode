# Micode Reference Parity

固定参考：`QUSETIONS/MiniCode-Python@b10f9eb79f37682ed5dbdc8a6663567533488048`。

本表记录能力等价关系，不表示复制参考源码。`planned` 是当前分支后续里程碑，
`excluded` 是用户明确排除；最终发布前所有 planned 必须转成 done 或给出解释。

| 能力域 | 参考模块 | Micode 实现 | 测试/证据 | 状态 |
|---|---|---|---|---|
| Agent loop 与 Tool contract | `agent_loop.py`, `tooling.py` | `agent.py`, `tools/registry.py` | `test_agent_integration.py`, `test_tool_registry.py` | done |
| Skill 路由 | `skills.py`, `tools/load_skill.py` | `skills.py`, `skill_routing.py` | `test_skills.py` | done |
| Session/Memory/Graph | `session.py`, `memory*.py`, `vector_memory.py` | `memory/` | memory test suite | done |
| Hook/Permission | `hooks.py`, `permissions.py` | `hooks/`, `permissions.py` | `test_hooks.py`, `test_permission.py` | done |
| Untrusted/Injection/Human Review | `auto_mode.py` input guard + Micode hardening | `security.py`, `human_review.py` | `test_security.py` | done |
| MCP | `mcp.py` | `mcp/` | `test_mcp.py` | done |
| Runtime profiles/turn kernel | `runtime_profiles.py`, `turn_kernel.py` | Stage 3 runtime package | runtime tests | planned |
| Session replay/checkpoint/rewind | `history.py`, `session.py` | Stage 3 session/checkpoint package | recovery tests | planned |
| Delegated background runtime | `background_tasks.py`, task modules | enhanced `subagents/` | subagent runtime tests | planned |
| Expanded tool catalog | `tools/` | expanded `tools/` | tool contract tests | planned |
| Provider fallback/readiness | adapters, retry, model registry | generic OpenAI-compatible provider | provider tests | planned |
| Memory pipeline/curator | `memory_pipeline.py`, curator/reranker | enhanced `memory/` | memory pipeline tests | planned |
| Local extensions | extension OpenSpec + hooks | extension manifest package | extension tests | planned |
| TUI/headless | `tui/`, `tty_app.py`, `headless.py` | Micode product surfaces | pilot/snapshot/smoke | planned |
| Cybernetic control layer | controller modules | optional `single-deep` layer | profile/e2e tests | planned |
| Structure/release readiness | engineering/readiness modules | structure/readiness commands + CI | JSON/Markdown evidence | planned |
| Gateway | removed from fixed reference | none | baseline tree audit | excluded |
| Cron | removed from fixed reference | none | baseline tree audit | excluded |
