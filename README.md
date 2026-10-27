# TrueTick

AI scam checker: share any suspicious message, screenshot, voice note or QR code and get a clear verdict, built with Meta's Muse Spark and SAM 3.1.

Built for the Meta Global AI Developer Hackathon (Indie Developer Track, "Build for Your World").

> 🚧 In progress (Oct 26 – Nov 4, 2026).

## Why TrueTick

The FBI's Internet Crime Complaint Center (IC3) 2025 report shows how big the problem is:

- **$20.9 billion** lost to internet crime in 2025, from **over 1 million** complaints (losses up 26%).
- People **over 60** lost the most: **$7.7 billion**, up 59% in a year, averaging **$38,500** per victim.
- Largest losses: investment fraud ($8.6B), business email compromise ($3.0B), tech support scams ($2.1B),
  romance scams ($929M), government impersonation ($798M).
- Most common: phishing and spoofing (191,561 complaints), then extortion (89,129).
- Cryptocurrency was involved in **$11.4 billion** of losses; AI-linked scams (deepfakes, voice clones) caused **$893 million**.

Source: [FBI IC3 2025 Internet Crime Report](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf)

TrueTick's scam patterns cover every one of these categories.

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
