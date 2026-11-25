# rule-check

A [Claude Code](https://claude.com/claude-code) skill that checks one or more TARGET documents (PDF/DOCX) against the rules in REFERENCE documents in a single, exhaustive pass, and optionally judges reviewers' comments.

The usual failure of "check this document against that rules PDF" is that the model finds a few obvious problems and finds new ones every round. This skill uses a **rule register + traceability matrix + coverage verification**: the job is not finished until every rule has an explicit result with evidence (`matrix.py verify` must pass). It also keeps a **process model** of the document as a persistent file, so that an update of the document can be checked for regressions.

## Features
- Numbered, atomic rule register (`rules.json`) with source document, page and quote
- One result per rule: ✅ compliant · ❌ violation · ⚠️ partial · ➖ not applicable · ❓ cannot verify
- Deterministic scripts: text extraction (PDF, DOCX incl. tracked changes and comments, plain text), ID index, broken/duplicate/skipped cross-references, number+unit consistency; the visual check uses Claude's native PDF page reading
- Environment check (`env_check.py`): which libraries/tools exist and which checks therefore cannot run; the report's "Environment" section states it
- DOCX visual pass: `docx_to_pdf.py` converts a DOCX with headless LibreOffice when available (otherwise reports "⏭️ visual pass skipped")
- Optional cell-level PDF tables (`extract.py --tables`, uses pdfplumber when importable, falls back to layout rows)
- Review-comment evaluation per person (valid / invalid / team decision …)
- Process model + invariants + document diff + impact analysis for regression checks on document updates

## Requirements
- **Docker.** Nothing is installed on the host. All scripts run in the `rule-check:local` image (Debian + Python 3 + PyYAML + pypdf + poppler-utils), which `scripts/run.sh` builds automatically on first use (and rebuilds when `docker/` changes). Containers run with no network, no capabilities and a read-only root filesystem.
- Claude Code (to use it as a skill).

## Installation
Repo root = skill root (`SKILL.md` is at the top level):
```bash
git clone <repo-url> ~/.claude/skills/rule-check      # user-wide
# or per project: <project>/.claude/skills/rule-check
```

## Usage
Ask Claude, for example:

> Use rule-check: `SRS_v3.pdf` is the target, `SRS_Rules.pdf` and `PAR.pdf` are references (PAR is immutable), `review_alice.docx` and `review_bob.docx` are reviews. Check every rule one by one and give me the coverage table and the per-person comment evaluation.

In an environment that already has Python 3 (for example a chat sandbox without Docker) call the scripts directly: `python3 scripts/env_check.py`, `python3 scripts/extract.py …`. Nothing needs to be installed; missing optional libraries only disable the corresponding check.

Scripts can also be run by hand through the wrapper (current directory → `/work`, skill → `/skill`):
```bash
R=./scripts/run.sh
$R python /skill/scripts/extract.py target.pdf -o work/ex
$R python /skill/scripts/xref_check.py work/ex/target.txt --numbers
$R python /skill/scripts/matrix.py verify work/rules.json work/report.md
```

## Contents
| Path | Purpose |
|---|---|
| `SKILL.md` | The workflow (steps 0–8; process model flows A/B/C) |
| `scripts/extract.py` | PDF (poppler) / DOCX (zip+XML) / TXT → text with page/line numbers; DOCX tracked changes + comments; extraction warnings |
| `scripts/id_index.py`, `xref_check.py` | ID index; broken/duplicate/skipped IDs; number+unit consistency |
| `scripts/matrix.py` | rule × target matrix, checkpoints, coverage table, `verify` |
| `scripts/model_check.py` | process model validation, invariant checks, Mermaid output, `bump` |
| `scripts/doc_diff.py`, `impact.py` | section/ID-level diff between versions; impact analysis |
| `scripts/env_check.py`, `docx_to_pdf.py`, `package.py` | environment report; DOCX→PDF via LibreOffice; builds `dist/rule-check.zip` (`make package`) |
| `scripts/id_patterns.json` | configurable ID regexes and units (English + Turkish labels) |
| `templates/`, `reference/` | report / rule register / model schemas; pitfalls and modeling guide |
| `docker/` | Dockerfile (runtime + test targets; Debian packages only) |
| `tests/` | synthetic scenarios, answer keys and scorers (see `tests/README.md`) |

## Tests
`make test` runs the scorers; `make chat-env-test` builds two replicas of a chat sandbox (`docker/chat-env.Dockerfile`, `docker/chat-env-v2.Dockerfile`: pypdf 6.17, pdfplumber, poppler 24.02, LibreOffice) and compares both scenarios across images and engines.
```bash
cd tests
RULE_CHECK_TARGET=test ../scripts/run.sh python /skill/tests/make_fixtures.py fixtures   # only to regenerate fixtures
../scripts/run.sh python /skill/tests/score.py run          # rule-check scenario
../scripts/run.sh python /skill/tests/score_v2.py run2      # process model / regression scenario
```

## Dependencies and licenses
No PyPI packages. The scripts use the Python standard library, PyYAML, pypdf (pure Python) and poppler's `pdftotext`, all from Debian packages inside the Docker image (details and licenses: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)). poppler is GPL but is only run as a separate process. Two independent PDF engines are available (`extract.py --engine pdftotext|pypdf`, default pdftotext); each one cross-checks the other and `extract.py` warns when they disagree. If you run it on your own PDFs and never see such a warning, pypdf alone is enough and poppler can be dropped from `docker/Dockerfile`.

## License
[MIT](LICENSE)
