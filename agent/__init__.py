"""
Agent 内部模块 —— 从 run_agent.py 中提取的独立模块。

这些模块包含纯工具函数和自包含的类，之前都嵌入在 3600+ 行的 run_agent.py 中。
将它们提取出来可以让 run_agent.py 专注于 AIAgent 协调器类本身。
"""

# 预加载 jiter 库以优化性能（ noqa: F401 表示忽略未使用导入的警告）
from . import jiter_preload as _jiter_preload  # noqa: F401
