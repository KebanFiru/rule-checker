#!/usr/bin/env python3
"""Scores the process-model/regression test against fixtures/process/expected_v2.json. Usage: score_v2.py run2/ (inside Docker)
The deterministic parts (diff, impact, invariants) are independent; classification.json is the model's own judgement (contaminated)."""
import json, sys
from pathlib import Path
d = Path(sys.argv[1]); e = json.loads(Path("fixtures/process/expected_v2.json").read_text(encoding="utf-8"))
J = lambda n: json.loads((d / n).read_text(encoding="utf-8")); tot = []
def line(name, got, want):
    tot.append(got == want); print(("✓" if got == want else "✗"), f"{name}: {got}/{want}")
df = J("diff.json")
line("doc_diff: changed units", len({c['key'] for c in df['changed']} & set(e['diff']['changed'])), len(e['diff']['changed']))
line("doc_diff: added unit", len({c['key'] for c in df['added']} & set(e['diff']['added'])), 1)
line("doc_diff: moved unit (SP-1.3/1.4)", int(bool({m['key'] for m in df['moved']} & set(e['diff']['moved_any_of']))), 1)
line("doc_diff: format noise separated (not in changed)", int(set(e['diff']['format_only']) <= set(df['format_only']) and not set(e['diff']['format_only']) & {c['key'] for c in df['changed']}), 1)
iv = {r['id']: r['status'] for r in J("inv_v2.json")}
line("invariant FAIL (regression/unpropagated)", sorted(k for k, v in iv.items() if v == "FAIL"), e['invariants_on_v2']['FAIL'])
line("invariant PASS (no false alarms)", sorted(k for k, v in iv.items() if v == "PASS"), e['invariants_on_v2']['PASS'])
im = J("impact.json")
line("impact: node using the same parameter", int(set(e['impact_must_include']['same_parameter']) <= set(im['same_parameter'])), 1)
line("impact: linked invariants", int(set(e['impact_must_include']['invariants']) <= {i['id'] for i in im['invariants']}), 1)
line("impact: change with no counterpart in the model (🆕 candidate)", int(any(k == 'SP-1.6' for k, _ in im['unmapped'])), 1)
cl = J("classification.json")
ok = sum(1 for k, v in e['classification'].items() if cl.get(k, {}).get('class') == v)
line("classification (✅/⚠️/❌/🆕)", ok, len(e['classification']))
ch = (d / ".rule-check/process/changelog.md").read_text(encoding="utf-8")
line("changelog v2 entry", sum(1 for w in e['changelog_must_mention'] if w in ch), len(e['changelog_must_mention']))
mm = (d / ".rule-check/process/process_model.yaml").read_text(encoding="utf-8")
line("regression not written to the model (P-reminder still 3 days)", int("param: P-reminder" in mm and "value: 3, unit: days, doc_unit" in mm), 1)
print("\nSUMMARY:", "FULL" if all(tot) else "GAPS")
