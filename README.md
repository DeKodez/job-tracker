# AI/ML Job Tracker — Singapore

Tracks AI Engineer, ML Engineer, and related roles at FAANG and top tech companies with Singapore offices. Runs on GitHub Actions, diffs against previous results, and emails a daily digest.

### Tracked Sources

- **LinkedIn** (aggregator) — broadest coverage
- **Greenhouse API** — 25+ companies (Stripe, Databricks, Anthropic, MongoDB, Airbnb, Vercel, etc.)
- **Google**, **Apple**, **Amazon** — direct career page scrapers
- **MyCareersFuture** — Singapore government job portal
- ByteDance, Microsoft, Meta, Shopee — scraped via LinkedIn (their career sites are client-rendered)

### How It Works

Runs twice daily (8am & 4pm SGT) via GitHub Actions. Each run:

1. Scrapes all sources for AI/ML roles in Singapore
2. Compares against the previous snapshot
3. Commits updated `data/jobs.json` to the repo
4. Emails a digest of new and removed listings

### Setup

```bash
git clone https://github.com/DeKodez/job-tracker
pip install -r requirements.txt
python main.py
```

Email requires three repo secrets: `SMTP_USER`, `SMTP_PASS`, `SMTP_TO`.
