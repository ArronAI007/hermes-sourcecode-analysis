"""Windows UTF-8 bootstrap for Hermes entry points.

Python on Windows has two long-standing text-encoding footguns:

1. ``sys.stdout`` / ``sys.stderr`` are bound to the console code page
   (``cp1252`` on US-locale installs), so ``print("café")`` crashes with
   ``UnicodeEncodeError: 'charmap' codec can't encode character``.

2. Child processes spawned via ``subprocess`` don't know to use UTF-8
   unless ``PYTHONUTF8`` and/or ``PYTHONIOENCODING`` are set in their
   environment — so any Python subprocess (the execute_code sandbox,
   delegation children, linter subprocesses, etc.) inherits the same
   cp1252 defaults and hits the same UnicodeEncodeError.

This module fixes both on Windows *only* — POSIX is untouched.  It
should be imported at the very top of every Hermes entry point
(``hermes``, ``hermes-agent``, ``hermes-acp``, ``python -m gateway.run``,
``batch_runner.py``, ``cron/scheduler.py``) before any other imports
that might do file I/O or print to stdout.

What this module does on Windows:

  - Sets ``os.environ["PYTHONUTF8"] = "1"`` (PEP 540 UTF-8 mode) so
    every child process we spawn uses UTF-8 for ``open()`` and stdio.
  - Sets ``os.environ["PYTHONIOENCODING"] = "utf-8"`` for belt-and-
    suspenders — some tools read this instead of / in addition to
    ``PYTHONUTF8``.
  - Reconfigures ``sys.stdout`` / ``sys.stderr`` to UTF-8 in the current
    process, using the ``reconfigure()`` API (Python 3.7+).  This fixes
    ``print("café")`` in the parent without a re-exec.

What this module does NOT do:

  - It does not re-exec Python with ``-X utf8``, so ``open()`` calls in
    the *current* process still default to locale encoding.  Those need
    an explicit ``encoding="utf-8"`` at the call site (lint rule
    ``PLW1514`` / ``PYI058``).  Ruff is the right tool for that sweep.

What this module does on POSIX:

  - Nothing.  POSIX systems are already UTF-8 by default in 99% of cases,
    and we don't want to touch ``LANG``/``LC_*`` behavior that users may
    have configured intentionally.  If someone hits a C/POSIX locale on
    Linux, they can export ``PYTHONUTF8=1`` themselves — we won't override.

Idempotent: safe to call multiple times.  ``_bootstrap_once`` guards
against double-reconfigure.
"""

from __future__ import annotations  # 启用向未来版本兼容的类型注解（如 list[str] 而非 typing.List[str]）

import os    # 操作系统接口，用于设置环境变量、文件路径操作
import sys   # 系统特定参数和函数，用于调整 Python 运行时的模块搜索路径和标准输入/输出

# 检测当前操作系统是否为 Windows（包括 win32 和 cygwin 等变种）
# 这决实了是否需要应用 Windows 特定的 UTF-8 修复
_IS_WINDOWS = sys.platform == "win32"

# 守护标志位，确保 bootstrap 只执行一次（幂等性）
# 即使多个模块导入此模块，也不会重复执行
_bootstrap_applied = False


