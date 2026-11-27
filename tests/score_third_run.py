#!/usr/bin/env python3
"""Regressions found in a real run: heading detection, warning noise, root findings, earlier-run protection, tracked-change gates.
Identical in every environment (no pdfplumber needed). Usage: score_third_run.py WORKDIR"""
import json, os, subprocess, sys
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import gates, judgement, progress, section_inventory
from id_index import load_patterns, parse_lines
from matrix import keywords
d = Path(sys.argv[1]).resolve(); d.mkdir(parents=True, exist_ok=True); tot = []


def line(name, got, want):
    tot.append(got == want); print(("✓" if got == want else "✗"), f"{name}: {got}/{want}")


def run(script, *args, cwd=d, env=None):
    return subprocess.run([sys.executable, str(REPO / "scripts" / script), *args], capture_output=True, text=True, cwd=cwd, env=env)


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def text(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"p1:L{i}\t{l}\n" for i, l in enumerate(lines, 1)), encoding="utf-8")


# ---------- headings ----------
NOT_HEADINGS = ["23 Feb – 17 Mar", "13 May 2026. Cancellation", "30 ECTS cannot be exceeded in one semester", "30 ECTS cannot…", "15 Mayıs Salı",
                "2 Students shall register before the deadline", "12 Applications that arrive late are returned to the sender and are not examined again"]
HEADINGS = ["1 Introduction", "2.3 Application Deadlines", "4 Marketing Plan", "5. ECTS Credits", "3 Başvuru Koşulları"]
line("headings: dates and sentences starting with a number are not headings", [t for t in NOT_HEADINGS if section_inventory.heading(t)], [])
line("headings: real headings still found", [t for t in HEADINGS if not section_inventory.heading(t)], [])
text(d / "h/doc.txt", ["1 Scope", "Body.", "2 Rules", "23 Feb – 17 Mar", "Body.", "3 Duties", "Body.", "1 Forms", "Body.", "2 Contacts", "Body."])
secs = section_inventory.scan_doc(d / "h/doc.txt")
line("headings: numbering back to 1 after the body is an appendix",
     [(s["id"], s["kind"]) for s in secs],
     [("doc#1", "heading"), ("doc#2", "heading"), ("doc#3", "heading"), ("doc#annex1:1", "appendix"), ("doc#annex1:2", "appendix")])
text(d / "h/list.txt", ["1 Scope", "Body.", "2 Rules", "1 Open the form", "Body.", "3 Duties", "Body."])
line("headings: a numbered list inside the body is not an appendix", [s["kind"] for s in section_inventory.scan_doc(d / "h/list.txt")],
     ["heading"] * 4)
text(d / "h/long.txt", [x for n in (1, 2, 3, 1, 2, 3, 4, 5) for x in (f"{n} Part", "Body.")])
line("headings: an appendix longer than the body stays an appendix", [s["kind"] for s in section_inventory.scan_doc(d / "h/long.txt")],
     ["heading"] * 3 + ["appendix"] * 5)

# ---------- warning noise ----------
patterns, _ = load_patterns()
own = judgement.Own({"rule": "RC-R", "fact": "RC-F", "self": "SD", "tbd": "TBD", "finding": "IF"})
rules = [{"id": "RC-R-109", "quote": "The coordinator approves each exchange application in writing."},
         {"id": "RC-R-110", "quote": "The ECTS total shown on S-4.1 shall respect IC-3."},
         {"id": "RC-F-054", "kind": "fact", "quote": "17.03.2026: 30 places (12 + 2), 4.1"},
         {"id": "RC-R-111", "quote": "Archive copies are retained."}]
good = {r["id"]: {"result": "✅", "evidence": r["quote"]} for r in rules}


def warned(changes, common=()):
    return [t for _, t in judgement.check_evidence(rules, {**good, **changes}, patterns, keywords, own, common)[0]]


w = warned({"RC-R-109": {"result": "✅", "evidence": "p3: the coordinator approves the application in writing. The ECTS total on S-4.1 follows IC-3."}})
line("evidence: a foreign sentence appended to a fitting row is warned",
     (len(w), w and w[0].startswith("RC-R-109:"), w and "RC-R-110" in w[0], w and "S-4.1" in w[0]), (1, True, True, True))
line("evidence: shared numbers, dates and letters raise no warning",
     warned({"RC-R-109": {"result": "✅", "evidence": "p4 b: the coordinator signs. Dated 17.03.2026, 30 places, 12 weeks, 2 rounds, section 4."},
             "RC-R-111": {"result": "✅", "evidence": "Archive copies: 17.03.2026, 30, 12, 2, 4."}}), [])
