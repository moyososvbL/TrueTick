"""The only place in TrueTick that talks to the Meta Model API.

Two styles of call:
- chat():        POST {base}/chat/completions   (OpenAI-compatible, text in → text out)
- upload_file(): POST {base}/files              (images/audio → file_id)
  respond():     POST {base}/responses          (file_id + prompt → streamed events; used by SAM 3.1
                                                  and for Muse Spark reading images)
"""

import json

import httpx

from backend.app.config import get_settings


class MetaAPIError(Exception):
    """A readable error for when the Meta Model API call fails."""


_HINTS = {
    400: "The request was rejected. The model may not accept this kind of input.",
    401: "The API key was rejected. Check META_API_KEY in your .env file.",
    402: "Payment required. Check that your hackathon credit is active on dev.meta.ai.",
    403: "Access denied. Your Meta Model API account may be restricted. Check the banner on dev.meta.ai.",
    404: "Not found. Check META_API_BASE_URL and the model name in .env.",
    413: "The file is too large for the Meta Model API.",
    429: "Too many requests or out of credit. Wait a moment, then check Usage on dev.meta.ai.",
}


def _base_and_headers() -> tuple[str, dict]:
    s = get_settings()
    if not s.meta_api_key:
        raise MetaAPIError("META_API_KEY is empty. Add your key to the .env file.")
    return s.meta_api_base_url.rstrip("/"), {"Authorization": f"Bearer {s.meta_api_key}"}


# If an account can't use the configured Muse Spark version, step down to an older one.
# (Never the "-contributor" models.)
SPARK_FALLBACKS = ["muse-spark-1.3", "muse-spark-1.2", "muse-spark-1.1"]
_working_model: dict[str, str] = {}


def _candidates(model: str) -> list[str]:
    if model in _working_model:
        return [_working_model[model]]
    if not model.startswith("muse-spark"):
        return [model]
    return list(dict.fromkeys([model] + SPARK_FALLBACKS))


def _model_missing(status: int, body: str) -> bool:
    return status == 404 and "model_not_found" in body


def _fail(status: int, body: str) -> MetaAPIError:
    hint = _HINTS.get(status, "Unexpected error from the Meta Model API.")
    return MetaAPIError(f"{hint} (HTTP {status}: {body[:300]})")


