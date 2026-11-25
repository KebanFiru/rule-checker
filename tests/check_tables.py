#!/usr/bin/env python3
"""Checks extract.py --tables output for target_srs.pdf. Usage: check_tables.py <ex_dir>   (stdlib only)
Expected tables on page 1: Table 1 (Rev/Description) and Table 2 (Service/Fee). Prints PASS/FAIL per engine path."""
import json, sys
from pathlib import Path
d = json.loads((Path(sys.argv[1]) / "target_srs.tables.json").read_text(encoding="utf-8"))
T1 = [["Rev", "Description"], ["1", "First draft"], ["2", "Review fixes"]]
T2 = [["Service", "Fee"], ["Standard", "250 USD"]]
if d["engine"] == "pdfplumber":
    got = [t["rows"] for t in d["tables"] if t["page"] == 1]
    ok = T1 in got and T2 in got
    print(f"tables: engine=pdfplumber, {len(d['tables'])} tables; Table 1 cells {'OK' if T1 in got else 'WRONG'}, Table 2 cells {'OK' if T2 in got else 'WRONG'} -> {'PASS' if ok else 'FAIL'}")
else:
    rows = [r["cells"] for r in d["rows"] if r["page"] == 1]
    ok = ["Rev", "Description"] in rows and ["Standard", "250 USD"] in rows
    print(f"tables: engine={d['engine']} ({d['reason']}); layout rows include header+data cells -> {'PASS' if ok else 'FAIL'} (fallback path)")
sys.exit(0 if ok else 1)
