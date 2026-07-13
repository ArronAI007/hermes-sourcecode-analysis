"""
转录提供商 —— 语音到文本的抽象接口。
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class TranscriptionProvider(abc.ABC):
    """Abstract base class for a speech-to-text backend.

    Subclasses must implement :attr:`name` and :meth:`transcribe`.
    Everything else has sane defaults — override only what your provider
    needs.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable short identifier used in ``stt.provider`` config.

        Lowercase, no spaces. Examples: ``openrouter``, ``sensaudio``,
        ``gemini``, ``deepgram``. Names that collide with a built-in STT
        provider (``local``, ``local_command``, ``groq``, ``openai``,
        ``mistral``, ``xai``) are rejected at registration time.
        """

    @property
    def display_name(self) -> str:
        """Human-readable label shown in ``hermes tools``.

        Defaults to ``name.title()``.
        """
        return self.name.title()

    def is_available(self) -> bool:
        """Return True when this provider can service calls.

        Typically checks for a required API key + that the SDK is
        importable. Default: True (providers with no external
        dependencies are always available).

        Must NOT raise — used by the picker and ``hermes setup`` for
        availability displays and should fail gracefully.
        """
        return True

    def list_models(self) -> List[Dict[str, Any]]:
        """Return model catalog entries.

        Each entry::

            {
                "id": "whisper-large-v3-turbo",  # required
                "display": "Whisper Large v3 Turbo",   # optional
                "languages": ["en", "es", "fr"],        # optional
                "max_audio_seconds": 1500,              # optional
            }

        Default: empty list (provider has a single fixed model or
        doesn't expose model selection).
        """
        return []

    def default_model(self) -> Optional[str]:
        """Return the default model id, or None if not applicable."""
        models = self.list_models()
        if models:
            return models[0].get("id")
        return None

    def get_setup_schema(self) -> Dict[str, Any]:
        """Return provider metadata for the ``hermes tools`` picker.

        Used by ``tools_config.py`` to inject this provider as a row in
        the Speech-to-Text provider list. Shape::

            {
                "name": "OpenRouter STT",              # picker label
                "badge": "paid",                       # optional short tag
                "tag": "Whisper via OpenRouter API",   # optional subtitle
                "env_vars": [                          # keys to prompt for
                    {"key": "OPENROUTER_API_KEY",
                     "prompt": "OpenRouter API key",
                     "url": "https://openrouter.ai/keys"},
                ],
            }

        Default: minimal entry derived from ``display_name`` with no
        env vars. Override to expose API key prompts and custom badges.
        """
        return {
            "name": self.display_name,
            "badge": "",
            "tag": "",
            "env_vars": [],
        }

    @abc.abstractmethod
    def transcribe(
        self,
        file_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """Transcribe the audio file at ``file_path``.

        Returns a dict with the standard envelope::

            {
                "success": True,
                "transcript": "the transcribed text",
                "provider": "<this provider's name>",
            }

        or on failure::

            {
                "success": False,
                "transcript": "",
                "error": "human-readable error message",
                "provider": "<this provider's name>",
            }

        Implementations should NOT raise — convert exceptions to the
        error envelope so the dispatcher can deliver a consistent shape
        to the gateway/CLI caller.

        Args:
            file_path: Absolute path to the audio file. The dispatcher
                has already validated existence + size before calling.
            model: Model identifier from :meth:`list_models`, or None
                to use :meth:`default_model`.
            language: Optional BCP-47 language hint (e.g. ``"en"``,
                ``"ja"``) — providers without language hints should
                ignore this argument.
            **extra: Forward-compat parameters future schema versions
                may expose. Implementations should ignore unknown keys.
        """
