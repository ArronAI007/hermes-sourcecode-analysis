# Hermes Agent 文件操作工具详解 (`file_tools.py`)

> **模块位置**: `/Users/arron/Desktop/ArronAI/hermes-sourcecode-analysis/tools/file_tools.py`
> **配套模块**: `/Users/arron/Desktop/ArronAI/hermes-sourcecode-analysis/tools/file_operations.py`, `/Users/arron/Desktop/ArronAI/hermes-sourcecode-analysis/tools/file_state.py`
> **核心职责**: 为 LLM Agent 提供安全、可靠、可审计的文件读写、搜索和编辑能力。

---

## 1. 架构概览

`file_tools.py` 是 Hermes Agent 与文件系统交互的核心网关。它不仅仅是简单的文件读写封装，而是一个多层安全、状态感知、防循环的复杂系统。其设计目标是在赋予 Agent 强大文件操作能力的同时，防止其陷入无限循环、误操作系统文件、或在多 Agent 协作时覆盖彼此的修改。

整个文件工具系统可以分为三个主要层次：

1.  **工具接口层 (`file_tools.py`)**: 负责接收来自 LLM 的工具调用请求（如 `read_file`, `write_file`），执行参数校验、安全审查、状态跟踪，并最终调用底层实现。
2.  **底层操作层 (`file_operations.py`)**: 提供跨终端环境（本地、Docker、SSH 等）的统一文件操作抽象。它通过 shell 命令（如 `sed`, `rg`, `cat`）或进程内逻辑（如 `ast.parse`）来执行实际的 I/O 操作。
3.  **状态协调层 (`file_state.py`)**: 一个进程级的单例注册表，用于在多 Agent（或子 Agent）并发执行时，协调对同一文件的读写操作，防止“读后写”冲突。

### 1.1 代码结构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                     模型请求 (Model Request)                          │
│        read_file, write_file, patch, search_files                     │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     工具接口层 (file_tools.py)                        │
│  ┌──────────────┬──────────────┬──────────────┬───────────────────┐  │
│  │ read_file    │ write_file   │ patch        │ search_files      │  │
│  │ _tool        │ _tool        │ _tool        │ _tool             │  │
│  └──────────────┴──────────────┴──────────────┴───────────────────┘  │
│  ┌──────────────┬──────────────┬───────────────────────────────────┐  │
│  │ 路径解析     │ 安全检查     │ 状态跟踪与防循环                  │  │
│  │ (_resolve_*) │ (_check_*)   │ (_read_tracker, file_state)       │  │
│  └──────────────┴──────────────┴───────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   底层操作层 (file_operations.py)                     │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │           ShellFileOperations (跨环境统一抽象)                 │   │
│  │  ┌────────┬─────────┬──────────────┬──────────────────────┐   │   │
│  │  │ _exec()│ read_*  │ write_file() │ patch_replace/v4a()  │   │   │
│  │  │ (Shell)│         │              │                      │   │   │
│  │  └────────┴─────────┴──────────────┴──────────────────────┘   │   │
│  │  ┌──────────────────────────────────────────────────────────┐ │   │
│  │  │  语法检查 (_check_lint*) & LSP 语义诊断 (_maybe_lsp_*)   │ │   │
│  │  └──────────────────────────────────────────────────────────┘ │   │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    状态协调层 (file_state.py)                         │
│         FileStateRegistry (跨 Agent 文件状态单例)                     │
│  ┌──────────────┬──────────────┬──────────────────────────────────┐  │
│  │ record_read  │ note_write   │ check_stale (冲突检测)           │  │
│  └──────────────┴──────────────┴──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心组件与函数详解

### 2.1 路径解析系统 (`_resolve_*`)

这是整个文件工具最基础也最复杂的部分之一。由于 Agent 可能在不同的工作目录（如 Git Worktree）或不同的执行环境（如 Docker 容器）中运行，路径解析必须非常精确，以防止“工作目录漂移”错误（即 Agent 认为自己在 A 目录，但文件写到了 B 目录）。

