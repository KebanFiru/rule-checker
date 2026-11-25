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
sys.exit(0 if ok else 1)
