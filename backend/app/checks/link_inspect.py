"""Looks behind a link safely, so the user never has to open it.

For each link in a message, TrueTick's server (never the user's phone):
1. Follows redirects step by step (unwraps bit.ly and similar) to find the real destination.
2. Downloads at most a small amount of the page as plain text. Nothing on the page is run:
   no JavaScript, no plugins, no downloads.
3. Reads the title and looks for forms asking for passwords, card numbers, CVV, OTP or PIN,
   and for pages claiming to be a famous brand on a website that isn't the brand's.
4. Checks how recently the website's name was registered (public RDAP records).

Safety: only http/https; private, local and internal network addresses are refused at every
hop; short timeouts; a size cap; and a limit on how many links and redirects we follow.
"""

import asyncio
import ipaddress
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from backend.app.checks.lookalike import BRANDS, is_official
from backend.app.config import get_settings
from backend.app.models import Finding

MAX_LINKS = 3
MAX_REDIRECTS = 5
MAX_BYTES = 300_000
TIMEOUT = httpx.Timeout(6.0, connect=4.0)
USER_AGENT = "Mozilla/5.0 (compatible; TrueTickLinkCheck/1.0; +https://github.com/moyososvbL/TrueTick)"

SENSITIVE_FIELDS = {
    "password": "a password", "passwd": "a password", "pin": "a PIN", "otp": "a one-time code (OTP)",
    "cvv": "a card security code (CVV)", "cvc": "a card security code (CVV)", "card": "a card number",
    "ssn": "a social security number", "bvn": "a BVN", "seed": "a crypto wallet recovery phrase",
    "mnemonic": "a crypto wallet recovery phrase",
}
TWO_PART_SUFFIXES = {"co.uk", "com.ng", "org.ng", "gov.ng", "com.au", "co.za", "com.br", "co.in", "co.jp", "com.gh", "co.ke"}


class UnsafeTarget(Exception):
    pass


async def _assert_public_host(host: str) -> None:
    """Refuse anything that resolves to a private/internal address (protects our server)."""
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror as e:
        raise UnsafeTarget("the website name doesn't exist") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeTarget("it points to a private network address")


class _PageReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.inputs: list[str] = []
        self.has_password = False
        self.text_parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "input":
            if a.get("type", "").lower() == "password":
                self.has_password = True
            self.inputs.append(" ".join([a.get("name", ""), a.get("id", ""), a.get("placeholder", ""),
                                         a.get("autocomplete", ""), a.get("aria-label", "")]).lower())

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and len(self.text_parts) < 400:
            self.text_parts.append(data)


def registrable_domain(host: str) -> str:
    parts = host.lower().strip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in TWO_PART_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


async def _domain_age_days(client: httpx.AsyncClient, host: str) -> int | None:
    try:
        r = await client.get(f"https://rdap.org/domain/{registrable_domain(host)}", follow_redirects=True)
        if r.status_code != 200:
            return None
        for ev in r.json().get("events", []):
            if ev.get("eventAction") == "registration" and ev.get("eventDate"):
                registered = datetime.fromisoformat(ev["eventDate"].replace("Z", "+00:00"))
                return (datetime.now(timezone.utc) - registered).days
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    return None


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[list[str], httpx.Response | None, bytes]:
    """Follow redirects manually so every hop is checked. Returns (chain of URLs, final response, body)."""
    chain = [url]
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise UnsafeTarget("it isn't a normal web address")
        await _assert_public_host(parsed.hostname)
        async with client.stream("GET", url, headers={"User-Agent": USER_AGENT}) as r:
            if r.is_redirect and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                chain.append(url)
                continue
            body = b""
            if "html" in r.headers.get("content-type", "").lower():
                async for chunk in r.aiter_bytes():
                    body += chunk
                    if len(body) >= MAX_BYTES:
                        break
            return chain, r, body
    raise UnsafeTarget("it redirects too many times")


async def inspect_url(url: str, transport: httpx.AsyncBaseTransport | None = None) -> list[Finding]:
    if not re.match(r"(?i)^https?://", url):
        url = "http://" + url
    findings: list[Finding] = []

    def add(sev, msg):
        findings.append(Finding(kind="link", severity=sev, message=msg))

    async with httpx.AsyncClient(timeout=TIMEOUT, transport=transport, follow_redirects=False) as client:
        try:
            chain, resp, body = await _fetch(client, url)
        except UnsafeTarget as e:
            add("medium", f"We couldn't safely open this link: {e}.")
            return findings
        except httpx.HTTPError:
            add("medium", "This link's website didn't respond. Scam sites often disappear quickly.")
            return findings

        first_host = (urlparse(chain[0]).hostname or "").lower()
        final_host = (urlparse(chain[-1]).hostname or "").lower()
        if len(chain) > 1 and registrable_domain(final_host) != registrable_domain(first_host):
            add("medium", f"This link secretly redirects to a different website: {final_host}.")
        if resp is not None and resp.headers.get("content-disposition", "").lower().startswith("attachment"):
            add("high", "This link immediately downloads a file instead of opening a page.")

        official = any(is_official(final_host, b) for b in BRANDS)
        asks: set[str] = set()
        claimed: list[str] = []
        title = ""
        if body and not official:
            reader = _PageReader()
            try:
                reader.feed(body.decode("utf-8", errors="replace"))
            except Exception:  # broken HTML shouldn't stop the check
                pass
            title = " ".join(reader.title.split())[:120]
            asks = {label for field, label in SENSITIVE_FIELDS.items()
                    if any(re.search(rf"\b{field}", inp) for inp in reader.inputs)}
            if reader.has_password:
                asks.add("a password")
            page_words = re.sub(r"[^a-z]", "", (title + " " + " ".join(reader.text_parts[:200])).lower())
            claimed = [name for brand, (name, _) in BRANDS.items() if brand in page_words]

        age = await _domain_age_days(client, final_host) if not official else None
        young = age is not None and age < 180

        if claimed and asks:
            add("high", f"The page looks like {claimed[0]} but is on {final_host}, and asks for "
                        f"{', '.join(sorted(asks))}. This is a typical fake login page.")
        elif claimed:
            add("medium", f"The page uses the name {claimed[0]} but isn't on {claimed[0]}'s website ({final_host}).")
        elif asks and (young or len(chain) > 1):
            add("medium", f"The page asks for {', '.join(sorted(asks))} on a website you didn't open yourself. "
                          "Only enter these on official apps or websites you type in yourself.")
        if title and (claimed or asks):
            add("medium", f'The link opens a page titled "{title}" on {final_host}.')

        if age is not None and age < 30:
            add("high", f"The website {registrable_domain(final_host)} was registered only "
                        f"{age} day{'s' if age != 1 else ''} ago. Scam sites are usually brand new.")
        elif young:
            add("medium", f"The website {registrable_domain(final_host)} is only about {max(1, age // 30)} months old.")
    return findings


async def inspect_links(urls: list[str], transport: httpx.AsyncBaseTransport | None = None) -> list[Finding]:
    """Inspect up to MAX_LINKS links in parallel. Returns [] when the feature is turned off."""
    if not get_settings().link_inspection or not urls:
        return []
    results = await asyncio.gather(*(inspect_url(u, transport) for u in urls[:MAX_LINKS]), return_exceptions=True)
    out: list[Finding] = []
    for r in results:
        if isinstance(r, list):
            out.extend(r)
    return out
