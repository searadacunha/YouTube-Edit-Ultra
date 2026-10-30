import pytest


@pytest.fixture(scope="session", autouse=True)
def exclude_generated_fixtures_from_real_catalogue(tmp_path_factory):
    # Synthetic sources must never enter the person's real production library.
    (tmp_path_factory.getbasetemp() / ".ultra-ignore").touch()


@pytest.fixture(autouse=True)
def no_mac_disk_floor(monkeypatch):
    # Tests must not depend on this Mac's free space; test_disk_floor sets the floor explicitly.
    monkeypatch.setenv("DISKGUARD_FLOOR_BYTES", "0")
    # Fixture renders must never create reservations in the person's live manager.
    from youtube_edit_ultra import storage
    monkeypatch.setattr(storage, 'GUARD_SCRIPT', None)
