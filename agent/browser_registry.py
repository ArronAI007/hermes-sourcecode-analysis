"""
浏览器注册表 —— 浏览器实例的发现与管理。
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from agent.browser_provider import BrowserProvider

logger = logging.getLogger(__name__)


_providers: Dict[str, BrowserProvider] = {}
_lock = threading.Lock()


def register_provider(provider: BrowserProvider) -> None:
    """Register a cloud browser provider.

    Re-registration (same ``name``) overwrites the previous entry and logs
    a debug message — makes hot-reload scenarios (tests, dev loops) behave
    predictably.
    """
    if not isinstance(provider, BrowserProvider):
        raise TypeError(
            f"register_provider() expects a BrowserProvider instance, "
            f"got {type(provider).__name__}"
        )
    name = provider.name
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Browser provider .name must be a non-empty string")
    with _lock:
        existing = _providers.get(name)
        _providers[name] = provider
    if existing is not None:
        logger.debug(
            "Browser provider '%s' re-registered (was %r)",
            name, type(existing).__name__,
        )
    else:
        logger.debug(
            "Registered browser provider '%s' (%s)",
            name, type(provider).__name__,
        )


def list_providers() -> List[BrowserProvider]:
    """Return all registered providers, sorted by name."""
    with _lock:
        items = list(_providers.values())
    return sorted(items, key=lambda p: p.name)


def get_provider(name: str) -> Optional[BrowserProvider]:
    """Return the provider registered under *name*, or None."""
    if not isinstance(name, str):
        return None
    with _lock:
        return _providers.get(name.strip())


# ---------------------------------------------------------------------------
# Active-provider resolution
# ---------------------------------------------------------------------------


# Legacy auto-detect order — used when no ``browser.cloud_provider`` is set.
# Matches the pre-migration walk in :func:`tools.browser_tool._get_cloud_provider`.
# Firecrawl is intentionally absent so users with ``FIRECRAWL_API_KEY`` set
# for web-extract don't get silently routed to a paid cloud browser. See
# :func:`_resolve` for the full rationale.
_LEGACY_PREFERENCE = (
    "browser-use",
    "browserbase",
)


def _resolve(configured: Optional[str]) -> Optional[BrowserProvider]:
    """Resolve the active browser provider.

    Resolution rules (in order):

    1. **Explicit "local".** Returns None — the dispatcher disables cloud
       mode entirely. Mirrors legacy short-circuit in
       :func:`tools.browser_tool._get_cloud_provider`.
    2. **Explicit config wins, ignoring availability.** If ``configured``
       names a registered provider, return it even if its
       :meth:`is_available` returns False — the dispatcher will surface a
       precise "X_API_KEY is not set" error instead of silently routing
       somewhere else.
    3. **Legacy preference walk, filtered by availability.** Walk
       :data:`_LEGACY_PREFERENCE` (``browser-use`` → ``browserbase``) looking
       for a provider whose ``is_available()`` is True.

    There is intentionally NO "single-eligible shortcut" rule here (unlike
    :func:`agent.web_search_registry._resolve`). Pre-migration, the
    auto-detect branch in ``tools.browser_tool._get_cloud_provider`` only
    considered Browser Use and Browserbase; Firecrawl was reachable only
    via an explicit ``browser.cloud_provider: firecrawl`` config key.
    Preserving that gate matters because Firecrawl shares its API key with
    the *web* extract plugin (``plugins/web/firecrawl/``), so users who set
    ``FIRECRAWL_API_KEY`` for web extract must NOT get silently routed to a
    paid cloud browser on a fresh install. Third-party browser-provider
    plugins added under ``~/.hermes/plugins/browser/<vendor>/`` are subject
    to the same gate — they must be explicitly configured to take effect.

    Returns None when no provider is configured AND no available provider
    matches the legacy preference; the dispatcher then falls back to local
    browser mode.
    """
    with _lock:
        snapshot = dict(_providers)

    def _is_available_safe(p: BrowserProvider) -> bool:
        """Wrap ``is_available()`` so a buggy provider doesn't kill resolution."""
        try:
            return bool(p.is_available())
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Browser provider %s.is_available() raised %s — treating as unavailable",
                p.name, exc, exc_info=True,
            )
            return False

    # 1. Explicit "local" short-circuit.
    if configured == "local":
        return None

    # 2. Explicit config wins — return regardless of is_available() so the
    #    user gets a precise downstream error message rather than a silent
    #    backend switch. Matches _get_cloud_provider() in browser_tool.py.
    if configured:
        provider = snapshot.get(configured)
        if provider is not None:
            return provider
        logger.debug(
            "browser cloud_provider '%s' configured but not registered; "
            "falling back to auto-detect",
            configured,
        )

    # 3. Legacy preference walk — only providers in _LEGACY_PREFERENCE are
    #    auto-eligible. Filtered by availability so we don't surface a
    #    provider the user has no credentials for. See docstring for why
    #    we do NOT fall back to "any single-eligible registered provider".
    for legacy in _LEGACY_PREFERENCE:
        provider = snapshot.get(legacy)
        if provider is not None and _is_available_safe(provider):
            return provider

    return None


def _reset_for_tests() -> None:
    """Clear the registry. **Test-only.**"""
    with _lock:
        _providers.clear()
