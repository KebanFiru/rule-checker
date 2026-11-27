---
name: rule-check
description: Check one or more target documents (PDF/DOCX) against the rules in reference documents, and optionally judge reviewer comments, in a single exhaustive pass: builds a numbered rule register, checks every rule individually with evidence, runs cross-reference and consistency scripts, inspects page images, and outputs a coverage table plus per-person findings. Also keeps a process model of the document as a persistent file and uses it to catch regressions when the document is updated. Use when asked to compare a document to a rules/requirements PDF, find violations, evaluate review comments, or check that a document update did not break anything.
---

# rule-check

Check TARGET documents against REFERENCE documents in ONE exhaustive pass. **Nothing is skipped silently:** whatever is skipped appears in the report with a count and a reason. The work is finished only when `matrix.py verify` passes.

Each step has its own detail file: when you START a step, read ONLY that file, once (never load them all up front, never re-read one). Read `reference/pitfalls.md` before starting.

```bash
S=<skill-dir>/scripts    # <skill-dir> contains this SKILL.md. Set once, use in every command below; plain python3, never pip install
```
When resuming (new session or summarized context) run FIRST:
```bash
python3 $S/progress.py show work/progress.json
python3 $S/matrix.py status work/rules.json work/results.json
```

## Steps (in order, WITHOUT skipping)
A step you cannot do: `python3 $S/progress.py step work/progress.json <step> skipped --reason "…"`. MANDATORY (`verify` fails if not run and not skipped with a reason; step names): `reference`, `visual`, `self-rules`, `self-audit`.

**E. Environment** (always first, one command) — tell the user which checks cannot run here.
▶ On starting this step read only: `reference/steps/e-environment.md`
```bash
python3 $S/env_check.py --json work/env.json
```

**0. Classify + identity** — target / reference (note immutable ones) / review; ask if unsure. Match EVERY document name the user used; if one is not a file, ASK (else the note goes to the top of the report).
▶ On starting this step read only: `reference/steps/0-identify.md`
```bash
python3 $S/extract.py target.pdf ref.pdf [ref2.pdf …] [review.docx] [--docx-source target.docx] [--tables] [--reading-order] -o work/ex
python3 $S/prefixes.py work/ex/*.txt -o work/prefixes.json    # own ID prefixes; R- F- TBD- IF- below stand for the chosen ones
python3 $S/section_inventory.py identity --target work/ex/target.txt --files ref.pdf --names "Ek B" "PAR" [--lang tr] -o work/doc_identity.json
```

**1. Reference coverage, then rule register** — classify EVERY section (rule-bearing | fact | open-question | descriptive-only) before writing rules; rules `R-001…`, facts `F-001…`, each with `source.section`, into `work/rules.json`.
▶ On starting this step read only: `reference/steps/1-rule-register.md`
```bash
python3 $S/section_inventory.py scan work/ex/ref.txt ["work/ex/target.txt@Appendix B"] -o work/ref_sections.json
python3 $S/section_inventory.py classify work/ref_sections.json work/classes.json
```

**2. Deterministic pass** — read the warnings; judge EVERY parameter conflict.
▶ On starting this step read only: `reference/steps/2-deterministic.md`
```bash
python3 $S/id_index.py work/ex/target.txt -o work/id_index.json
python3 $S/xref_check.py work/ex/target.txt --numbers --also-numbers work/ex/ref.txt -o work/xref_report.md
python3 $S/param_check.py scan --target work/ex/target.txt --ref work/ex/ref.txt [--model <model>] [--concepts work/param_concepts.local.json] -o work/params.json
python3 $S/param_check.py verdict work/param_verdicts.json work/param_part.json
```

