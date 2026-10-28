"""QR codes: read what's hidden inside without opening it. No AI needed for the decoding."""

import cv2
import numpy as np


def decode_qr_codes(image_bytes: bytes) -> list[str]:
    """Returns the text/links inside every QR code found in the image."""
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []
    detector = cv2.QRCodeDetector()
    results: list[str] = []

    for candidate in (img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)):
        try:
            ok, decoded, _, _ = detector.detectAndDecodeMulti(candidate)
        except cv2.error:
            ok, decoded = False, []
        if ok:
            results.extend(d for d in decoded if d)
        if not results:
            data, _, _ = detector.detectAndDecode(candidate)
            if data:
                results.append(data)
        if results:
            break
    return list(dict.fromkeys(results))


# ---------- What kind of thing is inside? (explained in plain words) ----------
import re  # noqa: E402

from backend.app.models import Finding  # noqa: E402

_WIFI = re.compile(r"^WIFI:", re.I)
_CRYPTO = re.compile(r"^(bitcoin|ethereum|litecoin|tron|usdt|solana|bnb):", re.I)
_PAY = re.compile(r"^(upi|paypal|venmo|cashapp|payto)://|^https?://(pay|paypal\.me|cash\.app)", re.I)


def _wifi_field(content: str, key: str) -> str:
    m = re.search(rf"(?:^WIFI:|;){key}:((?:\\.|[^;])*)", content, re.I)
    return m.group(1).replace("\\", "") if m else ""


def describe_qr(content: str) -> list[Finding]:
    """Plain-language facts about a QR code's content (what it will do if you open it)."""
    c = content.strip()
    low = c.lower()
    if _WIFI.match(c):
        name = _wifi_field(c, "S") or "an unnamed network"
        open_net = _wifi_field(c, "T").lower() in ("", "nopass")
        msg = f"This QR code connects your phone to a Wi-Fi network called \"{name}\"."
        if open_net:
            msg += " It has no password, so others on it may see what you do."
        return [Finding(kind="qr", severity="medium", message=msg)]
    if _CRYPTO.match(c):
        return [Finding(kind="qr", severity="high",
                        message="This QR code starts a crypto payment. Crypto payments can't be reversed.")]
    if _PAY.match(c):
        return [Finding(kind="qr", severity="medium",
                        message="This QR code opens a payment. Check who you're paying before you confirm.")]
    if low.startswith(("tel:", "sms:", "smsto:")):
        number = re.sub(r"^(tel|sms|smsto):", "", c, flags=re.I).split(":")[0]
        what = "call" if low.startswith("tel:") else "send a text to"
        return [Finding(kind="qr", severity="medium", message=f"This QR code makes your phone {what} {number}.")]
    if low.startswith(("market://", "itms-apps://")) or re.search(r"\.apk(\?|$)", low):
        return [Finding(kind="qr", severity="high",
                        message="This QR code installs an app. Only install apps from the official app store.")]
    if low.startswith(("http://", "https://")) or re.match(r"^[\w-]+(\.[\w-]+)+(/|$)", low):
        return [Finding(kind="qr", severity="medium", message=f"This QR code opens: {c}")]
    return [Finding(kind="qr", severity="medium", message=f"This QR code contains text: {c[:200]}")]
