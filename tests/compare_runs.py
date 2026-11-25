#!/usr/bin/env python3
"""Compares two output directories of run_deterministic.sh and classifies every difference (standard library only).
Usage: compare_runs.py DIR_A DIR_B [--log-a A.log --log-b B.log]
Classes: identical | expected environment difference | (a) text extraction only | (b) finding/verdict difference | (c) script error"""
import argparse, json, re, sys
from pathlib import Path

ENV_PREFIXES = ("s1docx/", "s1/ex_tables/", "s1/env.json", "s1/coverage_env.md", "s1/report_env.md")


def files(d):
    return {str(p.relative_to(d)): p for p in sorted(Path(d).rglob("*")) if p.is_file() and not p.is_symlink() and "fixtures" not in p.parts[:2]}


def classify(rel, pa, pb):
    if pa is None or pb is None:
        return "expected environment difference" if rel.startswith(ENV_PREFIXES) else "(c) file only in one run"
    if pa.read_bytes() == pb.read_bytes():
        return "identical"
    if rel.startswith(ENV_PREFIXES):
        return "expected environment difference"
    if "/ex/" in "/" + rel and rel.endswith(".json"):                 # extraction metadata: engines/versions differ by design
        ja, jb = json.loads(pa.read_text()), json.loads(pb.read_text())
        for j in (ja, jb):
            j.pop("engines", None); j["warnings"] = [w for w in j.get("warnings", []) if "different word sets" not in w and "Page count differs" not in w]
            j.pop("engine_diffs", None)
        return "expected environment difference" if ja == jb else "(b) finding/verdict difference (extraction metadata)"
    if "/ex/" in "/" + rel and rel.endswith(".txt"):
        ta, tb = pa.read_text(), pb.read_text()
        strip = lambda s: re.sub(r"p\d+:L\d+\t", "", s)
        if "".join(strip(ta).split()) == "".join(strip(tb).split()):
            return "(a) text extraction only (whitespace/line breaks/line numbers)"
        return "(a) text extraction only (words differ)"
    return "(b) finding/verdict difference"


def scorer_lines(log):
    return [l.strip() for l in Path(log).read_text(encoding="utf-8", errors="replace").splitlines() if l.lstrip().startswith(("✓", "✗", "SUMMARY"))] if log else []


def engine_warnings(d):
    pdfs = disagree = 0
    for p in Path(d).rglob("*.json"):
        if "/ex" in str(p) or p.parent.name.startswith("ex"):
            try: j = json.loads(p.read_text())
            except Exception: continue
            if j.get("engines", {}).get("second_opinion"):
                pdfs += 1; disagree += any("different word sets" in w for w in j.get("warnings", []))
    return pdfs, disagree


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--log-a"); ap.add_argument("--log-b")
    x = ap.parse_args(); fa, fb = files(x.a), files(x.b)
    classes = {}
    for rel in sorted(set(fa) | set(fb)):
        classes.setdefault(classify(rel, fa.get(rel), fb.get(rel)), []).append(rel)
    for k in ("identical", "expected environment difference", "(a) text extraction only (whitespace/line breaks/line numbers)", "(a) text extraction only (words differ)"):
        pass
    for k, v in sorted(classes.items(), key=lambda kv: (kv[0] != "identical", kv[0])):
        print(f"  {k}: {len(v)} file(s)" + ("" if k == "identical" or len(v) > 6 else "  " + ", ".join(v)))
    la, lb = scorer_lines(x.log_a), scorer_lines(x.log_b)
    for lg in (x.log_a, x.log_b):
        if lg and "Traceback" in Path(lg).read_text(errors="replace"):
            classes.setdefault("(c) script error", []).append(lg); print(f"  (c) script error: Traceback in {lg}")
    print(f"  scorer lines identical: {la == lb} ({len(la)} lines; ✗ in A: {sum('✗' in l for l in la)}, in B: {sum('✗' in l for l in lb)})")
    bad = [k for k in classes if k.startswith(("(b)", "(c)"))]
    print("  => " + ("NO finding/verdict differences, no script errors" if not bad else "ATTENTION: " + ", ".join(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
