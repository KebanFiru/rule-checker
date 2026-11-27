#!/usr/bin/env python3
"""Scores scenario 1c against fixtures/coverage/expected.json and runs the negative checks: verify MUST reject every kind of silent
gap. Usage: score_coverage.py s3/   (from the output directory of run_deterministic.sh)
Independent (deterministic): inventories, identity, parameter conflicts, verify behaviour, unit parsing, search. The visual findings,
classifications and results are committed model judgements (contaminated, see README)."""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import param_check, section_inventory, visual_inventory, judgement, prefixes, self_rules
from id_index import load_patterns
d = Path(sys.argv[1]).resolve(); e = json.loads((REPO / "tests/fixtures/coverage/expected.json").read_text(encoding="utf-8")); tot = []
J = lambda n, base=d: json.loads((base / n).read_text(encoding="utf-8"))


def line(name, got, want):
    tot.append(got == want); print(("✓" if got == want else "✗"), f"{name}: {got}/{want}")


def run(script, *args, cwd=d):
    return subprocess.run([sys.executable, str(REPO / "scripts" / script), *args], capture_output=True, text=True, cwd=cwd)


inv = J("visual_inventory.json"); pages = {p["page"]: p for p in inv["pages"]}
line("inventory: screen pages found (also after page 10)", sum(pages.get(p, {}).get("type") == "screen" for p in e["screen_pages"]), len(e["screen_pages"]))
line("inventory: vector-only data model page", pages.get(e["data_model_page"], {}).get("type"), "data-model")
vis = (d / "report.md").read_text(encoding="utf-8").split("## Visual pass findings")[1]
line("planted screen mismatches in the report (model judgement)", sum(all(w in vis for w in ws) for ws in e["screen_mismatches"].values()), len(e["screen_mismatches"]))
sec = {s["id"]: s for s in J("ref_sections.json")["sections"]}
line("sections: AS-IS paragraph flagged as containing «must»", "must" in sec[e["asis_section"]]["signals"]["modal"], True)
line("sections: target appendix scanned as a reference", "target_ui#Appendix B" in sec, True)
rep = (d / "report.md").read_text(encoding="utf-8")
line("fact conflict reported", all(w in rep for w in e["fact_conflict"]), True)
ident = J("doc_identity.json")["documents"][0]
line("identity: «Ek B» resolved to the target's own section", (ident["status"], ident["self_reference"]), (e["identity"]["status"], True))
line("identity: note at the top of the report", ident["note"] in rep.split("## Summary")[0], True)
line("identity: rows from the target marked as source assumption", sum("source assumption" in l for l in rep.split("## Coverage table")[1].splitlines() if l.startswith("| R-00")), 2)
conf = {c["id"]: c for c in J("params.json")["conflicts"]}
line("parameter: deviating reminder period flagged", conf.get(e["param_conflict"]["id"], {}).get("target_values"), e["param_conflict"]["target_values"])
line("report starts with the coverage summary", rep.index("## Coverage summary") < rep.index("## Summary") < rep.index("## Coverage table"), True)
line("search.py candidate file for the rule block", (d / "candidates_part_01.md").read_text(encoding="utf-8").count("\n## "), 12)


def broken(name, mutate, expect_text):
    """Copy the work folder, damage it, regenerate nothing: verify must exit non-zero and say why."""
    with tempfile.TemporaryDirectory() as t:
        w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
        mutate(w)
        r = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
        line(f"negative check, {name}: rejected", (r.returncode != 0, expect_text in r.stdout), (True, True))


def rewrite(w, name, fn):
    data = J(name, w); out = fn(data); (w / name).write_text(json.dumps(out if out is not None else data, ensure_ascii=False), encoding="utf-8")


def report_replace(w, old, new):
    p = w / "report.md"; p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


