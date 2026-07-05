# Hermes Agent 代码架构文档

> 本文档逐行/逐块解释 Hermes Agent 项目的代码结构、模块职责和调用关系。

---

## 一、项目总览

Hermes Agent 是由 **Nous Research** 开发的自我改进 AI Agent 系统。它是唯一内置学习循环的 Agent：从经验中创建技能、在使用中改进它们、推动自身持久化知识、搜索过去对话，并跨会话构建对用户的深入模型。

### 1.1 核心特性

- **自我学习循环**：Agent 策划的记忆、自主技能创建、技能自我改进
- **多平台支持**：Telegram、Discord、Slack、WhatsApp、Signal 和 CLI
- **定时任务**：内置 cron 调度器
- **并行化处理**：生成隔离的子 Agent 执行并行工作流
- **多终端后端**：本地、Docker、SSH、Singularity、Modal、Daytona
- **研究就绪**：批量轨迹生成、轨迹压缩用于训练下一代工具调用模型

### 1.2 架构分层

```
┌─────────────────────────────────────────────────────────────────────┐
│                      用户界面层 (UI Layer)                     │
│  ┌───────────┐ ┌───────────┐ ┌──────────────────────┐  │
│  │  CLI       │ │  TUI      │ │  Gateway (Telegram,    │  │
│  │  (cli.py)  │ │          │ │  Discord, Slack...)    │  │
│  └────┼──────┘ └────┼──────┘ └───────────┼─────────────────┘  │
│       │             │                  │                    │
│       └────────────┼─────────────┼─────────────────┘                    │
│                      │                                          │
│                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │              Agent 核心编排层 (Orchestration Layer)          │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │
│  │  │  run_agent.py (AIAgent 类) - 主对话循环、工具调度、状态管理    │ │ │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │
│  │                              │                               │ │
│  │         ┌─────────────────┼────────────────────┼─────────────────┐       │ │
│  │         │                  │                              │       │ │
│  │         ▼                  ▼                              ▼       │ │
│  │  ┌────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │ │
│  │  │  agent/    │ │  model_tools.py  │ │  toolsets.py    │   │ │
│  │  │  (内部逻辑)  │ │  (工具定义)    │ │  (工具分组)  │   │ │
│  │  └────────────┘ └─────────────────────┘ └─────────────────────┘   │ │
│  │           │                │                              │   │ │
│  │           └──────────────┼────────────────────┼─────────────────┘   │ │
│  │                      ▼                                     │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │
│  │  │                 tools/ (工具实现层)                       │ │ │
│  │  │  ┌───────────────────────────────────────────────────────────────────┐ │ │ │
│  │  │  │  file_tools.py · terminal_tool.py · browser_tool.py  · delegate_tool.py  │ │ │
│  │  │  │  code_execution_tool.py · mcp_tool.py · cronjob_tools.py    │ │ │
│  │  │  └───────────────────────────────────────────────────────────────────┘ │ │ │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │              支撑层 (Support Layer)                         │  │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │  │
│  │  │  hermes_cli/ (配置、认证、命令)                        │  │  │
│  │  │  hermes_state.py (状态管理) · hermes_constants.py (常量)  │  │  │
│  │  │  hermes_logging.py (日志) · utils.py (通用工具)          │  │  │
│  │  └───────────────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构与文档映射

以下是项目的主要目录和对应的详细文档位置：

| 项目目录 | 文档位置 | 说明 |
|---------|---------|------|
| `根目录` | `docs/root/` | 入口文件和核心配置 |
| `agent/` | `docs/agent/` | Agent 核心逻辑模块 |
| `tools/` | `docs/tools/` | 工具实现 |
| `gateway/` | `docs/gateway/` | 消息网关 |
| `hermes_cli/` | `docs/hermes_cli/` | CLI 支持工具 |
| `tests/` | `docs/tests/` | 测试套件 |
| `skills/` | `docs/skills/` | 技能系统 |
| `plugins/` | `docs/plugins/` | 插件系统 |
| `web/` | `docs/web/` | Web 前端 |
| `ui-tui/` | `docs/ui-tui/` | TUI 前端 |

---

## 三、核心文件快速导航

### 3.1 入口文件

| 文件 | 大小 | 职责 | 注释状态 |
|------|------|------|---------|
| `hermes_bootstrap.py` | 8.4KB | Windows UTF-8 修复、模块路径保护、懒加载激活 | ✅ 已注释 |
| `run_agent.py` | 268KB | **AIAgent 类**，核心编排器，处理对话循环和工具调度 | ✅ 已注释 |
| `cli.py` | 738KB | **CLI/TUI 界面**，命令行交互、REPL 循环 | ✅ 已注释 |
| `gateway/run.py` | 980KB | **网关运行时**，平台适配、会话调度 | ✅ 已注释 |
| `mcp_serve.py` | 33KB | MCP 服务端入口 | ⏳ 待注释 |
| `batch_runner.py` | 57KB | 批量任务运行器 | ⏳ 待注释 |
| `mini_swe_runner.py` | 28KB | 软件工程运行器 | ⏳ 待注释 |

### 3.2 工具系统

| 文件 | 大小 | 职责 | 注释状态 |
|------|------|------|---------|
| `model_tools.py` | 58KB | 工具定义 Schema、工具调度入口 | ✅ 已文档化 |
| `toolsets.py` | 35KB | 工具集分组、依赖检查 | ✅ 已文档化 |
| `toolset_distributions.py` | 12KB | 工具集分发配置 | ⏳ 待注释 |

### 3.3 Agent 核心

| 文件 | 大小 | 职责 | 注释状态 |
|------|------|------|---------|
| `agent/conversation_loop.py` | 298KB | **核心对话循环**，流式响应、工具调用处理 | ✅ 已文档化 |
| `agent/chat_completion_helpers.py` | 149KB | LLM API 调用封装，多提供商适配 | ✅ 已注释 |
| `agent/context_compressor.py` | 149KB | 上下文压缩、摘要生成 | ✅ 已注释 |
| `agent/memory_manager.py` | ~100KB | 记忆管理、跨会话搜索 | ✅ 已注释 |
| `agent/curator.py` | 85KB | **学习系统**，自主技能创建和改进 | ✅ 已注释 |
| `agent/agent_init.py` | 100KB | Agent 初始化流程 | ✅ 已文档化 |
| `agent/agent_runtime_helpers.py` | 144KB | 运行时辅助函数 | ⏳ 待注释 |
| `agent/error_classifier.py` | 65KB | 错误分类、故障转移策略 | ✅ 已注释 |
| `agent/insights.py` | 38KB | 会话洞察分析引擎 | ✅ 已注释 |
| `agent/redact.py` | ~20KB | 敏感信息脱敏 | ✅ 已注释 |
| `agent/usage_pricing.py` | ~30KB | Token 用量统计和费用估算 | ✅ 已注释 |

### 3.4 网关层

| 文件 | 大小 | 职责 | 注释状态 |
|------|------|------|---------|
| `gateway/run.py` | 980KB | **网关主入口**，平台适配器管理、会话调度 | ✅ 已注释 |
| `gateway/session.py` | 94KB | 会话创建、持久化、恢复 | ✅ 已注释 |
| `gateway/delivery.py` | 23KB | 消息投送路由 | ✅ 已注释 |
| `gateway/slash_commands.py` | 220KB | 斜杠命令处理 | ✅ 已注释 |
| `gateway/platform_registry.py` | 14KB | 平台适配器注册表 | ✅ 已注释 |
| `gateway/platforms/base.py` | ~245KB | 平台适配器基类 | ✅ 已注释 |
| `gateway/platforms/webhook.py` | ~47KB | Webhook 适配器 | ✅ 已注释 |

### 3.5 工具层

| 文件 | 大小 | 职责 | 注释状态 |
|------|------|------|---------|
| `tools/file_tools.py` | 96KB | 文件工具入口 | ✅ 已文档化 |
| `tools/terminal_tool.py` | ~80KB | 执行 shell 命令 | ✅ 已注释 |
| `tools/browser_tool.py` | 206KB | 浏览器自动化 | ✅ 已注释 |
| `tools/delegate_tool.py` | 151KB | **子 Agent 委派** | ✅ 已注释 |
| `tools/code_execution_tool.py` | 78KB | 代码沙箱执行 | ✅ 已注释 |
| `tools/mcp_tool.py` | 217KB | MCP 协议工具 | ✅ 已注释 |

### 3.6 支撑工具

| 文件 | 大小 | 职责 | 注释状态 |
|------|------|------|---------|
| `hermes_cli/config.py` | 372KB | **配置管理** | ✅ 已注释 |
| `hermes_cli/auth.py` | 327KB | **认证系统** | ✅ 已注释 |
| `hermes_state.py` | 256KB | 状态管理、SQLite 数据库 | ⏳ 待注释 |
| `hermes_constants.py` | 38KB | 常量定义、路径解析 | ⏳ 待注释 |
| `hermes_logging.py` | 24KB | 日志配置和管理 | ⏳ 待注释 |
| `utils.py` | 20KB | 通用工具函数 | ⏳ 待注释 |
| `trajectory_compressor.py` | 69KB | 轨迹压缩，用于训练数据 | ⏳ 待注释 |

---

## 四、调用关系图

### 4.1 CLI 模式流程

```
用户输入 $ hermes
    │
    ▼
