#!/usr/bin/env python3
"""Positive/negative controls for extract.py's engine cross-check and split-word repair (stdlib only, imports scripts/extract.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import extract
ok = True
def check(name, cond):
    global ok; ok &= bool(cond); print(("PASS" if cond else "FAIL"), name)
check("merged words ('userdata' vs 'user data') ARE reported", extract.compare_engines([["userdata handling"]], [["user data handling"]]))
check("missing word IS reported", extract.compare_engines([["the system shall"]], [["the shall"]]))
check("end-of-line hyphen join ('e-mail' vs 'email') is NOT reported", not extract.compare_engines([["by e-mail"]], [["by email"]]))
check("line-end hyphenation ('e-' + 'mail' vs 'email') is NOT reported", not extract.compare_engines([["by e-", "mail"]], [["by email"]]))
check("reading-order differences are NOT reported", not extract.compare_engines([["a b c"]], [["c b a"]]))
pages, other = [["T able 1 and T able 5, A big idea"]], [["Table 1 and Table 5, A big idea"]]
rep = extract.repair_splits(pages, other)
check("'T able' re-joined using the other engine (2 repairs)", len(rep) == 2 and pages[0][0].startswith("Table 1 and Table 5"))
check("text both engines agree on ('A big') is untouched", "A big idea" in pages[0][0])

# --- ligature fragments (LibreOffice + Type 1 fonts, seen with pypdf 6.17 in the Claude chat sandbox) ---
bad = [["1. The coordinator must approve the payment request | mail. Efficient office workflow: final file, flow and",
        "within three working days; otherwise the request is | e cient handling of Öğrenci İşleri, İstanbul Şişli, ağırffi çalışma",
        "automatically and the student is staff"]]
good = [["1. The coordinator must approve the payment request | mail. Efficient office workflow: final file, flow and",
         "within three working days; otherwise the request is | efficient handling of Öğrenci İşleri, İstanbul Şişli, ağır çalışma",
         "automatically and the student is staff"]]
check("ligature damage ('e cient', 'ağırffi') IS reported by the engine cross-check", extract.compare_engines(bad, good))
fixed = [list(bad[0])]
rep = extract.repair_splits(fixed, good)
kinds = sorted(r["kind"] for r in rep)
check("repair: 'e cient' -> 'efficient' (ligature-gap) and 'ağırffi' -> 'ağır' (ligature-stray)", kinds == ["ligature-gap", "ligature-stray"])
check("repaired primary text is correct", "efficient handling" in fixed[0][1] and "ağırffi" not in fixed[0][1] and "ağır" in fixed[0][1] and "e cient" not in fixed[0][1])
check("repair is recorded (from/to/kind)", all({"page", "kind", "from", "to"} <= set(r) for r in rep))
check("after repair the engine cross-check no longer disagrees", not extract.compare_engines(fixed, good))
check("words both engines agree on ('staff', 'file') are untouched", "staff" in fixed[0][2] and "final file" in fixed[0][0])
same = [["The staff of the office"]]; before = [list(same[0])]
check("no repair when both engines agree", not extract.repair_splits(same, before) and same == before)
sys.exit(0 if ok else 1)
