# Toolsets.py 代码结构详解

> 文件路径：`/Users/arron/Desktop/ArronAI/hermes-sourcecode-analysis/toolsets.py`
>
> 作用：Hermes Agent 的工具集分组配置文件，定义了所有可用工具的集合（toolset），支持组合、递归解析、动态注册和验证。

---

## 1. 整体架构

`toolsets.py` 是一个纯 Python 模块，**无外部依赖**（仅使用标准库 `typing`）。它的核心职责是：

1. **定义工具集（Toolset）**：将一组相关的工具名称（字符串）归为一个逻辑集合。
2. **支持组合（Composition）**：工具集可以通过 `includes` 引用其他工具集，实现复用。
3. **动态解析（Resolution）**：将工具集递归展开为最终的工具名称列表。
4. **插件扩展（Registry Integration）**：与 `tools.registry` 集成，支持运行时动态注册工具和别名。
5. **验证与查询**：提供校验、信息查询、自定义创建等辅助函数。

---

## 2. 工具集的定义方式

### 2.1 核心数据结构

每个工具集在 `TOOLSETS` 字典中定义，结构如下：

```python
"<toolset_name>": {
    "description": "<人类可读的描述>",
    "tools": ["tool_a", "tool_b"],      # 直接包含的工具名称列表
    "includes": ["other_toolset"],      # 引用的其他工具集名称列表（可选）
    "posture": True,                    # 特殊标记：是否为"姿势"工具集（可选）
    "module": "tools.xxx_tools",        # 关联的模块路径（可选，主要用于网关加载）
}
```

**关键设计原则：**
- `tools` 中的每一项都是**字符串**，对应某个具体工具的注册名（如 `"web_search"`）。
- `includes` 实现了**组合复用**：一个工具集可以包含其他工具集，避免重复罗列工具。
- 所有工具集名称使用**小写 + 连字符/下划线**的命名风格（如 `hermes-telegram`, `code_execution`）。

### 2.2 共享工具列表（Shared Tool Lists）

为了避免在 20+ 个平台工具集中重复书写相同的工具列表，模块顶部定义了两个**共享常量**：

```python
# 第 31-80 行
_HERMES_CORE_TOOLS = [
    # Web
    "web_search", "web_extract",
    # Terminal + process management
    "terminal", "process",
    # GUI 嵌入式终端（仅在桌面环境下可用）
    "read_terminal", "close_terminal",
    # File manipulation
    "read_file", "write_file", "patch", "search_files",
    # Vision + image generation
    "vision_analyze", "image_generate",
    # Skills
    "skills_list", "skill_view", "skill_manage",
    # Browser automation (13 tools)
    "browser_navigate", "browser_snapshot", ..., "browser_dialog",
    # Text-to-speech
    "text_to_speech",
    # Planning & memory
    "todo", "memory",
    # Session history search
    "session_search",
    # Clarifying questions
    "clarify",
    # Code execution + delegation
    "execute_code", "delegate_task",
    # Cronjob management
    "cronjob",
    # Home Assistant (gated on HASS_TOKEN)
    "ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service",
    # Kanban multi-agent coordination
    "kanban_show", "kanban_list", ..., "kanban_unblock",
    # Computer use (macOS, gated on cua-driver)
    "computer_use",
]
```

`_HERMES_CORE_TOOLS` 是 **CLI 和所有消息平台的共享核心**。修改这一处，所有平台同时生效。

```python
# 第 85-90 行
_HERMES_WEBHOOK_SAFE_TOOLS = [
    "web_search",
    "web_extract",
    "vision_analyze",
    "clarify",
]
```

`_HERMES_WEBHOOK_SAFE_TOOLS` 用于 **Webhook 场景**。由于 Webhook 可能接收来自不可信第三方的内容（如公开的 PR 标题/评论），默认工具集被**故意限制**，避免通过提示注入（prompt injection）执行本地文件/系统操作。

---

## 3. 各个工具集的职责

