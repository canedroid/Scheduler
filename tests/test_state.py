"""Tests for the persisted user preference state (transparency lives here)."""
from scheduler.state import StateStore


def test_opacity_round_trip(tmp_path):
    store = StateStore(tmp_path / "state.json")
    assert store.opacity == 0.75  # default
    store.opacity = 0.6
    assert store.opacity == 0.6
    reloaded = StateStore(tmp_path / "state.json")
    assert reloaded.opacity == 0.6


def test_opacity_clamped(tmp_path):
    store = StateStore(tmp_path / "state.json", defaults={"opacity": None})
    store.opacity = 5.0
    assert store.opacity == 1.0
    store.opacity = 0.05
    assert store.opacity == 0.1


def test_opacity_missing_defaults_safely(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"some_unknown": true}', encoding="utf-8")
    store = StateStore(path)
    assert store.opacity == 0.75


def test_was_fired_aliases_has_fired(tmp_path):
    store = StateStore(tmp_path / "state.json", defaults={"fired": []})
    assert not store.was_fired("abc")
    store.mark_fired("abc")
    assert store.was_fired("abc")
    assert store.has_fired("abc")


def test_tts_defaults_off(tmp_path):
    store = StateStore(tmp_path / "state.json")
    assert store.tts is False


def test_tts_round_trip(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.tts = True
    assert store.tts is True
    reloaded = StateStore(tmp_path / "state.json")
    assert reloaded.tts is True