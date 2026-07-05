# tools/ 目录解释

`tools/` 是 Hermes Agent 的工具实现层，包含所有可被 LLM 调用的工具。每个工具都是一个独立的 Python 模块，实现特定的功能。

---

## 目录结构

```
tools/
├─── __init__.py
├─── file_tools.py              # 文件操作（读写、搜索、编辑）
├─── file_state.py              # 文件状态跟踪
├─── file_operations.py         # 文件操作实现
├─── terminal_tool.py           # 终端命令执行
├─── close_terminal_tool.py     # 关闭终端
├─── browser_tool.py            # 浏览器自动化
├─── browser_cdp_tool.py        # Chrome DevTools Protocol
├─── browser_camofox.py         # Camofox 浏览器
├─── browser_camofox_state.py   # Camofox 状态
├─── browser_dialog_tool.py     # 浏览器对话框
├─── browser_supervisor.py      # 浏览器监督器
├─── delegate_tool.py           # 子 Agent 委派
├─── code_execution_tool.py     # 代码沙箱执行
├─── mcp_tool.py                # MCP 工具
├─── memory_tool.py             # 记忆读写
├─── cronjob_tools.py           # 定时任务
├─── kanban_tools.py            # 看板管理
├─── discord_tool.py            # Discord 平台操作
├─── image_generation_tool.py   # 图像生成
├─── image_source.py            # 图像来源处理
├─── computer_use_tool.py       # 计算机使用
├─── checkpoint_manager.py      # 检查点管理
├─── approval.py                # 操作审批
├─── clarify_tool.py            # 清晰化工具
├─── clarify_gateway.py         # 清晰化网关
├─── fuzzy_match.py             # 模糊匹配
├─── async_delegation.py        # 异步委派
├─── daemon_pool.py             # 守护进程池
├─── debug_helpers.py           # 调试工具
├─── env_passthrough.py         # 环境变量传递
├─── env_probe.py               # 环境探测
├─── interrupt.py               # 中断处理
├─── lazy_deps.py               # 懒加载依赖
├─── managed_tool_gateway.py    # 管理工具网关
├─── mcp_oauth.py               # MCP OAuth
├─── mcp_oauth_manager.py       # MCP OAuth 管理
├─── schema_sanitizer.py        # Schema 清洗
├─── blueprints.py              # 蓝图
├─── budget_config.py           # 预算配置
├─── credential_files.py        # 凭证文件
├─── feishu_doc_tool.py         # 飞书文档
├─── feishu_drive_tool.py       # 飞书云盘
├─── fal_common.py              # FAL 通用
├─── homeassistant_tool.py      # 家庭助手
├─── binary_extensions.py       # 二进制扩展名
├─── ansi_strip.py              # ANSI 字符剥离
└─── ... (其他文件)
```

---

## 工具分类

### 文件操作

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `file_tools.py` | 96KB | 文件工具入口，提供 LLM 可调用的文件操作 | `file_tools.md` |
| `file_operations.py` | 106KB | 文件操作的实际实现 | `file_operations.md` |
| `file_state.py` | 12KB | 文件状态跟踪（高亮、行号等） | `file_state.md` |

### 终端与命令

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `terminal_tool.py` | ~80KB | 执行 shell 命令 | `terminal_tool.md` |
| `close_terminal_tool.py` | 3KB | 关闭终端会话 | `close_terminal_tool.md` |

### 浏览器

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `browser_tool.py` | 206KB | 浏览器工具主入口 | `browser_tool.md` |
| `browser_cdp_tool.py` | 27KB | Chrome DevTools Protocol 工具 | `browser_cdp_tool.md` |
| `browser_camofox.py` | 35KB | Camofox 浏览器控制 | `browser_camofox.md` |
| `browser_supervisor.py` | 63KB | 浏览器监督器 | `browser_supervisor.md` |
| `browser_dialog_tool.py` | 5KB | 浏览器对话框处理 | `browser_dialog_tool.md` |

### 委派与执行

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `delegate_tool.py` | 151KB | **子 Agent 委派**，fork 独立工作流 | `delegate_tool.md` |
| `async_delegation.py` | 20KB | 异步委派支持 | `async_delegation.md` |
| `code_execution_tool.py` | 78KB | 代码沙箱执行 | `code_execution_tool.md` |

### 记忆与任务

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `memory_tool.py` | 66KB | 记忆读写操作 | `memory_tool.md` |
| `cronjob_tools.py` | 66KB | 定时任务管理 | `cronjob_tools.md` |
| `kanban_tools.py` | 68KB | 看板任务管理 | `kanban_tools.md` |

### 图像与多媒体

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `image_generation_tool.py` | 66KB | 图像生成 | `image_generation_tool.md` |
| `image_source.py` | 14KB | 图像来源处理 | `image_source.md` |
| `computer_use_tool.py` | 1KB | 计算机使用工具入口 | `computer_use_tool.md` |

### 平台集成

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `discord_tool.py` | 34KB | Discord 平台操作 | `discord_tool.md` |
| `feishu_doc_tool.py` | 5KB | 飞书文档 | `feishu_doc_tool.md` |
| `feishu_drive_tool.py` | 13KB | 飞书云盘 | `feishu_drive_tool.md` |
| `homeassistant_tool.py` | 18KB | Home Assistant | `homeassistant_tool.md` |

### 安全与审批

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `approval.py` | 129KB | **操作审批系统** | `approval.md` |
| `checkpoint_manager.py` | 62KB | 检查点管理 | `checkpoint_manager.md` |
| `clarify_tool.py` | 8KB | 清晰化工具 | `clarify_tool.md` |
| `interrupt.py` | 3KB | 中断处理 | `interrupt.md` |

### MCP 支持

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `mcp_tool.py` | 217KB | **MCP 工具**，Model Context Protocol | `mcp_tool.md` |
| `mcp_oauth.py` | 39KB | MCP OAuth 认证 | `mcp_oauth.md` |
| `mcp_oauth_manager.py` | 32KB | MCP OAuth 管理器 | `mcp_oauth_manager.md` |

---

## 工具注册机制

工具通过 `model_tools.py` 注册到系统中：

```python
# 示例：工具定义 Schema
{
    "name": "read_file",
    "description": "读取文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "offset": {"type": "integer", "description": "起始行号"},
            "limit": {"type": "integer", "description": "最大行数"}
        },
        "required": ["path"]
    }
}
```

工具被调用时的流程：

```
LLM 响应包含工具调用
    │
    ▼
model_tools.py:handle_function_call()
    │
    ▼
解析工具名称和参数
    │
    ▼
检查审批 (approval.py)
    │
    ▼
跳转到 tools/<tool>.py:execute()
    │
    ▼
执行实际操作
    │
    ▼
返回结果给 LLM
```

---

## 工具集（Toolsets）

工具按功能分组为工具集：

| 工具集 | 包含的工具 | 说明 |
|------|----------|------|
| `terminal` | terminal_tool | Shell 命令执行 |
| `web` | browser_tool, browser_cdp_tool | 浏览器自动化 |
| `coding` | file_tools, code_execution_tool | 代码编辑和执行 |
| `delegate` | delegate_tool | 子 Agent 委派 |
| `memory` | memory_tool | 记忆管理 |
| `cron` | cronjob_tools | 定时任务 |
| `kanban` | kanban_tools | 看板管理 |
| `image_gen` | image_generation_tool | 图像生成 |
| `mcp` | mcp_tool | MCP 协议 |
