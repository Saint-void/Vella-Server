import asyncio

import volco.actions.spotify as spotify


def test_spotify_pause_action():
    res = asyncio.run(spotify.pause())
    assert isinstance(res, dict)
    assert res.get("device_payload", {}).get("action") == "spotify_pause"
