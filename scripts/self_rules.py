#!/usr/bin/env python3
"""The TARGET'S OWN rules (constraints, invariants, consistency rules it declares itself). Kept apart from the reference register,
so they never count as reference coverage and need no "source assumption" mark. Standard library only.

  self_rules.py scan work/ex/target.txt [--prefix XY] [-o work/self_sections.json]
        candidates: sections headed constraint / invariant / integrity / consistency rule / business rule / kısıt / bütünlük /
        tutarlılık / iş kuralı …, and ID lists the target defines (IC-, BR-, C- … with any number of members; other prefixes from 3)
  self_rules.py classify work/self_sections.json part.json
        {"<candidate id>": {"class": "self-rules" | "not-rules", "reason": "required for not-rules"}}
Then register each declared rule in work/self_rules.json (same schema as rules.json):
  {"rules": [{"id": "SD-001", "doc_id": "IC-1", "source": {"doc": "target.pdf", "page": 8, "section": "target#4.1", "quote": "…"}}]}
and judge them with `matrix.py set-bulk work/self_results.json …`. verify: see check().
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from id_index import parse_lines, doc_stem
import section_inventory, progress

CLASSES = ("self-rules", "not-rules")
TITLE = re.compile(r"constraint|invariant|integrity|consistency\s+(?:rule|check|constraint)|business\s+rule|"
                   r"k[ıi]s[ıi]t|bütünlük|tutarlılık|iş\s+kural|değişmez", re.I)
KNOWN = {"IC", "BR", "C", "INV", "CR", "CON"}          # listed whatever their number of members
DEFINITION = re.compile(r"^[\s•*\-]*(?:\|\s*)?([A-Z]{1,4})-(\d+(?:\.\d+)*)(?![\w-])(?=\W*\S)")


def definitions(lines, extra=()):
    """{id: (prefix, loc)} for IDs defined at the start of a line or in the first table cell."""
    out = {}
    for loc, text in lines:
        m = DEFINITION.match(text)
        if m:
            out.setdefault(f"{m.group(1)}-{m.group(2)}", (m.group(1), loc))
    return out


def scan(path, extra=()):
    lines = list(parse_lines(path)); doc = doc_stem(path)
    order = {loc: i for i, (loc, _) in enumerate(lines)}
    defs = definitions(lines)
    found, covered = [], set()
    for s in section_inventory.scan_doc(path):
        if TITLE.search(s["title"]):
            a, b = order[s["start"]], order[s["end"]]
            ids = [i for i, (_, loc) in defs.items() if a <= order[loc] <= b]
            covered |= set(ids)
            found.append({"id": s["id"], "kind": "section", "title": s["title"], "section": s["id"], "loc": s["start"], "ids": ids})
    families = {}
    for i, (prefix, loc) in defs.items():
        families.setdefault(prefix, []).append(i)
    for prefix, ids in sorted(families.items()):
        left = [i for i in ids if i not in covered]
        if left and (prefix in KNOWN or prefix in extra or len(ids) >= 3):
            found.append({"id": f"{doc}#list:{prefix}", "kind": "id-list", "title": f"ID list {prefix}-", "section": "", "loc": defs[left[0]][1], "ids": left})
    return [{**c, "class": "", "reason": ""} for c in found]


def occurs(doc_id, text):
    return re.search(rf"(?<![\w-]){re.escape(doc_id)}(?![\w-]|\.\d)", text) is not None


def check(data, rules, results, target_text):
    """Errors for the self-rule gate. data: self_sections.json content; rules/results: self register and its results."""
    errors = []
    accepted = [c for c in data["candidates"] if c.get("class") == "self-rules"]
    for c in data["candidates"]:
        if c.get("class") not in CLASSES:
            errors.append(f"target's own rules: candidate not classified: {c['id']} «{c['title'][:50]}»")
        elif c["class"] == "not-rules" and not str(c.get("reason", "")).strip():
            errors.append(f"target's own rules: {c['id']} is not-rules but has no reason")
    registered = {r.get("doc_id") for r in rules if r.get("doc_id")}
    for c in accepted:
        for i in c["ids"]:
            if i not in registered:
                errors.append(f"target's own rules: {i} is declared in {c['id']} but has no row in self_rules.json")
        if not c["ids"] and not any((r.get("source") or {}).get("section") == c["section"] for r in rules):
            errors.append(f"target's own rules: no row in self_rules.json comes from {c['id']}")
    sections = {c["section"] for c in accepted if c["section"]}
    seen = set()
    for r in rules:
        rid = r["id"]; did = r.get("doc_id")
        if rid in seen: errors.append(f"{rid}: duplicate row in self_rules.json")
        seen.add(rid)
        if did and target_text is not None and not occurs(did, target_text):
            errors.append(f"{rid}: doc_id {did} does not occur in the target text")
        if not did and (r.get("source") or {}).get("section") not in sections:
            errors.append(f"{rid}: give doc_id (the target's own ID) or source.section of an accepted self-rule section")
        if rid not in results:
            errors.append(f"{rid}: the target's own rule has no result")
    return errors


def cmd_scan(a):
    out = Path(a.out)
    old = {c["id"]: c for c in json.loads(out.read_text(encoding="utf-8"))["candidates"]} if out.exists() else {}
    found = scan(a.target, tuple(a.prefix or ()))
    for c in found:
        if c["id"] in old and old[c["id"]].get("class"):
            c["class"], c["reason"] = old[c["id"]]["class"], old[c["id"]].get("reason", "")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"doc": doc_stem(a.target), "candidates": found}, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in found:
        print(f"{c['id']:<34} {c['kind']:<8} {c['loc']:<8} ids={','.join(c['ids'][:12]) or '(none: read the section)'}  «{c['title'][:50]}»  {c['class'] or '(classify)'}")
    print(f"{len(found)} candidate(s) for the target's own rules -> {out}" + ("" if found else " (check the table of contents: none detected)"))


def cmd_classify(a):
    data = json.loads(Path(a.sections).read_text(encoding="utf-8")); part = json.loads(Path(a.classes).read_text(encoding="utf-8"))
    by = {c["id"]: c for c in data["candidates"]}
    bad, done = [], []
    for cid, v in part.items():
        if cid not in by: bad.append(f"{cid}: unknown candidate")
        elif v.get("class") not in CLASSES: bad.append(f"{cid}: class must be one of {CLASSES}")
        elif v["class"] == "not-rules" and not str(v.get("reason", "")).strip(): bad.append(f"{cid}: not-rules needs a reason")
        else:
            by[cid]["class"], by[cid]["reason"] = v["class"], str(v.get("reason", "")).strip(); done.append(cid)
    Path(a.sections).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    progress.checkpoint(Path(a.sections).parent, "sections", done)
    print(f"{len(done)} classified; still open: {sum(1 for c in data['candidates'] if c.get('class') not in CLASSES)}")
    if bad:
        print("REJECTED:\n  " + "\n  ".join(bad)); sys.exit(1)


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("scan"); p.add_argument("target"); p.add_argument("--prefix", action="append"); p.add_argument("-o", "--out", default="work/self_sections.json"); p.set_defaults(f=cmd_scan)
    p = sp.add_parser("classify"); p.add_argument("sections"); p.add_argument("classes"); p.set_defaults(f=cmd_classify)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
