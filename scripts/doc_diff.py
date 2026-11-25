#!/usr/bin/env python3
"""Section/ID-level diff between two document versions (PDF/DOCX/extract .txt).

Unit = a block starting with an ID (UC-3.8, SP-7.3, FR-2 …) or a numbered heading block. Units are aligned by key.
Output: added / removed / changed units, format-only differences (line breaks, hyphens, whitespace, footers = NOISE),
moved units (order changed), and the changed number+unit and ID lists.
Usage: doc_diff.py old.pdf new.pdf [-o diff.json] [--patterns P]
"""
import argparse, difflib, json, re, sys, unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from id_index import load_patterns, blocks_by_id

FOOT = re.compile(r"^\s*(Sayfa|Page)\s*\d+(\s*/\s*\d+)?\s*$", re.I)


def load_lines(path):
    p = Path(path); suf = p.suffix.lower()
    if suf == ".txt":
        out = []
        for raw in p.read_text(encoding="utf-8").splitlines():
            if "\t" in raw: out.append(tuple(raw.split("\t", 1)))
        return out
    import extract
    if suf == ".pdf":
        return [(f"p{pi}:L{li}", l) for pi, ls in enumerate(extract.pdf_pages(p), 1) for li, l in enumerate(ls, 1)]
    if suf == ".docx":
        return [(b["loc"], b["text"]) for b in extract.docx_blocks(p)[0]]
    raise SystemExit(f"Unsupported type: {path}")


def norm(t):
    t = unicodedata.normalize("NFKC", t).replace("­", "").lower()
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)          # end-of-line hyphenation
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"\s+([.,;:)])", r"\1", t).strip()


NUM = re.compile(r"\d+(?:[.,]\d+)?\s*(?:gün|day|hafta|ay|ECTS|€|EUR|USD|TL|%|MB|GB|saat|sn|saniye|dakika|dk|karakter|adet|kişi|week|month|hour|minute|second|sec|min|character|char|item|person)\w*", re.I)
IDS = re.compile(r"\b[A-Z]{1,4}-[A-Z]?\.?\d+(?:\.(?:X)?\d+)*\b")


def units(path, pats):
    lines = [(l, t) for l, t in load_lines(path) if not FOOT.match(t)]
    return blocks_by_id(lines, pats)


def diff(old_path, new_path, pats):
    ob, nb = units(old_path, pats), units(new_path, pats)
    od, nd = {b["key"]: b for b in ob}, {b["key"]: b for b in nb}
    res = {"old": str(old_path), "new": str(new_path), "added": [], "removed": [], "changed": [], "format_only": [], "moved": []}
    for k in nd:
        if k not in od: res["added"].append({"key": k, "loc": nd[k]["loc"], "text": nd[k]["text"], "after": _prev(nb, k)})
    for k in od:
        if k not in nd: res["removed"].append({"key": k, "loc": od[k]["loc"], "text": od[k]["text"]})
    for k in od:
        if k not in nd: continue
        a, b = od[k], nd[k]
        if a["text"] == b["text"]:
            if a.get("nlines") != b.get("nlines"): res["format_only"].append(k)   # line breaks only
            continue
        na, nb_ = norm(a["text"]), norm(b["text"])
        if na == nb_:
            res["format_only"].append(k); continue
        wa, wb = na.split(), nb_.split()
        sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
        rem, add = [], []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op in ("replace", "delete"): rem.append(" ".join(wa[i1:i2]))
            if op in ("replace", "insert"): add.append(" ".join(wb[j1:j2]))
        n_o, n_n = NUM.findall(a["text"]), NUM.findall(b["text"])
        i_o, i_n = set(IDS.findall(a["text"])), set(IDS.findall(b["text"]))
        res["changed"].append({"key": k, "loc_old": a["loc"], "loc_new": b["loc"], "old": a["text"], "new": b["text"],
                               "words_removed": rem, "words_added": add,
                               "numbers": {"removed": [x for x in n_o if x not in n_n], "added": [x for x in n_n if x not in n_o]},
                               "ids": {"removed": sorted(i_o - i_n), "added": sorted(i_n - i_o)}})
    common = set(od) & set(nd)
    so, sn = [b["key"] for b in ob if b["key"] in common], [b["key"] for b in nb if b["key"] in common]
    sm = difflib.SequenceMatcher(None, so, sn, autojunk=False)
    kept = {so[i] for m in sm.get_matching_blocks() for i in range(m.a, m.a + m.size)}
    for k in sn:
        if k not in kept:
            res["moved"].append({"key": k, "old_prev": _prev(ob, k), "new_prev": _prev(nb, k),
                                 "note": "order changed (this unit or its neighbour may have been moved)"})
    return res


def _prev(blocks, key):
    for i, b in enumerate(blocks):
        if b["key"] == key: return blocks[i - 1]["key"] if i else None


def render_md(r):
    L = [f"# Document diff: {r['old']} → {r['new']}\n",
         f"added {len(r['added'])} · removed {len(r['removed'])} · changed {len(r['changed'])} · moved {len(r['moved'])} · format-only (noise) {len(r['format_only'])}\n"]
    for c in r["changed"]:
        L.append(f"- **CHANGED {c['key']}** ({c['loc_old']}→{c['loc_new']}): −«{' / '.join(c['words_removed'])}» +«{' / '.join(c['words_added'])}»"
                 + (f" · numbers: {c['numbers']['removed']}→{c['numbers']['added']}" if c['numbers']['removed'] or c['numbers']['added'] else "")
                 + (f" · ID: −{c['ids']['removed']} +{c['ids']['added']}" if c['ids']['removed'] or c['ids']['added'] else ""))
    for a in r["added"]: L.append(f"- **ADDED {a['key']}** ({a['loc']}, after {a['after']}): {a['text'][:100]}")
    for a in r["removed"]: L.append(f"- **REMOVED {a['key']}** ({a['loc']}): {a['text'][:100]}")
    for m in r["moved"]: L.append(f"- **MOVED {m['key']}**: previous neighbour {m['old_prev']} → new neighbour {m['new_prev']}")
    if r["format_only"]: L.append("- noise (format only): " + ", ".join(r["format_only"]))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("old"); ap.add_argument("new")
    ap.add_argument("-o", "--out", default="diff.json"); ap.add_argument("--patterns")
    a = ap.parse_args(); pats, _ = load_patterns(a.patterns)
    r = diff(a.old, a.new, pats)
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_md(r); Path(a.out).with_suffix(".md").write_text(md, encoding="utf-8"); print(md)


if __name__ == "__main__":
    main()
