# 360Nations Cost-of-Living Expansion — Nationwide Coverage

## What This Is
Expanding 360nations.com from 1 cost-of-living page per country into **7 dedicated cost sub-pages + cross-country cost comparisons**, enriched with **real World Bank API data**. Creates ~2,800 new pages targeting keywords like "rent in Kenya", "healthcare cost Nigeria", "Lagos vs Nairobi cost of living."

---

## Part A: What Was Built

### Files Modified
| File | What Changed |
|------|-------------|
| `data_enrichment.py` | Added World Bank API fetch, cache, factbox, comparison data functions |
| `country_pages.py` | Added 8 prompts, sidebar sub-items, hub links, cross-links, generation pipeline, 3 new CLI flags |
| `expansion_rules.json` | Added phases 9/10/11 for cost generation |

### Files Created
| File | What It Is |
|------|-----------|
| `cost_angle_registry.json` | Registry for 7 cost sub-angles + comparison type definition |
| `data_cache/worldbank/` | Cache directory for World Bank indicator data |

### 7 New Cost Sub-Angles
| Slug | Title Pattern |
|------|--------------|
| `cost-rent-housing` | Rent & Housing Prices in {Country} |
| `cost-food-groceries` | Food & Grocery Prices in {Country} |
| `cost-healthcare` | Healthcare Costs in {Country} |
| `cost-transportation` | Transportation Costs in {Country} |
| `cost-education` | Education Costs in {Country} |
| `cost-utilities-internet` | Utility & Internet Costs in {Country} |
| `cost-monthly-budget` | Monthly Budget Guide for {Country} |

### Page Count
| Type | Count |
|------|-------|
| New cost sub-angle pages | 1,708 (244 x 7) |
| New cost comparison pages | ~1,088 |
| Existing hub pages rebuilt | 244 |
| **Total new pages** | **~2,796** |

---

## Part B: How To Run

All commands run from: `E:\Projects\GlobalCountryPages\`

### Step 1: Prefetch World Bank Data (~6 min, no Groq API)
```bash
python data_enrichment.py prefetch-worldbank
```
- Fetches 5 economic indicators per country from World Bank API
- Caches to `data_cache/worldbank/{ISO}_indicators.json`
- Safe to re-run — skips already cached countries

### Step 2: Generate Cost Sub-Angle Pages (~57 min, uses Groq API)
```bash
python country_pages.py --generate-cost-angles --count 5000
```
- Generates 1,708 pages (244 countries x 7 sub-angles)
- **Safe to re-run** — skips already generated pages
- At 2s per call = ~57 min total

### Step 3: Generate Cost Comparison Pages (~36 min, uses Groq API)
```bash
python country_pages.py --generate-cost-comparisons --count 5000
```
- Generates ~1,088 comparison pages (common_comparisons + neighbors)
- **Safe to re-run** — skips already generated pages

### Step 4: Rebuild Hub Pages (~1 min, NO Groq API)
```bash
python country_pages.py --regenerate-cost-hubs
```
- Re-renders existing cost-of-living.html pages with new sub-angle link grids
- No API calls — just re-builds HTML from stored JSON

### Step 5 (Optional): Rebuild All HTML
```bash
python country_pages.py --rebuild-html
```
- Re-renders ALL pages with updated sidebar (shows cost sub-items)
- No API calls

---

## Power Loss / Resume Guide

**Every command is safe to re-run.** Each one checks if the output file already exists before generating. If power cuts out mid-run:

1. Just run the **same command again** — it picks up where it left off
2. No pages get corrupted (each page writes completely before moving to the next)
3. No need to track which page you were on

### Example: Resume after power loss during Step 2
```bash
# Just run the exact same command again
python country_pages.py --generate-cost-angles --count 5000
```
Output will show "Already exists: afghanistan/cost-rent-housing, skipping" for completed pages, then continue generating the rest.

---

## Filtering Options

### Generate for a single country (testing)
```bash
python country_pages.py --generate-cost-angles --entity kenya --count 7
```

### Generate for a continent only
```bash
python country_pages.py --generate-cost-angles --continent africa --count 5000
```

### Generate a single cost angle for one country
```bash
python country_pages.py --entity kenya --angle cost-rent-housing
```

---

## Groq Spend Limit

If you see `spend_limit_reached` error:
1. Go to https://console.groq.com/settings/billing
2. Raise or remove the spend alert threshold
3. Re-run the same command (it resumes automatically)

---

## Verification Checklist

After generation is complete:
- [ ] `data_cache/worldbank/` has JSON files for 244 countries
- [ ] Open any country's `cost-rent-housing.html` — verify World Bank factbox + price tables
- [ ] Open any country's `cost-of-living.html` — verify "Detailed Cost Guides" grid at bottom
- [ ] Check sidebar on a cost sub-page — verify indented items under "Cost Of Living"
- [ ] Generate 1 test comparison — verify side-by-side tables
- [ ] Run `python country_pages.py --status` to check overall progress
