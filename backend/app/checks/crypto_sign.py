"""Before you sign: explains crypto wallet requests in plain words, without AI.

Wallet-draining scams ("claim your airdrop", "verify your wallet", fake exchange refunds) don't
steal your password. They get you to sign something your wallet shows as unreadable code.
One signature can let a stranger take all of a token, all your NFTs, or control the whole wallet.

This decodes the common requests people are tricked into signing:
- token approvals (approve, increaseAllowance, Permit2 approve), including "unlimited" amounts
- NFT "approve all" (setApprovalForAll)
- direct transfers (transfer, transferFrom, safeTransferFrom)
- gasless signatures: EIP-2612 Permit, Permit2 PermitSingle / PermitBatch / PermitTransferFrom
- NFT marketplace listings (Seaport orders) that sell for almost nothing
- EIP-7702 authorizations that hand control of the whole wallet to a contract
- "blind" signatures of a bare 32-byte hash
It also catches recovery phrases and private keys pasted by mistake.
"""

import json
import re
from pathlib import Path

from backend.app.models import Finding

MAX_UINT = 2**256 - 1
UNLIMITED_FROM = 2**96  # no real approval needs more than this; drainers use the maximum

# Well-known tokens: address (lowercase) -> (symbol, decimals)
TOKENS = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6),
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6),
    "0x6b175474e89094c44da98b954eedeac495271d0f": ("DAI", 18),
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("WETH", 18),
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": ("WBTC", 8),
    "0x55d398326f99059ff775485246999027b3197955": ("USDT (BNB Chain)", 18),
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": ("USDC (BNB Chain)", 18),
}
KNOWN_SPENDERS = {
    "0x000000000022d473030f116ddee9f6b43ac78ba3": "Uniswap Permit2",
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap Universal Router",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch router",
}

SELECTORS = {
    "095ea7b3": "approve",
    "39509351": "increaseAllowance",
    "a22cb465": "setApprovalForAll",
    "a9059cbb": "transfer",
    "23b872dd": "transferFrom",
    "42842e0e": "safeTransferFrom",
    "b88d4fde": "safeTransferFrom",
    "d505accf": "permit",
    "87517c45": "permit2Approve",
}

_HEX = re.compile(r"0x[0-9a-fA-F]{8,}")
_ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _short(addr: str) -> str:
    addr = str(addr)
    return addr[:6] + "…" + addr[-4:] if _ADDR.match(addr) else addr


def _who(addr: str) -> str:
    name = KNOWN_SPENDERS.get(str(addr).lower())
    return f"{name} ({_short(addr)})" if name else f"the address {_short(addr)}"


def _token(addr: str | None, fallback: str = "this token") -> tuple[str, int | None]:
    if addr and str(addr).lower() in TOKENS:
        return TOKENS[str(addr).lower()]
    return (f"{fallback} ({_short(addr)})" if addr else fallback), None


def _amount(value: int, decimals: int | None, symbol: str) -> str:
    if value >= UNLIMITED_FROM:
        return f"ALL your {symbol} (no limit)"
    if decimals is None:
        return f"{value:,} units of {symbol}"
    whole = value / 10**decimals
    return f"{whole:,.2f} {symbol}" if whole < 1e12 else f"ALL your {symbol} (no limit)"


def _int(v) -> int:
    try:
        if isinstance(v, str) and v.lower().startswith("0x"):
            return int(v, 16)
        return int(v)
    except (TypeError, ValueError):
        return 0


def _f(sev: str, msg: str) -> Finding:
    return Finding(kind="crypto", severity=sev, message=msg)


# ---------------- raw transaction data ----------------

