# model_tools.py — Hermes Agent 工具定义与调度入口

> 文件路径：`/Users/arron/Desktop/ArronAI/hermes-sourcecode-analysis/model_tools.py`

## 概述

`model_tools.py` 是 Hermes Agent 的工具编排层（thin orchestration layer），职责是：

1. **发现** `tools/` 目录下的所有自注册工具模块
2. **提供公共 API**：`get_tool_definitions`、`handle_function_call` 等
3. **管理异步桥接**：在主线程、异步上下文和 worker 线程中安全运行异步工具
4. **集成权限检查与审批流程**：在工具执行前后拦截并校验

原始版本超过 2,400 行，当前版本将所有工具元数据下沉到 `tools/registry.py`，自身仅保留调度与缓存逻辑。

---

## 1. 模块级架构与导入链

```text
run_agent.py / cli.py / batch_runner.py
           │
           ▼
   model_tools.py  ───────┬───────  tools.registry (discover_builtin_tools, registry)
           │              │
           ▼              ▼
   toolsets.py      tools/*.py (自注册)
   (resolve_toolset)
```

### 关键导入

```python
from tools.registry import discover_builtin_tools, registry
from toolsets import resolve_toolset, validate_toolset
```

- **`tools.registry`**：中央注册表，线程安全，持有所有工具的 `ToolEntry`
- **`toolsets`**：静态 + 动态工具集定义系统，支持组合与别名

---

## 2. 工具 JSON Schema 的定义方式

Hermes 采用**自注册模式（self-registration）**：每个工具文件在模块级定义 JSON Schema，并在导入时调用 `registry.register(...)` 完成注册。

### 2.1 示例：`tools/web_tools.py` 中的 Schema 定义

```python
# tools/web_tools.py (末尾)

WEB_SEARCH_SCHEMA = {
    "name": "web_search",
    "description": (
        "Search the web for information. Returns up to 5 results by default "
        "with titles, URLs, and descriptions..."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up on the web..."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return. Defaults to 5.",
                "minimum": 1,
                "maximum": 100,
                "default": 5
            }
        },
        "required": ["query"]
    }
}

registry.register(
    name="web_search",
    toolset="web",
    schema=WEB_SEARCH_SCHEMA,
    handler=lambda args, **kw: web_search_tool(args.get("query", ""), limit=args.get("limit", 5)),
    check_fn=check_web_api_key,      # 可用性检查函数
    requires_env=_web_requires_env(), # 所需环境变量列表
    emoji="🔍",
    max_result_size_chars=100_000,
)
```

### 2.2 Schema 字段说明

| 字段 | 说明 |
|------|------|
| `name` | 工具唯一标识名 |
| `description` | LLM 看到的工具描述 |
| `parameters` | 符合 JSON Schema Draft 7 的参数定义 |
| `required` | 必填参数列表 |

### 2.3 动态 Schema 覆盖

某些工具的 Schema 需要运行时动态调整（如 `delegate_task` 的并发限制），`ToolEntry` 支持 `dynamic_schema_overrides`：

```python
# tools/registry.py
class ToolEntry:
    # ...
    dynamic_schema_overrides: Callable  # 零参数函数，返回 dict
```

在 `registry.get_definitions()` 中，每次调用都会合并静态 Schema 与动态覆盖：

```python
if entry.dynamic_schema_overrides is not None:
    overrides = entry.dynamic_schema_overrides()
    schema_with_name.update(overrides)
```

---

## 3. 工具发现机制（Discovery）

### 3.1 `discover_builtin_tools()` — 自动扫描

```python
# tools/registry.py

def discover_builtin_tools(tools_dir: Optional[Path] = None) -> List[str]:
    tools_path = Path(tools_dir) if tools_dir is not None else Path(__file__).resolve().parent
    module_names = [
        f"tools.{path.stem}"
        for path in sorted(tools_path.glob("*.py"))
        if path.name not in {"__init__.py", "registry.py", "mcp_tool.py"}
        and _module_registers_tools(path)  # AST 检测是否包含 registry.register()
    ]
    # ... import each module
```

