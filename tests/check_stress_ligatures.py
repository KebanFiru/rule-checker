#!/usr/bin/env python3
"""On the real LibreOffice stress PDF: the primary text of BOTH engines must not contain the damaged forms ('e cient', 'ağırffi'),
and the repair (if one was needed) must be recorded. Usage: check_stress_ligatures.py <dir with stress.txt + stress.json> [...]"""
import json, sys
from pathlib import Path
ok = True
for d in map(Path, sys.argv[1:]):
    txt = (d / "stress.txt").read_text(encoding="utf-8"); meta = json.loads((d / "stress.json").read_text(encoding="utf-8"))
    broken = [w for w in ("e cient", "ağırffi", "ağırff") if w in txt]
    reps = [r["kind"] for v in meta.get("repairs", {}).values() for r in v]
    warned = any("different word sets" in w for w in meta.get("warnings", []))
    good = not broken and not warned
    ok &= good
    print(f"{'PASS' if good else 'FAIL'} {d.name}: broken forms in primary text={broken or 'none'}; repairs={len(reps)} {sorted(set(reps))}; engine warning after repair={warned}")
sys.exit(0 if ok else 1)
