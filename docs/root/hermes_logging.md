# hermes_logging.py 注释文档

## 文件概述

`hermes_logging.py` 是 Hermes Agent 的**中心化日志配置模块**。CLI 和网关在启动时都会调用 `setup_logging()` 来配置日志系统。

## 日志文件结构

日志文件位置：`~/.hermes/logs/`（支持多配置文件）

| 日志文件 | 级别 | 内容 |
|---------|------|------|
| `agent.log` | INFO+ | 所有 Agent/工具/会话活动（主日志） |
| `errors.log` | WARNING+ | 仅错误和警告（快速排查） |
| `gateway.log` | INFO+ | 仅网关事件（mode="gateway" 时创建） |
| `gui.log` | INFO+ | 仪表盘/WebSocket/TUI 事件（mode="gui" 时创建） |

## 安全设计

- **RotatingFileHandler**：自动轮转，防止磁盘占满
- **RedactingFormatter**：过滤敏感信息，不会将密钥写入磁盘
- **Windows 特殊处理**：使用 `concurrent-log-handler` 避免轮转时的权限错误（`WinError 32`）

## 组件分离

- `gateway.log` 只接收 `gateway.*` 日志器的记录
- `gui.log` 接收仪表盘相关的记录
- `agent.log` 是万能日志（所有内容都会进入）

## 主要函数

### `setup_logging(...)`

**参数**：
- `hermes_home`: 覆盖 Hermes 主目录
- `log_level`: 最低日志级别（默认 INFO）
- `max_size_mb`: 每个日志文件的最大大小（默认 5MB）
- `backup_count`: 保留的轮转备份文件数（默认 3）
- `mode`: 调用者上下文 —— `"cli"`, `"gateway"`, `"gui"`, `"cron"`
- `force`: 强制重新设置，即使已经调用过

**幂等性**：安全地多次调用，第二次调用为空操作（除非 `force=True`）。

**实现细节**：
1. 创建日志目录
2. 读取 config.yaml 中的日志配置（best-effort）
3. 配置 `agent.log`（主活动日志）
4. 配置 `errors.log`（快速排查日志）
5. 根据 mode 配置 `gateway.log` 或 `gui.log`
6. 抑制嘈杂的第三方日志器（openai, httpx, asyncio 等）

### `set_session_context(session_id: str)` / `clear_session_context()`

**作用**：设置/清除当前线程的会话 ID。

**实现**：使用 `threading.local()` 存储 per-conversation 的会话上下文。所有日志行都会包含 `[session_id]` 便于过滤和关联。

### `_install_session_record_factory()`

**作用**：替换全局 LogRecord 工厂，在每个记录创建时注入 `session_tag`。

**设计选择**：使用 record factory 而非 Filter，因为 factory 对**所有**记录都运行（包括从子日志器传播的记录和第三方处理器的记录），保证 `%(session_tag)s` 始终可用。

### `setup_verbose_logging()`

**作用**：为 `--verbose` / `-v` 模式启用 DEBUG 级别的控制台日志。

**实现**：添加 StreamHandler 到 root logger，使用 `_safe_stderr()` 包装以容忍 Windows 上的 Unicode 编码问题。

## 内部类

### `_ManagedRotatingFileHandler`

继承自 `RotatingFileHandler`，增加两个职责：

1. **Managed 模式权限管理**：在 NixOS 等 managed 模式下，应用 `chmod 0660` 确保组可写
2. **外部轮转检测**：通过 `stat` 比较 inode，检测外部轮转（logrotate、手动 mv 等），自动重新打开文件

### `_ComponentFilter`

按日志器名称前缀过滤记录，用于将 gateway 特定记录路由到 `gateway.log`。

## Windows 特殊处理

在 Windows 上，`concurrent-log-handler` 包替代了标准库的 `RotatingFileHandler`，因为它：
- 使用跨进程文件锁（通过 `portalocker`/`pywin32`）
- 避免多进程同时写入时的 `PermissionError [WinError 32]`

POSIX 系统仍使用标准库的 `RotatingFileHandler`，因为：
- POSIX 重命名打开的文件没有问题
- NixOS managed 模式依赖 stdlib 的 `_open()`/`doRollover()` 生命周期

## 调用关系

```
cli.py / gateway/run.py 启动时
    → hermes_logging.py:setup_logging()
        → 配置日志级别、格式、处理器
        → 创建日志文件
        → 设置脱敏格式化器
```