**关键设计**：使用 AST 而非正则匹配，确保只导入真正包含 `registry.register()` 顶层调用的模块。

### 3.2 发现时机

```python
# model_tools.py (模块级，导入时执行)
discover_builtin_tools()

# Plugin 工具发现
try:
    from hermes_cli.plugins import discover_plugins
    discover_plugins()
except Exception as e:
    logger.debug("Plugin discovery failed: %s", e)
```

**注意**：MCP 工具发现已从模块级移除（见代码注释 #16856），改为由各入口点显式调用，避免阻塞网关心跳。

---

## 4. 工具集（Toolset）加载机制

### 4.1 核心数据结构：`toolsets.py`

```python
# toolsets.py

_HERMES_CORE_TOOLS = [
    "web_search", "web_extract",
    "terminal", "process",
    "read_file", "write_file", "patch", "search_files",
    # ... 约 30+ 核心工具
]

TOOLSETS = {
    "web": {
        "description": "Web research and content extraction tools",
        "tools": ["web_search", "web_extract"],
        "includes": []
    },
    "browser": {
        "description": "Browser automation...",
        "tools": ["browser_navigate", "browser_snapshot", ...],
        "includes": []
    },
    "hermes-cli": {
        "description": "Full interactive CLI toolset",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    "hermes-discord": {
        "description": "Discord bot toolset",
        "tools": _HERMES_CORE_TOOLS + ["discord", "discord_admin"],
        "includes": []
    },
    "coding": {
        "description": "Coding-focused toolset",
        "tools": [...],
        "includes": [],
        "posture": True,  # 姿态工具集，不进入配置持久化
    },
    # ... 数十个平台工具集
}
```

### 4.2 工具集解析：`resolve_toolset()`

```python
# toolsets.py

def resolve_toolset(name: str, visited: Set[str] = None, *, include_registry: bool = True) -> List[str]:
    if visited is None:
        visited = set()

    # 特殊别名：全部工具
    if name in {"all", "*"}:
        all_tools = set()
        for toolset_name in get_toolset_names():
            resolved = resolve_toolset(toolset_name, visited.copy(), include_registry=include_registry)
            all_tools.update(resolved)
        return sorted(all_tools)

    # 环路检测
    if name in visited:
        return []
    visited.add(name)

    toolset = get_toolset(name, include_registry=include_registry)
    if not toolset:
        return []

    tools = set(toolset.get("tools", []))
    for included_name in toolset.get("includes", []):
        tools.update(resolve_toolset(included_name, visited, include_registry=include_registry))

    return sorted(tools)
```

支持递归组合（如 `debugging` 包含 `web` + `file`）和环路检测。

### 4.3 在 `get_tool_definitions()` 中的过滤逻辑

```python
# model_tools.py — _compute_tool_definitions() 核心逻辑

def _compute_tool_definitions(enabled_toolsets, disabled_toolsets, ...):
    tools_to_include = set()

    if enabled_toolsets is not None:
        for toolset_name in enabled_toolsets:
            if validate_toolset(toolset_name):
                resolved = resolve_toolset(toolset_name)
                tools_to_include.update(resolved)
            elif toolset_name in _LEGACY_TOOLSET_MAP:
                # 向后兼容旧名（如 "web_tools" → ["web_search", "web_extract"]）
                tools_to_include.update(_LEGACY_TOOLSET_MAP[toolset_name])
    else:
        # 默认启用所有
        for ts_name in get_all_toolsets():
            tools_to_include.update(resolve_toolset(ts_name))

    # 减除 disabled_toolsets（对 hermes-* 平台 bundle 特殊处理，保留核心工具）
    if disabled_toolsets:
        for toolset_name in disabled_toolsets:
            if toolset_name.startswith("hermes-"):
                # 仅移除平台特有工具，保留 _HERMES_CORE_TOOLS
                to_remove = bundle_non_core_tools(toolset_name)
                tools_to_include.difference_update(to_remove)
            else:
                tools_to_include.difference_update(resolve_toolset(toolset_name))

    # 向注册表索取 Schema（同时过滤掉 check_fn 失败的工具）
    filtered_tools = registry.get_definitions(tools_to_include, quiet=quiet_mode)
    return filtered_tools
```