def decode_calldata(data: str, to: str | None = None) -> list[Finding]:
    data = data.lower().removeprefix("0x")
    if len(data) < 8:
        return []
    name = SELECTORS.get(data[:8])
    if not name:
        return []
    words = [data[8 + i * 64: 8 + (i + 1) * 64] for i in range((len(data) - 8) // 64)]
    addr = lambda w: "0x" + w[-40:]  # noqa: E731
    num = lambda w: int(w, 16) if w else 0  # noqa: E731
    symbol, dec = _token(to)

    if name in ("approve", "increaseAllowance") and len(words) >= 2:
        value = num(words[1])
        sev = "high" if value >= UNLIMITED_FROM else "medium"
        return [_f(sev, f"You'd be signing an approval: it lets {_who(addr(words[0]))} take "
                        f"{_amount(value, dec, symbol)} from your wallet at any time, without asking again. "
                        "Wallet-draining scams work exactly like this.")]
    if name == "setApprovalForAll" and len(words) >= 2 and num(words[1]) == 1:
        return [_f("high", f"You'd be signing \"approve all\": it lets {_who(addr(words[0]))} take EVERY NFT "
                           "in this collection from your wallet. Real sites almost never need this.")]
    if name == "transfer" and len(words) >= 2:
        return [_f("medium", f"You'd be sending {_amount(num(words[1]), dec, symbol)} to {_short(addr(words[0]))}. "
                             "Check this is exactly what you meant to do.")]
    if name in ("transferFrom", "safeTransferFrom") and len(words) >= 3:
        return [_f("medium", f"This moves tokens from {_short(addr(words[0]))} to {_short(addr(words[1]))}. "
                             "If you're being asked to 'verify' or 'claim' something, this is a transfer, not a check.")]
    if name == "permit" and len(words) >= 3:
        return [_f("high", f"This signs a permit that lets {_who(addr(words[1]))} take "
                           f"{_amount(num(words[2]), dec, symbol)}.")]
    if name == "permit2Approve" and len(words) >= 3:
        sym, d = _token(addr(words[0]))
        return [_f("high", f"This gives {_who(addr(words[1]))} permission to take {_amount(num(words[2]), d, sym)}.")]
    return []


# ---------------- signatures (eth_signTypedData) ----------------

def _deadline_note(value) -> str:
    v = _int(value)
    if v >= 2**40:
        return " The permission never expires."
    return ""


def decode_typed_data(td: dict) -> list[Finding]:
    primary = str(td.get("primaryType", ""))
    msg = td.get("message") or {}
    domain = td.get("domain") or {}
    out: list[Finding] = []
    gasless = (" It's only a signature, so it costs no gas and your wallet may not show it as a payment, "
               "but once signed it can be used to empty the wallet.")

    if primary == "Permit" and "spender" in msg:
        sym, dec = _token(domain.get("verifyingContract"), domain.get("name") or "this token")
        out.append(_f("high", f"You'd be signing a permit that lets {_who(msg['spender'])} take "
                              f"{_amount(_int(msg.get('value')), dec, sym)}." + _deadline_note(msg.get("deadline")) + gasless))
    elif primary in ("PermitSingle", "PermitBatch"):
        details = msg.get("details")
        items = details if isinstance(details, list) else [details or {}]
        for d in items[:5]:
            sym, dec = _token(d.get("token"))
            out.append(_f("high", f"You'd be signing a Permit2 approval that lets {_who(msg.get('spender'))} take "
                                  f"{_amount(_int(d.get('amount')), dec, sym)}." + _deadline_note(d.get("expiration")) + gasless))
    elif primary.startswith("Permit") and "TransferFrom" in primary:
        permitted = msg.get("permitted")
        items = permitted if isinstance(permitted, list) else [permitted or {}]
        for p in items[:5]:
            sym, dec = _token(p.get("token"))
            out.append(_f("high", f"You'd be signing a transfer: {_who(msg.get('spender'))} can move "
                                  f"{_amount(_int(p.get('amount')), dec, sym)} out of your wallet right away." + gasless))
    elif primary in ("OrderComponents", "Order") and "offer" in msg:
        offerer = str(msg.get("offerer", "")).lower()
        to_you = sum(_int(c.get("startAmount", c.get("amount"))) for c in msg.get("consideration") or []
                     if str(c.get("recipient", "")).lower() == offerer)
        if msg.get("offer") and to_you == 0:
            out.append(_f("high", "You'd be signing a marketplace listing that gives away your items for nothing: "
                                  "none of the payment goes to you. This is a common NFT-draining trick."))
        elif msg.get("offer"):
            out.append(_f("medium", "You'd be signing a marketplace listing. Check the price is what you expect."))
    elif any(k in msg for k in ("spender", "operator", "delegate")):
        who = msg.get("spender") or msg.get("operator") or msg.get("delegate")
        out.append(_f("medium", f"This signature gives {_who(who)} some power over your wallet ({primary or 'unknown request'})."))
    return out


def decode_authorization(obj: dict) -> list[Finding]:
    """EIP-7702: an account authorizes a contract to run as its own code."""
    auths = obj.get("authorizationList") or obj.get("authorization_list")
    if auths is None and {"chainId", "address", "nonce"} <= set(obj) and "data" not in obj and "to" not in obj:
        auths = [obj]
    if not auths:
        return []
    target = _short(str((auths[0] or {}).get("address", "")))
    return [_f("high", f"This hands control of your WHOLE wallet to the contract {target} (an EIP-7702 delegation). "
                       "It can then move every coin and token you hold, including ones you receive later. "
                       "Only sign this for a wallet upgrade you started yourself in your own wallet app.")]


# ---------------- entry point ----------------

def _json_objects(text: str) -> list[dict]:
    found = []
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return [obj]
        if isinstance(obj, list):
            return [o for o in obj if isinstance(o, dict)]
    except (ValueError, TypeError):
        pass
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict):
                found.append(obj)
        except (ValueError, TypeError):
            pass
    return found


# The official BIP-39 English word list (2048 words) used by almost every wallet's recovery phrase.
# Source: bitcoin/bips BIP-0039, via python-mnemonic (MIT).
_BIP39 = set((Path(__file__).with_name("bip39_english.txt")).read_text().split())


def _looks_like_recovery_phrase(text: str) -> bool:
    """12+ wallet words in a row, even inside a longer message."""
    run = 0
    for word in re.findall(r"[A-Za-z]+", text):
        run = run + 1 if word.lower() in _BIP39 else 0
        if run >= 12:
            return True
    return False


def check_signing_request(text: str) -> list[Finding]:
    if not text:
        return []
    findings: list[Finding] = []
    for obj in _json_objects(text):
        params = obj.get("params")
        if isinstance(params, list):  # a raw wallet request {"method": ..., "params": [...]}
            for p in params:
                if isinstance(p, str) and p.strip().startswith("{"):
                    try:
                        p = json.loads(p)
                    except ValueError:
                        continue
                if isinstance(p, dict):
                    findings += decode_typed_data(p) if "primaryType" in p else decode_authorization(p)
                    if p.get("data"):
                        findings += decode_calldata(str(p["data"]), p.get("to"))
        findings += decode_authorization(obj)
        if "primaryType" in obj:
            findings += decode_typed_data(obj)
        if obj.get("data") or obj.get("input"):
            findings += decode_calldata(str(obj.get("data") or obj.get("input")), obj.get("to"))
    if not findings:
        for h in sorted(_HEX.findall(text), key=len, reverse=True)[:3]:
            findings += decode_calldata(h)
            if findings:
                break
    stripped = text.strip()
    bare_hash = re.search(r"(?<![0-9a-fA-Fx])0x[0-9a-fA-F]{64}(?![0-9a-fA-F])", text)
    if re.fullmatch(r"0x[0-9a-fA-F]{64}", stripped) or (bare_hash and re.search(r"(?i)\bsign", text)):
        findings.append(_f("high", "You're being asked to sign a bare code (a 32-byte hash) that nobody can read. "
                                   "This is called blind signing: it can approve anything, including emptying your wallet."))
    elif re.fullmatch(r"(0x)?[0-9a-fA-F]{64}", stripped):
        findings.append(_f("high", "This looks like a wallet private key. Anyone who has it owns your wallet. "
                                   "Never share or type it into a website, and move your funds if someone else has seen it."))
    if _looks_like_recovery_phrase(text):
        findings.append(_f("high", "This looks like a wallet recovery phrase. Anyone who has these words owns your wallet. "
                                   "No real exchange, wallet or support agent will ever ask for it."))
    seen, unique = set(), []
    for f in findings:
        if f.message not in seen:
            seen.add(f.message)
            unique.append(f)
    return unique
