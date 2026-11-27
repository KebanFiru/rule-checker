# 6b. Self-audit (mandatory, last step before the report)

1. `matrix.py audit-plan work/rules.json work/results.json` lists the rows to re-check: every ❌, ⚠️ and ⚖️ row plus a random 10% of the ✅ rows (at least one), over the reference register AND the target's own rules. It refuses to run while a rule has no result: the random seed is created only when this step starts, so the selection is unknown during the main pass. The seed is stored in `progress.json` and `self_audit.json` and printed in the report. Do NOT pass `--seed` yourself; it exists only to reproduce a selection (a hand-supplied seed is marked as such in the report), and a run accepts one seed only.
2. For EACH listed row open the SOURCE again: the reference quote in context and the target place (Read tool or `search.py`), not your earlier note. Ask: does the quote really say this? Is the evidence about this rule? Is ❌ right, or ⚠️/⚖️? Is there a contradiction elsewhere in the target?
3. If a verdict or text changes, record it with `matrix.py set-bulk` first.
4. Record the check:
```json
{"R-001":{"source":"re-read ref p3 and target p9 QR-A.1","note":"why the verdict changed (required if it did)"}}
```
`matrix.py audit-record work/rules.json work/results.json work/self_audit.json work/audit_part.json`
5. Run `audit-plan` again: rows that became findings are added. Any row edited after its check must be recorded again.

The report lists changed verdicts under "Changed in self-audit". `verify` fails while a planned row is unchecked or stale. Only if the step truly cannot be done, and only before `audit-plan` (a planned audit must be finished): `progress.py step work/progress.json self-audit skipped --reason "…"` (counted in the report). Do not record a row you did not re-read.