### 4.4 动态 Schema 重建

某些工具的 Schema 依赖可用工具集合（如 `execute_code` 的 sandbox 可用工具列表），因此 `_compute_tool_definitions` 会针对特定工具重建 Schema：

```python
# execute_code 动态 Schema：仅列出实际可用的 sandbox 工具
if "execute_code" in available_tool_names:
    sandbox_enabled = SANDBOX_ALLOWED_TOOLS & available_tool_names
    dynamic_schema = build_execute_code_schema(sandbox_enabled, mode=_get_execution_mode())
    # 替换 filtered_tools 中的 execute_code 项

# discord 动态 Schema：基于 bot 权限意图调整
for discord_tool_name in ["discord", "discord_admin"]:
    if discord_tool_name in available_tool_names:
        dynamic = schema_fn()  # 可能返回 None → 隐藏该工具
```

---

## 5. 主要函数详解

### 5.1 `get_tool_definitions()` — Schema 提供器

```python
def get_tool_definitions(
    enabled_toolsets: Optional[List[str]] = None,
    disabled_toolsets: Optional[List[str]] = None,
    quiet_mode: bool = False,
    skip_tool_search_assembly: bool = False,
) -> List[Dict[str, Any]]:
    """
    获取用于模型 API 调用的工具定义列表。

    Args:
        enabled_toolsets: 仅包含这些工具集的工具
        disabled_toolsets: 排除这些工具集的工具（enabled_toolsets 为 None 时生效）
        quiet_mode: 静默模式，抑制状态打印
        skip_tool_search_assembly: 内部使用，跳过 Tool Search 桥接组装

    Returns:
        符合 OpenAI 格式的工具定义列表
        [{"type": "function", "function": {name, description, parameters}}, ...]
    """
```

**缓存策略**：

```python
# 缓存键包含：(enabled, disabled, registry generation, config mtime, kanban flag, skip flag)
cache_key = (
    frozenset(enabled_toolsets) if enabled_toolsets is not None else None,
    frozenset(disabled_toolsets) if disabled_toolsets else None,
    registry._generation,
    cfg_fp,  # (mtime_ns, size) 指纹
    bool(os.environ.get("HERMES_KANBAN_TASK")),
    bool(skip_tool_search_assembly),
)
```

缓存上限为 8 条（LRU 淘汰），避免长期运行的 Gateway 进程无限增长。

### 5.2 `handle_function_call()` — 主调度器

```python
def handle_function_call(
    function_name: str,
    function_args: Dict[str, Any],
    task_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    session_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    api_request_id: Optional[str] = None,
    user_task: Optional[str] = None,
    enabled_tools: Optional[List[str]] = None,
    skip_pre_tool_call_hook: bool = False,
    skip_tool_request_middleware: bool = False,
    tool_request_middleware_trace: Optional[List[Dict[str, Any]]] = None,
    enabled_toolsets: Optional[List[str]] = None,
    disabled_toolsets: Optional[List[str]] = None,
) -> str:
    """
    主函数调用调度器，将调用路由到工具注册表。

    Returns:
        JSON 字符串形式的工具执行结果
    """
```

**执行流程**：

