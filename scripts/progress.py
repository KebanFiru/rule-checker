#!/usr/bin/env python3
"""Intermediate state file work/progress.json (standard library only), so long runs can resume after the context is summarized.

  progress.py show work/progress.json                              what is done (read this FIRST when resuming)
  progress.py step work/progress.json STEP done|running|skipped [--reason "..."]
                                                                    record a workflow step; "skipped" REQUIRES a reason and is counted in the report
Other scripts record their own checkpoints automatically: `matrix.py set-bulk` (rule blocks), `visual_inventory.py record`
(visual pages), `section_inventory.py classify` (reference sections), `param_check.py verdict` (parameter conflicts).
"""
import argparse, json, sys
from pathlib import Path


def load(path):
    p = Path(path)
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for k, v in (("steps", {}), ("rule_blocks", []), ("visual_pages", []), ("sections", []), ("param_verdicts", [])):
        d.setdefault(k, v)
    return d


def save(path, data):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def checkpoint(workdir, key, values):
    """Merge `values` into progress.json[key] in workdir. `rule_blocks` entries are appended, the other lists are sets."""
    path = Path(workdir) / "progress.json"
    d = load(path)
    if key == "rule_blocks":
        d[key] += [v for v in values if v not in d[key]]
    else:
        d[key] = sorted(set(d[key]) | set(values))
    save(path, d)


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("show"); p.add_argument("file")
    p = sp.add_parser("step"); p.add_argument("file"); p.add_argument("step"); p.add_argument("state", choices=("done", "running", "skipped")); p.add_argument("--reason", default="")
    a = ap.parse_args()
    d = load(a.file)
    if a.cmd == "step":
        if a.state == "skipped" and not a.reason.strip():
            sys.exit("a skipped step needs --reason")
        d["steps"][a.step] = {"state": a.state, "reason": a.reason.strip()}
        save(a.file, d)
    for k, v in d["steps"].items():
        print(f"step {k}: {v['state']}" + (f" ({v['reason']})" if v["reason"] else ""))
    for b in d["rule_blocks"]:
        print(f"rule block: {b}")
    for k, label in (("visual_pages", "visual pages recorded"), ("sections", "reference sections classified"), ("param_verdicts", "parameter conflicts judged")):
        if d[k]:
            print(f"{label}: {len(d[k])}: " + ", ".join(map(str, d[k][:40])) + (" …" if len(d[k]) > 40 else ""))
    if not any(d.values()):
        print("(nothing recorded yet)")


if __name__ == "__main__":
    main()
