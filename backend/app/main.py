"""TrueTick web server.

Run from the project root:
    uvicorn backend.app.main:app --reload
Then open http://127.0.0.1:8000
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.analyzers.text import analyze_text
from backend.app.config import get_settings
from backend.app.models import CheckTextRequest, Verdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="TrueTick", version="0.1.0")
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@app.get("/api/health")
async def health():
    s = get_settings()
    return {"status": "ok", "model": s.text_model, "ai_configured": bool(s.meta_api_key)}


@app.post("/api/check/text", response_model=Verdict)
async def check_text(req: CheckTextRequest) -> Verdict:
    # Privacy: we never log or store the message itself.
    return await analyze_text(req.text)


# The web app. Mounted last so /api routes take priority.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