hermes (脚本) → python cli.py
    │
    ▼
cli.py:main()
    ├─── load_cli_config()          # 加载配置 (hermes_cli/config.py)
    ├─── setup_agent()              # 初始化 AIAgent
    │       │
    │       ▼
    │   AIAgent.__init__()           # run_agent.py
    │       ├─── 加载 .env
    │       ├─── 初始化 LLM 客户端
    │       ├─── 加载工具定义 (model_tools.py)
    │       └─── 初始化记忆系统
    │
    ▼
REPL 循环 (prompt_toolkit)
    │
    ▼
用户消息 → AIAgent.run_conversation()
    │
    ▼
conversation_loop.py
    ├─── 构建消息历史
    ├─── 调用 LLM (chat_completion_helpers.py)
    ├─── 处理流式响应
    ├─── 解析工具调用
    │       │
    │       ▼
    │   model_tools.py:handle_function_call()
    │       │
    │       ▼
    │   tools/<tool>.py:execute()
    │       │
    │       ▼
    │   返回结果 → LLM 继续循环
    │
    └─── 返回最终文本给用户
```

### 4.2 Gateway 模式流程

```
平台消息 (Telegram/Discord/Slack)
    │
    ▼
gateway/platforms/<platform>.py
    │
    ▼
gateway/run.py:GatewayRunner
    ├─── 查找/创建会话 (session.py)
    ├─── 获取 AIAgent (缓存或新建)
    ├─── 构建对话历史
    │
    ▼
AIAgent.run_conversation()
    │
    ▼
返回响应
    │
    ▼
gateway/delivery.py → 发送到平台
```

---

## 五、文档使用说明

本 docs 目录下的文档按项目目录结构组织：

- **注释方式**：对于核心代码文件，在原文件中添加详细注释
- **单独解释**：对于复杂模块，在 docs/ 下创建对应的 .md 文件

每个文件的解释包含：
1. 文件职责概述
2. 导入依赖说明
3. 类/函数逐个解释
4. 关键调用链路径
5. 设计亮点和注意事项
