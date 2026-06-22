"""Route parsed Vella intents to executable actions."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from volco.actions import chat, spotify

logger = logging.getLogger(__name__)

IntentHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def _spotify_play(intent_data: dict[str, Any]) -> dict[str, Any]:
    return await spotify.play(
        song=intent_data["song"],
        artist=intent_data.get("artist"),
    )


async def _spotify_play_playlist(intent_data: dict[str, Any]) -> dict[str, Any]:
    return await spotify.play_playlist(intent_data["playlist"])


async def _spotify_play_album(intent_data: dict[str, Any]) -> dict[str, Any]:
    return await spotify.play_album(intent_data["album"])


async def _spotify_next(_: dict[str, Any]) -> dict[str, Any]:
    return await spotify.next_track()


async def _spotify_previous(_: dict[str, Any]) -> dict[str, Any]:
    return await spotify.previous_track()


async def _spotify_resume(_: dict[str, Any]) -> dict[str, Any]:
    return await spotify.resume()


async def _conversation(intent_data: dict[str, Any]) -> dict[str, Any]:
    return await chat.handle(intent_data.get("text", ""))


class IntentRouter:
    """Expandable registry-based router for supported intents."""

    def __init__(self) -> None:
        self._handlers: dict[str, IntentHandler] = {
            "spotify_play": _spotify_play,
            "spotify_play_playlist": _spotify_play_playlist,
            "spotify_play_album": _spotify_play_album,
            "spotify_next": _spotify_next,
            "spotify_previous": _spotify_previous,
            "spotify_resume": _spotify_resume,
            "conversation": _conversation,
        }

    def register(self, intent: str, handler: IntentHandler) -> None:
        """Register or replace an intent handler."""

        self._handlers[intent] = handler

    async def route(self, intent_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the action for an intent dictionary."""

        intent = intent_data.get("intent", "conversation")
        handler = self._handlers.get(intent, self._handlers["conversation"])
        try:
            result = await handler(intent_data)
        except Exception as exc:
            logger.exception("Intent handler failed for %s.", intent)
            return {
                "status": "error",
                "message": "I could not complete that action.",
                "intent": intent,
                "action": intent_data.get("action"),
                "error": str(exc),
            }

        result.setdefault("intent", intent)
        result.setdefault("action", intent_data.get("action"))
        return result


async def route(intent_data: dict[str, Any]) -> dict[str, Any]:
    """Convenience function matching the project brief."""

    router = IntentRouter()
    return await router.route(intent_data)
