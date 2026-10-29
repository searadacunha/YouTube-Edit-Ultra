import pytest


@pytest.fixture(scope="session", autouse=True)
def exclude_generated_fixtures_from_real_catalogue(tmp_path_factory):
    # Synthetic sources must never enter the person's real production library.
    (tmp_path_factory.getbasetemp() / ".ultra-ignore").touch()