line("evidence: a rule with fewer than 2 meaningful keywords is never a comparison source",
     any("RC-F-054" in t for t in warned({"RC-R-111": {"result": "✅", "evidence": "30 places, 12 weeks, 2 rounds, 17.03.2026"}})), False)
quota = rules + [{"id": "RC-F-055", "kind": "fact", "quote": "Exchange quota for Erasmus partners: 17.03.2026, 30, 12, 2, 4.1"}]
dated = {**good, "RC-F-055": {"result": "✅", "evidence": quota[-1]["quote"]},
         "RC-R-111": {"result": "✅", "evidence": "Archive copies are retained. Seen 17.03.2026, 30, 12, 2, 4.1."}}
line("evidence: numbers shared with a rule that is a comparison source raise no warning",
     (len(judgement.terms_of(quota[-1], patterns, keywords, own, ())[1]) >= 2, [x for _, x in judgement.check_evidence(quota, dated, patterns, keywords, own)[0]]),
     (True, []))
line("keywords: numbers, dates, months, single letters and frequent words are dropped",
     judgement.meaningful(["30", "17.03.2026", "March", "b", "students", "coordinator", "ects"], {"students"}), ["coordinator", "ects"])
text(d / "c/a.txt", ["student " * 9 + "form form form " + " ".join(f"w{chr(97 + i)}x" for i in range(26)) + " once " * 1])
line("keywords: the most frequent 5% of the words count as common", "student" in judgement.common_words([d / "c/a.txt"], rules), True)

# ---------- root findings ----------
ids = ["RC-R-050", "RC-R-248", "RC-R-301", "F-050", "SD-018", "RC-R-007", "RC-R-008", "RC-R-009"]
res = {i: {"result": "❌", "evidence": "x", "target_loc": f"p{n}", "issue": f"issue {n}"} for n, i in enumerate(ids)}
res["RC-R-007"].update(target_loc="p9 S-1.1", issue="The button is missing.")
res["RC-R-008"].update(target_loc="p9, S-1.1", issue="the button is  missing")
findings = [{"id": "IF-7", "text": "t", "rules": ids[:4], "self_rules": ["SD-018"]}]
roots = judgement.root_findings([(i, res[i]) for i in ids], findings, judgement.Own())
line("root findings: rows of one internal finding on one line", roots[0]["label"], "IF-7 → RC-R-050, RC-R-248, RC-R-301, F-050, SD-018")
line("root findings: same location and issue grouped, others alone", [r["label"] for r in roots[1:]],
     ["same location and issue → RC-R-007, RC-R-008", "RC-R-009"])

two = {i: {"result": "❌", "evidence": "x", "target_loc": "p1", "issue": "the same issue"} for i in ("R-001", "R-002", "R-003", "R-004", "R-005")}
two["R-004"]["evidence"] = "see IF-3"                      # bound by citation only; R-005 has the same location and issue, no finding
pair = [{"id": "IF-1", "rules": ["R-001", "R-002"]}, {"id": "IF-2", "rules": ["R-002", "R-003"]}, {"id": "IF-3", "rules": []}]
roots = judgement.root_findings(list(two.items()), pair, judgement.Own())
line("root findings: a row bound to two findings is under each, no merge",
     [r["label"] for r in roots], ["IF-1 → R-001, R-002", "IF-2 → R-002, R-003", "IF-3 → R-004", "R-005"])
line("root findings: each group names exactly its own finding", [r["findings"] for r in roots], [["IF-1"], ["IF-2"], ["IF-3"], []])

# ---------- earlier runs ----------
p = d / "prev"; work = p / "work"
subprocess.run(["rm", "-rf", str(p)], check=True)
old = {"R-001": {"result": "✅", "evidence": "same"}, "R-002": {"result": "❌", "evidence": "old", "fix": "f"}}
dump(work / "results.json", old); dump(p / ".rule-check/doc/rules.json", {"rules": []})
progress.save(work / "progress.json", {"steps": {"visual": {"state": "skipped", "reason": "old"}}, "audit_seed": "old"})
dump(work / "self_audit.json", {"seed": "old"})
r = run("progress.py", "start", "work/progress.json", cwd=p)
state = progress.load(work / "progress.json")
line("earlier run: noticed at the start; its step records and self-audit are not carried over",
     ("earlier results found" in r.stdout, state["steps"], state.get("audit_seed"), (work / "self_audit.json").exists()), (True, {}, None, False))