async def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Send a conversation to Muse Spark and return the reply text."""
    base, headers = _base_and_headers()
    wanted = model or get_settings().text_model
    async with httpx.AsyncClient(timeout=60, transport=transport) as client:
        for name in _candidates(wanted):
            payload = {"model": name, "messages": messages, "temperature": temperature}
            try:
                r = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
            except httpx.HTTPError as e:
                raise MetaAPIError(f"Couldn't reach the Meta Model API ({e.__class__.__name__}). Check your internet.") from e
            if not _model_missing(r.status_code, r.text):
                if r.status_code < 400:
                    _working_model[wanted] = name
                break
    if r.status_code >= 400:
        raise _fail(r.status_code, r.text)
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise MetaAPIError(f"Unexpected reply format: {r.text[:300]}") from e


async def upload_file(
    data: bytes, filename: str, mime: str, transport: httpx.AsyncBaseTransport | None = None
) -> str:
    """Upload an image or audio file and return its file_id."""
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=120, transport=transport) as client:
        try:
            r = await client.post(
                f"{base}/files", headers=headers,
                data={"purpose": "user_data"}, files={"file": (filename, data, mime)},
            )
        except httpx.HTTPError as e:
            raise MetaAPIError(f"Couldn't upload the file to Meta ({e.__class__.__name__}).") from e
    if r.status_code >= 400:
        raise _fail(r.status_code, r.text)
    file_id = r.json().get("id")
    if not isinstance(file_id, str) or not file_id:
        raise MetaAPIError("File upload finished without a file id.")
    return file_id


async def respond(
    model: str,
    content: list[dict],
    metadata: dict | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[dict]:
    """Call the Responses API with streaming and return every event as a dict.

    content example: [{"type": "input_text", "text": "..."}, {"type": "input_image", "file_id": "..."}]
    """
    base, headers = _base_and_headers()
    headers = {**headers, "Accept": "text/event-stream"}
    names = _candidates(model)
    for i, name in enumerate(names):
        payload: dict = {
            "model": name,
            "input": [{"type": "message", "role": "user", "content": content}],
            "stream": True,
        }
        if metadata:
            payload["metadata"] = metadata
        try:
            events = await _stream_response(base, headers, payload, transport)
        except _ModelMissing as e:
            if i == len(names) - 1:
                raise _fail(404, str(e)) from None
            continue
        if name != model:
            _working_model[model] = name
        return events
    return []


class _ModelMissing(Exception):
    pass


async def _stream_response(base: str, headers: dict, payload: dict,
                           transport: httpx.AsyncBaseTransport | None) -> list[dict]:
    events: list[dict] = []
    async with httpx.AsyncClient(timeout=180, transport=transport) as client:
        try:
            async with client.stream("POST", f"{base}/responses", json=payload, headers=headers) as r:
                if r.status_code >= 400:
                    body = (await r.aread()).decode(errors="replace")
                    if _model_missing(r.status_code, body):
                        raise _ModelMissing(body)
                    raise _fail(r.status_code, body)
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        events.append(json.loads(data))
                    except json.JSONDecodeError:
                        events.append({"type": "raw", "data": data})
        except httpx.HTTPError as e:
            raise MetaAPIError(f"Couldn't reach the Meta Model API ({e.__class__.__name__}).") from e
    return events


def transcribe_request_parts(wav: bytes, request: dict) -> dict:
    """Multipart body for /asr/transcribe: a JSON 'request' part plus the 'audio' part."""
    return {
        "request": (None, json.dumps(request), "application/json"),
        "audio": ("audio.wav", wav, "audio/wav"),
    }


async def transcribe(wav: bytes, transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Muse Voice Transcribe: WAV (PCM 16-bit mono, 16/24 kHz, max 10 min) → text."""
    base, headers = _base_and_headers()
    # Confirmed working on the live API (Oct 27): model + audioEncoding "WAV".
    request = {"model": get_settings().transcribe_model, "audioEncoding": "WAV"}
    async with httpx.AsyncClient(timeout=180, transport=transport) as client:
        try:
            r = await client.post(f"{base}/asr/transcribe", headers=headers,
                                  files=transcribe_request_parts(wav, request))
        except httpx.HTTPError as e:
            raise MetaAPIError(f"Couldn't reach Muse Voice Transcribe ({e.__class__.__name__}).") from e
    if r.status_code >= 400:
        raise _fail(r.status_code, r.text)
    try:
        return transcript_from_response(r.json())
    except ValueError as e:
        raise MetaAPIError(f"Unexpected transcription reply: {r.text[:300]}") from e


def transcript_from_response(data) -> str:
    """Pull the transcript out of the reply, whichever common shape it uses."""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return " ".join(t for t in (transcript_from_response(x) for x in data) if t)
    if not isinstance(data, dict):
        return ""
    for key in ("text", "transcript", "transcription"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, (dict, list)):
            found = transcript_from_response(value)
            if found:
                return found
    for key in ("segments", "turns", "results", "utterances", "output"):
        if isinstance(data.get(key), list):
            found = transcript_from_response(data[key])
            if found:
                return found
    return ""


async def generate_image(prompt: str, size: str = "1024x1024",
                         transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    """Muse Image: text → PNG bytes (POST /images/generations, about $0.01 per image)."""
    import base64

    base, headers = _base_and_headers()
    payload = {"model": get_settings().image_model, "prompt": prompt, "n": 1, "size": size,
               "response_format": "b64_json", "output_format": "png"}
    async with httpx.AsyncClient(timeout=180, transport=transport) as client:
        try:
            r = await client.post(f"{base}/images/generations", json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise MetaAPIError(f"Couldn't reach Muse Image ({e.__class__.__name__}).") from e
    if r.status_code >= 400:
        raise _fail(r.status_code, r.text)
    try:
        b64 = r.json()["data"][0]["b64_json"]
        return base64.b64decode(b64)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        raise MetaAPIError(f"Unexpected Muse Image reply: {r.text[:300]}") from e


def output_text(events: list[dict]) -> str:
    """Assemble the text answer from Responses API events."""
    deltas = [e.get("delta", "") for e in events if str(e.get("type", "")).endswith("output_text.delta")]
    if deltas:
        return "".join(d for d in deltas if isinstance(d, str))
    for e in reversed(events):
        response = e.get("response") if isinstance(e.get("response"), dict) else None
        for item in (response or {}).get("output", []) or []:
            for part in item.get("content", []) or []:
                if part.get("type") in ("output_text", "text") and part.get("text"):
                    return part["text"]
    return ""
