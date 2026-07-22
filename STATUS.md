# 📋 Project Status — Dormant (paused, still live) · 2026-07-22

**360nations.com stays live.** This is NOT abandoned — the site remains published
and may be revisited if/when the content strategy changes. What's paused is the
automatic page-generation (it was deepening a Google demotion and costing money).

## Current state
- **Site: LIVE** at 360nations.com (12,414 pages), still deployable.
- **Auto-generation: PAUSED.** `daily_expansion.yml` schedule is commented out and
  the workflow disabled — publishing ~200 more templated pages/day was making the
  demotion worse and burning Groq API credits.
- **Deploy: active** — manual content changes will still publish.
- **Repo: active** (not archived).

## Why generation is paused — and the honest recovery read
Search Console (pulled 2026-07-22): **404 lifetime clicks / 0.24% CTR**; impressions
collapsed **~97% Apr→May 2026** and now sit at **~29/month** across 12k pages — an
algorithmic **scaled-content demotion**, effectively deindexed. Google demoted the
site for *what the content is*: authoritative data wrapped in templated LLM prose
that competes head-on with Wikipedia.

**Will it recover on its own "when things change"?** Realistically no — not from
Google changing. These updates trend **stricter** on scaled AI content, not looser.
A genuine recovery needs the **content** to change (data/tools/differentiation over
prose), not just waiting. Leaving the site live costs nothing, so there's no harm
keeping it up as a standing experiment — just don't bank on passive recovery.

## The asset worth keeping
`data_enrichment.py` (World Bank + REST Countries APIs) + `data_cache/` — **244
countries of real structured data** (population, GDP, area, capital, languages,
currencies, borders). If revisited, build **data/tools** around this, not prose.

## To resume auto-generation later (only after a strategy change)
1. `gh workflow enable "Daily Country Expansion"`
2. Uncomment the `schedule` block in `.github/workflows/daily_expansion.yml`.
