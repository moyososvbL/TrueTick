"""Dangerous file check: no AI needed.

Scammers send apps disguised as documents ("Wedding invitation", "Traffic fine.pdf.apk").
Installing one can let them read SMS codes, steal banking logins or control the phone.
We look at the name, the declared type AND the file's real contents, since names can lie.
"""

import io
import zipfile

from backend.app.models import Finding, Verdict

DANGEROUS_EXT = {
    "apk": "Android app", "xapk": "Android app", "apks": "Android app", "apkm": "Android app",
    "exe": "Windows program", "msi": "Windows installer", "scr": "Windows screensaver program",
    "bat": "Windows script", "cmd": "Windows script", "ps1": "PowerShell script",
    "vbs": "Windows script", "js": "script", "jar": "Java program",
    "dmg": "Mac installer", "pkg": "Mac installer", "ipa": "iPhone app",
}
MACRO_EXT = {"docm", "xlsm", "pptm"}
DANGEROUS_MIME = {
    "application/vnd.android.package-archive": "Android app",
    "application/x-msdownload": "Windows program",
    "application/x-msi": "Windows installer",
}


def _extensions(filename: str) -> list[str]:
    parts = (filename or "").lower().split(".")
    return parts[1:] if len(parts) > 1 else []


def _sniff(data: bytes) -> str | None:
    """Identify app files by their contents, whatever their name says."""
    if data[:2] == b"MZ":
        return "Windows program"
    if data[:4] == b"PK\x03\x04":
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return None
        if "AndroidManifest.xml" in names or any(n.endswith(".apk") for n in names):
            return "Android app"
        if any(n.startswith("Payload/") and n.endswith(".app/") for n in names):
            return "iPhone app"
    return None


def check_file(filename: str, mime: str, data: bytes) -> list[Finding]:
    findings: list[Finding] = []
    exts = _extensions(filename)
    last = exts[-1] if exts else ""

    kind = _sniff(data) or DANGEROUS_EXT.get(last) or DANGEROUS_MIME.get((mime or "").lower())
    if kind:
        findings.append(Finding(kind="file", severity="high",
                                message=f'"{filename or "This file"}" is actually an {kind}, not a document or photo.'
                                if kind[0] in "AEIOU" else
                                f'"{filename or "This file"}" is actually a {kind}, not a document or photo.'))
        if len(exts) >= 2 and exts[-2] in {"pdf", "jpg", "jpeg", "png", "doc", "docx", "mp4", "txt"}:
            findings.append(Finding(kind="file", severity="high",
                                    message=f"The name has a double ending (.{exts[-2]}.{last}) to trick you into thinking it's harmless."))
    elif last in MACRO_EXT:
        findings.append(Finding(kind="file", severity="medium",
                                message=f"This is an Office file with macros (.{last}). Macros can install harmful software."))
    return findings


def analyze_file(filename: str, mime: str, data: bytes) -> Verdict:
    findings = check_file(filename, mime, data)
    if any(f.severity == "high" for f in findings):
        return Verdict(
            risk="high", input_type="file", findings=findings,
            scam_type="Dangerous app disguised as a file",
            pattern_id="malicious_app_file",
            summary="This file is an app or program, not a normal document. Don't open or install it.",
            what_next="Installing it can let scammers read your SMS codes, steal your banking logins and control your phone.",
            advice=[
                "Don't open or install it, and delete it",
                "Never allow 'install from unknown sources' for a file someone sent you",
                "If you already installed it, disconnect from the internet and contact your bank",
            ],
        )
    if findings:
        return Verdict(
            risk="medium", input_type="file", findings=findings, scam_type="Risky document",
            summary="This document can run hidden code if you allow it.",
            advice=["Don't click 'Enable content' or 'Enable macros'", "Ask the sender through another channel if they really sent it"],
        )
    return Verdict(
        risk="unknown", input_type="file",
        summary="We didn't find a dangerous file type. We can't check what's written inside this kind of file yet.",
        advice=["If it asks you to log in, pay or 'enable content', stop and verify the sender",
                 "You can paste the text or send a screenshot of it to check the message itself"],
    )
