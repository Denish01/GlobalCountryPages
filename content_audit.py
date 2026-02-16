"""
Content Audit Script for 360Nations
Scans generated pages, flags thin content, cross-references with entity registry.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "generated_pages"
ENTITY_REGISTRY_FILE = BASE_DIR / "entity_registry.json"


def load_entity_registry():
    """Load entity registry for size_class cross-referencing."""
    if ENTITY_REGISTRY_FILE.exists():
        return json.loads(ENTITY_REGISTRY_FILE.read_text(encoding="utf-8"))
    return {}


def scan_pages():
    """Scan all generated JSON files and collect word counts."""
    pages = []
    for json_file in sorted(OUTPUT_DIR.rglob("*.json")):
        if json_file.name in ("index.json", "manifest.json"):
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        content = data.get("content", "")
        word_count = len(content.split()) if content else 0
        rel_path = json_file.relative_to(OUTPUT_DIR)

        pages.append({
            "path": str(rel_path),
            "entity": data.get("entity", ""),
            "entity_slug": data.get("entity_slug", ""),
            "iso_code": data.get("iso_code", ""),
            "continent": data.get("continent", ""),
            "angle": data.get("angle", ""),
            "word_count": word_count,
            "generated_date": data.get("generated_date", ""),
        })

    return pages


def audit(thin_threshold=400):
    """Run full content audit with entity registry cross-referencing.

    Args:
        thin_threshold: Pages below this word count are flagged as thin.

    Returns:
        dict with audit results
    """
    pages = scan_pages()
    if not pages:
        print("No pages found to audit.")
        return {}

    # Load entity registry for size_class info
    registry = load_entity_registry()
    entities = registry.get("entities", {})

    thin_pages = []
    for p in pages:
        if p["word_count"] < thin_threshold:
            # Cross-reference with entity registry
            entity_data = entities.get(p["entity_slug"], {})
            p["size_class"] = entity_data.get("size_class", "unknown")
            thin_pages.append(p)

    word_counts = [p["word_count"] for p in pages]

    report = {
        "audit_date": datetime.now().isoformat(),
        "thin_threshold": thin_threshold,
        "total_pages": len(pages),
        "thin_pages_count": len(thin_pages),
        "thin_percentage": round(len(thin_pages) / len(pages) * 100, 1) if pages else 0,
        "avg_word_count": round(sum(word_counts) / len(word_counts)) if word_counts else 0,
        "min_word_count": min(word_counts) if word_counts else 0,
        "max_word_count": max(word_counts) if word_counts else 0,
        "thin_pages": sorted(thin_pages, key=lambda p: p["word_count"]),
        "by_continent": {},
        "by_size_class": {},
        "by_angle": {},
    }

    # Group by continent
    by_continent = {}
    for p in pages:
        c = p.get("continent", "unknown")
        by_continent.setdefault(c, []).append(p["word_count"])
    for c, counts in sorted(by_continent.items()):
        thin_in = sum(1 for wc in counts if wc < thin_threshold)
        report["by_continent"][c] = {
            "total": len(counts),
            "thin": thin_in,
            "avg_words": round(sum(counts) / len(counts)) if counts else 0,
        }

    # Group thin pages by size_class
    size_counts = {}
    for p in thin_pages:
        sc = p.get("size_class", "unknown")
        size_counts.setdefault(sc, 0)
        size_counts[sc] += 1
    report["by_size_class"] = dict(sorted(size_counts.items()))

    # Group by angle
    by_angle = {}
    for p in pages:
        a = p.get("angle", "unknown")
        by_angle.setdefault(a, []).append(p["word_count"])
    for a, counts in sorted(by_angle.items()):
        thin_in = sum(1 for wc in counts if wc < thin_threshold)
        report["by_angle"][a] = {
            "total": len(counts),
            "thin": thin_in,
            "avg_words": round(sum(counts) / len(counts)) if counts else 0,
        }

    # Write reports
    report_file = BASE_DIR / "audit_report.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Audit report saved to: {report_file}")

    noindex_file = BASE_DIR / "noindex_pages.txt"
    noindex_lines = [p["path"] for p in thin_pages]
    noindex_file.write_text("\n".join(noindex_lines), encoding="utf-8")
    print(f"Noindex list saved to: {noindex_file} ({len(noindex_lines)} pages)")

    # Print summary
    print(f"\n{'='*50}")
    print(f"360Nations Content Audit")
    print(f"{'='*50}")
    print(f"Total pages: {report['total_pages']}")
    print(f"Thin pages (<{thin_threshold} words): {report['thin_pages_count']} ({report['thin_percentage']}%)")
    print(f"Average word count: {report['avg_word_count']}")
    print(f"Range: {report['min_word_count']} - {report['max_word_count']} words")

    print(f"\nBy continent:")
    for c, stats in report["by_continent"].items():
        print(f"  {c}: {stats['total']} pages, {stats['thin']} thin, avg {stats['avg_words']} words")

    print(f"\nThin pages by entity size class:")
    for sc, count in report["by_size_class"].items():
        print(f"  {sc}: {count} thin pages")

    if thin_pages:
        print(f"\nThinnest pages:")
        for p in thin_pages[:10]:
            sc = p.get("size_class", "?")
            print(f"  {p['word_count']:4d} words [{sc}] - {p['path']}")

    return report


if __name__ == "__main__":
    threshold = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    audit(thin_threshold=threshold)
