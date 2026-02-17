"""
Country Page Generator
Generates evergreen reference pages for 249 countries/territories.
30 angles per entity, with Level 3 sub-entity expansion.

Uses Groq API (OpenAI-compatible) for content generation.
Output: HTML + JSON + Markdown per page.
"""

import json
import os
import re
import sys
import time
import random
import argparse
from datetime import datetime
from pathlib import Path

# Try to import OpenAI SDK (used for Groq)
try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False

# Config
try:
    from config import GROQ_API_KEY, GROQ_MODEL, CONTINENT_COLORS, SITE_NAME, SITE_URL, iso_to_flag
except ImportError:
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = "llama-3.3-70b-versatile"
    SITE_NAME = "360 Nations"
    SITE_URL = ""
    CONTINENT_COLORS = {
        "africa": {"primary": "#E67E22", "secondary": "#F39C12", "name": "Africa"},
        "asia": {"primary": "#E74C3C", "secondary": "#C0392B", "name": "Asia"},
        "europe": {"primary": "#3498DB", "secondary": "#2980B9", "name": "Europe"},
        "north-america": {"primary": "#27AE60", "secondary": "#229954", "name": "North America"},
        "south-america": {"primary": "#8E44AD", "secondary": "#7D3C98", "name": "South America"},
        "oceania": {"primary": "#16A085", "secondary": "#138D75", "name": "Oceania"},
        "antarctica": {"primary": "#5DADE2", "secondary": "#3498DB", "name": "Antarctica"},
    }
    def iso_to_flag(iso_code):
        if not iso_code or len(iso_code) != 2:
            return ""
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso_code.upper())


# Paths
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "generated_pages"
OUTPUT_DIR.mkdir(exist_ok=True)

ENTITY_REGISTRY_FILE = BASE_DIR / "entity_registry.json"
LEVEL3_REGISTRY_FILE = BASE_DIR / "level3_registry.json"
ANGLE_REGISTRY_FILE = BASE_DIR / "angle_registry.json"
REGION_MANIFEST_FILE = BASE_DIR / "region_manifest.json"
PENDING_ENTITIES_FILE = BASE_DIR / "pending_entities.json"


# =============================================================================
# UTILITIES
# =============================================================================

def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {"INFO": "[i]", "SUCCESS": "[+]", "ERROR": "[!]", "WARN": "[*]"}.get(level, "")
    print(f"[{timestamp}] {prefix} {message}")


def load_json(filepath):
    if Path(filepath).exists():
        return json.loads(Path(filepath).read_text(encoding="utf-8"))
    return {}


def save_json(filepath, data):
    Path(filepath).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# REGISTRIES
# =============================================================================

def load_entity_registry():
    return load_json(ENTITY_REGISTRY_FILE)


def load_angle_registry():
    return load_json(ANGLE_REGISTRY_FILE)


def load_level3_registry():
    return load_json(LEVEL3_REGISTRY_FILE)


def get_entity(entity_slug):
    """Get entity metadata by slug."""
    registry = load_entity_registry()
    return registry.get("entities", {}).get(entity_slug)


def get_all_entity_slugs():
    """Get all entity slugs."""
    registry = load_entity_registry()
    return list(registry.get("entities", {}).keys())


# =============================================================================
# GROQ API
# =============================================================================