broken("pages after 10 never opened", lambda w: rewrite(w, "visual_log.json", lambda l: [r for r in l if r["page"] <= 10]), "visual pass incomplete")
broken("unchecked page without a reason", lambda w: rewrite(w, "visual_log.json", lambda l: l[-1].update(checked=False, findings="") ), "visual pass incomplete")
broken("visual log deleted", lambda w: (w / "visual_log.json").unlink(), "visual pass incomplete")
broken("unclassified section", lambda w: rewrite(w, "ref_sections.json", lambda s: s["sections"][3].update({"class": ""})), "not classified")
broken("rule-bearing section without rules", lambda w: rewrite(w, "ref_sections.json", lambda s: s["sections"][1].update({"class": "rule-bearing"})), "no rule was extracted")
broken("parameter conflict without verdict", lambda w: (w / "param_verdicts.json").unlink(), "without verdict")
broken("identity note removed", lambda w: report_replace(w, ident["note"], ""), "missing or stale")
broken("summary removed", lambda w: report_replace(w, "## Coverage summary", "## Notes"), "must START")
broken("stale counts", lambda w: report_replace(w, "Visual coverage: 8/8", "Visual coverage: 9/9"), "missing or stale")
broken("assumption mark removed", lambda w: report_replace(w, " ⚑ source assumption |", " |"), "must carry")

with tempfile.TemporaryDirectory() as t:                      # a deliberate skip passes, but is counted at the top
    w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
    rewrite(w, "visual_log.json", lambda l: l[-1].update(checked=False, findings="", skipped_reason="table equals the text layer"))
    run("matrix.py", "coverage", "rules.json", "results.json", "-o", "coverage.md", cwd=w)
    (w / "report.md").write_text("# R\n\n" + (w / "coverage.md").read_text(encoding="utf-8"), encoding="utf-8")
    r = run("matrix.py", "verify", "rules.json", "report.md", cwd=w); top = (w / "report.md").read_text(encoding="utf-8").split("## Summary")[0]
    line("deliberate skip: accepted and counted at the top", (r.returncode, "Visual coverage: 7/8 pages; skipped with reason: 1" in top, "table equals the text layer (1)" in top), (0, True, True))
    rewrite(w, "ref_sections.json", lambda s: s["sections"][3].update({"class": "descriptive-only", "reason": "history"}))
    rewrite(w, "rules.json", lambda x: {"rules": [r for r in x["rules"] if not r["id"].startswith("F-")]})
    run("matrix.py", "coverage", "rules.json", "results.json", "-o", "coverage.md", cwd=w)
    line("«descriptive-only» section containing «must» is warned", "is 'descriptive-only' but contains must" in (w / "coverage.md").read_text(encoding="utf-8"), True)

UNITS = [("3 iş günü içinde", [("3", "business-day")]), ("14 günlük süre, 2 günde yanıt", [("14", "day"), ("2", "day")]),
         ("within five working days", [("5", "business-day")]), ("a 30-day period", [("30", "day")]), ("three (3) weeks", [("3", "week")]),
         ("%20 indirim ve 15 % pay", [("20", "%"), ("15", "%")]), ("€ 120 or 1.500,00 € or 1,500.50 EUR", [("120", "EUR"), ("1500", "EUR"), ("1500.5", "EUR")]),
         ("30 AKTS, 6 ECTS, 25 MB", [("30", "ECTS"), ("6", "ECTS"), ("25", "MB")]), ("iki hafta, 3 ay, 48 saat", [("2", "week"), ("3", "month"), ("48", "hour")]),
         ("3-5 days", [("3-5", "day")]), ("UC-3.8 güncel 2 ayrı liste, 14.03.2026", [])]
