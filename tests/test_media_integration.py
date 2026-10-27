import shutil
from pathlib import Path

import pytest

from youtube_edit_ultra.events import make_action
from youtube_edit_ultra.media import probe, run
from youtube_edit_ultra.planner import plan_edit
from youtube_edit_ultra.render import render_edits
from youtube_edit_ultra.thumbnail import create_thumbnail


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg missing')
def test_render_preserves_full_action_with_music(tmp_path):
    source = tmp_path / 'ronaldo.mp4'
    song = tmp_path / 'song.m4a'
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
         '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=30:d=6',
         '-f', 'lavfi', '-i', 'sine=frequency=220:duration=6',
         '-shortest', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)])
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
         '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6', '-c:a', 'aac', str(song)])
    a = [make_action(source, 0, 3, 6, 6, 'football', 'goal', padding=0)]
    edits = plan_edit(a, [], 6, {str(source.resolve()): 6})
    out = tmp_path / 'mix.mp4'
    result = render_edits(edits, song, out, tmp_path / 'cache', width=320, height=180, fps=30)
    assert out.is_file()
    info = probe(out)
    assert info['has_audio'] and info['has_video']
    assert info['duration'] == pytest.approx(6, abs=.45)
    assert result['resolution'] == '320x180'

    # Centre-anchored text must stay centred and inside a small thumbnail.
    import numpy as np
    from PIL import Image

    thumbnail = create_thumbnail(edits[0], "RONALDO", tmp_path / "thumbnail.jpg",
                                 width=320, height=180)
    pixels = np.asarray(Image.open(thumbnail))
    _, xs = np.where(np.all(pixels[120:] > 200, axis=2))
    assert xs.size > 0
    assert (int(xs.min()) + int(xs.max())) / 2 == pytest.approx(160, abs=8)