**3. Traceability** — one result per rule/fact, one by one, in blocks of 20: ✅ ❌ ⚠️ ➖ ❓ ⚖️ with evidence (⚖️ = reference contradiction / team decision, cites TBD-n). Search a whole block in ONE call; never one grep per term.
▶ On starting this step read only: `reference/steps/3-traceability.md` and `reference/steps/3-verdicts.md`
```bash
python3 $S/search.py work/ex/target.txt --rules work/rules.json --all-blocks
python3 $S/search.py work/ex/target.txt -t "term" -t "other term"
python3 $S/matrix.py set-bulk work/results.json work/part_01.json
python3 $S/matrix.py status work/rules.json work/results.json
```

**4. Internal consistency** — references, IDs, values, names, screens vs body → `work/internal.md`; every contradiction also into `work/internal.json`, as `IF-n`, bound to the rules it concerns (decisions: `work/tbd.json`).
▶ On starting this step read only: `reference/steps/4-internal.md` and `reference/steps/4-self-rules.md`
Check the whole target against the rules it declares itself (`SD-n`, separate from the reference register):
```bash
python3 $S/self_rules.py scan work/ex/target.txt -o work/self_sections.json
python3 $S/self_rules.py classify work/self_sections.json work/self_classes.json
python3 $S/matrix.py set-bulk work/self_results.json work/self_part_01.json
```

**5. Visual pass** — EVERY inventory page gets a log row; Read tool in batches of up to 20 pages.
▶ On starting this step read only: `reference/steps/5-visual.md`
```bash
python3 $S/visual_inventory.py scan target.pdf -o work/visual_inventory.json
python3 $S/visual_inventory.py record work/visual_log.json work/visual_part_01.json
```
DOCX target: `python3 $S/docx_to_pdf.py target.docx -o work/docx_pdf` first.

**6. Review documents** (if given) — one verdict per comment, `templates/per_person.md`.
▶ On starting this step read only: `reference/steps/6-reviews.md`

**6b. Self-audit** (MANDATORY before the report) — after all rules have a result: re-read the source for every ❌/⚠️/⚖️ row and a seeded random 10% of ✅.
▶ On starting this step read only: `reference/steps/6b-self-audit.md`
```bash
python3 $S/matrix.py audit-plan work/rules.json work/results.json
python3 $S/matrix.py audit-record work/rules.json work/results.json work/self_audit.json work/audit_part.json
```

**7. Report** — title lines, then the generated output unchanged ("Coverage summary" first), then your findings (`templates/report.md`).
▶ On starting this step read only: `reference/steps/7-report.md`
```bash
python3 $S/matrix.py coverage work/rules.json work/results.json -o work/coverage.md --env work/env.json [--visual work/docx_pdf/visual_status.json]
python3 $S/matrix.py verify work/rules.json work/report.md      # must exit 0
```

**8. Fixes only if the user asks** — then run steps 2–5 again and list regressions separately.
▶ On starting this step read only: `reference/steps/8-fixes.md`

## Process model + regression check
On every run, FIRST read `.rule-check/<document>/process_model.yaml` and `invariants.yaml` if they exist.
▶ Before building the model (A) read only `reference/steps/process-model.md`; before updating (B) or fixing a document (C) also `reference/steps/process-model-update.md`.
```bash
python3 $S/model_check.py check <model> --rules <rules.json>
python3 $S/model_check.py invariants <model> <invariants.yaml> --doc work/ex/new.txt -o work/inv.json
python3 $S/doc_diff.py old.pdf new.pdf -o work/diff.json
python3 $S/impact.py --model <model> --diff work/diff.json --rules <rules.json> --invariants <invariants.yaml> -o work/impact
python3 $S/model_check.py bump <model> --nodes SP-1.5 --reason "…"
```

## Rules
- Never invent a rule/value with no source; what the reference does not answer = "TBD / team decision".
- Mark your own assumptions as "assumption".
- Do not propose a change that would make something look done that nobody did (e.g. "show it as if it had been done in Figma").
- Write the report in the user's language; quotes from documents stay in their original language.
- Flag separately any proposal that requires touching an immutable document.
- Never delete or change invariants or rules without user approval: report a "proposed change".
