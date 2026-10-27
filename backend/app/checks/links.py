"""Fast, non-AI checks on links. Facts from here are passed to Muse Spark as evidence."""

import ipaddress
import re
from urllib.parse import urlparse

from backend.app.checks.lookalike import (
    BRANDS,
    brands_imitated_by_host,
    check_text_lookalikes,
    decode_host,
    is_official,
)
from backend.app.models import Finding

URL_RE = re.compile(
    r"(?i)\b((?:https?://|www\.)[^\s<>\"']+|(?:[a-z0-9-]+\.)+[a-z]{2,}/[^\s<>\"']*)"
)
SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "cutt.ly", "rb.gy",
    "shorturl.at", "tiny.cc", "t.ly", "rebrand.ly", "s.id",
}
RISKY_TLDS = {
    "xyz", "top", "click", "zip", "mov", "icu", "buzz", "rest", "cam", "support", "live",
    "online", "site", "info", "shop", "loan", "work", "cfd", "sbs", "lol", "quest",
}
BAIT_WORDS = ("verify", "secure", "login", "signin", "update", "unlock", "reward", "claim",
              "bonus", "wallet", "refund", "giveaway", "payout")


def extract_urls(text: str) -> list[str]:
    return list(dict.fromkeys(u.rstrip(".,!?)") for u in URL_RE.findall(text or "")))


def _parse(url: str):
    if not re.match(r"(?i)^https?://", url):
        url = "http://" + url
    return urlparse(url)


def check_url(url: str) -> list[Finding]:
    parsed = _parse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return []
    if not parsed.username and any(is_official(host, b) for b in BRANDS):
        return []  # genuinely on a known company's real website
    out: list[Finding] = []

    def add(sev, msg):
        out.append(Finding(kind="link", severity=sev, message=msg))

    shown = decode_host(host)
    for brand, used_lookalike in brands_imitated_by_host(host):
        name = BRANDS[brand][0]
        if used_lookalike:
            add("high", f"Link uses lookalike letters to pretend to be {name} ({shown}).")
        else:
            add("high", f"Link pretends to be {name} but is NOT {name}'s real website ({shown}).")

    if parsed.username or "@" in parsed.netloc:
        add("high", f"Link hides its real destination with an '@' trick. It actually goes to {shown}.")
    try:
        ipaddress.ip_address(host)
        add("high", f"Link goes to a bare number address ({host}) instead of a website name.")
    except ValueError:
        pass
    if "xn--" in host and not out:
        add("high", f"Link uses unusual characters that can imitate real websites ({shown}).")
    if host in SHORTENERS:
        add("medium", f"Link is shortened ({host}), which hides where it really goes.")
    tld = host.rsplit(".", 1)[-1]
    if tld in RISKY_TLDS:
        add("medium", f"Link ends in .{tld}, a website ending often used in scams.")
    if any(w in host for w in BAIT_WORDS) or host.count("-") >= 2:
        add("medium", f"Website name ({shown}) uses bait words or many dashes, typical of phishing.")
    if parsed.scheme == "http" and not url.lower().startswith("www."):
        add("medium", "Link is not secure (http instead of https).")
    return out


def run_checks(text: str) -> list[Finding]:
    """All non-AI checks on a piece of text."""
    findings: list[Finding] = []
    urls = extract_urls(text)
    for url in urls:
        findings.extend(check_url(url))
    without_urls = text
    for url in urls:
        without_urls = without_urls.replace(url, " ")
    findings.extend(Finding(kind="lookalike", severity="high", message=m) for m in check_text_lookalikes(without_urls))
    seen, unique = set(), []
    for f in findings:
        if f.message not in seen:
            seen.add(f.message)
            unique.append(f)
    return unique
