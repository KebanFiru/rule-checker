#!/usr/bin/env python3
"""PDF tracked-change detection (needs pdfplumber: run in the chat-env-v2 image). Usage: score_tracked.py WORKDIR"""
import json, shutil, subprocess, sys
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent; F = REPO / "tests/fixtures/tracked"
d = Path(sys.argv[1]).resolve(); shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True); tot = []


def line(name, got, want):
    tot.append(got == want); print(("✓" if got == want else "✗"), f"{name}: {got}/{want}")


def run(script, *args):
    r = subprocess.run([sys.executable, str(REPO / "scripts" / script), *args], capture_output=True, text=True, cwd=d)
    if r.returncode:
        print(r.stdout, r.stderr)
    return r.stdout


def current(out, stem):
    return [l.split("\t", 1)[1] for l in (d / out / f"{stem}.current.txt").read_text(encoding="utf-8").splitlines()]


def changes(out, stem, kind):
    return [c["text"] for c in json.loads((d / out / f"{stem}.changes.json").read_text(encoding="utf-8"))["changes"] if c["type"] == kind]


DELETED = ["30", "always", "also", "Paper forms are accepted at the front desk."]
for engine in ("pdftotext", "pypdf"):
    out = f"ex_{engine}"
    said = run("extract.py", str(F / "tracked.pdf"), "--engine", engine, "-o", out)
    text = current(out, "tracked")
    line(f"{engine}: strike line, thin rectangle, grey struck text and StrikeOut annotation detected", changes(out, "tracked", "deleted"), DELETED)
    line(f"{engine}: deleted text removed from the current text",
         text[1:5], ["Students shall register within 60 days.", "The fee is 30 EUR and the form has 30 fields.", "Late requests are rejected.", "A paper copy is required."])
    line(f"{engine}: underline, table rule, link and red text are not deletions",
         [any(w in l for l in text) for w in ("important", "check the deadline", "the portal", "front desk")], [True, True, True, False])
    found = " ".join(c["text"] for c in json.loads((d / out / "tracked.changes.json").read_text(encoding="utf-8"))["changes"])
    line(f"{engine}: labels crossed by a long connector stay and are not reported",
         [(any(w in l for l in text), w in found) for w in ("Enrolment record", "Course", "Student")], [(True, False)] * 3)
    line(f"{engine}: insertion and colour-only candidate reported", (changes(out, "tracked", "added"), changes(out, "tracked", "suspected")),
         (["60"], ["check the deadline"]))
    data = json.loads((d / out / "tracked.changes.json").read_text(encoding="utf-8"))
    line(f"{engine}: page recorded, nothing left unremoved, run says so",
         ({c["page"] for c in data["changes"]}, data["unremoved"], "izlenen değişiklik algılandı" in said), ({1}, [], True))

run("section_inventory.py", "scan", "ex_pdftotext/tracked.txt", "-o", "work/ref_sections.json")
line("section inventory reads the current text", json.loads((d / "work/ref_sections.json").read_text(encoding="utf-8"))["sections"][0]["doc"], "tracked")

run("docx_to_pdf.py", str(F / "office.fodt"), "-o", "pdf", "--timeout", "90")
if (d / "pdf/office.pdf").exists():
    run("extract.py", "pdf/office.pdf", "-o", "ex_office")
    line("LibreOffice export: struck text removed, inserted and ordinary text kept", current("ex_office", "office"),
         ["1 Registration", "Students shall register within 60 days after the offer.", "The registration office confirms every request by e-mail.",
          "The fee is 30 EUR and it is paid once."])
else:
    line("LibreOffice export converted", False, True)

run("extract.py", str(REPO / "tests/fixtures/rules.pdf"), str(REPO / "tests/fixtures/target_srs.pdf"), str(REPO / "tests/fixtures/coverage/target_ui.pdf"), "-o", "plain")
line("documents without tracked changes: nothing detected, no extra files",
     ([json.loads(p.read_text(encoding="utf-8"))["tracked_pdf"]["status"] for p in sorted((d / "plain").glob("*.json"))],
      list((d / "plain").glob("*.current.txt"))), (["none"] * 3, []))

print(f"SUMMARY: {'FULL' if all(tot) else 'GAPS'} {sum(tot)}/{len(tot)}")
sys.exit(0 if all(tot) else 1)