bad = [(t, got) for t, want in UNITS for got in [[(v, u) for _, _, v, u, _ in param_check.find_values(t)]] if got != want]
line("number+unit parsing (EN/TR forms)", len(UNITS) - len(bad), len(UNITS))
if bad: print("  wrong:", bad)
files = ["PAR_v2.pdf", "ProjectCharter.docx", "srs.pdf"]
line("identity: names matched to file names", [[f for f in files if section_inventory.matches_file(n, f)] for n in ("PAR", "charter", "Ek B")], [["PAR_v2.pdf"], ["ProjectCharter.docx"], []])
caps = ["Ekran S-6.2 Başvuru", "Screen S-1.1 Sign in", "S-6.3 Onay", "Şekil 4 Akış", "Figure A1", "Diagram 2"]
line("captions recognised (EN/TR, with screen IDs)", sum(bool(visual_inventory.CAPTION.match(c)) for c in caps), len(caps))
with tempfile.TemporaryDirectory() as t:                      # an incomplete inventory is counted as a skipped check
    w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
    rewrite(w, "visual_inventory.json", lambda x: x["documents"][0].update(images_detected=False, decorative_only_pages=[1, 2]))
    run("matrix.py", "coverage", "rules.json", "results.json", "-o", "coverage.md", cwd=w)
    top = (w / "coverage.md").read_text(encoding="utf-8").split("## Summary")[0]
    line("incomplete inventory counted in the summary", ("incomplete (14)" in top, "treated as decoration) (2)" in top), (True, True))
proc = REPO / "tests/fixtures/process"
params, _ = param_check.model_parameters(proc / "model_v1/process_model.yaml", param_check.load_concepts(None))
occ = [{"role": "target", "doc": "v2", "loc": "x", "value": v, "unit": "day", "dimension": "time", "concept": "reminder"} for v in ("5", "3")]
line("parameter: compared with the process model", [c["kinds"] for c in param_check.conflicts(occ, params)], [["target-internal", "target-vs-model"]])
# ---------- judgement checks (aggregate findings, evidence fit, references, verdict types, internal findings, self-audit) ----------
line("baseline: no judgement warning on the sample", "- Judgement warnings: 0 " in rep, True)
line("self-audit: changed verdict listed in the report", "- R-001: ❌ → ⚠️" in rep.split("## Changed in self-audit")[1].split("\n## ")[0], True)
line("reference contradiction shown as a team decision, not as a violation",
     ("| R-008 ⚖️ |" in rep.split("## Reference conflicts / team decisions")[1].split("\n## ")[0], "R-008" in rep.split("## Violations")[1].split("\n## ")[0]), (True, False))


def reaudit(w):
    """Re-plan and re-record every row, so the planted defect is the only thing wrong."""
    run("matrix.py", "audit-plan", "rules.json", "results.json", cwd=w)
    plan = J("self_audit.json", w)["planned"]
    (w / "all.json").write_text(json.dumps({i: {"source": "re-read", "note": "test"} for i in plan}), encoding="utf-8")
    run("matrix.py", "audit-record", "rules.json", "results.json", "self_audit.json", "all.json", cwd=w)


