import shutil

import pytest

from youtube_edit_ultra.media import run, probe, UltraError
from youtube_edit_ultra.music import extract_beats, build_soundtrack, soundtrack_playlist


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg missing')
def test_music_duration_and_fast_beat_map(tmp_path):
    a = tmp_path / 'trackA.m4a'
    b = tmp_path / 'trackB.m4a'
    for f, freq in ((a, 330), (b, 440)):
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
             '-f', 'lavfi', '-i', f'sine=frequency={freq}:duration=4:sample_rate=11025',
             '-c:a', 'aac', str(f)])
    out = tmp_path / 'music.m4a'
    chosen = build_soundtrack([a, b], 6, out)
    assert len(chosen) == 2
    assert probe(out)['duration'] == pytest.approx(6, abs=.25)
    beats = extract_beats(out, engine='fast')
    assert isinstance(beats, list)
    assert all(0 <= x <= 6.1 for x in beats)


def test_no_music_replay_without_opt_in(tmp_path):
    # The file has to exist for preflight.
    with pytest.raises(UltraError):
        soundtrack_playlist([tmp_path / 'missing.mp3'], 1800)


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg missing')
def test_silent_tail_does_not_count_as_soundtrack_coverage(tmp_path):
    from youtube_edit_ultra.music import audio_profile
    track = tmp_path / 'silent-tail.wav'
    run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
         'sine=frequency=440:duration=4', '-af', 'adelay=500|500,apad=pad_dur=5', str(track)])
    profile = audio_profile(track)
    assert profile['source_start'] == pytest.approx(.5, abs=.05)
    assert profile['source_end'] == pytest.approx(4.5, abs=.05)
    assert profile['usable_duration'] < 4.1
    with pytest.raises(UltraError, match='Playlist trop courte'):
        soundtrack_playlist([track], 6)


def test_automatic_playlist_progression_is_cached_and_not_claimed_harmonic(tmp_path, monkeypatch):
    from youtube_edit_ultra import music
    rows = []
    for name in ('busy', 'quiet'):
        path = tmp_path / (name + '.wav');path.write_bytes(name.encode())
        rows.append(dict(path=str(path)))
    calls = []
    def beats(path):
        calls.append(path)
        return list(range(8 if path.stem == 'busy' else 2))
    monkeypatch.setattr(music, 'extract_beats', beats)
    monkeypatch.setattr(music, 'audio_profile', lambda *a, **k: {'usable_duration': 10})
    ordered, report = music.arrange_playlist(rows, cache_dir=tmp_path / 'cache')
    assert ordered == rows[::-1]
    assert report['tempo_is_estimate'] and not report['harmonic_compatibility_verified']
    assert music.arrange_playlist(rows, cache_dir=tmp_path / 'cache')[0] == ordered
    assert len(calls) == 2
