"""Fast deterministic intent rules for common Volco voice commands."""

from __future__ import annotations

import re
from typing import Any


_PLAY_COMMAND = re.compile(
    r"\b(?:play|put on|start playing|start|queue)\b\s+(?P<query>.+)",
    flags=re.IGNORECASE,
)
_NEXT_COMMAND = re.compile(
    r"\b(?:next|skip)(?:\s+(?:song|track|music))?\b",
    flags=re.IGNORECASE,
)
_PREVIOUS_COMMAND = re.compile(
    r"\b(?:previous|last|back)(?:\s+(?:song|track|music))?\b",
    flags=re.IGNORECASE,
)
_RESUME_COMMAND = re.compile(
    r"\b(?:resume|continue|unpause)(?:\s+(?:song|track|music|playback))?\b",
    flags=re.IGNORECASE,
)
_PAUSE_COMMAND = re.compile(
    r"\b(?:pause|stop|hold|mute|hang on|wait a sec|wait)\b(?:\s+(?:music|song|track|playback|audio))?",
    flags=re.IGNORECASE,
)
_VAGUE_PLAY_QUERIES = {
    "a song",
    "music",
    "my music",
    "song",
    "some music",
    "the music",
    "the song",
}


def detect_intent(text: str) -> dict[str, Any] | None:
    """Return a high-confidence intent without calling the LLM."""

    clean_text = _clean_text(text)
    if not clean_text:
        return None

    if _NEXT_COMMAND.search(clean_text):
        return {"intent": "spotify_next", "action": "spotify_next"}

    if _PREVIOUS_COMMAND.search(clean_text):
        return {"intent": "spotify_previous", "action": "spotify_previous"}

    if _RESUME_COMMAND.search(clean_text):
        return {"intent": "spotify_resume", "action": "spotify_resume"}
    if _PAUSE_COMMAND.search(clean_text):
        return {"intent": "spotify_pause", "action": "spotify_pause"}
    match = _PLAY_COMMAND.search(clean_text)
    if not match:
        return None

    query = _clean_query(match.group("query"))
    if not query:
        return None

    if _is_vague_resume_query(query):
        return {"intent": "spotify_resume", "action": "spotify_resume"}

    playlist = _collection_query(query, "playlist")
    if playlist:
        return {
            "intent": "spotify_play_playlist",
            "action": "spotify_play_playlist",
            "playlist": playlist,
        }

    album = _collection_query(query, "album")
    if album:
        return {
            "intent": "spotify_play_album",
            "action": "spotify_play_album",
            "album": album,
        }

    song, artist = _split_song_artist(query)
    if not song:
        return None

    return {
        "intent": "spotify_play",
        "action": "spotify_play",
        "song": song,
        "artist": artist,
    }


def _clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^(?:okay|ok|alright|please|hey vella|vella)[,\s]+", "", text, flags=re.IGNORECASE)
    return text.strip()


def _clean_query(query: str) -> str:
    query = query.strip()
    query = re.sub(r"\b(?:please|for me|right now|now)\b", "", query, flags=re.IGNORECASE)
    query = re.sub(r"^(?:something like|like)\s+", "", query, flags=re.IGNORECASE)
    query = query.strip(" .,!?:;\"'")
    return re.sub(r"\s+", " ", query).strip()


def _is_vague_resume_query(query: str) -> bool:
    normalized = _clean_query(query).lower()
    return normalized in _VAGUE_PLAY_QUERIES


def _collection_query(query: str, media_type: str) -> str | None:
    trailing_match = re.match(
        rf"(?P<name>.+?)\s+{media_type}\b.*$",
        query,
        flags=re.IGNORECASE,
    )
    if trailing_match:
        return _clean_collection_name(trailing_match.group("name"))

    leading_match = re.match(
        rf"{media_type}\s+(?:called|named\s+)?(?P<name>.+)$",
        query,
        flags=re.IGNORECASE,
    )
    if leading_match:
        return _clean_collection_name(leading_match.group("name"))

    return None


def _clean_collection_name(query: str) -> str | None:
    query = _clean_query(query)
    query = re.sub(r"^(?:my|the|a|an)\s+", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+(?:playlist|album)$", "", query, flags=re.IGNORECASE)
    query = _clean_query(query)
    return query or None


def _split_song_artist(query: str) -> tuple[str, str | None]:
    by_match = re.match(r"(?P<song>.+?)\s+by\s+(?P<artist>.+)$", query, flags=re.IGNORECASE)
    if by_match:
        return _clean_query(by_match.group("song")), _clean_query(by_match.group("artist")) or None

    if "," in query:
        artist, song = query.split(",", 1)
        clean_song = _clean_query(song)
        clean_artist = _clean_query(artist)
        if clean_song and clean_artist:
            return clean_song, clean_artist

    return _clean_query(query), None
