from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

VERDICT = {"risk": "high", "scam_type": "Fake bank alert", "summary": "Phishing link.",
           "extracted_text": "Verify at http://zenora-verify.top", "findings": [
               {"kind": "link", "severity": "high", "message": "Link ends in .top"}]}


def test_nigeria_links_and_summary():
    r = client.post("/api/report", json={"verdict": VERDICT, "country": "NG", "what_happened": "Got an SMS"}).json()
    urls = [l["url"] for l in r["options"]["links"]]
    assert "https://nccc.npf.gov.ng/" in urls and "https://www.efcc.gov.ng/" in urls
    s = r["summary"]
    assert "HIGH (Fake bank alert)" in s and "Got an SMS" in s and "zenora-verify.top" in s and "Link ends in .top" in s


def test_unknown_country_gets_default():
    r = client.post("/api/report", json={"verdict": VERDICT, "country": "ZZ"}).json()
    assert r["options"]["country"] == "Anywhere" and "local police" in r["options"]["note"]


def test_threat_adds_image_removal_help():
    v = dict(VERDICT, is_threat=True)
    urls = [l["url"] for l in client.post("/api/report", json={"verdict": v, "country": "US"}).json()["options"]["links"]]
    assert urls[0] == "https://stopncii.org/" and "https://takeitdown.ncmec.org/" in urls
    assert "https://reportfraud.ftc.gov/" in urls


def test_country_list():
    codes = {c["code"] for c in client.get("/api/report/countries").json()}
    assert {"NG", "US", "GB"} <= codes
