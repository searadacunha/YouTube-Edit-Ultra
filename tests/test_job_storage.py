import pytest

from youtube_edit_ultra import storage
from youtube_edit_ultra.media import UltraError


def test_existing_disk_guard_owns_heavy_process(tmp_path, monkeypatch):
    guard = tmp_path / 'diskguard.py'
    guard.touch()
    monkeypatch.setattr(storage, 'GUARD_SCRIPT', guard)
    cmd = storage.guarded_command(['ffmpeg', '-version'], need=123, path=tmp_path, label='test')
    assert cmd[1:3] == [str(guard), 'run']
    assert cmd[cmd.index('--') + 1:] == ['ffmpeg', '-version']
    assert '--accord' not in cmd and 'DISKGUARD_FLOOR_BYTES' not in ' '.join(cmd)


def test_disk_refusal_precedes_command(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'GUARD_SCRIPT', None)
    monkeypatch.setenv('DISKGUARD_FLOOR_BYTES', '999999999999999')
    with pytest.raises(UltraError, match='Insufficient space'):
        storage.guarded_command(['ffmpeg'], need=1, path=tmp_path, label='test')


def test_safe_cleanup_only_verified_job_temporaries(tmp_path):
    job = tmp_path / 'job';job.mkdir()
    owned = job / 'cache.tmp';owned.write_bytes(b'temp')
    final = job / 'final.mp4';final.write_bytes(b'final')
    personal = tmp_path / 'personal.mp4';personal.write_bytes(b'keep')
    link = job / 'link';link.symlink_to(personal)
    with pytest.raises(UltraError):
        storage.cleanup_temporaries(job, [owned], verified=False, protected=[final])
    for unsafe in [final, personal, link]:
        with pytest.raises(UltraError):
            storage.cleanup_temporaries(job, [unsafe], verified=True, protected=[final])
    assert owned.exists() and personal.exists() and final.exists()
    assert storage.cleanup_temporaries(job, [owned], verified=True, protected=[final]) == [str(owned)]
    assert not owned.exists()
