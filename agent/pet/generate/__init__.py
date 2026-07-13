"""
宠物生成 —— 程序化的外观与性格创建。
"""

from __future__ import annotations

from agent.pet.generate.imagegen import GenerationError
from agent.pet.generate.orchestrate import (
    HatchResult,
    generate_base_drafts,
    hatch_pet,
)

__all__ = [
    "GenerationError",
    "HatchResult",
    "generate_base_drafts",
    "hatch_pet",
]
