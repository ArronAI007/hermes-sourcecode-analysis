"""
宠物状态 —— 情绪、饥饿度与成长持久化。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agent.pet.constants import PetState


def todos_all_done(todos: Iterable[Any] | None) -> bool:
    """True iff there's ≥1 todo and every one is completed/cancelled.

    The "celebrate" beat (``JUMP``) fires when a plan finishes; this mirrors
    the TUI's ``isTodoDone`` so the trigger is defined once across surfaces.
    Accepts dicts (``{"status": ...}``) or objects with a ``status`` attr.
    """
    items = list(todos or [])
    if not items:
        return False

    def _status(t: Any) -> Any:
        return t.get("status") if isinstance(t, dict) else getattr(t, "status", None)

    return all(_status(t) in ("completed", "cancelled") for t in items)


def derive_pet_state(
    *,
    busy: bool = False,
    awaiting_input: bool = False,
    error: bool = False,
    celebrate: bool = False,
    just_completed: bool = False,
    tool_running: bool = False,
    reasoning: bool = False,
) -> PetState:
    """Resolve the animation state from coarse activity signals.

    Priority (highest first) — only one row can show at a time, so the most
    salient signal wins:

    1. ``error``          → ``FAILED``  (a tool/turn just failed)
    2. ``celebrate``      → ``JUMP``    (explicit success beat, e.g. todos done)
    3. ``just_completed`` → ``WAVE``    (turn finished cleanly / greeting)
    4. ``awaiting_input`` → ``WAITING`` (blocked on the user — a clarify/approval
       prompt is open; this outranks the in-flight signals below because the turn
       is paused on *you*, even though a tool is technically mid-call)
    5. ``tool_running``   → ``RUN``     (a tool is executing)
    6. ``reasoning``      → ``REVIEW``  (model is thinking / reading)
    7. ``busy``           → ``RUN``     (turn in flight, unspecified work)
    8. otherwise          → ``IDLE``
    """
    if error:
        return PetState.FAILED
    if celebrate:
        return PetState.JUMP
    if just_completed:
        return PetState.WAVE
    if awaiting_input:
        return PetState.WAITING
    if tool_running:
        return PetState.RUN
    if reasoning:
        return PetState.REVIEW
    if busy:
        return PetState.RUN
    return PetState.IDLE
