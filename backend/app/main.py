"""TrueTick web server.

Run from the project root:
    uvicorn backend.app.main:app --reload
Then open http://127.0.0.1:8000
"""

import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.app import cards
from backend.app.analyzers.conversation import MAX_IMAGES, analyze_conversation
from backend.app.analyzers.audio import BadAudioError, analyze_audio
from backend.app.analyzers.files import analyze_file, check_file
from backend.app.analyzers.image import BadImageError, analyze_image, analyze_qr_contents
from backend.app.analyzers.text import analyze_text
from backend.app.checks import site_visit
from backend.app.checks.links import extract_urls
from backend.app.config import get_settings
from backend.app.intel import reports
from backend.app.live.routes import router as live_router
from backend.app.models import CheckTextRequest, SiteVisit, Verdict
from backend.app.reporting import helper as report_helper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="TrueTick", version="0.3.0")
app.include_router(live_router)
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
AUDIO_EXT = (".ogg", ".opus", ".oga", ".m4a", ".mp3", ".wav", ".aac", ".amr", ".webm")


@app.get("/api/health")
async def health():
    s = get_settings()
    return {"status": "ok", "model": s.text_model, "ai_configured": bool(s.meta_api_key)}


@app.post("/api/check/text", response_model=Verdict)
async def check_text(req: CheckTextRequest) -> Verdict:
    # Privacy: we never log or store the message itself.
    return _with_links(reports.annotate(await analyze_text(req.text), req.text), req.text)


async def _read_limited(upload: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is too large (max {get_settings().max_upload_mb} MB).")
    if not data:
        raise HTTPException(400, "The file is empty.")
    return data


@app.post("/api/check", response_model=Verdict)
async def check_anything(
    text: str = Form(default="", max_length=8000),
    file: UploadFile | None = File(default=None),
) -> Verdict:
    """One endpoint for everything: text, screenshots/photos, voice notes and files."""
    verdict = await _route(text, file)
    return _with_links(reports.annotate(verdict, text), text)


def _with_links(verdict: Verdict, text: str) -> Verdict:
    if not verdict.links:
        verdict.links = extract_urls(f"{text}\n{verdict.extracted_text}")[:3]
    return verdict


@app.post("/api/check/conversation", response_model=Verdict)
async def check_conversation(
    files: list[UploadFile] = File(...),
    text: str = Form(default="", max_length=2000),
) -> Verdict:
    """Several screenshots of one chat, read together as one story (timeline, stage, contradictions)."""
    if not 2 <= len(files) <= MAX_IMAGES:
        raise HTTPException(422, f"Send between 2 and {MAX_IMAGES} screenshots, in order.")
    images = []
    for f in files:
        mime = (f.content_type or "").lower()
        if mime not in IMAGE_TYPES:
            raise HTTPException(400, "Only screenshots or photos (JPG, PNG, WebP) can be checked together.")
        images.append((await _read_limited(f), mime))
    try:
        verdict = await analyze_conversation(images, caption=text)
    except BadImageError as e:
        raise HTTPException(400, str(e)) from e
    return reports.annotate(verdict, verdict.extracted_text)


class QRRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


@app.post("/api/check/qr", response_model=Verdict)
async def check_qr(req: QRRequest) -> Verdict:
    """A QR code read live by the phone or laptop camera. Only its text is sent, never the camera image."""
    verdict = await analyze_qr_contents([req.content.strip()])
    return reports.annotate(verdict, req.content)


class VisitRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2000)


@app.post("/api/visit", response_model=SiteVisit)
async def visit_site(req: VisitRequest) -> SiteVisit:
    """Open a link in a sealed browser on our server, screenshot it and say what it's pretending to be."""
    url = req.url.strip()
    if "://" not in url:
        url = "http://" + url
    return await site_visit.visit(url)


class ReportRequest(BaseModel):
    verdict: Verdict
    country: str = Field(default="", max_length=2)
    what_happened: str = Field(default="", max_length=4000)


@app.get("/api/report/countries")
async def report_countries():
    return report_helper.countries()


@app.post("/api/report")
async def report(req: ReportRequest):
    """Official reporting links for the user's country, plus a summary they can paste into a report."""
    return {
        "options": report_helper.report_options(req.country, intimate_images=req.verdict.is_threat),
        "summary": report_helper.report_summary(req.verdict, req.what_happened),
    }


class CardRequest(BaseModel):
    pattern_id: str | None = Field(default=None, max_length=60)
    scam_type: str = Field(default="", max_length=80)


@app.post("/api/card")
async def warning_card(req: CardRequest):
    """A shareable family warning card for a scam TYPE. The user's own message is never sent."""
    site = get_settings().public_url or "TrueTick"
    png, illustrated = await cards.make_card(req.pattern_id, req.scam_type, site)
    return Response(png, media_type="image/png", headers={"X-Illustrated-By": "muse-image" if illustrated else "none"})


@app.get("/api/stats")
async def stats():
    """Anonymous weekly totals (no message content) for a future Scam Weather Report."""
    return reports.weekly_stats()


async def _route(text: str, file: UploadFile | None) -> Verdict:
    if file is None or not file.filename:
        if not text.strip():
            raise HTTPException(422, "Send a message or a file to check.")
        return await analyze_text(text)

    data = await _read_limited(file)
    mime = (file.content_type or "").lower()
    name = file.filename or ""

    # Dangerous apps are caught first, whatever they claim to be.
    if any(f.severity == "high" for f in check_file(name, mime, data)):
        return analyze_file(name, mime, data)

    if mime in IMAGE_TYPES:
        try:
            return await analyze_image(data, mime, caption=text)
        except BadImageError as e:
            raise HTTPException(400, str(e)) from e

    if mime.startswith("audio/") or name.lower().endswith(AUDIO_EXT):
        try:
            return await analyze_audio(data, caption=text)
        except BadAudioError as e:
            raise HTTPException(400, str(e)) from e

    return analyze_file(name, mime, data)


# The web app. Mounted last so /api routes take priority.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