#### `_expand_tilde(path: str) -> str`

负责将路径中的 `~` 展开为用户的主目录。这里有一个特殊处理：它会优先使用 `hermes_constants.get_subprocess_home()` 获取的“有效 profile home”，而不是简单的 `os.path.expanduser`。这是为了确保在网关进程（gateway process）和交互式 CLI 会话中，`~` 的解析结果是一致的，避免在定时任务（cron job）中路径解析错误。

```python
def _expand_tilde(path: str) -> str:
    if not path or "~" not in path:
        return path
    try:
        from hermes_constants import get_subprocess_home
        home = get_subprocess_home()
    except Exception:
        home = None
    if home and (path == "~" or path.startswith("~/")):
        return home if path == "~" else os.path.join(home, path[2:])
    return os.path.expanduser(path)
```

#### `_resolve_base_dir(task_id: str) -> Path | PurePosixPath`

这是路径解析的核心。它决定了相对路径的“锚点”。解析顺序如下：

1.  **实时终端 CWD (Live Terminal CWD)**: 如果 Agent 已经通过 `terminal_tool` 执行过 `cd` 命令，那么当前的工作目录是最权威的。
2.  **注册的任务 CWD 覆盖 (Registered Task CWD Override)**: 对于 TUI、Desktop 或 ACP 会话，在没有任何终端命令运行前，会注册一个特定的工作区路径。
3.  **`$TERMINAL_CWD` 环境变量**: 由 `cli.py` 或 `main.py` 在启动 `-w` 会话时设置。这里会严格过滤掉 `""`, `"."`, `"auto"` 等哨兵值，防止它们被错误地解析为进程当前目录。
4.  **进程当前目录 (Process CWD)**: 最后的 fallback。

```python
def _resolve_base_dir(task_id: str = "default", *, container_paths: bool | None = None):
    root = _authoritative_workspace_root(task_id)
    # ... 容器路径与本地路径的差异化处理 ...
    if root:
        base_text = _expand_tilde(root)
    else:
        base_text = os.getcwd()
    # 如果是容器后端（如 Docker），使用 PurePosixPath 避免宿主机符号链接干扰
    if container_paths:
        return _normalize_without_host_deref(base_text)
    # 本地路径则使用 Path.resolve() 获取绝对路径
    base = Path(base_text)
    if not base.is_absolute():
        base = Path(os.getcwd()) / base
    return base.resolve()
```

#### `_path_resolution_warning(...)`

这是一个防御性函数。当 Agent 传入一个相对路径，但解析后的绝对路径**超出了**当前任务的工作区根目录时，它会返回一条警告。这能有效防止 Agent 在 Git Worktree 会话中，不小心将修改写入到了主仓库（main checkout）中。

---

### 2.2 安全检查系统 (`_check_*`)

安全是文件工具的重中之重。系统通过多层检查来防止 Agent 访问或修改敏感数据。

#### 设备路径黑名单 (`_is_blocked_device`)

为了防止 Agent 读取 `/dev/zero` 或 `/dev/urandom` 等导致进程挂起（无限输出或阻塞输入）的特殊设备文件，系统维护了一个黑名单，并在读取前进行静态路径检查。

```python
_BLOCKED_DEVICE_PATHS = frozenset({
    "/dev/zero", "/dev/random", "/dev/urandom", "/dev/full",
    "/dev/stdin", "/dev/tty", "/dev/console",
    # ... 还包括 /proc/self/fd/* 和 /proc/*/environ 等可能泄露秘密的路径
})
```

#### 敏感路径检查 (`_check_sensitive_path`)

阻止 Agent 直接写入系统关键位置，如 `/etc/`, `/boot/`, `/usr/lib/systemd/` 等。此外，它还会阻止写入 Hermes 自身的配置文件（`~/.hermes/config.yaml`），防止恶意或被注入的 Agent 静默关闭安全设置。