`TOOLSETS` 字典中定义了约 40 个工具集，可分为以下几大类：

### 3.1 基础原子工具集（Basic / Leaf Toolsets）

这些工具集只包含直接工具（`includes: []`），是最小粒度的功能单元：

| 工具集名称 | 职责 | 包含工具 |
|-----------|------|---------|
| `web` | 网络研究与内容提取 | `web_search`, `web_extract` |
| `search` | 仅搜索（无内容抓取） | `web_search` |
| `x_search` | X (Twitter) 搜索（通过 xAI） | `x_search` |
| `vision` | 图像分析 | `vision_analyze` |
| `video` | 视频分析（可选，不在默认集） | `video_analyze` |
| `image_gen` | 图像生成 | `image_generate` |
| `video_gen` | 视频生成 | `video_generate`, `xai_video_edit`, `xai_video_extend` |
| `computer_use` | 后台桌面控制（macOS/Win/Linux） | `computer_use` |
| `terminal` | 终端命令执行与进程管理 | `terminal`, `process` |
| `skills` | Skill 文档的访问与管理 | `skills_list`, `skill_view`, `skill_manage` |
| `browser` | 浏览器自动化 + 搜索 | 13 个 browser_* 工具 + `web_search` |
| `cronjob` | 定时任务管理 | `cronjob` |
| `file` | 文件读写、补丁、搜索 | `read_file`, `write_file`, `patch`, `search_files` |
| `tts` | 文本转语音 | `text_to_speech` |
| `todo` | 多步骤任务规划 | `todo` |
| `memory` | 跨会话持久记忆 | `memory` |
| `context_engine` | 由活跃上下文引擎暴露的工具 | （动态，空列表） |
| `session_search` | 历史会话搜索与总结 | `session_search` |
| `project` | 桌面项目管理（仅 GUI 会话） | `project_list`, `project_create`, `project_switch` |
| `clarify` | 向用户发起澄清问题 | `clarify` |
| `code_execution` | 程序化调用工具的 Python 脚本执行 | `execute_code` |
| `delegation` | 子代理委派 | `delegate_task` |
| `homeassistant` | 智能家居控制 | `ha_list_entities`, `ha_get_state`, `ha_list_services`, `ha_call_service` |
| `kanban` | 多智能体看板协调 | `kanban_show`, `kanban_list`, ... `kanban_unblock` |
| `discord` / `discord_admin` | Discord 读取/管理 | `discord` / `discord_admin` |
| `yuanbao` | 元宝平台工具 | `yb_query_group_info`, `yb_send_dm`, ... |
| `feishu_doc` / `feishu_drive` | 飞书文档读取/评论 | `feishu_doc_read`, `feishu_drive_*` |
| `spotify` | Spotify 播放控制 | `spotify_playback`, `spotify_search`, ... |

### 3.2 场景组合工具集（Scenario Composites）

这些工具集通过 `includes` 组合基础工具集，面向特定使用场景：

#### `debugging` — 调试与故障排查工具包

```python
"debugging": {
    "description": "Debugging and troubleshooting toolkit",
    "tools": ["terminal", "process"],
    "includes": ["web", "file"]   # 搜索错误信息和解决方案 + 文件操作
}
```

- **设计意图**：调试时需要终端执行命令、进程管理，同时需要搜索网络错误信息，以及读写日志/配置文件。
- **解析结果**：`terminal`, `process`, `web_search`, `web_extract`, `read_file`, `write_file`, `patch`, `search_files`

#### `safe` — 无终端访问的安全工具包

```python
"safe": {
    "description": "Safe toolkit without terminal access",
    "tools": [],
    "includes": ["web", "vision", "image_gen"]
}
```

- **设计意图**：在不可信或受限环境中使用，**完全排除**了可能危险的操作（终端、文件写、浏览器自动化等）。
- **解析结果**：`web_search`, `web_extract`, `vision_analyze`, `image_generate`

