# 🗄️ Project Archived — 2026-07-22

**360nations.com** (12,414 auto-generated country/region pages) is archived and
its automation is stopped. This file records why and how to revive it.

## Why it was wound down

Search Console data (pulled 2026-07-22) was conclusive:

| Month | Clicks | Impressions |
|---|---|---|
| Feb 2026 (launch) | 337 | 144,090 |
| Mar | 16 | 17,973 |
| Apr | 11 | 8,087 |
| **May** | **9** | **218** |
| Jun | 27 | 79 |
| Jul | 4 | 29 |

- **Lifetime: 404 clicks / 170,476 impressions = 0.24% CTR.** Even when Google
  showed the pages, almost nobody clicked.
- **Impressions collapsed ~97% Apr→May 2026** (8,087 → 218) and sit near zero now
  (~29/month across 12k pages) — the signature of a Google **scaled-content /
  Helpful-Content algorithmic demotion**, effectively deindexed.
- Ranks for nothing with real volume: head terms ("slovenia", "greece") sat at
  position 60–85; the only page-1 queries were verbatim exact-phrase matches with
  no search demand.

Root cause: authoritative data was wrapped in **templated LLM prose that competed
head-on with Wikipedia** — thin content by Google's 2024 standards. The failure
was the *form*, not the data.

## What was stopped

- `daily_expansion.yml` — schedule commented out **and** workflow disabled (was
  spending Groq API credits + Actions minutes generating pages into a dead site).
- `deploy.yml` — disabled.
- The GitHub repository is **archived** (read-only).

## Salvageable asset (if a future project wants it)

The data layer is real and worth keeping: `data_enrichment.py` pulls from the
**World Bank API** + **REST Countries API**, and `data_cache/` holds **244
countries** of authoritative structured data (population, GDP, area, capital,
languages, currencies, borders, timezones). A future *data-first* product —
interactive comparisons/tools, not prose — could reuse this on a **fresh domain**
(360nations.com carries the demotion).

## Live site & housekeeping

- The site may still be served by GitHub Pages at 360nations.com but is deindexed.
  To take it fully offline: repo **Settings → Pages → unpublish** (unarchive first).
- **Revoke/rotate the `GROQ_API_KEY`** if it isn't used elsewhere — it's stored as
  a GitHub Actions secret on this repo.

## How to revive

1. Unarchive the repo (GitHub → Settings → Danger Zone).
2. Re-enable + uncomment the schedule in `daily_expansion.yml`.
3. **Only** after a real content-strategy change (data/tools over prose) — otherwise
   it will be demoted again.