```
handle_function_call
│
├─ 1. 参数类型强制转换 (coerce_tool_args)
│   └─ 将 LLM 常犯的字符串数字/布尔值转为正确类型
│   └─ 将裸标量包装为数组（当 schema 期望 array 时）
│
├─ 2. Tool Search 桥接分发（tool_search / tool_describe / tool_call）
│   └─ tool_search / tool_describe：直接返回目录查询结果
│   └─ tool_call：解析底层工具名，递归调用 handle_function_call
│
├─ 3. 工具请求中间件 (apply_tool_request_middleware)
│   └─ 插件可重写参数
│
├─ 4. 权限检查层（详见第 6 节）
│   ├─ pre_tool_call 插件钩子（阻塞性）
│   ├─ ACP/Zed 编辑审批（write_file / patch）
│   └─ read-loop 通知重置
│
├─ 5. 实际工具执行
│   └─ registry.dispatch(function_name, function_args, ...)
│   └─ 测量执行耗时 duration_ms
│
├─ 6. 后处理钩子
│   ├─ post_tool_call 观察钩子
│   ├─ transform_tool_result 转换钩子
│   └─ 返回结果 JSON 字符串
│
└─ 异常捕获 → 返回 {"error": "..."}
```

### 5.3 `_run_async()` — 异步桥接

Hermes 的工具体系同时支持同步和异步 handler。`_run_async` 是同步 → 异步的统一桥接入口：

```python
def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 在异步上下文中（如网关事件循环）：在新线程中运行
        # 使用 ThreadPoolExecutor + 自定义事件循环，支持 300s 超时取消
        ...
    elif threading.current_thread() is not threading.main_thread():
        # Worker 线程（如 delegate_task 并行执行）：使用线程本地持久循环
        worker_loop = _get_worker_loop()
        return worker_loop.run_until_complete(coro)
    else:
        # 主线程 CLI 路径：使用全局持久循环
        tool_loop = _get_tool_loop()
        return tool_loop.run_until_complete(coro)
```

**关键设计**：使用持久循环（persistent loop）而非 `asyncio.run()`，避免 "Event loop is closed" 错误——因为缓存的 `httpx`/`AsyncOpenAI` 客户端在垃圾回收时会尝试在已关闭的循环上清理资源。

---

## 6. 权限检查与审批流程

Hermes 的权限系统是多层纵深防御（defense-in-depth），分布在多个模块中：

### 6.1 审批系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    handle_function_call                          │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ pre_tool_call │    │ ACP edit_approval │    │ read-loop guard │
│   插件钩子    │    │ (write_file/patch)│    │ (防 read 循环)  │
└───────────────┘    └─────────────────┘    └─────────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
   返回 error JSON      返回 error JSON       重置计数器
```

### 6.2 插件级阻塞：`pre_tool_call` 钩子

```python
# model_tools.py — handle_function_call()

if not skip_pre_tool_call_hook:
    block_message = get_pre_tool_call_block_message(
        function_name, function_args,
        task_id=..., session_id=..., tool_call_id=..., turn_id=..., api_request_id=...,
        middleware_trace=...
    )
    if block_message is not None:
        result = json.dumps({"error": block_message}, ensure_ascii=False)
        _emit_post_tool_call_hook(..., status="blocked", error_type="plugin_block")
        return result
```

插件可以注册 `pre_tool_call` 钩子，在工具执行前进行审查并返回阻塞消息（例如安全扫描、预算超限等）。

### 6.3 ACP/Zed 编辑审批

```python
# model_tools.py — handle_function_call()

try:
    from acp_adapter.edit_approval import maybe_require_edit_approval
    edit_block_message = maybe_require_edit_approval(function_name, function_args)
    if edit_block_message is not None:
        return edit_block_message
except Exception:
    if function_name in {"write_file", "patch"}:
        return json.dumps({"error": "Edit approval denied: approval guard failed"})