#### `coding` — 编码专注工具集（"姿势"工具集）

```python
"coding": {
    "description": "Coding-focused toolset: files, terminal, search, web docs, skills, todo, delegate, vision, browser",
    "tools": ["web_search", "web_extract", "terminal", "process", ... "delegate_task"],
    "includes": [],
    "posture": True,   # <-- 关键标记
}
```

- **设计意图**：在代码工作区中自动选择。保留了编码时需要的所有工具（文件操作、终端、搜索、浏览器、技能、待办、委派、视觉分析），但**去掉了**消息平台相关工具（`tts`, `image_gen`, `spotify`, `homeassistant`, `cron`, `computer_use` 等）。
- **特殊标记 `posture: True`**：表示这是一个**姿势（posture）工具集**，由 `agent/coding_context.py` 按会话动态选择，**不会**被自动恢复到按平台的工具配置中（参见 `hermes_cli/tools_config.py` 中的 non-configurable-toolset 恢复逻辑）。

### 3.3 全功能平台工具集（Full Hermes Toolsets）

这些工具集对应 Hermes Agent 支持的各种运行平台/网关。它们大多以 `_HERMES_CORE_TOOLS` 为基础，加上平台特有的扩展：

| 工具集名称 | 对应平台 | 特殊说明 |
|-----------|---------|---------|
| `hermes-acp` | 编辑器插件（VS Code, Zed, JetBrains） | 无 `clarify`（无交互式 UI） |
| `hermes-api-server` | OpenAI 兼容 API 服务器 | 无交互式 UI 工具 |
| `hermes-cli` | 交互式 CLI | 完整核心工具 |
| `hermes-cron` | 定时任务 | 与 CLI 相同核心工具，由 `hermes tools` 过滤 |
| `hermes-telegram` | Telegram 机器人 | 完整核心工具 |
| `hermes-discord` | Discord 机器人 | 核心工具 + `discord`, `discord_admin` |
| `hermes-whatsapp` | WhatsApp 机器人 | 完整核心工具 |
| `hermes-slack` | Slack 机器人 | 完整核心工具 |
| `hermes-signal` | Signal 机器人 | 完整核心工具 |
| `hermes-bluebubbles` | BlueBubbles iMessage | 完整核心工具 |
| `hermes-homeassistant` | Home Assistant 机器人 | 完整核心工具 |
| `hermes-email` | Email (IMAP/SMTP) | 完整核心工具 |
| `hermes-sms` | SMS (Twilio) | 完整核心工具 |
| `hermes-mattermost` | Mattermost | 完整核心工具 |
| `hermes-matrix` | Matrix | 完整核心工具 |
| `hermes-dingtalk` | 钉钉 | 完整核心工具 |
| `hermes-feishu` | 飞书/Lark | 核心工具 + 飞书文档/评论工具 |
| `hermes-weixin` | 微信（iLink） | 完整核心工具 |
| `hermes-qqbot` | QQ 机器人 | 完整核心工具 |
| `hermes-wecom` / `hermes-wecom-callback` | 企业微信 | 完整核心工具 |
| `hermes-yuanbao` | 元宝 Bot | 核心工具 + 元宝平台工具 |
| `hermes-webhook` | Webhook 接收 | 仅安全工具（`_HERMES_WEBHOOK_SAFE_TOOLS`） |
| `hermes-gateway` | 网关统一集 | **包含所有消息平台工具集**（见下文） |

#### `hermes-gateway` — 网关统一工具集

```python
"hermes-gateway": {
    "description": "Gateway toolset - union of all messaging platform tools",
    "tools": [],
    "includes": [
        "hermes-telegram", "hermes-discord", "hermes-whatsapp",
        "hermes-slack", "hermes-signal", "hermes-bluebubbles",
        "hermes-homeassistant", "hermes-email", "hermes-sms",
        "hermes-mattermost", "hermes-matrix", "hermes-dingtalk",
        "hermes-feishu", "hermes-wecom", "hermes-wecom-callback",
        "hermes-weixin", "hermes-qqbot", "hermes-webhook",
        "hermes-yuanbao"
    ]
}
```

