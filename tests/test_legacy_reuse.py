import json
import subprocess

from youtube_edit_ultra import catalogue, produce
from youtube_edit_ultra.spec import parse_prompt


def test_analysis_is_not_usage_and_aliases_require_timeline(tmp_path):
    audio = tmp_path / 'analysis' / 'audio_analysis.json'
    catalogue.save(audio, {'tracks': [
        {'track': {'file': '/gone/one.webm', 'title': 'Used song', 'artist': 'A'}},
        {'track': {'file': '/gone/two.webm', 'title': 'Only analyzed', 'artist': 'B'}},
    ]})
    state = catalogue.scan([tmp_path], catalogue.empty())
    assert not state['used']
    catalogue.save(tmp_path / 'timeline' / 'soundtrack_v5.json', {
        'tracks': [{'source': '/gone/one.webm', 'timeline_start': 0, 'timeline_end': 10}]})
    catalogue.scan([tmp_path], state)
    assert {r['title'] for r in state['used']} == {'Used song'}
    assert state['used'][0]['identity_evidence'] == str(audio)
    catalogue.scan([tmp_path], state)
    assert len(state['used']) == 1


def test_old_analysis_exclusions_are_preserved_as_unconfirmed(tmp_path):
    state = catalogue.empty()
    evidence = str(tmp_path / 'audio_analysis.json')
    state['used'] = [{'title': 'Unconfirmed', 'family': 'unconfirmed', 'evidence': evidence}]
    catalogue.scan([tmp_path], state)
    assert not state['used']
    assert state['unconfirmed_history'][0]['title'] == 'Unconfirmed'


def test_old_searches_and_manifests_reused_without_granting_rights(tmp_path):
    catalogue.save(tmp_path / 'sources' / 'search_canelo.json', {
        'query': 'Canelo Alvarez best knockouts', 'entries': [
            {'id': 'abcdefghijk', 'title': 'Canelo Alvarez highlights', 'duration': 600}]})
    catalogue.save(tmp_path / 'sources' / 'sources.json', {'clip': {
        'url': 'https://www.youtube.com/watch?v=abcdefghijk', 'file': '/gone/clip.mp4',
        'title': 'Canelo Alvarez highlights', 'license': 'Standard YouTube License'}})
    state = catalogue.scan([tmp_path], catalogue.empty())
    assert len(state['discovered_sources']) == 1
    row = next(iter(state['discovered_sources'].values()))
    assert len(row['evidence']) == 2
    assert not state['permissions']
    assert produce.legacy_candidates(state, 'Canelo Alvarez') == [row]


def test_search_resumes_each_query_and_keeps_partial_success(tmp_path, monkeypatch):
    calls = []
    def call(argv, **kwargs):
        query = argv[-1]
        calls.append(query)
        if 'full fight' in query:
            raise subprocess.TimeoutExpired(argv, 100)
        return subprocess.CompletedProcess(argv, 0, json.dumps({'entries': [{
            'id': 'same', 'title': 'Canelo Alvarez', 'webpage_url': 'https://example.org/video'}]}), '')
    monkeypatch.setattr(produce.shutil, 'which', lambda _: 'yt-dlp')
    monkeypatch.setattr(produce.subprocess, 'run', call)
    rows = produce.discover('Canelo Alvarez', tmp_path)
    assert len(rows) == 1 and len(calls) >= 3
    report = catalogue.read(tmp_path / 'last_search_report.json')
    assert report['errors'] and report['candidate_count'] == 1
    first = len(calls)
    produce.discover('Canelo Alvarez', tmp_path)
    assert len(calls) == first + 1  # only failed query retried


def test_generic_subject_does_not_require_builtin_athlete():
    p = parse_prompt('Boxing 18s orchestral')
    assert p['athlete'] == 'Boxing' and p['duration_seconds'] == 18
    assert p['style'] == 'orchestral'


def test_loudness_gain_respects_true_peak(tmp_path, monkeypatch):
    from youtube_edit_ultra import music
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, '', 'prefix\n{"input_i":"-25", "input_tp":"-4"}\ntrailing diagnostics')
    monkeypatch.setattr(music.subprocess, 'run', run)
    levels = music.measure_loudness(tmp_path / 'x.wav')
    assert levels['gain_db'] == 1  # LUFS asks +7 dB, peak only permits +1 dB


def test_latino_analysis_list_is_identity_only(tmp_path):
    catalogue.save(tmp_path / 'audio_analysis.json', [{'filename': 'Artist - Candidate.mp3', 'duration': 120}])
    state = catalogue.scan([tmp_path], catalogue.empty())
    assert not state['used'] and not state['errors']


def test_direct_original_download_reuses_validated_cache(tmp_path, monkeypatch):
    from youtube_edit_ultra import media
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == 'curl':
            assert argv[argv.index('--proto-redir') + 1] == '=https'
            from pathlib import Path
            Path(argv[argv.index('--output') + 1]).write_bytes(b'fixture')
            return ''
        if argv[0] == 'ffmpeg':
            return 'out_time_us=20000000\nprogress=end\n'
        return json.dumps({'streams': [{'codec_type': 'audio'}], 'format': {'duration': '20'}})
    monkeypatch.setattr(media, 'run', run)
    monkeypatch.setattr(media.shutil, 'which', lambda _: 'curl')
    url = 'https://example.org/original.ogg'
    a = media.download_audio_explicit([url], tmp_path)
    b = media.download_audio_explicit([url], tmp_path)
    assert a == b and a[0].suffix == '.ogg'
    assert sum(c[0] == 'curl' for c in calls) == 1
    assert all(c[0] != 'yt-dlp' for c in calls)