```

ACZ/Zed 编辑器集成通过 `ContextVar` 绑定请求者身份，仅在 ACP 会话中生效。

### 6.4 危险命令审批：`tools/approval.py`

这是 Hermes 最复杂的审批子系统，覆盖 `terminal` 工具的危险命令：

#### 6.4.1 审批层级

```
┌──────────────────────────────────────────────────────────────┐
│  Level 1: Hardline Blocklist（绝对禁止，无视 YOLO）            │
│  - rm -rf /, mkfs, dd to block device, fork bomb,            │
│    shutdown/reboot, kill -1                                   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼ (通过 hardline)
┌──────────────────────────────────────────────────────────────┐
│  Level 2: DANGEROUS_PATTERNS（需审批或 YOLO 绕过）            │
│  - sudo, rm -rf *, curl | sh, systemctl, 写入敏感路径等       │
└──────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
        YOLO mode ON                    YOLO mode OFF
        (HERMES_YOLO_MODE=1)            正常审批流程
              │                               │
              ▼                               ▼
        直接执行                        ┌──────────────┐
                                      │ 交互式 CLI   │ → 回调 prompt
                                      ├──────────────┤
                                      │ Gateway/API  │ → 挂起 pending queue
                                      ├──────────────┤
                                      │ Cron         │ → cron_mode 配置
                                      └──────────────┘
```

#### 6.4.2 会话隔离与上下文变量

```python
# tools/approval.py

_approval_session_key: contextvars.ContextVar[str] = contextvars.ContextVar("approval_session_key", default="")
_approval_turn_id: contextvars.ContextVar[str] = contextvars.ContextVar("approval_turn_id", default="")
_approval_tool_call_id: contextvars.ContextVar[str] = contextvars.ContextVar("approval_tool_call_id", default="")
```

所有审批状态按会话键隔离，支持并发 Gateway 会话互不干扰。

#### 6.4.3 智能审批（Smart Approval）

对于低风险命令，系统可以使用辅助 LLM 自动审批，无需打扰用户：

```python
# 伪代码流程
if command_matches_dangerous_patterns(cmd):
    if is_yolo_mode():
        return APPROVE
    if is_smart_approval_enabled() and is_low_risk(cmd):
        return SMART_APPROVE  # 自动通过，记录日志
    return PROMPT_USER       # 弹窗/消息等待用户决策
```

### 6.5 文件写入审批：`tools/write_approval.py`

针对 `memory` 和 `skills` 两个持久化子系统的写入门控：

```python
# tools/write_approval.py

class GateDecision:
    __slots__ = ("allow", "blocked", "stage", "message")
    # allow  → 直接写入
    # blocked → 用户拒绝
    # stage   → 暂存到 pending 目录，等待后续审批
```

**决策矩阵**：

| 场景 | 门控关闭 | 门控开启 + 交互式 CLI | 门控开启 + Gateway/后台 |
|------|----------|----------------------|------------------------|
| Memory 前台 | Allow | Inline prompt (Approve/Deny) | Stage to pending |
| Memory 后台 | Allow | Stage to pending | Stage to pending |
| Skills 任何来源 | Allow | Stage to pending | Stage to pending |

暂存记录保存在 `<HERMES_HOME>/pending/{memory,skills}/<id>.json`。

### 6.6 文件工具敏感路径拦截：`tools/file_tools.py`

```python
# file_tools.py 中的路径安全检查

_BLOCKED_DEVICE_PATHS = frozenset({
    "/dev/zero", "/dev/random", "/dev/urandom", "/dev/full",
    "/dev/stdin", "/dev/tty", "/dev/console",
})

