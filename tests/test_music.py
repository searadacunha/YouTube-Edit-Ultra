import shutil
from pathlib import Path

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
