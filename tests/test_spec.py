from youtube_edit_ultra.spec import parse_duration, parse_prompt


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
