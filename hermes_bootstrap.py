"""Hermes 入口点的 Windows UTF-8 引导模块。

Windows 上的 Python 存在两个长期存在的文本编码陷阱：

1. ``sys.stdout`` / ``sys.stderr`` 绑定到控制台的代码页
   （美国区域设置为 ``cp1252``），因此 ``print("café")`` 会崩溃并抛出
   ``UnicodeEncodeError: 'charmap' codec can't encode character``。

2. 通过 ``subprocess`` 生成的子进程不会自动使用 UTF-8，
   除非在它们的环境中设置了 ``PYTHONUTF8`` 和/或 ``PYTHONIOENCODING``
   —— 因此任何 Python 子进程（execute_code 沙箱、委托子进程、
   linter 子进程等）都会继承相同的 cp1252 默认值并遇到同样的
   UnicodeEncodeError。

本模块仅在 Windows 上修复这两个问题 —— POSIX 系统不受影响。
它应该在每个 Hermes 入口点的最顶部导入
（``hermes``、``hermes-agent``、``hermes-acp``、``python -m gateway.run``、
``batch_runner.py``、``cron/scheduler.py``），在任何可能进行文件 I/O
或输出到 stdout 的其他导入之前。

本模块在 Windows 上的作用：

  - 设置 ``os.environ["PYTHONUTF8"] = "1"``（PEP 540 UTF-8 模式），
    使我们生成的每个子进程都使用 UTF-8 进行 ``open()`` 和 stdio 操作。
  - 设置 ``os.environ["PYTHONIOENCODING"] = "utf-8"`` 作为双重保险 ——
    某些工具读取的是这个变量，而不是或除了 ``PYTHONUTF8`` 之外。
  - 使用 ``reconfigure()`` API（Python 3.7+）将当前进程中的
    ``sys.stdout`` / ``sys.stderr`` 重新配置为 UTF-8。
    这可以在不重启的情况下修复父进程中的 ``print("café")``。

本模块不会做的事情：

  - 它不会使用 ``-X utf8`` 重新执行 Python，因此 *当前* 进程中的
    ``open()`` 调用仍然默认使用区域编码。这些需要在调用点显式指定
    ``encoding="utf-8"``（lint 规则 ``PLW1514`` / ``PYI058``）。
    Ruff 是执行此扫描的正确工具。

本模块在 POSIX 上的作用：

  - 什么都不做。POSIX 系统在 99% 的情况下已经默认使用 UTF-8，
    我们不想触碰用户可能有意配置的 ``LANG``/``LC_*`` 行为。
    如果有人在 Linux 上遇到 C/POSIX 区域设置，他们可以自行导出
    ``PYTHONUTF8=1`` —— 我们不会覆盖。

幂等性：可以安全地多次调用。``_bootstrap_once`` 防止重复重新配置。
"""

from __future__ import (
    annotations,  # 启用向未来版本兼容的类型注解（如 list[str] 而非 typing.List[str]）
)

import os  # 操作系统接口，用于设置环境变量、文件路径操作
import sys  # 系统特定参数和函数，用于调整 Python 运行时的模块搜索路径和标准输入/输出

# 检测当前操作系统是否为 Windows（包括 win32 和 cygwin 等变种）
# 这决定了是否需要应用 Windows 特定的 UTF-8 修复
_IS_WINDOWS = sys.platform == "win32"

# 守护标志位，确保 bootstrap 只执行一次（幂等性）
# 即使多个模块导入此模块，也不会重复执行
_bootstrap_applied = False


def apply_windows_utf8_bootstrap() -> bool:
    """如果在 Windows 上运行，则应用 Windows UTF-8 引导。

    如果引导已应用（即在 Windows 上且尚未执行过）则返回 True，
    否则返回 False。返回值仅供参考 —— 调用者通常不需要它，
    但测试可能需要断言该路径已被执行。

    幂等性：首次调用之后的后续调用均为空操作。
    """
    global _bootstrap_applied

    if not _IS_WINDOWS:
        return False
    if _bootstrap_applied:
        return False

    # 1. 子进程继承这些环境变量并以 UTF-8 模式运行。
    #    我们使用 setdefault() 而非直接覆盖，以便用户可以在其环境中
    #    显式设置 PYTHONUTF8=0（或 PYTHONIOENCODING=其他值）
    #    如果他们真的想退出的话。
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # 2. 将当前进程的标准输入/输出重新配置为 UTF-8。
    #    这是必要的，因为修改 os.environ 不会追溯性地重新绑定
    #    sys.stdout —— 这些流是在解释器启动时根据控制台代码页绑定的。
    #    ``reconfigure`` 是自 Python 3.7 起 TextIOWrapper 的方法。
    #
    #    errors="replace" 意味着如果我们从 stdin *读取*到非 UTF-8 的内容
    #    （不太可能，但使用来自旧工具的管道输入时可能发生），
    #    我们会得到 U+FFFD 替换字符而不是崩溃。输出是纯 UTF-8。
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            # 不是 TextIOWrapper（在测试中可能重定向到 BytesIO，
            # 或在某些嵌入式情况下为非标准流）。
            # 静默跳过 —— 环境变量修复仍然对子进程生效，
            # 而这才是更重要的收益。
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            # 已关闭，或被替换为不可重新配置的对象。
            # 非致命错误。
            pass

    # stdin 也单独使用 errors="replace" 重新配置 ——
    # 来自旧管道的输入不应导致进程崩溃。
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
    root = (
        src_root
        or os.environ.get("HERMES_PYTHON_SRC_ROOT")
        or os.path.dirname(os.path.abspath(__file__))
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
        # 动态导入 lazy_deps 模块，避免在 bootstrap 阶段引入过多依赖
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
