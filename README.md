# TrueTick

**Not sure it's real? Check it first.**

TrueTick is a scam checker for everyone. Share a suspicious message, screenshot, voice note, QR code or link, or let it listen to a phone call on speaker, and it tells you in plain words how risky it is, why, what usually happens next, and exactly what to do.

Built for the **Meta Global AI Developer Hackathon** (Indie Developer Track, "Build for Your World").

## Why

Scams are getting harder to spot. The FBI's Internet Crime Complaint Center (IC3) 2025 report counts **$20.9 billion** lost to internet crime from over 1 million complaints. People over 60 lost **$7.7 billion**, up 59% in one year. Investment fraud, business email compromise, tech support scams, romance scams and government impersonation lead the losses, and AI voice clones and deepfakes are growing fast.
Source: [FBI IC3 2025 Internet Crime Report](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf)

The idea came from a real call: a "bank officer" who already knew my name and account details asked for a code. Knowing your details doesn't make someone your bank. TrueTick exists to say that out loud, at the moment it matters.

## What it does

| Feature | What happens |
|---|---|
| **Message & link check** | Paste any text, email or link. Muse Spark names the scam, explains why, says what usually happens next and what to do. |
| **Screenshot check** | Upload screenshots of chats, posts, emails or receipts. Muse Spark reads them and checks the text. |
| **Whole-chat check** | Upload up to 8 screenshots of one conversation. TrueTick builds a timeline, names the scam stage (e.g. "asking for money") and points out where their story contradicts itself. |
| **Voice notes** | Muse Voice Transcribe turns the recording into words (fixing common mishearings like "items card" → iTunes card), then it's checked like a message. |
| **Live Call Guard** | Put a call on speaker next to a second device. Every few seconds the call is transcribed; if the caller asks for a code, PIN, gift card, crypto, a "safe account" transfer or remote access, a warning appears instantly, with a running verdict from Muse Spark. |
| **"We visited the website for you"** | Suspicious links are opened in a sealed, throwaway browser on our side. Muse Spark looks at the page and says which brand it's dressed up as, then TrueTick compares that with the real web address. |
| **QR scanner** | Scan with the camera or a photo. The code is read on your device without being opened; Wi-Fi, payment, crypto, app-install and web QR codes are each checked. |
| **Non-AI checks** | Lookalike letters (`rnicrosoft` → Microsoft), risky domain endings, link shorteners, `@` tricks, brand-new websites, redirects, dangerous files (`.apk`, double extensions). These still work if the AI is unreachable. |
| **Family warning card** | Muse Image draws a warning card about the scam to share with family. |
| **Report a scam** | Shows the official place to report it in your country, with a ready-to-copy summary. |
| **Safety tips** | Short rules anyone can remember: codes are secret, gift cards are for gifts, love doesn't ask for money. |

## Meta models used

| Model | Job in TrueTick |
|---|---|
| **Muse Spark 1.3** (`muse-spark-1.3`) | Reads text, screenshots and whole chats; judges live calls; reads visited web pages; writes every verdict |
| **Muse Voice Transcribe 1.0** | Voice notes and Live Call Guard |
| **Muse Image 1.0** | Family warning cards |

TrueTick never uses the `-contributor` models, because people send private messages.

## Privacy

- No account, no sign-up.
- Messages, images and recordings are checked and then thrown away. They are never stored or logged.
- QR codes are decoded on the device.
- Community reports store only a hashed link or number, never message content.
- All demo brands (e.g. "Zenora Bank") are fictional.

## Run it

You need Python 3.11+ and a Meta Model API key from [dev.meta.ai](https://dev.meta.ai).

**Windows**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**Mac / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your key in `.env` (`META_API_KEY=...`), then start it:

```bash
python -m uvicorn backend.app.main:app --port 8000
```

Open http://127.0.0.1:8000. Check your key at http://127.0.0.1:8000/api/health/models: each Muse Spark version should show `200`.

For the website visit feature, also run `pip install playwright` and `python -m playwright install chromium`.

**Use it on your phone.** Phones need an https address for the camera and microphone. With [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/):

```bash
cloudflared tunnel --url http://localhost:8000
```

Open the `https://….trycloudflare.com` address it prints, then use **Add to Home Screen**.

**Docker:** `docker build -t truetick .` then `docker run -p 7860:7860 -e META_API_KEY=... truetick`.

**Android app:** `mobile/` contains a Capacitor shell that opens the live site; the GitHub Action "Build Android APK" builds it once the repository variable `TRUETICK_URL` is set.

## Tests

```bash
python -m pytest
```

88 automated tests cover the analyzers, link and lookalike checks, QR handling, Live Call Guard rules, the Meta client and the API.

Accuracy scripts (need a key): `python scripts/evaluate.py` runs the labelled messages in `samples/test_cases.csv`; `python scripts/evaluate_links.py` checks live phishing links from the public OpenPhish feed. `samples/test_images/` holds fictional test screenshots.

## Project structure

```
truetick/
├── backend/app/
│   ├── main.py           API routes
│   ├── ai/               meta_client.py (the only file that calls Meta), prompts
│   ├── analyzers/        text, image, conversation, QR, files
│   ├── checks/           link checks, lookalike letters, sealed website visit
│   ├── live/             Live Call Guard (rules + routes)
│   ├── intel/            hashed community reports
│   └── reporting/        official reporting places by country
├── frontend/             web app (responsive, light and dark mode)
├── mobile/               Android app shell (Capacitor)
├── scripts/              live-API checks and evaluation
├── samples/              fictional test messages and images
└── tests/
```

## Built by

Moyosoreoluwa Oganla, product designer and software engineer, Lagos.
