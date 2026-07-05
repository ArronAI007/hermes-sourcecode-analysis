# hermes_cli/ 目录解释

`hermes_cli/` 是 Hermes Agent 的命令行支持工具包，提供配置管理、认证流程、命令实现、美化输出等功能。

---

## 目录结构

```
hermes_cli/
├─── __init__.py
├─── config.py                  # 【配置管理】YAML/JSON 配置读写
├─── commands.py                # CLI 命令实现
├─── cli_commands_mixin.py      # 命令混合类（给 cli.py 使用）
├─── cli_agent_setup_mixin.py   # Agent 设置混合类
├─── auth.py                    # 【认证系统】OAuth、API Key、登录
├─── auth_commands.py           # 认证相关命令
├─── fallback_config.py         # 回退配置
├─── banner.py                  # ASCII 艺术横幅
├─── colors.py                  # 颜色定义
├─── cli_output.py              # CLI 输出格式化
├─── clipboard.py               # 剪贴板操作
├─── completion.py              # 命令补全
├─── checkpoints.py             # 检查点管理
├─── backup.py                  # 备份管理
├─── env_loader.py              # 环境变量加载
├─── timeouts.py                # 超时配置
├─── pt_input_extras.py         # prompt_toolkit 扩展
├─── claw.py                    # 爪取工具
├─── bundles.py                 # 工具包管理
├─── callbacks.py               # 回调管理
├─── build_info.py              # 构建信息
├─── codex_models.py            # Codex 模型配置
├─── codex_runtime_plugin_migration.py  # 插件迁移
├─── codex_runtime_switch.py    # Codex 运行时切换
├─── browser_connect.py         # 浏览器连接
├─── blueprint_cmd.py           # 蓝图命令
├─── active_sessions.py         # 活动会话
├─── _parser.py                 # 内部解析器
├─── _subprocess_compat.py      # 子进程兼容层
├─── subcommands/               # 子命令
│   ├─── ...
└─── dashboard_auth/            # 仪表盘认证
    ├─── ...
```

---

## 核心模块说明

### 配置系统

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `config.py` | 372KB | **核心配置**，YAML/JSON 配置的读写、验证、默认值 | `config.md` |
| `fallback_config.py` | ~10KB | 回选配置链 | `fallback_config.md` |
| `env_loader.py` | ~5KB | `.env` 文件加载 | `env_loader.md` |
| `timeouts.py` | ~5KB | 请求超时配置 | `timeouts.md` |

### 命令系统

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `commands.py` | 88KB | CLI 命令实现（model, tools, skills, config 等） | `commands.md` |
| `cli_commands_mixin.py` | 119KB | 命令混合类，供 cli.py 继承 | `cli_commands_mixin.md` |
| `cli_agent_setup_mixin.py` | 33KB | Agent 初始化混合类 | `cli_agent_setup_mixin.md` |
| `auth_commands.py` | 30KB | 认证相关命令 | `auth_commands.md` |

### 认证系统

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `auth.py` | 327KB | **认证主体**，OAuth 流、API Key 管理、密码存储 | `auth.md` |

### 美化与输出

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `banner.py` | 38KB | ASCII 艺术横幅生成 | `banner.md` |
| `cli_output.py` | 3KB | 输出格式化工具 | `cli_output.md` |
| `colors.py` | 1KB | ANSI 颜色定义 | `colors.md` |
| `completion.py` | 11KB | Tab 补全支持 | `completion.md` |

### 数据管理

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `backup.py` | 52KB | 数据备份和恢复 | `backup.md` |
| `checkpoints.py` | 17KB | 会话检查点 | `checkpoints.md` |
| `active_sessions.py` | 11KB | 活动会话列表 | `active_sessions.md` |

### Codex 支持

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `codex_models.py` | 11KB | Codex 模型列表 | `codex_models.md` |
| `codex_runtime_plugin_migration.py` | 32KB | 插件迁移工具 | `codex_runtime_plugin_migration.md` |
| `codex_runtime_switch.py` | 11KB | Codex 运行时切换 | `codex_runtime_switch.md` |

---

## 调用关系

```
cli.py
    │
    ▼
hermes_cli/
    ├─── config.py          # 加载配置
    ├─── auth.py            # 认证检查
    ├─── commands.py        # 命令执行
    ├─── env_loader.py      # 加载 .env
    ├─── banner.py          # 横幅显示
    └─── completion.py      # Tab 补全
```
