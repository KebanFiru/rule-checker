# Rule Register

Every row is ONE atomic, checkable statement. Never add a rule that has no source.
Put interpretation in the "Interpretation / assumption" column (never mixed into the rule itself); your own assumptions start with "ASSUMPTION:".

| ID | Source document | Page | Quote (original language) | Type | Scope (target sections) | Interpretation / assumption |
|---|---|---|---|---|---|---|
| R-001 | | | | required content | | |

Type: required content / prohibition / format / numeric value / process order / terminology / template section

## rules.json schema
```json
{"rules":[{"id":"R-001","source":{"doc":"rules.pdf","page":2,"quote":"..."},
  "type":"required content","scope":"whole document","interpretation":"","keywords":["..."]}]}
```
`keywords` is optional but recommended (`matrix.py skeleton` finds candidates with it).

## Conflicting references
If the same rule is worded differently in two places, register BOTH as separate rules and list them here:
| Rule A | Rule B | Conflict | Decision |
