"""Instant (non-AI) danger signals for Live Call Guard.

Run on every few seconds of transcript, so the user gets a warning the moment a caller asks for
something no legitimate organisation would. Patterns allow for common mishearings
("items card" for "iTunes card", "oh tee pee" for "OTP").
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LiveAlert:
    id: str
    severity: str  # "stop" (hang up now) or "warn"
    title: str
    advice: str


RULES: list[tuple[re.Pattern, LiveAlert]] = [
    (re.compile(r"\b(o\.?\s?t\.?\s?p|oh tee pee|one[- ]time (pass)?code|verification code|6[- ]digit code|"
                r"code (we|i) (just )?sent|read (me )?the code|pin|cvv|cvc|security code|password)\b", re.I),
     LiveAlert("secret_code", "stop", "They're asking for a code, PIN or password",
               "No bank, company or government ever asks for these. Hang up now.")),
    (re.compile(r"\b(gift ?cards?|itunes|i tunes|items card|apple card|google play|steam (card|guard)|amazon card|"
                r"scratch (the|it)|card code)\b", re.I),
     LiveAlert("gift_card", "stop", "They want payment in gift cards",
               "Anyone asking for gift cards is a scammer. Hang up.")),
    (re.compile(r"\b(safe account|secure account|holding account|move (all )?(your|the) (money|funds|savings)|"
                r"transfer (all )?(your|the) (money|funds|balance))\b", re.I),
     LiveAlert("safe_account", "stop", "They want you to move your money to a 'safe' account",
               "Real banks never do this. Hang up and call the number on the back of your card.")),
    (re.compile(r"\b(any ?desk|team ?viewer|remote access|share (your )?screen|install (this|an|the) app|quick ?support)\b", re.I),
     LiveAlert("remote_access", "stop", "They want control of your phone or computer",
               "Don't install anything. Hang up.")),
    (re.compile(r"\b(bit ?coin|btc|crypto|usdt|tether|bitcoin atm|crypto atm|wallet address)\b", re.I),
     LiveAlert("crypto", "stop", "They want payment in crypto",
               "Crypto payments can't be reversed. Real organisations don't demand them. Hang up.")),
    (re.compile(r"\b(don'?t tell (anyone|anybody|your|the)|keep (this|it) (secret|between us|confidential)|"
                r"don'?t hang up|stay on the line|don'?t call (anyone|the bank|your))\b", re.I),
     LiveAlert("secrecy", "warn", "They're telling you to keep it secret or stay on the line",
               "Scammers isolate you so no one can warn you. You can hang up and call someone you trust.")),
    (re.compile(r"\b(warrant|arrest(ed)?|police (will|are)|court case|deport(ed|ation)?|jail|fine (must|has to) be paid)\b", re.I),
     LiveAlert("threat", "warn", "They're threatening arrest or legal trouble",
               "Police and courts don't demand payment over the phone. Hang up and check with the agency directly.")),
    (re.compile(r"\b(western union|money ?gram|wire (the|it|money)|bank transfer (now|today|immediately))\b", re.I),
     LiveAlert("wire", "warn", "They're pushing an urgent transfer",
               "Pause. Verify who this is through a number you already know before sending anything.")),
]


def scan(transcript: str) -> list[LiveAlert]:
    """All alerts triggered anywhere in the transcript so far, most serious first, no duplicates."""
    hits = {alert.id: alert for pattern, alert in RULES if pattern.search(transcript or "")}
    return sorted(hits.values(), key=lambda a: a.severity != "stop")
