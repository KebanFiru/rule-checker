---
name: rule-check
description: Check one or more target documents (PDF/DOCX) against the rules in reference documents, and optionally judge reviewer comments, in a single exhaustive pass: builds a numbered rule register, checks every rule individually with evidence, runs cross-reference and consistency scripts, inspects page images, and outputs a coverage table plus per-person findings. Also keeps a process model of the document as a persistent file and uses it to catch regressions when the document is updated. Use when asked to compare a document to a rules/requirements PDF, find violations, evaluate review comments, or check that a document update did not break anything.
---

# rule-check

Goal: check TARGET documents against the rules in REFERENCE documents in ONE pass, exhaustively. This fixes the "finds a few obvious problems, finds new ones every round" failure mode with a **rule register + traceability matrix + coverage verification**: the work is not finished until every rule has an explicit result. "Finished" means `matrix.py verify` passes.

## Running: two modes (never install anything on the host)
The scripts need only Python 3, PyYAML, pypdf and/or poppler's `pdftotext` (all optional ones degrade gracefully, see step E).
- **Docker available** (a developer machine): run everything through the wrapper; it builds the image `rule-check:local` on first use, runs with no network and a read-only filesystem. `cd` into the directory that holds the documents (mounted as `/work`; the skill as `/skill`):
  ```bash
  R=<skill-dir>/scripts/run.sh    # the directory this skill is installed in (the repo root)
  $R python3 /skill/scripts/extract.py target.pdf ref.pdf -o work/ex
  ```
- **No Docker** (e.g. a chat sandbox that already has Python): call the scripts directly: `python3 <skill-dir>/scripts/extract.py …`. Replace `$R python3 /skill/scripts/` by `python3 <skill-dir>/scripts/` in every command below.

Do not `pip install` anything on the host or in the sandbox; if a library is missing, `env_check.py` tells you which checks are then unavailable and the workflow continues without them. Use `python3`, never `python`.

## Workflow (in order, WITHOUT skipping)

**E. Environment check** (always first, one command):
```bash
$R python3 /skill/scripts/env_check.py --json work/env.json     # or: python3 <skill-dir>/scripts/env_check.py --json work/env.json
```
It reports the Python, pypdf, pdfplumber, PyYAML, `pdftotext` and LibreOffice (`soffice`) versions and lists the checks that CANNOT be done here (no second PDF engine, no cell-level tables, no DOCX visual pass, no process model). Tell the user up front which checks will be skipped, and pass `--env work/env.json` to `matrix.py coverage` (step 7) so the report's "Environment" section states it.

**0. Classify the documents**: target / reference / review. If unsure, ask the user; if the user is unavailable, write your guess at the top of the report. Identify which documents are IMMUTABLE (e.g. a Project Report) and use them as reference only. Create a working folder `work/`; intermediate files live there.

**1. RULE REGISTER**: Run `extract.py` on the references and READ them page by page (all of it). Split every checkable statement into an atomic rule (if one sentence has two conditions joined by "and", make two rules) and number them `R-001…`. Per rule: source document + page + short quote (original language), type (required content / prohibition / format / numeric value / process order / terminology / template section), scope (which parts of the target it applies to), optional `keywords`. Put interpretation in a separate field (`interpretation`), never mixed into the rule itself. If the same rule is worded differently in two places, register both. Output: `work/rules.json` + `work/rule_register.md` (see `templates/rule_register.md`). Never invent a rule or value that has no source; what the reference does not answer becomes "TBD / team decision". Mark your own assumptions with "ASSUMPTION:".

**2. Deterministic pass** (take the results as they are):
```bash
$R python3 /skill/scripts/extract.py target.pdf [ref.pdf …] [--docx-source target.docx] -o work/ex
$R python3 /skill/scripts/id_index.py work/ex/target.txt -o work/id_index.json
$R python3 /skill/scripts/xref_check.py work/ex/target.txt --numbers -o work/xref_report.md
```
Cell-level tables: add `--tables` to `extract.py` (pdfplumber cells as `p<page>:T<table>R<row>C<col>` in `<stem>.tables.txt`/`.json`; without pdfplumber it falls back to the `-layout` rows and says so). Multi-column PDFs: add `--reading-order` (default `-layout` interleaves columns).
To catch numeric rules, add the reference values to the inventory with `xref_check.py … --also-numbers work/ex/ref.txt` (compare differing values for the same unit by hand).
Read the `extract.py` warnings (PDF text comes from two independent engines, pdftotext and pypdf; `--engine` picks the primary one): if the two engines disagree, merged words are reported, or a page has no text layer, these may be extraction artifacts → do not report them as document errors. Verify against the DOCX source or by reading that PDF page natively with the Read tool (`pages` parameter); Claude's own reading of the page is the final arbiter for doubtful text. ID patterns live in `scripts/id_patterns.json`; adapt them to the document's ID style (`--patterns`). xref findings are heuristic: verify each one in the document.

