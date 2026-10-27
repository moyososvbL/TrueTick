import pytest

from backend.app.config import get_settings


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own empty community-reports database."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LINK_INSPECTION", "false")  # no real internet in tests
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
