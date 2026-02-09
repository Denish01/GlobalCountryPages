"""
Entity Discovery & Queue Manager
Phase-based processing for GlobalCountryPages.
Picks next work unit, locks it, tracks completion.
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "generated_pages"
ENTITY_REGISTRY_FILE = BASE_DIR / "entity_registry.json"
LEVEL3_REGISTRY_FILE = BASE_DIR / "level3_registry.json"
ANGLE_REGISTRY_FILE = BASE_DIR / "angle_registry.json"
PENDING_ENTITIES_FILE = BASE_DIR / "pending_entities.json"
REGION_MANIFEST_FILE = BASE_DIR / "region_manifest.json"
EXPANSION_RULES_FILE = BASE_DIR / "expansion_rules.json"

CONTINENT_ORDER = ["africa", "asia", "europe", "north-america", "south-america", "oceania"]


def load_json(filepath):
    if Path(filepath).exists():
        return json.loads(Path(filepath).read_text(encoding="utf-8"))
    return {}


def save_json(filepath, data):
    Path(filepath).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def slugify(text):
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def detect_current_phase():
    """Detect which phase we're in based on what's been generated."""
    registry = load_json(ENTITY_REGISTRY_FILE)
    angle_reg = load_json(ANGLE_REGISTRY_FILE)
    entities = registry.get("entities", {})
    required_angles = [a for a, cfg in angle_reg.get("angles", {}).items() if a != "vs"]

    overview_done = 0
    full_done = 0
    vs_done = 0
    total = len(entities)

    for slug, entity in entities.items():
        continent = entity.get("continent", "general")
        entity_dir = OUTPUT_DIR / continent / slug
        if not entity_dir.exists():
            continue
        existing = {f.stem for f in entity_dir.glob("*.html")}

        if "overview" in existing:
            overview_done += 1
        if all(a in existing for a in required_angles):
            full_done += 1
        if any(f.startswith("vs-") for f in existing):
            vs_done += 1

    # Determine phase
    if overview_done < total:
        return 1
    elif full_done < total:
        return 2
    elif vs_done < total * 0.5:  # At least half should have vs pages
        return 3
    else:
        # Check Level 3
        l3_reg = load_json(LEVEL3_REGISTRY_FILE)
        countries = l3_reg.get("countries", {})
        l3_regions_done = True
        for country_slug, data in countries.items():
            entity = entities.get(country_slug, {})
            continent = entity.get("continent", "general")
            for region in data.get("regions", []):
                r_slug = slugify(region.get("name", region) if isinstance(region, dict) else region)
                if not (OUTPUT_DIR / continent / country_slug / "regions" / r_slug / "overview.html").exists():
                    l3_regions_done = False
                    break
        if not l3_regions_done:
            return 4
        return 5

    return 1


def get_next_work_unit(phase=None):
    """Determine next entity+angle to process."""
    if phase is None:
        phase = detect_current_phase()

    registry = load_json(ENTITY_REGISTRY_FILE)
    angle_reg = load_json(ANGLE_REGISTRY_FILE)
    entities = registry.get("entities", {})

    if phase == 1:
        # Find entities without overview
        for continent in CONTINENT_ORDER:
            for slug, entity in entities.items():
                if entity.get("continent") != continent:
                    continue
                entity_dir = OUTPUT_DIR / continent / slug
                if not (entity_dir / "overview.html").exists():
                    return {"phase": 1, "entity": slug, "angle": "overview", "continent": continent}

    elif phase == 2:
        # Find entities missing required angles (excluding vs)
        required = [a for a, cfg in angle_reg.get("angles", {}).items() if cfg.get("required") and a != "vs"]
        for continent in CONTINENT_ORDER:
            for slug, entity in entities.items():
                if entity.get("continent") != continent:
                    continue
                entity_dir = OUTPUT_DIR / continent / slug
                existing = {f.stem for f in entity_dir.glob("*.html")} if entity_dir.exists() else set()
                for angle in required:
                    if angle not in existing:
                        return {"phase": 2, "entity": slug, "angle": angle, "continent": continent}

    elif phase == 3:
        # Find entities needing vs pages
        for slug, entity in entities.items():
            continent = entity.get("continent", "general")
            comparisons = entity.get("common_comparisons", [])
            for comp in comparisons:
                vs_slug = f"vs-{slugify(comp)}"
                entity_dir = OUTPUT_DIR / continent / slug
                if not (entity_dir / f"{vs_slug}.html").exists():
                    return {"phase": 3, "entity": slug, "angle": "vs", "comparison": comp, "continent": continent}

    elif phase == 4:
        # Level 3 regions
        l3_reg = load_json(LEVEL3_REGISTRY_FILE)
        l3_angles = angle_reg.get("level3_angles", {}).get("regions", ["overview"])
        for country_slug, data in l3_reg.get("countries", {}).items():
            entity = entities.get(country_slug, {})
            continent = entity.get("continent", "general")
            for region in data.get("regions", []):
                r_name = region.get("name", region) if isinstance(region, dict) else region
                r_slug = slugify(r_name)
                for angle in l3_angles:
                    if not (OUTPUT_DIR / continent / country_slug / "regions" / r_slug / f"{angle}.html").exists():
                        return {"phase": 4, "entity": country_slug, "sub_type": "regions", "sub_entity": r_name, "angle": angle, "continent": continent}

    elif phase == 5:
        # Level 3 cities
        l3_reg = load_json(LEVEL3_REGISTRY_FILE)
        l3_angles = angle_reg.get("level3_angles", {}).get("cities", ["overview"])
        for country_slug, data in l3_reg.get("countries", {}).items():
            entity = entities.get(country_slug, {})
            continent = entity.get("continent", "general")
            for city in data.get("cities", []):
                c_name = city if isinstance(city, str) else city.get("name", "")
                c_slug = slugify(c_name)
                for angle in l3_angles:
                    if not (OUTPUT_DIR / continent / country_slug / "cities" / c_slug / f"{angle}.html").exists():
                        return {"phase": 5, "entity": country_slug, "sub_type": "cities", "sub_entity": c_name, "angle": angle, "continent": continent}

    return None


def lock_entity(entity_slug):
    """Lock an entity for processing."""
    pending = load_json(PENDING_ENTITIES_FILE)
    pending["processing"] = entity_slug
    save_json(PENDING_ENTITIES_FILE, pending)
    return True


def unlock_entity(entity_slug, status="completed"):
    """Unlock an entity after processing."""
    pending = load_json(PENDING_ENTITIES_FILE)
    if pending.get("processing") == entity_slug:
        pending["processing"] = None
    if status == "completed" and entity_slug not in pending.get("completed", []):
        pending.setdefault("completed", []).append(entity_slug)
    save_json(PENDING_ENTITIES_FILE, pending)
    return True


def check_closure(continent=None):
    """Check if a continent (or all) has achieved closure."""
    registry = load_json(ENTITY_REGISTRY_FILE)
    angle_reg = load_json(ANGLE_REGISTRY_FILE)
    entities = registry.get("entities", {})
    required = [a for a, cfg in angle_reg.get("angles", {}).items() if cfg.get("required")]

    results = {}
    for slug, entity in entities.items():
        c = entity.get("continent", "general")
        if continent and c != continent:
            continue

        if c not in results:
            results[c] = {"total": 0, "complete": 0, "incomplete": []}

        results[c]["total"] += 1
        entity_dir = OUTPUT_DIR / c / slug
        existing = {f.stem for f in entity_dir.glob("*.html")} if entity_dir.exists() else set()

        if all(a in existing for a in required):
            results[c]["complete"] += 1
        else:
            missing = [a for a in required if a not in existing]
            results[c]["incomplete"].append({"entity": slug, "missing": missing})

    for c, data in results.items():
        data["percentage"] = round(data["complete"] / data["total"] * 100, 1) if data["total"] else 0
        data["is_closed"] = data["complete"] == data["total"]

    return results


def pick_next_continent():
    """Pick the next continent to process (for phase 2)."""
    closure = check_closure()
    for continent in CONTINENT_ORDER:
        if continent in closure and not closure[continent]["is_closed"]:
            return continent
    return None


def main():
    parser = argparse.ArgumentParser(description="Entity Discovery & Queue Manager")
    parser.add_argument("--pick-next", action="store_true", help="Pick next work unit")
    parser.add_argument("--phase", type=int, help="Override phase detection")
    parser.add_argument("--lock", help="Lock entity for processing")
    parser.add_argument("--unlock", help="Unlock entity after processing")
    parser.add_argument("--check-closure", nargs="?", const="all", help="Check closure status")
    parser.add_argument("--detect-phase", action="store_true", help="Detect current phase")

    args = parser.parse_args()

    if args.detect_phase:
        phase = detect_current_phase()
        print(f"CURRENT_PHASE={phase}")
        return

    if args.pick_next:
        unit = get_next_work_unit(phase=args.phase)
        if unit:
            print(f"NEXT_ENTITY={unit['entity']}")
            print(f"NEXT_ANGLE={unit['angle']}")
            print(f"NEXT_PHASE={unit['phase']}")
            print(f"NEXT_CONTINENT={unit.get('continent', '')}")
            if unit.get("comparison"):
                print(f"NEXT_COMPARISON={unit['comparison']}")
            if unit.get("sub_entity"):
                print(f"NEXT_SUB_ENTITY={unit['sub_entity']}")
                print(f"NEXT_SUB_TYPE={unit['sub_type']}")
        else:
            print("ALL_COMPLETE=true")
        return

    if args.lock:
        lock_entity(args.lock)
        print(f"Locked: {args.lock}")
        return

    if args.unlock:
        unlock_entity(args.unlock)
        print(f"Unlocked: {args.unlock}")
        return

    if args.check_closure is not None:
        continent = None if args.check_closure == "all" else args.check_closure
        results = check_closure(continent)
        print(json.dumps(results, indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
