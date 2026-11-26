#!/usr/bin/env python3
"""rules.json × target -> traceability matrix + result log + coverage verification.

Alt komutlar:
  skeleton rules.json target.txt [...] [-o matrix] [--top 4]   candidate locations in the target per rule (CSV+MD)
  set-bulk results.json part.json                              merges {"R-001": {"result":"✅","evidence":"p3 UC-2.1", ...}} (checkpoint)
  status rules.json results.json                               how many rules are done, which remain (resume where you left off)
  coverage rules.json results.json [-o coverage.md] [--env env.json] [--visual visual_status.json] [--work DIR]
                                                               "Coverage summary" (report top), visual / reference / parameter sections,
                                                               the coverage table (EVERY rule and fact one row) and the violation list;
                                                               --env adds the Environment section, --visual the visual-pass status line
  verify rules.json report.md [--work DIR]                     is the report complete? coverage table == register, and every gate of the
                                                               steps that were run (files in DIR, default: folder of rules.json; see gates.py)
Facts (F-001 …, "kind": "fact") live in the same register and get the same result symbols as rules.

Result values: ✅ ❌ ⚠️ ➖ ❓ ; evidence is required for ✅/❌/⚠️, the reason for ➖, and what is missing for ❓.
results.json fields: result, evidence, [target_loc, issue, fix, severity]
"""
import argparse, csv, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import progress

VALID = ["✅", "❌", "⚠️", "➖", "❓"]
# stop words for keyword extraction (English + Turkish)
STOP = set("olmalıdır olmalı gerekir gerekli için ile veya olan olarak bir bu şu the and for must shall should with that this from have been are not".split())


def load_rules(p):
    r = json.loads(Path(p).read_text(encoding="utf-8"))
    return r["rules"] if isinstance(r, dict) else r


def norm_res(s):
    return (s or "").replace("️", "").strip()


def keywords(rule):
    if rule.get("keywords"):
        return [k.lower() for k in rule["keywords"]]
    q = rule.get("quote", "") or (rule.get("source", {}) or {}).get("quote", "")
    ws = re.findall(r"[^\W\d_]{5,}|\b[A-Z]{2,}-?\d*\b|\d+", q)
    return [w.lower() for w in dict.fromkeys(ws) if w.lower() not in STOP][:10]


def load_lines(files):
    out = []
    for f in files:
        for raw in Path(f).read_text(encoding="utf-8").splitlines():
            if "\t" in raw:
                loc, t = raw.split("\t", 1)
                out.append((Path(f).stem, loc, t))
    return out