_SENSITIVE_WRITE_TARGET = (
    rf'(?:/etc/|{_MACOS_PRIVATE_SYSTEM_PATH}|/dev/sd|'
    rf'{_SSH_SENSITIVE_PATH}|'
    rf'{_HERMES_ENV_PATH}|'
    rf'{_HERMES_CONFIG_PATH}|'
    rf'{_SHELL_RC_FILES}|'
    rf'{_CREDENTIAL_FILES})'
)
```

`write_file` 和 `patch` 会检查目标路径是否命中敏感模式（如 `.ssh/`、`config.yaml`、系统目录），命中则拒绝写入。

---

## 7. 调用关系图

### 7.1 工具定义与获取流程

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   run_agent.py  │     │      cli.py         │     │  batch_runner.py    │
│  AIAgent.__init__│     │  start_conversation │     │  run_batch_task     │
└────────┬────────┘     └──────────┬──────────┘     └──────────┬──────────┘
         │                         │                           │
         └─────────────────────────┼───────────────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │   get_tool_definitions()     │
                    │   (model_tools.py)           │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │  cache lookup   │  │ _compute_tool   │  │ registry.get    │
    │  (memoization)  │  │ _definitions()  │  │ _definitions()  │
    └─────────────────┘  └────────┬────────┘  │ (registry.py)   │
                                  │           └────────┬────────┘
                                  ▼                    │
                    ┌─────────────────────┐            │
                    │ enabled_toolsets?   │            │
                    │ → resolve_toolset() │            │
                    │   (toolsets.py)     │            │
                    └─────────────────────┘            │
                                  │                    │
                                  ▼                    ▼
                    ┌─────────────────────┐   ┌─────────────────┐
                    │ disabled_toolsets?  │   │ check_fn probe  │
                    │ → bundle_non_core   │   │ (TTL cache 30s) │
                    │   _tools()          │   └─────────────────┘
                    └─────────────────────┘            │
                                                       ▼
                                            ┌─────────────────────┐
                                            │ dynamic schema rebuild│
                                            │ (execute_code, discord)│
                                            └─────────────────────┘
```

### 7.2 工具执行调度流程

```
┌─────────────────────────────────────────────────────────────────────┐
│ LLM Response: function_call(name="web_search", args={"query": "x"}) │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────┐
                    │   handle_function_call()    │
                    │      (model_tools.py)       │
                    └──────────────┬──────────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       ▼                           ▼                           ▼
┌──────────────┐        ┌──────────────────┐        ┌──────────────────┐
│coerce_tool_  │        │ Tool Search      │        │ apply_tool_request│
│args()        │        │ bridge dispatch  │        │ _middleware()     │
│(类型强制转换) │        │ (tool_search/    │        │ (参数重写)        │
└──────────────┘        │  describe/call)  │        └──────────────────┘
                        └──────────────────┘                │
                                                            ▼
                    ┌──────────────────────────────────────────────────┐
                    │              权限检查层 (Permission Layer)        │
                    ├──────────────────────────────────────────────────┤
                    │ 1. pre_tool_call hook (插件阻塞)                  │
                    │ 2. ACP edit_approval (write_file/patch)           │
                    │ 3. dangerous command approval (terminal)          │
                    │ 4. write_approval gate (memory/skills)            │
                    └──────────────────────────────────────────────────┘
                                            │
                                            ▼ (通过所有检查)
                    ┌──────────────────────────────────────────────────┐
                    │              registry.dispatch()                  │
                    │                  (registry.py)                    │
                    └──────────────────────────────────────────────────┘
                                            │
                            ┌───────────────┴───────────────┐
                            ▼                               ▼
                    ┌───────────────┐               ┌───────────────┐
                    │ sync handler  │               │ async handler │
                    │ 直接调用       │               │ → _run_async()│
                    └───────────────┘               └───────┬───────┘
                                                            │
                                            ┌───────────────┼───────────────┐
                                            ▼               ▼               ▼
                                    ┌──────────┐    ┌──────────┐    ┌──────────┐
                                    │主线程持久│    │worker线程│    │新线程+   │
                                    │event loop│    │本地 loop │    │独立 loop │
                                    └──────────┘    └──────────┘    └──────────┘
                                                                            │
                                                                            ▼
                                                                    ┌──────────────┐
                                                                    │ 超时取消机制  │
                                                                    │ (300s 上限)  │
                                                                    └──────────────┘
                                            │
                                            ▼
                    ┌──────────────────────────────────────────────────┐
                    │              后处理钩子 (Post Hooks)              │
                    ├──────────────────────────────────────────────────┤
                    │ 1. _emit_post_tool_call_hook (观察)               │
                    │ 2. transform_tool_result (结果转换)               │
                    │ 3. 返回 JSON 字符串                                │
                    └──────────────────────────────────────────────────┘
```