**3. TRACEABILITY**:
```bash
$R python3 /skill/scripts/matrix.py skeleton work/rules.json work/ex/target.txt -o work/matrix
```
Then process the rules ONE BY ONE (never in groups); for each, read the whole rule and the relevant part of the target side by side and give ONE result:
✅ Compliant (evidence: page/ID in target) | ❌ Violation | ⚠️ Partial | ➖ Not applicable (reason) | ❓ Cannot verify (what is missing)

Work in **blocks of 20** rules. After each block write the part as JSON and record it (checkpoint; work can resume even if the context fills up):
```json
{"R-001":{"result":"✅","evidence":"p4 UC-2.1 heading present"},
 "R-002":{"result":"❌","evidence":"…","target_loc":"p7 UC-3.8","issue":"…","fix":"…","severity":"high"}}
```
```bash
$R python3 /skill/scripts/matrix.py set-bulk work/results.json work/part_01.json
$R python3 /skill/scripts/matrix.py status work/rules.json work/results.json   # where you are
```
When resuming (new session/context) run `status` first and continue with the remaining rules. Empty `evidence` is rejected. For "absence" violations write where you looked. The candidate list (skeleton) is only a hint; even with no candidate, search the target for the rule.

**4. Internal consistency pass** (outside the rules but mandatory): broken references, undefined/duplicate IDs and numbering gaps from xref_check; the same value appearing differently in different places (durations, amounts, codes, ECTS, dates); the same concept under different names; text inside screens/figures vs body text. Write findings to `work/internal.md`.

**5. Visual pass** (no script: Claude reads the pages itself): open the PDF pages that contain screenshots, tables or figures with the **Read tool and its `pages` parameter** (e.g. `pages: "2"` or `"3-5"`; max 20 pages per call) and LOOK at them: text, dates, codes and amounts inside images are not in the text layer. Which pages? Every page with an embedded image or figure (spot them in the text output: "Figure N" / "Screen" captions, or pages whose text is very short), every page with a table, and every page `extract.py` warned about (no text layer). Compare what you see with the body and the rules. Read table rows that split across a page break as one table. If the target is a DOCX, convert it first: `$R python3 /skill/scripts/docx_to_pdf.py target.docx -o work/docx_pdf` (headless LibreOffice, 60 s limit; works without network and with a read-only filesystem), then read the pages of `work/docx_pdf/<name>.pdf` with the Read tool. The script prints either `Visual pass: DOCX→PDF (LibreOffice …)` or `⏭️ visual pass skipped (<reason>)` (no LibreOffice, timeout …) and never fails the run: if it is skipped, ask the user for a PDF export, or continue without the visual pass. Pass `--visual work/docx_pdf/visual_status.json` to `matrix.py coverage` so the report states which of the two happened.

**6. Review documents** (if given; `extract.py` puts comments + tracked changes in the DOCX json): make EACH comment its own item (person + comment no.). Give one value per item: Valid (per which rule/evidence) | Partially valid | Invalid (why) | Team decision needed (options) | Already fixed | Requires touching an immutable document. If different people give conflicting suggestions on the same topic, merge them and propose a middle path but DO NOT decide; ask.

