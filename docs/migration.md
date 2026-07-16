# Micode 状态迁移

Micode 的标准运行状态目录是 `.micode`。旧版本生成的 `.minicode` 不会在
程序启动时被隐式读取或修改，必须由用户显式执行迁移。

## 执行迁移

在工作区根目录运行：

```bash
micode migrate-state
```

也可以指定其他目录：

```bash
micode migrate-state --source /path/to/.minicode --target /path/to/.micode
```

命令输出 JSON 审计报告，其中包含每个普通文件的相对路径、源文件 SHA-256
和 `copied`、`unchanged` 或 `conflict` 状态。

## 安全与幂等规则

- 迁移只复制普通文件，不跟随符号链接。
- 目标文件不存在时，先创建父目录，再保留元数据复制文件。
- 目标文件哈希相同时不重复写入，并记录为 `unchanged`。
- 目标文件哈希不同时不覆盖，并记录为 `conflict`。
- 每个成功文件都在复制后重新计算 SHA-256。
- 迁移永远不删除旧 `.minicode` 目录。
- 任意冲突都会让 CLI 返回非零退出码，方便脚本和 CI 检测。
