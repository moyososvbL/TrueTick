"""Checks Muse Voice Transcribe on a recording (WhatsApp voice note, .mp3, .m4a, .wav...).

Run from the project root (virtual environment active):
    python scripts/check_transcribe.py path/to/voice_note.ogg
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ai.meta_client import _base_and_headers, MetaAPIError, transcript_from_response  # noqa: E402
from backend.app.analyzers.audio import BadAudioError, to_wav_16k_mono  # noqa: E402
from backend.app.config import get_settings  # noqa: E402


async def main(path: Path) -> None:
    try:
        wav, seconds = to_wav_16k_mono(path.read_bytes())
    except BadAudioError as e:
        print(f"❌ {e}")
        sys.exit(1)
    print(f"Converted {path.name}: {seconds:.1f} seconds of audio.")

    try:
        base, headers = _base_and_headers()
    except MetaAPIError as e:
        print(f"❌ {e}")
        sys.exit(1)
    model = get_settings().transcribe_model
    print(f"Sending to {model} ...")
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{base}/asr/transcribe", headers=headers,
                              data={"model": model}, files={"file": ("audio.wav", wav, "audio/wav")})
    print(f"HTTP {r.status_code}")
    try:
        body = r.json()
        print("Raw reply (shortened):", json.dumps(body)[:1500])
    except ValueError:
        body = None
        print("Raw reply:", r.text[:1500])
    if r.status_code < 400 and body is not None:
        text = transcript_from_response(body)
        print(f"\n✅ Transcript: {text}" if text else "\n⚠️ Couldn't find the transcript in the reply. Send me the raw reply above.")


def _require_file(path: Path) -> Path:
    if not path.is_file():
        print(f"❌ File not found: {path}")
        print("Put the file in your TrueTick folder and use its exact name (including .jpg/.png/.ogg),")
        print('or give the full path in quotes, e.g. "C:/Users/pc/Pictures/receipt.jpg"')
        sys.exit(1)
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_transcribe.py path/to/recording")
        sys.exit(1)
    asyncio.run(main(_require_file(Path(sys.argv[1]))))
