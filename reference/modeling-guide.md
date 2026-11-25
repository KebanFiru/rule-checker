# Process model guide

## What is modelled
The processes in the document: steps, actors, order, conditions (preconditions), durations/amounts/thresholds (parameters), exceptions (on_exception), status values, TBDs, entities. Purpose: detail must not be lost from the context of a long document, and regressions must be caught on update. The model is persistent memory: on EVERY run `process_model.yaml` and `invariants.yaml` are read first.

## Rules
1. **Source is mandatory.** Every process/step/parameter carries `source` (page + ID + short quote). Unsourced information does not enter. An inference not stated in the document gets `assumption: true` and still cites the place it is based on.
2. **Short and complete.** Do not copy sentences; record structure and values. But no value, condition or exception may be dropped ("3 days" and "only if OLA v2 is uploaded" must both be in the model).
3. **Take IDs from the document.** If the document has IDs like SP-7.3 / UC-3.8 / QR-G.14, use them as node IDs; `impact.py` maps a changed paragraph to a node by ID. If there are no IDs, assign your own and always write `source.quote` (mapping falls back to the quote).
4. **One place per parameter.** A duration/amount/threshold is defined once in `parameters`; steps link to it with `duration.param` and its usages are listed in `used_in`. If the document gives the same concept different values in two places the model errors out → make it a finding of the first report, do not pick one (TBD).
5. **Flow.** `next` is the normal order; `on_exception.goto` is the exception branch. The last step is either at the end of the list or `terminal: true`. For an intentional cycle (retry) set `allow_loop: true` on a step in the cycle.
6. **YAML is the single source of truth.** `.mmd` is auto-generated (`model_check.py check`), never edited by hand.

## Deriving invariants
From the model and the rules derive checkable "must not break" statements: order, same parameter everywhere (param_equal), reachability, must exist, must be absent, cardinality, reference integrity (cross_ref). Each has a source. They are cheap: all of them run on every update. They are never deleted without user approval; if one has to change, report it as a `proposed change`.

## Classification (update run)
- ✅ expected change: conflicts with no invariant/shared parameter and the intent is clear (review comment, user request).
- ❌ regression: was correct before (invariant was PASS) and is now broken, e.g. step order broken.
- ⚠️ unpropagated change: changed in one place, still old in another place using the same parameter/concept.
- 🆕 new process/step: no counterpart in the model.
- ❓ model needs updating: the change looks right but the model is stale / unclear.
Regressions and unpropagated changes come first in the report. ❌/⚠️ items are not written to the model until the user decides (recorded as TBD).

## File layout (next to the document)
```
.rule-check/<document-name>/
├── process_model.yaml   # single source of truth
├── process_model.mmd    # auto-generated
├── invariants.yaml
├── rules.json
└── changelog.md         # written by model_check.py bump
```

## Noise
Line breaks, hyphens, whitespace and footers ("Page N") are noise (`doc_diff.py` lists them separately). They do not count as real changes, but you can read the page with the Read tool to be sure.