```python
def _check_sensitive_path(filepath: str, task_id: str = "default") -> str | None:
    resolved = str(_resolve_path_for_task(filepath, task_id))
    _err = f"Refusing to write to sensitive system path: {filepath}\nUse the terminal tool with sudo if you need to modify system files."
    for prefix in _SENSITIVE_PATH_PREFIXES:
        if resolved.startswith(prefix):
            return _err
    # 阻止修改 Hermes 配置文件
    hermes_config = _get_hermes_config_resolved()
    if hermes_config and resolved == hermes_config:
        return f"Refusing to write to Hermes config file: {filepath}..."
    return None
```

#### 跨 Profile 检查 (`_check_cross_profile_path`)

Hermes 支持多用户配置（profile）。此检查作为一个“软守卫”，当 Agent 试图写入另一个 profile 的 `skills/`, `plugins/`, `cron/`, `memories/` 目录时发出警告。这防止了 Agent A 意外修改 Agent B 的记忆或技能文件。

---

### 2.3 主要工具函数

#### `read_file_tool(path, offset, limit, task_id) -> str`

读取文件内容，是 Agent 最常用的工具之一。其内部逻辑非常复杂，远非简单的 `open().read()`：

1.  **分页规范化**: 调用 `normalize_read_pagination` 确保 `offset` 和 `limit` 在合法范围内。
2.  **设备/黑名单检查**: 防止读取危险文件。
3.  **文档提取**: 如果是 `.docx`, `.xlsx` 等结构化文档，会尝试先提取文本。
4.  **二进制检查**: 通过文件扩展名判断是否为二进制文件，如果是则拒绝读取。
5.  **内容去重 (Dedup)**: 如果 Agent 在短时间内重复读取同一个文件的同一区域，且文件未修改，系统会返回一个轻量级的提示（`"File unchanged since last read..."`），以节省上下文窗口的 Token。如果重复次数过多（`>= 4`），则会硬阻断（`BLOCKED`）。
6.  **字符数限制**: 单次读取的内容不能超过 `_get_max_read_chars()`（默认 100,000 字符），防止大文件撑爆上下文窗口。
7.  **敏感信息脱敏**: 读取完成后，调用 `redact_sensitive_text` 对内容中的密钥、密码等进行脱敏处理。
8.  **防循环检测**: 记录读取历史，如果 Agent 连续 4 次读取完全相同的文件区域，将强制返回错误，打断无限循环。

```python
def read_file_tool(path: str, offset: int = 1, limit: int = 500, task_id: str = "default") -> str:
    # 1. 规范化分页参数
    offset, limit = normalize_read_pagination(offset, limit)
    
    # 2. 安全检查：设备路径黑名单
    if _is_blocked_device(path, ...):
        return json.dumps({"error": "Cannot read device file..."})
    
    _resolved = _resolve_path_for_task(path, task_id)
    
    # 3. 检查重复读取（Dedup）
    dedup_key = (str(_resolved), offset, limit)
    cached_mtime = task_data.get("dedup", {}).get(dedup_key)
    if cached_mtime is not None and os.path.getmtime(str(_resolved)) == cached_mtime:
        return json.dumps({"status": "unchanged", "message": _READ_DEDUP_STATUS_MESSAGE, ...})
    
    # 4. 调用底层 ShellFileOperations 执行读取
    file_ops = _get_file_ops(task_id)
    result = file_ops.read_file(path, offset, limit)
    
    # 5. 内容长度安全检查与脱敏
    content_len = len(result.content or "")
    if content_len > _get_max_read_chars():
        return json.dumps({"error": "Read exceeds safety limit..."})
    result.content = redact_sensitive_text(result.content, file_read=True)
    
    # 6. 记录读取状态，用于防循环检测
    # ...
    return json.dumps(result_dict, ensure_ascii=False)
```

#### `write_file_tool(path, content, task_id, cross_profile) -> str`

写入文件，完全覆盖原有内容。