- **设计意图**：网关（gateway）需要知道所有可能的消息平台工具，但不需要重复列出每个工具。通过 `includes` 引用所有平台工具集，形成**并集**。
- **注意**：`tools` 为空列表，所有工具都通过 `includes` 间接引入。

---

## 4. 工具集的依赖关系（Includes / Composition）

### 4.1 依赖图

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                     hermes-gateway                          │
                    │  (includes: all platform toolsets)                          │
                    └────────┬────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┬───────────────────┐
        │                    │                    │                   │
   ┌────▼────┐         ┌─────▼─────┐       ┌─────▼──────┐      ┌─────▼──────┐
   │hermes-  │         │hermes-    │       │hermes-     │      │hermes-     │
   │telegram │         │discord    │       │feishu      │      │yuanbao     │
   │(core)   │         │(core +    │       │(core +     │      │(core +     │
   │         │         │ discord*) │       │ feishu*)   │      │ yuanbao*)  │
   └─────────┘         └───────────┘       └────────────┘      └────────────┘
        ▲                    ▲                   ▲                  ▲
        │                    │                   │                  │
        └────────────────────┴───────────────────┴──────────────────┘
                             │
                    ┌────────▼────────┐
                    │ _HERMES_CORE_   │
                    │     TOOLS       │
                    │  (shared list)  │
                    └─────────────────┘

   ┌────────────────────────────────────────────────────────────────────────┐
   │                         Scenario Composites                            │
   │                                                                        │
   │   debugging ──includes──> [web, file]                                  │
   │   safe      ──includes──> [web, vision, image_gen]                     │
   │                                                                        │
   └────────────────────────────────────────────────────────────────────────┘
```

### 4.2 解析规则

依赖解析由 `resolve_toolset()` 函数（第 687-766 行）处理：

1. **递归展开**：遇到 `includes` 中的工具集名称时，递归调用自身获取该工具集的所有工具。
2. **去重**：使用 `set` 合并工具，同名工具只保留一份（支持菱形依赖）。
3. **循环检测**：通过 `visited` 集合检测循环依赖。若发现循环，安全地返回空列表（`[]`），不报错。
4. **特殊别名**：`"all"` 或 `"*"` 代表**所有工具集**的并集，自动包含未来新增的工具集。

```python
def resolve_toolset(name: str, visited: Set[str] = None, *, include_registry: bool = True) -> List[str]:
    if visited is None:
        visited = set()

    # 1. 特殊别名：代表所有工具
    if name in {"all", "*"}:
        all_tools: Set[str] = set()
        for toolset_name in get_toolset_names():
            resolved = resolve_toolset(toolset_name, visited.copy(), include_registry=include_registry)
            all_tools.update(resolved)
        return sorted(all_tools)

    # 2. 循环/菱形依赖检测
    if name in visited:
        return []   # 安全跳过，工具已通过其他路径收集
    visited.add(name)

    # 3. 获取工具集定义
    toolset = get_toolset(name, include_registry=include_registry)
    if not toolset:
        # 4. 为插件平台自动生成（如 hermes-<name>）
        if include_registry and name.startswith("hermes-"):
            # ... 自动构建平台工具列表 ...
            pass
        return []

    # 5. 收集直接工具 + 递归解析 includes
    tools = set(toolset.get("tools", []))
    for included_name in toolset.get("includes", []):
        included_tools = resolve_toolset(included_name, visited, include_registry=include_registry)
        tools.update(included_tools)

    return sorted(tools)
