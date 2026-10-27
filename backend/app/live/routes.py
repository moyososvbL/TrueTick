"""Live Call Guard API.

The browser records the call (on speaker) in short, complete pieces and sends each one here.
- POST /api/live/chunk   → transcript of that piece (Muse Voice Transcribe) + instant alerts
- POST /api/live/assess  → Muse Spark verdict on the whole conversation so far
Nothing is stored: audio and transcripts exist only for the request.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.app.ai import meta_client
from backend.app.ai.prompts import LIVE_EXTRA, VOICE_EXTRA
from backend.app.analyzers.audio import BadAudioError, to_wav_mono
from backend.app.analyzers.text import analyze_text
from backend.app.live.rules import scan
from backend.app.models import Verdict

router = APIRouter(prefix="/api/live", tags=["live"])
MAX_CHUNK_BYTES = 2 * 1024 * 1024
MAX_TRANSCRIPT = 12000


@router.post("/chunk")
async def live_chunk(audio: UploadFile = File(...), so_far: str = Form(default="", max_length=MAX_TRANSCRIPT)):
    data = await audio.read(MAX_CHUNK_BYTES + 1)
    if len(data) > MAX_CHUNK_BYTES:
        raise HTTPException(413, "Audio piece too large.")
    try:
        wav, seconds = to_wav_mono(data)
    except BadAudioError:
        # Silence or a broken piece: not an error for a live session, just nothing new.
        return {"text": "", "alerts": [a.__dict__ for a in scan(so_far)]}
    try:
        text = (await meta_client.transcribe(wav)).strip()
    except meta_client.MetaAPIError:
        return {"text": "", "alerts": [a.__dict__ for a in scan(so_far)], "error": "transcription unavailable"}
    full = f"{so_far} {text}".strip()
    return {"text": text, "alerts": [a.__dict__ for a in scan(full)]}


class AssessRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=MAX_TRANSCRIPT)


@router.post("/assess", response_model=Verdict)
async def live_assess(req: AssessRequest) -> Verdict:
    context = "Live transcript of a phone call that is STILL IN PROGRESS (on speaker):\n" + req.transcript
    verdict = await analyze_text(context, extra_system=VOICE_EXTRA + LIVE_EXTRA)
    verdict.input_type = "audio"
    return verdict
