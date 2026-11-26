# Rule Register

Every row is ONE atomic, checkable statement. Never add a rule that has no source.
Put interpretation in the "Interpretation / assumption" column (never mixed into the rule itself); your own assumptions start with "ASSUMPTION:".

| ID | Source document | Page | Quote (original language) | Type | Scope (target sections) | Interpretation / assumption |
|---|---|---|---|---|---|---|
| R-001 | | | | required content | | |

Type: required content / prohibition / format / numeric value / process order / terminology / template section

## rules.json schema
```json
{"rules":[{"id":"R-001","source":{"doc":"rules.pdf","page":2,"section":"rules#3.1","quote":"..."},
  "type":"required content","scope":"whole document","interpretation":"","keywords":["..."]}]}
```
`keywords` is optional but recommended (`search.py` and `matrix.py skeleton` find candidates with it).
`source.section` is the id from `work/ref_sections.json` (required once that file exists). Facts from AS-IS text or interview notes
use `"id": "F-001"` and `"kind": "fact"` in the same file; they get the same result symbols as rules.

## Conflicting references
If the same rule is worded differently in two places, register BOTH as separate rules and list them here:
| Rule A | Rule B | Conflict | Decision |
