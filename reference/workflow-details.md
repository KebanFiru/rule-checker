# Workflow details

Read the section of the step you are on, once. `SKILL.md` holds the steps and commands; this file explains them. Visual pass: `visual-pass.md`. Process model: `process-model.md`.

Basic principle: **nothing is skipped silently.** Whatever is skipped appears in the report with a count and a reason, and `matrix.py verify` checks it. Goal: check TARGET documents against the rules in REFERENCE documents in ONE pass, exhaustively. This fixes the "finds a few obvious problems, finds new ones every round" failure mode with a **rule register + traceability matrix + coverage verification**: the work is not finished until every rule has an explicit result. "Finished" means `matrix.py verify` passes.

## Running
The scripts are plain Python 3 (standard library only) and run directly: `python3 <skill-dir>/scripts/<script>.py …`, where `<skill-dir>` is the directory that contains SKILL.md. Optional pieces degrade gracefully (step E reports what is missing): PyYAML (process model), pypdf and/or poppler's `pdftotext` (PDF text), pdfplumber (cell-level tables), LibreOffice (DOCX visual pass). Never `pip install` anything on the host or in the sandbox, and use `python3`, never `python`. (Developers of this repository run everything in Docker through `dev/run.sh`; that is not needed to use the skill.)

## Resuming and `work/progress.json`
`matrix.py set-bulk`, `visual_inventory.py record`, `section_inventory.py classify` and `param_check.py verdict` record their checkpoints in `work/progress.json`. Record the other steps yourself: `progress.py step work/progress.json <step> done`. A step you deliberately do not do: `… <step> skipped --reason "…"` (counted in the report). After a context summary or in a new session run `progress.py show work/progress.json` and `matrix.py status` FIRST, then continue where they stop.

## E. Environment check
It reports the Python, pypdf, pdfplumber, PyYAML, `pdftotext` and LibreOffice (`soffice`) versions and lists the checks that CANNOT be done here (no second PDF engine, no cell-level tables, no DOCX visual pass, no process model). Tell the user up front which checks will be skipped, and pass `--env work/env.json` to `matrix.py coverage` so the report's "Environment" section states it.

## 0. Classify the documents and settle their identity
Classify each file: target / reference / review. If unsure, ask the user; if the user is unavailable, write your guess at the top of the report. Identify which documents are IMMUTABLE (e.g. a Project Report) and use them as reference only. Create a working folder `work/`; intermediate files live there.

**Document identity.** Run `section_inventory.py identity` with EVERY document name the user used ("Ek B", "PAR", "charter"), after `extract.py` has produced the target text. Possible outcomes:
- `file`: matched to an uploaded file (correct a wrong or ambiguous match with `--map "name=file"`). If it is the target itself, that is a circular check.
- `internal-section`: no such file, but the target has a section of that name. Never treat this as the same thing silently. ASK the user whether a separate document exists. If the user is unavailable, the note ("«Ek B» was not provided as a separate file; the section «Appendix B» of the target was used") stays at the top of the report; use `--lang tr` for a Turkish report; record an answer with `--confirmed "name=answer"`. Add the section to the section inventory (`scan … "work/ex/target.txt@Appendix B"`). Rules taken from it keep their normal result (do not turn them into ❓): the report marks them `⚑ source assumption` and lists them as a circular check (the target verifies itself).
- `missing`: neither. Ask; otherwise it is counted as a skipped check.

## 1. Reference coverage and the rule register
First `section_inventory.py scan` on all references, then READ the references page by page (all of it) and classify EVERY section BEFORE writing rules (`section_inventory.py classify work/ref_sections.json classes.json`):

| class | typical content | what to do |
|---|---|---|
| `rule-bearing` | functional requirements, constraints, TO-BE functions, table values | EVERY checkable statement becomes an atomic rule; every item of a TO-BE list is its own rule |
| `fact` | AS-IS description, interview notes | not a rule, but a fact `F-001…` to check in the target: does anything there contradict it (an AS-IS duration, fee, actor responsibility, system name)? Same result symbols as rules |
| `open-question` | undecided points | one-line reason; list under TBD |
| `descriptive-only` | motivation, introduction | one-line reason; the report warns if such a section contains numbers, durations or "shall/must/zorunlu/gerekir": re-read those |

The script's heading detection is heuristic: check its list against the table of contents. If it merged sections, read the merged section as a whole and give it the strictest class that applies (rule-bearing before fact); if a section needs both rules and facts, class it rule-bearing and add the facts too.

Split every checkable statement into an atomic rule (if one sentence has two conditions joined by "and", make two rules) and number them `R-001…`. Per rule: source document + page + **section id** (`source.section`) + short quote (original language), type (required content / prohibition / format / numeric value / process order / terminology / template section), scope (which parts of the target it applies to), optional `keywords`. Facts additionally carry `"kind": "fact"`. Put interpretation in a separate field (`interpretation`), never mixed into the rule itself. If the same rule is worded differently in two places, register both. Output: `work/rules.json` + `work/rule_register.md` (see `templates/rule_register.md`). Never invent a rule or value that has no source; what the reference does not answer becomes "TBD / team decision". Mark your own assumptions with "ASSUMPTION:".

