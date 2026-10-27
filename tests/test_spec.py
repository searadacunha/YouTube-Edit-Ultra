from pathlib import Path

import pytest

from youtube_edit_ultra.spec import Settings, parse_duration, parse_prompt


def test_duration():
    assert parse_duration("30 min") == 1800
    assert parse_duration("30mn") == 1800
    assert parse_duration("1h 15min") == 4500
    assert parse_duration("90s") == 90
    assert parse_duration("3") == 180


def test_prompt_ronaldo():
    config = parse_prompt("Fais un montage de Cristiano Ronaldo, 30 minutes, sur du hip-hop US")
    assert config["athlete"] == "Cristiano Ronaldo"
    assert config["sport"] == "football"
    assert config["style"] == "hip-hop"
    assert config["duration_seconds"] == 1800


def test_prompt_boxing():
    config = parse_prompt("Mike Tyson 20 minutes sur du rap US")
    assert config["sport"] == "boxing"
    assert config["duration_seconds"] == 1200


def test_compact_duration_and_short_name():
    assert parse_duration("1h15") == 4500
    assert parse_prompt("Ronaldo 30 min hip-hop")["athlete"] == "Ronaldo"


def test_prompt_compact_hour_minutes():
    assert parse_prompt("Cristiano Ronaldo 1h15 hip-hop")["duration_seconds"] == 4500
    assert parse_prompt("Ronaldo 1h30min rock")["duration_seconds"] == 5400
    assert parse_prompt("Mike Tyson 1h rap US")["duration_seconds"] == 3600


def test_settings_reject_invalid_render_parameters():
    config = {"athlete": "Tyson", "sport": "boxing", "style": "hip-hop",
              "duration_seconds": 1800, "output": Path("/tmp/output"),
              "library": Path("/tmp/library")}
    for bad in ({"duration_seconds": float("nan")}, {"width": 0},
                {"height": -2}, {"fps": 0}, {"fps": 30.5}):
        with pytest.raises(ValueError):
            Settings(**{**config, **bad})
