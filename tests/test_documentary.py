import json
import subprocess

import numpy as np
import pytest

from youtube_edit_ultra import documentary as doc


def test_script_text_wins_over_asr_and_unmatched_words_are_interpolated():
    asr = [dict(w='Canelo', start=0.0, end=0.5), dict(w='a', start=0.5, end=0.6),
           dict(w='36', start=0.6, end=1.0), dict(w='ans.', start=1.0, end=1.3)]
    toks = doc.timed_tokens('Canelo a trente-six 36 ans.', asr, 2.0)
    assert [t[0] for t in toks] == ['Canelo', 'a', 'trente-six', '36', 'ans.']
    assert toks[0][1:] == (0.0, 0.5) and toks[3][1:] == (0.6, 1.0)
    assert 0.6 <= toks[2][1] <= toks[2][2] <= 0.6  # squeezed between matched neighbours


def test_cues_break_on_sentences_never_overlap_and_stay_two_lines():
    words = ('Tout le monde connaît Canelo. Les titres, les millions, les grandes soirées de '
             'Las Vegas et une très longue phrase qui doit forcément être coupée.').split()
    toks = [(w, i * .3, i * .3 + .25) for i, w in enumerate(words)]
    cues = doc.make_cues(toks, offset=10)
    assert cues[0]['lines'] == [['Tout', 'le', 'monde', 'connaît', 'Canelo.']]
    assert all(len(c['lines']) <= 2 for c in cues)
    assert all(a['end'] <= b['start'] for a, b in zip(cues, cues[1:]))
    assert cues[0]['start'] == 10


def _spec(tmp_path, visuals, facts=None):
    (tmp_path / 'facts.json').write_text(json.dumps(facts or [dict(id='f1', status='verified', claim_fr='x', value='1', sources=[])]))
    return dict(_out=str(tmp_path), facts=['facts.json'], video=dict(width=320, height=180, fps=30),
                sources=dict(S=dict(url='u', rights=dict(status='official_upload_fair_use_claim'), credit='C',
                                    fight='A vs B', fight_date='2025-01-01')),
                chapters=[dict(id='c', blocks=[dict(id='b1', text='Un texte.', visuals=visuals,
                                                     claims=[dict(cat='verified_fact', facts=['f1'])])])])


def test_validation_refuses_self_assigned_human_review_and_unverified_facts(tmp_path):
    clip = dict(type='clip', src='S', t=[0, 1], action='jab', confidence=.8, provenance='visual_review')
    errors = doc.validate(_spec(tmp_path, [clip], [dict(id='f1', status='unverified')]))
    assert any('provenance' in e for e in errors) and any('not verified' in e for e in errors)
    clip['provenance'] = 'agent_frame_review'
    assert doc.validate(_spec(tmp_path, [clip])) == []


def test_plan_keeps_clip_windows_and_stretches_only_flexible_visuals(tmp_path):
    spec = _spec(tmp_path, [dict(type='clip', src='S', t=[0, 1], speed=.5), dict(type='card', kind='title', lines=['X'])])
    plan = doc.build_plan(spec, {'b1': 4.0})
    clip, card = plan['segments']
    assert clip['frames'] == 60  # 1 s of source at half speed, never shortened
    assert card["frames"] == round((0.45 + 4.0 + .8 - 2.0) * 30)
    with pytest.raises(doc.UltraError):
        doc.build_plan(_spec(tmp_path, [dict(type='clip', src='S', t=[0, 1])]), {'b1': 4.0})


def test_real_small_render_with_cards_slow_motion_freeze_split_and_subtitles(tmp_path):
    (tmp_path / 'sources/proxies').mkdir(parents=True)
    src = tmp_path / 'sources/proxies/S.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=30:d=3', '-f', 'lavfi',
                    '-i', 'sine=f=220:d=3', '-shortest', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(src)], check=True)
    vo = tmp_path / 'vo.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=180:d=1.5', str(vo)], check=True)
    part = dict(src='S', t=[0.5, 1.5], label='A B', action='a', confidence=.5, provenance='agent_frame_review')
    spec = _spec(tmp_path, [dict(type='card', kind='stat', value='29-0-1', caption='x', duration=.5),
                            dict(part, type='clip', speed=.5, overlays=[dict(type='arrow', **{'from': [.2, .2], 'to': [.6, .6]}, at=.1)]),
                            dict(type='freeze', src='S', at=1.0, duration=.4, action='a', confidence=.5, provenance='agent_frame_review'),
                            dict(type='split', left=part, right=dict(part, t=[1.5, 2.5]))])
    plan = doc.build_plan(spec, {'b1': 1.5})
    cues = doc.make_cues(doc.timed_tokens('Un texte.', [], 1.5), plan['blocks'][0]['vo_start'])
    audio = tmp_path / 'mix.flac'
    stats = doc.mix(spec, plan, {'b1': str(vo)}, audio, proxy=True)
    out = doc.render(spec, plan, cues, audio, tmp_path / 'out.mp4', proxy=True)
    assert out['frames'] == plan['frames'] == 15 + 60 + 12 + 30
    info = doc.probe(tmp_path / 'out.mp4')
    assert info['width'] == 320 and abs(info['duration'] - plan['duration']) < .1
    assert stats['voice_to_bed_db'] is None or np.isfinite(stats['voice_to_bed_db'])


def test_slow_motion_keeps_moving_until_the_last_frame(tmp_path):
    src = tmp_path / 's.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=30:d=3', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(src)], check=True)
    frames = list(doc.decode(src, 0.5, 60, 160, 90, 30, speed=0.5))  # 1 s of source over 2 s
    assert len(frames) == 60
    assert not np.array_equal(frames[-1], frames[-5])  # the old output-side -t froze the second half
    with pytest.raises(doc.UltraError):
        list(doc.decode(src, 2.5, 60, 160, 90, 30))  # beyond the source: refuse, never pad silently


def test_youtube_metadata_comes_from_the_spec_not_from_a_previous_film(tmp_path):
    spec = _spec(tmp_path, [dict(type='card', kind='title', lines=['X'])])
    spec['sources']['S'].update(channel='C', title='T')
    spec.update(title='Titre', description='Ma description.', voice=dict(credit='Voix off : ma voix, avec accord.'))
    spec['chapters'][0]['title'] = 'Premier chapitre'
    doc.write_reports(spec, doc.build_plan(spec, {'b1': 2.0}), [])
    meta = (tmp_path / 'youtube_metadata.md').read_text()
    assert 'Ma description.' in meta and '0:00 Premier chapitre' in meta and 'ma voix, avec accord' in meta
    assert 'Canelo' not in meta and 'aucune voix réelle' not in meta
