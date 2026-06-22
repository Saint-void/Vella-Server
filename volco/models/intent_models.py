"""Intent data contracts for the Vella intent router."""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field


class BaseIntent(BaseModel):
    """Base model shared by all intent classifier outputs."""

    intent: str
    action: str


class SpotifyPlayIntent(BaseIntent):
    """Intent for playing a song, optionally constrained by artist."""

    intent: Literal["spotify_play"]
    action: Literal["spotify_play"]
    song: str = Field(..., min_length=1)
    artist: str | None = None


class SpotifyPlayPlaylistIntent(BaseIntent):
    """Intent for playing a Spotify playlist."""

    intent: Literal["spotify_play_playlist"]
    action: Literal["spotify_play_playlist"]
    playlist: str = Field(..., min_length=1)


class SpotifyPlayAlbumIntent(BaseIntent):
    """Intent for playing a Spotify album."""

    intent: Literal["spotify_play_album"]
    action: Literal["spotify_play_album"]
    album: str = Field(..., min_length=1)


class SpotifyNextIntent(BaseIntent):
    """Intent for skipping to the next Spotify track."""

    intent: Literal["spotify_next"]
    action: Literal["spotify_next"]


class SpotifyPreviousIntent(BaseIntent):
    """Intent for returning to the previous Spotify track."""

    intent: Literal["spotify_previous"]
    action: Literal["spotify_previous"]


class SpotifyResumeIntent(BaseIntent):
    """Intent for resuming paused Spotify playback."""

    intent: Literal["spotify_resume"]
    action: Literal["spotify_resume"]

class SpotifyPauseIntent(BaseIntent):
    """Intent for pausing Spotify playback."""

    intent: Literal["spotify_pause"]
    action: Literal["spotify_pause"]


class ConversationIntent(BaseIntent):
    """Fallback intent for normal conversation."""

    intent: Literal["conversation"]
    action: Literal["call_llm"]
    text: str = Field(..., min_length=1)


IntentModel = Union[
    SpotifyPlayIntent,
    SpotifyPlayPlaylistIntent,
    SpotifyPlayAlbumIntent,
    SpotifyNextIntent,
    SpotifyPreviousIntent,
    SpotifyResumeIntent,
    SpotifyPauseIntent,
    ConversationIntent,
]


class IntentRequest(BaseModel):
    """Request body for text routed through the intent pipeline."""

    text: str = Field(..., min_length=1)


class IntentResponse(BaseModel):
    """Public response shape returned by the intent pipeline."""

    status: str
    message: str
    intent: str | None = None
    action: str | None = None
    device_payload: dict[str, Any] | None = None
    error: str | None = None


def validate_intent_payload(payload: dict[str, Any]) -> IntentModel:
    """Validate classifier output against the supported intent models."""

    intent = payload.get("intent")
    model_by_intent: dict[str, type[IntentModel]] = {
        "spotify_play": SpotifyPlayIntent,
        "spotify_play_playlist": SpotifyPlayPlaylistIntent,
        "spotify_play_album": SpotifyPlayAlbumIntent,
        "spotify_next": SpotifyNextIntent,
        "spotify_previous": SpotifyPreviousIntent,
        "spotify_resume": SpotifyResumeIntent,
        "spotify_pause": SpotifyPauseIntent,
        "conversation": ConversationIntent,
    }

    model = model_by_intent.get(intent)
    if model is None:
        raise ValueError(f"Unsupported intent: {intent}")

    if intent == "spotify_play":
        song = payload.get("song")
        artist = payload.get("artist")
        if isinstance(song, str):
            payload["song"] = song.strip()
        if isinstance(artist, str):
            payload["artist"] = artist.strip() or None
    elif intent == "spotify_play_playlist":
        playlist = payload.get("playlist")
        if isinstance(playlist, str):
            payload["playlist"] = playlist.strip()
    elif intent == "spotify_play_album":
        album = payload.get("album")
        if isinstance(album, str):
            payload["album"] = album.strip()

    return model(**payload)