### 7.3 工具注册与发现关系

```
┌─────────────────────────────────────────────────────────────────────┐
│                        tools/ 目录                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ web_tools.py│  │file_tools.py│  │terminal_tool│  │ browser_   │ │
│  │             │  │             │  │  .py        │  │  tool.py   │ │
│  │ WEB_SEARCH_ │  │ read_file() │  │ terminal()  │  │ navigate() │ │
│  │   SCHEMA    │  │ write_file()│  │             │  │            │ │
│  │             │  │             │  │ DANGEROUS_  │  │            │ │
│  │ registry.   │  │ registry.   │  │  PATTERNS   │  │ registry.  │ │
│  │ register()  │  │ register()  │  │             │  │ register() │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
│         │                │                │               │        │
│         └────────────────┴────────────────┴───────────────┘        │
│                                     │                               │
│                                     ▼                               │
│                         ┌─────────────────────┐                     │
│                         │   tools/registry.py   │                     │
│                         │   ToolRegistry (单例)  │                     │
│                         │   _tools: Dict[str,   │                     │
│                         │          ToolEntry]   │                     │
│                         └───────────┬───────────┘                     │
│                                     │                               │
└─────────────────────────────────────┼───────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │       model_tools.py                │
                    │  discover_builtin_tools()           │
                    │  get_tool_definitions()             │
                    │  handle_function_call()             │
                    └─────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │    run_agent.py / cli.py / gateway  │
                    └─────────────────────────────────────┘
```

---

## 8. 关键常量与状态

### 8.1 向后兼容映射

```python
# model_tools.py
_LEGACY_TOOLSET_MAP = {
    "web_tools": ["web_search", "web_extract"],
    "terminal_tools": ["terminal"],
    "vision_tools": ["vision_analyze"],
    "image_tools": ["image_generate"],
    "skills_tools": ["skills_list", "skill_view", "skill_manage"],
    "browser_tools": ["browser_navigate", "browser_snapshot", ...],
    "cronjob_tools": ["cronjob"],
    "file_tools": ["read_file", "write_file", "patch", "search_files"],
    "tts_tools": ["text_to_speech"],
}
```

### 8.2 全局状态

```python
# model_tools.py
TOOL_TO_TOOLSET_MAP: Dict[str, str] = registry.get_tool_to_toolset_map()
TOOLSET_REQUIREMENTS: Dict[str, dict] = registry.get_toolset_requirements()
_last_resolved_tool_names: List[str] = []  # 最近一次 get_tool_definitions 解析出的工具名
```

### 8.3 代理循环拦截工具

```python
# 这些工具需要 agent loop 级别的状态（TodoStore, MemoryStore），
# 因此 handle_function_call 中直接返回错误，阻止 registry.dispatch
_AGENT_LOOP_TOOLS = {"todo", "memory", "session_search", "delegate_task"}
_READ_SEARCH_TOOLS = {"read_file", "search_files"}
```

---

## 9. 错误处理与安全设计

### 9.1 工具错误清洗

```python
_TOOL_ERROR_ROLE_TAG_RE = re.compile(
    r'</?(?:tool_call|function_call|result|response|output|input|system|assistant|user)>',
    re.IGNORECASE,
)
_TOOL_ERROR_FENCE_OPEN_RE = re.compile(r'^\s*```(?:json|xml|html|markdown)?\s*', re.MULTILINE)
_TOOL_ERROR_FENCE_CLOSE_RE = re.compile(r'\s*```\s*$', re.MULTILINE)
_TOOL_ERROR_CDATA_RE = re.compile(r'<!\[CDATA\[.*?\]\]>', re.DOTALL)
_TOOL_ERROR_MAX_LEN = 2000

