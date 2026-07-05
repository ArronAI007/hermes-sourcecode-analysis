# 根目录文件解释

本目录包含 Hermes Agent 的入口文件和核心配置。

## 文件列表

| 文件 | 大小 | 职责 | 文档位置 |
|------|------|------|---------|
| `hermes_bootstrap.py` | 8.4KB | Windows UTF-8 修复、模块路径保护 | 原文件注释 |
| `run_agent.py` | 268KB | **AIAgent 类**，核心编排器 | `docs/root/run_agent.md` |
| `cli.py` | 738KB | **CLI/TUI 界面** | `docs/root/cli.md` |
| `mcp_serve.py` | 33KB | MCP 服务端入口 | `docs/root/mcp_serve.md` |
| `batch_runner.py` | 57KB | 批量任务运行器 | `docs/root/batch_runner.md` |
| `mini_swe_runner.py` | 28KB | 软件工程运行器 | `docs/root/mini_swe_runner.md` |
| `model_tools.py` | 58KB | 工具定义 Schema、调度入口 | `docs/root/model_tools.md` |
| `toolsets.py` | 35KB | 工具集分组配置 | `docs/root/toolsets.md` |
| `toolset_distributions.py` | 12KB | 工具集分发配置 | `docs/root/toolset_distributions.md` |
| `hermes_constants.py` | 38KB | 常量定义、路径解析 | `docs/root/hermes_constants.md` |
| `hermes_logging.py` | 24KB | 日志系统配置 | `docs/root/hermes_logging.md` |
| `hermes_state.py` | 256KB | 状态管理、SQLite 数据库 | `docs/root/hermes_state.md` |
| `hermes_time.py` | 4KB | 时间工具函数 | `docs/root/hermes_time.md` |
| `utils.py` | 20KB | 通用工具函数 | `docs/root/utils.md` |
| `trajectory_compressor.py` | 69KB | 轨迹压缩 | `docs/root/trajectory_compressor.md` |
| `setup.py` | 2.3KB | 安装配置 | `docs/root/setup.md` |
| `pyproject.toml` | 21KB | Python 项目配置 | `docs/root/pyproject.md` |
| `Dockerfile` | 21KB | Docker 映像构建 | `docs/root/dockerfile.md` |

## 调用关系

```
入口点
┌───────────────────────────────────────────────────────────────────────┐
│  hermes (脚本)                                                   │
│  ├─── python cli.py              # CLI/TUI 模式                   │
│  ├─── python -m gateway.run      # 网关模式                     │
│  ├─── python mcp_serve.py        # MCP 服务模式                   │
│  └─── python batch_runner.py     # 批量任务模式                 │
└───────────────────────────────────────────────────────────────────────┘

共同依赖
    │
    ▼
hermes_bootstrap.py    # 最先执行的引导代码
    │
    ▼
run_agent.py           # AIAgent 核心类
    ├─── model_tools.py     # 工具定义
    ├─── toolsets.py        # 工具集配置
    └─── agent/             # 内部逻辑

支撑工具
    ├─── hermes_constants.py
    ├─── hermes_logging.py
    ├─── hermes_state.py
    └─── utils.py
```
