"""
Country Page Generator
Generates evergreen reference pages for 249 countries/territories.
11 angles per entity, with Level 3 sub-entity expansion.

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
    SITE_NAME = "Global Country Guide"
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
# 11 ANGLE PROMPTS
# =============================================================================

def get_prompt_for_angle(entity, angle_id, comparison_entity=None):
    """Build the AI prompt for a given entity + angle."""
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

    prompts = {
        "overview": f"""Write an overview page about {name}.

{context}

Structure:
1. IDENTITY: What {name} is (sovereign nation/territory/etc), where it sits, sovereignty status
2. AT A GLANCE: Key facts - capital, population, languages, currency, time zone
3. BRIEF HISTORY: 3-4 sentences covering founding/independence and key milestones
4. WHAT MAKES IT UNIQUE: 3-4 distinctive characteristics
5. QUICK SUMMARY: One sentence capturing the essence of {name}

Rules: 800 words, factual, evergreen, no opinions, 8th-grade reading level, no emojis, no markdown.""",

        "geography": f"""Write a geography page about {name}.

{context}

Structure:
1. LOCATION: Exact position, borders, what region/continent it belongs to
2. TERRAIN & LANDSCAPE: Mountains, rivers, deserts, coastlines, notable features
3. CLIMATE: Weather patterns, seasons, temperature ranges
4. BEST TIME TO VISIT: Optimal months and why
5. NATURAL HIGHLIGHTS: National parks, natural wonders, biodiversity
6. SIZE COMPARISON: Compare land area to well-known reference countries

Rules: 700 words, factual, evergreen, no opinions, 8th-grade reading level, no emojis, no markdown.""",

        "must_know_truth": f"""Write a "must-know truth" page about {name}.

{context}

Structure:
1. REAL HISTORY: Colonial history (if any), independence story, or "never colonized" status
2. THINGS MOST PEOPLE GET WRONG: 4-5 common misconceptions and the truth
3. CHALLENGES: Current realities people should know about (poverty, governance, etc.)
4. RESILIENCE: How the country has overcome or is addressing challenges
5. WHAT THE MEDIA MISSES: Nuanced facts that don't make headlines

Rules: 800 words, factual, balanced, no propaganda, no sensationalism, 8th-grade reading level, no emojis, no markdown.""",

        "positive_things": f"""Write a page about positive things about {name}.

{context}

Structure:
1. ACHIEVEMENTS: Notable accomplishments in science, sport, arts, development
2. CULTURAL TREASURES: UNESCO sites, traditions, art forms worth celebrating
3. PEOPLE & VALUES: Hospitality, community values, notable figures
4. INNOVATION & PROGRESS: Modern achievements, economic growth, tech
5. HIDDEN GEMS: Underappreciated positive aspects
6. WHY PEOPLE LOVE IT: What visitors and residents consistently praise

Rules: 700 words, factual, genuinely positive without being promotional, 8th-grade reading level, no emojis, no markdown.""",

        "cities_and_regions": f"""Write a cities and regions guide for {name}.

{context}

Structure:
1. ADMINISTRATIVE STRUCTURE: How {name} is divided (states/provinces/regions/etc.)
2. MAJOR CITIES: Top 5-8 cities with brief description of each (character, population, role)
3. KEY REGIONS: Notable regions and what they're known for
4. REGIONAL DIFFERENCES: Cultural, economic, or geographic variations
5. GETTING AROUND: How regions connect (transport overview)

Rules: 900 words, factual, evergreen, useful for trip planning, 8th-grade reading level, no emojis, no markdown.""",

        "visa_and_entry": f"""Write a visa and entry requirements page for {name}.

{context}

Structure:
1. GENERAL POLICY: Visa-free, visa-on-arrival, or visa-required overview
2. BY VISITOR TYPE: Requirements for tourists, business travelers, students, workers
3. COMMON NATIONALITIES: Visa rules for US, UK, EU, Australian, Canadian citizens
4. DOCUMENTS NEEDED: Passport validity, photos, proof of funds, return ticket
5. BORDER CROSSINGS: Entry points, land borders, airport procedures
6. TIPS: Common mistakes to avoid, processing times

Note: Use general/typical requirements. Add disclaimer that rules change and travelers should verify with official sources.

