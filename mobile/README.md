# TrueTick Android app

A Capacitor shell that opens the live TrueTick site, with microphone and camera permissions
(Live Call Guard, voice notes, QR scanner) and the TrueTick icon.

GitHub builds it: Actions → "Build Android APK" → Run workflow. The APK appears under
Releases ("TrueTick Android, latest"). It needs the repository variable `HF_SPACE`
(or `TRUETICK_URL`) so the app knows the live https address.