```

### 4.3 核心与非核心分离（Bundle Non-Core）

`bundle_non_core_tools()` 函数（第 659-684 行）解决了一个关键问题：

> 当用户在某个平台禁用了一个工具集（如 `hermes-discord`），如果直接减去整个工具集，会误删 `_HERMES_CORE_TOOLS` 中的共享工具（如 `terminal`, `read_file`），导致其他平台工具集也被掏空。

**解决方案**：只减去该工具集的**非核心增量**（即该平台独有的额外工具）。

```python
def bundle_non_core_tools(toolset_name: str) -> Set[str]:
    core = set(_HERMES_CORE_TOOLS)
    ts_def = get_toolset(toolset_name)
    if not (ts_def and "tools" in ts_def):
        return set(resolve_toolset(toolset_name)) - core

    # 只取该工具集独有的工具
    to_remove = set(ts_def["tools"]) - core

    # 同时处理 includes 中的非核心工具（一级深度）
    for inc in ts_def.get("includes", []):
        inc_def = get_toolset(inc)
        if inc_def and "tools" in inc_def:
            to_remove.update(set(inc_def["tools"]) - core)

    return to_remove
```

---

## 5. 验证和检查机制

### 5.1 工具集存在性校验

```python
def validate_toolset(name: str) -> bool:
    """
    Check if a toolset name is valid.
    """
    # 接受特殊别名
    if name in {"all", "*"}:
        return True
    # 检查静态定义
    if name in TOOLSETS:
        return True
    # 检查插件注册的工具集
    if name in _get_plugin_toolset_names():
        return True
    # 检查注册表别名
    return name in _get_registry_toolset_aliases()
```

校验逻辑分层检查：
1. **特殊别名**：`all` / `*` 始终有效。
2. **静态定义**：`TOOLSETS` 字典中的内置工具集。
3. **插件工具集**：运行时通过 `tools.registry` 动态注册的工具集。
4. **注册表别名**：插件可能为现有工具集注册别名（如 MCP 服务器名称映射）。

### 5.2 循环依赖安全处理

在 `resolve_toolset()` 中，循环依赖通过 `visited` 集合检测：

```python
if name in visited:
    return []   # 安全返回空列表，不抛异常
visited.add(name)
```

- **菱形依赖**（A includes B, A includes C, B includes D, C includes D）：D 被解析一次后进入 `visited`，第二次遇到时返回 `[]`，工具已通过第一次路径收集。
- **真循环**（A includes B, B includes A）：第二次遇到 A 时返回 `[]`，避免无限递归。

### 5.3 插件平台自动推断

对于以 `hermes-` 前缀命名但不在 `TOOLSETS` 中的工具集，模块会尝试**自动生成**：

```python
if include_registry and name.startswith("hermes-"):
    platform_name = name[len("hermes-"):]
    try:
        from gateway.platform_registry import platform_registry
        if platform_registry.is_registered(platform_name):
            plugin_tools = set(_HERMES_CORE_TOOLS)
            # 合并该插件注册到对应 toolset 的工具
            plugin_tools.update(
                e.name for e in registry._tools.values()
                if e.toolset == platform_name
            )
            return list(plugin_tools)
    except Exception:
        pass
```

这使得新增消息平台**无需修改 `toolsets.py`**，只需在网关注册平台并注册工具即可自动获得完整工具集。

### 5.4 条件工具的门控（Gating）

虽然 `toolsets.py` 本身只是静态配置，但部分工具的**实际可用性**由外部的 `check_fn` 控制：

- `read_terminal`, `close_terminal`：仅在 `HERMES_DESKTOP` 环境变量设置时可用。
- `ha_*` (Home Assistant)：仅在 `HASS_TOKEN` 配置时可用。
- `kanban_*`：仅在 `HERMES_KANBAN_TASK` 环境变量设置或当前 profile 启用看板工具集时可用。
- `computer_use`：仅在 `cua-driver` 已安装时可用。

这些门控逻辑不在 `toolsets.py` 中，而在各自的工具实现文件（如 `tools/kanban_tools.py`）或网关加载逻辑中。

---

## 6. 运行时动态操作

### 6.1 自定义工具集创建

```python
def create_custom_toolset(
    name: str,
    description: str,
    tools: List[str] = None,
    includes: List[str] = None
) -> None:
    TOOLSETS[name] = {
        "description": description,
        "tools": tools or [],
        "includes": includes or []
    }
