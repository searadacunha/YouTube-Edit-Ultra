import json
from pathlib import Path

from youtube_edit_ultra.events import from_json


def test_import_soccer_annotations(tmp_path):
    source = tmp_path / 'ronaldo.mp4'
    annotation = tmp_path / 'ronaldo.actions.json'
    annotation.write_text(json.dumps({'events': [
        {'start': 10, 'peak': 14, 'end': 19, 'label': 'skill-and-shot'}
    ]}))
    items = from_json(annotation, source, 50, 'football')
    assert len(items) == 1
    assert items[0].start <= 10
    assert items[0].end >= 19
    assert items[0].provenance == 'annotation'


def test_soccer_net_timestamp(tmp_path):
    src = tmp_path / 'match.mp4'
    file = tmp_path / 'match.actions.json'
    file.write_text(json.dumps({'predictions': [{'position': 60000, 'label': 'Goal', 'confidence': .9}]}))
    items = from_json(file, src, 160, 'football')
    assert items[0].peak == 60
    assert items[0].start < items[0].peak < items[0].end
    assert items[0].provenance == 'SoccerNet'
