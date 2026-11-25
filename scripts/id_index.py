#!/usr/bin/env python3
"""Indexes the IDs in extract.py output (.txt): definitions and references are collected separately.

Definition heuristic: an ID at the start of a line (bullet/number allowed) or in the first cell of a table row
-> DEFINITION (title = text after the ID). Every other occurrence is a REFERENCE. Title/label extraction is heuristic.
Usage: id_index.py extracted/target.txt [...] [--patterns id_patterns.json] [-o index.json]
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent


def load_patterns(p=None):
    cfg = json.loads(Path(p or HERE / "id_patterns.json").read_text(encoding="utf-8"))
    return [(x["name"], re.compile(x["regex"])) for x in cfg["patterns"]], cfg


def parse_lines(path):
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if "\t" in raw:
            loc, text = raw.split("\t", 1)
            yield loc, text


def norm_id(s):
    return re.sub(r"\s+", " ", s.strip()).replace("Tablo", "Table").replace("Şekil", "Figure").replace("Fig.", "Figure")


def build_index(files, patterns):
    idx = {}
    for f in files:
        doc = Path(f).stem
        for loc, text in parse_lines(f):
            first_cell = text.split(" | ")[0].strip()
            for name, rx in patterns:
                for m in rx.finditer(text):
                    key = norm_id(m.group(0))
                    e = idx.setdefault(key, {"pattern": name, "defs": [], "refs": []})
                    at_start = m.start() == 0 or text[:m.start()].strip(" -•*0123456789.)(") == ""
                    is_cell = first_cell == m.group(0) or first_cell.startswith(m.group(0))
                    if at_start or is_cell:
                        title = text[m.end():].strip(" :-–—|").strip()
                        e["defs"].append({"doc": doc, "loc": loc, "title": title})
                    else:
                        e["refs"].append({"doc": doc, "loc": loc, "context": text.strip()[:140]})
    return idx


HEAD_RX = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+\S")


def line_def_id(text, patterns):
    """If the line starts with an ID (a definition), return the ID."""
    for name, rx in patterns:
        m = rx.match(text.lstrip(" -•*"))
        if m:
            return norm_id(m.group(0))
    return None


def blocks_by_id(lines, patterns):
    """[(loc,text)] -> ordered block list: {key,loc,text,pos}. Block = a line starting with an ID + the following ID-less lines.
    A numbered heading line also starts a block (key='H:<heading>'). Lines before the first block get key='(preamble)'."""
    blocks, cur, seen = [], None, {}
    for loc, text in lines:
        key = line_def_id(text, patterns)
        if key is None and HEAD_RX.match(text):
            key = "H:" + re.sub(r"\s+", " ", text.strip())
        if key is not None:
            seen[key] = seen.get(key, 0) + 1
            k = key if seen[key] == 1 else f"{key}#{seen[key]}"
            cur = {"key": k, "loc": loc, "text": text.strip(), "pos": len(blocks), "nlines": 1}
            blocks.append(cur)
        else:
            if cur is None:
                cur = {"key": "(preamble)", "loc": loc, "text": "", "pos": 0, "nlines": 0}; blocks.append(cur)
            cur["text"] += " " + text.strip(); cur["nlines"] += 1
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--patterns")
    ap.add_argument("-o", "--out", default="id_index.json")
    a = ap.parse_args()
    pats, _ = load_patterns(a.patterns)
    idx = build_index(a.files, pats)
    Path(a.out).write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    nd = sum(1 for v in idx.values() if v["defs"]); nr = sum(1 for v in idx.values() if v["refs"])
    print(f"{len(idx)} unique IDs  (defined={nd}, referenced={nr}) -> {a.out}")


if __name__ == "__main__":
    main()