def apply_windows_utf8_bootstrap() -> bool:
    """Apply the Windows UTF-8 bootstrap if we're on Windows.

    Returns True if bootstrap was applied (i.e. we're on Windows and
    haven't already done this), False otherwise.  The return value is
    advisory — callers normally don't need it, but tests may want to
    assert the path was taken.

    Idempotent: subsequent calls after the first are a no-op.
    """
    global _bootstrap_applied

    if not _IS_WINDOWS:
        return False
    if _bootstrap_applied:
        return False

    # 1. Child processes inherit these and run in UTF-8 mode.
    #    We use setdefault() rather than overwriting so the user can
    #    explicitly opt out by setting PYTHONUTF8=0 in their environment
    #    (or PYTHONIOENCODING=something-else) if they really want to.
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # 2. Reconfigure the current process's stdio to UTF-8.  Needed
    #    because os.environ changes don't retroactively rebind sys.stdout
    #    — those were bound at interpreter startup based on the console
    #    code page.  ``reconfigure`` is a TextIOWrapper method since 3.7.
    #
    #    errors="replace" means that if we ever *read* something from
    #    stdin that isn't UTF-8 (unlikely but possible with piped input
    #    from legacy tools), we'll get U+FFFD replacement chars rather
    #    than a crash.  Output is pure UTF-8.
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            # Not a TextIOWrapper (could be redirected to a BytesIO in
            # tests, or a non-standard stream in some embedded cases).
            # Skip silently — the env-var fix is still in effect for
            # child processes, which is the bigger win.
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            # Already closed, or someone replaced it with something
            # non-reconfigurable.  Non-fatal.
            pass

    # stdin is reconfigured separately with errors="replace" too — input
    # from a legacy pipe shouldn't crash the process.
    stdin = getattr(sys, "stdin", None)
    if stdin is not None:
        reconfigure = getattr(stdin, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass

    _bootstrap_applied = True
    return True


def harden_import_path(src_root: str | None = None) -> None:
    """防止当前目录下的同名包覆盖 Hermes 内部模块。

    Hermes 的顶层模块名称比较通用（如 ``utils``、``proxy``、``ui``）。
    Python 默认会在 ``sys.path`` 第一个位置插入当前工作目录，
    这意味着如果用户从包含自己的 ``utils/`` 的项目目录中启动，
    ``from utils import ...`` 会解析到用户的包而导致 ImportError。

    完整的保护需要处理两种情况：

    1. 当前目录以空字符串 ``""`` 或 ``"."`` 出现在 ``sys.path[0]``
       — 这是 Python 在 ``-m`` 或直接运行脚本时插入的形式。
    2. 当前目录的绝对路径被显式放入 ``sys.path``
       — 例如通过 venv 激活或 ``PYTHONPATH`` 设置。

    本函数会：
    - 删除 ``sys.path`` 中的相对形式（"" 和 "." ）
    - 将 Hermes 源码根目录移到 ``sys.path`` 最前端
    - 确保绝对路径形式的 cwd 不会覆盖 Hermes 模块

    Args:
        src_root: Hermes 源码根目录路径。默认为本模块所在目录
                 （即仓库根目录）。可通过 HERMES_PYTHON_SRC_ROOT
                 环境变量覆盖。
    """
    # 确定 Hermes 源码根目录的优先顺序：
    # 1. 传入参数
    # 2. HERMES_PYTHON_SRC_ROOT 环境变量
    # 3. 本模块所在目录（通常就是仓库根目录）
    root = src_root or os.environ.get("HERMES_PYTHON_SRC_ROOT") or os.path.dirname(
        os.path.abspath(__file__)
    )

    # 删除 sys.path 中的相对形式（空字符串 "" 和 "."）
    # 这是 Python 在启动时插入的当前工作目录，可能导致模块覆盖
    sys.path[:] = [p for p in sys.path if p not in ("", ".")]

    # 将 Hermes 源码根目录转换为绝对路径
    root_abs = os.path.abspath(root)
    # 先移除可能已存在的绝对路径，避免重复
    sys.path[:] = [p for p in sys.path if os.path.abspath(p) != root_abs]
    # 将 Hermes 源码根目录插入到 sys.path 最前端
    # 确保 Hermes 模块优先被解析
    sys.path.insert(0, root)


def activate_durable_lazy_target() -> None:
    """如果配置了持久化懒加载目录，则将其添加到 ``sys.path``。

    在不可变的 Docker 镜像中，Agent 的虚拟环境是封闭的，
    懒加载的包被重定向到数据卷上的可写目录
    （由 ``HERMES_LAZY_INSTALL_TARGET`` 环境变量指定，
    例如 ``/opt/data/lazy-packages``）。

    在之前运行中安装到该目录的包在当前运行中必须可导入，
    所以我们在第一次导入时就激活该目录，在任何后端模块
    导入其 SDK 之前。

    激活操作会将目录追加到 ``sys.path`` 的**末尾**，
    这样核心 venv 中的包始终优先（避免名称冲突）。
    具体安全原理参见 ``tools.lazy_deps`` 模块。

    注意：本函数不会抛出异常。如果目录不存在或为空，则什么也不做。
    """
    # 检查 HERMES_LAZY_INSTALL_TARGET 环境变量是否已设置且非空
    if not os.environ.get("HERMES_LAZY_INSTALL_TARGET", "").strip():
        return
    try:
        # 动态导入 lazy_deps 模块，避在 bootstrap 阶段引入过多依赖
        from tools import lazy_deps
        # 调用 lazy_deps 中的激活函数
        lazy_deps.activate_durable_lazy_target()
    except Exception:
        # Bootstrap 必须永远不要崩溃。
        # 如果激活失败，后端模块会报告其不可用，
        # 这与之前的行为一致。
        pass


# ============================================================================
# 模块导入时自动执行
# ============================================================================
# 所有入口点只需要在模块最顶部写 ``import hermes_bootstrap``
# 或 ``from hermes_bootstrap import apply_windows_utf8_bootstrap``
# 就可以触发以下导入副作用。无需显式调用。

# 1. 应用 Windows UTF-8 引导（在 Windows 上修复编码问题，在 POSIX 上无操作）
apply_windows_utf8_bootstrap()

# 2. 激活持久化懒加载目标（用于不可变 Docker 镜像）
#    让之前运行安装的包在当前运行中可导入。
#    未设置 HERMES_LAZY_INSTALL_TARGET 时为空操作。
activate_durable_lazy_target()
