import asyncio
import json

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


def test_upload_file_returns_id():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return httpx.Response(200, json={"id": "file-123"})

    fid = asyncio.run(meta_client.upload_file(b"img", "a.jpg", "image/jpeg", transport=httpx.MockTransport(handler)))
    assert fid == "file-123"
    assert seen["url"].endswith("/v1/files")
    assert b"user_data" in seen["body"] and b"a.jpg" in seen["body"]


def test_respond_parses_stream_and_text():
    sse = (
        'data: {"type": "response.created"}\n\n'
        'data: {"type": "response.output_text.delta", "delta": "Hello "}\n\n'
        'data: {"type": "response.output_text.delta", "delta": "world"}\n\n'
        "data: [DONE]\n\n"
    )
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    events = asyncio.run(meta_client.respond(
        "sam-3.1", [{"type": "input_text", "text": "hi"}], metadata={"mask_encoding": "lossless"},
        transport=httpx.MockTransport(handler),
    ))
    assert len(events) == 3
    assert meta_client.output_text(events) == "Hello world"
    body = json.loads(seen["body"])
    assert body["stream"] is True and body["metadata"] == {"mask_encoding": "lossless"}


def test_output_text_from_completed_event():
    events = [{"type": "response.completed",
               "response": {"output": [{"content": [{"type": "output_text", "text": "Done"}]}]}}]
    assert meta_client.output_text(events) == "Done"


def test_respond_error_is_readable():
    def handler(request):
        return httpx.Response(403, text="restricted")

    with pytest.raises(meta_client.MetaAPIError, match="restricted"):
        asyncio.run(meta_client.respond("sam-3.1", [], transport=httpx.MockTransport(handler)))


def test_chat_steps_down_when_model_missing(monkeypatch):
    import asyncio
    import httpx
    from backend.app.ai import meta_client
    from backend.app.config import get_settings
    monkeypatch.setenv("META_API_KEY", "test")
    monkeypatch.setenv("TEXT_MODEL", "muse-spark-1.3")
    get_settings.cache_clear()
    meta_client._working_model.clear()
    tried = []

    def handler(request):
        import json as _j
        model = _j.loads(request.content)["model"]
        tried.append(model)
        if model == "muse-spark-1.1":
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        return httpx.Response(404, json={"error": {"code": "model_not_found"}})

    out = asyncio.run(meta_client.chat([{"role": "user", "content": "hi"}], transport=httpx.MockTransport(handler)))
    assert out == "ok"
    assert tried == ["muse-spark-1.3", "muse-spark-1.2", "muse-spark-1.1"]
    assert all("contributor" not in m for m in tried)
    meta_client._working_model.clear()
    get_settings.cache_clear()
