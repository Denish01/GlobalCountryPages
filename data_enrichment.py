"""
Data Enrichment Module for 360Nations
Fetches real data from REST Countries API and builds verified factboxes.
"""

import json
import os
import time
from pathlib import Path

try:
    import urllib.request
    import urllib.error
    URLLIB_AVAILABLE = True
except ImportError:
    URLLIB_AVAILABLE = False

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)

ENTITY_REGISTRY_FILE = BASE_DIR / "entity_registry.json"


def fetch_country_data(iso_code):
    """Fetch country data from REST Countries API.
    Caches results to data_cache/{ISO}.json for offline use.

    Args:
        iso_code: 2-letter ISO country code (e.g., 'US', 'FR')

    Returns:
        dict with country data, or None on failure
    """
    if not iso_code:
        return None

    iso_code = iso_code.upper()
    cache_file = CACHE_DIR / f"{iso_code}.json"

    # Return cached data if available
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch from API
    url = f"https://restcountries.com/v3.1/alpha/{iso_code}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "360Nations/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        if not raw or not isinstance(raw, list):
            return None

        data = raw[0]

        # Extract and normalize the fields we care about
        enriched = {
            "iso_code": iso_code,
            "name_common": data.get("name", {}).get("common", ""),
            "name_official": data.get("name", {}).get("official", ""),
            "capital": data.get("capital", [""])[0] if data.get("capital") else "",
            "population": data.get("population", 0),
            "area_km2": data.get("area", 0),
            "region": data.get("region", ""),
            "subregion": data.get("subregion", ""),
            "languages": data.get("languages", {}),
            "currencies": {},
            "timezones": data.get("timezones", []),
            "borders": data.get("borders", []),
            "flag_emoji": data.get("flag", ""),
            "coat_of_arms_svg": data.get("coatOfArms", {}).get("svg", ""),
            "maps_google": data.get("maps", {}).get("googleMaps", ""),
            "independent": data.get("independent", True),
            "un_member": data.get("unMember", False),
            "landlocked": data.get("landlocked", False),
            "driving_side": data.get("car", {}).get("side", ""),
            "start_of_week": data.get("startOfWeek", ""),
            "continents": data.get("continents", []),
            "latlng": data.get("latlng", []),
            "gini": data.get("gini", {}),
        }

        # Parse currencies
        for code, info in data.get("currencies", {}).items():
            enriched["currencies"][code] = {
                "name": info.get("name", ""),
                "symbol": info.get("symbol", ""),
            }

        # Cache the result
        cache_file.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")

        return enriched

    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        print(f"[!] Failed to fetch data for {iso_code}: {e}")
        return None


def format_population(pop):
    """Format population number for display."""
    if pop >= 1_000_000_000:
        return f"{pop / 1_000_000_000:.2f} billion"
    elif pop >= 1_000_000:
        return f"{pop / 1_000_000:.1f} million"
    elif pop >= 1_000:
        return f"{pop:,}"
    return str(pop)


def format_area(area_km2):
    """Format area for display."""
    if area_km2 >= 1_000_000:
        return f"{area_km2:,.0f} km² ({area_km2 * 0.386102:.0f} sq mi)"
    elif area_km2 >= 1000:
        return f"{area_km2:,.0f} km² ({area_km2 * 0.386102:,.0f} sq mi)"
    return f"{area_km2:,.1f} km²"


def build_verified_factbox(entity, enriched):
    """Build an HTML factbox with verified data from REST Countries API.

    Args:
        entity: Entity dict from entity_registry
        enriched: Dict from fetch_country_data()

    Returns:
        HTML string for the verified factbox
    """
    if not enriched:
        return ""

    rows = []

    if enriched.get("name_official"):
        rows.append(("Official Name", enriched["name_official"]))

    if enriched.get("capital"):
        rows.append(("Capital", enriched["capital"]))

    if enriched.get("population"):
        rows.append(("Population", format_population(enriched["population"])))

    if enriched.get("area_km2"):
        rows.append(("Area", format_area(enriched["area_km2"])))

    if enriched.get("languages"):
        lang_names = list(enriched["languages"].values())
        rows.append(("Languages", ", ".join(lang_names[:5])))

    if enriched.get("currencies"):
        currency_strs = []
        for code, info in enriched["currencies"].items():
            symbol = info.get("symbol", "")
            name = info.get("name", code)
            currency_strs.append(f"{name} ({symbol})" if symbol else name)
        rows.append(("Currency", ", ".join(currency_strs)))

    if enriched.get("timezones"):
        tz = enriched["timezones"]
        if len(tz) <= 3:
            rows.append(("Timezone", ", ".join(tz)))
        else:
            rows.append(("Timezones", f"{tz[0]} to {tz[-1]} ({len(tz)} zones)"))

    if enriched.get("region"):
        sub = enriched.get("subregion", "")
        region_str = f"{enriched['region']}" + (f" / {sub}" if sub else "")
        rows.append(("Region", region_str))

    if enriched.get("driving_side"):
        rows.append(("Drives on", enriched["driving_side"].title()))

    if not rows:
        return ""

    fact_rows_html = ""
    for key, val in rows:
        fact_rows_html += f'    <div class="fact-row"><span class="fact-key">{key}</span><span class="fact-val">{val}</span></div>\n'

    return f"""<div class="factbox verified-factbox">
    <h3>Verified Facts</h3>
{fact_rows_html}    <div style="font-size:11px;color:#9CA3AF;margin-top:8px;text-align:right;">Source: REST Countries API</div>
</div>"""


def prefetch_all(registry_path=None):
    """Batch-fetch data for all entities in the registry.

    Args:
        registry_path: Path to entity_registry.json. Defaults to standard location.
    """
    if registry_path is None:
        registry_path = ENTITY_REGISTRY_FILE

    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    entities = registry.get("entities", {})

    total = len(entities)
    fetched = 0
    cached = 0
    failed = 0

    print(f"Prefetching data for {total} entities...")

    for slug, entity in entities.items():
        iso_code = entity.get("iso_code", "")
        if not iso_code:
            continue

        cache_file = CACHE_DIR / f"{iso_code.upper()}.json"
        if cache_file.exists():
            cached += 1
            continue

        result = fetch_country_data(iso_code)
        if result:
            fetched += 1
            print(f"  [+] {entity.get('name', slug)}: OK")
        else:
            failed += 1
            print(f"  [!] {entity.get('name', slug)}: FAILED")

        # Rate limiting: be kind to the free API
        time.sleep(0.5)

    print(f"\nDone: {fetched} fetched, {cached} already cached, {failed} failed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "prefetch":
        prefetch_all()
    elif len(sys.argv) > 1:
        iso = sys.argv[1].upper()
        data = fetch_country_data(iso)
        if data:
            print(json.dumps(data, indent=2))
        else:
            print(f"No data for {iso}")
    else:
        print("Usage:")
        print("  python data_enrichment.py prefetch    # Fetch all entities")
        print("  python data_enrichment.py US           # Fetch single country")