def judged(name, mutate, expect, rejected=True, audit=True):
    """mutate(results, workdir); regenerate the report; verify. expect: texts that must appear in the verify output or the report."""
    with tempfile.TemporaryDirectory() as t:
        w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
        res = J("results.json", w); mutate(res, w)
        (w / "results.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        if audit: reaudit(w)
        run("matrix.py", "coverage", "rules.json", "results.json", "-o", "coverage.md", cwd=w)
        body = (w / "coverage.md").read_text(encoding="utf-8")
        (w / "report.md").write_text("# R\n\n" + body, encoding="utf-8")
        r = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
        seen = r.stdout if rejected else body
        missing = [x for x in expect if x not in seen]
        line(f"judgement check, {name}", (r.returncode != 0, missing), (rejected, []))
        if missing: print("  output was:", r.stdout[:600])


judged("aggregate member without its own finding", lambda r, w: r["R-006"].update(result="✅"), ["R-007: aggregate member R-006 has no ❌/⚠️ row"])
judged("aggregate member missing from the register", lambda r, w: r["R-007"]["members"].append("R-044"), ["aggregate member R-044 is not in the register"])
judged("aggregate written without members is warned", lambda r, w: r["R-007"].pop("members"), ["R-007: reads like an aggregate finding"], rejected=False)
judged("absent open-question fact marked ➖", lambda r, w: r["F-003"].update(result="➖"), ["F-003: ➖ for a fact absent from the target"])
judged("rule marked ➖ with 'absent' wording is warned", lambda r, w: r["R-004"].update(result="➖", evidence="the late fee is not mentioned outside Appendix B"),
       ["R-004: ➖ with 'absent' wording"], rejected=False)
judged("conditional rule that does not apply stays ➖", lambda r, w: r["R-004"].update(result="➖", evidence="the target does not contain any late fee screen, so the rule does not apply"),
       ["| R-004 |"], rejected=False)
judged("aggregate member turned into ➖", lambda r, w: r["R-005"].update(result="➖"), ["aggregate member R-005 has no ❌/⚠️ row"])
moved = J("results.json")["R-002"]["evidence"]
judged("evidence written on the wrong row is warned", lambda r, w: r["R-001"].update(evidence=moved + " (IF-1)", issue="", target_loc=""),
       ["R-001: evidence uses none of the rule's keywords", "of R-002's"], rejected=False)
judged("evidence IDs outside the rule's IDs are warned", lambda r, w: (rewrite(w, "rules.json", lambda x: x["rules"][1].update(scope="screen S-1.2")), None)[1],
       ["R-002: evidence IDs", "do not overlap the rule's IDs (S-1.2)"], rejected=False)
judged("broken row reference", lambda r, w: r["R-002"].update(evidence=r["R-002"]["evidence"] + "; see R-099"), ["R-099 is not a row of the register"])
judged("broken fact reference", lambda r, w: r["R-002"].update(evidence=r["R-002"]["evidence"] + "; see F-9"), ["F-9 is not a row of the register"])
judged("broken TBD reference", lambda r, w: r["R-008"].update(fix="TBD-9"), ["TBD-9 is not defined in tbd.json"])
for fix in ("No change needed", "değişiklik yok", "Team decision", "TBD / team decision", "Ekip kararı"):
    judged(f"❌ with fix «{fix}»", lambda r, w: r["R-005"].update(fix=fix), ["R-005: ❌ with fix"])
judged("❌ without a fix", lambda r, w: r["R-005"].pop("fix"), ["R-005: a ❌ row needs a fix"])
judged("⚖️ without a TBD number", lambda r, w: r["R-009"].update(fix="decide", evidence="the reference gives two values"), ["R-009: a ⚖️ row must cite"])
judged("contradiction not written on the rule's row", lambda r, w: r["R-001"].update(evidence=r["R-001"]["evidence"].replace(" (IF-1)", "")), ["IF-1: it concerns R-001"])
judged("finding with neither rule nor reason", lambda r, w: rewrite(w, "internal.json", lambda x: x[2].update(no_rule_reason="", self_rules=[])), ["IF-3: list the rules"])
judged("real parameter contradiction not bound", lambda r, w: rewrite(w, "internal.json", lambda x: x[0].pop("param") and None), ["P:reminder:time is a real contradiction"])
judged("unbound candidate rule is warned", lambda r, w: rewrite(w, "internal.json", lambda x: x[1].update(text=x[1]["text"] + "; the confirmation fee appears before payment")),
       ["IF-2: may also concern R-002"], rejected=False)
judged("result changed after the self-audit", lambda r, w: r["R-005"].update(severity="high"), ["R-005 changed after it was re-checked"], audit=False)
judged("self-audit left out", lambda r, w: (w / "self_audit.json").unlink(), ["Self-audit not run"], audit=False)
judged("new violation not re-checked", lambda r, w: r["R-004"].update(result="⚠️"), ["R-004 not re-checked"], audit=False)
rules3 = J("rules.json")["rules"]
# ---------- mandatory steps ----------
GATES = {"reference": ("Reference coverage", ["ref_sections.json"]), "visual": ("Visual coverage", ["visual_inventory.json", "visual_log.json"]),
         "self-rules": ("Target's own rules", ["self_sections.json", "self_rules.json", "self_results.json"]),
         "identity": ("Document identity", ["doc_identity.json"]), "params": ("Parameter conflicts", ["params.json", "param_verdicts.json"]),
         "internal": ("Internal findings", ["internal.json"])}


def without(w, steps):
    for step in steps:
        for n in GATES[step][1]:
            (w / n).unlink()
    if "self-rules" in steps and (w / "internal.json").exists():
        rewrite(w, "internal.json", lambda x: [f.pop("self_rules", None) and f.setdefault("no_rule_reason", "test") for f in x] and None)


def gate_run(steps, skips=(), also_delete=(), extra=None):
    """(verify exit code, verify output, report top)."""
    with tempfile.TemporaryDirectory() as t:
        w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
        without(w, steps)
        for n in also_delete: (w / n).unlink()
        for step, why in skips:
            run("progress.py", "step", "progress.json", step, "skipped", "--reason", why, cwd=w)
        if extra: extra(w)
        if "self-rules" in steps:      # the register changed: audit again so only the gate is tested
            (w / "self_audit.json").unlink(missing_ok=True) if "self-audit" not in dict(skips) else None
            if "self-audit" not in dict(skips): reaudit(w)
        run("matrix.py", "coverage", "rules.json", "results.json", "-o", "coverage.md", cwd=w)
        body = (w / "coverage.md").read_text(encoding="utf-8")
        (w / "report.md").write_text("# R\n\n" + body, encoding="utf-8")
        r = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
        return r.returncode, r.stdout, body.split("## Summary")[0]


for step, (label, _) in GATES.items():
    code, out, top = gate_run([step])
    line(f"mandatory {step}: not run is rejected", (code != 0, f"{label} not run" in out, f"- {label}: NOT RUN" in top), (True, True, True))
    code, out, top = gate_run([step], skips=[(step, "no input for it")])
    line(f"mandatory {step}: skipped with a reason passes, shown and counted once",
         (code, f"- {label}: SKIPPED (no input for it)" in top, "- Skipped checks: 1" in top, top.count("no input for it")), (0, True, True, 2))
code, out, top = gate_run([], skips=[], also_delete=["self_audit.json"], extra=lambda w: run("progress.py", "step", "progress.json", "self-audit", "skipped", "--reason", "no time", cwd=w))
line("mandatory self-audit: skipped with a reason passes, counted once", (code, "- Self-audit: SKIPPED (no time)" in top, "- Skipped checks: 1" in top), (0, True, True))
code, out, top = gate_run(["visual"], extra=lambda w: rewrite(w, "progress.json", lambda x: x["steps"].update(visual={"state": "skipped", "reason": " "})))
line("mandatory: a skip without a reason is rejected", (code != 0, "Visual coverage not run" in out), (True, True))
code, out, top = gate_run(list(GATES), skips=[(k, f"why {k}") for k in GATES])
line("all six file-based steps skipped with reasons: accepted, none shown as NOT RUN",
     (code, top.count(": SKIPPED ("), top.count(": NOT RUN"), "- Skipped checks: 6" in top), (0, 6, 0, True))
code, out, top = gate_run(list(GATES))
line("all six missing without a reason: each one rejected", sum(f"{label} not run" in out for label, _ in GATES.values()), 6)
code, out, top = gate_run([], extra=lambda w: (w / "internal.json").write_text("[]", encoding="utf-8"))
line("empty internal findings list counts as run (own-rule violations still need a finding)", ("Internal findings not run" in out, "SD-001: the target breaks its own rule" in out), (False, True))
with tempfile.TemporaryDirectory() as t:                      # the summary itself stays mandatory
    w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
    p = w / "report.md"; p.write_text("# R\n\n## Summary" + p.read_text(encoding="utf-8").split("## Summary", 1)[1], encoding="utf-8")
    r = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
    line("summary removed: rejected", (r.returncode != 0, "must START" in r.stdout), (True, True))
# ---------- seeded self-audit ----------
many = [f"R-{i:03d}" for i in range(1, 101)]
line("self-audit sample: 10%, reproducible with the seed, different for another seed",
     (len(judgement.sample(many, "a")), judgement.sample(many, "a") == judgement.sample(many[::-1], "a"), judgement.sample(many, "a") != judgement.sample(many, "b")), (10, True, True))
seeds = []
for _ in range(2):
    with tempfile.TemporaryDirectory() as t:
        w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
        (w / "self_audit.json").unlink(); rewrite(w, "progress.json", lambda x: [x.pop("audit_seed"), x.pop("audit_seed_source")] and None)
        res = J("results.json", w); last = res.pop("R-009"); (w / "results.json").write_text(json.dumps(res), encoding="utf-8")
        early = run("matrix.py", "audit-plan", "rules.json", "results.json", cwd=w)
        no_seed_yet = "audit_seed" not in J("progress.json", w)
        res["R-009"] = last; (w / "results.json").write_text(json.dumps(res), encoding="utf-8")
        run("matrix.py", "audit-plan", "rules.json", "results.json", cwd=w)
        first = J("self_audit.json", w); seeds.append(first["seed"])
        if len(seeds) == 1:
            line("self-audit: no seed (and no selection) before every rule has a result", (early.returncode != 0, no_seed_yet), (True, True))
            (w / "self_audit.json").unlink()
            run("matrix.py", "audit-plan", "rules.json", "results.json", cwd=w)
            other = run("matrix.py", "audit-plan", "rules.json", "results.json", "--seed", "another", cwd=w)
            again = J("self_audit.json", w)
            line("self-audit: same seed and selection after deleting the audit file; a second seed refused",
                 (again["seed"] == first["seed"], again["planned"] == first["planned"], other.returncode != 0), (True, True, True))
            run("matrix.py", "coverage", "rules.json", "results.json", "-o", "coverage.md", cwd=w)
            line("self-audit: generated seed stated in the report", f"seed {first['seed']}, generated at the start of the step" in (w / "coverage.md").read_text(encoding="utf-8"), True)
line("self-audit: every run generates its own seed", len(set(seeds)), 2)
judged("self-audit seed edited by hand", lambda r, w: rewrite(w, "self_audit.json", lambda x: x.update(seed="picked")), ["seed does not match progress.json"], audit=False)

# ---------- own ID prefixes ----------
with tempfile.TemporaryDirectory() as t:
    f = Path(t) / "doc.txt"
    f.write_text("p1:L1\tFR-1 uses QR-A.1 and UC-3.7\np2:L1\tIC-1, IC-3, IC-4 consistency rules\n", encoding="utf-8")
    free = prefixes.choose([f])
    f.write_text("p1:L1\tIC-1 and FR-2\np3:L2\t| R7 | supplier risk |\np3:L3\t| R11 | delay |\np4:L1\tF3 key, TBD-2, IF-4, RC-IF-1, SD7\n", encoding="utf-8")
    used = prefixes.choose([f])
line("prefixes: IC-, FR-, QR- are no collision", (free["prefixes"], free["collisions"]), (prefixes.DEFAULT, []))
line("prefixes: R7/R11, F3, TBD-2, IF-4 (with or without hyphen) switch", used["prefixes"], {"rule": "RC-R", "fact": "RC-F", "self": "RC-SD", "tbd": "RC-TBD", "finding": "RC2-IF"})

with tempfile.TemporaryDirectory() as t:                      # end to end: the documents use R, F, TBD and IF themselves
    w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
    with open(w / "ex/ref_policy.txt", "a", encoding="utf-8") as fh: fh.write("p9:L1\t| R7 | supplier | F2 | TBD-4 | IF-1 | SD-1 |\n")
    stale = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
    line("prefixes: collision with the documents rejected", (stale.returncode != 0, "prefix R- collides" in stale.stdout), (True, True))
    run("prefixes.py", "ex/target_ui.txt", "ex/ref_policy.txt", "-o", "prefixes.json", cwd=w)
    old = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
    line("prefixes: old IDs rejected after the switch", "must use the chosen prefix RC-R-" in old.stdout, True)
    for n in ("rules.json", "results.json", "self_rules.json", "self_results.json", "tbd.json", "internal.json"):
        p = w / n; p.write_text(re.sub(r"(?<![\w-])(R|F|SD|TBD|IF)-(\d+)", r"RC-\1-\2", p.read_text(encoding="utf-8")), encoding="utf-8")
    (w / "self_audit.json").unlink(); reaudit(w)
    run("matrix.py", "coverage", "rules.json", "results.json", "-o", "coverage.md", cwd=w)
    body = (w / "coverage.md").read_text(encoding="utf-8"); (w / "report.md").write_text("# R\n\nThe policy numbers its risks R7.\n\n" + body, encoding="utf-8")
    r = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
    line("prefixes: renumbered run verifies", (r.returncode, "12/12 rules" in r.stdout), (0, True))
    line("prefixes: choice in the report and in progress.json",
         ("rules RC-R-, facts RC-F-, target's own rules RC-SD-, decisions RC-TBD-, internal findings RC-IF-" in body, J("progress.json", w)["prefixes"]["rule"]), (True, "RC-R"))
    res = J("results.json", w); res["RC-R-005"]["fix"] = "RC-TBD-1"; (w / "results.json").write_text(json.dumps(res), encoding="utf-8")
    r = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
    res["RC-R-005"].update(fix="add it", evidence=res["RC-R-005"]["evidence"] + "; see RC-R-099"); (w / "results.json").write_text(json.dumps(res), encoding="utf-8")
    r2 = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
    line("prefixes: verdict and reference checks follow the new prefix",
         ("RC-R-005: ❌ with fix" in r.stdout, "RC-R-099 is not a row" in r2.stdout), (True, True))
judged("prefixes never chosen", lambda r, w: (w / "prefixes.json").unlink(), ["ID prefixes not chosen"])
# ---------- the target's own rules (self-declared) ----------
own_part = rep.split("## Target's own rules (self-declared)")[1].split("\n## ")[0]
cov_part = rep.split("## Coverage table")[1].split("\n## ")[0]
line("own rules: separate section, none in the coverage table, no source-assumption mark",
     (own_part.count("| SD-00"), "SD-0" in cov_part.replace("(IF-", ""), "source assumption" in own_part), (4, False, False))
with tempfile.TemporaryDirectory() as t:                      # without them the reference counts are exactly the same
    w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True)
    for n in ("self_rules.json", "self_results.json", "self_sections.json", "self_audit.json"): (w / n).unlink()
    rewrite(w, "internal.json", lambda x: [f.pop("self_rules") and f.setdefault("no_rule_reason", "test") for f in x if "self_rules" in f] and None)
    run("matrix.py", "coverage", "rules.json", "results.json", "-o", "coverage.md", cwd=w)
    counts = lambda body: [l for l in body.splitlines() if l.startswith(("- Rules:", "- Reference coverage", "Total rules"))]
    line("own rules: reference and rule counts unchanged by them", (len(counts(rep)), counts((w / "coverage.md").read_text(encoding="utf-8")) == counts(rep)), (3, True))


