#!/usr/bin/env python3
"""Intermediate state file work/progress.json (standard library only), so long runs can resume after the context is summarized.

  progress.py start work/progress.json [--fresh]                   FIRST command of a NEW run (never when resuming): notes the results
                                                                    earlier runs left in work/ and .rule-check/, so the report can say how
                                                                    many rows repeat them. --fresh ("from scratch"): earlier work files are
                                                                    moved to work/_set_aside/ unread and .rule-check/ is not to be read
  progress.py show work/progress.json                              what is done (read this FIRST when resuming)
  progress.py step work/progress.json STEP done|running|skipped [--reason "..."]
                                                                    record a workflow step; "skipped" REQUIRES a reason and is counted in the report
Other scripts record their own checkpoints automatically: `matrix.py set-bulk` (rule blocks), `visual_inventory.py record`
(visual pages), `section_inventory.py classify` (reference sections), `param_check.py verdict` (parameter conflicts).
"""
import argparse, hashlib, json, re, shutil, sys
from pathlib import Path


def load(path):
    p = Path(path)
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for k, v in (("steps", {}), ("rule_blocks", []), ("visual_pages", []), ("sections", []), ("param_verdicts", []), ("audited", [])):
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


# ---------- earlier runs (blind-test protection) ----------
ASIDE = "_set_aside"


def row_key(v):
    result = str(v.get("result", "")).replace("\ufe0f", "")
    return hashlib.sha256(f"{result}\n{' '.join(str(v.get('evidence', '')).split())}".encode("utf-8")).hexdigest()[:16]


def result_files(work):
    """JSON files under the work folder and .rule-check/ that hold row results: [(name, {row id: result dict})]."""
    work = Path(work).resolve()
    roots = [work] + sorted({d for d in (Path.cwd() / ".rule-check", work / ".rule-check", work.parent / ".rule-check") if d.is_dir()})
    found, seen = [], set()
    for root in roots:
        for f in sorted(root.rglob("*.json")):
            if f in seen or ASIDE in f.parts:
                continue
            seen.add(f)
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if isinstance(data, dict):
                rows = {k: v for k, v in data.items() if re.fullmatch(r"[A-Z0-9-]+-\d+", k) and isinstance(v, dict) and "result" in v}
                if rows:
                    found.append((f.relative_to(work.parent).as_posix() if work.parent in f.parents else f.name, rows))
    return found


def earlier(work, names=None):
    """names: only result files with these names (used mid-run, when this run's own part files already exist)."""
    files = [(n, d) for n, d in result_files(work) if names is None or Path(n).name in names]
    rows = {}
    for _, data in files:
        for rid, v in data.items():
            rows.setdefault(row_key(v), []).append(rid)
    return {"fresh": False, "files": [n for n, _ in files], "rows": sorted(rows)}


def start(work, fresh=False):
    """Begin a new run: record what earlier runs left; the step records of an earlier run are not carried over."""
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    old = sorted(p for p in work.iterdir() if p.name != ASIDE)
    aside = work / ASIDE / f"{len(list((work / ASIDE).glob('*'))) + 1:03d}"
    if fresh:
        run = {"fresh": True, "set_aside": len(old), "rule_check_dir": any((d / ".rule-check").is_dir() for d in (Path.cwd(), work, work.parent))}
        move = old
    else:
        run = earlier(work)
        move = [p for p in old if p.name in ("progress.json", "self_audit.json")]          # a new run audits again
    if move:
        aside.mkdir(parents=True)
        for p in move:
            shutil.move(str(p), str(aside / p.name))
    state = load(work / "progress.json"); state["run"] = run; save(work / "progress.json", state)
    return run


def ensure_run(work):
    """Called before results are written: a run that was never started (or the one before is finished) is noted now, nothing moved."""
    path = Path(work) / "progress.json"
    state = load(path)
    if not state.get("run") or state["run"].get("finished"):
        state["run"] = {**earlier(work, ("results.json", "self_results.json")), "automatic": True}; save(path, state)


def finish(work):
    path = Path(work) / "progress.json"
    state = load(path)
    if state.get("run") and not state["run"].get("finished"):
        state["run"]["finished"] = True; save(path, state)


def run_summary(state, results):
    """(report line, error or None)."""
    run = state.get("run")
    if not run:
        return ("- Previous run results: NOT CHECKED (progress.py start)",
                "earlier results not checked: a run starts with progress.py start work/progress.json [--fresh]")
    if run.get("fresh"):
        return (f"- Previous run results: not read, started from scratch (sıfırdan): {run['set_aside']} earlier item(s) in the work folder set aside"
                + ("; .rule-check/ exists and must not be read (declared, not checkable)" if run.get("rule_check_dir") else ""), None)
    if not run["rows"]:
        return "- Previous run results: none found in the work folder or .rule-check/", None
    known = set(run["rows"])
    same = sum(1 for v in results.values() if row_key(v) in known)
    how = "; noted automatically when results were written without progress.py start, e.g. after a verified report" if run.get("automatic") else ""
    return (f"- Previous run results were used (önceki çalıştırmanın sonuçları kullanıldı{how}): {same}/{len(results)} rows identical "
            f"(same result and evidence); found in: {', '.join(run['files'][:5])}" + (f" and {len(run['files']) - 5} more" if len(run['files']) > 5 else ""), None)


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("show"); p.add_argument("file")
    p = sp.add_parser("start"); p.add_argument("file"); p.add_argument("--fresh", action="store_true")
    p = sp.add_parser("step"); p.add_argument("file"); p.add_argument("step"); p.add_argument("state", choices=("done", "running", "skipped")); p.add_argument("--reason", default="")
    a = ap.parse_args()
    if a.cmd == "start":
        run = start(Path(a.file).parent, a.fresh)
        print(run_summary({"run": run}, {})[0][2:] if run.get("fresh") or not run["rows"]
              else f"earlier results found in {', '.join(run['files'])}: the report will say how many rows repeat them (use --fresh to start from scratch)")
        return
    d = load(a.file)
    if a.cmd == "step":
        if a.state == "skipped" and not a.reason.strip():
            sys.exit("a skipped step needs --reason")
        d["steps"][a.step] = {"state": a.state, "reason": a.reason.strip()}
        save(a.file, d)
    if d.get("prefixes"):
        print("ID prefixes: " + ", ".join(f"{k} {v}-" for k, v in d["prefixes"].items()))
    if d.get("extract_dirs"):
        print("extracted text in: " + ", ".join(d["extract_dirs"]))
    if d.get("audit_seed"):
        print(f"self-audit seed: {d['audit_seed']} ({d.get('audit_seed_source', '')})")
    for k, v in d["steps"].items():
        print(f"step {k}: {v['state']}" + (f" ({v['reason']})" if v["reason"] else ""))
    for b in d["rule_blocks"]:
        print(f"rule block: {b}")
    for k, label in (("visual_pages", "visual pages recorded"), ("sections", "reference sections classified"), ("param_verdicts", "parameter conflicts judged"), ("audited", "rows re-checked in the self-audit")):
        if d[k]:
            print(f"{label}: {len(d[k])}: " + ", ".join(map(str, d[k][:40])) + (" …" if len(d[k]) > 40 else ""))
    if not any(d.values()):
        print("(nothing recorded yet)")


if __name__ == "__main__":
    main()
