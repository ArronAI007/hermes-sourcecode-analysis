# utils.py 注释文档

## 文件概述

`utils.py` 是 Hermes Agent 各组件共享的**通用工具函数模块**。设计原则：
- 纯函数，无状态
- 不依赖其他 Hermes 模块（避免循环依赖）
- 类型安全，有完整的类型注解

## 主要功能

### 布尔值解析

#### `is_truthy_value(value: Any, default: bool = False) -> bool`

将类布尔值转换为布尔值。支持的 truthy 字符串：`"1"`, `"true"`, `"yes"`, `"on"`。

#### `env_var_enabled(name: str, default: str = "") -> bool`

检查环境变量是否设置为 truthy 值。

### 文件操作工具

#### `atomic_replace(tmp_path, target) -> str`

**原子文件替换**，保留符号链接。

**问题背景**：`os.replace(tmp, target)` 在 target 是符号链接时会替换链接本身而非目标文件，这会断开 managed 部署中从 `~/.hermes/` 到 git-tracked 配置包的符号链接。

**实现**：
1. 解析符号链接到真实路径
2. 尝试 `os.replace`
3. 如果失败且错误码是 `EXDEV`（跨设备）或 `EBUSY`（繁忙），回退到 `copyfile` + `fsync` + `unlink`

#### `atomic_json_write(path, data, ...)`

原子写入 JSON 文件：
1. 创建临时文件
2. 写入 JSON 数据
3. `fsync` 确保数据落盘
4. `atomic_replace` 原子替换目标文件
5. 恢复原始文件的权限和所有者

#### `atomic_yaml_write(path, data, ...)`

原子写入 YAML 文件，逻辑与 `atomic_json_write` 类似。

使用 `IndentDumper` 强制缩进列表项（PyYAML 默认的 "indentless" 序列会导致某些解析器拒绝）。

#### `atomic_roundtrip_yaml_update(path, key_path, value)`

使用 `ruamel.yaml` 更新 YAML 文件的单个键，**保留注释和格式**。

适用场景：用户编辑过的配置文件，需要保留注释、排序、引号和 Unicode。

### YAML/JSON 处理

#### `fast_safe_load(stream) -> Any`

使用 `CSafeLoader`（libyaml C 扩展）加速 YAML 解析，比纯 Python 的 `SafeLoader` 快约 8 倍。

在 libyaml 不可用时自动回退到 `SafeLoader`。

#### `safe_json_loads(text: str, default: Any = None) -> Any`

安全的 JSON 解析，任何解析错误都返回默认值。

### URL 解析工具

#### `base_url_hostname(base_url: str) -> str`

返回 base URL 的小写主机名。

**安全设计**：使用精确的主机名比较而非子字符串匹配，避免攻击者控制的 URL（如 `https://api.openai.com.example/v1`）被误认为原生端点。

#### `base_url_host_matches(base_url: str, domain: str) -> bool`

安全地检查 base URL 的主机名是否匹配给定域名或其子域名。

### 模型能力检测

#### `model_forces_max_completion_tokens(model: str) -> bool`

检测模型家族是否需要 `max_completion_tokens` 参数而非 `max_tokens`。

覆盖的模型：
- `gpt-4o` 系列
- `gpt-4.1` 系列
- `gpt-5` 系列
- `o1` / `o3` / `o4` 系列

处理供应商前缀（如 `openai/gpt-5.4`）。

### 环境变量辅助函数

- `env_int(key, default=0) -> int`
- `env_float(key, default=0.0) -> float`
- `env_bool(key, default=False) -> bool`

### 代理 URL 规范化

#### `normalize_proxy_url(proxy_url) -> str | None`

将 `socks://` 代理 URL 规范化为 `socks5://`，解决 httpx/aiohttp 兼容性问题。

### 文件权限保留工具

- `_preserve_file_mode(path)`: 捕获文件权限位
- `_preserve_file_owner(path)`: 捕获文件所有者 uid/gid
- `_restore_file_mode(path, mode)`: 恢复文件权限
- `_restore_file_owner(path, owner)`: 恢复文件所有者

这些函数在原子写入后恢复原始文件的权限和所有权，避免临时文件的 0o600 权限破坏 Docker/NAS 卷挂载。

## 调用关系

```
几乎所有模块
    → from utils import ...
        → 使用通用工具函数
```
