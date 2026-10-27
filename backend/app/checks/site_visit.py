"""'We visited the website for you.'

Opens a suspicious link in a sealed, throwaway headless browser on TrueTick's server, so the user
never has to. The page is screenshotted and Muse Spark describes what it is pretending to be.
TrueTick then compares that with the real web address: a page dressed up as a bank on a domain
that isn't the bank's is the clearest phishing sign there is.

Sealed means: a fresh browser profile every time, no downloads, no permissions, every request
(not just the first) refused if it points to a private network address, and a hard time limit.
"""

import asyncio
import base64
import io
import logging
import re
from urllib.parse import urlsplit

from PIL import Image

from backend.app.ai import meta_client, prompts
from backend.app.analyzers.common import parse_model_json
from backend.app.checks.link_inspect import UnsafeTarget, _assert_public_host, registrable_domain
from backend.app.checks.lookalike import BRANDS, is_official, normalize
from backend.app.config import get_settings
from backend.app.models import RISK_ORDER, Finding, SiteVisit

log = logging.getLogger("truetick.site")

VIEWPORT = {"width": 412, "height": 915}  # a typical phone, because that's where people open these links
PAGE_TIMEOUT_MS = 12000
SENSITIVE = re.compile(r"\b(password|card|cvv|otp|code|pin|seed|recovery phrase|bvn|ssn|social security|"
                       r"id|passport|login|account number)\b", re.I)


class VisitUnavailable(Exception):
    pass


async def _host_ok(host: str, cache: dict[str, bool]) -> bool:
    if host not in cache:
        try:
            await _assert_public_host(host)
            cache[host] = True
        except UnsafeTarget:
            cache[host] = False
    return cache[host]


async def screenshot(url: str) -> tuple[bytes, str]:
    """PNG screenshot of the page and the address it finally landed on."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise VisitUnavailable("the safe browser isn't installed on this server") from e

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeTarget("only normal web links can be visited")
    cache: dict[str, bool] = {}
    if not await _host_ok(parts.hostname, cache):
        raise UnsafeTarget("it points to a private network address")

    async def guard(route):
        req = urlsplit(route.request.url)
        if req.scheme in ("data", "blob"):
            return await route.continue_()
        if req.scheme not in ("http", "https") or not req.hostname or not await _host_ok(req.hostname, cache):
            return await route.abort()
        if route.request.resource_type in ("media", "websocket", "eventsource"):
            return await route.abort()
        await route.continue_()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            ctx = await browser.new_context(
                viewport=VIEWPORT, device_scale_factor=1, is_mobile=True, has_touch=True,
                accept_downloads=False, service_workers="block", permissions=[],
                user_agent=("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/126.0 Mobile Safari/537.36"),
            )
            await ctx.route("**/*", guard)
            page = await ctx.new_page()
            page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                await page.wait_for_timeout(1500)  # let phishing kits draw their fake login box
            except Exception as e:  # timeouts still leave something worth screenshotting
                log.info("Page load incomplete: %s", e.__class__.__name__)
            png = await page.screenshot(full_page=False, timeout=5000)
            return png, page.url
        finally:
            await browser.close()


def _jpeg_data_url(png: bytes) -> str:
    with Image.open(io.BytesIO(png)) as im:
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=75)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _brand_key(name: str) -> str | None:
    compact = re.sub(r"[^a-z0-9]", "", normalize(name))
    for key, (display, _) in BRANDS.items():
        if key in compact or re.sub(r"[^a-z0-9]", "", display.lower()) in compact:
            return key
    return None


def compare(host: str, looks_like: str, purpose: str, asks_for: list[str]) -> list[Finding]:
    """The decisive check: does the brand on the page match the real web address?"""
    findings: list[Finding] = []
    asks_sensitive = purpose in ("login", "payment", "personal_details") or any(
        SENSITIVE.search(a) for a in asks_for)
    domain = registrable_domain(host)
    brand = (looks_like or "").strip()
    if brand:
        key = _brand_key(brand)
        if key:
            mismatch = not is_official(host, key)
            shown = BRANDS[key][0]
            official = BRANDS[key][1][0]
        else:
            # A brand we don't have on file: does any real word of its name appear in the address?
            words = [w for w in re.findall(r"[a-z0-9]{3,}", normalize(brand)) if w not in {"bank", "the", "inc", "ltd", "plc"}]
            mismatch = bool(words) and not any(w in re.sub(r"[^a-z0-9]", "", domain) for w in words)
            shown, official = brand, ""
        if mismatch:
            where = f" (the real one is {official})" if official else ""
            findings.append(Finding(
                kind="site", severity="high" if asks_sensitive else "medium",
                message=f"This page is dressed up as {shown}, but it is on {domain}, not {shown}'s real website{where}."))
    if asks_sensitive and (not brand or findings):
        wanted = ", ".join(asks_for[:4]) or purpose.replace("_", " ")
        findings.append(Finding(kind="site", severity="medium", message=f"The page asks you to enter: {wanted}."))
    if purpose == "download":
        findings.append(Finding(kind="site", severity="high",
                                message="The page pushes you to download something. Don't install apps from links."))
    return findings


async def visit(url: str) -> SiteVisit:
    s = get_settings()
    result = SiteVisit(url=url)
    if not s.site_visit:
        result.error = "Website visits are switched off on this server."
        return result
    try:
        png, final_url = await screenshot(url)
    except UnsafeTarget as e:
        result.error = f"We didn't open this link because {e}."
        return result
    except VisitUnavailable as e:
        result.error = f"We couldn't open the website: {e}."
        return result
    except Exception as e:
        log.error("Visit failed: %s", e.__class__.__name__)
        result.error = "The website didn't load. It may already be taken down, which scam sites often are."
        return result

    result.final_url = final_url
    result.screenshot = _jpeg_data_url(png)
    host = urlsplit(final_url).hostname or urlsplit(url).hostname or ""
    try:
        file_id = await meta_client.upload_file(png, "page.png", "image/png")
        events = await meta_client.respond(s.vision_model, [
            {"type": "input_text", "text": prompts.SITE_PROMPT.format(url=final_url)},
            {"type": "input_image", "file_id": file_id},
        ])
        data = parse_model_json(meta_client.output_text(events))
    except (meta_client.MetaAPIError, ValueError, TypeError) as e:
        log.error("Site vision failed: %s", e)
        result.summary = "Here's what the page looks like. We couldn't describe it automatically right now."
        return result

    result.looks_like = str(data.get("looks_like") or "")[:80]
    result.page_purpose = str(data.get("page_purpose") or "other")[:30]
    result.asks_for = [str(a)[:60] for a in (data.get("asks_for") or [])][:6]
    result.summary = str(data.get("summary") or "")[:300]
    result.findings = compare(host, result.looks_like, result.page_purpose, result.asks_for)
    result.findings += [Finding(kind="site", severity="medium", message=str(f)[:160])
                        for f in (data.get("visual_red_flags") or [])[:3]]
    risk = "low"
    for f in result.findings:
        if f.kind == "site" and f.message.startswith(("This page is dressed", "The page pushes", "The page asks")):
            risk = max(risk, f.severity, key=lambda r: RISK_ORDER[r])
    result.risk = risk
    return result

