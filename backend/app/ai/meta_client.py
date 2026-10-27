"""The only place in TrueTick that talks to the Meta Model API.

The API is OpenAI-compatible: POST {base_url}/chat/completions with a Bearer key.
"""

import httpx

from backend.app.config import get_settings


class MetaAPIError(Exception):
    """A readable error for when the Meta Model API call fails."""


_HINTS = {
    401: "The API key was rejected. Check META_API_KEY in your .env file.",
    402: "Payment required. Check that your hackathon credit is active on dev.meta.ai.",
    403: "Access denied. Your Meta Model API account may be restricted. Check the banner on dev.meta.ai.",
    404: "Not found. Check META_API_BASE_URL and the model name in .env.",
    429: "Too many requests or out of credit. Wait a moment, then check Usage on dev.meta.ai.",
}


async def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Send a conversation to Muse Spark and return the reply text."""
    s = get_settings()
    if not s.meta_api_key:
        raise MetaAPIError("META_API_KEY is empty. Add your key to the .env file.")

    url = f"{s.meta_api_base_url.rstrip('/')}/chat/completions"
    payload = {"model": model or s.text_model, "messages": messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {s.meta_api_key}"}

    async with httpx.AsyncClient(timeout=60, transport=transport) as client:
        try:
            r = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise MetaAPIError(f"Couldn't reach the Meta Model API ({e.__class__.__name__}). Check your internet.") from e

    if r.status_code >= 400:
        hint = _HINTS.get(r.status_code, "Unexpected error from the Meta Model API.")
        raise MetaAPIError(f"{hint} (HTTP {r.status_code}: {r.text[:300]})")

    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise MetaAPIError(f"Unexpected reply format: {r.text[:300]}") from e
