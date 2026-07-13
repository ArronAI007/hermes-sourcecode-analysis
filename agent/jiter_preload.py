"""
Jiter 预加载 —— JSON 解析器的早期初始化优化。
"""

from __future__ import annotations

import importlib

_JITER_PRELOADED = False
_JITER_PRELOAD_ERROR: Exception | None = None


def preload_jiter_native_extension() -> bool:
    """Import jiter's native extension early if it is available."""

    global _JITER_PRELOADED, _JITER_PRELOAD_ERROR

    if _JITER_PRELOADED:
        return True

    try:
        importlib.import_module("jiter.jiter")
        from jiter import from_json as _from_json  # noqa: F401
    except Exception as exc:
        _JITER_PRELOAD_ERROR = exc
        return False

    _JITER_PRELOADED = True
    _JITER_PRELOAD_ERROR = None
    return True


preload_jiter_native_extension()