def own(w, name, fn):
    rewrite(w, name, fn)


judged("declared own rule without a row", lambda r, w: own(w, "self_rules.json", lambda x: x["rules"].pop(1) and None), ["IC-2 is declared in target_ui#4.1 but has no row"])
judged("own rule with an invented ID", lambda r, w: own(w, "self_rules.json", lambda x: x["rules"][3].update(doc_id="IC-9")), ["doc_id IC-9 does not occur"])
judged("own rule without a result", lambda r, w: own(w, "self_results.json", lambda x: x.pop("SD-004") and None), ["SD-004: the target's own rule has no result"])
judged("broken own rule not bound to a finding", lambda r, w: own(w, "internal.json", lambda x: x[2].update(self_rules=[], no_rule_reason="x")),
       ["SD-003: the target breaks its own rule (IC-3)"])
judged("finding mentions IC-3 but does not bind it", lambda r, w: own(w, "internal.json", lambda x: x[0].update(text=x[0]["text"] + "; see IC-3")),
       ["IF-1: mentions IC-3"])
judged("finding number missing on the own rule's row", lambda r, w: own(w, "self_results.json", lambda x: x["SD-001"].update(evidence="p9 QR-A.1 differs")),
       ["IF-1: it concerns SD-001"])
judged("own rule candidate not classified", lambda r, w: own(w, "self_sections.json", lambda x: x["candidates"][1].update({"class": ""})), ["candidate not classified"])
judged("own rule copied into the reference register", lambda r, w: own(w, "rules.json", lambda x: x["rules"][3]["source"].update(doc="target_ui.pdf", quote="IC-2 Every screen shows the same fee")),
       ["R-004: IC-2 is the target's own rule"])