1.  **前置检查**: 依次执行敏感路径检查、跨 Profile 检查、内部内容检查（防止 Agent 将 `read_file` 返回的带行号的内容原样写入文件，导致文件损坏）。
2.  **跨 Agent 冲突检测**: 通过 `file_state.lock_path` 获取文件级锁，确保同一进程内不同线程对同一文件的“读-改-写”操作是串行的。然后调用 `file_state.check_stale` 检查是否有其他 Agent 在本地 Agent 读取后修改了该文件。
3.  **本地陈旧性检查**: 调用 `_check_file_staleness` 检查文件是否在本地 Agent 读取后被外部进程修改过。
4.  **执行写入**: 调用 `file_ops.write_file` 执行原子写入（通过临时文件 + `mv` 实现）。
5.  **后置处理**: 成功后，更新读取时间戳（`_update_read_timestamp`），使后续的连续写入不会触发陈旧性警告。

```python
def write_file_tool(path: str, content: str, task_id: str = "default", cross_profile: bool = False) -> str:
    # 1. 多层安全检查
    sensitive_err = _check_sensitive_path(path, task_id)
    if sensitive_err: return tool_error(sensitive_err)
    if not cross_profile:
        cross_warning = _check_cross_profile_path(path, task_id)
        if cross_warning: return tool_error(cross_warning)
    
    # 2. 获取文件锁并检查跨 Agent 冲突
    with file_state.lock_path(_resolved):
        cross_warning = file_state.check_stale(task_id, _resolved)
        stale_warning = _check_file_staleness(path, task_id)
        
        # 3. 调用底层写入
        file_ops = _get_file_ops(task_id)
        result = file_ops.write_file(_resolved, content)
        
        # 4. 更新状态
        _update_read_timestamp(path, task_id)
        file_state.note_write(task_id, _resolved)
    return json.dumps(result_dict, ensure_ascii=False)
```

#### `patch_tool(mode, path, old_string, new_string, patch, task_id) -> str`

提供了两种文件编辑模式：

*   **`replace` 模式**: 传统的“查找并替换”。它会调用 `file_operations.py` 中的 `fuzzy_find_and_replace`，该函数使用 9 种模糊匹配策略，能够容忍微小的空格和缩进差异。
*   **`patch` 模式**: 应用 V4A 格式的多文件补丁。适合批量修改。

在调用底层操作前，`patch_tool` 会进行与 `write_file_tool` 类似的安全检查、路径解析和锁获取。对于 `patch` 模式，它会解析 patch 内容，提取所有涉及的路径，并对每个路径进行敏感路径检查。如果 `old_string` 找不到，它会递增 `_patch_failure_tracker` 中的计数器，并在连续失败 3 次后，向模型发出更强烈的提示，建议其重新读取文件或使用 `write_file`。

```python
def patch_tool(mode: str = "replace", path: str = None, old_string: str = None, ...):
    # 1. 提取并检查 patch 中涉及的所有路径
    if mode == "patch" and patch:
        for _m in _re.finditer(r'^\*\*\*\s*(?:Update|Add|Delete)\s+File:\s*(.+)$', patch, _re.MULTILINE):
            v4a_path = _m.group(1).strip()
            # 检查敏感路径和跨 profile 路径...
            
    # 2. 按排序后的路径顺序获取锁，防止死锁
    with ExitStack() as _locks:
        for _r in _resolved_paths:
            _locks.enter_context(file_state.lock_path(_r))
        
        # 3. 检查每个文件是否陈旧
        for _p in _paths_to_check:
            _cross = file_state.check_stale(task_id, _r)
            _sw = _cross or _check_file_staleness(_p, task_id)
            
        # 4. 调用底层 patch 操作
        if mode == "replace":
            result = file_ops.patch_replace(_replace_target, old_string, new_string, replace_all)
        elif mode == "patch":
            result = file_ops.patch_v4a(patch)
            
    # 5. 失败处理与提示升级
    if result_dict.get("error") and "Could not find" in str(result_dict["error"]):
        failure_count = _record_patch_failure(task_id, resolved)
        if failure_count >= 3:
            result_dict["_hint"] = "This is failure #X patching ... Stop retrying ..."
```

