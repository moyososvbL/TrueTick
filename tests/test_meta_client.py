import asyncio

import httpx
import pytest

from backend.app.ai import meta_client
from backend.app.config import get_settings


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "test-key")
    monkeypatch.setenv("META_API_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("TEXT_MODEL", "muse-spark-1.3")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _run(handler):
    transport = httpx.MockTransport(handler)
    return asyncio.run(meta_client.chat([{"role": "user", "content": "hi"}], transport=transport))


def test_sends_openai_style_request_and_reads_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello from Muse Spark"}}]})

    assert _run(handler) == "Hello from Muse Spark"
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    assert '"model":"muse-spark-1.3"' in seen["body"].replace(" ", "")


def test_bad_key_gives_readable_error():
    with pytest.raises(meta_client.MetaAPIError, match="API key was rejected"):
        _run(lambda r: httpx.Response(401, json={"error": "invalid key"}))


def test_missing_key(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(meta_client.MetaAPIError, match="META_API_KEY is empty"):
        _run(lambda r: httpx.Response(200))
