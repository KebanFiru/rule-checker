#!/usr/bin/env python3
"""Chooses the skill's own ID prefixes so they cannot be confused with IDs of the documents (standard library only).

  prefixes.py work/ex/*.txt [-o work/prefixes.json]        run at the START of a run, on the text of the target AND every reference

Own IDs: rules R-, facts F-, the target's own rules SD-, open decisions TBD-, internal findings IF-. If a document uses a prefix (with or without hyphen:
"R-3", "R7", "IF-2"), that kind switches to RC-R / RC-F / RC-SD / RC-TBD / RC-IF (then RC2-…). The choice is written to prefixes.json and
progress.json, stated at the top of the report, and enforced by matrix.py verify. IDs that exist only inside images are not seen.
"""
import argparse, json, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from id_index import parse_lines
import progress

DEFAULT = {"rule": "R", "fact": "F", "self": "SD", "tbd": "TBD", "finding": "IF"}
LABEL = {"rule": "rules", "fact": "facts", "self": "target's own rules", "tbd": "decisions", "finding": "internal findings"}


def pattern(prefix):
    """The prefix used as an ID, hyphenated or not; not as the tail of a longer one (FR-1, RC-R-001)."""
    return re.compile(rf"(?<![\w-]){re.escape(prefix)}-?\d+(?![^\W_])")


def first_use(prefix, files):
    rx = pattern(prefix)
    for f in files:
        for loc, text in parse_lines(f):
            m = rx.search(text)
            if m:
                return f"{m.group(0)} in {Path(f).stem} {loc}"
    return None


def choose(files):
    files = sorted(str(f) for f in files)
    chosen, collisions = {}, []
    for kind, base in DEFAULT.items():
        for cand in [base, f"RC-{base}"] + [f"RC{n}-{base}" for n in range(2, 10)]:
            used = first_use(cand, files)
            if not used:
                chosen[kind] = cand
                break
            collisions.append({"kind": kind, "prefix": cand, "found": used})
        else:
            sys.exit(f"no free prefix for {kind}")
    return {"prefixes": chosen, "collisions": collisions, "scanned": [Path(f).name for f in files]}


def load(work):
    """(prefixes, file content or None)."""
    p = Path(work) / "prefixes.json"
    if not p.exists():
        return dict(DEFAULT), None
    d = json.loads(p.read_text(encoding="utf-8"))
    return {**DEFAULT, **d["prefixes"]}, d


def texts(work):
    """(extracted text files, errors). The directories come from progress.json (else prefixes.json, else work/ex); a missing or
    empty extraction is an error, never a silently empty check."""
    work = Path(work)
    state = progress.load(work / "progress.json")
    dirs = state.get("extract_dirs") or (load(work)[1] or {}).get("extract_dirs") or ["ex"]
    files, errors = [], []
    for d in dirs:
        p = Path(d) if Path(d).is_absolute() else work / d
        found = sorted(str(f) for f in p.glob("*.txt") if not f.name.endswith((".second.txt", ".tables.txt")) and f.stat().st_size) if p.is_dir() else []
        if not found:
            errors.append(f"no extracted text in {d} (relative to the work folder): run extract.py, then prefixes.py on its .txt files")
        files += found
    return files, errors


def describe(data):
    line = "- ID prefixes: " + ", ".join(f"{LABEL[k]} {v}-" for k, v in data["prefixes"].items())
    if data["collisions"]:
        line += " (changed because the documents use them: " + "; ".join(f"{c['prefix']}: {c['found']}" for c in data["collisions"]) + ")"
    return line


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("-o", "--out", default="work/prefixes.json")
    a = ap.parse_args()
    files = [f for f in a.files if not f.endswith((".second.txt", ".tables.txt"))]
    data = choose(files)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    data["extract_dirs"] = sorted({os.path.relpath(Path(f).resolve().parent, out.parent.resolve()) for f in files})
    old = load(out.parent)[1]
    if old and old["prefixes"] != data["prefixes"] and (out.parent / "rules.json").exists():
        print("WARNING: the prefixes changed after the register was written: renumber rules.json, results.json, tbd.json and internal.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    state = progress.load(out.parent / "progress.json"); state["prefixes"] = data["prefixes"]; state["extract_dirs"] = data["extract_dirs"]; progress.save(out.parent / "progress.json", state)
    print(describe(data)[2:])
    p = data["prefixes"]
    print(f"Use {p['rule']}-001, {p['fact']}-001, {p['self']}-001, {p['tbd']}-1, {p['finding']}-1 in every work file -> {out}")


if __name__ == "__main__":
    main()