#### `search_tool(pattern, target, path, file_glob, limit, offset, output_mode, context, task_id) -> str`

用于在文件系统中搜索内容或文件。

*   **内容搜索 (`target='content'`)**: 底层优先使用 `ripgrep` (`rg`)，回退到 `grep`。支持正则表达式、文件过滤 (`file_glob`)、上下文行 (`context`) 和多种输出模式 (`content`, `files_only`, `count`)。
*   **文件搜索 (`target='files'`)**: 使用 `rg --files` 或 `find` 按文件名模式查找。

它也具备与 `read_file_tool` 相同的**防循环检测**机制，防止 Agent 重复执行相同的搜索。

```python
def search_tool(pattern: str, target: str = "content", path: str = ".", ...):
    # 1. 防循环检测
    search_key = ("search", pattern, target, str(path), file_glob or "", limit, offset)
    # ... 如果连续执行相同搜索超过 4 次，则 BLOCKED ...
    
    # 2. 调用底层搜索
    file_ops = _get_file_ops(task_id)
    result = file_ops.search(pattern=pattern, path=path, target=target, ...)
    
    # 3. 过滤掉搜索结果中指向敏感/凭证文件的路径
    omitted = _filter_read_blocked_search_results(result, task_id)
    
    # 4. 对匹配内容脱敏
    for m in result.matches:
        m.content = redact_sensitive_text(m.content, file_read=True)
    return json.dumps(result_dict, ensure_ascii=False)
```

---

## 3. 与 `file_operations.py` 的调用关系

`file_tools.py` 是“指挥官”，`file_operations.py` 是“执行者”。两者之间的调用关系非常清晰：

### 3.1 桥梁函数: `_get_file_ops(task_id)`

`file_tools.py` 中的所有操作（读、写、搜）都不会直接操作文件系统，而是通过 `_get_file_ops(task_id)` 获取一个 `ShellFileOperations` 实例，然后调用该实例的方法。

```python
def _get_file_ops(task_id: str = "default") -> ShellFileOperations:
    # 1. 检查缓存，如果环境仍然活跃则直接返回
    cached = _file_ops_cache.get(task_id)
    if cached is not None and task_id in _active_environments:
        return cached
    
    # 2. 如果环境已被清理（如长时间会话），则重建终端环境
    if task_id not in _active_environments:
        terminal_env = _create_environment(env_type=config["env_type"], ...)
        _active_environments[task_id] = terminal_env
        
    # 3. 构建 file_ops 并缓存
    file_ops = ShellFileOperations(terminal_env)
    _file_ops_cache[task_id] = file_ops
    return file_ops
```

这个函数的核心职责是管理终端环境的生命周期。它利用 `_file_ops_cache` 缓存 `ShellFileOperations` 实例，避免重复创建。同时，它会检测底层的终端环境是否已被清理线程销毁，如果销毁了，则会重新创建，以保证长会话的稳定性。

### 3.2 `ShellFileOperations` 的核心职责

`ShellFileOperations` 类实现了 `FileOperations` 抽象接口，它将所有文件操作转化为 shell 命令，通过终端环境（`terminal_env.execute()`）执行。这带来了巨大的**跨平台/跨环境**优势：

*   **本地环境**: 命令直接在本机 shell 执行。
*   **Docker 环境**: 命令在容器内执行，但文件路径解析在宿主机完成，实现了无缝的“文件挂载”体验。
*   **SSH 环境**: 命令在远程主机执行。

它封装了诸如原子写入 (`_atomic_write`)、行尾符保留 (`_detect_file_line_ending`)、UTF-8 BOM 保留 (`_file_has_bom`)、行号添加 (`_add_line_numbers`) 等复杂细节。

