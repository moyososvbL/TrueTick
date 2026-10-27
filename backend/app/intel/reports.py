"""Community scam intelligence: "This link was reported 12 times on TrueTick this week".

Privacy by design:
- We never store messages, names or images.
- From risky checks we keep only scrambled fingerprints (salted SHA-256) of the links, phone/account
  numbers and crypto wallets they contained, plus the time and risk level.
- A fingerprint can be matched against a new message, but the original value can't be read back.
"""

import hashlib
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from backend.app.checks.links import extract_urls
from backend.app.config import get_settings
from backend.app.models import RISK_ORDER, Finding, Verdict

WEEK = 7 * 24 * 3600
_lock = threading.Lock()

NUMBER_RE = re.compile(r"(?<![\w.])\+?\d[\d\s-]{8,16}\d(?![\w.])")
WALLET_RE = re.compile(r"\b(?:bc1[a-z0-9]{25,60}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|0x[a-fA-F0-9]{40}|T[1-9A-HJ-NP-Za-km-z]{33})\b")


def _db_path() -> Path:
    path = Path(get_settings().data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path / "truetick.db"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path())
    con.execute("CREATE TABLE IF NOT EXISTS reports (fp TEXT, kind TEXT, risk TEXT, ts INTEGER)")
    con.execute("CREATE INDEX IF NOT EXISTS reports_fp ON reports (fp, ts)")
    con.execute("CREATE TABLE IF NOT EXISTS checks (ts INTEGER, risk TEXT, pattern_id TEXT, input_type TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    return con


def _salt(con: sqlite3.Connection) -> str:
    row = con.execute("SELECT value FROM meta WHERE key='salt'").fetchone()
    if row:
        return row[0]
    salt = secrets.token_hex(16)
    con.execute("INSERT INTO meta VALUES ('salt', ?)", (salt,))
    return salt


def extract_indicators(text: str) -> list[tuple[str, str, str]]:
    """Returns (kind, value_to_fingerprint, short_label_for_display)."""
    found: list[tuple[str, str, str]] = []
    for url in extract_urls(text):
        u = url if re.match(r"(?i)^https?://", url) else "http://" + url
        host = (urlparse(u).hostname or "").lower().removeprefix("www.")
        if host:
            found.append(("link", host, host))
    for m in NUMBER_RE.findall(text):
        digits = re.sub(r"\D", "", m)
        if 9 <= len(digits) <= 15:
            found.append(("number", digits[-10:], "number ending " + digits[-4:]))
    for w in WALLET_RE.findall(text):
        found.append(("wallet", w, "crypto wallet " + w[:6] + "…"))
    seen, unique = set(), []
    for item in found:
        if item[1] not in seen:
            seen.add(item[1])
            unique.append(item)
    return unique


def _fp(salt: str, kind: str, value: str) -> str:
    return hashlib.sha256(f"{salt}|{kind}|{value}".encode()).hexdigest()


def annotate(verdict: Verdict, text: str) -> Verdict:
    """Adds 'reported N times' facts, then records this check if it was risky."""
    indicators = extract_indicators(f"{text}\n{verdict.extracted_text}")
    now = int(time.time())
    with _lock, _connect() as con:
        salt = _salt(con)
        best = 0
        for kind, value, label in indicators:
            fp = _fp(salt, kind, value)
            (n,) = con.execute("SELECT COUNT(*) FROM reports WHERE fp=? AND ts>=?", (fp, now - WEEK)).fetchone()
            if n:
                best = max(best, n)
                times = "once" if n == 1 else f"{n} times"
                verdict.findings.append(Finding(
                    kind="community", severity="medium",
                    message=f"This {label} was flagged as risky {times} on TrueTick in the last 7 days."))
        verdict.community_reports = best
        if best >= 2 and RISK_ORDER[verdict.risk] < RISK_ORDER["medium"]:
            verdict.risk = "medium"
            verdict.summary = verdict.summary or "Other TrueTick users have flagged details in this message."

        if verdict.risk in ("high", "medium"):
            con.executemany("INSERT INTO reports VALUES (?,?,?,?)",
                            [(_fp(salt, k, v), k, verdict.risk, now) for k, v, _ in indicators])
        con.execute("INSERT INTO checks VALUES (?,?,?,?)", (now, verdict.risk, verdict.pattern_id or "", verdict.input_type))
    return verdict


def weekly_stats() -> dict:
    """Anonymous totals for a public 'Scam Weather Report'. No content, no fingerprints."""
    since = int(time.time()) - WEEK
    with _lock, _connect() as con:
        total = con.execute("SELECT COUNT(*) FROM checks WHERE ts>=?", (since,)).fetchone()[0]
        risky = con.execute("SELECT COUNT(*) FROM checks WHERE ts>=? AND risk IN ('high','medium')", (since,)).fetchone()[0]
        by_pattern = con.execute(
            "SELECT pattern_id, COUNT(*) FROM checks WHERE ts>=? AND pattern_id!='' GROUP BY pattern_id ORDER BY 2 DESC LIMIT 10",
            (since,)).fetchall()
        by_input = con.execute("SELECT input_type, COUNT(*) FROM checks WHERE ts>=? GROUP BY input_type", (since,)).fetchall()
    return {"checks_7d": total, "risky_7d": risky,
            "top_patterns": [{"pattern_id": p, "count": c} for p, c in by_pattern],
            "by_input_type": dict(by_input)}
