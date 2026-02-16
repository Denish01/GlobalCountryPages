"""
Sitemap Generator for GlobalCountryPages.
Crawls generated_pages/ directory structure and builds sitemap.xml.
Supports 3-level depth: continent/country/angle + continent/country/regions|cities/sub/angle.
"""

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "generated_pages"

try:
    from config import SITE_URL
except ImportError:
    import os
    SITE_URL = os.environ.get("SITE_URL", "https://360nations.com")

SKIP_FILES = {"robots.txt", "sitemap.xml", "CNAME", ".nojekyll"}

# Priority by angle type
ANGLE_PRIORITY = {
    "overview": "1.0",
    "geography": "0.8",
    "must-know-truth": "0.8",
    "positive-things": "0.7",
    "cities-and-regions": "0.8",
    "visa-and-entry": "0.9",
    "cost-of-living": "0.8",
    "economy": "0.7",
    "culture": "0.8",
    "travel-safety": "0.9",
    # New angles - Practical / Travel
    "food-and-cuisine": "0.9",
    "language-guide": "0.7",
    "transportation": "0.8",
    "best-time-to-visit": "0.9",
    "top-things-to-do": "0.9",
    "where-to-stay": "0.8",
    "internet-and-connectivity": "0.6",
    # New angles - Living / Expat
    "moving-there": "0.7",
    "education": "0.7",
    "real-estate": "0.7",
    "taxes": "0.7",
    "healthcare": "0.8",
    "retirement": "0.7",
    "digital-nomad-guide": "0.7",
    # New angles - Deeper Understanding
    "history-timeline": "0.8",
    "politics-and-government": "0.6",
    "demographics": "0.6",
    "infrastructure": "0.6",
    "business-and-investment": "0.7",
}


def get_priority(filename):
    """Get sitemap priority for a page."""
    stem = Path(filename).stem
    if stem.startswith("vs-"):
        return "0.6"
    return ANGLE_PRIORITY.get(stem, "0.5")


def get_all_pages():
    """Crawl all generated pages and collect URLs."""
    pages = []

    if not OUTPUT_DIR.exists():
        return pages

    for continent_dir in sorted(OUTPUT_DIR.iterdir()):
        if not continent_dir.is_dir() or continent_dir.name in SKIP_FILES:
            continue

        continent = continent_dir.name

        # Continent index page (e.g. /africa/)
        continent_index = continent_dir / "index.html"
        if continent_index.exists():
            mtime = datetime.fromtimestamp(continent_index.stat().st_mtime)
            pages.append({
                "url": f"/{continent}/",
                "lastmod": mtime.strftime("%Y-%m-%d"),
                "priority": "0.9",
                "changefreq": "weekly",
            })

        for country_dir in sorted(continent_dir.iterdir()):
            if not country_dir.is_dir():
                continue

            country = country_dir.name

            # Country index page (e.g. /africa/nigeria/)
            country_index = country_dir / "index.html"
            if country_index.exists():
                mtime = datetime.fromtimestamp(country_index.stat().st_mtime)
                pages.append({
                    "url": f"/{continent}/{country}/",
                    "lastmod": mtime.strftime("%Y-%m-%d"),
                    "priority": "0.8",
                    "changefreq": "weekly",
                })

            # Level 2 pages: direct HTML files (skip index.html, already added above)
            for html_file in sorted(country_dir.glob("*.html")):
                if html_file.name == "index.html":
                    continue
                url_path = f"/{continent}/{country}/{html_file.name}"
                mtime = datetime.fromtimestamp(html_file.stat().st_mtime)

                pages.append({
                    "url": url_path,
                    "lastmod": mtime.strftime("%Y-%m-%d"),
                    "priority": get_priority(html_file.name),
                    "changefreq": "monthly",
                })

            # Level 3 pages: regions/ and cities/ subdirectories
            for sub_type in ["regions", "cities"]:
                sub_dir = country_dir / sub_type
                if not sub_dir.exists():
                    continue

                for sub_entity_dir in sorted(sub_dir.iterdir()):
                    if not sub_entity_dir.is_dir():
                        continue

                    sub_entity = sub_entity_dir.name

                    for html_file in sorted(sub_entity_dir.glob("*.html")):
                        url_path = f"/{continent}/{country}/{sub_type}/{sub_entity}/{html_file.name}"
                        mtime = datetime.fromtimestamp(html_file.stat().st_mtime)

                        pages.append({
                            "url": url_path,
                            "lastmod": mtime.strftime("%Y-%m-%d"),
                            "priority": str(max(0.3, float(get_priority(html_file.name)) - 0.1)),
                            "changefreq": "monthly",
                        })

    return pages


def generate_sitemap_xml(pages, base_url=None):
    """Generate sitemap.xml content."""
    base = (base_url or SITE_URL).rstrip("/")

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    # Add homepage
    xml_lines.append("  <url>")
    xml_lines.append(f"    <loc>{base}/</loc>")
    xml_lines.append(f"    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>")
    xml_lines.append("    <changefreq>daily</changefreq>")
    xml_lines.append("    <priority>1.0</priority>")
    xml_lines.append("  </url>")

    for page in pages:
        full_url = base + quote(page["url"])
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{full_url}</loc>")
        xml_lines.append(f"    <lastmod>{page['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{page['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{page['priority']}</priority>")
        xml_lines.append("  </url>")

    xml_lines.append("</urlset>")
    return "\n".join(xml_lines)


def main():
    pages = get_all_pages()
    print(f"Found {len(pages)} pages")

    sitemap_xml = generate_sitemap_xml(pages)

    output_file = OUTPUT_DIR / "sitemap.xml"
    output_file.write_text(sitemap_xml, encoding="utf-8")
    print(f"Sitemap written to {output_file} ({len(pages)} URLs)")


if __name__ == "__main__":
    main()