### 3.3 调用流程示例: `read_file`

```
Model -> read_file_tool(path="src/main.py", offset=1, limit=50)
    -> _resolve_path_for_task("src/main.py") -> /workspace/src/main.py
    -> _is_blocked_device(...) -> False
    -> _get_file_ops("default") -> ShellFileOperations(instance)
    -> file_ops.read_file("src/main.py", 1, 50)
        -> ShellFileOperations._exec("sed -n '1,50p' 'src/main.py'")
            -> terminal_env.execute(...)
        -> ReadResult(content="1|import os\n2|...", total_lines=100, ...)
    -> redact_sensitive_text(content)
    -> json.dumps({...})
```

### 3.4 调用流程示例: `write_file`

```
Model -> write_file_tool(path="src/main.py", content="...")
    -> _check_sensitive_path("src/main.py") -> None
    -> _resolve_path_for_task("src/main.py") -> /workspace/src/main.py
    -> file_state.lock_path("/workspace/src/main.py") (获取锁)
    -> file_state.check_stale("default", "/workspace/src/main.py") -> None
    -> _get_file_ops("default") -> ShellFileOperations(instance)
    -> file_ops.write_file("/workspace/src/main.py", content)
        -> _expand_path(...) -> /workspace/src/main.py
        -> _is_write_denied(...) -> False
        -> _atomic_write("/workspace/src/main.py", content)
            -> terminal_env.execute(script_with_mktemp_and_mv, stdin_data=content)
        -> _check_lint_delta("/workspace/src/main.py", pre_content, post_content)
            -> _lint_python_inproc(content) -> (True, "")
        -> WriteResult(bytes_written=1234, lint={"status": "ok"})
    -> file_state.note_write("default", "/workspace/src/main.py")
    -> _update_read_timestamp("src/main.py", "default")
    -> json.dumps({...})
```

---

## 4. 安全检查机制深度解析

### 4.1 写入拒绝列表 (Write Denied List)

在 `file_operations.py` 中，定义了写入拒绝列表。它会阻止写入 SSH 密钥、Git 凭证、环境变量文件等。

```python
# file_operations.py
from agent.file_safety import build_write_denied_paths, build_write_denied_prefixes
WRITE_DENIED_PATHS = build_write_denied_paths(_HOME)
WRITE_DENIED_PREFIXES = build_write_denied_prefixes(_HOME)

def _is_write_denied(path: str) -> bool:
    return _shared_is_write_denied(path)
```

当 `ShellFileOperations.write_file` 或 `patch_replace` 被调用时，首先会检查目标路径是否在拒绝列表中。如果是，则直接返回错误，不会执行任何 shell 命令。

### 4.2 路径遍历防护

对于 V4A patch 模式，由于文件路径来源于 patch 字符串内容，更容易受到 prompt injection 攻击。因此，`patch_tool` 会显式检查 V4A header 中的路径是否包含 `..` 遍历组件。

```python
# file_tools.py -> patch_tool
def _reject_v4a_traversal(v4a_path: str) -> str | None:
    if has_traversal_component(v4a_path):
        return tool_error(
            f"V4A patch header contains '..' traversal: {v4a_path!r}. "
            "Use the agent's cwd-relative path (no '..') or an absolute path..."
        )
```

### 4.3 敏感内容写入防护

Agent 有时会因为上下文压力，将 `read_file` 返回的内部状态文本（例如 `"File unchanged since last read..."`）误以为是文件内容，并试图将其写入文件。`_is_internal_file_tool_content` 函数通过启发式算法检测这种错误，并拒绝写入。

```python
def _is_internal_file_status_text(content: str) -> bool:
    # 如果内容与内部状态消息完全匹配，或内容被该消息主导且很短
    if stripped == _READ_DEDUP_STATUS_MESSAGE:
        return True
    if _READ_DEDUP_STATUS_MESSAGE in stripped and len(stripped) <= 2 * len(_READ_DEDUP_STATUS_MESSAGE):
        return True
    return False

def _looks_like_read_file_line_numbered_content(content: str) -> bool:
    # 检测内容是否主要由 "LINE_NUM|CONTENT" 格式的行组成
    # 防止 Agent 将 read_file 的行号前缀也写入文件
    # ...
```

