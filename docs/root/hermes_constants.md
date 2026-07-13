# hermes_constants.py 注释文档

## 文件概述

`hermes_constants.py` 是 Hermes Agent 的**共享常量模块**。这是一个**导入安全**的模块 —— 没有任何依赖，可以从任何地方导入而不会导致循环导入。

## 设计原则

- 无任何依赖的安全模块
- 所有路径和配置通过函数提供
- 支持环境变量覆盖

## Hermes Home 目录管理

### `get_hermes_home() -> Path`

返回 Hermes 主目录（默认：平台原生路径）。

**解析顺序**：
1. 上下文本地覆盖（`set_hermes_home_override()`）
2. `HERMES_HOME` 环境变量
3. 平台原生默认路径：
   - Windows: `%LOCALAPPDATA%\hermes`
   - POSIX: `~/.hermes`

**安全守卫**：如果 `HERMES_HOME` 未设置但 `active_profile` 文件指示非默认配置文件处于活动状态，会向 `errors.log` 写入一次警告，防止跨配置文件数据损坏。

### `get_default_hermes_root() -> Path`

返回 Hermes 根目录，用于配置文件级操作。

**场景处理**：
- 标准部署：`~/.hermes`
- Docker/自定义部署：`HERMES_HOME` 本身
- 配置文件模式：`<root>/profiles/<name>` → 返回 `<root>`

### `set_hermes_home_override(path) -> Token`

设置上下文本地的 Hermes home 覆盖。

使用 `ContextVar` 而非 `os.environ`，因为：
- `os.environ` 被进程中每个线程共享
- `ContextVar` 提供 per-task 的作用域

## Node.js 工具链管理

### `find_node_executable(command: str) -> str | None`

解析 Node.js 命令，优先使用健康的 Hermes 管理安装。

**解析顺序**：
1. Hermes 管理的 Node 树（`$HERMES_HOME/node`）
2. 如果管理树存在但无法修复，返回 `None`
3. 系统 PATH 上的 Node/npm

### `node_tool_runnable(path: str) -> bool`

探测 Node/npm/npx 二进制文件是否**实际可运行**。

**问题背景**：部分升级或中断安装可能留下包装器文件但缺失实际模块（`MODULE_NOT_FOUND`）。单纯的存在检查不够，需要通过 `--version` 实际探测。

### `heal_hermes_managed_node() -> bool`

重新下载 Hermes 管理的 Node 树（当树存在但损坏时）。

- Windows：直接下载 portable zip
- POSIX：调用 `scripts/lib/node-bootstrap.sh`

最多每进程运行一次。

### `with_hermes_node_path(env) -> dict`

将 Hermes 管理的 Node 目录添加到 PATH 环境变量。

## 路径解析工具

### `get_hermes_dir(new_subpath, old_name) -> Path`

解析 Hermes 子目录，支持向后兼容。

**策略**：
- 如果旧路径存在且有内容，继续使用旧路径
- 否则使用新路径
- 空目录**不算**"有内容"，避免空存根静默屏蔽新布局数据

### `get_config_path() -> Path`

返回 `config.yaml` 的路径。

### `get_skills_dir() -> Path`

返回 skills 目录的路径。

### `get_env_path() -> Path`

返回 `.env` 文件的路径。

## 平台检测

### `is_termux() -> bool`

检测是否在 Termux（Android）环境中运行。

### `is_wsl() -> bool`

检测是否在 WSL（Windows Subsystem for Linux）中运行。

缓存结果以提升性能。

### `is_container() -> bool`

检测是否在容器中运行。

**检测方法**：
1. `/.dockerenv` 文件（Docker）
2. `/run/.containerenv` 文件（Podman）
3. `KUBERNETES_SERVICE_HOST` 环境变量（Kubernetes）
4. `/proc/1/cgroup` 中的 docker/podman/lxc/kubepods/containerd/crio 标记
5. `/proc/self/mountinfo` 中的 kubepods/containerd/crio 标记（cgroup v2 回退）

缓存结果以提升性能。

## 网络偏好

### `apply_ipv4_preference(force: bool = False) -> None`

Monkey-patch `socket.getaddrinfo` 以优先使用 IPv4 连接。

**问题背景**：在 IPv6 不可用或损坏的服务器上，Python 会先尝试 AAAA 记录，等待完整的 TCP 超时后才回退到 IPv4。

**实现**：拦截 `family=AF_UNSPEC` 的调用，先尝试 `AF_INET`，失败后才回退到完整解析。

## 子进程 HOME 管理

### `get_real_home(env) -> str`

返回 OS 用户的真实 home 目录，避免使用 Hermes 配置文件的 HOME。

**问题背景**：父进程可能将 `HOME` 设置为 `{HERMES_HOME}/home`，这会破坏依赖 `~` 存储凭证的外部 CLI。

### `get_subprocess_home(env) -> str | None`

返回子进程的 `HOME` 覆盖值（如果需要应用）。

**模式**：
- `auto`（默认）：主机安装保持真实用户 HOME；容器使用 `{HERMES_HOME}/home`
- `real`：始终优先真实 OS 用户 HOME
- `profile`：使用 `{HERMES_HOME}/home`（严格的 per-profile 工具配置隔离）

## 推理努力度解析

### `parse_reasoning_effort(effort) -> dict | None`

解析推理努力度级别到配置字典。

有效级别：`"minimal"`, `"low"`, `"medium"`, `"high"`, `"xhigh"`, `"max"`

特殊值：
- `"none"` / `"false"` / `"disabled"` → `{"enabled": False}`
- `False`（YAML 布尔值）→ `{"enabled": False}`
- `None` 或 `True` → `None`（使用默认值）

## 安全工具

### `secure_parent_dir(path) -> None`

对 `path` 的父目录应用 `chmod 0o700`（仅当安全时）。

**安全守卫**：拒绝 chmod `/` 或任何顶级目录，防止意外的主机损坏。

## 目录发现

### `get_optional_skills_dir() -> Path`

返回 optional-skills 目录，支持包管理器包装器。

解析顺序：
1. `HERMES_OPTIONAL_SKILLS` 环境变量
2. Wheel 安装的数据文件目录
3. 调用者提供的默认值
4. `<HERMES_HOME>/optional-skills`

### `get_optional_mcps_dir() -> Path`

返回 optional-mcps 目录，逻辑与 `get_optional_skills_dir` 相同。

### `get_bundled_skills_dir() -> Path`

返回捆绑 skills 目录。

解析顺序：
1. `HERMES_BUNDLED_SKILLS` 环境变量
2. Wheel 安装的数据文件目录
3. 调用者提供的默认值
4. `<HERMES_HOME>/skills`

## 调用关系

```
任何模块
    → from hermes_constants import get_hermes_home, OPENROUTER_BASE_URL
        → 获取配置路径、基础 URL 等常量
```