Rules: 700 words, factual, practical, evergreen framework, 8th-grade reading level, no emojis, no markdown.""",

        "cost_of_living": f"""Write a cost of living page for {name}.

{context}

Structure:
1. OVERVIEW: How affordable is {name} compared to global averages
2. ACCOMMODATION: Typical rent prices (budget/mid-range/luxury)
3. FOOD & DINING: Meal costs (street food, casual restaurant, fine dining)
4. TRANSPORT: Public transit, taxis, fuel prices
5. DAILY ESSENTIALS: Groceries, utilities, internet, mobile
6. BUDGET BREAKDOWN: Sample monthly budgets for budget/mid-range/comfortable lifestyles
7. MONEY TIPS: How to save, where to splurge

Rules: 700 words, use approximate ranges not exact prices, evergreen framework, 8th-grade reading level, no emojis, no markdown.""",

        "economy": f"""Write an economy page about {name}.

{context}

Structure:
1. ECONOMIC OVERVIEW: GDP, income level, economic classification
2. KEY INDUSTRIES: Top 3-5 industries driving the economy
3. TRADE: Major exports and imports, key trading partners
4. INFRASTRUCTURE: Transport, energy, digital connectivity
5. EMPLOYMENT: Job market, key sectors, unemployment context
6. ECONOMIC OUTLOOK: Growth trajectory and development priorities

Rules: 700 words, factual, use ranges not exact figures, evergreen framework, 8th-grade reading level, no emojis, no markdown.""",

        "culture": f"""Write a culture page about {name}.

{context}

Structure:
1. CULTURAL IDENTITY: What defines {name}'s culture, key influences
2. FOOD & CUISINE: Signature dishes, eating customs, food culture
3. TRADITIONS & FESTIVALS: Major celebrations, customs, rituals
4. ETIQUETTE: Social norms, do's and don'ts for visitors
5. ARTS & MUSIC: Notable art forms, music genres, literature
6. LANGUAGE: How language shapes culture, useful phrases for visitors

Rules: 800 words, respectful, informative, celebratory without stereotyping, 8th-grade reading level, no emojis, no markdown.""",

        "travel_safety": f"""Write a travel safety page for {name}.

{context}

Structure:
1. OVERALL SAFETY LEVEL: General safety assessment for tourists
2. COMMON RISKS: Petty crime, scams, natural hazards specific to {name}
3. AREAS TO AVOID: Regions or neighborhoods with higher risk
4. HEALTH: Vaccinations, water safety, medical facilities
5. EMERGENCY INFO: Emergency numbers, embassy contacts framework
6. SAFETY TIPS: Practical advice for staying safe
7. WOMEN/SOLO TRAVELERS: Specific considerations if applicable

Add disclaimer that safety conditions change and travelers should check current advisories.

Rules: 600 words, factual, helpful without being alarmist, 8th-grade reading level, no emojis, no markdown.""",

        "vs": f"""Write a comparison page: {name} vs {comparison_entity or entity.get('common_comparisons', [''])[0]}.

{context}

Compare {name} with {comparison_entity or entity.get('common_comparisons', [''])[0]}.

Structure:
1. WHY PEOPLE COMPARE THEM: What makes this comparison common
2. KEY DIFFERENCES: 5-6 major differences (geography, culture, cost, etc.)
3. KEY SIMILARITIES: 3-4 things they share
4. FOR TRAVELERS: Which suits what type of traveler
5. SIDE BY SIDE: Quick comparison of key stats (size, population, cost level, language, climate)
6. VERDICT: Not a winner, but clarifying which excels at what

