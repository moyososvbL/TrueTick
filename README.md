# TrueTick

AI scam checker: share any suspicious message, screenshot, voice note or QR code and get a clear verdict, built with Meta's Muse Spark and SAM 3.1.

Built for the Meta Global AI Developer Hackathon (Indie Developer Track, "Build for Your World").

> 🚧 In progress (Oct 26 – Nov 4, 2026).

## Project structure

```
truetick/
├── backend/app/     Python FastAPI backend (API + AI analysis)
├── frontend/        Web app (installable on phones)
├── tests/           Automated tests
├── samples/         Anonymized test examples (samples/private/ is never committed)
├── .env.example     Settings template (copy to .env)
└── requirements.txt Python packages
```

## Run locally (Windows)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

On Mac/Linux use `source .venv/bin/activate` and `cp .env.example .env`.

Then fill in your Meta API key in `.env`.