---

## 5. 文件状态跟踪系统

文件状态跟踪是 Hermes Agent 高可靠性的关键。它分为两个层面：**单 Agent 防循环**和**跨 Agent 冲突协调**。

### 5.1 单 Agent 状态跟踪 (`_read_tracker`)

`_read_tracker` 是一个以 `task_id` 为键的字典，记录了每个 Agent 会话的读取历史。其数据结构如下：

```python
_read_tracker: dict = {
    "task_id_1": {
        "last_key": ("read", "src/main.py", 1, 50), # 最近一次操作标识
        "consecutive": 3,                           # 该操作已连续执行次数
        "read_history": set(),                      # 历史读取记录 (path, offset, limit)
        "dedup": {("/abs/path", 1, 50): 1690000000.0}, # 去重缓存: key -> mtime
        "dedup_hits": {("/abs/path", 1, 50): 1},    # 去重命中次数
        "read_timestamps": {"/abs/path": 1690000000.0} # 文件最后读取时的 mtime
    }
}
```

#### 5.1.1 防重复读取 (Dedup)

当 Agent 调用 `read_file` 时，系统会记录 `(resolved_path, offset, limit)` 和文件当前的 `mtime`。如果 Agent 再次发起完全相同的读取请求，且 `mtime` 未变，系统不会重复读取文件，而是返回一个状态消息，告诉 Agent “文件未变，请参考之前的读取结果”。如果 Agent 无视该提示继续重复读取，系统在 2 次后会升级为硬阻断 (`BLOCKED`)。

#### 5.1.2 防无限循环 (Loop Detection)

如果 Agent 连续 4 次执行完全相同的 `read_file` 或 `search_files` 调用（即使文件内容有变化），系统也会硬阻断。当 Agent 执行了其他类型的工具（如 `write_file`）后，`notify_other_tool_call` 会被调用，重置 `consecutive` 计数器。

#### 5.1.3 外部修改检测 (Staleness Check)

在 `write_file_tool` 和 `patch_tool` 执行写入前，会调用 `_check_file_staleness`。它会比较文件当前的 `mtime` 和 `_read_tracker` 中记录的 `read_timestamps`。如果 `mtime` 发生了变化，说明文件在 Agent 读取后被外部进程（或其他 Agent）修改过，系统会附加一条警告信息，建议 Agent 重新读取文件。

```python
def _check_file_staleness(filepath: str, task_id: str) -> str | None:
    read_mtime = task_data.get("read_timestamps", {}).get(resolved)
    current_mtime = os.path.getmtime(resolved)
    if current_mtime != read_mtime:
        return "Warning: file was modified since you last read it..."
```

### 5.2 跨 Agent 状态协调 (`file_state.py`)

`_read_tracker` 只能解决单个 Agent 内部的问题。在多 Agent 协作或父 Agent 委托子 Agent 的场景下，需要 `FileStateRegistry` 来协调。

#### 5.2.1 `FileStateRegistry` 核心机制

这是一个进程级的单例，内部维护了三个核心数据结构：

1.  **`_reads`**: `{task_id: {resolved_path: (mtime, read_ts, partial)}}`
    记录每个 Agent 读取了哪些文件，以及读取时文件的 `mtime` 和读取时间戳。
2.  **`_last_writer`**: `{resolved_path: (task_id, write_ts)}`
    记录每个文件最后被哪个 Agent 修改。
3.  **`_path_locks`**: `{resolved_path: threading.Lock}`
    为每个文件路径维护一个独立的锁。

#### 5.2.2 冲突检测流程 (`check_stale`)

