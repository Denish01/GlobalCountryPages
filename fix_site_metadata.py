"""
One-time metadata repair for the already-generated pages (2026-07-22).

Fixes, deterministically from each file's real path (no LLM calls, no content change):
  1. Canonical + JSON-LD url/mainEntityOfPage that pointed at the parent country
     page instead of the page itself (region/sub-entity pages self-cannibalized).
  2. Broken internal links that used the linking page's continent for a target on
     a different continent (e.g. /south-america/mexico/... -> /north-america/mexico/...).

The generator (country_pages.py, save_level3_page + build_related_links) is fixed
separately so regenerations are correct.
"""
import os, re, glob
from collections import defaultdict

ROOT = "generated_pages"
SITE = "https://360nations.com"

htmls = glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True)
existing = set(os.path.relpath(f, ROOT).replace("\\", "/") for f in htmls)

# tail (path without leading continent segment) -> [full relpaths], for relocating links
tail_map = defaultdict(list)
for e in existing:
    parts = e.split("/", 1)
    if len(parts) == 2:
        tail_map[parts[1]].append(e)

link_re = re.compile(r'href="(/[^"?:#]+\.html)"')
canon_re = re.compile(r'<link rel="canonical" href="([^"]+)"')

def expected_canonical(rel):
    # index.html is served at its clean directory URL, so it canonicals there
    # (root "/" or "/africa/"), NOT at "/index.html". Everything else self-canonicals.
    if rel == "index.html":
        return f"{SITE}/"
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[:-len('index.html')]}"
    return f"{SITE}/{rel}"

canon_fixed = 0
files_link_fixed = 0
links_fixed = 0
unresolved = set()

for f in htmls:
    rel = os.path.relpath(f, ROOT).replace("\\", "/")
    correct = expected_canonical(rel)
    txt = open(f, encoding="utf-8").read()
    orig = txt

    # 1) self-canonical (also fixes JSON-LD url/mainEntityOfPage/Country url, same string)
    m = canon_re.search(txt)
    if m and m.group(1) != correct:
        txt = txt.replace(m.group(1), correct)
        canon_fixed += 1

    # 2) relocate broken internal links
    n_here = [0]
    def fix_link(mo):
        href = mo.group(1)
        target = href.lstrip("/")
        if target in existing:
            return mo.group(0)
        parts = target.split("/", 1)
        if len(parts) == 2 and parts[1] in tail_map:
            cands = tail_map[parts[1]]
            if len(cands) == 1:  # unambiguous relocation
                n_here[0] += 1
                return f'href="/{cands[0]}"'
        unresolved.add(href)
        return mo.group(0)
    txt = link_re.sub(fix_link, txt)
    if n_here[0]:
        files_link_fixed += 1
        links_fixed += n_here[0]

    if txt != orig:
        open(f, "w", encoding="utf-8").write(txt)

print(f"pages scanned:            {len(htmls)}")
print(f"canonicals repaired:      {canon_fixed}")
print(f"broken links relocated:   {links_fixed} across {files_link_fixed} files")
print(f"unresolved broken links:  {len(unresolved)} distinct" + (f" (e.g. {sorted(unresolved)[:3]})" if unresolved else ""))