def cmd_skeleton(a):
    rules = load_rules(a.rules); lines = load_lines(a.targets)
    low = [(d, l, t, t.lower()) for d, l, t in lines]
    rows = []
    for r in rules:
        kws = keywords(r); scored = []
        for d, l, t, tl in low:
            sc = sum(1 for k in kws if k in tl)
            if sc: scored.append((sc, d, l, t))
        scored.sort(key=lambda x: -x[0])
        hits = [f"{d} {l} [{sc}/{len(kws)}] {t[:90]}" for sc, d, l, t in scored[:a.top]]
        rows.append({"rule": r["id"], "type": r.get("type", ""), "scope": r.get("scope", ""), "keywords": ", ".join(kws),
                     "candidate_hits": " || ".join(hits) if hits else "(NO CANDIDATE — absence may be a violation, or widen the keywords)",
                     "result": ""})
    base = Path(a.out)
    with open(base.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    md = ["| Rule | Type | Keywords | Candidate locations (target) |", "|---|---|---|---|"]
    for x in rows:
        md.append(f"| {x['rule']} | {x['type']} | {x['keywords']} | {x['candidate_hits'].replace('|', '¦')} |")
    base.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    nohit = sum(1 for x in rows if x["candidate_hits"].startswith("(NO CANDIDATE"))
    print(f"{len(rows)} rules -> {base}.csv/.md ; rules with no candidate: {nohit}")
    print("WARNING: the candidate list is only a hint; give each result by comparing the whole rule with the target.")


def cmd_set_bulk(a):
    res = json.loads(Path(a.results).read_text(encoding="utf-8")) if Path(a.results).exists() else {}
    part = json.loads(Path(a.part).read_text(encoding="utf-8"))
    bad = []
    for rid, v in part.items():
        if norm_res(v.get("result")) not in [norm_res(x) for x in VALID]:
            bad.append(f"{rid}: invalid result {v.get('result')!r}"); continue
        if not (v.get("evidence") or "").strip():
            bad.append(f"{rid}: evidence is empty (evidence/reason required)"); continue
        res[rid] = v
    Path(a.results).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = [r for r in part if r in res and res[r] is part[r]]
    if ok:
        progress.checkpoint(Path(a.results).parent, "rule_blocks", [f"{Path(a.part).name}: {ok[0]}..{ok[-1]} ({len(ok)})"])
    print(f"{len(res)} rules recorded")
    if bad:
        print("REJECTED:\n  " + "\n  ".join(bad)); sys.exit(1)


def cmd_status(a):
    rules = load_rules(a.rules)
    res = json.loads(Path(a.results).read_text(encoding="utf-8")) if Path(a.results).exists() else {}
    ids = [r["id"] for r in rules]; todo = [i for i in ids if i not in res]
    extra = [i for i in res if i not in ids]
    print(f"Done: {len(ids) - len(todo)}/{len(ids)}")
    print("Remaining: " + (", ".join(todo[:20]) + (f" … (+{len(todo) - 20})" if len(todo) > 20 else "") if todo else "(none)"))
    if extra: print("Results not in the rule register:", extra)


def cell(s): return str(s or "").replace("|", "¦").replace("\n", " ")


def cmd_coverage(a):
    import gates
    rules = load_rules(a.rules)
    g = gates.collect(a.work or Path(a.rules).parent, rules, a.env)
    res = json.loads(Path(a.results).read_text(encoding="utf-8"))
    cnt = {k: 0 for k in VALID}; L = ["| Rule | Source | Result | Evidence / Reason |", "|---|---|---|---|"]
    viol = []
    for r in rules:
        v = res.get(r["id"])
        if not v:
            L.append(f"| {r['id']} | | ❓ | **NO RESULT** |"); cnt["❓"] += 1; continue
        sym = next(x for x in VALID if norm_res(x) == norm_res(v["result"])); cnt[sym] += 1
        src = r.get("source", {}); srcs = f"{src.get('doc', '')} s.{src.get('page', '')}"
        if r["id"] in g["assumed"]: srcs += f" {gates.ASSUMPTION}"
        L.append(f"| {r['id']} | {cell(srcs)} | {sym} | {cell(v['evidence'])} |")
        if sym in ("❌", "⚠️"):
            viol.append((r, v, sym, srcs))
    nf = sum(1 for r in rules if gates.is_fact(r))
    total = f"Total rules: {len(rules) - nf}" + (f", facts: {nf}" if nf else "")
    head = [f"{total} — " + ", ".join(f"{k} {n}" for k, n in cnt.items()), ""]
    V = ["", "| # | Rule | Source | Target location | Issue | Suggested fix | Severity |", "|---|---|---|---|---|---|---|"]
    for n, (r, v, sym, srcs) in enumerate(viol, 1):
        V.append(f"| {n} | {r['id']} {sym} | {cell(srcs)} | {cell(v.get('target_loc'))} | {cell(v.get('issue') or v['evidence'])} | {cell(v.get('fix'))} | {cell(v.get('severity'))} |")
    extra = []
    if a.visual:
        extra += ["## Visual pass", json.loads(Path(a.visual).read_text(encoding="utf-8"))["line"], ""]
    if a.env:
        extra += json.loads(Path(a.env).read_text(encoding="utf-8"))["md"].rstrip("\n").splitlines() + [""]
    out = "\n".join(["## Coverage summary", *g["summary"], "", "## Summary", *head, *extra, *g["sections"], "## Coverage table", *L, "", "## Violations", *V]) + "\n"
    Path(a.out).write_text(out, encoding="utf-8")
    print(f"{a.out}: {len(L) - 2} coverage rows, {len(viol)} violations/partial")


def cmd_verify(a):
    rules = load_rules(a.rules); ids = [r["id"] for r in rules]
    text = Path(a.report).read_text(encoding="utf-8")
    # count only the coverage TABLE section (English or Turkish heading), not the summary / reference / visual coverage sections
    body = r"[^\n]*\n(.*?)(?=\n#+\s|\Z)"
    m = re.search(r"^#+[ \t]*(?:\d+\.[ \t]*)?(?:coverage table|kapsama tablosu)" + body, text, re.S | re.M | re.I) or re.search(
        r"^#+(?![^\n]*(?:summary|reference|visual|özet|referans|görsel))[^\n]*(?:coverage|kapsama)" + body, text, re.S | re.M | re.I)
    if not m:
        print("VERIFICATION FAILED — no 'Coverage' (or Turkish 'Kapsama') section heading found in the report"); sys.exit(1)
    sect = m.group(1)
    rows = re.findall(r"^\|\s*([RF]-\d+)\s*\|([^\n]*)$", sect, re.M)
    got = [r[0] for r in rows]; err = []
    if len(got) != len(ids): err.append(f"Row count {len(got)} ≠ rule count {len(ids)}")
    miss = [i for i in ids if i not in got]; dup = sorted({i for i in got if got.count(i) > 1}); unk = [i for i in got if i not in ids]
    if miss: err.append(f"Rules missing from the table: {miss}")
    if dup: err.append(f"Duplicate rows: {dup}")
    if unk: err.append(f"IDs not in the register: {unk}")
    for rid, rest in rows:
        cells = [c.strip() for c in rest.split("|")]
        sym = next((x for x in VALID if norm_res(x) in [norm_res(c) for c in cells[:3]]), None)
        if not sym: err.append(f"{rid}: no valid result symbol")
        elif "NO RESULT" in rest: err.append(f"{rid}: result not entered")
        elif not cells[-2 if cells[-1] == "" else -1]: err.append(f"{rid}: evidence/reason empty")
    err += verify_gates(a, rules, text, rows)
    if err:
        print("VERIFICATION FAILED — not finished:\n  " + "\n  ".join(err)); sys.exit(1)
    print(f"VERIFICATION OK: {len(got)}/{len(ids)} rules, one row each, result+evidence filled")


def verify_gates(a, rules, text, rows):
    """Checks of the steps that were run: gate errors, generated lines present in the report, summary first, assumption marks."""
    import gates
    work = Path(a.work or Path(a.rules).parent)
    if not any((work / n).exists() for n in ("visual_inventory.json", "ref_sections.json", "params.json", "doc_identity.json")):
        return []
    g = gates.collect(work, rules)
    err = list(g["errors"])
    first = re.search(r"^##[ \t]+(.*)$", text, re.M)
    if not first or not re.match(r"(?i)(coverage summary|kapsam özeti)", first.group(1)):
        err.append("the report must START with the generated «## Coverage summary» section (matrix.py coverage)")
    missing = [l for l in g["required"] if l.strip() not in text]
    if missing:
        err.append(f"{len(missing)} generated line(s) missing or stale in the report (paste the current matrix.py coverage output), e.g. {missing[:3]}")
    for rid, rest in rows:
        if rid in g["assumed"] and gates.ASSUMPTION not in rest:
            err.append(f"{rid}: rests on the target itself, the row must carry «{gates.ASSUMPTION}»")
    return err


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("skeleton"); p.add_argument("rules"); p.add_argument("targets", nargs="+"); p.add_argument("-o", "--out", default="matrix"); p.add_argument("--top", type=int, default=4); p.set_defaults(f=cmd_skeleton)
    p = sp.add_parser("set-bulk"); p.add_argument("results"); p.add_argument("part"); p.set_defaults(f=cmd_set_bulk)
    p = sp.add_parser("status"); p.add_argument("rules"); p.add_argument("results"); p.set_defaults(f=cmd_status)
    p = sp.add_parser("coverage"); p.add_argument("rules"); p.add_argument("results"); p.add_argument("-o", "--out", default="coverage.md"); p.add_argument("--env"); p.add_argument("--visual"); p.add_argument("--work"); p.set_defaults(f=cmd_coverage)
    p = sp.add_parser("verify"); p.add_argument("rules"); p.add_argument("report"); p.add_argument("--work"); p.set_defaults(f=cmd_verify)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
