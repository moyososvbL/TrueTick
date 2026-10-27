"""Shapes of the data TrueTick passes around and returns to the web app."""

from typing import Literal

from pydantic import BaseModel, Field

Risk = Literal["high", "medium", "low", "unknown"]
RISK_ORDER = {"unknown": 0, "low": 1, "medium": 2, "high": 3}


class Finding(BaseModel):
    """A fact found by a non-AI check (links, lookalike letters, QR codes, files...)."""

    kind: Literal["link", "lookalike", "qr", "file", "community", "receipt", "site", "conversation"]
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
    corrections: list[str] = Field(default_factory=list)  # likely mishearings fixed in a voice transcript
    annotated_image: str = ""  # screenshot with suspicious areas boxed (data: URL)
    marked_regions: list[str] = Field(default_factory=list)  # numbered explanations for the boxes
    community_reports: int = 0  # how often its links/numbers were reported on TrueTick in the last 7 days
    links: list[str] = Field(default_factory=list)  # links found, so the app can offer a safe website visit
    # Whole-conversation check (several screenshots)
    stage: str = ""  # how far the scam has got, e.g. "Asking for money"
    timeline: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


class SiteVisit(BaseModel):
    """What TrueTick saw when it opened a link in a sealed browser on its own server."""

    url: str
    final_url: str = ""
    screenshot: str = ""  # data: URL (JPEG)
    looks_like: str = ""  # brand the page is dressed up as, if any
    page_purpose: str = ""  # login | payment | download | personal_details | shop | info | other
    asks_for: list[str] = Field(default_factory=list)
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    risk: Risk = "unknown"
    error: str = ""


class CheckTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