**7. Report**:
```bash
$R python3 /skill/scripts/matrix.py coverage work/rules.json work/results.json -o work/coverage.md --env work/env.json [--visual work/docx_pdf/visual_status.json]
```
Build `work/report.md` using `templates/report.md`: summary counts; violations table (#, rule ID, source document+page, target location page+ID, issue, suggested fix, severity); **COVERAGE TABLE (EVERY rule one row)**; cross-reference/internal-consistency findings; visual findings; extraction warnings; TBDs. If reviews were given, also output `templates/per_person.md` format: person heading + numbered items, nothing else.
**Completion condition:**
```bash
$R python3 /skill/scripts/matrix.py verify work/rules.json work/report.md   # must exit 0
```
If it fails, the job is not finished; fill the gaps.

**8. Fixes only if the user asks.** If asked: (with a process model, run step C first) fix → regenerate the document → run steps 2–5 AGAIN → list regressions (previously ✅, now ❌) separately.

## Process model + regression check (persistent memory)
The processes in a document (steps, actors, order, conditions, durations, exceptions) are turned into a compact model stored as a FILE. When the document is updated, the changes are checked against this model so that an update cannot break something that was previously correct. **On every run, FIRST read the model and the invariants** (so detail is not lost from the context of a long document). Guide: `reference/modeling-guide.md`; schemas: `templates/process_model.schema.yaml`, `templates/invariants.schema.yaml`.

The model lives next to the document (in the working folder):
```
.rule-check/<document-name>/ process_model.yaml (single source of truth) · process_model.mmd (auto-generated, do not edit) · invariants.yaml · rules.json · changelog.md
```
Rules: `source` is REQUIRED on every node/parameter, unsourced information never enters the model; interpretation/assumption is marked `assumption: true`; keep the model short but never drop a value/condition/exception. Invariants or rules are never deleted/changed without user approval: report them as a "proposed change".

### A. FIRST RUN (no `.rule-check/<document>/process_model.yaml` yet)
1. After the rule register (step 1), extract the process model → `$R python3 /skill/scripts/model_check.py check .rule-check/<document>/process_model.yaml --rules .rule-check/<document>/rules.json` (the same call generates the `.mmd`) → fix the errors; repeat until there are 0 errors.
2. Coverage check: is every process section/UC/screen of the document linked to at least one node? List the ones that are not.
3. Derive the invariants (`invariants.yaml`) and verify them: `$R python3 /skill/scripts/model_check.py invariants <model> <invariants> --doc work/ex/document.txt`. Show the user a summary: how many processes, nodes, parameters, invariants.
4. If the document already contradicts the model (e.g. two different durations in two places), make that a finding of the first report (model_check reports "same parameter, different value").
5. Write the v1 entry in `changelog.md`.

### B. UPDATE RUN (model exists; read the model + invariants first)
1. `$R python3 /skill/scripts/doc_diff.py old.pdf new.pdf -o work/diff.json` (PDF/DOCX; line breaks/hyphens/footers are listed separately as noise).
2. `$R python3 /skill/scripts/impact.py --model <model> --diff work/diff.json --rules <rules.json> --invariants <invariants.yaml> -o work/impact` → affected nodes, neighbours, nodes using the same parameter, rules, invariants; changes with no counterpart in the model (🆕/❓). **Run it BEFORE updating the model.**
3. Check every affected item in the new document one by one; also re-verify ALL invariants (not only the affected ones): `model_check.py invariants … --doc work/ex/new.txt -o work/inv.json`.
4. Classify: ✅ expected change | ❌ regression (was correct, now broken) | ⚠️ unpropagated change (changed in one place, still old in linked places) | 🆕 new process/step (not in the model) | ❓ model needs updating.
5. Report: regressions and unpropagated changes FIRST, then the rest.
6. Model update: apply only ✅/🆕 changes to the model (❌/⚠️ are not written to the model until the user decides; record them in `tbd`); run `model_check.py check` again; then `$R python3 /skill/scripts/model_check.py bump <model> --nodes SP-1.5,SP-2.2 --doc-version "Rev 2" --reason "<finding/review no.>"` (increments the version and writes version/date/nodes/reason to `changelog.md`). Rule and invariant changes need user approval.

### C. When I (Claude) make a fix in the document
BEFORE the fix, list the impact with `impact.py --keys SP-1.5,SP-2.3 …` (which nodes/parameters/rules/invariants are affected); AFTER the fix, run the B steps (doc_diff → impact → all invariants → classification → report) for my own change and list regressions separately.

## Rules
- Never invent a rule/value with no source; what the reference does not answer = "TBD / team decision".
- Mark your own assumptions as "assumption".
- Do not propose a change that would make something look done that nobody did (e.g. "show it as if it had been done in Figma").
- Write the report in the user's language; quotes from documents stay in their original language.
- Flag separately any proposal that requires touching an immutable document.
- Read `reference/pitfalls.md` before starting.
