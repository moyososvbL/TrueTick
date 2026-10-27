"""Voice notes and call recordings.

1. Convert any recording (WhatsApp .opus/.ogg, browser .webm, .m4a, .mp3...) to the format
   Muse Voice Transcribe accepts: WAV, PCM 16-bit, mono, 16 or 24 kHz, max 10 minutes.
2. Transcribe it with Muse Voice Transcribe.
3. Check the transcript with the same text checker (link checks + patterns + Muse Spark).
"""

import io
import wave

import av
import numpy as np

from backend.app.ai import meta_client
from backend.app.ai.prompts import VOICE_EXTRA
from backend.app.analyzers.text import analyze_text
from backend.app.models import Verdict

SAMPLE_RATE = 24000  # Meta accepts 16 or 24 kHz; 24 kHz keeps more detail for names like 'iTunes'
MAX_SECONDS = 10 * 60


class BadAudioError(ValueError):
    pass


def to_wav_mono(data: bytes) -> tuple[bytes, float]:
    """Decode any common audio format and return (WAV bytes, duration in seconds)."""
    try:
        container = av.open(io.BytesIO(data))
    except (av.error.FFmpegError, ValueError) as e:
        raise BadAudioError("This doesn't look like an audio recording we can read.") from e
    try:
        if not container.streams.audio:
            raise BadAudioError("This file has no audio in it.")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        chunks: list[np.ndarray] = []
        total = 0
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                arr = out.to_ndarray().reshape(-1)
                chunks.append(arr)
                total += arr.size
                if total > MAX_SECONDS * SAMPLE_RATE:
                    raise BadAudioError("The recording is longer than 10 minutes. Please send a shorter clip.")
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    except av.error.FFmpegError as e:
        raise BadAudioError("We couldn't read this recording.") from e
    finally:
        container.close()

    pcm = np.concatenate(chunks).astype(np.int16) if chunks else np.zeros(0, np.int16)
    if pcm.size < SAMPLE_RATE // 2:
        raise BadAudioError("The recording is too short to understand.")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    return buf.getvalue(), pcm.size / SAMPLE_RATE


async def analyze_audio(data: bytes, caption: str = "") -> Verdict:
    wav, _seconds = to_wav_mono(data)
    try:
        transcript = (await meta_client.transcribe(wav)).strip()
    except meta_client.MetaAPIError:
        return Verdict(
            risk="unknown", input_type="audio",
            summary="We couldn't transcribe this recording right now. Please try again in a minute.",
            advice=["If a voice asks for money, codes or secrecy, hang up and call the person back on a number you know"],
        )
    if not transcript:
        return Verdict(
            risk="unknown", input_type="audio",
            summary="We couldn't hear any clear speech in this recording.",
            advice=["Try a clearer recording, or type what was said and check that"],
        )

    context = "Transcript of a voice note or phone call the user received:\n" + transcript
    if caption:
        context += f"\n\nThe user added: {caption}"
    verdict = await analyze_text(context, extra_system=VOICE_EXTRA)
    verdict.input_type = "audio"
    corrected = verdict.extracted_text.strip()
    verdict.extracted_text = corrected if corrected and verdict.corrections else transcript
    voice_tip = "Voices can be cloned with AI. If it sounds like someone you know, hang up and call them back on their usual number."
    if verdict.risk in ("high", "medium") and voice_tip not in verdict.advice:
        verdict.advice.append(voice_tip)
    return verdict


to_wav_16k_mono = to_wav_mono  # old name, kept for scripts
