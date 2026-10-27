"""Shapes of the data TrueTick passes around and returns to the web app."""

from typing import Literal

from pydantic import BaseModel, Field

Risk = Literal["high", "medium", "low", "unknown"]
RISK_ORDER = {"unknown": 0, "low": 1, "medium": 2, "high": 3}


class Finding(BaseModel):
    """A fact found by a non-AI check (links, lookalike letters, QR codes, files...)."""

    kind: Literal["link", "lookalike", "qr", "file", "community"]
    severity: Literal["high", "medium"]
    message: str


class Verdict(BaseModel):
    risk: Risk = "unknown"
    scam_type: str = ""
    pattern_id: str | None = None
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    what_next: str = ""
    advice: list[str] = Field(default_factory=list)
    is_threat: bool = False
    findings: list[Finding] = Field(default_factory=list)
    ai_used: bool = False
    input_type: Literal["text", "image", "audio", "file"] = "text"
    extracted_text: str = ""  # e.g. what a QR code contains, or a voice note transcript
    community_reports: int = 0  # how often its links/numbers were reported on TrueTick in the last 7 days


class CheckTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