Rules: 800 words, balanced, no bias, practical for decision-making, 8th-grade reading level, no emojis, no markdown.""",
    }

    return prompts.get(angle_id, prompts["overview"])


# =============================================================================
# HTML TEMPLATE
# =============================================================================

def build_html(entity, angle_id, title, content, breadcrumbs=None):
    """Build themed HTML page for a country angle."""
    continent = entity.get("continent", "europe")
    colors = CONTINENT_COLORS.get(continent, CONTINENT_COLORS["europe"])
    flag = iso_to_flag(entity.get("iso_code", ""))
    entity_name = entity["name"]

    # Convert content to HTML paragraphs
    html_content = content_to_html(content)

    # Build breadcrumb HTML
    if not breadcrumbs:
        breadcrumbs = [
            ("Home", "/"),
            (colors["name"], f"/{continent}/"),
            (entity_name, f"/{continent}/{slugify(entity_name)}/"),
            (angle_id.replace("-", " ").title(), None),
        ]

    breadcrumb_html = ' &raquo; '.join(
        f'<a href="{url}">{label}</a>' if url else f'<span>{label}</span>'
        for label, url in breadcrumbs
    )

    # Build angle navigation
    angle_registry = load_angle_registry()
    angles = angle_registry.get("angles", {})
    angle_nav_items = []
    entity_slug = slugify(entity_name)
    for aid, aconfig in angles.items():
        if aid == "vs":
            continue
        is_active = "active" if aid == angle_id else ""
        angle_label = aid.replace("-", " ").title()
        angle_nav_items.append(
            f'<a href="/{continent}/{entity_slug}/{aid}.html" class="angle-link {is_active}">{angle_label}</a>'
        )
    angle_nav_html = "\n        ".join(angle_nav_items)

    meta_desc = f"{title} - Comprehensive guide to {entity_name}. {SITE_NAME}."

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{meta_desc}">
    <title>{title} | {SITE_NAME}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.7;
            color: #2d3436;
            background: #fafafa;
        }}
        header {{
            background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']});
            color: white;
            padding: 24px 0;
        }}
        header .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 0 20px;
        }}
        header h1 {{
            font-size: 1.8em;
            font-weight: 700;
        }}
        .flag {{ font-size: 1.4em; margin-right: 8px; }}
        .breadcrumb {{
            max-width: 900px;
            margin: 0 auto;
            padding: 12px 20px;
            font-size: 0.85em;
            color: #636e72;
        }}
        .breadcrumb a {{ color: {colors['primary']}; text-decoration: none; }}
        .breadcrumb a:hover {{ text-decoration: underline; }}
        .angle-nav {{
            max-width: 900px;
            margin: 0 auto;
            padding: 0 20px 16px;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .angle-link {{
            display: inline-block;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.82em;
            text-decoration: none;
            color: #636e72;
            background: #f1f2f6;
            transition: all 0.2s;
        }}
        .angle-link:hover {{ background: #dfe6e9; }}
        .angle-link.active {{
            background: {colors['primary']};
            color: white;
        }}
        article {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            margin-bottom: 40px;
        }}
        article h2 {{
            color: {colors['primary']};
            margin: 28px 0 12px;
            padding-bottom: 6px;
            border-bottom: 2px solid {colors['primary']}22;
        }}
        article h3 {{ color: #2d3436; margin: 20px 0 8px; }}
        article p {{ margin-bottom: 14px; }}
        article ul, article ol {{ padding-left: 24px; margin-bottom: 14px; }}
        article li {{ margin-bottom: 6px; }}
        footer {{
            text-align: center;
            padding: 30px 20px;
            color: #b2bec3;
            font-size: 0.8em;
        }}
        footer a {{ color: #636e72; }}
        @media (max-width: 600px) {{
            header h1 {{ font-size: 1.3em; }}
            .angle-nav {{ gap: 4px; }}
            .angle-link {{ padding: 4px 10px; font-size: 0.75em; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1><span class="flag">{flag}</span> {title}</h1>
        </div>
    </header>

    <nav class="breadcrumb">{breadcrumb_html}</nav>

    <nav class="angle-nav">
        {angle_nav_html}
    </nav>

    <article>
        {html_content}
    </article>

    <footer>
        <p>&copy; {datetime.now().year} {SITE_NAME}. Evergreen reference content.</p>
        <p>This page contains factual, timeless information. Always verify visa and safety details with official sources.</p>
    </footer>
</body>
</html>"""
    return html


