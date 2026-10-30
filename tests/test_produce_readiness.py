import pytest
from youtube_edit_ultra import catalogue, produce, spotify
from youtube_edit_ultra.media import UltraError


def test_configured_playlist_outage_uses_authorized_local_music(tmp_path, monkeypatch):
    config = {'playlists': {'hip-hop': 'spotify:playlist:' + 'a' * 22}}
    monkeypatch.setattr(spotify, 'client', lambda _: (_ for _ in ()).throw(UltraError('Spotify non connecté')))
    playlist, url, status = produce.resolve_playlist(tmp_path, config, 'hip-hop', None)
    assert playlist is None and url is None
    assert status['mode'] == 'local_fallback' and status['membership_verified'] is False
    assert status['requested_url'] == config['playlists']['hip-hop']


def test_explicit_playlist_outage_never_silently_substitutes(tmp_path, monkeypatch):
    monkeypatch.setattr(spotify, 'client', lambda _: (_ for _ in ()).throw(UltraError('Spotify non connecté')))
    with pytest.raises(UltraError, match='Spotify non connecté'):
        produce.resolve_playlist(tmp_path, {}, 'reggaeton', 'spotify:playlist:' + 'a' * 22)


def test_verified_playlist_remains_a_selection_constraint(tmp_path, monkeypatch):
    data = {'complete': True, 'tracks': [], 'url': 'test'}
    monkeypatch.setattr(spotify, 'client', lambda _: object())
    monkeypatch.setattr(spotify, 'playlist', lambda *args: data)
    result, url, status = produce.resolve_playlist(tmp_path, {'playlists': {'hip-hop': 'test'}}, 'hip-hop', None)
    assert result is data and url == 'test' and status['membership_verified']


def test_no_playlist_does_not_need_spotify(tmp_path, monkeypatch):
    monkeypatch.setattr(spotify, 'client', lambda _: pytest.fail('Unnecessary Spotify call'))
    assert produce.resolve_playlist(tmp_path, {}, 'hip-hop', None)[2]['mode'] == 'local'


def test_ready_report_separates_local_access_from_rights():
    state = catalogue.empty()
    row = dict(path='/cache/Canelo Alvarez fight.mp4', title='Canelo Alvarez', kind='video',
               sha256='v', available=True, duration=3600)
    state['media'] = {'v': row}
    report = produce.readiness(state, 'Canelo Alvarez', 1800, [], [])
    assert report['video']['accessible_raw_seconds'] == 3600
    assert report['video']['permitted_raw_seconds'] == 0
    assert report['permissions']['video_files_without_evidence'] == [row['path']]
    assert report['technical']['video_files_missing'] is False
    assert report['editorial']['unique_complete_actions_seconds'] is None


def test_home_directory_is_not_an_athlete_tag():
    from pathlib import Path
    row = dict(kind='video', path=str(Path.home() / 'Documents/unrelated/boxing.mp4'), title='Boxing')
    assert not produce.relevant_video(row, 'Benjamin Da Cunha')


def test_downloader_prefers_environment_module(monkeypatch):
    from youtube_edit_ultra import media
    monkeypatch.setattr(media.importlib.util, 'find_spec', lambda _: object())
    monkeypatch.setattr(media.shutil, 'which', lambda _: '/old/yt-dlp')
    assert media.downloader_command() == [media.sys.executable, '-m', 'yt_dlp']


def test_downloader_falls_back_or_explains_missing_dependency(monkeypatch):
    from youtube_edit_ultra import media
    monkeypatch.setattr(media.importlib.util, 'find_spec', lambda _: None)
    monkeypatch.setattr(media.shutil, 'which', lambda _: '/available/yt-dlp')
    assert media.downloader_command() == ['/available/yt-dlp']
    monkeypatch.setattr(media.shutil, 'which', lambda _: None)
    with pytest.raises(media.UltraError, match='download'):
        media.downloader_command()


def test_preflight_reports_both_duration_shortfalls_without_render(tmp_path, monkeypatch):
    from youtube_edit_ultra.cli import main
    state = catalogue.empty()
    video = tmp_path / 'Mike Tyson.mp4'
    audio = tmp_path / 'hip-hop.wav'
    video.write_bytes(b'preflight video metadata fixture')
    audio.write_bytes(b'preflight audio metadata fixture')
    state['media'] = {
        str(video): dict(path=str(video), title='Mike Tyson', kind='video',
                        sha256=catalogue.sha256(video), available=True, duration=63),
        str(audio): dict(path=str(audio), title='Unheard', artist='A', genre='hip-hop',
                        kind='audio', sha256=catalogue.sha256(audio), available=True, duration=120),
    }
    state['permissions'] = {row['sha256']: dict(reuse=True, evidence='test')
                            for row in state['media'].values()}
    catalogue.save(tmp_path/'state/catalogue.json', state)
    from youtube_edit_ultra import music
    monkeypatch.setattr(music, 'audio_profile', lambda path, **kwargs: {'usable_duration': 120})
    monkeypatch.setattr(catalogue, 'scan', lambda roots, state: state)
    monkeypatch.setattr(produce.subprocess, 'run', lambda *a, **k: pytest.fail('Must not render or search'))
    assert main(['produce', 'Mike Tyson 30 minutes hip-hop', '--offline', '--state-dir',
                 str(tmp_path/'state'), '--output-dir', str(tmp_path/'out')]) == 2
    report = catalogue.read(next((tmp_path/'out').glob('*/production_report.json')))
    assert any('63.000' in b for b in report['blockers'])
    assert any('120.000' in b for b in report['blockers'])


def test_canelo_nickname_matches_official_titles_without_alvarez():
    assert produce.athlete_match('Canelo vs Cotto FULL FIGHT', 'Canelo Alvarez')
    assert not produce.athlete_match('Boxing: Alvarez', 'Canelo Alvarez')


def test_long_raw_video_is_not_complete_action_coverage(tmp_path):
    import json
    path = tmp_path / 'Canelo.mp4'
    row = dict(path=str(path), sha256='same-file', duration=3600)
    assert produce.annotated_coverage([row], 'boxing') == 0
    path.with_suffix('.actions.json').write_text(json.dumps({'events': [
        dict(start=10, peak=15, end=20), dict(start=18, peak=23, end=28)]}))
    assert produce.annotated_coverage([row, row], 'boxing') == 19
