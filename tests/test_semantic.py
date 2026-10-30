import json
import os

import pytest

from youtube_edit_ultra import semantic
from youtube_edit_ultra.events import Action
from youtube_edit_ultra.media import UltraError


def candidate(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"first")
    return Action(str(source), 0, 2, 4, "boxing", "motion", .25, "heuristic")


def valid_response(**fields):
    return dict(sports_action_visible=True, intensity=.5, event_label="exchange",
                is_crowd_or_graphics_only=False,
                complete_action_visible_in_these_frames=True, **fields)


@pytest.mark.parametrize("bad", ["unknown", None, True, float("nan"), float("inf"), -1, 2])
def test_invalid_model_intensity_is_explicit_error(tmp_path, monkeypatch, bad):
    action = candidate(tmp_path)
    response = valid_response()
    response["intensity"] = bad
    monkeypatch.setattr(semantic, "_frame_base64", lambda *args: "frame")
    monkeypatch.setattr(semantic, "_ask_ollama", lambda *args: response)
    with pytest.raises(UltraError, match="intensit|intensity"):
        semantic.enrich([action], sport="boxing", model="fake", cache_dir=tmp_path / "cache")
    assert not list((tmp_path / "cache").glob("*.json"))


@pytest.mark.parametrize("field,bad", [("sports_action_visible", "true"),
                                      ("event_label", []),
                                      ("is_crowd_or_graphics_only", None)])
def test_model_response_shape_is_validated(tmp_path, monkeypatch, field, bad):
    action = candidate(tmp_path)
    response = valid_response()
    response[field] = bad
    monkeypatch.setattr(semantic, "_frame_base64", lambda *args: "frame")
    monkeypatch.setattr(semantic, "_ask_ollama", lambda *args: response)
    with pytest.raises(UltraError, match="visuel|modèle"):
        semantic.enrich([action], sport="boxing", model="fake", cache_dir=tmp_path / "cache")


def test_semantic_cache_binds_content_sport_and_model(tmp_path, monkeypatch):
    action = candidate(tmp_path)
    source = tmp_path / "source.mp4"
    original = source.stat()
    queries = []
    monkeypatch.setattr(semantic, "_frame_base64", lambda *args: "frame")
    monkeypatch.setattr(semantic, "_ask_ollama", lambda *args: queries.append(args) or valid_response())
    def enrich(sport="boxing", model="fake"):
        return semantic.enrich([action], sport=sport, model=model, cache_dir=tmp_path / "cache")
    first, _ = enrich()
    cached, _ = enrich()
    assert first == cached and len(queries) == 1
    source.write_bytes(b"other")
    os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
    enrich()
    enrich(sport="football")
    enrich(model="other")
    assert len(queries) == 4
    assert first[0].provenance == "heuristic_vlm"


def test_graphics_stays_low_confidence_candidate(tmp_path, monkeypatch):
    action = candidate(tmp_path)
    response = valid_response()
    response["is_crowd_or_graphics_only"] = True
    monkeypatch.setattr(semantic, "_frame_base64", lambda *args: "frame")
    monkeypatch.setattr(semantic, "_ask_ollama", lambda *args: response)
    result, _ = semantic.enrich([action], sport="boxing", model="fake", cache_dir=tmp_path / "cache")
    assert result[0].confidence <= .1 and result[0].provenance == "heuristic_vlm"


def test_semantic_corrupt_cache_has_contextual_error(tmp_path, monkeypatch):
    action = candidate(tmp_path)
    monkeypatch.setattr(semantic, "_frame_base64", lambda *args: "frame")
    monkeypatch.setattr(semantic, "_ask_ollama", lambda *args: valid_response())
    semantic.enrich([action], sport="boxing", model="fake", cache_dir=tmp_path / "cache")
    cache = next((tmp_path / "cache").glob("*.json"))
    cache.write_text(json.dumps(["invalid response"]))
    with pytest.raises(UltraError, match="[Cc]ache"):
        semantic.enrich([action], sport="boxing", model="fake", cache_dir=tmp_path / "cache")