def content_to_html(content):
    """Convert AI-generated text content into HTML."""
    lines = content.strip().split("\n")
    html_parts = []
    in_list = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        # Headers
        if line.upper() == line and len(line) > 3 and not line.startswith("-") and not line.startswith("*") and ":" in line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            heading = line.rstrip(":").strip()
            html_parts.append(f"<h2>{heading.title()}</h2>")
            continue

        # Numbered section headers like "1. IDENTITY:" or "1. IDENTITY"
        num_header = re.match(r'^\d+\.\s+([A-Z][A-Z\s&/,\'-]+):?\s*$', line)
        if num_header:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            heading = num_header.group(1).strip().rstrip(":")
            html_parts.append(f"<h2>{heading.title()}</h2>")
            continue

        # Section headers like "IDENTITY:" at start of line followed by content
        section_match = re.match(r'^(\d+\.\s+)?([A-Z][A-Z\s&/,\'-]+):\s+(.+)', line)
        if section_match and len(section_match.group(2)) > 2:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            heading = section_match.group(2).strip()
            rest = section_match.group(3).strip()
            html_parts.append(f"<h2>{heading.title()}</h2>")
            html_parts.append(f"<p>{rest}</p>")
            continue

        # Bullet points
        if line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item = line.lstrip("-*• ").strip()
            html_parts.append(f"<li>{item}</li>")
            continue

        # Regular paragraph
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        html_parts.append(f"<p>{line}</p>")

    if in_list:
        html_parts.append("</ul>")

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


def save_page(entity, angle_id, title, content):
    """Save page in HTML, JSON, and MD formats."""
    continent = entity.get("continent", "general")
    entity_slug = slugify(entity["name"])

    # Create output directory
    page_dir = OUTPUT_DIR / continent / entity_slug
    page_dir.mkdir(parents=True, exist_ok=True)

    # Generate all formats
    html = build_html(entity, angle_id, title, content)
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

    log(f"Generating: {entity['name']} / {angle_id}...")
    content = generate_with_groq(prompt, max_tokens=angle_config.get("word_target", 800) * 3)

    # Save
    if angle_id == "vs" and comparison_entity:
        vs_slug = f"vs-{slugify(comparison_entity)}"
        title_vs = f"{entity['name']} vs {comparison_entity}"
        return save_page(entity, vs_slug, title_vs, content)
    else:
        return save_page(entity, angle_id, title, content)


def generate_batch(entity_slugs=None, angle_id=None, count=200, phase=None):
    """
    Generate multiple pages in batch.

    Args:
        entity_slugs: List of entity slugs, or None for all
        angle_id: Single angle, or None for phase-appropriate angles
        count: Max pages to generate this run
        phase: Processing phase (1-5)
    """
    angle_registry = load_angle_registry()
    all_angles = angle_registry.get("angles", {})

    # Determine what to generate based on phase
    if phase == 1:
        angles_to_generate = ["overview"]
    elif phase == 2:
        angles_to_generate = [a for a in all_angles if a != "overview" and a != "vs"]
    elif phase == 3:
        angles_to_generate = ["vs"]
    elif angle_id:
        angles_to_generate = [angle_id]
    else:
        angles_to_generate = [a for a in all_angles if a != "vs"]

    # Get entities
    if entity_slugs:
        slugs = entity_slugs
    else:
        slugs = get_all_entity_slugs()

    # Build work queue: (entity_slug, angle)
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

    log(f"Generating {len(work)} pages...")
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

    # Update manifest
    update_manifest()

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
        continent_stats[continent]["pages_total"] += 11

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
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="GlobalCountryPages Generator")
    parser.add_argument("--entity", help="Generate for specific entity slug")
    parser.add_argument("--angle", help="Generate specific angle")
    parser.add_argument("--generate-batch", action="store_true", help="Batch generate pages")
    parser.add_argument("--count", type=int, default=200, help="Pages per batch run")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5], help="Processing phase")
    parser.add_argument("--continent", help="Filter by continent")
    parser.add_argument("--level3", help="Generate Level 3 for country slug")
    parser.add_argument("--level3-type", default="cities", choices=["cities", "regions"])
    parser.add_argument("--status", action="store_true", help="Show completion status")
    parser.add_argument("--status-entity", help="Show status for specific entity")
    parser.add_argument("--update-manifest", action="store_true", help="Update manifest")

    args = parser.parse_args()

    if args.status or args.status_entity:
        status = get_completion_status(args.status_entity)
        print(json.dumps(status, indent=2))
        return

    if args.update_manifest:
        update_manifest()
        return

    if args.level3:
        generate_level3_batch(args.level3, sub_type=args.level3_type, count=args.count)
        return

    if args.entity and args.angle:
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
