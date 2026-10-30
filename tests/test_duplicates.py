import json
import subprocess

import pytest

from youtube_edit_ultra import duplicates
from youtube_edit_ultra.media import UltraError
from youtube_edit_ultra.planner import Edit


def video(path, pattern='testsrc2', crf='18'):
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    f'{pattern}=size=160x90:rate=30:duration=5', '-c:v', 'libx264',
                    '-crf', crf, '-pix_fmt', 'yuv420p', str(path)], check=True)
    return path


def shot(path, label):
    return dict(source=str(path), safe_start=0, core_start=0, core_end=5,
                safe_end=5, label=label, provenance='visual_review')


def test_same_sequence_different_encoding_is_rejected_before_planning(tmp_path):
    a = video(tmp_path/'a.mp4', crf='16'); b = video(tmp_path/'b.mp4', crf='28')
    c = video(tmp_path/'c.mp4', pattern='testsrc', crf='22')
    rows = [shot(a, 'first'), shot(b, 'copy'), shot(c, 'other')]
    retained, report = duplicates.deduplicate_shots(rows, tmp_path/'cache')
    assert [s['label'] for s in retained] == ['first', 'other']
    assert report['retained'] == [0, 2]
    assert report['rejected'][0]['index'] == 1
    assert report['complete'] and not report['semantic_duplicates_verified']
    assert len(report['source_evidence']) == 3


def test_final_scan_detects_cross_shot_repeated_sequence(tmp_path):
    source = video(tmp_path/'a.mp4')
    full = tmp_path/'twice.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-stream_loop', '1', '-i', str(source),
                    '-c', 'copy', str(full)], check=True)
    edits = [Edit(str(source), 0, 5, i*5, (i+1)*5, str(i), 2, 'annotation', 1)
             for i in range(2)]
    report = duplicates.check_video_duplicates(full, edits, tmp_path/'cache')
    assert report['candidates'] and report['complete']
    assert report['candidates'][0]['clip_a'] == 0 and report['candidates'][0]['clip_b'] == 1


def test_scan_bound_is_reported_not_a_false_negative(tmp_path):
    source = video(tmp_path/'a.mp4')
    edits = [dict(timeline_start=i, timeline_end=i+1) for i in range(5)]
    report = duplicates.check_video_duplicates(source, edits, tmp_path/'cache', max_comparisons=0)
    assert not report['complete'] and report['truncated']


def test_corrupt_hash_cache_is_explicit(tmp_path):
    source = video(tmp_path/'a.mp4')
    duplicates.sample_hashes(source, tmp_path/'cache')
    path = next((tmp_path/'cache').glob('*.json'));path.write_text(json.dumps({'hashes': ['not a hash']}))
    with pytest.raises(UltraError, match='cache'):
        duplicates.sample_hashes(source, tmp_path/'cache')


@pytest.mark.parametrize('reverse', [False, True])
def test_short_duplicate_never_discards_complete_longer_action(tmp_path, monkeypatch, reverse):
    import random
    rng = random.Random(81)
    hashes = [rng.getrandbits(63) for _ in range(20)]
    long = dict(shot(tmp_path/'long.mp4', 'whole combination'), core_end=10, safe_end=10)
    short = dict(shot(tmp_path/'short.mp4', 'cropped combination'), core_end=4, safe_end=4)
    samples = {
        long['source']: dict(hashes=hashes, duration=10, sha256='a'*64),
        short['source']: dict(hashes=hashes[:8], duration=4, sha256='b'*64),
    }
    monkeypatch.setattr(duplicates, 'sample_hashes', lambda path, *a, **kw: samples[str(path)])
    rows = [short, long] if not reverse else [long, short]
    retained, report = duplicates.deduplicate_shots(rows, tmp_path/'cache')
    assert [s['label'] for s in retained] == ['whole combination']
    assert report['complete']


def test_shared_run_with_different_ending_is_not_discarded(tmp_path, monkeypatch):
    import random
    rng = random.Random(491)
    common = [rng.getrandbits(63) for _ in range(17)]
    rows = [dict(shot(tmp_path/f'{i}.mp4', str(i)), core_end=10, safe_end=10) for i in range(2)]
    samples = {row['source']: dict(hashes=common+[rng.getrandbits(63) for _ in range(3)],
                                  duration=10, sha256=str(i)*64) for i, row in enumerate(rows)}
    monkeypatch.setattr(duplicates, 'sample_hashes', lambda path, *a, **kw: samples[str(path)])
    retained, report = duplicates.deduplicate_shots(rows, tmp_path/'cache')
    assert retained == rows and not report['rejected']
