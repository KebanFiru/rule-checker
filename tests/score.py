#!/usr/bin/env python3
"""Scores a run against the answer key (fixtures/expected.json). Usage: score.py run/   (inside Docker)
NOTE: the rule-violation catch rate is contaminated when the same session that wrote the key also runs the scenario (see README)."""
import json, re, sys
from pathlib import Path
d = Path(sys.argv[1]); exp = json.loads(Path("fixtures/expected.json").read_text(encoding="utf-8"))
res = json.loads((d / "results.json").read_text(encoding="utf-8")); report = (d / "report.md").read_text(encoding="utf-8")
xref = (d / "xref_report.md").read_text(encoding="utf-8")
ok = lambda b: "✓" if b else "✗"; tot = {}
def line(name, got, want): tot[name] = (got, want); print(f"{ok(got == want)} {name}: {got}/{want}")

cov_sect = re.search(r"## Coverage table\n(.*?)\n## ", report, re.S).group(1)
line("Coverage table row count", len(re.findall(r"^\| R-\d+ ", cov_sect, re.M)), exp["rule_count"])

flag = {int(k[2:]) for k, v in res.items() if v["result"].replace("️", "") in ("❌", "⚠")}
planted = {x["rule_n"] for x in exp["planted_rule_violations"]}
line("Planted rule violations caught", len(flag & planted), len(planted))
print(f"  missed: {sorted(planted - flag)}  false positives: {sorted(flag - planted)}")

und = xref.split("## Undefined references")[1].split("##")[0]
line("Broken cross-references (xref_check, deterministic)", sum(1 for i in exp["broken_xrefs"] if f"`{i}`" in und), len(exp["broken_xrefs"]))
rep_x = sum(1 for i in exp["broken_xrefs"] if re.search(re.escape(i), report.split("## Cross-reference")[1]))
line("Broken references in the report", rep_x, len(exp["broken_xrefs"]))

vis = report.split("## Visual pass")[1].split("\n## ")[0]
hit = 0
for m in exp["screenshot_mismatches"]:
    seg = "\n".join(l for l in vis.splitlines() if m["name"] in l)
    hit += all(re.search(p, seg) for p in m["patterns"])
line("Screenshot/body mismatches in the report", hit, len(exp["screenshot_mismatches"]))

ex = json.loads(Path(d / "ex/target_srs.json").read_text(encoding="utf-8"))
line("Extraction artifact flagged (extract.py)", int(exp["extraction_artifact"]["word"] in ex.get("joined_words_extraction_artifacts", {})), 1)
rv = json.loads(Path(d / "ex/review.json").read_text(encoding="utf-8"))
line("DOCX comments extracted", len(rv["comments"]), len(exp["comments"]))
line("Tracked changes extracted (with author)", sum(1 for c in rv["tracked_changes"] if c["author"]), exp["tracked_changes"])

pp = (d / "per_person.md").read_text(encoding="utf-8"); persons = {}
for blk in re.split(r"^## ", pp, flags=re.M)[1:]:
    name, *rest = blk.splitlines(); persons[name.strip()] = [re.match(r"\d+\.\s*\[([^\]]+)\]", l).group(1) for l in rest if re.match(r"\d+\.\s*\[", l)]
good = 0
for c in exp["comments"]:
    try: good += persons[c["person"]][c["n"] - 1] == c["expected"]
    except Exception: pass
line("Review comment verdict accuracy", good, len(exp["comments"]))
print("\nSUMMARY:", "FULL" if all(g == w for g, w in tot.values()) else "GAPS")
