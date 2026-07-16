# Day 77：Security Review

## 本章目标

提供独立于 Agent 的只读安全复盘入口。

## CLI

```bash
micode security-review .micode/traces/<trace>.json
```

报告输出 `pass/warn/fail`、信任级别统计、注入风险统计、已审核写入数、严重级别
统计和可定位 finding。Prompt Injection 命中会产生 warn；污染后未审核写成功会
产生 critical 并令报告 fail。

专项测试覆盖 provenance、规则解释、污染升级、单次消费恢复、Run
`WAITING_HUMAN` 和安全报告。
