# Process model + regression check

Read this before step A. Before B (update) or C (fix) read `process-model-update.md` as well. Modelling rules: `../modeling-guide.md`; schemas: `../../templates/process_model.schema.yaml`, `../../templates/invariants.schema.yaml`. With a model present, pass it to `param_check.py scan --model <model>`.

## Overview (persistent memory)
The processes in a document (steps, actors, order, conditions, durations, exceptions) are turned into a compact model stored as a FILE. When the document is updated, the changes are checked against this model so that an update cannot break something that was previously correct. **On every run, FIRST read the model and the invariants** (so detail is not lost from the context of a long document). Guide: `../modeling-guide.md`; schemas: `../../templates/process_model.schema.yaml`, `../../templates/invariants.schema.yaml`.

The model lives next to the document (in the working folder):
```
.rule-check/<document-name>/ process_model.yaml (single source of truth) · process_model.mmd (auto-generated, do not edit) · invariants.yaml · rules.json · changelog.md
```
Rules: `source` is REQUIRED on every node/parameter, unsourced information never enters the model; interpretation/assumption is marked `assumption: true`; keep the model short but never drop a value/condition/exception. Invariants or rules are never deleted/changed without user approval: report them as a "proposed change".

### A. FIRST RUN (no `.rule-check/<document>/process_model.yaml` yet)
1. After the rule register (step 1), extract the process model → `python3 $S/model_check.py check .rule-check/<document>/process_model.yaml --rules .rule-check/<document>/rules.json` (the same call generates the `.mmd`) → fix the errors; repeat until there are 0 errors.
2. Coverage check: is every process section/UC/screen of the document linked to at least one node? List the ones that are not.
3. Derive the invariants (`invariants.yaml`) and verify them: `python3 $S/model_check.py invariants <model> <invariants> --doc work/ex/document.txt`. Show the user a summary: how many processes, nodes, parameters, invariants.
4. If the document already contradicts the model (e.g. two different durations in two places), make that a finding of the first report (model_check reports "same parameter, different value").
5. Write the v1 entry in `changelog.md`.
