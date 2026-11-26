#!/usr/bin/env python3
"""Scores scenario 1c against fixtures/coverage/expected.json and runs the negative checks: verify MUST reject every kind of silent
gap. Usage: score_coverage.py s3/   (from the output directory of run_deterministic.sh)
Independent (deterministic): inventories, identity, parameter conflicts, verify behaviour, unit parsing, search. The visual findings,
classifications and results are committed model judgements (contaminated, see README)."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import param_check, section_inventory, visual_inventory
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
line("search.py candidate file for the rule block", (d / "candidates_part_01.md").read_text(encoding="utf-8").count("\n## "), 6)


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
print("\nSUMMARY:", "FULL" if all(tot) else "GAPS")
