# 3. Verdict rules (checked by `verify`)

## Which result
- **❌ needs a change in the target** and a `fix` that says which one. A fix that is or starts with "no change", "none", "team decision", "TBD" (TR: "değişiklik yok/gerekmez", "ekip/takım kararı") is rejected. A TBD detail inside a concrete fix is fine: "Add the Scope section (content: TBD-2)".
- **⚖️** the reference contradicts itself, or nothing has to change in the target until the team decides. Cite `TBD-n` and define it in `work/tbd.json`: `[{"id":"TBD-1","text":"what has to be decided"}]`. A real violation that merely needs a value from the team stays ❌.
- **➖ is not for absent things.** A required item missing from the target is ❌/⚠️ (or ❓/⚖️). A fact that the target never mentions may not be ➖ if its reference section is an open question or rule-bearing (rejected). ➖ on a rule stays valid when the rule does not apply (nothing it could apply to); the report warns on such rows: check each.

## One row per missing item
"Section X is missing …" or "these questions are unanswered" never replaces the single findings. Every missing item gets its OWN rule or fact row with ❌ or ⚠️ (add the rule/fact to the register if step 1 did not), and the aggregate row lists them:
```json
{"R-020":{"result":"⚠️","evidence":"p12: name only, see R-021 and R-022","issue":"missing contact details","fix":"…","members":["R-021","R-022"]}}
```

## Evidence belongs to its row
Quote the target place that decides THIS rule, using the rule's IDs and terms. The report warns when the evidence IDs do not overlap the rule's IDs, or when it uses another rule's keywords and none of its own: check each warning. References such as `see R-012`, `see F-003`, `TBD-2` must exist, otherwise `verify` fails.

## Contradictions inside the target
If a contradiction found in step 2, 4 or 5 (e.g. a use-case exception against a screen) falls under a rule's topic, write it on that rule's row too, with its `IF-n` number (see `4-internal.md`), and let it influence the result.
