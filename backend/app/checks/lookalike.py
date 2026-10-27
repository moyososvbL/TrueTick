"""Detects text pretending to be a famous brand using lookalike letters.

Scammers write "rnicrosoft" (r+n looks like m), "paypa1" (1 looks like l), or swap in
letters from other alphabets that look identical ("аpple" with a Cyrillic а).
We turn lookalikes back into normal letters and compare with real brand names.
"""

import re
import unicodedata

# brand key -> (display name, official domains)
BRANDS: dict[str, tuple[str, list[str]]] = {
    "microsoft": ("Microsoft", ["microsoft.com", "live.com", "office.com", "outlook.com", "microsoftonline.com"]),
    "paypal": ("PayPal", ["paypal.com", "paypal.me"]),
    "amazon": ("Amazon", ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.in", "amazon.ca", "amazon.com.au"]),
    "apple": ("Apple", ["apple.com", "icloud.com"]),
    "netflix": ("Netflix", ["netflix.com"]),
    "google": ("Google", ["google.com", "youtube.com", "gmail.com"]),
    "facebook": ("Facebook", ["facebook.com", "fb.com", "meta.com"]),
    "instagram": ("Instagram", ["instagram.com"]),
    "whatsapp": ("WhatsApp", ["whatsapp.com", "wa.me"]),
    "linkedin": ("LinkedIn", ["linkedin.com"]),
    "dhl": ("DHL", ["dhl.com"]),
    "fedex": ("FedEx", ["fedex.com"]),
    "binance": ("Binance", ["binance.com"]),
    "coinbase": ("Coinbase", ["coinbase.com"]),
    "westernunion": ("Western Union", ["westernunion.com"]),
}

# Single characters that look like Latin letters.
_CHAR_MAP = {
    # Cyrillic
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",
    "ј": "j", "ѕ": "s", "ԁ": "d", "ӏ": "l", "к": "k", "м": "m", "т": "t", "в": "b", "н": "h",
    # Greek
    "ο": "o", "α": "a", "ν": "v", "ι": "i", "ρ": "p", "κ": "k", "τ": "t", "ε": "e",
    # Digits and symbols
    "0": "o", "1": "l", "3": "e", "5": "s", "$": "s", "@": "a", "!": "i", "|": "l",
}
# Letter pairs that look like one letter.
_PAIRS = [("rn", "m"), ("vv", "w")]


def decode_host(host: str) -> str:
    """Turns punycode (xn--...) into the characters a person would actually see."""
    try:
        return host.encode("ascii").decode("idna") if "xn--" in host else host
    except UnicodeError:
        return host


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", decode_host(text)).lower()
    text = "".join(_CHAR_MAP.get(ch, ch) for ch in text)
    for pair, single in _PAIRS:
        text = text.replace(pair, single)
    return text


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text)


def is_official(host: str, brand: str) -> bool:
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in BRANDS[brand][1])


def brands_imitated_by_host(host: str) -> list[tuple[str, bool]]:
    """Returns (brand, used_lookalike_letters) for each brand a host pretends to be."""
    raw = _compact(host.lower())
    norm = _compact(normalize(host))
    hits = []
    for brand in BRANDS:
        if brand in norm and not is_official(host, brand):
            hits.append((brand, brand not in raw))
    return hits


_WORD_RE = re.compile(r"[^\s,;:()\[\]{}\"'<>]{5,}")


def check_text_lookalikes(text: str) -> list[str]:
    """Finds words like 'rnicrosoft' or 'PayPa1' that imitate a brand with lookalike letters."""
    found = []
    for word in _WORD_RE.findall(text):
        raw = _compact(word.lower())
        norm = _compact(normalize(word))
        for brand, (name, _) in BRANDS.items():
            if len(brand) >= 5 and brand in norm and brand not in raw:
                found.append(f'"{word}" uses lookalike letters to imitate {name}.')
    return list(dict.fromkeys(found))