judged("own rule ❌ with fix «no change»", lambda r, w: own(w, "self_results.json", lambda x: x["SD-001"].update(fix="no change")), ["SD-001: ❌ with fix"])
judged("own rule result changed after the self-audit", lambda r, w: own(w, "self_results.json", lambda x: x["SD-001"].update(severity="high")),
       ["SD-001 changed after it was re-checked"], audit=False)
with tempfile.TemporaryDirectory() as t:
    f = Path(t) / "t.txt"
    f.write_text("p1:L1\t1. Kısıtlar\np1:L2\tHer kayıt tek bir sahibe bağlıdır.\np2:L1\t2. Data\np2:L2\t| BR-1 | one owner |\np2:L3\tC-1 no empty names\n"
                 "p2:L4\tAB-1 first\np2:L5\tAB-2 second\np3:L1\t3. Tutarlılık kuralları\np3:L2\tIC-1 a\np3:L3\tIC-3 b\n", encoding="utf-8")
    got = {c["title"]: c["ids"] for c in self_rules.scan(f)}
line("own rule detection: TR headings, BR- in a table, C- lines; a two-member unknown prefix is not a list",
     got, {"Kısıtlar": [], "Tutarlılık kuralları": ["IC-1", "IC-3"], "ID list BR-": ["BR-1"], "ID list C-": ["C-1"]})

