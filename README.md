# rule-check

A [Claude Code](https://claude.com/claude-code) skill that checks one or more **target documents** (PDF/DOCX) against the rules in **reference documents**, **exhaustively and in a single pass**, and optionally judges reviewers' comments. It can also keep a **process model** of a document and use it to catch regressions when the document is updated.

## Why

Asked to "check this document against that rules PDF", a model tends to find a few obvious problems and then finds new ones in every following round. `rule-check` removes that failure mode with three mechanisms:

1. **Rule register** – every checkable statement of the references becomes a numbered, atomic rule (`R-001…`) with source document, page and quote.
2. **Traceability + one result per rule** – each rule is checked on its own and gets exactly one result with evidence: ✅ compliant · ❌ violation · ⚠️ partial · ➖ not applicable · ❓ cannot verify · ⚖️ reference contradiction / team decision.
3. **Coverage verification** – `matrix.py verify` fails unless the report's coverage table has exactly one filled row per rule. The job is not finished until it passes.

**Nothing is skipped silently.** The report starts with a coverage summary, and `verify` fails if

- a page with a screenshot, diagram or table was neither looked at nor skipped with a stated reason,
- a section of a reference was not classified (rules, facts to check, open question, or descriptive with a reason),
- a conflicting duration or amount was left without a verdict,
- a document you named was replaced by a section of the target without saying so,
- a "section X is missing" finding hides the single missing items, or an absent open question is marked "not applicable",
- evidence points to a rule or decision that does not exist, a ❌ needs no change, or a contradiction inside the target is not written on the rules it concerns,
- the final self-audit (every finding and 10% of the compliant rows, re-read against the source) is unfinished.

On top of that, deterministic scripts do what a model should not do by eye (text extraction with page/line numbers, cross-reference and ID checks, number/unit consistency, document diffs), and the model looks at page images for what text extraction cannot see (screenshots, figures).

## Install

The repository root is the skill root (`SKILL.md` is at the top level).

```bash
# user-wide
git clone https://github.com/KebanFiru/rule-checker.git ~/.claude/skills/rule-check
# or per project
git clone https://github.com/KebanFiru/rule-checker.git <project>/.claude/skills/rule-check
```

Or download `rule-check.zip` from a [release](../../releases) and unzip it into a `skills` directory (the archive contains a top-level `rule-check/` folder; it ships only the skill, no tests or development tooling).

### Requirements

Only **Python 3** (standard library). Everything else is optional and the skill degrades gracefully; `scripts/env_check.py` reports what is available and which checks cannot be done:

| Optional piece | Enables | Without it |
|---|---|---|
| `pdftotext` (poppler) and/or `pypdf` | PDF text; with both, an independent cross-check of the extraction | no PDF text from scripts (read pages with the Read tool); with only one, no cross-check |
| PyYAML | process model, invariants, impact analysis | those features are unavailable |
| pdfplumber | cell-level PDF tables (`extract.py --tables`) | table rows are rebuilt from the layout text (reported as such) |
| LibreOffice (`soffice`) | DOCX → PDF for the visual pass | "⏭️ visual pass skipped (reason)"; ask for a PDF export |

Nothing is ever installed by the skill. DOCX, TXT/MD/CSV need no extra software.

## Use

Ask Claude in natural language, for example:

> Use rule-check: `SRS_v3.pdf` is the target, `SRS_Rules.pdf` and `PAR.pdf` are references (PAR must not be changed), `review_alice.docx` and `review_bob.docx` are reviews. Check every rule one by one and give me the coverage table and the per-person comment evaluation.

> Use rule-check to compare `SRS_v4.pdf` with the process model of `SRS_v3`: tell me what was expected, what regressed and what was not propagated.

The report is written in your language; quotes from documents stay in their original language.

## What you get

- a **coverage summary** at the top: rules, facts, reference sections, visual pages, parameter conflicts, skipped checks with reasons
- `rules.json` / `rule_register.md` – the rule register (rules and facts)
- a **violations table** (rule, source, location in the target, issue, suggested fix, severity)
- a **coverage table**: one row per rule with result and evidence, checked by `verify`
- cross-reference / internal-consistency findings, visual-pass findings, extraction warnings, an *Environment* section
- per-person comment evaluations (valid / partially valid / invalid / team decision / already fixed / touches an immutable document)
- optionally a persistent process model (`.rule-check/<document>/`) and an update report (✅ expected · ❌ regression · ⚠️ unpropagated · 🆕 new · ❓ model needs updating)

## Scripts

All are standard-library Python; run them as `python3 scripts/<name>.py …` (see `SKILL.md` for the full workflow).

| Script | Purpose |
|---|---|
| `env_check.py` | versions of the optional libraries/tools; lists the checks that cannot run here |
| `extract.py` | PDF (pdftotext and/or pypdf) / DOCX (zip + XML) / TXT → text with page/line numbers; DOCX comments and tracked changes with authors; second-opinion cross-check, normalization and repair of extraction artifacts; `--tables`, `--engine`, `--reading-order` |
| `docx_to_pdf.py` | DOCX → PDF with headless LibreOffice (60 s limit, never fails the run) for the visual pass |
| `id_index.py`, `xref_check.py` | ID definitions vs references; undefined, duplicate and skipped IDs; same ID with different titles; number+unit inventory |
| `matrix.py`, `gates.py` | rule × target candidate matrix, checkpoints in blocks of 20, coverage summary and table, `verify` |
| `visual_inventory.py` | which pages need the visual pass (images, drawings, captions), Read batches, per-page log |
| `section_inventory.py` | reference section structure and classification; matches the documents the user named to files |
| `param_check.py`, `param_concepts.json` | number+unit values (English and Turkish) per concept; conflicts with the references and the process model |
| `search.py` | many terms, or the candidates of 20 rules, in one call |
| `judgement.py` | checks on the verdicts themselves, self-audit selection (used by `matrix.py`) |
| `progress.py` | `work/progress.json`, to resume long runs |
| `model_check.py` | process-model validation, invariant checks (model and document), Mermaid output, version `bump` |
| `doc_diff.py`, `impact.py` | section/ID-level diff between two versions (format noise separated); impact of changes on model nodes, parameters, rules and invariants |
| `id_patterns.json` | configurable ID regexes and units (English and Turkish labels) |

`templates/` holds the report, rule-register, per-person and model schemas; `reference/steps/` holds one detail file per workflow step (each at most 4 KB, read only when the step starts); `reference/` also holds `modeling-guide.md` and `pitfalls.md` (extraction and review traps).

## Process model and regression check

The processes of a document (steps, actors, order, conditions, durations, exceptions) are stored as `process_model.yaml` next to the document, together with `invariants.yaml` (facts that must not break), `rules.json` and a `changelog.md`. When the document is updated, `doc_diff.py` → `impact.py` → `model_check.py invariants` classify every change, and the model is updated only for expected changes and new steps; regressions and unpropagated changes wait for a decision. Schemas: `templates/process_model.schema.yaml`, `templates/invariants.schema.yaml`.

## Limitations

- Scanned (image-only) PDF pages have no text layer; the scripts warn and the pages must be read with the Read tool. There is no OCR.
- Table detection is layout-based unless pdfplumber is available.
- On multi-column pages the default layout mode interleaves columns; use `extract.py --reading-order`.
- The visual pass depends on Claude reading page images; for DOCX it needs LibreOffice or a PDF export. `verify` checks that every inventory page has a log row, not that the model looked carefully.
- Evidence-fit, aggregate wording and "which rules does this contradiction concern" are heuristics that only warn; an aggregate written without its member list can go unnoticed.
- Visual inventory, section detection and parameter binding are heuristics: images need pypdf, headings must look like headings, and spelled-out numbers are recognised only up to twelve.
- Heuristics (ID definition vs reference, number/unit concepts) can produce false positives; `SKILL.md` requires verifying each finding in the document.
- Verified on synthetic documents only; check it on your own PDFs before relying on it (an extraction disagreement shows up as a warning).

## Development

Using the skill needs no Docker. Development is done in Docker so nothing is installed on the host.

```
SKILL.md  scripts/  templates/  reference/  LICENSE  THIRD_PARTY_NOTICES.md   ← the skill (what the release zip ships)
dev/        run.sh (Docker wrapper) · package.py · docker/ (images)             ← development tooling
tests/      fixtures, scenarios, scorers, environment-comparison tests
.github/    CI workflow and Dependabot
Makefile    make test · make chat-env-test · make package
```

| Command | What it does |
|---|---|
| `make test` | all scenarios end to end in the regular image (self-contained; works on a fresh clone) |
| `make chat-env-test` | builds two replicas of a chat sandbox (`dev/docker/chat-env*.Dockerfile`; the newer one has pypdf 6.17, pdfplumber, poppler 24.02, LibreOffice and the sandbox's fonts), runs all scenarios with both PDF engines in each, and prints a classified comparison |
| `make package` | builds `dist/rule-check.zip` (explicit include list; no tests, no `dev/`) |
| `dev/run.sh <cmd>` | runs any command in the Docker image: no network, read-only root filesystem, dropped capabilities |

See [`tests/README.md`](tests/README.md) for the scenarios, the answer keys and the honesty notes (the rule-violation score is contaminated when one session writes the key and runs the scenario; the deterministic parts are independent measurements).

### CI and releases

`.github/workflows/ci.yml`: `make test` on every push and pull request; `make chat-env-test` on `main`, tags, weekly and on demand; on a `v*` tag it builds the zip, checks that no development tooling leaked into it and attaches it to a GitHub Release. Actions are pinned by commit SHA and Dependabot keeps them and the Docker base images current. To release: `git tag v1.0.0 && git push origin v1.0.0`.

## Dependencies and licenses

No PyPI packages are used by the skill. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the optional components (pypdf, pdfplumber, PyYAML, poppler, LibreOffice) and their licenses.

## License

[MIT](LICENSE)
