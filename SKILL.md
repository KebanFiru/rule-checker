---
name: rule-check
description: Check one or more target documents (PDF/DOCX) against the rules in reference documents, and optionally judge reviewer comments, in a single exhaustive pass: builds a numbered rule register, checks every rule individually with evidence, runs cross-reference and consistency scripts, inspects page images, and outputs a coverage table plus per-person findings. Also keeps a process model of the document as a persistent file and uses it to catch regressions when the document is updated. Use when asked to compare a document to a rules/requirements PDF, find violations, evaluate review comments, or check that a document update did not break anything.
---

# rule-check

Check TARGET documents against REFERENCE documents in ONE exhaustive pass. **Nothing is skipped silently:** whatever is skipped appears in the report with a count and a reason. The work is finished only when `matrix.py verify` passes.

Details are in `reference/workflow-details.md`, one `##` section per step: when you reach a step, read ITS section once (do not load the whole file up front or re-read it). Read `reference/pitfalls.md` once before step 1.

```bash
S=<skill-dir>/scripts    # the directory that contains this SKILL.md; plain python3, never pip install
```
When resuming (new session or summarized context) run FIRST:
```bash
python3 $S/progress.py show work/progress.json
python3 $S/matrix.py status work/rules.json work/results.json
```

## Steps (in order, WITHOUT skipping)
A step you cannot do: `python3 $S/progress.py step work/progress.json <step> skipped --reason "…"`.

**E. Environment** — tell the user which checks cannot run here.
```bash
python3 $S/env_check.py --json work/env.json
```

**0. Classify + identity** — target / reference (note immutable ones) / review; ask if unsure. Match EVERY document name the user used; if one is not a file, ASK (else the note goes to the top of the report).
```bash
python3 $S/extract.py target.pdf ref.pdf [review.docx] [--docx-source target.docx] [--tables] [--reading-order] -o work/ex
python3 $S/section_inventory.py identity --target work/ex/target.txt --files ref.pdf --names "Ek B" "PAR" [--lang tr] -o work/doc_identity.json
```

**1. Reference coverage, then rule register** — classify EVERY section (rule-bearing | fact | open-question | descriptive-only) before writing rules; rules `R-001…`, facts `F-001…`, each with `source.section`, into `work/rules.json`.
```bash
python3 $S/section_inventory.py scan work/ex/ref.txt ["work/ex/target.txt@Appendix B"] -o work/ref_sections.json
python3 $S/section_inventory.py classify work/ref_sections.json work/classes.json
```

**2. Deterministic pass** — read the warnings; judge EVERY parameter conflict.
```bash
python3 $S/id_index.py work/ex/target.txt -o work/id_index.json
python3 $S/xref_check.py work/ex/target.txt --numbers --also-numbers work/ex/ref.txt -o work/xref_report.md
python3 $S/param_check.py scan --target work/ex/target.txt --ref work/ex/ref.txt [--model <model>] [--concepts work/param_concepts.local.json] -o work/params.json
python3 $S/param_check.py verdict work/param_verdicts.json work/param_part.json
```

**3. Traceability** — one result per rule/fact, one by one, in blocks of 20: ✅ ❌ ⚠️ ➖ ❓ with evidence. Search a whole block in ONE call; never one grep per term.
```bash
python3 $S/search.py work/ex/target.txt --rules work/rules.json --all-blocks
python3 $S/search.py work/ex/target.txt -t "term" -t "other term"
python3 $S/matrix.py set-bulk work/results.json work/part_01.json
python3 $S/matrix.py status work/rules.json work/results.json
```

**4. Internal consistency** — references, IDs, values, names, screens vs body → `work/internal.md`.

**5. Visual pass** — read `reference/visual-pass.md`. EVERY inventory page gets a log row; Read tool in batches of up to 20 pages.
```bash
python3 $S/visual_inventory.py scan target.pdf -o work/visual_inventory.json
python3 $S/visual_inventory.py record work/visual_log.json work/visual_part_01.json
```
DOCX target: `python3 $S/docx_to_pdf.py target.docx -o work/docx_pdf` first.

**6. Review documents** (if given) — one verdict per comment, `templates/per_person.md`.

**7. Report** — title lines, then the generated output unchanged ("Coverage summary" first), then your findings (`templates/report.md`).
```bash
python3 $S/matrix.py coverage work/rules.json work/results.json -o work/coverage.md --env work/env.json [--visual work/docx_pdf/visual_status.json]
python3 $S/matrix.py verify work/rules.json work/report.md      # must exit 0
```

**8. Fixes only if the user asks** — then run steps 2–5 again and list regressions separately.

## Process model + regression check
On every run, FIRST read `.rule-check/<document>/process_model.yaml` and `invariants.yaml` if they exist. Before building (A), updating (B) or fixing a document (C), read `reference/process-model.md`.
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
