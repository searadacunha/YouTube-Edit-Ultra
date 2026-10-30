import pytest

from youtube_edit_ultra.spec import parse_prompt, parse_request


@pytest.mark.parametrize('prompt,athlete,style,seconds', [
    ('Terence Crawford — R&B 2000s — 30 minutes', 'Terence Crawford', 'rnb-2000s', 1800),
    ('Canelo Álvarez — Reggaeton — 30 minutes', 'Canelo Alvarez', 'reggaeton', 1800),
    ('Naoya Inoue — Japanese hip-hop — 20 minutes', 'Naoya Inoue', 'japanese-hip-hop', 1200),
    ('Gervonta Davis, soul 1990s, 90s', 'Gervonta Davis', 'soul-1990s', 90),
    ('Canelo Alvarez, reggaeton, 6 seconds', 'Canelo Alvarez', 'reggaeton', 6),
])
def test_three_field_request(prompt, athlete, style, seconds):
    request = parse_request(prompt)
    assert (request['athlete'], request['style'], request['duration_seconds']) == (athlete, style, seconds)
    assert request['sport'] == 'boxing'


@pytest.mark.parametrize('prompt', ['Crawford', 'Crawford 30m', 'R&B 30m', 'Crawford rnb', 'Crawford rnb 0s'])
def test_one_shot_rejects_missing_or_invalid_core_information(prompt):
    with pytest.raises(ValueError):
        parse_request(prompt)


def test_legacy_prompt_defaults_remain_compatible():
    assert parse_prompt('Mike Tyson')['duration_seconds'] == 300


def test_negative_duration_never_becomes_positive():
    with pytest.raises(ValueError):
        parse_request('Crawford, rnb, -3s')
