"""
数字宠物 —— 交互式桌面伴侣系统。
"""

from agent.pet.constants import (
    DEFAULT_SCALE,
    FRAME_H,
    FRAME_W,
    FRAMES_PER_STATE,
    LOOP_MS,
    STATE_ROWS,
    PetState,
)
from agent.pet.state import derive_pet_state

__all__ = [
    "DEFAULT_SCALE",
    "FRAME_H",
    "FRAME_W",
    "FRAMES_PER_STATE",
    "LOOP_MS",
    "STATE_ROWS",
    "PetState",
    "derive_pet_state",
]
