# 4. The target's own rules (self-declared)

Constraints, invariants and consistency rules the TARGET declares itself (e.g. `IC-1`, `BR-3`, a "Consistency rules" section). They are NOT reference rules: registering them as `R-` would let the target verify itself and inflate the rule counts. They get their own register, results and report section, and no `⚑ source assumption` mark.

1. `self_rules.py scan work/ex/target.txt` lists candidates: sections headed constraint / invariant / integrity / consistency rule / business rule / kısıt / bütünlük / tutarlılık / iş kuralı, and ID lists (IC-, BR-, C- …; other prefixes from 3 members). Compare with the table of contents; add a missed prefix with `--prefix XY`.
2. Classify EVERY candidate (`self_rules.py classify work/self_sections.json part.json`): `self-rules`, or `not-rules` with a reason (e.g. requirement lists judged against the references).
3. Register one row per declared rule in `work/self_rules.json` (a section without IDs: one row per rule, `source.section`):
```json
{"rules":[{"id":"SD-001","doc_id":"IC-1","source":{"doc":"target.pdf","page":146,"section":"target#9.2","quote":"…"}}]}
```
4. Check the WHOLE target against each one (`search.py work/ex/target.txt --rules work/self_rules.json --all-blocks`), then record: `matrix.py set-bulk work/self_results.json work/self_part_01.json` (same result symbols and verdict rules).
5. Every violation (❌/⚠️) becomes an `IF-n` finding in `work/internal.json` with `"self_rules": ["SD-003"]`; the row mentions the `IF-n`. If the same topic also falls under a reference rule, list it in `"rules"` too and write the finding on that row as well.

The scan is mandatory, also when you expect none (zero candidates is a result); the only alternative is `progress.py step work/progress.json self-rules skipped --reason "…"`.

`verify` fails on: an unclassified candidate; a declared ID without a row; an ID that does not occur in the target; a row without result; a violation without a finding; a finding that mentions a declared ID but does not list its row.
