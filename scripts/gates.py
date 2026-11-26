"""Coverage gates used by matrix.py: every count in the report is computed HERE from the files in the work folder, and verify
recomputes it. A step counts as run when its file exists; files are discovered in the work folder (the folder of rules.json), so a
check cannot be left out by forgetting a flag.

  visual_inventory.json + visual_log.json     visual coverage
  ref_sections.json                           reference coverage
  params.json + param_verdicts.json           parameter conflicts
  doc_identity.json                           documents the user named
  env.json, progress.json                     skipped checks
"""
import json
from collections import Counter
from pathlib import Path
import visual_inventory, section_inventory, param_check, progress

ASSUMPTION = "⚑ source assumption"


def is_fact(r):
    return r.get("kind") == "fact" or r["id"].startswith("F-")


def cell(s):
    return str(s or "").replace("|", "¦").replace("\n", " ")


def read(work, name):
    p = Path(work) / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def collect(work, rules, env_path=None):
    """{summary: [lines], sections: [markdown lines], required: [lines that must be in the report], errors: [..], assumed: set(rule ids)}"""
    errors, required, sections, skipped, summary = [], [], [], [], []
    facts = [r for r in rules if is_fact(r)]
    summary.append(f"- Rules: {len(rules) - len(facts)}; facts: {len(facts)}")

    ident = read(work, "doc_identity.json")
    assumed = set()
    if ident:
        target = ident["target"]
        for r in rules:
            if Path(str((r.get("source") or {}).get("doc", ""))).stem == target:
                assumed.add(r["id"])
        for e in ident["documents"]:
            summary.append(f"- Document identity: {e['note']}")
            if e["status"] == "missing":
                skipped.append((f"checks depending on «{e['name']}»", "document not provided", 1))
        if assumed:
            summary.append(f"- Circular check: {len(assumed)} rule(s)/fact(s) come from the target itself and are marked «{ASSUMPTION}»: {', '.join(sorted(assumed))}")
    else:
        summary.append("- Document identity: NOT RUN (section_inventory.py identity)"); skipped.append(("document identity", "step not run", 1))

    ref = read(work, "ref_sections.json")
    if ref:
        rows, errs, warns = section_inventory.evaluate(ref, rules); errors += errs
        done = sum(1 for r in rows if r.get("class") in section_inventory.CLASSES)
        summary.append(f"- Reference coverage: {done}/{len(rows)} sections classified; warnings: {len(warns)}")
        sections += ["## Reference coverage", "| Section | Title | Pages | Class | Rules | Facts | Reason |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            pg = f"{r['pages'][0]}-{r['pages'][-1]}" if r["pages"] else r["start"]
            sections.append(f"| {cell(r['id'])} | {cell(r['title'])} | {pg} | {r.get('class') or '**UNCLASSIFIED**'} | {len(r['rules'])} | {len(r['facts'])} | {cell(r.get('reason'))} |")
            required.append(f"| {cell(r['id'])} |")
        if warns:
            sections += ["", "Warnings (descriptive-only sections with values or obligation words; re-check them):"] + [f"- {w}" for w in warns]
            required += [f"- {w}" for w in warns]
        sections.append("")
    else:
        summary.append("- Reference coverage: NOT RUN (section_inventory.py scan)"); skipped.append(("reference coverage", "step not run", 1))

    inv = read(work, "visual_inventory.json")
    if inv:
        checked, skip, missing, errs = visual_inventory.evaluate(inv, read(work, "visual_log.json"))
        errors += errs
        if missing:
            errors.append(f"visual pass incomplete, {len(missing)} inventory page(s) neither checked nor skipped with a reason: {', '.join(missing[:30])}")
        line = f"Visual coverage: {len(checked)}/{len(inv['pages'])} pages"
        summary.append(f"- {line}; skipped with reason: {len(skip)}; open: {len(missing)}")
        for reason, n in sorted(Counter(r for _, r in skip).items()):
            skipped.append(("visual pages", reason, n))
        for d in inv["documents"]:
            if not d.get("images_detected", True):
                skipped.append((f"image and drawing detection in {d['file']}", "pypdf not available; the visual inventory is incomplete", d["pages_total"]))
            if d["decorative_only_pages"]:
                skipped.append((f"visual pages of {d['file']}", "only graphic is an image repeated on most pages (treated as decoration)", len(d["decorative_only_pages"])))
        log = read(work, "visual_log.json") or []
        sections += ["## Visual coverage", line,
                     "Skipped pages: " + ("; ".join(f"{n} ({r})" for n, r in skip) or "none"),
                     "Open pages: " + (", ".join(missing) or "none")]
        sections += [f"- WARNING: {w}" for w in inv["warnings"]]
        for d in inv["documents"]:
            if d["decorative_only_pages"]:
                sections.append(f"- {d['doc']}: pages whose only graphic is a repeated (decorative) image, not in the inventory: {d['decorative_only_pages']}")
        sections += ["", "| Document | Page | Type | IDs | Checked | Findings / skip reason |", "|---|---|---|---|---|---|"]
        docs = [d["doc"] for d in inv["documents"]]
        by = {visual_inventory.key(r, docs): r for r in log if "page" in r}
        for p in inv["pages"]:
            r = by.get((p["doc"], p["page"]), {})
            sections.append(f"| {p['doc']} | {p['page']} | {p['type']} | {cell(' '.join(p['ids']))} | {'yes' if r.get('checked') is True else 'no'} | {cell(r.get('findings') or r.get('skipped_reason'))} |")
        sections.append("")
        required += [line] + ([f"{n} ({r})" for n, r in skip])
    else:
        summary.append("- Visual coverage: NOT RUN (visual_inventory.py scan)"); skipped.append(("visual coverage", "step not run", 1))

    params = read(work, "params.json")
    if params:
        rows, errs = param_check.evaluate(params, read(work, "param_verdicts.json")); errors += errs
        judged = sum(1 for r in rows if r["verdict"])
        real = sum(1 for r in rows if r["verdict"] == "real")
        summary.append(f"- Parameter conflicts: {len(rows)} (judged {judged}, real {real}); values without a concept: {params['unassigned']}")
        sections += ["## Parameter conflicts (internal-consistency candidates)", "| Conflict | Kind | Target | Reference | Model | Verdict | Note |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            sections.append(f"| {r['id']} | {', '.join(r['kinds'])} | {', '.join(r['target_values'])} | {', '.join(r['reference_values'])} | {', '.join(r['model_values'])} | {r['verdict'] or '**NO VERDICT**'} | {cell(r['note'])} |")
            required.append(f"| {r['id']} |")
        sections += [f"- {n}" for n in params["notes"]] + [""]
    else:
        summary.append("- Parameter conflicts: NOT RUN (param_check.py scan)"); skipped.append(("parameter consistency", "step not run", 1))

    env = json.loads(Path(env_path).read_text(encoding="utf-8")) if env_path else read(work, "env.json")
    if env:
        skipped += [("environment", u, 1) for u in env.get("unavailable_checks", [])]
    prog = progress.load(Path(work) / "progress.json")
    skipped += [(f"step {k}", v["reason"], 1) for k, v in prog["steps"].items() if v["state"] == "skipped"]
    summary.append(f"- Skipped checks: {sum(n for *_, n in skipped)}")
    summary += [f"  - {what}: {reason} ({n})" for what, reason, n in skipped]
    required = summary + required
    return {"summary": summary, "sections": sections, "required": required, "errors": errors, "assumed": assumed}
