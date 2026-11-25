#!/usr/bin/env python3
"""Cross-reference / ID consistency check + number-unit consistency.

Usage: xref_check.py extracted/target.txt [...] [--patterns P] [--numbers] [-o xref_report.md]
Findings: undefined reference, unreferenced definition, duplicate definition, numbering gap, same ID with different titles,
          (--numbers) different number+unit values for the same concept.
Note: heuristic; verify every finding in the document (false positives are possible).
"""
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from id_index import load_patterns, build_index, parse_lines


def split_id(i):
    m = re.match(r"^(.*?)(\d+(?:\.\d+)*)$", i)
    return (m.group(1), [int(x) for x in m.group(2).split(".")]) if m else (i, [])


def gaps(idx):
    fam = defaultdict(set)
    for i, e in idx.items():
        if not e["defs"]:
            continue
        pre, nums = split_id(i)
        if nums:
            fam[(pre, tuple(nums[:-1]))].add(nums[-1])
    out = []
    for (pre, parent), s in sorted(fam.items()):
        full = set(range(1, max(s) + 1)); miss = sorted(full - s)
        if miss:
            par = ".".join(map(str, parent)) + "." if parent else ""
            out.append(f"{pre}{par}: defined {sorted(s)} -> missing number(s): {miss}")
    return out


def numbers(files, units):
    unit_rx = "|".join(units)
    rx = re.compile(rf"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(?:-\s*)?({unit_rx})(?![\wçğıöşü])", re.I)
    rows = []
    for f in files:
        doc = Path(f).stem
        for loc, text in parse_lines(f):
            ids = re.findall(r"\b[A-Z]{1,4}-[A-Z]?\.?\d+(?:\.\d+)*\b", text)
            for m in rx.finditer(text):
                before = re.findall(r"[^\W\d_]{3,}", text[:m.start()].lower())[-2:]
                after = re.findall(r"[^\W\d_]{3,}", text[m.end():].lower())[:1]
                rows.append({"doc": doc, "loc": loc, "value": m.group(1), "unit": m.group(2).lower(),
                             "concept": " ".join(before + ["…"] + after), "ids": ids})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--patterns")
    ap.add_argument("--numbers", action="store_true", help="also run number+unit consistency")
    ap.add_argument("--also-numbers", nargs="*", default=[], help="extra files added only to the number inventory (e.g. the reference .txt) to see target-vs-reference value differences")
    ap.add_argument("-o", "--out", default="xref_report.md")
    a = ap.parse_args()
    pats, cfg = load_patterns(a.patterns)
    idx = build_index(a.files, pats)
    L = ["# Cross-reference report (automatic, heuristic)\n"]

    und = [(i, e) for i, e in idx.items() if e["refs"] and not e["defs"]]
    L.append(f"## Undefined references ({len(und)})")
    for i, e in sorted(und):
        for r in e["refs"]:
            L.append(f"- `{i}` referenced at {r['doc']} {r['loc']}: “{r['context']}” — not defined anywhere")
    unused = [(i, e) for i, e in idx.items() if e["defs"] and not e["refs"]]
    L.append(f"\n## Definitions never referenced ({len(unused)}) — informational")
    for i, e in sorted(unused):
        d = e["defs"][0]; L.append(f"- `{i}` ({d['doc']} {d['loc']}: {d['title'][:60]})")
    dup = [(i, e) for i, e in idx.items() if len(e["defs"]) > 1]
    L.append(f"\n## Duplicate definitions ({len(dup)})")
    for i, e in sorted(dup):
        L.append(f"- `{i}`: " + "; ".join(f"{d['doc']} {d['loc']} «{d['title'][:50]}»" for d in e["defs"]))
    L.append("\n## Same ID, different title")
    n = 0
    for i, e in sorted(idx.items()):
        titles = {re.sub(r"\W+", " ", d["title"].lower()).strip() for d in e["defs"]}
        if len(titles) > 1:
            n += 1; L.append(f"- `{i}`: " + " ≠ ".join(f"«{d['title'][:50]}» ({d['loc']})" for d in e["defs"]))
    if not n: L.append("- (none)")
    g = gaps(idx)
    L.append(f"\n## Numbering gaps ({len(g)})")
    L += [f"- {x}" for x in g] or ["- (none)"]

    if a.numbers:
        rows = numbers(a.files + a.also_numbers, cfg["units"])
        L.append(f"\n## Number+unit inventory ({len(rows)} occurrences)")
        by = defaultdict(list)
        for r in rows:
            by[(r["unit"], r["concept"])].append(r)
        L.append("\n### Same unit + same context, different value (flagged)")
        flagged = 0
        for (u, c), rs in sorted(by.items()):
            if len({r["value"] for r in rs}) > 1:
                flagged += 1
                L.append(f"- **{u}** «{c}»: " + ", ".join(f"{r['value']} ({r['doc']} {r['loc']})" for r in rs))
        if not flagged: L.append("- (none)")
        cur = {r["unit"] for r in rows} & {"€", "eur", "tl"}
        if len(cur) > 1:
            L.append("- **Mixed currencies**: " + ", ".join(sorted(cur)) + " appear together (is a single currency required?)")
        # all values of the same unit even if contexts differ (to scan by eye)
        L.append("\n### All values per unit (the concept may be worded differently; scan manually)")
        per = defaultdict(lambda: defaultdict(list))
        for r in rows: per[r["unit"]][r["value"]].append(f"{r['loc']}")
        for u, d in sorted(per.items()):
            L.append(f"- **{u}**: " + "; ".join(f"{v} → {', '.join(l[:4])}" for v, l in sorted(d.items())))
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
