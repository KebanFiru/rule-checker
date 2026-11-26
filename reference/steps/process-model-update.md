# Process model: update (B) and fixes (C)

Model layout and rules: `process-model.md`.

### B. UPDATE RUN (model exists; read the model + invariants first)
1. `python3 $S/doc_diff.py old.pdf new.pdf -o work/diff.json` (PDF/DOCX; line breaks/hyphens/footers are listed separately as noise).
2. `python3 $S/impact.py --model <model> --diff work/diff.json --rules <rules.json> --invariants <invariants.yaml> -o work/impact` → affected nodes, neighbours, nodes using the same parameter, rules, invariants; changes with no counterpart in the model (🆕/❓). **Run it BEFORE updating the model.**
3. Check every affected item in the new document one by one; also re-verify ALL invariants (not only the affected ones): `model_check.py invariants … --doc work/ex/new.txt -o work/inv.json`.
4. Classify: ✅ expected change | ❌ regression (was correct, now broken) | ⚠️ unpropagated change (changed in one place, still old in linked places) | 🆕 new process/step (not in the model) | ❓ model needs updating.
5. Report: regressions and unpropagated changes FIRST, then the rest.
6. Model update: apply only ✅/🆕 changes to the model (❌/⚠️ are not written to the model until the user decides; record them in `tbd`); run `model_check.py check` again; then `python3 $S/model_check.py bump <model> --nodes SP-1.5,SP-2.2 --doc-version "Rev 2" --reason "<finding/review no.>"` (increments the version and writes version/date/nodes/reason to `changelog.md`). Rule and invariant changes need user approval.

### C. When I (Claude) make a fix in the document
BEFORE the fix, list the impact with `impact.py --keys SP-1.5,SP-2.3 …` (which nodes/parameters/rules/invariants are affected); AFTER the fix, run the B steps (doc_diff → impact → all invariants → classification → report) for my own change and list regressions separately.
