import pytest

from volco.intent.rules import detect_intent


def test_detect_pause_intent():
    res = detect_intent("pause the music")
    assert isinstance(res, dict)
    assert res.get("intent") == "spotify_pause"


def test_detect_resume_intent():
    res = detect_intent("resume song")
    assert isinstance(res, dict)
    assert res.get("intent") == "spotify_resume"