```

允许在运行时向 `TOOLSETS` 字典注入新的工具集定义。

### 6.2 多工具集联合解析

```python
def resolve_multiple_toolsets(toolset_names: List[str]) -> List[str]:
    all_tools = set()
    for name in toolset_names:
        tools = resolve_toolset(name)
        all_tools.update(tools)
    return sorted(all_tools)
```

用于同时启用多个工具集的场景（如用户自定义配置 `"web,terminal,file"`）。

### 6.3 工具集详细信息查询

```python
def get_toolset_info(name: str) -> Dict[str, Any]:
    toolset = get_toolset(name)
    if not toolset:
        return None

    resolved_tools = resolve_toolset(name)

    return {
        "name": name,
        "description": toolset["description"],
        "direct_tools": toolset["tools"],      # 直接声明的工具
        "includes": toolset["includes"],       # 引用的子工具集
        "resolved_tools": resolved_tools,      # 递归展开后的全部工具
        "tool_count": len(resolved_tools),
        "is_composite": bool(toolset["includes"])  # 是否为组合工具集
    }
```

---

## 7. 与插件注册表（Registry）的集成

`toolsets.py` 通过 `get_toolset()` 函数与 `tools.registry` 模块解耦集成：

```python
def get_toolset(name: str, *, include_registry: bool = True) -> Optional[Dict[str, Any]]:
    toolset = TOOLSETS.get(name)

    if not include_registry:
        # 静态视图：仅返回 TOOLSETS 中的定义
        if not toolset:
            return None
        return {**toolset, "tools": list(toolset.get("tools", [])), ...}

    # 动态视图：合并注册表中为该 toolset 注册的工具
    try:
        from tools.registry import registry
    except Exception:
        return toolset if toolset else None

    if toolset:
        merged_tools = sorted(
            set(toolset.get("tools", []))
            | set(registry.get_tool_names_for_toolset(name))
        )
        return {**toolset, "tools": merged_tools}

    # 处理纯注册表工具集（插件添加的全新 toolset）
    # ...
```

**`include_registry` 参数的关键作用：**

- **`True`（默认）**：返回动态合并视图。适用于实际运行时代理获取工具列表。
- **`False`（静态视图）**：仅返回 `TOOLSETS` 中的原始定义。用于平台反向映射（`_get_platform_tools`），避免注册表新增的工具导致整个工具集被错误地从平台推断中排除（参见 issue #49622）。

---

## 8. 总结

| 组件 | 职责 |
|------|------|
| `_HERMES_CORE_TOOLS` | 共享核心工具列表，被所有 CLI/消息平台复用 |
| `_HERMES_WEBHOOK_SAFE_TOOLS` | Webhook 场景的安全子集，防止提示注入 |
| `TOOLSETS` | 所有工具集的静态定义字典 |
| `get_toolset()` | 按名称获取工具集定义，支持注册表合并 |
| `resolve_toolset()` | 递归解析工具集，处理 includes、循环检测、特殊别名 |
| `bundle_non_core_tools()` | 提取平台工具集的非核心增量，用于安全禁用 |
| `resolve_multiple_toolsets()` | 联合解析多个工具集 |
| `validate_toolset()` | 校验工具集名称是否有效 |
| `create_custom_toolset()` | 运行时创建自定义工具集 |
| `get_toolset_info()` | 获取工具集的完整元数据 |
| `get_all_toolsets()` / `get_toolset_names()` | 枚举所有可用工具集 |

`toolsets.py` 的设计体现了**分层、组合、扩展**的思想：基础原子工具集像乐高积木，通过 `includes` 组合成面向场景和平台的复合工具集，再通过注册表机制支持运行时动态扩展，同时保持静态定义的清晰和可预测。