def generate_with_groq(prompt, model=None, max_tokens=2500):
    """Generate content using Groq API."""
    if not OPENAI_SDK_AVAILABLE:
        raise Exception("OpenAI SDK not installed. Run: pip install openai")

    api_key = GROQ_API_KEY
    if not api_key:
        raise Exception("GROQ_API_KEY not configured")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    response = client.chat.completions.create(
        model=model or GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are an expert travel writer and cultural guide creating comprehensive, evergreen reference pages about countries and territories worldwide. Write factual, engaging content."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content


# =============================================================================
# 30 ANGLE PROMPTS
# =============================================================================

def get_prompt_for_angle(entity, angle_id, comparison_entity=None):
    """Build the AI prompt for a given entity + angle.
    Each angle produces a DIFFERENT content structure matching its search intent."""
    name = entity["name"]
    capital = entity.get("capital", "")
    continent = entity.get("continent", "")
    pop = entity.get("population_millions", 0)
    languages = ", ".join(entity.get("languages", []))
    currency = entity.get("currency", "")
    entity_type = entity.get("type", "sovereign")
    parent = entity.get("parent_entity", "")
    neighbors = ", ".join(entity.get("neighbors", []))

    context = f"""Country/Territory: {name}
Capital: {capital}
Continent: {continent.replace('-', ' ').title()}
Population: {pop}M
Languages: {languages}
Currency: {currency}
Type: {entity_type}
{f'Parent: {parent}' if parent else ''}
Neighbors: {neighbors}"""

    # Add enriched data to context if available
    try:
        from data_enrichment import fetch_country_data
        enriched = fetch_country_data(entity.get("iso_code", ""))
        if enriched:
            real_pop = enriched.get("population", 0)
            real_area = enriched.get("area_km2", 0)
            if real_pop:
                context += f"\nVerified Population: {real_pop:,}"
            if real_area:
                context += f"\nVerified Area: {real_area:,.0f} km²"
    except ImportError:
        pass

    # ── FORMAT INSTRUCTIONS (shared across prompts) ──
    format_rules = """
OUTPUT FORMAT RULES (follow exactly):
- Use [SECTION] Section Name [/SECTION] to wrap major sections
- Use [TABLE] with | pipes | for data tables (first row = header, use | --- | for separator)
- Use [FACTBOX] for quick-reference stat boxes (one "Key: Value" per line)
- Use [CALLOUT] for important tips, warnings, or highlights
- Use [RATING] label: X/5 for ratings (whole numbers only)
- Use - for bullet lists, 1. for numbered lists
- Use ** for bold text on key terms
- No emojis, no markdown headings (#), no HTML tags
- 8th-grade reading level, factual, evergreen
- Start with a direct one-sentence answer before any sections"""

    prompts = {
        # ── OVERVIEW: Quick-reference factsheet + short narrative ──
        "overview": f"""Generate a country overview reference page for {name}.

{context}

This page answers: "What is {name}? Give me the essential facts quickly."

FORMAT:

[FACTBOX]
Official Name: (full official name)
Capital: {capital}
Population: {pop} million
Languages: {languages}
Currency: {currency}
Government: (type)
Continent: {continent.replace('-', ' ').title()}
ISO Code: {entity.get('iso_code', '')}
Calling Code: (phone code)
Drives On: (left/right)
Time Zone: (UTC offset)
[/FACTBOX]

[SECTION] What Is {name}? [/SECTION]
2-3 paragraphs: sovereignty status, geographic position, what it is known for. Plain language.

[SECTION] Key History [/SECTION]
A numbered timeline of 5-7 major events. Format: "1. YEAR - Event description"

[SECTION] What Makes {name} Unique [/SECTION]
4-5 bullet points, each one sentence, factual.

[SECTION] Quick Summary [/SECTION]
One sentence capturing the essence.

{format_rules}
Target: 700-900 words.""",

        # ── GEOGRAPHY: Data-heavy with climate table ──
        "geography": f"""Generate a geography reference page for {name}.

{context}

This page answers: "Where is {name}? What's the terrain and climate like? When should I visit?"

FORMAT:

[FACTBOX]
Land Area: (km2 and comparison, e.g. "about the size of Texas")
Highest Point: (name, elevation)
Lowest Point: (name, elevation)
Coastline: (km, or "landlocked")
Borders: {neighbors}
Climate Type: (e.g. tropical, arid, temperate)
[/FACTBOX]

[SECTION] Location & Borders [/SECTION]
Where exactly it sits. Which countries border it. What bodies of water surround it. 2 paragraphs.

[SECTION] Terrain & Landscape [/SECTION]
Mountains, rivers, deserts, forests, coastlines. What does the land actually look like? 2-3 paragraphs.

[SECTION] Climate By Season [/SECTION]
[TABLE]
| Season | Months | Temperature Range | Rainfall | Conditions |
| --- | --- | --- | --- | --- |
(fill 3-4 rows for main seasons)
[/TABLE]

[SECTION] Best Time To Visit [/SECTION]
[CALLOUT] Best months: (months). Why: (1-2 sentences). Avoid: (months and why). [/CALLOUT]

[SECTION] Natural Highlights [/SECTION]
5-6 bullet points: national parks, natural wonders, unique biodiversity. One sentence each.

{format_rules}
Target: 700-800 words.""",

        # ── MUST-KNOW TRUTH: Fact-check format with myth/reality pairs ──
        "must_know_truth": f"""Generate a "must-know facts" reference page for {name}.

{context}

This page answers: "What do most people get wrong about {name}? What's the real story?"

FORMAT:

[SECTION] Historical Context [/SECTION]
3-4 paragraphs covering: founding/colonization/independence timeline. State only verifiable facts, dates, and classifications. No moral judgments.

[SECTION] Common Misconceptions [/SECTION]
Format each as a myth/reality pair:

[CALLOUT] Misconception: "(common false belief)"
Reality: (the verified truth, with context) [/CALLOUT]

Provide 5-6 of these pairs. Cover geography, culture, safety, economy, people.

[SECTION] Challenges & Context [/SECTION]
4-5 bullet points on real challenges. State facts and data. No editorializing.

[SECTION] What Gets Overlooked [/SECTION]
4-5 bullet points of nuanced facts that don't make international headlines. Positive or neutral facts that add depth.

{format_rules}
Rules: Factual only. No moral conclusions. State timelines, classifications, and verified data. No "colonization was good/bad" framing.
Target: 800-900 words.""",

        # ── POSITIVE THINGS: Achievement cards + evidence ──
        "positive_things": f"""Generate a page about positive achievements and highlights of {name}.

{context}

This page answers: "What is {name} good at? What should people know that's positive?"

FORMAT:

[SECTION] Notable Achievements [/SECTION]
[TABLE]
| Category | Achievement | Details |
| --- | --- | --- |
(6-8 rows covering: science, sports, arts, development, innovation, global contributions)
[/TABLE]

[SECTION] Cultural Treasures [/SECTION]
4-5 bullet points: UNESCO sites, traditions, art forms. Include specific names. One sentence each.

[SECTION] People & Global Impact [/SECTION]
3-4 bullet points: notable figures, diaspora contributions, values. Factual, not promotional.

[SECTION] What Visitors Love [/SECTION]
5-6 bullet points of consistently praised aspects: hospitality, food, scenery, experiences. Evidence-based (travel reviews, cultural recognition).

[SECTION] Hidden Gems [/SECTION]
3-4 lesser-known positives that deserve more recognition. One sentence each.

{format_rules}
Rules: Evidence-based. Cite specific achievements, places, people. No generic praise.
Target: 700-800 words.""",

        # ── CITIES & REGIONS: City cards with role/character/pop ──
        "cities_and_regions": f"""Generate a cities and regions reference guide for {name}.

{context}

This page answers: "What are the main cities and regions? How is {name} divided?"

FORMAT:

[FACTBOX]
Administrative Divisions: (how many states/provinces/regions and what they're called)
Largest City: (name, population)
Capital: {capital}
Number of Cities Over 1M: (number)
[/FACTBOX]

[SECTION] How {name} Is Divided [/SECTION]
1-2 paragraphs explaining the administrative structure.

[SECTION] Major Cities [/SECTION]
For each of the top 5-8 cities, use this format:

**City Name** (population estimate)
Role: (capital / economic hub / cultural center / port city / etc.)
Known For: (1-2 sentences on character and identity)
Best For: (what type of visitor or interest it serves)

[SECTION] Key Regions [/SECTION]
[TABLE]
| Region | Character | Known For | Major City |
| --- | --- | --- | --- |
(5-8 rows for main regions/states/provinces)
[/TABLE]

[SECTION] Regional Differences [/SECTION]
3-4 bullet points on how regions differ (culture, economy, climate, language).

[SECTION] Getting Around [/SECTION]
Brief transport overview: domestic flights, trains, buses, driving conditions. 1-2 paragraphs.

{format_rules}
Target: 900-1000 words.""",

        # ── VISA & ENTRY: Lookup table by nationality ──
        "visa_and_entry": f"""Generate a visa and entry requirements reference page for {name}.

{context}

This page answers: "Do I need a visa for {name}? What documents do I need?"

FORMAT:

[CALLOUT] Visa rules change frequently. Always verify current requirements with the official embassy or consulate of {name} before traveling. [/CALLOUT]

[SECTION] Visa Policy Overview [/SECTION]
1-2 paragraphs: general visa stance (liberal/moderate/strict), how many countries get visa-free access.

[SECTION] Requirements By Nationality [/SECTION]
[TABLE]
| Nationality | Visa Required? | Type | Max Stay | Notes |
| --- | --- | --- | --- | --- |
| US Citizens | (Yes/No/On Arrival) | (Tourist/eVisa/etc) | (days) | (key note) |
| UK Citizens | ... | ... | ... | ... |
| EU Citizens | ... | ... | ... | ... |
| Canadian Citizens | ... | ... | ... | ... |
| Australian Citizens | ... | ... | ... | ... |
| Indian Citizens | ... | ... | ... | ... |
| Chinese Citizens | ... | ... | ... | ... |
[/TABLE]

[SECTION] By Visitor Type [/SECTION]
**Tourists:** (requirements, typical stay, extensions)
**Business Travelers:** (requirements, invitation letters, differences)
**Students:** (requirements, enrollment proof, duration)
**Workers:** (requirements, sponsorship, process)

[SECTION] Documents Checklist [/SECTION]
Numbered list of documents typically required. 8-10 items.

[SECTION] Entry Points & Procedures [/SECTION]
Main airports, land borders, what to expect at immigration. 1-2 paragraphs.

[SECTION] Common Mistakes To Avoid [/SECTION]
5-6 bullet points of practical tips.

{format_rules}
Target: 700-800 words.""",

        # ── COST OF LIVING: Price tables + budget tiers ──
        "cost_of_living": f"""Generate a cost of living reference page for {name}.

{context}
Local currency: {currency}

This page answers: "How much does it cost to live in or visit {name}?"

FORMAT:

[FACTBOX]
Cost Level: (Cheap / Affordable / Moderate / Expensive / Very Expensive)
Daily Budget (Backpacker): ($XX-XX USD)
Daily Budget (Mid-Range): ($XX-XX USD)
Daily Budget (Comfort): ($XX-XX USD)
Currency: {currency}
Tipping Custom: (expected/not expected/percentage)
[/FACTBOX]

[SECTION] How Expensive Is {name}? [/SECTION]
1-2 paragraphs positioning {name} relative to global averages and neighbors.

[SECTION] Accommodation Prices [/SECTION]
[TABLE]
| Type | Price Range (USD/night) | Notes |
| --- | --- | --- |
| Hostel/Budget | $X-X | (typical quality) |
| Mid-Range Hotel | $X-X | (what to expect) |
| Luxury/Resort | $X-X | (what to expect) |
| Apartment Rent (monthly) | $X-X | (city center vs outside) |
[/TABLE]

[SECTION] Food & Dining Prices [/SECTION]
[TABLE]
| Meal Type | Price Range (USD) |
| --- | --- |
| Street Food / Local Eatery | $X-X |
| Casual Restaurant | $X-X |
| Mid-Range Restaurant (2 people) | $X-X |
| Fine Dining | $X-X |
| Beer (local) | $X-X |
| Coffee | $X-X |
| Water (1.5L bottle) | $X-X |
[/TABLE]

[SECTION] Transport Costs [/SECTION]
[TABLE]
| Transport | Cost (USD) |
| --- | --- |
| Local bus/metro ride | $X-X |
| Taxi (per km) | $X-X |
| Domestic flight | $X-X |
| Fuel (per liter) | $X-X |
[/TABLE]

[SECTION] Monthly Budget Breakdown [/SECTION]
[TABLE]
| Category | Budget ($) | Mid-Range ($) | Comfortable ($) |
| --- | --- | --- | --- |
| Rent | X | X | X |
| Food | X | X | X |
| Transport | X | X | X |
| Utilities | X | X | X |
| Entertainment | X | X | X |
| **Total** | **X** | **X** | **X** |
[/TABLE]

[SECTION] Money-Saving Tips [/SECTION]
5-6 bullet points specific to {name}.

{format_rules}
Rules: Use approximate USD ranges. Prices are rough guides, not exact.
Target: 700-800 words.""",

        # ── ECONOMY: Key indicators table + sector breakdown ──
        "economy": f"""Generate an economy reference page for {name}.

{context}

This page answers: "How does {name}'s economy work? What drives it?"

FORMAT:

[FACTBOX]
GDP (nominal): ($X billion/million estimate)
GDP Per Capita: ($X,XXX estimate)
Income Classification: (Low / Lower-Middle / Upper-Middle / High)
Main Industries: (top 3)
Currency: {currency}
Unemployment Rate: (approximate %)
Ease of Doing Business: (general ranking context)
[/FACTBOX]

[SECTION] Economic Overview [/SECTION]
2-3 paragraphs: economic classification, development level, trajectory. What kind of economy is this?

[SECTION] Key Industries [/SECTION]
[TABLE]
| Industry | Contribution | Details |
| --- | --- | --- |
(4-6 rows: agriculture, mining, manufacturing, services, tourism, tech, etc.)
[/TABLE]

[SECTION] Trade Profile [/SECTION]
**Top Exports:** (5 items with brief context)
**Top Imports:** (5 items)
**Key Trading Partners:** (3-5 countries)

[SECTION] Infrastructure [/SECTION]
4-5 bullet points covering: transport networks, energy, internet/mobile penetration, ports/airports.

[SECTION] Economic Outlook [/SECTION]
2 paragraphs: growth direction, development priorities, major projects or reforms.

{format_rules}
Target: 700-800 words.""",

        # ── CULTURE: Do's/don'ts + food guide + phrase table ──
        "culture": f"""Generate a culture reference page for {name}.

{context}

This page answers: "What's the culture like in {name}? What should I know before visiting?"

FORMAT:

[SECTION] Cultural Identity [/SECTION]
2-3 paragraphs: what defines {name}'s culture, key influences, ethnic/linguistic makeup.

[SECTION] Food & Cuisine [/SECTION]
[TABLE]
| Dish | Type | Description | Must-Try? |
| --- | --- | --- | --- |
(6-8 rows of signature dishes/drinks)
[/TABLE]
1 paragraph on eating customs and food culture.

[SECTION] Traditions & Festivals [/SECTION]
[TABLE]
| Festival/Tradition | When | What It Is |
| --- | --- | --- |
(5-6 major celebrations)
[/TABLE]

[SECTION] Etiquette: Do's and Don'ts [/SECTION]
**Do:**
- (5-6 bullet points)

**Don't:**
- (5-6 bullet points)

[SECTION] Arts & Music [/SECTION]
4-5 bullet points: notable art forms, music genres, literature, film. Specific names and examples.

[SECTION] Useful Phrases [/SECTION]
[TABLE]
| English | Local Language | Pronunciation |
| --- | --- | --- |
| Hello | ... | ... |
| Thank you | ... | ... |
| Please | ... | ... |
| Yes / No | ... | ... |
| How much? | ... | ... |
| Goodbye | ... | ... |
(8-10 essential phrases in the primary local language)
[/TABLE]

{format_rules}
Rules: Respectful. Avoid stereotypes. Specific over generic.
Target: 800-900 words.""",

        # ── TRAVEL SAFETY: Risk ratings + area-by-area ──
        "travel_safety": f"""Generate a travel safety reference page for {name}.

{context}

This page answers: "Is {name} safe to visit? What should I watch out for?"

FORMAT:

[CALLOUT] Safety conditions change. Always check your government's current travel advisory for {name} before traveling. [/CALLOUT]

[FACTBOX]
Overall Safety Rating: X/5 (1=very dangerous, 5=very safe)
Petty Crime Risk: (Low/Moderate/High)
Violent Crime Risk: (Low/Moderate/High)
Scam Risk: (Low/Moderate/High)
Natural Disaster Risk: (Low/Moderate/High)
Health Risk: (Low/Moderate/High)
Emergency Number: (number)
Tourist Police: (Yes/No, number if yes)
[/FACTBOX]

[SECTION] Overall Safety Assessment [/SECTION]
2 paragraphs: honest, balanced assessment. Not alarmist, not dismissive.

[SECTION] Safety By Area [/SECTION]
[TABLE]
| Area/Region | Safety Level | Notes |
| --- | --- | --- |
(5-8 rows covering major tourist areas and areas to avoid)
[/TABLE]

[SECTION] Common Risks & Scams [/SECTION]
6-8 bullet points: specific scams, crime patterns, and hazards that affect tourists in {name}. Be specific, not generic.

[SECTION] Health & Medical [/SECTION]
- **Vaccinations:** (recommended/required ones)
- **Water Safety:** (tap water safe? bottled recommended?)
- **Medical Facilities:** (quality, availability, insurance needed?)
- **Pharmacy Access:** (easy/limited?)

[SECTION] Practical Safety Tips [/SECTION]
6-8 bullet points specific to {name}. Actionable advice.

[SECTION] For Solo & Women Travelers [/SECTION]
3-4 bullet points with honest, specific guidance.

{format_rules}
Target: 600-700 words.""",

        # ── VS: Side-by-side comparison table ──
        "vs": f"""Generate a comparison reference page: {name} vs {comparison_entity or entity.get('common_comparisons', [''])[0]}.

{context}

The other country: {comparison_entity or entity.get('common_comparisons', [''])[0]}

This page answers: "{name} or {comparison_entity or entity.get('common_comparisons', [''])[0]}? Which is better for me?"

FORMAT:

[SECTION] Why People Compare Them [/SECTION]
1-2 paragraphs: what makes this a common comparison.

[SECTION] At A Glance [/SECTION]
[TABLE]
| Factor | {name} | {comparison_entity or entity.get('common_comparisons', [''])[0]} |
| --- | --- | --- |
| Population | ... | ... |
| Size | ... | ... |
| Language | ... | ... |
| Currency | ... | ... |
| Climate | ... | ... |
| Cost Level | ... | ... |
| Safety Level | ... | ... |
| Visa Ease | ... | ... |
| Best For | ... | ... |
[/TABLE]

[SECTION] Key Differences [/SECTION]
6 bullet points. Each starts with the category in bold. One sentence per difference.

[SECTION] Key Similarities [/SECTION]
4 bullet points. Same format.

[SECTION] Which Is Better For... [/SECTION]
[TABLE]
| If You Want... | Choose | Why |
| --- | --- | --- |
| Budget Travel | ... | ... |
| Culture & History | ... | ... |
| Beaches / Nature | ... | ... |
| Food | ... | ... |
| Nightlife | ... | ... |
| Safety | ... | ... |
| Ease of Travel | ... | ... |
[/TABLE]

[SECTION] Bottom Line [/SECTION]
2-3 sentences. No winner declared. Clarify what each excels at.

{format_rules}
Rules: Balanced. No bias. Practical for trip planning decisions.
Target: 800-900 words.""",

        # ── FOOD & CUISINE: Dish guide + street food + dining customs ──
        "food_and_cuisine": f"""Generate a food and cuisine reference page for {name}.

{context}

This page answers: "What should I eat in {name}? What are the must-try dishes?"

FORMAT:

[FACTBOX]
Staple Foods: (top 3-4 staple ingredients)
National Dish: (name and brief description)
Meal Times: (typical breakfast/lunch/dinner times)
Tipping at Restaurants: (custom)
Dietary Notes: (halal/kosher/vegetarian-friendly, etc.)
[/FACTBOX]

[SECTION] Food Culture Overview [/SECTION]
2-3 paragraphs: what defines {name}'s cuisine, key influences, regional variations.

[SECTION] Must-Try Dishes [/SECTION]
[TABLE]
| Dish | Type | Description | Where to Find |
| --- | --- | --- | --- |
(8-10 rows of signature dishes)
[/TABLE]

[SECTION] Street Food & Snacks [/SECTION]
6-8 bullet points: popular street foods with descriptions and typical prices in USD.

[SECTION] Drinks [/SECTION]
5-6 bullet points: local beverages (alcoholic and non-alcoholic), what to order.

[SECTION] Dining Customs [/SECTION]
5-6 bullet points: eating etiquette, tipping, reservation culture, dress codes.

[SECTION] Where to Eat [/SECTION]
4-5 bullet points: types of dining venues (markets, food courts, restaurants), what to expect at each.

[SECTION] Food Markets & Food Experiences [/SECTION]
4-5 specific markets or food experiences worth visiting. Name and location for each.

{format_rules}
Rules: Specific dish names, not generic. Include local-language names where helpful.
Target: 800-900 words.""",

        # ── LANGUAGE GUIDE: Phrases + communication tips ──
        "language_guide": f"""Generate a language and communication guide for {name}.

{context}

This page answers: "What language do they speak in {name}? What phrases do I need?"

FORMAT:

[FACTBOX]
Official Language(s): {languages}
Widely Spoken: (other common languages)
English Proficiency: (High/Moderate/Low/Very Low)
Script: (Latin/Arabic/Cyrillic/etc.)
Language Family: (e.g. Romance, Bantu, Sino-Tibetan)
[/FACTBOX]

[SECTION] Language Overview [/SECTION]
2-3 paragraphs: linguistic landscape, regional dialects, minority languages, how widely English is understood.

[SECTION] Essential Phrases [/SECTION]
[TABLE]
| English | Local Language | Pronunciation | Notes |
| --- | --- | --- | --- |
| Hello | ... | ... | (formal/informal) |
| Thank you | ... | ... | ... |
| Please | ... | ... | ... |
| Yes / No | ... | ... | ... |
| Excuse me | ... | ... | ... |
| How much? | ... | ... | ... |
| Where is...? | ... | ... | ... |
| I don't understand | ... | ... | ... |
| Do you speak English? | ... | ... | ... |
| Help! | ... | ... | ... |
| Goodbye | ... | ... | ... |
| Sorry | ... | ... | ... |
(12-15 essential phrases in the primary language)
[/TABLE]

[SECTION] Numbers & Bargaining [/SECTION]
[TABLE]
| Number | Local Word | Pronunciation |
| --- | --- | --- |
(1-10 plus 100, 1000)
[/TABLE]

[SECTION] Communication Tips [/SECTION]
6-8 bullet points: body language, gestures to avoid, formality levels, how to get help.

[SECTION] Translation Tools & Resources [/SECTION]
4-5 bullet points: recommended apps, phrasebooks, language learning tips for visitors.

{format_rules}
Target: 700-800 words.""",

        # ── TRANSPORTATION: Getting around guide ──
        "transportation": f"""Generate a transportation and getting-around guide for {name}.

{context}

This page answers: "How do I get around in {name}? What transport options exist?"

FORMAT:

[FACTBOX]
Main International Airport(s): (name, code)
Domestic Air Network: (extensive/moderate/limited)
Rail Network: (extensive/moderate/limited/none)
Drives On: (left/right)
Road Quality: (good/moderate/poor)
Ride-Hailing Apps: (Uber/Grab/Bolt/local alternatives)
[/FACTBOX]

[SECTION] Getting There [/SECTION]
2 paragraphs: main airports, direct flight hubs, overland entry points.

[SECTION] Domestic Flights [/SECTION]
1-2 paragraphs: domestic airlines, main routes, booking tips, approximate costs.

[SECTION] Trains & Rail [/SECTION]
1-2 paragraphs: rail network quality, key routes, high-speed options, booking process.

[SECTION] Buses & Coaches [/SECTION]
1-2 paragraphs: intercity bus companies, quality, routes, costs.

[SECTION] City Transport [/SECTION]
[TABLE]
| Mode | Available In | Cost (USD) | Notes |
| --- | --- | --- | --- |
| Metro/Subway | (cities) | $X | ... |
| City Bus | (cities) | $X | ... |
| Taxi | (everywhere/cities) | $X/km | ... |
| Ride-Hailing | (cities) | $X-X | ... |
| Tuk-tuk/Rickshaw | (if applicable) | $X | ... |
[/TABLE]

[SECTION] Driving [/SECTION]
5-6 bullet points: license requirements, road conditions, fuel costs, car rental tips, hazards.

[SECTION] Transport Tips [/SECTION]
6-8 practical bullet points specific to {name}: scams to avoid, payment methods, apps to download, safety.

{format_rules}
Target: 700-800 words.""",

        # ── BEST TIME TO VISIT: Month-by-month guide ──
        "best_time_to_visit": f"""Generate a best-time-to-visit guide for {name}.

{context}

This page answers: "When is the best time to visit {name}? What's each month like?"

FORMAT:

[CALLOUT] Best months to visit {name}: (months). Peak season: (months). Budget season: (months). Avoid: (months and why). [/CALLOUT]

[SECTION] Seasons Overview [/SECTION]
2-3 paragraphs: climate zones, dry vs wet seasons, how seasons affect travel.

[SECTION] Month-by-Month Guide [/SECTION]
[TABLE]
| Month | Weather | Crowds | Prices | Best For |
| --- | --- | --- | --- | --- |
| January | ... | Low/Med/High | $/$$/$$$  | ... |
| February | ... | ... | ... | ... |
| March | ... | ... | ... | ... |
| April | ... | ... | ... | ... |
| May | ... | ... | ... | ... |
| June | ... | ... | ... | ... |
| July | ... | ... | ... | ... |
| August | ... | ... | ... | ... |
| September | ... | ... | ... | ... |
| October | ... | ... | ... | ... |
| November | ... | ... | ... | ... |
| December | ... | ... | ... | ... |
[/TABLE]

[SECTION] Festivals & Events Calendar [/SECTION]
[TABLE]
| Event | Month(s) | Description |
| --- | --- | --- |
(6-8 major festivals/events worth timing a visit around)
[/TABLE]

[SECTION] Regional Variations [/SECTION]
4-5 bullet points: how timing differs by region within {name}.

[SECTION] Practical Tips [/SECTION]
5-6 bullet points: booking windows, shoulder season advantages, weather gear, holidays to avoid.

{format_rules}
Target: 700-800 words.""",

        # ── TOP THINGS TO DO: Attractions & experiences ──
        "top_things_to_do": f"""Generate a top-things-to-do reference page for {name}.

{context}

This page answers: "What are the best things to do in {name}? What should I not miss?"

FORMAT:

[SECTION] Top Attractions [/SECTION]
[TABLE]
| Attraction | Location | Type | Why Visit |
| --- | --- | --- | --- |
(8-10 must-see attractions with specific names and locations)
[/TABLE]

[SECTION] Unique Experiences [/SECTION]
6-8 bullet points: experiences unique to {name} that you can't easily do elsewhere. Specific, not generic.

[SECTION] Outdoor & Nature [/SECTION]
5-6 bullet points: national parks, hiking, beaches, wildlife, adventure activities. Specific names.

[SECTION] Cultural Experiences [/SECTION]
5-6 bullet points: museums, temples, historical sites, local workshops, performances. Specific names.

[SECTION] Hidden Gems [/SECTION]
4-5 lesser-known spots or activities that experienced travelers recommend.

[SECTION] Day Trips [/SECTION]
4-5 day trip ideas from major cities with distance, travel time, and highlights.

[SECTION] Planning Tips [/SECTION]
[CALLOUT] Suggested itineraries: 3-day (highlights), 7-day (comprehensive), 14-day (deep exploration). Key tips for booking and prioritizing. [/CALLOUT]

{format_rules}
Rules: Use specific place names, not generic descriptions. Prioritize by visitor ratings and cultural significance.
Target: 800-900 words.""",

        # ── WHERE TO STAY: Neighborhoods & accommodation ──
        "where_to_stay": f"""Generate a where-to-stay guide for {name}.

{context}

This page answers: "Where should I stay in {name}? What neighborhoods are best?"

FORMAT:

[SECTION] Best Areas to Stay [/SECTION]
For each of the top 5-7 areas/neighborhoods:

**Area Name** (City)
Best For: (type of traveler: backpacker / luxury / family / business)
Vibe: (1-2 sentences on character)
Price Range: ($X-X/night)
Pros: (2-3 key advantages)
Cons: (1-2 honest downsides)

[SECTION] Accommodation Types [/SECTION]
[TABLE]
| Type | Price Range (USD/night) | Best For | Notes |
| --- | --- | --- | --- |
| Hostels | $X-X | Budget/Social | ... |
| Guesthouses | $X-X | Mid-range/Local | ... |
| Hotels | $X-X | Comfort/Business | ... |
| Boutique Hotels | $X-X | Experience | ... |
| Resorts | $X-X | Relaxation | ... |
| Apartments/Airbnb | $X-X | Long stays/Families | ... |
[/TABLE]

[SECTION] Booking Tips [/SECTION]
6-8 bullet points: best platforms, advance booking needs, negotiation tips, seasonal pricing.

[SECTION] Safety & Location Tips [/SECTION]
5-6 bullet points: areas to avoid, safety considerations, proximity to transport.

{format_rules}
Target: 700-800 words.""",

        # ── INTERNET & CONNECTIVITY ──
        "internet_and_connectivity": f"""Generate an internet and connectivity guide for {name}.

{context}

This page answers: "What's the internet like in {name}? How do I get a SIM card?"

FORMAT:

[FACTBOX]
Average Internet Speed: (Mbps download)
Mobile Network Coverage: (Excellent/Good/Moderate/Poor)
Main Carriers: (top 2-3 mobile providers)
SIM Card Cost: (approx. USD for tourist SIM)
WiFi Availability: (Widespread/Common/Limited)
5G Available: (Yes/No/Limited)
[/FACTBOX]

[SECTION] Internet Overview [/SECTION]
2 paragraphs: general internet quality, urban vs rural divide, reliability.

[SECTION] Getting a SIM Card [/SECTION]
1-2 paragraphs: where to buy, documents needed, recommended carriers, data plans with prices.

[TABLE]
| Carrier | Tourist Plan | Data | Price (USD) | Notes |
| --- | --- | --- | --- | --- |
(3-4 major carriers with tourist-friendly plans)
[/TABLE]

[SECTION] WiFi Availability [/SECTION]
4-5 bullet points: hotel WiFi quality, cafe WiFi culture, coworking spaces, public WiFi.

[SECTION] For Remote Workers [/SECTION]
4-5 bullet points: coworking spaces, reliable cafe chains, backup internet options, VPN needs.

[SECTION] Tips & Warnings [/SECTION]
5-6 bullet points: internet censorship, blocked sites, VPN recommendations, roaming alternatives, eSIM options.

{format_rules}
Target: 600-700 words.""",

        # ── MOVING THERE: Expat relocation guide ──
        "moving_there": f"""Generate a moving-to / expat relocation guide for {name}.

{context}

This page answers: "How do I move to {name}? What do I need to know about relocating?"

FORMAT:

[SECTION] Why People Move to {name} [/SECTION]
2-3 paragraphs: common reasons, expat demographics, quality of life overview.

[SECTION] Visa & Residency Options [/SECTION]
[TABLE]
| Visa Type | Duration | Requirements | Cost (USD) | Path to PR? |
| --- | --- | --- | --- | --- |
| Tourist | ... | ... | ... | No |
| Work Visa | ... | ... | ... | ... |
| Business/Investor | ... | ... | ... | ... |
| Retirement | ... | ... | ... | ... |
| Student | ... | ... | ... | ... |
| Digital Nomad | ... | ... | ... | ... |
[/TABLE]

[SECTION] Relocation Checklist [/SECTION]
Numbered list of 10-12 steps from decision to settling in.

[SECTION] Expat Communities [/SECTION]
4-5 bullet points: where expats concentrate, online groups, social networks, meetups.

[SECTION] Banking & Finances [/SECTION]
4-5 bullet points: opening bank accounts, money transfers, currency considerations.

[SECTION] Challenges & Honest Advice [/SECTION]
5-6 bullet points: culture shock, bureaucracy, language barriers, common complaints.

{format_rules}
Target: 800-900 words.""",

        # ── EDUCATION: Schools & universities ──
        "education": f"""Generate an education reference page for {name}.

{context}

This page answers: "What is the education system like in {name}? Where can I study?"

FORMAT:

[FACTBOX]
Literacy Rate: (%)
School System: (years of compulsory education)
Language of Instruction: (primary language)
Academic Calendar: (months)
International Schools: (available/limited)
Top University Ranking: (global ranking context)
[/FACTBOX]

[SECTION] Education System Overview [/SECTION]
2-3 paragraphs: structure (primary/secondary/tertiary), quality, public vs private.

[SECTION] Top Universities [/SECTION]
[TABLE]
| University | Location | Known For | Est. Tuition (USD/year) |
| --- | --- | --- | --- |
(5-7 top universities)
[/TABLE]

[SECTION] International Schools [/SECTION]
4-5 bullet points: availability, curricula offered (IB, British, American), costs, locations.

[SECTION] Studying as a Foreigner [/SECTION]
5-6 bullet points: student visa process, language requirements, scholarships, living costs for students.

[SECTION] Education Quality & Challenges [/SECTION]
4-5 bullet points: strengths and weaknesses of the system, recent reforms.

{format_rules}
Target: 700-800 words.""",

        # ── REAL ESTATE: Property & buying guide ──
        "real_estate": f"""Generate a real estate and property guide for {name}.

{context}

This page answers: "What's the property market like in {name}? Can foreigners buy?"

FORMAT:

[FACTBOX]
Can Foreigners Buy?: (Yes/Restricted/No)
Average Price (Capital, per sqm): ($X USD)
Rental Yield: (approximate %)
Property Tax: (approximate annual %)
Popular Areas: (top 3 for investment)
[/FACTBOX]

[SECTION] Market Overview [/SECTION]
2-3 paragraphs: current market conditions, trends, price trajectory, urban vs rural.

[SECTION] Prices by Area [/SECTION]
[TABLE]
| Area/City | Buy (per sqm, USD) | Rent (monthly, USD) | Type |
| --- | --- | --- | --- |
(6-8 rows covering major cities/areas)
[/TABLE]

[SECTION] Foreign Ownership Rules [/SECTION]
4-5 bullet points: restrictions, workarounds (leasehold, company structures), required permits.

[SECTION] Buying Process [/SECTION]
Numbered list: 8-10 steps from search to ownership transfer.

[SECTION] Rental Market [/SECTION]
4-5 bullet points: tenant rights, typical lease terms, deposit norms, furnished vs unfurnished.

[SECTION] Investment Tips [/SECTION]
5-6 bullet points: emerging areas, risks, legal considerations, property management.

{format_rules}
Target: 700-800 words.""",

        # ── TAXES: Tax guide ──
        "taxes": f"""Generate a tax guide reference page for {name}.

{context}
Currency: {currency}

This page answers: "What are the tax rates in {name}? What do expats need to know?"

FORMAT:

[CALLOUT] Tax laws change frequently. Always consult a qualified tax professional for advice specific to your situation. This is a general guide only. [/CALLOUT]

[FACTBOX]
Income Tax Range: (X% - X%)
Corporate Tax: (X%)
VAT/GST: (X%)
Capital Gains Tax: (X% or included in income)
Tax Year: (Jan-Dec / Apr-Mar / etc.)
Tax Treaty Network: (X countries)
[/FACTBOX]

[SECTION] Tax System Overview [/SECTION]
2 paragraphs: territorial vs worldwide taxation, residency rules for tax purposes.

[SECTION] Personal Income Tax [/SECTION]
[TABLE]
| Income Bracket ({currency}) | Tax Rate |
| --- | --- |
(4-6 brackets)
[/TABLE]
1 paragraph on deductions, allowances, filing requirements.

[SECTION] Corporate & Business Tax [/SECTION]
4-5 bullet points: corporate rate, small business incentives, free zones, registration requirements.

[SECTION] VAT / Sales Tax [/SECTION]
3-4 bullet points: standard rate, reduced rates, exemptions, tourist refund schemes.

[SECTION] For Expats & Foreign Workers [/SECTION]
5-6 bullet points: tax residency rules, double taxation treaties, social security, remittance rules.

[SECTION] Crypto & Investment Income [/SECTION]
3-4 bullet points: how investment income, dividends, and cryptocurrency are taxed.

{format_rules}
Target: 700-800 words.""",

        # ── HEALTHCARE: Medical guide ──
        "healthcare": f"""Generate a healthcare reference page for {name}.

{context}

This page answers: "What is healthcare like in {name}? What do I need to know about hospitals and insurance?"

FORMAT:

[FACTBOX]
Healthcare System: (Universal/Mixed/Private)
Quality Rating: (relative context)
Emergency Number: (number)
Hospital Standard: (Excellent/Good/Adequate/Basic)
Insurance Required: (recommended/required/not needed)
Pharmacy Access: (widespread/moderate/limited)
[/FACTBOX]

[SECTION] Healthcare Overview [/SECTION]
2-3 paragraphs: system structure, public vs private, quality of care, urban vs rural access.

[SECTION] Hospitals & Clinics [/SECTION]
[TABLE]
| Facility | Location | Type | Specialties | English-Speaking |
| --- | --- | --- | --- | --- |
(5-6 major hospitals, especially those serving foreigners)
[/TABLE]

[SECTION] Health Insurance [/SECTION]
5-6 bullet points: recommended insurance types, local insurance options, coverage for expats, costs.

[SECTION] Pharmacies & Medications [/SECTION]
4-5 bullet points: availability of medications, prescription requirements, common brands, costs.

[SECTION] Vaccinations & Health Risks [/SECTION]
5-6 bullet points: required and recommended vaccinations, endemic diseases, water safety, food safety.

[SECTION] Medical Tourism [/SECTION]
3-4 bullet points: if applicable, popular procedures, accredited hospitals, cost savings.

[SECTION] Emergency Procedures [/SECTION]
4-5 bullet points: what to do in an emergency, ambulance reliability, nearest hospitals, insurance claims.

{format_rules}
Target: 700-800 words.""",

        # ── RETIREMENT: Retiring abroad guide ──
        "retirement": f"""Generate a retirement guide for {name}.

{context}

This page answers: "Can I retire in {name}? What's it like for retirees?"

FORMAT:

[FACTBOX]
Retirement Visa Available: (Yes/No/Limited)
Monthly Budget (Comfortable): ($X,XXX USD)
Healthcare for Retirees: (good/adequate/limited)
Safety for Seniors: (High/Moderate/Low)
English-Friendly: (Yes/Moderate/No)
Expat Retiree Community: (Large/Growing/Small)
[/FACTBOX]

[SECTION] Why Retire in {name}? [/SECTION]
2-3 paragraphs: lifestyle appeal, cost advantages, climate, community.

[SECTION] Retirement Visa Options [/SECTION]
[TABLE]
| Visa Type | Age Requirement | Financial Requirement | Duration | Renewable? |
| --- | --- | --- | --- | --- |
(2-4 applicable visa types)
[/TABLE]

[SECTION] Cost of Retirement [/SECTION]
[TABLE]
| Category | Monthly Cost (USD) | Notes |
| --- | --- | --- |
| Housing | $X-X | ... |
| Food | $X-X | ... |
| Healthcare/Insurance | $X-X | ... |
| Transport | $X-X | ... |
| Entertainment | $X-X | ... |
| Utilities | $X-X | ... |
| **Total** | **$X,XXX-X,XXX** | ... |
[/TABLE]

[SECTION] Healthcare for Retirees [/SECTION]
4-5 bullet points: access to care, insurance options, quality of senior care, specialist availability.

[SECTION] Where Retirees Live [/SECTION]
4-5 areas/cities popular with retirees, with brief description and cost context.

[SECTION] Honest Assessment [/SECTION]
5-6 bullet points: pros and cons for retirees, common complaints, what surprises people.

{format_rules}
Target: 700-800 words.""",

        # ── DIGITAL NOMAD GUIDE ──
        "digital_nomad_guide": f"""Generate a digital nomad guide for {name}.

{context}

This page answers: "Is {name} good for digital nomads? What about visas, WiFi, and coworking?"

FORMAT:

[FACTBOX]
Digital Nomad Visa: (Yes/No/In Progress)
Average Internet Speed: (Mbps)
Coworking Spaces: (Many/Some/Few)
Monthly Cost (Nomad Budget): ($X,XXX USD)
Safety: (rating context)
Time Zone: (UTC offset)
[/FACTBOX]

[SECTION] Digital Nomad Overview [/SECTION]
2-3 paragraphs: overall suitability, nomad scene, community size, trending or established.

[SECTION] Visa Options for Remote Workers [/SECTION]
[TABLE]
| Visa Type | Duration | Income Requirement | Cost (USD) | Notes |
| --- | --- | --- | --- | --- |
(3-4 relevant visa types for remote workers)
[/TABLE]

[SECTION] Internet & Connectivity [/SECTION]
4-5 bullet points: speeds, reliability, SIM cards, backup options.

[SECTION] Coworking Spaces [/SECTION]
[TABLE]
| Space | City | Day Pass (USD) | Monthly (USD) | Notes |
| --- | --- | --- | --- | --- |
(4-6 popular coworking spaces)
[/TABLE]

[SECTION] Nomad-Friendly Cities [/SECTION]
For top 3-4 cities, briefly describe: vibe, cost, internet quality, community.

[SECTION] Monthly Budget Breakdown [/SECTION]
[TABLE]
| Category | Budget ($) | Comfortable ($) |
| --- | --- | --- |
| Accommodation | X | X |
| Food | X | X |
| Coworking | X | X |
| Transport | X | X |
| Entertainment | X | X |
| **Total** | **X** | **X** |
[/TABLE]

[SECTION] Tips & Warnings [/SECTION]
5-6 bullet points: tax implications, best neighborhoods, seasonal considerations, community resources.

{format_rules}
Target: 700-800 words.""",

        # ── HISTORY TIMELINE: Key events ──
        "history_timeline": f"""Generate a history reference page for {name}.

{context}

This page answers: "What is the history of {name}? What are the key events?"

FORMAT:

[SECTION] Historical Overview [/SECTION]
3-4 paragraphs: broad sweep from earliest known history to modern era. Cover pre-colonial, colonial (if applicable), independence, and modern periods.

[SECTION] Timeline of Key Events [/SECTION]
Numbered list of 15-20 major events in chronological order. Format each as:
1. **YEAR** - Event description (1-2 sentences)

Cover: ancient/pre-colonial era, colonial period, independence/formation, major wars or conflicts, political changes, modern milestones.

[SECTION] Founding & Formation [/SECTION]
2 paragraphs: how {name} became the entity it is today. Key figures, key moments.

[SECTION] Colonial & Independence Period [/SECTION]
2-3 paragraphs: colonial history (if applicable), independence movement, first leaders. If not applicable, cover the equivalent formative period.

[SECTION] Modern Era [/SECTION]
2-3 paragraphs: post-independence trajectory, major political changes, economic development, current direction.

[SECTION] Historical Figures [/SECTION]
[TABLE]
| Name | Period | Role | Significance |
| --- | --- | --- | --- |
(5-7 most important historical figures)
[/TABLE]

{format_rules}
Rules: Factual dates and events only. No moral judgments on historical events. State what happened and let readers draw conclusions.
Target: 800-900 words.""",

        # ── POLITICS & GOVERNMENT ──
        "politics_and_government": f"""Generate a politics and government reference page for {name}.

{context}

This page answers: "How is {name} governed? What's the political system?"

FORMAT:

[FACTBOX]
Government Type: (e.g. Federal Republic, Constitutional Monarchy, etc.)
Head of State: (title and current holder)
Head of Government: (title and current holder)
Legislature: (name, structure, seats)
Legal System: (common law/civil law/sharia/mixed)
Political Stability Index: (context)
Corruption Index: (Transparency International ranking context)
[/FACTBOX]

[SECTION] Political System [/SECTION]
2-3 paragraphs: how the government works, separation of powers, federal vs unitary.

[SECTION] Government Structure [/SECTION]
[TABLE]
| Branch | Institution | Head/Leader | Role |
| --- | --- | --- | --- |
| Executive | ... | ... | ... |
| Legislative | ... | ... | ... |
| Judicial | ... | ... | ... |
[/TABLE]

[SECTION] Major Political Parties [/SECTION]
[TABLE]
| Party | Position | Leader | Seats | Notes |
| --- | --- | --- | --- | --- |
(4-6 major parties)
[/TABLE]

[SECTION] Elections [/SECTION]
3-4 bullet points: electoral system, frequency, last election, next election, voter participation.

[SECTION] Political Stability & Challenges [/SECTION]
5-6 bullet points: current political climate, key issues, regional dynamics, freedom indices.

[SECTION] Foreign Relations [/SECTION]
4-5 bullet points: key alliances, international memberships (UN, EU, AU, ASEAN, etc.), diplomatic stance.

{format_rules}
Rules: Factual and neutral. State political positions without endorsing them. Use verified indices and rankings for context.
Target: 700-800 words.""",

        # ── DEMOGRAPHICS ──
        "demographics": f"""Generate a demographics reference page for {name}.

{context}

This page answers: "Who lives in {name}? What's the population breakdown?"

FORMAT:

[FACTBOX]
Total Population: ({pop} million)
Population Growth Rate: (%)
Median Age: (years)
Urban Population: (%)
Population Density: (per km2)
Life Expectancy: (years)
Fertility Rate: (children per woman)
[/FACTBOX]

[SECTION] Population Overview [/SECTION]
2-3 paragraphs: population size in context, growth trends, urbanization, migration patterns.

[SECTION] Ethnic Groups [/SECTION]
[TABLE]
| Ethnic Group | Percentage | Region | Notes |
| --- | --- | --- | --- |
(5-8 major ethnic groups)
[/TABLE]
1 paragraph on ethnic relations and diversity context.

[SECTION] Languages [/SECTION]
4-5 bullet points: official language(s), regional languages, lingua franca, endangered languages.

[SECTION] Religions [/SECTION]
[TABLE]
| Religion | Percentage | Notes |
| --- | --- | --- |
(4-6 major religions/denominations)
[/TABLE]
1 paragraph on religious freedom and interfaith relations.

[SECTION] Age Distribution [/SECTION]
[TABLE]
| Age Group | Percentage | Implications |
| --- | --- | --- |
| 0-14 | X% | ... |
| 15-24 | X% | ... |
| 25-54 | X% | ... |
| 55-64 | X% | ... |
| 65+ | X% | ... |
[/TABLE]

[SECTION] Urbanization & Major Cities [/SECTION]
4-5 bullet points: urban vs rural split, fastest-growing cities, migration trends, diaspora.

{format_rules}
Rules: Use latest available estimates. Cite approximate percentages. Handle ethnic/religious data respectfully and factually.
Target: 700-800 words.""",

        # ── INFRASTRUCTURE ──
        "infrastructure": f"""Generate an infrastructure reference page for {name}.

{context}

This page answers: "What is the infrastructure like in {name}? Roads, power, water?"

FORMAT:

[FACTBOX]
Electricity Access: (% of population)
Internet Penetration: (%)
Road Network: (km, quality context)
Rail Network: (km or none)
Major Airports: (count)
Major Ports: (count or landlocked)
[/FACTBOX]

[SECTION] Infrastructure Overview [/SECTION]
2-3 paragraphs: overall development level, recent investments, urban vs rural gap.

[SECTION] Transport Infrastructure [/SECTION]
[TABLE]
| Type | Coverage | Quality | Notes |
| --- | --- | --- | --- |
| Roads | X km | Good/Moderate/Poor | ... |
| Railways | X km | ... | ... |
| Airports | X international, X domestic | ... | ... |
| Ports | X major | ... | ... |
[/TABLE]

[SECTION] Energy & Electricity [/SECTION]
4-5 bullet points: power generation sources, reliability, outages, renewable energy progress.

[SECTION] Water & Sanitation [/SECTION]
4-5 bullet points: tap water safety, sanitation coverage, water access in rural areas.

[SECTION] Telecommunications [/SECTION]
4-5 bullet points: mobile coverage, fiber/broadband, 4G/5G rollout, postal services.

[SECTION] Development Projects [/SECTION]
4-5 bullet points: major ongoing or planned infrastructure projects, funding sources, timeline.

{format_rules}
Target: 600-700 words.""",

        # ── BUSINESS & INVESTMENT ──
        "business_and_investment": f"""Generate a doing-business and investment guide for {name}.

{context}

This page answers: "How easy is it to do business in {name}? What are the investment opportunities?"

FORMAT:

[FACTBOX]
Ease of Doing Business: (World Bank ranking context)
Corporate Tax Rate: (%)
FDI Inflow: ($X billion/million annual)
Special Economic Zones: (Yes/No, count)
Key Industries: (top 3)
Currency Stability: (Stable/Moderate/Volatile)
[/FACTBOX]

[SECTION] Business Environment [/SECTION]
2-3 paragraphs: overall climate, government attitude toward foreign investment, bureaucracy level, corruption context.

[SECTION] Starting a Business [/SECTION]
[TABLE]
| Step | Requirement | Time | Cost (USD) |
| --- | --- | --- | --- |
(6-8 steps to register and start a business)
[/TABLE]

[SECTION] Investment Opportunities [/SECTION]
[TABLE]
| Sector | Opportunity | Growth Potential | Notes |
| --- | --- | --- | --- |
(5-7 key sectors with investment potential)
[/TABLE]

[SECTION] Foreign Direct Investment [/SECTION]
4-5 bullet points: FDI trends, main investing countries, incentives, restricted sectors.

[SECTION] Legal & Regulatory Framework [/SECTION]
5-6 bullet points: business laws, intellectual property protection, labor laws, dispute resolution.

[SECTION] Challenges & Risks [/SECTION]
5-6 bullet points: honest assessment of business risks, political risk, market limitations, currency risks.

[SECTION] Free Zones & Incentives [/SECTION]
3-4 bullet points: special economic zones, tax incentives, investment promotion agencies.

{format_rules}
Rules: Balanced assessment. Include both opportunities and realistic challenges.
Target: 800-900 words.""",
    }

    # ── COST SUB-ANGLE PROMPTS ──
    # Inject World Bank data as context for cost pages
    wb_context = ""
    try:
        from data_enrichment import fetch_worldbank_indicators
        wb_data = fetch_worldbank_indicators(entity.get("iso_code", ""))
        if wb_data and wb_data.get("indicators"):
            ind = wb_data["indicators"]
            wb_lines = []
            if "NY.GDP.PCAP.PP.CD" in ind:
                wb_lines.append(f"GDP per capita PPP: ${ind['NY.GDP.PCAP.PP.CD']['value']:,.0f} ({ind['NY.GDP.PCAP.PP.CD']['year']})")
            if "FP.CPI.TOTL.ZG" in ind:
                wb_lines.append(f"Inflation rate: {ind['FP.CPI.TOTL.ZG']['value']:.1f}% ({ind['FP.CPI.TOTL.ZG']['year']})")
            if "SH.XPD.CHEX.PC.CD" in ind:
                wb_lines.append(f"Health expenditure per capita: ${ind['SH.XPD.CHEX.PC.CD']['value']:,.0f} ({ind['SH.XPD.CHEX.PC.CD']['year']})")
            if "SH.XPD.OOPC.CH.ZS" in ind:
                wb_lines.append(f"Out-of-pocket health spend: {ind['SH.XPD.OOPC.CH.ZS']['value']:.1f}% ({ind['SH.XPD.OOPC.CH.ZS']['year']})")
            if "SE.XPD.TOTL.GD.ZS" in ind:
                wb_lines.append(f"Education spend (% of GDP): {ind['SE.XPD.TOTL.GD.ZS']['value']:.1f}% ({ind['SE.XPD.TOTL.GD.ZS']['year']})")
            if wb_lines:
                wb_context = "\n\nWORLD BANK DATA (use these real figures in your response):\n" + "\n".join(wb_lines)
    except ImportError:
        pass

    cost_prompts = {
        # ── COST-RENT-HOUSING ──
        "cost_rent_housing": f"""Generate a rent and housing prices reference page for {name}.

{context}{wb_context}
Local currency: {currency}

This page answers: "How much does rent cost in {name}? What are housing prices?"

FORMAT:

[FACTBOX]
GDP per Capita (PPP): (use World Bank figure if available, otherwise estimate)
Affordability Rating: (Very Affordable / Affordable / Moderate / Expensive / Very Expensive)
Average Monthly Rent (1BR, City Center): ($X USD / local equivalent)
Average Monthly Rent (1BR, Outside Center): ($X USD / local equivalent)
Property Purchase (per sqm, City Center): ($X USD)
Currency: {currency}
[/FACTBOX]

[SECTION] Housing Market Overview [/SECTION]
2 paragraphs: rental market conditions, typical lease terms, deposit requirements, tenant rights. How {name}'s housing costs compare to regional neighbors.

[SECTION] Apartment Rental Prices [/SECTION]
[TABLE]
| Apartment Type | City Center (USD/month) | Outside Center (USD/month) | Notes |
| --- | --- | --- | --- |
| Studio / Bedsitter | $X-X | $X-X | (typical quality) |
| 1 Bedroom | $X-X | $X-X | (what to expect) |
| 2 Bedroom | $X-X | $X-X | (family size) |
| 3 Bedroom | $X-X | $X-X | (spacious) |
[/TABLE]

[SECTION] Property Purchase Prices [/SECTION]
[TABLE]
| Area Type | Price per sqm (USD) | Notes |
| --- | --- | --- |
| City Center | $X-X | (prime locations) |
| Suburbs | $X-X | (residential areas) |
| Rural | $X-X | (if applicable) |
[/TABLE]

[SECTION] Best Neighborhoods for Expats [/SECTION]
4-5 bullet points naming specific neighborhoods in the capital or largest city, with typical rent range and character description.

[SECTION] Renter Tips for {name} [/SECTION]
5-6 bullet points: how to find housing, negotiation tips, scams to avoid, utilities usually included or not, furnished vs unfurnished norms.

{format_rules}
Rules: All prices in USD with local currency equivalent where helpful. Prices are approximate guides.
Target: 700-800 words.""",

        # ── COST-FOOD-GROCERIES ──
        "cost_food_groceries": f"""Generate a food and grocery prices reference page for {name}.

{context}{wb_context}
Local currency: {currency}

This page answers: "How much does food cost in {name}? What do groceries cost?"

FORMAT:

[FACTBOX]
Meal at Inexpensive Restaurant: ($X USD)
Meal for 2 at Mid-Range Restaurant: ($X USD)
Monthly Grocery Budget (1 person): ($X-X USD)
Local Beer (500ml): ($X USD)
Currency: {currency}
[/FACTBOX]

[SECTION] Food Costs Overview [/SECTION]
2 paragraphs: how food prices in {name} compare to regional average, what drives prices up or down, eating-out culture vs home cooking.

[SECTION] Grocery Prices [/SECTION]
[TABLE]
| Item | Price (USD) | Local Price | Notes |
| --- | --- | --- | --- |
| Milk (1 liter) | $X | X {currency} | |
| Bread (white loaf) | $X | X {currency} | |
| Eggs (dozen) | $X | X {currency} | |
| Rice (1 kg) | $X | X {currency} | |
| Chicken breast (1 kg) | $X | X {currency} | |
| Beef (1 kg) | $X | X {currency} | |
| Apples (1 kg) | $X | X {currency} | |
| Tomatoes (1 kg) | $X | X {currency} | |
| Potatoes (1 kg) | $X | X {currency} | |
| Onions (1 kg) | $X | X {currency} | |
| Local cheese (1 kg) | $X | X {currency} | |
| Water (1.5L bottle) | $X | X {currency} | |
[/TABLE]

[SECTION] Restaurant Prices [/SECTION]
[TABLE]
| Meal Type | Price Range (USD) | Notes |
| --- | --- | --- |
| Street Food / Local Eatery | $X-X | (typical dishes) |
| Casual Restaurant | $X-X | (one person) |
| Mid-Range Restaurant (2 people) | $X-X | (3 courses) |
| Fine Dining (2 people) | $X-X | (upscale) |
| Local Beer (draft, 500ml) | $X-X | |
| Imported Beer (330ml) | $X-X | |
| Cappuccino | $X-X | |
| Soft Drink (can) | $X-X | |
[/TABLE]

[SECTION] Supermarket vs Local Market [/SECTION]
2 paragraphs: price difference between supermarkets and open-air markets, what to buy where, bargaining norms.

[SECTION] Local Food Tips [/SECTION]
5-6 bullet points: cheapest ways to eat, local staples that are good value, what to avoid buying imported.

{format_rules}
Rules: All prices in USD with local currency equivalent. Prices are approximate guides based on typical costs.
Target: 700-800 words.""",

        # ── COST-HEALTHCARE ──
        "cost_healthcare": f"""Generate a healthcare costs reference page for {name}.

{context}{wb_context}
Local currency: {currency}

This page answers: "How much does healthcare cost in {name}? What does insurance cost?"

FORMAT:

[FACTBOX]
Health Expenditure per Capita: (use World Bank figure if available)
Out-of-Pocket Spend: (use World Bank figure if available)
Healthcare System: (Universal / Mixed / Private / Public)
Emergency Number: (local emergency number)
Insurance Required: (Yes/No/Recommended)
Currency: {currency}
[/FACTBOX]

[SECTION] Healthcare System Overview [/SECTION]
2 paragraphs: public vs private healthcare quality, how the system works for locals vs foreigners, whether you need insurance.

[SECTION] Medical Visit Costs [/SECTION]
[TABLE]
| Service | Public (USD) | Private (USD) | Notes |
| --- | --- | --- | --- |
| GP / Doctor Visit | $X-X | $X-X | |
| Specialist Consultation | $X-X | $X-X | |
| Dental Checkup | $X-X | $X-X | |
| Eye Exam | $X-X | $X-X | |
| Blood Test (basic panel) | $X-X | $X-X | |
[/TABLE]

[SECTION] Hospital & Procedure Costs [/SECTION]
[TABLE]
| Procedure | Cost Range (USD) | Notes |
| --- | --- | --- |
| Emergency Room Visit | $X-X | |
| Hospital Stay (per night) | $X-X | |
| Basic Surgery | $X-X | |
| Childbirth (normal delivery) | $X-X | |
| MRI Scan | $X-X | |
| X-Ray | $X-X | |
[/TABLE]

[SECTION] Health Insurance [/SECTION]
[TABLE]
| Coverage Type | Monthly Cost (USD) | What It Covers |
| --- | --- | --- |
| Basic Local Insurance | $X-X | (outline) |
| Comprehensive Private | $X-X | (outline) |
| International / Expat | $X-X | (outline) |
[/TABLE]

[SECTION] Pharmacy & Medication Costs [/SECTION]
5-6 bullet points: common medication prices, prescription rules, pharmacy availability, over-the-counter norms.

[SECTION] Emergency Care [/SECTION]
2 paragraphs: what to do in a medical emergency, ambulance availability, best hospitals for foreigners.

{format_rules}
Rules: All prices in USD. Distinguish public vs private costs. Note that prices vary by city.
Target: 700-800 words.""",

        # ── COST-TRANSPORTATION ──
        "cost_transportation": f"""Generate a transportation costs reference page for {name}.

{context}{wb_context}
Local currency: {currency}

This page answers: "How much does transportation cost in {name}?"

FORMAT:

[FACTBOX]
Monthly Transit Pass: ($X USD)
Taxi Start Rate: ($X USD)
Fuel (per liter): ($X USD)
Ride-Hailing Available: (Yes/No — name apps)
Currency: {currency}
[/FACTBOX]

[SECTION] Getting Around Overview [/SECTION]
2 paragraphs: main transportation modes, quality of public transit, how most people get around.

[SECTION] Public Transportation [/SECTION]
[TABLE]
| Transport Type | Single Fare (USD) | Monthly Pass (USD) | Notes |
| --- | --- | --- | --- |
| City Bus | $X | $X | (coverage quality) |
| Metro / Subway | $X | $X | (if available) |
| Minibus / Shared Taxi | $X | N/A | (routes) |
| Commuter Train | $X-X | $X | (if available) |
[/TABLE]

[SECTION] Taxi & Ride-Hailing [/SECTION]
[TABLE]
| Service | Base Fare (USD) | Per km (USD) | Typical City Ride (USD) | Notes |
| --- | --- | --- | --- | --- |
| Metered Taxi | $X | $X | $X-X | |
| Ride-Hailing App | $X | $X | $X-X | (which apps) |
| Airport Transfer | N/A | N/A | $X-X | (to city center) |
[/TABLE]

[SECTION] Fuel & Driving Costs [/SECTION]
[TABLE]
| Item | Cost (USD) | Notes |
| --- | --- | --- |
| Gasoline (per liter) | $X | |
| Diesel (per liter) | $X | |
| Car Rental (per day) | $X-X | (economy car) |
| Parking (per hour, city) | $X-X | |
| Toll Roads (typical) | $X-X | (if applicable) |
[/TABLE]

[SECTION] Intercity & Long-Distance [/SECTION]
[TABLE]
| Route Type | Cost Range (USD) | Notes |
| --- | --- | --- |
| Intercity Bus (4-5 hrs) | $X-X | |
| Domestic Flight | $X-X | (typical route) |
| Train (long-distance) | $X-X | (if available) |
[/TABLE]

[SECTION] Transport Tips [/SECTION]
5-6 bullet points: saving money on transport, apps to use, safety advice, negotiating taxi fares.

{format_rules}
Rules: All prices in USD with local currency where helpful. Note variation between cities.
Target: 600-700 words.""",

        # ── COST-EDUCATION ──
        "cost_education": f"""Generate an education costs reference page for {name}.

{context}{wb_context}
Local currency: {currency}

This page answers: "How much does education cost in {name}? What are school fees and tuition?"

FORMAT:

[FACTBOX]
Education Spend (% GDP): (use World Bank figure if available)
Literacy Rate: (approximate %)
School System: (years of compulsory education)
Academic Year: (months)
Currency: {currency}
[/FACTBOX]

[SECTION] Education System Overview [/SECTION]
2 paragraphs: public vs private education quality, language of instruction, compulsory education years, international school availability.

[SECTION] School Fees [/SECTION]
[TABLE]
| School Type | Annual Fee (USD) | Notes |
| --- | --- | --- |
| Public Primary | $X (free/subsidized) | (quality notes) |
| Private Primary | $X-X | (range by tier) |
| Public Secondary | $X (free/subsidized) | (quality notes) |
| Private Secondary | $X-X | (range by tier) |
| International School | $X-X | (curriculum types) |
[/TABLE]

[SECTION] University Tuition [/SECTION]
[TABLE]
| Institution Type | Annual Tuition - Local (USD) | Annual Tuition - International (USD) | Notes |
| --- | --- | --- | --- |
| Public University | $X-X | $X-X | |
| Private University | $X-X | $X-X | |
| Top-Ranked University | $X-X | $X-X | (name if applicable) |
[/TABLE]

[SECTION] Other Education Costs [/SECTION]
[TABLE]
| Item | Cost (USD) | Notes |
| --- | --- | --- |
| Preschool / Daycare (monthly) | $X-X | |
| Private Tutoring (per hour) | $X-X | |
| Language Course (monthly) | $X-X | |
| School Supplies (annual) | $X-X | |
| School Uniform | $X-X | |
[/TABLE]

[SECTION] Education Quality & Tips [/SECTION]
5-6 bullet points: best schools for expats, scholarship availability, online learning options, education quality compared to region.

{format_rules}
Rules: All prices in USD. Distinguish between local and international student fees where applicable.
Target: 600-700 words.""",

        # ── COST-UTILITIES-INTERNET ──
        "cost_utilities_internet": f"""Generate a utility and internet costs reference page for {name}.

{context}{wb_context}
Local currency: {currency}

This page answers: "How much do utilities and internet cost in {name}?"

FORMAT:

[FACTBOX]
Monthly Utilities (85 sqm apt): ($X USD)
Internet (60 Mbps): ($X USD/month)
Mobile Data (10GB): ($X USD/month)
Electricity Cost: ($X per kWh)
Currency: {currency}
[/FACTBOX]

[SECTION] Utility Costs Overview [/SECTION]
2 paragraphs: utility infrastructure quality, whether costs are stable or fluctuating, seasonal variation.

[SECTION] Monthly Utility Bills [/SECTION]
[TABLE]
| Utility | Small Apt (45 sqm) | Medium Apt (85 sqm) | Large Apt (120 sqm) | Notes |
| --- | --- | --- | --- | --- |
| Electricity | $X | $X | $X | |
| Water | $X | $X | $X | |
| Gas / Heating | $X | $X | $X | |
| Garbage / Municipal | $X | $X | $X | (if separate) |
| **Total** | **$X** | **$X** | **$X** | |
[/TABLE]

[SECTION] Internet & Phone Plans [/SECTION]
[TABLE]
| Service | Monthly Cost (USD) | Speed / Allowance | Provider Examples |
| --- | --- | --- | --- |
| Fiber Internet (basic) | $X-X | X Mbps | |
| Fiber Internet (fast) | $X-X | X Mbps | |
| Mobile Data (prepaid) | $X-X | X GB | |
| Mobile Data (postpaid) | $X-X | X GB | |
| Phone + Internet Bundle | $X-X | varies | |
[/TABLE]

[SECTION] Streaming & Digital Services [/SECTION]
[TABLE]
| Service | Monthly Cost (USD) | Notes |
| --- | --- | --- |
| Netflix (standard) | $X | |
| Spotify (premium) | $X | |
| Local Streaming | $X | (if applicable) |
[/TABLE]

[SECTION] Utility Tips [/SECTION]
4-5 bullet points: how to set up utilities, prepaid vs postpaid electricity, best internet providers, saving on bills.

{format_rules}
Rules: All prices in USD. Note seasonal variation where applicable.
Target: 500-600 words.""",

        # ── COST-MONTHLY-BUDGET ──
        "cost_monthly_budget": f"""Generate a comprehensive monthly budget guide for {name}.

{context}{wb_context}
Local currency: {currency}

This page answers: "How much money do I need per month to live in {name}?"

FORMAT:

[FACTBOX]
GDP per Capita (PPP): (use World Bank figure if available)
Budget Living (monthly): ($X USD)
Mid-Range Living (monthly): ($X USD)
Comfortable Living (monthly): ($X USD)
Average Local Salary: ($X USD/month, approximate)
Currency: {currency}
[/FACTBOX]

[SECTION] Cost of Living Overview [/SECTION]
2 paragraphs: overall affordability of {name} using GDP PPP as anchor, how far different budgets go, comparison to neighboring countries.

[SECTION] Monthly Budget Breakdown [/SECTION]
[TABLE]
| Category | Budget ($) | Mid-Range ($) | Comfortable ($) | Notes |
| --- | --- | --- | --- | --- |
| Rent (1BR apartment) | X | X | X | (budget=shared/outside, mid=1BR center, comfortable=nice 2BR) |
| Food & Groceries | X | X | X | (budget=cook mostly, mid=mix, comfortable=eat out often) |
| Transportation | X | X | X | (budget=public only, mid=mix, comfortable=taxi/car) |
| Utilities & Internet | X | X | X | (electricity, water, internet, phone) |
| Healthcare / Insurance | X | X | X | (budget=public only, comfortable=private) |
| Entertainment & Social | X | X | X | (going out, hobbies, gym) |
| Clothing & Personal | X | X | X | |
| Savings / Misc | X | X | X | |
| **Total** | **X** | **X** | **X** | |
[/TABLE]

[SECTION] Budget Tier Lifestyles [/SECTION]
3 paragraphs (one per tier): what daily life looks like at each budget level. Be specific about what you can and cannot afford.

[SECTION] Cost Comparison by City [/SECTION]
[TABLE]
| City | Rent (1BR) | Food (monthly) | Transport | Overall Level |
| --- | --- | --- | --- | --- |
| (capital/largest) | $X | $X | $X | (Expensive/Moderate/Cheap) |
| (second city) | $X | $X | $X | |
| (third city or tourist hub) | $X | $X | $X | |
[/TABLE]

[SECTION] Money-Saving Strategies [/SECTION]
6-8 bullet points: specific, actionable tips for reducing costs in {name}. Include local knowledge.

[SECTION] Is {name} Affordable? [/SECTION]
2 paragraphs: honest assessment of who {name} is affordable for (digital nomads, retirees, students, families), and who might find it expensive.

{format_rules}
Rules: All prices in USD. Budget tiers should be realistic and internally consistent. Use GDP PPP data to anchor estimates.
Target: 800-900 words.""",

        # ── COST-COMPARISON ──
        "cost_comparison": f"""Generate a cost of living comparison page: {name} vs {comparison_entity or '[Other Country]'}.

{context}
Local currency: {currency}

{"Comparison country: " + comparison_entity if comparison_entity else ""}

This page answers: "Is {name} cheaper or more expensive than {comparison_entity or 'the other country'}? How do costs compare?"

FORMAT:

[FACTBOX]
{name} GDP per Capita (PPP): (use real figure if available)
{comparison_entity or 'Other'} GDP per Capita (PPP): (use real figure if available)
{name} Inflation Rate: (use real figure if available)
{comparison_entity or 'Other'} Inflation Rate: (use real figure if available)
Overall Winner (Cheaper): (which country)
[/FACTBOX]

[SECTION] Overview: {name} vs {comparison_entity or 'Other'} [/SECTION]
2 paragraphs: high-level comparison of cost levels, economic context, which country is generally cheaper and by roughly how much.

[SECTION] Rent & Housing Comparison [/SECTION]
[TABLE]
| Item | {name} (USD) | {comparison_entity or 'Other'} (USD) | Difference |
| --- | --- | --- | --- |
| 1BR Apartment (City Center) | $X | $X | X% cheaper/more |
| 1BR Apartment (Outside) | $X | $X | X% cheaper/more |
| 3BR Apartment (City Center) | $X | $X | X% cheaper/more |
[/TABLE]

[SECTION] Food & Dining Comparison [/SECTION]
[TABLE]
| Item | {name} (USD) | {comparison_entity or 'Other'} (USD) | Difference |
| --- | --- | --- | --- |
| Meal at Restaurant | $X | $X | X% |
| Groceries (monthly) | $X | $X | X% |
| Beer (500ml) | $X | $X | X% |
| Coffee | $X | $X | X% |
[/TABLE]

[SECTION] Transport Comparison [/SECTION]
[TABLE]
| Item | {name} (USD) | {comparison_entity or 'Other'} (USD) | Difference |
| --- | --- | --- | --- |
| Monthly Transit Pass | $X | $X | X% |
| Taxi (per km) | $X | $X | X% |
| Fuel (per liter) | $X | $X | X% |
[/TABLE]

[SECTION] Utilities & Internet Comparison [/SECTION]
[TABLE]
| Item | {name} (USD) | {comparison_entity or 'Other'} (USD) | Difference |
| --- | --- | --- | --- |
| Utilities (85 sqm apt) | $X | $X | X% |
| Internet (60 Mbps) | $X | $X | X% |
| Mobile Plan | $X | $X | X% |
[/TABLE]

[SECTION] Monthly Budget Comparison [/SECTION]
[TABLE]
| Budget Tier | {name} (USD) | {comparison_entity or 'Other'} (USD) | Savings |
| --- | --- | --- | --- |
| Budget | $X | $X | X% |
| Mid-Range | $X | $X | X% |
| Comfortable | $X | $X | X% |
[/TABLE]

[SECTION] Where Each Country Wins [/SECTION]
2 subsections:
- **{name} is cheaper for:** 3-4 bullet points with specific categories
- **{comparison_entity or 'Other'} is cheaper for:** 3-4 bullet points with specific categories

[SECTION] Bottom Line [/SECTION]
1-2 paragraphs: which country offers better value for different lifestyles (expats, students, retirees, families).

{format_rules}
Rules: All prices in USD. Show percentage differences. Be balanced and factual.
Target: 800-900 words.""",
    }

    prompts.update(cost_prompts)

    return prompts.get(angle_id, prompts["overview"])


# =============================================================================
# HTML TEMPLATE
# =============================================================================

def build_html(entity, angle_id, title, content, breadcrumbs=None, enriched_data=None):
    """Build themed HTML page for a country angle with two-column layout."""
    continent = entity.get("continent", "europe")
    colors = CONTINENT_COLORS.get(continent, CONTINENT_COLORS["europe"])
    flag = iso_to_flag(entity.get("iso_code", ""))
    entity_name = entity["name"]

    # Convert content to HTML paragraphs
    html_content = content_to_html(content)

    # Generate TOC
    toc_html = generate_toc_html(content)

    # Build verified factbox from enriched data
    verified_factbox_html = ""
    if enriched_data:
        from data_enrichment import build_verified_factbox
        verified_factbox_html = build_verified_factbox(entity, enriched_data)

    # Add World Bank cost factbox for cost-related pages
    cost_related_angles = {"cost-of-living", "cost-rent-housing", "cost-food-groceries",
                           "cost-healthcare", "cost-transportation", "cost-education",
                           "cost-utilities-internet", "cost-monthly-budget"}
    if angle_id in cost_related_angles or angle_id.startswith("cost-compare-"):
        try:
            from data_enrichment import fetch_worldbank_indicators, build_cost_factbox
            wb_data = fetch_worldbank_indicators(entity.get("iso_code", ""))
            wb_factbox = build_cost_factbox(entity, wb_data)
            if wb_factbox:
                verified_factbox_html += "\n" + wb_factbox
        except ImportError:
            pass

    # Generate related links
    related_links_html = build_related_links(entity)

    # Build cost-specific linking HTML
    cost_hub_links_html = ""
    cost_cross_links_html = ""
    cost_sub_angle_ids = []
    cost_registry_path = BASE_DIR / "cost_angle_registry.json"
    if cost_registry_path.exists():
        try:
            _cost_reg = json.loads(cost_registry_path.read_text(encoding="utf-8"))
            cost_sub_angle_ids = list(_cost_reg.get("cost_angles", {}).keys())
        except (json.JSONDecodeError, OSError):
            pass

    if angle_id == "cost-of-living":
        # Hub page gets "Detailed Cost Guides" grid
        cost_hub_links_html = build_cost_hub_links(entity)
    elif angle_id in cost_sub_angle_ids:
        # Cost sub-pages get "Related Cost Guides" footer
        cost_cross_links_html = build_cost_cross_links(entity, angle_id)
    elif angle_id == "economy":
        # Economy page links to cost pages
        entity_slug_tmp = slugify(entity_name)
        econ_links = []
        for link_id, link_label in [("cost-of-living", "Cost of Living"), ("cost-monthly-budget", "Monthly Budget Guide")]:
            link_page = OUTPUT_DIR / continent / entity_slug_tmp / f"{link_id}.html"
            if link_page.exists():
                econ_links.append(f'<a href="/{continent}/{entity_slug_tmp}/{link_id}.html">{link_label}</a>')
        if econ_links:
            cost_cross_links_html = f'<div style="margin-top:24px;padding:16px 20px;background:#F3F4F6;border-radius:8px;font-size:14px;"><strong>Related:</strong> {" &middot; ".join(econ_links)}</div>'
    elif angle_id in ("moving-there", "real-estate", "healthcare"):
        # These pages link to relevant cost pages
        entity_slug_tmp = slugify(entity_name)
        link_map = {
            "moving-there": [("cost-of-living", "Cost of Living")],
            "real-estate": [("cost-rent-housing", "Rent & Housing Prices")],
            "healthcare": [("cost-healthcare", "Healthcare Costs")],
        }
        outbound_links = []
        for link_id, link_label in link_map.get(angle_id, []):
            link_page = OUTPUT_DIR / continent / entity_slug_tmp / f"{link_id}.html"
            if link_page.exists():
                outbound_links.append(f'<a href="/{continent}/{entity_slug_tmp}/{link_id}.html">{link_label}</a>')
        if outbound_links:
            cost_cross_links_html = f'<div style="margin-top:24px;padding:16px 20px;background:#F3F4F6;border-radius:8px;font-size:14px;"><strong>Related:</strong> {" &middot; ".join(outbound_links)}</div>'

    # Build breadcrumb HTML
    if not breadcrumbs:
        breadcrumbs = [
            ("Home", "/"),
            (colors["name"], f"/{continent}/"),
            (entity_name, f"/{continent}/{slugify(entity_name)}/"),
            (angle_id.replace("-", " ").title(), None),
        ]

    breadcrumb_html = ' <span>&rsaquo;</span> '.join(
        f'<a href="{url}">{label}</a>' if url else f'<span class="current">{label}</span>'
        for label, url in breadcrumbs
    )

    # Build sidebar angle navigation
    angle_registry = load_angle_registry()
    angles = angle_registry.get("angles", {})
    angle_nav_items = []
    entity_slug = slugify(entity_name)

    # Load cost sub-angle labels for sidebar
    cost_registry_path = BASE_DIR / "cost_angle_registry.json"
    cost_sidebar_labels = {}
    cost_sub_angle_ids = []
    if cost_registry_path.exists():
        try:
            cost_reg = json.loads(cost_registry_path.read_text(encoding="utf-8"))
            cost_sidebar_labels = cost_reg.get("sidebar_labels", {})
            cost_sub_angle_ids = list(cost_reg.get("cost_angles", {}).keys())
        except (json.JSONDecodeError, OSError):
            pass

    for aid, aconfig in angles.items():
        if aid == "vs":
            continue
        angle_label = aid.replace("-", " ").title()
        angle_page = OUTPUT_DIR / continent / entity_slug / f"{aid}.html"
        if aid == angle_id:
            angle_nav_items.append(
                f'<li><a href="/{continent}/{entity_slug}/{aid}.html" class="active">{angle_label}</a></li>'
            )
        elif angle_page.exists():
            angle_nav_items.append(
                f'<li><a href="/{continent}/{entity_slug}/{aid}.html">{angle_label}</a></li>'
            )

        # After "Cost Of Living", insert indented cost sub-angle links
        if aid == "cost-of-living" and cost_sub_angle_ids:
            for csub_id in cost_sub_angle_ids:
                csub_label = cost_sidebar_labels.get(csub_id, csub_id.replace("-", " ").title())
                csub_page = OUTPUT_DIR / continent / entity_slug / f"{csub_id}.html"
                if csub_id == angle_id:
                    angle_nav_items.append(
                        f'<li><a href="/{continent}/{entity_slug}/{csub_id}.html" class="active" style="padding-left:28px;font-size:13px;">{csub_label}</a></li>'
                    )
                elif csub_page.exists():
                    angle_nav_items.append(
                        f'<li><a href="/{continent}/{entity_slug}/{csub_id}.html" style="padding-left:28px;font-size:13px;">{csub_label}</a></li>'
                    )
    angle_nav_html = "\n                ".join(angle_nav_items)

    # Continent nav links for header
    continent_nav = ""
    for cslug, cmeta in CONTINENT_COLORS.items():
        if cslug == "antarctica":
            continue
        active_cls = ' class="active"' if cslug == continent else ""
        continent_nav += f'<li><a href="/{cslug}/"{active_cls}>{cmeta["name"]}</a></li>\n            '

    meta_desc = f"{title} - Comprehensive guide to {entity_name}. {SITE_NAME}."
    canonical_url = f"{SITE_URL}/{continent}/{entity_slug}/{angle_id}.html"

    # JSON-LD: BreadcrumbList
    breadcrumb_items = []
    for i, (label, url) in enumerate(breadcrumbs):
        item = {
            "@type": "ListItem",
            "position": i + 1,
            "name": label,
        }
        if url:
            item["item"] = f"{SITE_URL}{url}"
        breadcrumb_items.append(item)

    breadcrumb_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": breadcrumb_items,
    }, ensure_ascii=False)

    # JSON-LD: Article
    angle_label = angle_id.replace("-", " ").title()
    article_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": meta_desc,
        "url": canonical_url,
        "mainEntityOfPage": canonical_url,
        "author": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_URL,
        },
        "datePublished": datetime.now().strftime("%Y-%m-%d"),
        "dateModified": datetime.now().strftime("%Y-%m-%d"),
        "about": {
            "@type": "Country",
            "name": entity_name,
        },
        "articleSection": angle_label,
    }, ensure_ascii=False)

    # JSON-LD: Country (only on overview pages)
    country_ld_tag = ""
    if angle_id == "overview":
        country_data = {
            "@context": "https://schema.org",
            "@type": "Country",
            "name": entity_name,
            "url": canonical_url,
        }
        if entity.get("iso_code"):
            country_data["identifier"] = entity["iso_code"]
        if entity.get("capital"):
            country_data["containsPlace"] = {
                "@type": "City",
                "name": entity["capital"],
            }
        if entity.get("languages"):
            langs = entity["languages"]
            if isinstance(langs, list):
                country_data["knowsLanguage"] = langs
        country_ld_tag = f'\n    <script type="application/ld+json">{json.dumps(country_data, ensure_ascii=False)}</script>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{meta_desc}">
    <link rel="canonical" href="{canonical_url}">
    <title>{title} | {SITE_NAME}</title>
    <script type="application/ld+json">{breadcrumb_ld}</script>
    <script type="application/ld+json">{article_ld}</script>{country_ld_tag}
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.7;
            color: #2d3436;
            background: #FAFBFC;
            -webkit-font-smoothing: antialiased;
        }}
        a {{ color: {colors['primary']}; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}

        /* === Sticky Header === */
        .site-header {{
            background: #1F2937;
            position: sticky;
            top: 0;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .header-inner {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 24px;
            height: 56px;
        }}
        .site-logo {{
            font-size: 19px;
            font-weight: 700;
            color: #fff;
            text-decoration: none;
            letter-spacing: -0.5px;
        }}
        .site-logo:hover {{ text-decoration: none; opacity: 0.9; }}
        .site-logo span {{ color: {colors['primary']}; }}
        .continent-nav {{ display: flex; gap: 4px; list-style: none; }}
        .continent-nav a {{
            color: rgba(255,255,255,0.8);
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s, color 0.2s;
            text-decoration: none;
            white-space: nowrap;
        }}
        .continent-nav a:hover {{ background: rgba(255,255,255,0.12); color: #fff; text-decoration: none; }}
        .continent-nav a.active {{ background: rgba(255,255,255,0.18); color: #fff; }}

        /* Mobile hamburger */
        .menu-toggle {{ display: none; background: none; border: none; cursor: pointer; padding: 8px; }}
        .menu-toggle span, .menu-toggle span::before, .menu-toggle span::after {{
            display: block; width: 22px; height: 2px; background: #fff; position: relative; transition: 0.3s;
        }}
        .menu-toggle span::before, .menu-toggle span::after {{ content: ''; position: absolute; left: 0; }}
        .menu-toggle span::before {{ top: -7px; }}
        .menu-toggle span::after {{ top: 7px; }}
        #mobile-menu-state {{ display: none; }}

        /* === Title Banner === */
        .page-banner {{
            background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']});
            color: white;
            padding: 28px 0;
        }}
        .banner-inner {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
        }}
        .page-banner h1 {{
            font-size: 28px;
            font-weight: 700;
        }}
        .flag {{ font-size: 1.3em; margin-right: 8px; }}

        /* === Breadcrumbs === */
        .breadcrumbs {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 14px 24px;
            font-size: 14px;
            color: #6B7280;
        }}
        .breadcrumbs a {{ color: {colors['primary']}; }}
        .breadcrumbs span {{ margin: 0 8px; color: #D1D5DB; }}
        .breadcrumbs .current {{ color: #374151; }}

        /* === Two-Column Layout === */
        .article-wrapper {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px 40px;
            display: grid;
            grid-template-columns: 1fr 280px;
            gap: 32px;
            align-items: start;
        }}

        /* Main content */
        .article-main {{ min-width: 0; }}
        .article-main article {{
            background: #fff;
            border-radius: 12px;
            padding: 36px 40px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            border: 1px solid #E5E7EB;
        }}
        article h2 {{
            font-size: 22px;
            font-weight: 700;
            color: {colors['primary']};
            margin: 32px 0 14px;
            padding-bottom: 8px;
            border-bottom: 2px solid color-mix(in srgb, {colors['primary']} 20%, white);
        }}
        article h3 {{ font-size: 18px; font-weight: 600; color: {colors['primary']}; margin: 24px 0 10px; }}
        article p {{ margin-bottom: 14px; color: #374151; }}
        article ul, article ol {{ padding-left: 24px; margin-bottom: 14px; }}
        article li {{ margin-bottom: 6px; color: #374151; }}

        /* === Sidebar === */
        .article-sidebar {{
            position: sticky;
            top: 72px;
        }}
        .sidebar-card {{
            background: #fff;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            border: 1px solid #E5E7EB;
        }}
        .sidebar-card h3 {{
            font-size: 15px;
            font-weight: 700;
            color: #1F2937;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 2px solid color-mix(in srgb, {colors['primary']} 20%, white);
        }}
        .sidebar-card .angle-nav {{ list-style: none; }}
        .sidebar-card .angle-nav li {{ margin-bottom: 4px; }}
        .sidebar-card .angle-nav a {{
            display: block;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 14px;
            color: #4B5563;
            transition: background 0.2s, color 0.2s;
            text-decoration: none;
        }}
        .sidebar-card .angle-nav a:hover {{
            background: #F3F4F6;
            color: {colors['primary']};
            text-decoration: none;
        }}
        .sidebar-card .angle-nav a.active {{
            background: color-mix(in srgb, {colors['primary']} 12%, white);
            color: {colors['primary']};
            font-weight: 600;
        }}
        .sidebar-card .back-link {{
            display: block;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #E5E7EB;
            font-size: 13px;
            color: #6B7280;
        }}
        .sidebar-card .back-link:hover {{ color: {colors['primary']}; text-decoration: none; }}

        /* === Content Styling === */
        .factbox {{
            background: linear-gradient(135deg, color-mix(in srgb, {colors['primary']} 5%, white), color-mix(in srgb, {colors['primary']} 12%, white));
            border: 1px solid color-mix(in srgb, {colors['primary']} 20%, white);
            border-radius: 10px;
            padding: 20px 24px;
            margin: 20px 0;
        }}
        .factbox h3 {{
            color: {colors['primary']};
            margin: 0 0 12px;
            font-size: 16px;
        }}
        .fact-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid color-mix(in srgb, {colors['primary']} 10%, white);
        }}
        .fact-row:last-child {{ border-bottom: none; }}
        .fact-key {{ font-weight: 600; color: #1F2937; flex: 0 0 45%; }}
        .fact-val {{ color: #6B7280; text-align: right; flex: 0 0 50%; }}

        .table-wrapper {{ overflow-x: auto; margin: 16px 0; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
        th {{
            background: {colors['primary']};
            color: white;
            padding: 10px 14px;
            text-align: left;
            font-weight: 600;
        }}
        td {{ padding: 10px 14px; border-bottom: 1px solid #E5E7EB; }}
        tr:nth-child(even) {{ background: #F9FAFB; }}
        tr:hover {{ background: color-mix(in srgb, {colors['primary']} 5%, white); }}

        .callout {{
            background: #FEF3C7;
            border-left: 4px solid #F59E0B;
            padding: 14px 18px;
            border-radius: 0 8px 8px 0;
            margin: 16px 0;
            font-size: 14px;
        }}
        .callout .misconception {{ color: #856404; margin-bottom: 4px; }}
        .callout .reality {{ color: #155724; background: #d4edda; padding: 8px 12px; border-radius: 4px; margin-bottom: 12px; }}

        .rating {{ display: flex; align-items: center; gap: 10px; padding: 6px 0; }}
        .rating-label {{ font-weight: 600; min-width: 160px; }}
        .rating-dots {{ font-size: 1.2em; color: {colors['primary']}; letter-spacing: 2px; }}
        .rating-score {{ color: #6B7280; font-size: 13px; }}

        /* === Footer === */
        .site-footer {{
            background: #111827;
            color: #9CA3AF;
            margin-top: 40px;
            padding: 40px 24px 28px;
        }}
        .footer-inner {{
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 2fr 1fr 1fr;
            gap: 40px;
        }}
        .footer-brand .site-logo {{ font-size: 18px; display: inline-block; margin-bottom: 12px; }}
        .footer-brand p {{ font-size: 14px; line-height: 1.6; max-width: 320px; }}
        .footer-col h4 {{ color: #fff; font-size: 14px; font-weight: 600; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .footer-col a {{ display: block; color: #9CA3AF; font-size: 14px; padding: 4px 0; transition: color 0.2s; text-decoration: none; }}
        .footer-col a:hover {{ color: #fff; text-decoration: none; }}
        .footer-bottom {{
            max-width: 1200px;
            margin: 24px auto 0;
            padding-top: 20px;
            border-top: 1px solid #374151;
            text-align: center;
            font-size: 13px;
        }}

        /* === Table of Contents === */
        .toc {{ background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px 24px; margin: 0 0 28px; }}
        .toc h3 {{ font-size: 14px; font-weight: 600; color: #475569; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .toc ol {{ padding-left: 20px; margin: 0; }}
        .toc li {{ font-size: 14px; margin-bottom: 4px; line-height: 1.5; }}
        .toc a {{ color: {colors['primary']}; }}

        /* === Article Meta === */
        .article-meta {{ font-size: 13px; color: #6B7280; margin-bottom: 20px; }}

        /* === Related Concepts === */
        .related-concepts {{ margin-top: 32px; padding-top: 24px; border-top: 2px solid #E5E7EB; }}
        .related-section {{ margin-bottom: 20px; }}
        .related-section h4 {{ font-size: 15px; font-weight: 600; color: #374151; margin-bottom: 10px; }}
        .related-grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .related-link {{
            display: inline-block; padding: 8px 16px; background: #F3F4F6;
            border-radius: 8px; font-size: 14px; color: {colors['primary']};
            font-weight: 500; transition: background 0.2s; text-decoration: none;
        }}
        .related-link:hover {{ background: color-mix(in srgb, {colors['primary']} 12%, white); text-decoration: none; }}

        /* === Responsive === */
        @media (max-width: 900px) {{
            .article-wrapper {{
                grid-template-columns: 1fr;
                padding: 0 16px 32px;
            }}
            .article-sidebar {{
                position: static;
                order: -1;
            }}
            .article-main article {{ padding: 24px; }}
            .page-banner h1 {{ font-size: 22px; }}
            .footer-inner {{ grid-template-columns: 1fr; gap: 24px; }}
        }}
        @media (max-width: 768px) {{
            .menu-toggle {{ display: block; }}
            .continent-nav {{
                display: none; flex-direction: column; position: absolute;
                top: 56px; left: 0; right: 0; background: #1F2937;
                padding: 12px; gap: 2px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            }}
            .continent-nav a {{ padding: 12px 16px; border-radius: 8px; }}
            #mobile-menu-state:checked ~ .header-inner .continent-nav {{ display: flex; }}
        }}
    </style>
</head>
<body>
    <input type="checkbox" id="mobile-menu-state" aria-hidden="true">
    <header class="site-header">
        <div class="header-inner">
            <a href="/" class="site-logo">360 <span>Nations</span></a>
            <label for="mobile-menu-state" class="menu-toggle" aria-label="Toggle menu"><span></span></label>
            <ul class="continent-nav">
            {continent_nav}</ul>
        </div>
    </header>

    <div class="page-banner">
        <div class="banner-inner">
            <h1><span class="flag">{flag}</span> {title}</h1>
        </div>
    </div>

    <nav class="breadcrumbs" aria-label="Breadcrumb">{breadcrumb_html}</nav>

    <div class="article-wrapper">
        <main class="article-main">
            <article>
                <div class="article-meta">Last updated: {datetime.now().strftime("%B %Y")}</div>
                {toc_html}
                {verified_factbox_html}
                {html_content}
                {cost_hub_links_html}
                {cost_cross_links_html}
                {related_links_html}
            </article>
        </main>

        <aside class="article-sidebar">
            <div class="sidebar-card">
                <h3>{entity_name}</h3>
                <ul class="angle-nav">
                {angle_nav_html}
                </ul>
                <a href="/{continent}/" class="back-link">&larr; All {colors['name']} countries</a>
            </div>
        </aside>
    </div>

    <footer class="site-footer">
        <div class="footer-inner">
            <div class="footer-brand">
                <a href="/" class="site-logo">360 <span>Nations</span></a>
                <p>Comprehensive country guides covering culture, travel, safety, and practical information for every nation.</p>
            </div>
            <div class="footer-col">
                <h4>Continents</h4>
                <a href="/africa/">Africa</a>
                <a href="/asia/">Asia</a>
                <a href="/europe/">Europe</a>
                <a href="/north-america/">North America</a>
                <a href="/south-america/">South America</a>
                <a href="/oceania/">Oceania</a>
            </div>
            <div class="footer-col">
                <h4>Info</h4>
                <a href="/privacy.html">Privacy Policy</a>
                <a href="/terms.html">Terms of Use</a>
                <a href="/sitemap.xml">Sitemap</a>
            </div>
        </div>
        <div style="max-width:1200px;margin:24px auto 0;padding:0 24px;font-size:12px;color:#6B7280;line-height:1.5;">
            Editorial note: {SITE_NAME} content is researched by regional contributors and fact-checked for accuracy. Verify visa requirements and safety advisories with official government sources before traveling.
        </div>
        <div class="footer-bottom">
            &copy; {datetime.now().year} {SITE_NAME} &mdash; Evergreen reference content. Always verify visa and safety details with official sources.
        </div>
    </footer>
</body>
</html>"""
    return html


def generate_toc_html(content):
    """Generate a table of contents from h2 headings in raw content.
    Extracts headings from [SECTION] tags and numbered ALL-CAPS headers.
    Returns empty string if fewer than 2 headings found."""
    headings = []
    for line in content.strip().split('\n'):
        stripped = line.strip()
        # [SECTION] tag
        section_match = re.match(r'^\[SECTION\]\s*(.+?)\s*\[/SECTION\]$', stripped)
        if section_match:
            headings.append(section_match.group(1))
        # Numbered ALL-CAPS header: "1. TITLE" or "1. TITLE:"
        num_header = re.match(r'^(\d+)\.\s+([A-Z][A-Z\s&/,\'-]+):?\s*$', stripped)
        if num_header:
            headings.append(num_header.group(2).strip().rstrip(":").title())
        # ALL-CAPS header with colon
        if stripped.upper() == stripped and len(stripped) > 3 and ":" in stripped and not stripped.startswith("-") and not stripped.startswith("|"):
            heading_text = stripped.rstrip(":").strip().title()
            if heading_text not in headings:  # avoid duplicates
                headings.append(heading_text)

    if len(headings) < 2:
        return ""

    items = ""
    for h in headings:
        slug = slugify(h)
        display = re.sub(r'\*\*(.+?)\*\*', r'\1', h)
        items += f'            <li><a href="#{slug}">{display}</a></li>\n'

    return f"""<nav class="toc">
        <h3>In This Article</h3>
        <ol>
{items}        </ol>
    </nav>"""


def build_related_links(entity):
    """Build 'Compare With' and 'Nearby Countries' link sections."""
    comparisons = entity.get("common_comparisons", [])
    neighbors = entity.get("neighbors", [])
    continent = entity.get("continent", "europe")

    if not comparisons and not neighbors:
        return ""

    sections = []

    if comparisons:
        comp_links = ""
        for comp in comparisons[:6]:
            comp_slug = slugify(comp)
            comp_links += f'            <a href="/{continent}/{comp_slug}/overview.html" class="related-link">{comp}</a>\n'
        sections.append(f"""<div class="related-section">
        <h4>Compare With</h4>
        <div class="related-grid">
{comp_links}        </div>
    </div>""")

    if neighbors:
        nb_links = ""
        for nb in neighbors[:6]:
            nb_slug = slugify(nb)
            nb_links += f'            <a href="/{continent}/{nb_slug}/overview.html" class="related-link">{nb}</a>\n'
        sections.append(f"""<div class="related-section">
        <h4>Nearby Countries</h4>
        <div class="related-grid">
{nb_links}        </div>
    </div>""")

    return f"""<div class="related-concepts">
    {''.join(sections)}
</div>"""


def build_cost_hub_links(entity):
    """Build a 'Detailed Cost Guides' grid for the cost-of-living hub page.
    Links to all 7 cost sub-angles + available cost comparisons.

    Args:
        entity: Entity dict from entity_registry

    Returns:
        HTML string with cost guide links grid
    """
    continent = entity.get("continent", "europe")
    entity_slug = slugify(entity["name"])

    # Load cost registry for sub-angle info
    cost_registry_path = BASE_DIR / "cost_angle_registry.json"
    if not cost_registry_path.exists():
        return ""

    try:
        cost_reg = json.loads(cost_registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    cost_angles = cost_reg.get("cost_angles", {})
    sidebar_labels = cost_reg.get("sidebar_labels", {})

    # Build sub-angle links
    sub_links = []
    for csub_id, csub_config in cost_angles.items():
        csub_page = OUTPUT_DIR / continent / entity_slug / f"{csub_id}.html"
        if csub_page.exists():
            label = sidebar_labels.get(csub_id, csub_config.get("title_pattern", "").replace("{Entity}", entity["name"]))
            desc = csub_config.get("description", "")
            sub_links.append(f'<a href="/{continent}/{entity_slug}/{csub_id}.html" class="cost-guide-link"><strong>{label}</strong><span>{desc}</span></a>')

    # Build comparison links
    comp_links = []
    for comp in entity.get("common_comparisons", []):
        comp_slug = slugify(comp)
        comp_file = OUTPUT_DIR / continent / entity_slug / f"cost-compare-{comp_slug}.html"
        if comp_file.exists():
            comp_links.append(f'<a href="/{continent}/{entity_slug}/cost-compare-{comp_slug}.html" class="cost-guide-link"><strong>{entity["name"]} vs {comp}</strong><span>Side-by-side cost comparison</span></a>')

    if not sub_links and not comp_links:
        return ""

    all_links = "\n".join(sub_links + comp_links)
    return f"""<div class="cost-guides-grid" style="margin-top:32px;">
    <h2 style="margin-bottom:16px;">Detailed Cost Guides</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;">
{all_links}
    </div>
</div>
<style>.cost-guide-link{{display:block;padding:16px;background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;text-decoration:none;transition:border-color 0.2s,box-shadow 0.2s;}}.cost-guide-link:hover{{border-color:#6B7280;box-shadow:0 2px 8px rgba(0,0,0,0.08);text-decoration:none;}}.cost-guide-link strong{{display:block;color:#1F2937;margin-bottom:4px;}}.cost-guide-link span{{font-size:13px;color:#6B7280;}}</style>"""


def build_cost_cross_links(entity, current_angle_id):
    """Build 'Related Cost Guides' footer for cost sub-pages.
    Links to hub, related sub-pages, economy, and comparison pages.

    Args:
        entity: Entity dict from entity_registry
        current_angle_id: Current cost sub-angle slug

    Returns:
        HTML string with related cost guide links
    """
    continent = entity.get("continent", "europe")
    entity_slug = slugify(entity["name"])

    # Load cost registry
    cost_registry_path = BASE_DIR / "cost_angle_registry.json"
    if not cost_registry_path.exists():
        return ""

    try:
        cost_reg = json.loads(cost_registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    cost_angles = cost_reg.get("cost_angles", {})
    sidebar_labels = cost_reg.get("sidebar_labels", {})
    current_config = cost_angles.get(current_angle_id, {})
    related = current_config.get("related_angles", [])

    links = []

    # Link to cost-of-living hub
    hub_page = OUTPUT_DIR / continent / entity_slug / "cost-of-living.html"
    if hub_page.exists():
        links.append(f'<a href="/{continent}/{entity_slug}/cost-of-living.html">Cost of Living Overview</a>')

    # Related sub-pages
    for rel_id in related:
        if rel_id == current_angle_id:
            continue
        rel_page = OUTPUT_DIR / continent / entity_slug / f"{rel_id}.html"
        if rel_page.exists():
            label = sidebar_labels.get(rel_id, rel_id.replace("-", " ").title())
            links.append(f'<a href="/{continent}/{entity_slug}/{rel_id}.html">{label}</a>')

    # Link to economy page
    econ_page = OUTPUT_DIR / continent / entity_slug / "economy.html"
    if econ_page.exists():
        links.append(f'<a href="/{continent}/{entity_slug}/economy.html">Economy</a>')

    # Comparison links
    for comp in entity.get("common_comparisons", [])[:2]:
        comp_slug = slugify(comp)
        comp_file = OUTPUT_DIR / continent / entity_slug / f"cost-compare-{comp_slug}.html"
        if comp_file.exists():
            links.append(f'<a href="/{continent}/{entity_slug}/cost-compare-{comp_slug}.html">{entity["name"]} vs {comp}</a>')

    if not links:
        return ""

    links_html = " &middot; ".join(links)
    return f"""<div style="margin-top:24px;padding:16px 20px;background:#F3F4F6;border-radius:8px;font-size:14px;">
    <strong>Related Cost Guides:</strong> {links_html}
</div>"""


def content_to_html(content):
    """Convert structured AI output into styled HTML.
    Handles: [SECTION], [TABLE], [FACTBOX], [CALLOUT], [RATING], bold, lists."""
    # Pre-process: handle inline bold **text**
    def bold(text):
        return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    lines = content.strip().split("\n")
    html_parts = []
    in_list = False        # inside <ul>
    in_ol = False          # inside <ol>
    in_table = False       # inside <table>
    in_factbox = False
    in_callout = False
    table_header_done = False

    def close_list():
        nonlocal in_list, in_ol
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        if in_ol:
            html_parts.append("</ol>")
            in_ol = False

    for line in lines:
        stripped = line.strip()

        # ── Skip empty lines (close open lists) ──
        if not stripped:
            if not in_table and not in_factbox and not in_callout:
                close_list()
            continue

        # ── [FACTBOX] / [/FACTBOX] ──
        if stripped == "[FACTBOX]":
            close_list()
            in_factbox = True
            html_parts.append('<div class="factbox"><h3>Quick Facts</h3>')
            continue
        if stripped == "[/FACTBOX]":
            in_factbox = False
            html_parts.append("</div>")
            continue
        if in_factbox:
            # Parse "Key: Value" lines
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                html_parts.append(f'<div class="fact-row"><span class="fact-key">{bold(key.strip())}</span><span class="fact-val">{bold(val.strip())}</span></div>')
            continue

        # ── [CALLOUT] / [/CALLOUT] ──
        if stripped == "[CALLOUT]":
            close_list()
            in_callout = True
            html_parts.append('<div class="callout">')
            continue
        if stripped == "[/CALLOUT]":
            in_callout = False
            html_parts.append("</div>")
            continue
        # Line ending with [/CALLOUT] (close block and keep content)
        if in_callout and stripped.endswith("[/CALLOUT]"):
            text = stripped[:-len("[/CALLOUT]")].strip()
            if text:
                if text.startswith("Misconception:") or text.startswith("Reality:"):
                    key, _, val = text.partition(":")
                    css_class = "misconception" if key.strip() == "Misconception" else "reality"
                    html_parts.append(f'<p class="{css_class}"><strong>{key.strip()}:</strong> {bold(val.strip())}</p>')
                else:
                    html_parts.append(f"<p>{bold(text)}</p>")
            in_callout = False
            html_parts.append("</div>")
            continue
        # Inline callout (single line: [CALLOUT] text [/CALLOUT])
        callout_inline = re.match(r'^\[CALLOUT\]\s*(.+?)\s*\[/CALLOUT\]$', stripped)
        if callout_inline:
            close_list()
            html_parts.append(f'<div class="callout"><p>{bold(callout_inline.group(1))}</p></div>')
            continue
        # [CALLOUT] with text on same line (opens block, first line is content)
        callout_open_with_text = re.match(r'^\[CALLOUT\]\s+(.+)$', stripped)
        if callout_open_with_text:
            close_list()
            in_callout = True
            text = callout_open_with_text.group(1)
            html_parts.append('<div class="callout">')
            if text.startswith("Misconception:") or text.startswith("Reality:"):
                key, _, val = text.partition(":")
                css_class = "misconception" if key.strip() == "Misconception" else "reality"
                html_parts.append(f'<p class="{css_class}"><strong>{key.strip()}:</strong> {bold(val.strip())}</p>')
            else:
                html_parts.append(f"<p>{bold(text)}</p>")
            continue
        if in_callout:
            # Check for Misconception/Reality pattern
            if stripped.startswith("Misconception:") or stripped.startswith("Reality:"):
                key, _, val = stripped.partition(":")
                css_class = "misconception" if key.strip() == "Misconception" else "reality"
                html_parts.append(f'<p class="{css_class}"><strong>{key.strip()}:</strong> {bold(val.strip())}</p>')
            else:
                html_parts.append(f"<p>{bold(stripped)}</p>")
            continue

        # ── [SECTION] Name [/SECTION] ──
        section_match = re.match(r'^\[SECTION\]\s*(.+?)\s*\[/SECTION\]$', stripped)
        if section_match:
            close_list()
            html_parts.append(f'<h2 id="{slugify(section_match.group(1))}">{bold(section_match.group(1))}</h2>')
            continue

        # ── [TABLE] / [/TABLE] ──
        if stripped == "[TABLE]":
            close_list()
            in_table = True
            table_header_done = False
            html_parts.append('<div class="table-wrapper"><table>')
            continue
        if stripped == "[/TABLE]":
            in_table = False
            table_header_done = False
            html_parts.append("</table></div>")
            continue
        if in_table:
            # Skip separator rows like | --- | --- |
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            # Parse table row
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not table_header_done:
                html_parts.append("<thead><tr>" + "".join(f"<th>{bold(c)}</th>" for c in cells) + "</tr></thead><tbody>")
                table_header_done = True
            else:
                html_parts.append("<tr>" + "".join(f"<td>{bold(c)}</td>" for c in cells) + "</tr>")
            continue

        # ── [RATING] label: X/5 ──
        rating_match = re.match(r'^\[RATING\]\s*(.+?):\s*(\d)/5', stripped)
        if rating_match:
            close_list()
            label = rating_match.group(1)
            score = int(rating_match.group(2))
            filled = "●" * score + "○" * (5 - score)
            html_parts.append(f'<div class="rating"><span class="rating-label">{bold(label)}</span><span class="rating-dots">{filled}</span><span class="rating-score">{score}/5</span></div>')
            continue

        # ── Numbered headers: "1. TITLE" or "1. TITLE:" (all caps) ──
        num_header = re.match(r'^(\d+)\.\s+([A-Z][A-Z\s&/,\'-]+):?\s*$', stripped)
        if num_header:
            close_list()
            heading = num_header.group(2).strip().rstrip(":")
            html_parts.append(f'<h2 id="{slugify(heading.title())}">{heading.title()}</h2>')
            continue

        # ── ALL-CAPS headers with colon: "SECTION NAME:" ──
        if stripped.upper() == stripped and len(stripped) > 3 and ":" in stripped and not stripped.startswith("-") and not stripped.startswith("|"):
            close_list()
            heading = stripped.rstrip(":").strip()
            html_parts.append(f'<h2 id="{slugify(heading.title())}">{heading.title()}</h2>')
            continue

        # ── Bold subheader: **Label:** followed by text ──
        bold_header = re.match(r'^\*\*(.+?)\*\*:?\s*$', stripped)
        if bold_header:
            close_list()
            html_parts.append(f"<h3>{bold_header.group(1)}</h3>")
            continue

        # ── Bold label with inline content: **Label:** some text ──
        bold_inline = re.match(r'^\*\*(.+?)\*\*:\s+(.+)', stripped)
        if bold_inline:
            close_list()
            html_parts.append(f"<p><strong>{bold_inline.group(1)}:</strong> {bold(bold_inline.group(2))}</p>")
            continue

        # ── Bullet points ──
        if re.match(r'^[-*•]\s+', stripped):
            if not in_list:
                close_list()
                html_parts.append("<ul>")
                in_list = True
            item = re.sub(r'^[-*•]\s+', '', stripped)
            html_parts.append(f"<li>{bold(item)}</li>")
            continue

        # ── Numbered list ──
        ol_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if ol_match:
            if not in_ol:
                close_list()
                html_parts.append("<ol>")
                in_ol = True
            html_parts.append(f"<li>{bold(ol_match.group(2))}</li>")
            continue

        # ── Bare markdown table (| col | col | without [TABLE] wrapper) ──
        if re.match(r'^\|.+\|$', stripped):
            # Skip separator rows
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not in_table:
                close_list()
                in_table = True
                table_header_done = False
                html_parts.append('<div class="table-wrapper"><table>')
            if not table_header_done:
                html_parts.append("<thead><tr>" + "".join(f"<th>{bold(c)}</th>" for c in cells) + "</tr></thead><tbody>")
                table_header_done = True
            else:
                html_parts.append("<tr>" + "".join(f"<td>{bold(c)}</td>" for c in cells) + "</tr>")
            continue

        # ── Close bare markdown table when non-table line encountered ──
        if in_table and not stripped.startswith("|"):
            in_table = False
            table_header_done = False
            html_parts.append("</tbody></table></div>")

        # ── Regular paragraph ──
        close_list()
        html_parts.append(f"<p>{bold(stripped)}</p>")

    close_list()
    if in_table:
        html_parts.append("</tbody></table></div>")
    if in_factbox:
        html_parts.append("</div>")
    if in_callout:
        html_parts.append("</div>")

    return "\n        ".join(html_parts)


# =============================================================================
# FILE OUTPUT
# =============================================================================

def format_as_json(entity, angle_id, title, content):
    """Format page data as JSON."""
    return json.dumps({
        "entity": entity["name"],
        "entity_slug": slugify(entity["name"]),
        "iso_code": entity.get("iso_code", ""),
        "continent": entity.get("continent", ""),
        "angle": angle_id,
        "title": title,
        "content": content,
        "word_count": len(content.split()),
        "generated_date": datetime.now().isoformat(),
    }, indent=2, ensure_ascii=False)


def format_as_markdown(entity, angle_id, title, content):
    """Format page data as Markdown."""
    return f"""---
title: "{title}"
entity: "{entity['name']}"
iso_code: "{entity.get('iso_code', '')}"
continent: "{entity.get('continent', '')}"
angle: "{angle_id}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
---

# {title}

{content}

---

*Evergreen reference content. Verify time-sensitive details with official sources.*
"""


def save_page(entity, angle_id, title, content, enriched_data=None):
    """Save page in HTML, JSON, and MD formats."""
    continent = entity.get("continent", "general")
    entity_slug = slugify(entity["name"])

    # Create output directory
    page_dir = OUTPUT_DIR / continent / entity_slug
    page_dir.mkdir(parents=True, exist_ok=True)

    # Generate all formats
    html = build_html(entity, angle_id, title, content, enriched_data=enriched_data)
    json_data = format_as_json(entity, angle_id, title, content)
    md = format_as_markdown(entity, angle_id, title, content)

    # Save files
    (page_dir / f"{angle_id}.html").write_text(html, encoding="utf-8")
    (page_dir / f"{angle_id}.json").write_text(json_data, encoding="utf-8")
    (page_dir / f"{angle_id}.md").write_text(md, encoding="utf-8")

    log(f"Saved: {continent}/{entity_slug}/{angle_id} (HTML+JSON+MD)", "SUCCESS")
    return page_dir / f"{angle_id}.html"


def save_level3_page(entity, sub_entity_name, sub_type, angle_id, title, content):
    """Save a Level 3 sub-entity page."""
    continent = entity.get("continent", "general")
    entity_slug = slugify(entity["name"])
    sub_slug = slugify(sub_entity_name)

    # regions/ or cities/ subdirectory
    page_dir = OUTPUT_DIR / continent / entity_slug / sub_type / sub_slug
    page_dir.mkdir(parents=True, exist_ok=True)

    html = build_html(entity, angle_id, title, content, breadcrumbs=[
        ("Home", "/"),
        (CONTINENT_COLORS.get(continent, {}).get("name", continent.title()), f"/{continent}/"),
        (entity["name"], f"/{continent}/{entity_slug}/"),
        (sub_type.title(), f"/{continent}/{entity_slug}/{sub_type}/"),
        (sub_entity_name, f"/{continent}/{entity_slug}/{sub_type}/{sub_slug}/"),
        (angle_id.replace("-", " ").title(), None),
    ])
    json_data = format_as_json(entity, angle_id, title, content)
    md = format_as_markdown(entity, angle_id, title, content)

    (page_dir / f"{angle_id}.html").write_text(html, encoding="utf-8")
    (page_dir / f"{angle_id}.json").write_text(json_data, encoding="utf-8")
    (page_dir / f"{angle_id}.md").write_text(md, encoding="utf-8")

    log(f"Saved L3: {continent}/{entity_slug}/{sub_type}/{sub_slug}/{angle_id}", "SUCCESS")
    return page_dir / f"{angle_id}.html"


# =============================================================================
# INDEX PAGE GENERATION
# =============================================================================

def generate_all_index_pages():
    """Generate index.html for every continent and every country that has pages."""
    registry = load_entity_registry()
    entities = registry.get("entities", {})

    # Group entities by continent
    by_continent = {}
    for slug, entity in entities.items():
        continent = entity.get("continent", "general")
        by_continent.setdefault(continent, []).append((slug, entity))

    for continent, country_list in by_continent.items():
        continent_dir = OUTPUT_DIR / continent
        if not continent_dir.exists():
            continue

        # Only include countries that have at least one generated page
        countries_with_pages = []
        for slug, entity in country_list:
            entity_dir = continent_dir / slug
            if entity_dir.exists() and list(entity_dir.glob("*.html")):
                pages = sorted([f.stem for f in entity_dir.glob("*.html") if f.stem != "index"])
                countries_with_pages.append((slug, entity, pages))

        if not countries_with_pages:
            continue

        # ── Generate continent index ──
        _write_continent_index(continent, countries_with_pages)

        # ── Generate country index for each country ──
        for slug, entity, pages in countries_with_pages:
            _write_country_index(continent, slug, entity, pages)

    log("All index pages generated", "SUCCESS")


def _write_continent_index(continent, countries_with_pages):
    """Write continent/index.html listing all countries."""
    colors = CONTINENT_COLORS.get(continent, CONTINENT_COLORS.get("europe"))
    continent_name = colors["name"]

    country_cards = []
    for slug, entity, pages in sorted(countries_with_pages, key=lambda x: x[1]["name"]):
        flag = iso_to_flag(entity.get("iso_code", ""))
        page_count = len(pages)
        pop = entity.get("population_millions", 0)
        capital = entity.get("capital", "")
        country_cards.append(f"""
            <a href="/{continent}/{slug}/" class="country-card">
                <span class="card-flag">{flag}</span>
                <h3>{entity['name']}</h3>
                <p>{capital} &middot; {pop}M people &middot; {page_count} pages</p>
            </a>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Country guides for {continent_name} - explore every country with 30 in-depth angles.">
    <title>{continent_name} Country Guides | {SITE_NAME}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2d3436; background: #fafafa; }}
        header {{ background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']}); color: white; padding: 40px 20px; text-align: center; }}
        header h1 {{ font-size: 2em; }}
        header p {{ opacity: 0.9; margin-top: 8px; }}
        .breadcrumb {{ max-width: 1100px; margin: 0 auto; padding: 12px 20px; font-size: 0.85em; color: #636e72; }}
        .breadcrumb a {{ color: {colors['primary']}; text-decoration: none; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
        .country-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
        .country-card {{
            display: block; background: white; border-radius: 10px; padding: 20px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06); text-decoration: none; color: #2d3436;
            border-left: 4px solid {colors['primary']}; transition: transform 0.2s;
        }}
        .country-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
        .country-card h3 {{ color: {colors['primary']}; margin: 4px 0; }}
        .country-card p {{ font-size: 0.85em; color: #636e72; }}
        .card-flag {{ font-size: 1.6em; }}
        footer {{ text-align: center; padding: 30px; color: #b2bec3; font-size: 0.8em; }}
    </style>
</head>
<body>
    <header>
        <h1>{continent_name}</h1>
        <p>{len(countries_with_pages)} countries and territories</p>
    </header>
    <nav class="breadcrumb"><a href="/">Home</a> &raquo; <span>{continent_name}</span></nav>
    <div class="container">
        <div class="country-grid">
            {''.join(country_cards)}
        </div>
    </div>
    <footer><p>&copy; {datetime.now().year} {SITE_NAME}. Evergreen reference content.</p></footer>
</body>
</html>"""

    out = OUTPUT_DIR / continent / "index.html"
    out.write_text(html, encoding="utf-8")
    log(f"Index: {continent}/ ({len(countries_with_pages)} countries)", "INFO")


def _write_country_index(continent, entity_slug, entity, pages):
    """Write continent/country/index.html linking to all angles."""
    colors = CONTINENT_COLORS.get(continent, CONTINENT_COLORS.get("europe"))
    continent_name = colors["name"]
    flag = iso_to_flag(entity.get("iso_code", ""))
    name = entity["name"]
    capital = entity.get("capital", "")
    pop = entity.get("population_millions", 0)
    languages = ", ".join(entity.get("languages", []))

    angle_registry = load_angle_registry()
    angles = angle_registry.get("angles", {})

    # Build angle links (required angles first, then vs)
    angle_links = []
    vs_links = []
    for page in pages:
        if page.startswith("vs-"):
            comp_name = page.replace("vs-", "").replace("-", " ").title()
            vs_links.append(f'<a href="/{continent}/{entity_slug}/{page}.html" class="angle-card vs"><span class="angle-icon">&#8644;</span><h3>{name} vs {comp_name}</h3></a>')
        elif page in angles:
            desc = angles[page].get("description", "")
            angle_links.append(f'<a href="/{continent}/{entity_slug}/{page}.html" class="angle-card"><span class="angle-icon">&#9654;</span><h3>{page.replace("-", " ").title()}</h3><p>{desc}</p></a>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{name} - comprehensive country guide covering geography, culture, visa, cost of living, safety, and more.">
    <title>{name} Country Guide | {SITE_NAME}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2d3436; background: #fafafa; }}
        header {{ background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']}); color: white; padding: 40px 20px; text-align: center; }}
        header h1 {{ font-size: 2.2em; }}
        .flag {{ font-size: 1.6em; margin-right: 8px; }}
        .subtitle {{ opacity: 0.9; margin-top: 8px; }}
        .breadcrumb {{ max-width: 900px; margin: 0 auto; padding: 12px 20px; font-size: 0.85em; color: #636e72; }}
        .breadcrumb a {{ color: {colors['primary']}; text-decoration: none; }}
        .quick-facts {{
            max-width: 900px; margin: 0 auto; padding: 0 20px;
        }}
        .quick-facts-inner {{
            display: flex; flex-wrap: wrap; gap: 20px; background: white;
            border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px;
        }}
        .qf-item {{ text-align: center; flex: 1; min-width: 100px; }}
        .qf-item .qf-val {{ font-size: 1.1em; font-weight: 700; color: {colors['primary']}; }}
        .qf-item .qf-label {{ font-size: 0.75em; color: #636e72; text-transform: uppercase; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 0 20px 40px; }}
        h2 {{ margin: 24px 0 12px; color: #2d3436; }}
        .angle-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }}
        .angle-card {{
            display: block; background: white; border-radius: 10px; padding: 18px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06); text-decoration: none; color: #2d3436;
            border-left: 4px solid {colors['primary']}; transition: transform 0.2s;
        }}
        .angle-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
        .angle-card h3 {{ color: {colors['primary']}; font-size: 1em; margin: 4px 0; }}
        .angle-card p {{ font-size: 0.82em; color: #636e72; margin: 0; }}
        .angle-card.vs {{ border-left-color: #636e72; }}
        .angle-card.vs h3 {{ color: #636e72; }}
        .angle-icon {{ font-size: 0.9em; color: {colors['primary']}; }}
        footer {{ text-align: center; padding: 30px; color: #b2bec3; font-size: 0.8em; }}
    </style>
</head>
<body>
    <header>
        <h1><span class="flag">{flag}</span> {name}</h1>
        <p class="subtitle">{capital} &middot; {pop}M people &middot; {languages}</p>
    </header>
    <nav class="breadcrumb"><a href="/">Home</a> &raquo; <a href="/{continent}/">{continent_name}</a> &raquo; <span>{name}</span></nav>
    <div class="quick-facts"><div class="quick-facts-inner">
        <div class="qf-item"><div class="qf-val">{capital}</div><div class="qf-label">Capital</div></div>
        <div class="qf-item"><div class="qf-val">{pop}M</div><div class="qf-label">Population</div></div>
        <div class="qf-item"><div class="qf-val">{entity.get('currency', '')}</div><div class="qf-label">Currency</div></div>
        <div class="qf-item"><div class="qf-val">{len(pages)}</div><div class="qf-label">Pages</div></div>
    </div></div>
    <div class="container">
        <h2>Explore {name}</h2>
        <div class="angle-grid">
            {''.join(angle_links)}
        </div>
        {"<h2>Comparisons</h2><div class='angle-grid'>" + ''.join(vs_links) + "</div>" if vs_links else ""}
    </div>
    <footer><p>&copy; {datetime.now().year} {SITE_NAME}. Evergreen reference content.</p></footer>
</body>
</html>"""

    out = OUTPUT_DIR / continent / entity_slug / "index.html"
    out.write_text(html, encoding="utf-8")


# =============================================================================
# PAGE GENERATION
# =============================================================================

def generate_page(entity_slug, angle_id, comparison_entity=None):
    """Generate a single page for an entity + angle."""
    entity = get_entity(entity_slug)
    if not entity:
        log(f"Entity not found: {entity_slug}", "ERROR")
        return None

    angle_registry = load_angle_registry()
    angle_config = angle_registry.get("angles", {}).get(angle_id)
    if not angle_config:
        log(f"Angle not found: {angle_id}", "ERROR")
        return None

    # Skip optional angles for small entities
    size_class = entity.get("size_class", "medium")
    is_required = angle_config.get("required", False)
    if size_class == "small" and not is_required:
        log(f"Skipping optional angle {angle_id} for small entity {entity_slug}", "INFO")
        return None

    # Build title
    title = angle_config["title_pattern"].replace("{Entity}", entity["name"])
    if comparison_entity and angle_id == "vs":
        title = title.replace("{Comparison}", comparison_entity)

    # Check if already exists
    continent = entity.get("continent", "general")
    existing = OUTPUT_DIR / continent / entity_slug / f"{angle_id}.html"
    if existing.exists():
        log(f"Already exists: {entity_slug}/{angle_id}, skipping", "WARN")
        return existing

    # Generate content
    prompt_key = angle_config.get("prompt_key", angle_id)
    prompt = get_prompt_for_angle(entity, prompt_key, comparison_entity)

    # Fetch enriched data for verified factbox
    enriched_data = None
    try:
        from data_enrichment import fetch_country_data
        enriched_data = fetch_country_data(entity.get("iso_code", ""))
    except ImportError:
        pass

    log(f"Generating: {entity['name']} / {angle_id}...")
    content = generate_with_groq(prompt, max_tokens=angle_config.get("word_target", 800) * 3)

    # Save
    if angle_id == "vs" and comparison_entity:
        vs_slug = f"vs-{slugify(comparison_entity)}"
        title_vs = f"{entity['name']} vs {comparison_entity}"
        return save_page(entity, vs_slug, title_vs, content, enriched_data=enriched_data)
    else:
        return save_page(entity, angle_id, title, content, enriched_data=enriched_data)


def generate_cost_page(entity_slug, cost_angle_id, comparison_entity=None):
    """Generate a single cost sub-angle or cost comparison page.

    Args:
        entity_slug: Entity slug (e.g., 'kenya')
        cost_angle_id: Cost sub-angle slug (e.g., 'cost-rent-housing') or 'cost-comparison'
        comparison_entity: For comparison pages, the other country name

    Returns:
        Path to generated HTML file, or None
    """
    entity = get_entity(entity_slug)
    if not entity:
        log(f"Entity not found: {entity_slug}", "ERROR")
        return None

    # Load cost registry for config
    cost_registry_path = BASE_DIR / "cost_angle_registry.json"
    if not cost_registry_path.exists():
        log("cost_angle_registry.json not found", "ERROR")
        return None

    cost_reg = json.loads(cost_registry_path.read_text(encoding="utf-8"))
    continent = entity.get("continent", "general")

    if cost_angle_id == "cost-comparison" and comparison_entity:
        # Cost comparison page
        comp_slug = slugify(comparison_entity)
        file_slug = f"cost-compare-{comp_slug}"
        title = cost_reg["comparison"]["title_pattern"].replace("{Entity}", entity["name"]).replace("{Other}", comparison_entity)
        prompt_key = cost_reg["comparison"]["prompt_key"]
        word_target = cost_reg["comparison"].get("word_target", 900)
    else:
        # Cost sub-angle page
        angle_config = cost_reg.get("cost_angles", {}).get(cost_angle_id)
        if not angle_config:
            log(f"Cost angle not found: {cost_angle_id}", "ERROR")
            return None
        file_slug = cost_angle_id
        title = angle_config["title_pattern"].replace("{Entity}", entity["name"])
        prompt_key = angle_config["prompt_key"]
        word_target = angle_config.get("word_target", 800)

    # Check if already exists
    existing = OUTPUT_DIR / continent / entity_slug / f"{file_slug}.html"
    if existing.exists():
        log(f"Already exists: {entity_slug}/{file_slug}, skipping", "WARN")
        return existing

    # Generate content
    prompt = get_prompt_for_angle(entity, prompt_key, comparison_entity)

    # Fetch enriched data
    enriched_data = None
    try:
        from data_enrichment import fetch_country_data
        enriched_data = fetch_country_data(entity.get("iso_code", ""))
    except ImportError:
        pass

    log(f"Generating: {entity['name']} / {file_slug}...")
    content = generate_with_groq(prompt, max_tokens=word_target * 3)

    return save_page(entity, file_slug, title, content, enriched_data=enriched_data)


def generate_cost_angles_batch(entity_slugs=None, count=200):
    """Generate cost sub-angle pages in batch.

    Args:
        entity_slugs: List of entity slugs, or None for all
        count: Max pages to generate this run
    """
    cost_registry_path = BASE_DIR / "cost_angle_registry.json"
    if not cost_registry_path.exists():
        log("cost_angle_registry.json not found", "ERROR")
        return []

    cost_reg = json.loads(cost_registry_path.read_text(encoding="utf-8"))
    cost_angle_ids = list(cost_reg.get("cost_angles", {}).keys())

    if entity_slugs is None:
        entity_slugs = get_all_entity_slugs()

    # Build work queue
    work = []
    for slug in entity_slugs:
        entity = get_entity(slug)
        if not entity:
            continue
        continent = entity.get("continent", "general")
        for caid in cost_angle_ids:
            existing = OUTPUT_DIR / continent / slug / f"{caid}.html"
            if not existing.exists():
                work.append((slug, caid))

    if not work:
        log("No cost angle pages to generate (all done)", "WARN")
        return []

    work = work[:count]
    log(f"Generating {len(work)} cost angle pages (Phase 9)...")
    print("=" * 60)

    results = []
    for i, (slug, caid) in enumerate(work, 1):
        entity = get_entity(slug)
        print(f"\n[{i}/{len(work)}] {entity['name']} / {caid}")
        print("-" * 40)

        try:
            result = generate_cost_page(slug, caid)
            if result:
                results.append(result)
        except Exception as e:
            log(f"Failed: {e}", "ERROR")

        if i < len(work):
            time.sleep(2)

    print("\n" + "=" * 60)
    log(f"Generated {len(results)}/{len(work)} cost angle pages", "SUCCESS")

    update_manifest()
    generate_all_index_pages()
    return results


def generate_cost_comparisons_batch(entity_slugs=None, count=200):
    """Generate cost comparison pages in batch.

    Args:
        entity_slugs: List of entity slugs, or None for all
        count: Max pages to generate this run
    """
    if entity_slugs is None:
        entity_slugs = get_all_entity_slugs()

    # Build work queue from common_comparisons + neighbors
    work = []
    seen_pairs = set()

    for slug in entity_slugs:
        entity = get_entity(slug)
        if not entity:
            continue
        continent = entity.get("continent", "general")

        # common_comparisons
        for comp in entity.get("common_comparisons", []):
            pair_key = tuple(sorted([slug, slugify(comp)]))
            if pair_key in seen_pairs:
                continue
            comp_slug = slugify(comp)
            existing = OUTPUT_DIR / continent / slug / f"cost-compare-{comp_slug}.html"
            if not existing.exists():
                work.append((slug, comp))
                seen_pairs.add(pair_key)

        # neighbors (for additional coverage)
        for nb in entity.get("neighbors", []):
            pair_key = tuple(sorted([slug, slugify(nb)]))
            if pair_key in seen_pairs:
                continue
            nb_slug = slugify(nb)
            existing = OUTPUT_DIR / continent / slug / f"cost-compare-{nb_slug}.html"
            if not existing.exists():
                work.append((slug, nb))
                seen_pairs.add(pair_key)

    if not work:
        log("No cost comparison pages to generate (all done)", "WARN")
        return []

    work = work[:count]
    log(f"Generating {len(work)} cost comparison pages (Phase 10)...")
    print("=" * 60)

    results = []
    for i, (slug, comp) in enumerate(work, 1):
        entity = get_entity(slug)
        print(f"\n[{i}/{len(work)}] {entity['name']} vs {comp}")
        print("-" * 40)

        try:
            result = generate_cost_page(slug, "cost-comparison", comparison_entity=comp)
            if result:
                results.append(result)
        except Exception as e:
            log(f"Failed: {e}", "ERROR")

        if i < len(work):
            time.sleep(2)

    print("\n" + "=" * 60)
    log(f"Generated {len(results)}/{len(work)} cost comparison pages", "SUCCESS")

    update_manifest()
    generate_all_index_pages()
    return results


def regenerate_cost_hubs(entity_slugs=None):
    """Regenerate cost-of-living hub pages with new sub-angle links.
    Re-renders HTML from existing JSON content (no new AI generation).

    Args:
        entity_slugs: List of entity slugs, or None for all
    """
    if entity_slugs is None:
        entity_slugs = get_all_entity_slugs()

    rebuilt = 0
    for slug in entity_slugs:
        entity = get_entity(slug)
        if not entity:
            continue
        continent = entity.get("continent", "general")
        json_file = OUTPUT_DIR / continent / slug / "cost-of-living.json"
        if not json_file.exists():
            continue

        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            content = data.get("content", "")
            title = data.get("title", "")
            if not content or not title:
                continue

            enriched_data = None
            try:
                from data_enrichment import fetch_country_data
                enriched_data = fetch_country_data(entity.get("iso_code", ""))
            except ImportError:
                pass

            html = build_html(entity, "cost-of-living", title, content, enriched_data=enriched_data)
            html_file = OUTPUT_DIR / continent / slug / "cost-of-living.html"
            html_file.write_text(html, encoding="utf-8")
            rebuilt += 1
        except (json.JSONDecodeError, OSError) as e:
            log(f"Failed to rebuild hub for {slug}: {e}", "ERROR")

    log(f"Rebuilt {rebuilt} cost-of-living hub pages with new links", "SUCCESS")
    return rebuilt


def generate_batch(entity_slugs=None, angle_id=None, count=200, phase=None):
    """
    Generate multiple pages in batch. Handles all 5 phases automatically.

    Args:
        entity_slugs: List of entity slugs, or None for all
        angle_id: Single angle, or None for phase-appropriate angles
        count: Max pages to generate this run
        phase: Processing phase (1-5), or None for auto-detect
    """
    # Auto-detect phase if not specified
    if phase is None:
        from entity_discovery import detect_current_phase
        phase = detect_current_phase()
        log(f"Auto-detected phase: {phase}", "INFO")

    # ── Phase 7 & 8: delegate to Level 3 batch generator ──
    if phase in (7, 8):
        sub_type = "regions" if phase == 7 else "cities"
        return _generate_level3_auto(sub_type=sub_type, count=count)

    # ── Phase 1-3, 6: Level 2 entity pages ──
    angle_registry = load_angle_registry()
    all_angles = angle_registry.get("angles", {})
    optional = set(angle_registry.get("rules", {}).get("optional_angles", []))
    core_angles = {"overview", "geography", "must-know-truth", "positive-things",
                   "cities-and-regions", "visa-and-entry", "cost-of-living",
                   "economy", "culture", "travel-safety"}

    # Determine what to generate based on phase
    if phase == 1:
        angles_to_generate = ["overview"]
    elif phase == 2:
        angles_to_generate = [a for a in core_angles if a != "overview"]
    elif phase == 3:
        angles_to_generate = ["vs"]
    elif phase == 6:
        # Extended angles: all non-core, non-optional angles
        angles_to_generate = [a for a in all_angles if a not in core_angles and a not in optional]
    elif angle_id:
        angles_to_generate = [angle_id]
    else:
        angles_to_generate = [a for a in all_angles if a not in optional]

    # Get entities
    if entity_slugs:
        slugs = entity_slugs
    else:
        slugs = get_all_entity_slugs()

    # Build work queue: (entity_slug, angle, comparison)
    work = []
    for slug in slugs:
        entity = get_entity(slug)
        if not entity:
            continue
        continent = entity.get("continent", "general")
        for aid in angles_to_generate:
            if aid == "vs":
                # Generate vs pages for each comparison
                for comp in entity.get("common_comparisons", []):
                    vs_slug = f"vs-{slugify(comp)}"
                    existing = OUTPUT_DIR / continent / slug / f"{vs_slug}.html"
                    if not existing.exists():
                        work.append((slug, "vs", comp))
            else:
                existing = OUTPUT_DIR / continent / slug / f"{aid}.html"
                if not existing.exists():
                    work.append((slug, aid, None))

    if not work:
        log("No pages to generate (all done or none found)", "WARN")
        return []

    # Limit to count
    work = work[:count]

    log(f"Generating {len(work)} pages (Phase {phase})...")
    print("=" * 60)

    results = []
    for i, (slug, aid, comp) in enumerate(work, 1):
        entity = get_entity(slug)
        print(f"\n[{i}/{len(work)}] {entity['name']} / {aid}" + (f" (vs {comp})" if comp else ""))
        print("-" * 40)

        try:
            result = generate_page(slug, aid, comparison_entity=comp)
            if result:
                results.append(result)
        except Exception as e:
            log(f"Failed: {e}", "ERROR")

        # Rate limiting
        if i < len(work):
            time.sleep(2)

    print("\n" + "=" * 60)
    log(f"Generated {len(results)}/{len(work)} pages", "SUCCESS")

    # Update manifest and index pages
    update_manifest()
    generate_all_index_pages()

    return results


def _generate_level3_auto(sub_type="regions", count=200):
    """Automatically generate Level 3 pages across all large countries."""
    l3_registry = load_level3_registry()
    angle_registry = load_angle_registry()
    l3_angles = angle_registry.get("level3_angles", {}).get(sub_type, ["overview"])
    countries = l3_registry.get("countries", {})

    # Build global work queue across all countries
    work = []
    for country_slug, data in countries.items():
        entity = get_entity(country_slug)
        if not entity:
            continue
        continent = entity.get("continent", "general")

        if sub_type == "cities":
            sub_entities = data.get("cities", [])
            sub_entities = [{"name": c, "slug": slugify(c)} if isinstance(c, str) else c for c in sub_entities]
        else:
            sub_entities = data.get("regions", [])

        for sub in sub_entities:
            sub_name = sub if isinstance(sub, str) else sub.get("name", "")
            sub_slug = slugify(sub_name)
            for aid in l3_angles:
                existing = OUTPUT_DIR / continent / country_slug / sub_type / sub_slug / f"{aid}.html"
                if not existing.exists():
                    work.append((country_slug, sub_name, aid))

    if not work:
        log(f"No Level 3 {sub_type} pages to generate (all done)", "WARN")
        return []

    work = work[:count]
    phase_num = 7 if sub_type == "regions" else 8
    log(f"Generating {len(work)} Level 3 {sub_type} pages (Phase {phase_num})...")
    print("=" * 60)

    results = []
    for i, (country_slug, sub_name, aid) in enumerate(work, 1):
        entity = get_entity(country_slug)
        print(f"\n[{i}/{len(work)}] {entity['name']} > {sub_name} / {aid}")

        sub_entity = {
            "name": sub_name,
            "capital": "",
            "continent": entity["continent"],
            "population_millions": 0,
            "languages": entity.get("languages", []),
            "currency": entity.get("currency", ""),
            "type": sub_type.rstrip("s"),
            "parent_entity": entity["name"],
            "neighbors": [],
            "iso_code": entity.get("iso_code", ""),
            "common_comparisons": [],
        }

        angle_config = angle_registry.get("angles", {}).get(aid, {})
        prompt_key = angle_config.get("prompt_key", aid)
        prompt = get_prompt_for_angle(sub_entity, prompt_key)
        title = angle_config.get("title_pattern", "{Entity}").replace("{Entity}", sub_name)

        try:
            content = generate_with_groq(prompt, max_tokens=2000)
            result = save_level3_page(entity, sub_name, sub_type, aid, title, content)
            results.append(result)
        except Exception as e:
            log(f"Failed: {e}", "ERROR")

        if i < len(work):
            time.sleep(2)

    print("\n" + "=" * 60)
    log(f"Generated {len(results)}/{len(work)} Level 3 pages", "SUCCESS")
    update_manifest()
    generate_all_index_pages()
    return results


def generate_level3_batch(country_slug, sub_type="cities", count=50):
    """Generate Level 3 sub-entity pages."""
    entity = get_entity(country_slug)
    if not entity:
        log(f"Entity not found: {country_slug}", "ERROR")
        return []

    l3_registry = load_level3_registry()
    country_data = l3_registry.get("countries", {}).get(country_slug)
    if not country_data:
        log(f"No Level 3 data for: {country_slug}", "ERROR")
        return []

    angle_registry = load_angle_registry()
    l3_angles = angle_registry.get("level3_angles", {}).get(sub_type, ["overview"])

    # Build work queue
    if sub_type == "cities":
        sub_entities = country_data.get("cities", [])
        sub_entities = [{"name": c, "slug": slugify(c)} if isinstance(c, str) else c for c in sub_entities]
    else:
        sub_entities = country_data.get("regions", [])

    work = []
    continent = entity.get("continent", "general")
    for sub in sub_entities:
        sub_name = sub if isinstance(sub, str) else sub.get("name", "")
        sub_slug = slugify(sub_name)
        for aid in l3_angles:
            existing = OUTPUT_DIR / continent / country_slug / sub_type / sub_slug / f"{aid}.html"
            if not existing.exists():
                work.append((sub_name, aid))

    work = work[:count]
    if not work:
        log(f"No Level 3 pages to generate for {country_slug}/{sub_type}", "WARN")
        return []

    log(f"Generating {len(work)} Level 3 pages for {entity['name']}/{sub_type}...")
    results = []

    for i, (sub_name, aid) in enumerate(work, 1):
        print(f"\n[{i}/{len(work)}] {entity['name']} > {sub_name} / {aid}")

        # Build a sub-entity dict for prompt generation
        sub_entity = {
            "name": sub_name,
            "capital": "",
            "continent": entity["continent"],
            "population_millions": 0,
            "languages": entity.get("languages", []),
            "currency": entity.get("currency", ""),
            "type": sub_type.rstrip("s"),
            "parent_entity": entity["name"],
            "neighbors": [],
            "iso_code": entity.get("iso_code", ""),
            "common_comparisons": [],
        }

        angle_config = angle_registry.get("angles", {}).get(aid, {})
        prompt_key = angle_config.get("prompt_key", aid)
        prompt = get_prompt_for_angle(sub_entity, prompt_key)
        title = angle_config.get("title_pattern", "{Entity}").replace("{Entity}", sub_name)

        try:
            content = generate_with_groq(prompt, max_tokens=2000)
            result = save_level3_page(entity, sub_name, sub_type, aid, title, content)
            results.append(result)
        except Exception as e:
            log(f"Failed: {e}", "ERROR")

        if i < len(work):
            time.sleep(2)

    log(f"Generated {len(results)}/{len(work)} Level 3 pages", "SUCCESS")
    return results


# =============================================================================
# MANIFEST / STATUS
# =============================================================================

def update_manifest():
    """Update region_manifest.json with current progress."""
    manifest = load_json(REGION_MANIFEST_FILE)
    registry = load_entity_registry()
    entities = registry.get("entities", {})

    continent_stats = {}
    total_pages = 0

    for slug, entity in entities.items():
        continent = entity.get("continent", "other")
        if continent not in continent_stats:
            continent_stats[continent] = {"entities": 0, "pages_generated": 0, "pages_total": 0}

        continent_stats[continent]["entities"] += 1
        continent_stats[continent]["pages_total"] += 30

        # Count generated pages
        entity_dir = OUTPUT_DIR / continent / slug
        if entity_dir.exists():
            html_files = list(entity_dir.glob("*.html"))
            continent_stats[continent]["pages_generated"] += len(html_files)
            total_pages += len(html_files)

    for continent, stats in continent_stats.items():
        status = "completed" if stats["pages_generated"] >= stats["pages_total"] else "in_progress" if stats["pages_generated"] > 0 else "pending"
        stats["status"] = status

    manifest["continents"] = continent_stats
    manifest["totals"]["pages_generated"] = total_pages
    manifest["totals"]["entities_total"] = len(entities)
    manifest["last_updated"] = datetime.now().isoformat()

    save_json(REGION_MANIFEST_FILE, manifest)
    log(f"Manifest updated: {total_pages} pages total", "INFO")


def get_completion_status(entity_slug=None):
    """Check completion status."""
    angle_registry = load_angle_registry()
    required_angles = [a for a, cfg in angle_registry.get("angles", {}).items() if cfg.get("required")]

    if entity_slug:
        entity = get_entity(entity_slug)
        if not entity:
            return {"error": f"Entity not found: {entity_slug}"}
        continent = entity.get("continent", "general")
        entity_dir = OUTPUT_DIR / continent / entity_slug
        existing = {f.stem for f in entity_dir.glob("*.html")} if entity_dir.exists() else set()
        missing = [a for a in required_angles if a not in existing]
        return {
            "entity": entity["name"],
            "complete": len(missing) == 0,
            "generated": len(existing),
            "required": len(required_angles),
            "missing": missing,
        }

    # Global status
    all_slugs = get_all_entity_slugs()
    complete = 0
    incomplete = []
    for slug in all_slugs:
        status = get_completion_status(slug)
        if status.get("complete"):
            complete += 1
        else:
            incomplete.append(status)

    return {
        "total_entities": len(all_slugs),
        "complete": complete,
        "incomplete": len(incomplete),
        "percentage": round(complete / len(all_slugs) * 100, 1) if all_slugs else 0,
    }


# =============================================================================
# REBUILD PIPELINE
# =============================================================================

def rebuild_all_html():
    """Re-render all HTML pages from stored JSON data.
    Applies new template features (TOC, verified factbox, related links,
    last-updated, editorial footer) without regenerating content from AI.
    """
    json_files = list(OUTPUT_DIR.rglob("*.json"))
    log(f"Found {len(json_files)} JSON files to rebuild")

    rebuilt = 0
    errors = 0

    for json_file in json_files:
        if json_file.name in ("index.json", "manifest.json"):
            continue

        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log(f"  Skip {json_file}: {e}", "WARN")
            errors += 1
            continue

        content = data.get("content", "")
        if not content:
            continue

        entity_slug = data.get("entity_slug", "")
        angle_id = data.get("angle", "")
        title = data.get("title", "")

        if not entity_slug or not angle_id:
            continue

        entity = get_entity(entity_slug)
        if not entity:
            log(f"  Entity not found: {entity_slug}", "WARN")
            errors += 1
            continue

        # Fetch enriched data
        enriched_data = None
        try:
            from data_enrichment import fetch_country_data
            enriched_data = fetch_country_data(entity.get("iso_code", ""))
        except ImportError:
            pass

        # Rebuild HTML
        html = build_html(entity, angle_id, title, content, enriched_data=enriched_data)

        html_file = json_file.with_suffix(".html")
        html_file.write_text(html, encoding="utf-8")
        rebuilt += 1

    log(f"Rebuilt {rebuilt} HTML pages ({errors} errors)", "SUCCESS")
    return rebuilt


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="GlobalCountryPages Generator")
    parser.add_argument("--entity", help="Generate for specific entity slug")
    parser.add_argument("--angle", help="Generate specific angle")
    parser.add_argument("--generate-batch", action="store_true", help="Batch generate pages")
    parser.add_argument("--count", type=int, default=200, help="Pages per batch run")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 6, 7, 8], help="Processing phase")
    parser.add_argument("--continent", help="Filter by continent")
    parser.add_argument("--level3", help="Generate Level 3 for country slug")
    parser.add_argument("--level3-type", default="cities", choices=["cities", "regions"])
    parser.add_argument("--status", action="store_true", help="Show completion status")
    parser.add_argument("--status-entity", help="Show status for specific entity")
    parser.add_argument("--update-manifest", action="store_true", help="Update manifest")
    parser.add_argument("--generate-indexes", action="store_true", help="Regenerate all index pages")
    parser.add_argument("--rebuild-html", action="store_true", help="Rebuild all HTML from JSON with new template features")
    # Cost expansion CLI flags
    parser.add_argument("--generate-cost-angles", action="store_true", help="Generate cost sub-angle pages (Phase 9)")
    parser.add_argument("--generate-cost-comparisons", action="store_true", help="Generate cost comparison pages (Phase 10)")
    parser.add_argument("--regenerate-cost-hubs", action="store_true", help="Rebuild cost-of-living hub pages with sub-angle links (Phase 11)")

    args = parser.parse_args()

    # Helper to resolve entity filter
    def _resolve_entity_slugs():
        entity_slugs = None
        if args.entity:
            entity_slugs = [args.entity]
        elif args.continent:
            registry = load_entity_registry()
            entity_slugs = [
                slug for slug, e in registry.get("entities", {}).items()
                if e.get("continent") == args.continent
            ]
        return entity_slugs

    # Cost expansion commands
    if args.generate_cost_angles:
        entity_slugs = _resolve_entity_slugs()
        generate_cost_angles_batch(entity_slugs=entity_slugs, count=args.count)
        return

    if args.generate_cost_comparisons:
        entity_slugs = _resolve_entity_slugs()
        generate_cost_comparisons_batch(entity_slugs=entity_slugs, count=args.count)
        return

    if args.regenerate_cost_hubs:
        entity_slugs = _resolve_entity_slugs()
        regenerate_cost_hubs(entity_slugs=entity_slugs if entity_slugs else None)
        return

    if args.rebuild_html:
        count = rebuild_all_html()
        print(f"\nRebuilt {count} HTML pages with new template features.")
        return

    if args.status or args.status_entity:
        status = get_completion_status(args.status_entity)
        print(json.dumps(status, indent=2))
        return

    if args.update_manifest:
        update_manifest()
        return

    if args.generate_indexes:
        generate_all_index_pages()
        return

    if args.level3:
        generate_level3_batch(args.level3, sub_type=args.level3_type, count=args.count)
        return

    if args.entity and args.angle:
        # Support cost sub-angles via --entity + --angle
        cost_registry_path = BASE_DIR / "cost_angle_registry.json"
        cost_angle_ids = set()
        if cost_registry_path.exists():
            try:
                cost_reg = json.loads(cost_registry_path.read_text(encoding="utf-8"))
                cost_angle_ids = set(cost_reg.get("cost_angles", {}).keys())
            except (json.JSONDecodeError, OSError):
                pass

        if args.angle in cost_angle_ids:
            generate_cost_page(args.entity, args.angle)
        else:
            generate_page(args.entity, args.angle)
        return

    if args.generate_batch:
        # Filter by continent if specified
        entity_slugs = None
        if args.continent:
            registry = load_entity_registry()
            entity_slugs = [
                slug for slug, e in registry.get("entities", {}).items()
                if e.get("continent") == args.continent
            ]

        generate_batch(
            entity_slugs=entity_slugs,
            angle_id=args.angle,
            count=args.count,
            phase=args.phase,
        )
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
