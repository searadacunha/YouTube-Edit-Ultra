import json
from youtube_edit_ultra import music_sources as m


def test_mixkit_exact_genre_and_licence():
    row = {'@type':'MusicRecording', 'name':'New', 'byArtist':'Artist', 'url':'https://assets.mixkit.co/music/1.mp3', 'license':'https://mixkit.co/license/#musicFree', 'isAccessibleForFree':True, 'genre':'Reggaeton'}
    def page(r):return '<script type="application/ld+json">'+json.dumps({'@graph':[{'itemListElement':[r]}]})+'</script>'
    assert m.mixkit_rows(page(row),'reggaeton')[0]['artist']=='Artist'
    assert not m.mixkit_rows(page(dict(row,license='unknown')),'reggaeton')
    assert not m.mixkit_rows(page(row),'funk-brasileiro')


def test_fsm_track_licence_after_separator_not_related_track():
    page="""<title>Fiesta by Mike | Music</title><a href='/music/mike.mp3'>download</a><hr/>
    <p class='trackCategories'><a>Reggaeton</a></p><a href='https://creativecommons.org/licenses/by/3.0/'>licence</a>
    <div class='spotifyPlaylistsCont'>other tracks</div>"""
    assert m.fsm_row(page,'https://www.free-stock-music.com/mike.html','reggaeton')['title']=='Fiesta'
    assert m.fsm_row(page.replace('by/3.0','by-nc/3.0'),'https://www.free-stock-music.com/mike.html','reggaeton') is None
    assert m.fsm_row(page,'https://www.free-stock-music.com/mike.html','rnb') is None


def test_decade_is_not_faked_by_stock_catalogue(tmp_path):
    tracks,errors=m.discover('rnb-2000s',tmp_path)
    assert not tracks and 'release years' in errors[0]


def test_failed_track_does_not_stop_next_source(tmp_path,monkeypatch):
    from youtube_edit_ultra import catalogue as cat
    rows=[dict(title=n,artist='A',url='https://assets.mixkit.co/music/'+n+'.mp3',license='licence',evidence='page') for n in ['bad','good']]
    monkeypatch.setattr(m,'discover',lambda *a:(rows,[]))
    attempts=[]
    def run(cmd,**kwargs):
        from types import SimpleNamespace
        attempts.append(cmd[-1]);return SimpleNamespace(returncode=1,stderr='download unavailable')
    monkeypatch.setattr(m.subprocess,'run',run)
    r=m.acquire('reggaeton',1800,cat.empty(),tmp_path)
    assert len(attempts)==2 and all(x['status']=='FAILED' for x in r['attempts'])
    assert len(r['errors']) == 2 and all('download unavailable' in error for error in r['errors'])


def test_commercial_mode_does_not_promote_catalogue_declarations(tmp_path, monkeypatch):
    from youtube_edit_ultra import catalogue as cat
    rows = [dict(title='New', artist='A', url='https://assets.mixkit.co/music/new.mp3',
                 license='https://mixkit.co/license/#musicFree', evidence='publisher page')]
    monkeypatch.setattr(m, 'discover', lambda *a: (rows, []))
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError('Unverified commercial source must not download')))
    report = m.acquire('reggaeton', 30, cat.empty(), tmp_path, mode='commercial')
    assert report['attempts'][0]['status'] == 'SKIPPED_COMMERCIAL_RIGHTS_UNVERIFIED'
    assert report['errors']