def _sanitize_tool_error(error_msg: str) -> str:
    """在将错误展示给模型前，剥离结构性格式化令牌。"""
    sanitized = _TOOL_ERROR_ROLE_TAG_RE.sub("", error_msg)
    sanitized = _TOOL_ERROR_FENCE_OPEN_RE.sub("", sanitized)
    sanitized = _TOOL_ERROR_FENCE_CLOSE_RE.sub("", sanitized)
    sanitized = _TOOL_ERROR_CDATA_RE.sub("", sanitized)
    if len(sanitized) > _TOOL_ERROR_MAX_LEN:
        sanitized = sanitized[:_TOOL_ERROR_MAX_LEN - 3] + "..."
    return f"[TOOL_ERROR] {sanitized}"
```

### 9.2 参数类型强制转换

LLM 经常输出字符串形式的数字或布尔值。`coerce_tool_args()` 依据 JSON Schema 做安全强制转换：

```python
def coerce_tool_args(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    schema = registry.get_schema(tool_name)
    properties = (schema.get("parameters") or {}).get("properties")

    for key, value in list(args.items()):
        prop_schema = properties.get(key)
        expected = prop_schema.get("type")

        # 1. 数组包装：将裸字符串包装为单元素列表
        if expected == "array" and value is not None and not isinstance(value, (list, tuple)):
            args[key] = [value]

        # 2. 标量类型强制：string → integer/number/boolean
        if isinstance(value, str):
            coerced = _coerce_value(value, expected, schema=prop_schema)
            if coerced is not value:
                args[key] = coerced
```

---

## 10. 缓存与性能

### 10.1 `check_fn` TTL 缓存

```python
# tools/registry.py

_CHECK_FN_TTL_SECONDS = 30.0
_CHECK_FN_FAILURE_GRACE_SECONDS = 60.0
_check_fn_cache: Dict[Callable, tuple[float, bool]] = {}
_check_fn_last_good: Dict[Callable, float] = {}
```

外部依赖探针（如 Docker daemon、Playwright 二进制、API 密钥检查）结果被缓存 30 秒，且具备**瞬态失败容错**：如果最近一次成功在 60 秒内，即使当前探测失败也视为可用（避免网络抖动导致工具被静默移除）。

### 10.2 `get_tool_definitions` 结果缓存

```python
_tool_defs_cache: Dict[tuple, List[Dict[str, Any]]] = {}
_TOOL_DEFS_CACHE_MAX = 8  # LRU 上限
```

缓存键捕获了所有输入变量 + 注册表世代计数器 + 配置文件指纹，确保配置修改能自动失效缓存。

---

## 11. 相关文件速查

| 文件 | 职责 |
|------|------|
| `model_tools.py` | 工具调度入口、异步桥接、缓存 |
| `tools/registry.py` | 工具注册表、发现、Schema 获取、dispatch |
| `toolsets.py` | 工具集定义、解析、组合 |
| `tools/approval.py` | 危险命令审批系统（终端工具） |
| `tools/write_approval.py` | 内存/技能写入门控 |
| `tools/file_tools.py` | 文件读写、路径安全、搜索 |
| `tools/web_tools.py` | Web 搜索与内容提取 |
| `tools/terminal_tool.py` | 终端命令执行、环境管理 |
| `hermes_cli/middleware.py` | 请求/执行中间件框架 |
| `acp_adapter/edit_approval.py` | ACP 编辑器集成审批 |

---

## 12. 总结

`model_tools.py` 是 Hermes Agent 工具系统的**调度中枢**：

1. **自注册架构**：`tools/*.py` 各自定义 Schema 并在导入时注册到 `registry`
2. **工具集系统**：`toolsets.py` 提供静态定义 + 动态解析，支持平台化工具组合
3. **多层权限检查**：从插件钩子 → ACP 审批 → 危险命令检测 → 写入门控，形成纵深防御
4. **异步桥接**：`_run_async()` 统一处理主线程/worker线程/异步上下文三种运行环境
5. **性能优化**：多层缓存（`check_fn` TTL + `get_tool_definitions` 结果缓存）降低每次调用的开销
