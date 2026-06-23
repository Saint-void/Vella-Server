"""Mock Spotify actions for the first Vella intent-routing version."""

from __future__ import annotations

from typing import Any


def _track_query(song: str, artist: str | None = None) -> str:
    return f"{song} by {artist}" if artist else song


async def play(song: str, artist: str | None = None) -> dict[str, Any]:
    """Mock playing a Spotify track."""

    query = _track_query(song, artist)
    return {
        "status": "success",
        "message": f"Playing {query}",
        "device_payload": {
            "action": "spotify_play_track",
            "query": query,
            "continue_session": False,
            "end_session": True,
        },
    }


async def play_playlist(playlist: str) -> dict[str, Any]:
    """Play a Spotify playlist by search query."""

    return {
        "status": "success",
        "message": f"Playing {playlist} playlist",
        "device_payload": {
            "action": "spotify_play_playlist",
            "query": playlist,
            "continue_session": False,
            "end_session": True,
        },
    }


async def play_album(album: str) -> dict[str, Any]:
    """Play a Spotify album by search query."""

    return {
        "status": "success",
        "message": f"Playing {album} album",
        "device_payload": {
            "action": "spotify_play_album",
            "query": album,
            "continue_session": False,
            "end_session": True,
        },
    }


async def next_track() -> dict[str, Any]:
    """Mock skipping to the next Spotify track."""

    return {
        "status": "success",
        "message": "Skipping to the next track",
        "device_payload": {
            "action": "spotify_next",
            "continue_session": False,
            "end_session": True,
        },
    }


async def previous_track() -> dict[str, Any]:
    """Mock returning to the previous Spotify track."""

    return {
        "status": "success",
        "message": "Going back to the previous track",
        "device_payload": {
            "action": "spotify_previous",
            "continue_session": False,
            "end_session": True,
        },
    }


async def resume() -> dict[str, Any]:
    """Resume paused Spotify playback."""

    return {
        "status": "success",
        "message": "Resuming Spotify",
        "device_payload": {
            "action": "spotify_resume",
            "continue_session": False,
            "end_session": True,
        },
    }

async def pause() -> dict[str, Any]:
    """Pause Spotify playback."""

    return {                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
        "status": "success",
        "message": "Pausing Spotify",
        "device_payload": {
            "action": "spotify_pause",
            "continue_session": False,
            "end_session": True,
        },
    }