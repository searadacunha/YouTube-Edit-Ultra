import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from youtube_edit_ultra.editorial import analyze_structure, editorial_integrity, plan_editorial
from youtube_edit_ultra.events import Action, from_json, validate_no_overlap
from youtube_edit_ultra.media import UltraError
from youtube_edit_ultra.planner import Edit, plan_edit


def structure():
    return [dict(start=0, end=100, beats=list(range(101)), features={'wave': [.5] * 101})]


def shot(source, start, duration, label):
    return dict(source=source, safe_start=start, core_start=start, core_end=start + duration,
                safe_end=start + duration, label=label, provenance='visual_review')


def test_long_protected_combination_can_end_off_beat_horizon():
    s = dict(source='fight.mp4', safe_start=0, core_start=1, core_end=16,
             safe_end=18, label='combination and aftermath', provenance='visual_review')
    edits = plan_editorial([s], structure(), 17)
    assert len(edits) == 1
    assert edits[0].source_start <= 1 and edits[0].source_end >= 16
    assert not editorial_integrity(edits, [s], 17)['violations']


def test_atomic_planner_recovers_from_greedy_dead_end():
    actions = [Action('a', 0, 3, 6, confidence=1),
               Action('b', 0, 2, 5, confidence=.8), Action('c', 0, 2, 5, confidence=.8)]
    edits = plan_edit(actions, [], 10, {'a': 6, 'b': 5, 'c': 5})
    assert [e.duration for e in edits] == [5, 5]
    assert edits[-1].timeline_end == 10


def test_editorial_recovers_from_greedy_dead_end():
    rows = [dict(shot('a', 0, 6, 'six'), quality=20), shot('b', 0, 5, 'five-b'),
            shot('c', 0, 5, 'five-c')]
    edits = plan_editorial(rows, structure(), 10)
    assert [e.duration for e in edits] == [5, 5]
    assert not editorial_integrity(edits, rows, 10)['violations']


def test_reviewed_outro_is_reserved_and_not_repeated():
    outro = Edit('fight.mp4', 20, 22, 8, 10, 'outro', None, 'visual_review', 1)
    rows = [shot('fight.mp4', 0, 8, 'action'), shot('fight.mp4', 20, 2, 'duplicate outro')]
    edits = plan_editorial(rows, structure(), 10, outro=[outro])
    assert edits[-1] == outro
    assert not editorial_integrity(edits, rows, 10, outro=[outro])['violations']


def test_annotation_preserves_heuristic_provenance_and_checks_source(tmp_path):
    source = tmp_path / 'clip.mp4'; source.write_bytes(b'source identity')
    path = tmp_path / 'clip.actions.json'
    path.write_text(json.dumps({'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                               'events': [dict(start=1, peak=2, end=3, provenance='heuristic_motion')]}))
    rows = from_json(path, source, 10, 'boxing')
    assert rows[0].provenance == 'heuristic_motion'
    source.write_bytes(b'changed source')
    with pytest.raises(UltraError, match='SHA|source|empreinte'):
        from_json(path, source, 10, 'boxing')


def test_mixed_merge_does_not_upgrade_heuristic_edges():
    rows = [Action('a', 0, 1, 3, provenance='annotation', confidence=1),
            Action('a', 2, 3, 5, provenance='heuristic', confidence=.2)]
    merged = validate_no_overlap(rows)
    assert len(merged) == 1 and merged[0].end == 5
    assert merged[0].provenance not in {'annotation', 'visual_review'}
    assert merged[0].confidence <= .2


def test_annotation_envelope_provenance_is_not_upgraded(tmp_path):
    path = tmp_path/'events.json'
    path.write_text(json.dumps(dict(provenance='heuristic_motion',
                                    events=[dict(start=1, peak=2, end=3)])))
    action = from_json(path, tmp_path/'source.mp4', 10, 'boxing')[0]
    assert action.provenance == 'heuristic_motion'
    assert action.confidence == .2


def test_portable_structure_without_retained_repositories(tmp_path, monkeypatch):
    from youtube_edit_ultra import editorial
    song = tmp_path / 'music.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'aevalsrc=0.3*sin(2*PI*100*t)*lt(mod(t\\,0.5)\\,0.1):s=11025:d=6', str(song)], check=True)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path / 'empty-home'))
    tracks = [dict(title='fixture', timeline_start=0, timeline_end=6)]
    result = analyze_structure(song, tracks, tmp_path / 'cache')
    assert len(result) == 1 and result[0]['start'] == 0 and result[0]['end'] == 6
    assert result[0]['method'].startswith('portable')
    assert len(result[0]['beats']) == len(result[0]['features']['wave'])
    assert all(0 <= t < 6 for t in result[0]['cut_accents'])
    # A cache is evidence, not an unchecked return path.
    cached = next((tmp_path / 'cache').rglob('structure.json'))
    cached.write_text('{bad')
    with pytest.raises(UltraError, match='cache|cached|structure'):
        editorial.analyze_structure(song, tracks, tmp_path / 'cache')


def test_audio_profile_can_keep_cache_inside_job(tmp_path):
    from youtube_edit_ultra.music import audio_profile
    path = tmp_path / 'tone.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=150:d=3', str(path)], check=True)
    profile = audio_profile(path, cache_dir=tmp_path/'job-cache')
    assert profile['usable_duration'] > 2.9
    cached = next((tmp_path/'job-cache').glob('*.json'))
    cached.write_text('{bad')
    with pytest.raises(UltraError, match='cache'):
        audio_profile(path, cache_dir=tmp_path/'job-cache')
