from backend.app.checks.links import check_url, extract_urls, run_checks
from backend.app.checks.lookalike import check_text_lookalikes, normalize


def _msgs(findings):
    return " | ".join(f.message for f in findings)


def test_normalize_lookalikes():
    assert normalize("rnicrosoft") == "microsoft"
    assert normalize("PayPa1") == "paypal"
    assert normalize("аpple") == "apple"  # Cyrillic а


def test_real_sites_are_clean():
    assert check_url("https://www.paypal.com/signin") == []
    assert check_url("https://login.microsoftonline.com") == []
    assert check_url("https://www.amazon.co.uk/orders") == []


def test_lookalike_domain():
    assert "lookalike letters to pretend to be Microsoft" in _msgs(check_url("http://rnicrosoft-secure-login.top/verify"))


def test_brand_on_fake_domain():
    m = _msgs(check_url("https://paypal-account-verify.top/login"))
    assert "NOT PayPal's real website" in m and ".top" in m


def test_at_sign_trick_and_ip_and_shortener():
    assert "'@' trick" in _msgs(check_url("https://paypal.com@evil.example/login"))
    assert "number address" in _msgs(check_url("http://192.168.4.20/bank"))
    assert "shortened" in _msgs(check_url("https://bit.ly/3xYz"))


def test_punycode_domain():
    assert "Apple" in _msgs(check_url("https://xn--pple-43d.com/id"))  # аpple.com with Cyrillic а


def test_text_lookalikes():
    assert check_text_lookalikes("Message from Rnicrosoft Support team")
    assert check_text_lookalikes("Your Microsoft account is fine") == []
    assert check_text_lookalikes("a modern design") == []


def test_extract_and_run_checks():
    text = "Click www.paypal-verify.top/login now or bit.ly/abc. Normal words here."
    assert len(extract_urls(text)) == 2
    assert run_checks("Are we still meeting for lunch on Friday?") == []


def test_link_to_apk_download():
    assert "Android app file" in _msgs(check_url("http://quickloan-ng.app/QuickLoan.apk"))