new = {"R-001": old["R-001"], "R-002": {"result": "❌", "evidence": "re-read p4", "fix": "f"}, "R-003": {"result": "✅", "evidence": "new"}}
dump(p / "part.json", new); run("matrix.py", "set-bulk", "work/results.json", "part.json", cwd=p)
summary = progress.run_summary(progress.load(work / "progress.json"), json.loads((work / "results.json").read_text(encoding="utf-8")))[0]
line("earlier run: report line counts the identical rows", "önceki çalıştırmanın sonuçları kullanıldı): 1/3 rows identical" in summary, True)
run("progress.py", "start", "work/progress.json", "--fresh", cwd=p)
state = progress.load(work / "progress.json"); summary = progress.run_summary(state, new)[0]
line("from scratch: earlier files moved aside (not deleted) and not read",
     ((work / "results.json").exists(), any((work / "_set_aside").glob("*/results.json")), state["run"].get("rows"), "sıfırdan" in summary, ".rule-check/ exists" in summary),
     (False, True, None, True, True))
run("matrix.py", "set-bulk", "work/results.json", "part.json", cwd=p)
line("from scratch: writing results afterwards does not look at the set-aside run",
     (progress.load(work / "progress.json")["run"].get("fresh"), progress.result_files(work)[0][0].startswith("work/_set_aside")), (True, False))
progress.finish(work); run("matrix.py", "set-bulk", "work/results.json", "part.json", cwd=p)
state = progress.load(work / "progress.json")
line("forgotten start: writing after a finished run records it as an earlier run",
     (state["run"].get("automatic"), "3/3 rows identical" in progress.run_summary(state, new)[0]), (True, True))
line("no run record: verify gets an error", progress.run_summary({}, new)[1] is not None, True)

# ---------- tracked changes: the other scripts read the current text; quoting deleted text is rejected ----------
t = d / "tracked/work"
text(t / "ex/ref.txt", ["1 Deadlines", "Register within 30 60 days.", "A paper form is accepted."])
text(t / "ex/ref.current.txt", ["1 Deadlines", "Register within 60 days."])
dump(t / "ex/ref.changes.json", {"document": "ref", "unremoved": [], "changes": [{"page": 1, "type": "deleted", "text": "30"}]})
dump(t / "ex/ref.json", {"tracked_pdf": {"status": "detected"}})
line("tracked: <stem>.txt is read as <stem>.current.txt", [x for _, x in parse_lines(t / "ex/ref.txt")], ["1 Deadlines", "Register within 60 days."])
line("tracked: document name stays the stem", {s["doc"] for s in section_inventory.scan_doc(t / "ex/ref.current.txt")}, {"ref"})
quoted = [{"id": "R-001", "source": {"doc": "ref.pdf", "quote": "Register within 60 days."}},
          {"id": "R-002", "source": {"doc": "ref.pdf", "quote": "A paper form is accepted."}}]
lines_, _, errors = gates.tracked_changes(t, quoted)
line("tracked: report says it was detected", len(lines_) == 1 and "izlenen değişiklik algılandı" in lines_[0] and "ref.current.txt" in lines_[0], True)
line("tracked: only the rule quoting deleted text is rejected", [e.split(":")[0] for e in errors], ["R-002"])

# ---------- tracked changes without pdfplumber ----------
(d / "stub").mkdir(exist_ok=True); (d / "stub/pdfplumber.py").write_text("raise ImportError('stub')\n", encoding="utf-8")
out = d / "noplumber/ex"       # "ex": compared as extraction output across environments
r = run("extract.py", str(REPO / "tests/fixtures/tracked/tracked.pdf"), "-o", str(out), env={**os.environ, "PYTHONPATH": str(d / "stub")})
info = json.loads((out / "tracked.json").read_text(encoding="utf-8"))["tracked_pdf"]
line("no pdfplumber: reported as not run, with the annotated page; nothing removed",
     (info["status"], "page(s) 1" in info["reason"], (out / "tracked.current.txt").exists(), "NOT run" in r.stdout), ("not-run", True, False, True))
_, skipped, _ = gates.tracked_changes(d, [])
progress.save(d / "np/progress.json", {"extract_dirs": [str(out)]})
line("no pdfplumber: counted as a skipped check", [s[0] for s in gates.tracked_changes(d / "np", [])[1]], ["tracked-change detection in tracked"])

print(f"SUMMARY: {'FULL' if all(tot) else 'GAPS'} {sum(tot)}/{len(tot)}")
sys.exit(0 if all(tot) else 1)