当一个 Agent（`task_id=A`）准备写入文件 `X` 时：

1.  **获取路径锁**: `lock_path(X)` 确保同一时间只有一个 Agent 能修改文件 `X`。
2.  **检查冲突**: `check_stale("A", X)` 被调用，它会检查三种冲突情况：
    *   **Case 1 (最严重)**: 兄弟 Agent 修改。如果 `_last_writer[X]` 是 `task_id=B`，且 `B` 的写入时间 `write_ts` 晚于 Agent A 上次读取 `X` 的时间 `read_ts`。这意味着 Agent B 在 Agent A 读取后修改了文件，Agent A 现在写入会覆盖 B 的修改。
    *   **Case 2**: 外部修改。如果 `_reads["A"][X]` 中记录的 `mtime` 与磁盘上当前的 `mtime` 不一致。
    *   **Case 3**: 未读即写。如果 Agent A 从未读取过文件 `X`，但文件已存在。

3.  **返回警告**: 如果检测到任何冲突，`check_stale` 会返回一条详细的警告信息，其中会指明是哪个 Agent 造成了冲突，以及冲突发生的时间。

```python
# file_state.py -> check_stale
if last_writer is not None:
    writer_tid, writer_ts = last_writer
    if writer_tid != task_id:
        read_ts = stamp[1]
        if writer_ts > read_ts:
            return (
                f"{resolved} was modified by sibling subagent "
                f"{writer_tid!r} at {_fmt_ts(writer_ts)} — after "
                f"this agent's last read at {_fmt_ts(read_ts)}. "
                "Re-read the file before writing."
            )
```

#### 5.2.3 状态更新

*   **`record_read`**: 在 `read_file_tool` 成功返回后调用，更新 Agent 的读取记录。
*   **`note_write`**: 在 `write_file_tool` 或 `patch_tool` 成功写入后调用，更新全局的 `_last_writer`，并更新该 Agent 自身的读取记录（因为写入后，Agent 已经知道了最新内容）。

### 5.3 分页与偏移量 (Offset & Limit)

为了处理大型文件并节省上下文窗口，`read_file_tool` 和 `search_tool` 都支持分页。

*   **`read_file`**: `offset` 是 1-indexed 的行号，`limit` 是最大返回行数。底层通过 `sed -n '{offset},{end_line}p'` 实现高效的分页读取。
*   **`search_files`**: `offset` 是跳过的结果数，`limit` 是最大返回结果数。底层通过 `head` 和 `tail` 管道实现分页。

当结果存在截断时，系统会在返回的 JSON 中附加一个 `_hint` 字段，明确提示 Agent 如何使用 `offset` 和 `limit` 来获取下一页内容。

```python
# read_file_tool 中的截断提示
if truncated:
    result_dict["hint"] = (
        f"Use offset={end_line + 1} to continue reading "
        f"(showing {offset}-{min(end_line, total_lines)} of {total_lines} lines)"
    )
```

---

## 6. 总结

`file_tools.py` 及其配套模块共同构建了一个企业级的 Agent 文件操作基础设施。它的设计亮点包括：

1.  **多层安全防御**: 从设备黑名单、敏感路径、跨 Profile 隔离到路径遍历防护，层层设防。
2.  **智能防循环**: 通过 Dedup 和 Loop Detection，有效防止 Agent 陷入无限读取或搜索的困境，节省 Token 和计算资源。
3.  **强一致性保障**: 通过 `file_state.py` 的跨 Agent 协调和 `_read_tracker` 的外部修改检测，最大限度地避免了并发编辑导致的数据覆盖。
4.  **环境无关性**: 借助 `ShellFileOperations`，文件操作逻辑与底层执行环境（本地/Docker/SSH）解耦，实现了“一次编写，处处运行”。
5.  **开发者体验优化**: 自动行号、语法检查、LSP 诊断、行尾符/BOM 保留、错误提示升级等细节，都旨在让 Agent 更高效、更准确地完成代码编辑任务。