## 2. Deterministic pass (take the results as they are)
Cell-level tables: add `--tables` to `extract.py` (pdfplumber cells as `p<page>:T<table>R<row>C<col>` in `<stem>.tables.txt`/`.json`; without pdfplumber it falls back to the `-layout` rows and says so). Multi-column PDFs: add `--reading-order` (default `-layout` interleaves columns).
To catch numeric rules, add the reference values to the inventory with `xref_check.py … --also-numbers work/ex/ref.txt`.
Read the `extract.py` warnings (PDF text comes from two independent engines, pdftotext and pypdf; `--engine` picks the primary one): if the two engines disagree, merged words are reported, or a page has no text layer, these may be extraction artifacts → do not report them as document errors. Verify against the DOCX source or by reading that PDF page natively with the Read tool (`pages` parameter); Claude's own reading of the page is the final arbiter for doubtful text. ID patterns live in `scripts/id_patterns.json`; adapt them to the document's ID style (`--patterns`). xref findings are heuristic: verify each one in the document.

**Parameters.** `param_check.py scan` extracts number+unit values (days, business days, weeks, months, hours, ECTS, €, %, MB …; English and Turkish), binds each to a concept and reports conflicts: different values for one concept inside the target, a target value that differs from the reference (violation candidate), and differences from the process model (`--model`). Read `work/params.md` including "Values without a concept". On the first run add document-specific concepts to `work/param_concepts.local.json` (`{"concepts": {"learning-agreement": ["learning agreement", "öğrenim anlaşması"]}}`) and re-run with `--concepts`. EVERY conflict is a candidate for the internal-consistency findings: open the places it lists and record `real | false-positive | legitimate-difference | tbd` with a note (`param_check.py verdict`). Do not check durations by hand instead of running the script; do check what the script cannot see (spelled-out numbers above twelve, values inside images).

## 3. Traceability
Process the rules ONE BY ONE (never in groups); for each, read the whole rule and the relevant part of the target side by side and give ONE result:
✅ Compliant (evidence: page/ID in target) | ❌ Violation | ⚠️ Partial | ➖ Not applicable (reason) | ❓ Cannot verify (what is missing)

Work in **blocks of 20** rules. Get the candidates of a whole block with one command (`search.py … --rules work/rules.json --block N`, or `--all-blocks` once) and read `work/candidates_part_NN.md`; collect further search terms and run them in ONE `search.py -t … -t …` call instead of one grep per term. After each block write the part as JSON and record it (checkpoint; work can resume even if the context fills up):
```json
{"R-001":{"result":"✅","evidence":"p4 UC-2.1 heading present"},
 "R-002":{"result":"❌","evidence":"…","target_loc":"p7 UC-3.8","issue":"…","fix":"…","severity":"high"}}
```
When resuming (new session/context) run `status` first and continue with the remaining rules. Empty `evidence` is rejected. For "absence" violations write where you looked. `matrix.py skeleton work/rules.json work/ex/target.txt -o work/matrix` gives the same hints as one CSV/MD matrix for all rules. The candidate list (skeleton / search.py) is only a hint; even with no candidate, search the target for the rule.

## 4. Internal consistency pass (outside the rules but mandatory)
Broken references, undefined/duplicate IDs and numbering gaps from xref_check; the same value appearing differently in different places (durations, amounts, codes, ECTS, dates; start from the judged parameter conflicts); the same concept under different names; text inside screens/figures vs body text. Write findings to `work/internal.md`.

## 6. Review documents (if given; `extract.py` puts comments + tracked changes in the DOCX json)
Make EACH comment its own item (person + comment no.). Give one value per item: Valid (per which rule/evidence) | Partially valid | Invalid (why) | Team decision needed (options) | Already fixed | Requires touching an immutable document. If different people give conflicting suggestions on the same topic, merge them and propose a middle path but DO NOT decide; ask.

## 7. Report
`matrix.py coverage` generates, in this order: **Coverage summary** (rules, facts, reference sections classified, visual pages, parameter conflicts, document identity, skipped checks with reason and count), summary counts, visual status, Environment, Reference coverage, Visual coverage, Parameter conflicts, Coverage table, Violations. It discovers the gate files in the folder of `rules.json` (`--work` to change). Build `work/report.md` from `templates/report.md`: title lines, then the generated output **unchanged** (the "Coverage summary" must be the first `##` section; regenerate and paste again after any change), then cross-reference/internal-consistency findings, visual findings, extraction warnings, TBDs. The violations table has #, rule ID, source document+page, target location page+ID, issue, suggested fix and severity; the coverage table has EVERY rule and fact as one row. If reviews were given, also output `templates/per_person.md` format: person heading + numbered items, nothing else.
**Completion condition:** `matrix.py verify work/rules.json work/report.md` must exit 0. It fails on: a summary that was left out (also when none of the new steps ran: they show as NOT RUN); a rule or fact without a result row; an inventory page neither checked nor skipped with a reason; an unclassified section, or one whose class has no matching rule/fact/reason; a parameter conflict without a verdict; a missing identity note or `⚑ source assumption` mark; a summary that is missing, not first, or stale. If it fails, the job is not finished; fill the gaps. Never edit the gate files just to make it pass: a check you did not do is a skip with a reason.

## 8. Fixes only if the user asks
If asked: (with a process model, run step C first) fix → regenerate the document → run steps 2–5 AGAIN (re-scan the inventories) → list regressions (previously ✅, now ❌) separately.
