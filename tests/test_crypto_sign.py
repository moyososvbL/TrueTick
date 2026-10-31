"""Before you sign: wallet requests decoded without AI."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.ai import meta_client
from backend.app.checks.crypto_sign import check_signing_request
from backend.app.main import app

USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
THIEF = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
MAX = "f" * 64


def one(text):
    found = check_signing_request(text)
    assert found, text
    return found[0]


def test_unlimited_usdt_approval():
    f = one(json.dumps({"to": USDT, "data": "0x095ea7b3" + "0" * 24 + THIEF + MAX}))
    assert f.severity == "high" and "ALL your USDT" in f.message and "0xa1b2" in f.message


def test_small_approval_is_medium():
    f = one("0x095ea7b3" + "0" * 24 + THIEF + hex(100_000_000)[2:].zfill(64))
    assert f.severity == "medium"


def test_approve_all_nfts():
    f = one("0xa22cb465" + "0" * 24 + THIEF + "1".zfill(64))
    assert f.severity == "high" and "EVERY NFT" in f.message


def test_permit2_signature():
    td = {"primaryType": "PermitSingle", "domain": {"name": "Permit2"},
          "message": {"details": {"token": USDT, "amount": str(2**160 - 1), "expiration": str(2**48 - 1)},
                      "spender": "0x" + THIEF}}
    f = one(json.dumps(td))
    assert f.severity == "high" and "ALL your USDT" in f.message and "never expires" in f.message


def test_eip2612_permit_inside_wallet_request():
    td = {"primaryType": "Permit", "domain": {"name": "USD Coin", "verifyingContract": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"},
          "message": {"owner": "0x" + "1" * 40, "spender": "0x" + THIEF, "value": str(2**256 - 1), "deadline": str(2**256 - 1)}}
    req = {"method": "eth_signTypedData_v4", "params": ["0x" + "1" * 40, json.dumps(td)]}
    f = one(json.dumps(req))
    assert f.severity == "high" and "ALL your USDC" in f.message


def test_eip7702_delegation():
    f = one(json.dumps({"chainId": 1, "address": "0x" + THIEF, "nonce": 7}))
    assert f.severity == "high" and "WHOLE wallet" in f.message


def test_free_nft_listing():
    order = {"primaryType": "OrderComponents", "message": {
        "offerer": "0x" + "1" * 40, "offer": [{"token": "0xabc", "identifierOrCriteria": "7"}],
        "consideration": [{"recipient": "0x" + "2" * 40, "startAmount": "1"}]}}
    assert one(json.dumps(order)).severity == "high"


@pytest.mark.parametrize("text", [
    "0x" + "ab" * 32,
    "apple river stone cloud orange paper lion music forest window tiger glass",
])
def test_blind_hash_and_recovery_phrase(text):
    assert one(text).severity == "high"


@pytest.mark.parametrize("text", [
    "Hi mum, I'll be home by 7. Can you buy bread?",
    "Your verification code is 482913. Don't share it.",
    "Send the invoice to accounts@company.com before Friday",
    "Tx hash 0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060 confirmed",
])
def test_normal_text_is_not_flagged(text):
    assert check_signing_request(text) == []


def test_fooled_ai_still_warns(monkeypatch):
    async def fake_chat(messages, **kwargs):
        return json.dumps({"risk": "low", "summary": "Looks fine."})
    monkeypatch.setattr(meta_client, "chat", fake_chat)
    msg = ("Binance compensation: sign this to receive your refund after the hack. "
           + json.dumps({"to": USDT, "data": "0x095ea7b3" + "0" * 24 + THIEF + MAX}))
    v = TestClient(app).post("/api/check/text", json={"text": msg}).json()
    assert v["risk"] == "high" and any(f["kind"] == "crypto" for f in v["findings"])
