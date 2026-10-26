from pathlib import Path

import pytest

from youtube_edit_ultra.events import make_action, validate_no_overlap
from youtube_edit_ultra.planner import integrity_report, nearest_beat_distance, plan_edit
from youtube_edit_ultra.media import UltraError


def test_atomic_action_preserved():
    source = Path('/tmp/football.mp4')
    actions = [
        make_action(source, 4, 10, 20, 180, 'football', 'dribble_goal_celebration', padding=0),
        make_action(source, 41, 48, 60, 180, 'football', 'free_kick', padding=0),
        make_action(source, 71, 79, 87, 180, 'football', 'counterattack', padding=0),
    ]
    edl = plan_edit(actions, [i * .5 for i in range(200)], 54, {str(source): 180}, max_filler=18)
    assert all(edit.source_end - edit.source_start >= 16 for edit in edl if edit.provenance != 'filler')
    assert all(edit.source_start == next(a.start for a in actions if a.peak == edit.source_peak)
               for edit in edl if edit.provenance != 'filler')
    report = integrity_report(edl, actions, 54)
    assert report['cuts_inside_selected_event_windows'] == 0
    assert report['all_selected_event_windows_preserved'] is True
    assert report['semantic_completeness_guaranteed'] is False


def test_insufficient_footage_does_not_cut_action():
    source = Path('/tmp/boxing.mp4')
    actions = [make_action(source, 2, 5, 10, 20, 'boxing', 'combination', padding=0)]
    with pytest.raises(UltraError, match='insuffisante'):
        plan_edit(actions, [], 1800, {str(source): 20})


def test_merge_punch_combinations():
    source = Path('/tmp/fight.mp4')
    a = [make_action(source, 4, 8, 15, 100, 'boxing', 'jab_cross', padding=0),
         make_action(source, 13, 16, 23, 100, 'boxing', 'followup', padding=0)]
    merged = validate_no_overlap(a)
    assert len(merged) == 1
    assert merged[0].start == 4
    assert merged[0].end == 23


def test_no_beat_forced_cut():
    source = Path('/tmp/fight.mp4')
    a = [make_action(source, 0, 6, 12, 40, 'boxing', 'exchange', padding=0)]
    edl = plan_edit(a, [i * .333 for i in range(60)], 12, {str(source): 40})
    assert len(edl) == 1
    assert edl[0].source_start == 0 and edl[0].source_end == 12


def test_nearest_beat():
    assert nearest_beat_distance(2.25, [1, 2, 3]) == pytest.approx(.25)
