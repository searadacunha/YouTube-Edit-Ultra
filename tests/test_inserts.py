import json
import subprocess

import pytest
from PIL import Image

from youtube_edit_ultra.cli import main
from youtube_edit_ultra.media import probe


def test_image_insert_cli_keeps_geometry_frames_and_unreviewed_provenance(tmp_path):
    source, output = tmp_path / 'meme.png', tmp_path / 'insert.mp4'
    Image.new('RGB', (120, 90), (50, 180, 70)).save(source)
    original = source.read_bytes()
    assert main(['insert-image', str(source), str(output), '--duration', '1.5',
                 '--width', '160', '--height', '90']) == 0
    info = probe(output)
    assert (info['width'], info['height'], info['duration']) == (160, 90, 1.5)
    assert not info['has_audio']
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output),
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                             check=True, capture_output=True).stdout
    assert len(decoded) == 45 * 160 * 90 * 3
    # Pillarboxing preserves the original 4:3 picture inside a 16:9 output.
    assert max(decoded[:3]) < 10
    pixel = decoded[(45 * 160 + 80) * 3:(45 * 160 + 80) * 3 + 3]
    assert pixel[1] > 150
    report = json.loads(output.with_suffix('.insert.json').read_text())
    assert report['rights_verified'] is False
    assert report['visual_review_completed'] is False
    assert report['candidate_shot']['provenance'] == 'candidate_still_insert'
    assert report['candidate_shot']['kind'] == 'insert'
    assert report['candidate_shot']['audio_intent'] == 'mute'
    assert report['source_sha256'] and report['output_sha256']
    assert source.read_bytes() == original
    before = output.read_bytes()
    assert main(['insert-image', str(source), str(output), '--duration', '1.5']) == 2
    assert output.read_bytes() == before


@pytest.mark.parametrize('duration', ['nan', '-1', '0', '2', '3', '1.01'])
def test_image_insert_rejects_invalid_or_long_stills(tmp_path, duration):
    source, output = tmp_path / 'meme.png', tmp_path / 'insert.mp4'
    Image.new('RGB', (16, 16), 'green').save(source)
    assert main(['insert-image', str(source), str(output), '--duration', duration]) == 2
    assert not output.exists()


def test_image_insert_respects_disk_floor(tmp_path, monkeypatch):
    source, output = tmp_path / 'meme.png', tmp_path / 'insert.mp4'
    Image.new('RGB', (16, 16), 'green').save(source)
    monkeypatch.setenv('DISKGUARD_FLOOR_BYTES', str(10**30))
    assert main(['insert-image', str(source), str(output), '--duration', '1']) == 2
    assert not output.exists()


@pytest.mark.parametrize('kind', ['corrupt', 'animated', 'symlink'])
def test_image_insert_rejects_non_still_sources(tmp_path, kind):
    source, output = tmp_path / 'source.png', tmp_path / 'insert.mp4'
    if kind == 'corrupt':
        source.write_text('not an image')
    elif kind == 'animated':
        Image.new('RGB', (16, 16), 'green').save(
            source, format='PNG', save_all=True,
            append_images=[Image.new('RGB', (16, 16), 'blue')], duration=100, loop=0)
    else:
        target = tmp_path / 'original.png'
        Image.new('RGB', (16, 16), 'green').save(target)
        source.symlink_to(target)
    assert main(['insert-image', str(source), str(output), '--duration', '1']) == 2
    assert not output.exists()


def test_still_insert_works_between_whole_video_actions_and_passes_quality(tmp_path):
    from youtube_edit_ultra.planner import Edit
    from youtube_edit_ultra.quality import verify_output
    from youtube_edit_ultra.render import render_streamed

    source, insert, moving, music, output = [tmp_path / name for name in
        ('meme.jpg', 'insert.mp4', 'moving.mp4', 'music.wav', 'montage.mp4')]
    Image.new('RGB', (120, 90), (50, 180, 70)).save(source)
    assert main(['insert-image', str(source), str(insert), '--duration', '1.5',
                 '--width', '160', '--height', '90']) == 0
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=160x90:rate=30:duration=4', '-c:v', 'libx264',
                    str(moving)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=48000:duration=5.5', str(music)], check=True)
    edits = [Edit(str(moving), 0, 2, 0, 2, 'action', 1, 'synthetic', 1),
             Edit(str(insert), 0, 1.5, 2, 3.5, 'insert still', None, 'synthetic', 1, 'mute'),
             Edit(str(moving), 2, 4, 3.5, 5.5, 'action', 3, 'synthetic', 1)]
    render_streamed(edits, music, output, width=160, height=90, video_kbps=200)
    report = verify_output(output, 5.5, width=160, height=90, fps=30)
    assert report['full_decode'] and report['decoded_video_frames'] == 165
    assert report['quality_flags'] == []
    assert report['semantic_actions_verified'] is False