# ---------- extracted text must be there ----------
def extracted(name, mutate, expect_ok, text=""):
    with tempfile.TemporaryDirectory() as t:
        w = Path(t) / "w"; shutil.copytree(d, w, symlinks=True); mutate(w)
        r = run("matrix.py", "verify", "rules.json", "report.md", cwd=w)
        line(f"extracted text, {name}", (r.returncode == 0, text in r.stdout), (expect_ok, True))


extracted("directory missing: rejected", lambda w: shutil.rmtree(w / "ex"), False, "no extracted text in ex")
extracted("directory empty: rejected", lambda w: [p.unlink() for p in (w / "ex").iterdir()] and None, False, "no extracted text in ex")
def move(w):
    shutil.move(w / "ex", w / "elsewhere"); run("prefixes.py", "elsewhere/target_ui.txt", "elsewhere/ref_policy.txt", "-o", "prefixes.json", cwd=w)
extracted("other directory recorded in progress.json: accepted", move, True)
def stale(w):
    move(w); shutil.move(w / "elsewhere", w / "gone")
extracted("recorded directory gone: rejected", stale, False, "no extracted text in elsewhere")
line("Turkish İ matches in the evidence-fit check", judgement.has_word("itiraz", "İtiraz süresi"), True)
pats, _ = load_patterns()
line("IDs: use-case exception steps and internal findings", sorted(judgement.ids_in("UC-3.7.EX.2 and UC-3.7.EX.1 vs S-4.1, IC-3. See UC-3.7.", pats)),
     ["IC-3", "S-4.1", "UC-3.7", "UC-3.7.EX.1", "UC-3.7.EX.2"])
line("aggregate wording not triggered by a single missing item", bool(judgement.AGGREGATE.search("No Scope section. Headings 1-6 listed; the word does not occur")), False)
print("\nSUMMARY:", "FULL" if all(tot) else "GAPS")
