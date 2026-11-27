# Test scenarios

Everything runs inside Docker via `dev/run.sh`. Run from the `tests/` directory. Fixture generation needs the
*test* image (adds Pillow and ReportLab from Debian packages): `RULE_CHECK_TARGET=test`. The DOCX fixtures are written by
`tests/docx_mini.py` (standard library only).

## 1. Rule-check scenario (`run/`)
```bash
cd tests; R=../dev/run.sh
RULE_CHECK_TARGET=test $R python /skill/tests/make_fixtures.py fixtures    # rules.pdf (25 rules), target_srs.pdf, review.docx, expected.json
$R python /skill/scripts/extract.py fixtures/target_srs.pdf fixtures/rules.pdf fixtures/review.docx --docx-source fixtures/review.docx -o run/ex
$R python /skill/tests/build_rules.py run/ex/rules.txt run/rules.json rules.pdf
# … workflow in SKILL.md …  then:
$R python /skill/tests/score.py run
```
The target has 12 deliberate rule violations, 3 broken cross-references and 2 screenshot/body mismatches; the review DOCX has
8 comments from 2 people (some valid, some not) and 2 tracked changes. `run/` holds the output of one sample run
(`rules.json`, `results.json`, `report.md`, `per_person.md`, …).

## 1c. Nothing skipped silently (`run3/`, `fixtures/coverage/`)
A 14-page target with 6 screens (the screens on pages 11 and 13 contradict the body), a vector-only data model, a reminder period
stated three times with one deviation, an AS-IS reference paragraph with "must" and a fact conflict, and a prompt naming "Ek B"
that exists only as the target's own Appendix B. `score_coverage.py` also runs negative checks: `verify` must reject unopened pages,
unclassified sections, missing verdicts, a removed identity note and stale summaries; it also unit-checks number/unit and caption
recognition (English and Turkish), the process-model comparison and the counting of an incomplete inventory.
The judgement checks are exercised the same way: two required contact details the target lacks (aggregate row R-007 with members),
a payment term the reference states twice (⚖️), an absent open-question fact (F-003), evidence moved to the wrong row, broken
references, the fix wordings that forbid ❌, unbound contradictions and the self-audit. R-003 and F-001 in `run3/` were reworded or
reclassified (F-001 is now ⚖️) to satisfy the new verdict rules. `audit_part.json` in `run/` and `run3/` are model-written notes. Regenerate fixtures with
`RULE_CHECK_TARGET=test ../dev/run.sh python /skill/tests/make_fixtures_coverage.py fixtures/coverage`. The visual findings,
classifications and results in `run3/` are model judgements by the session that wrote the key (contaminated); no blind run yet.

## 2. Process model / regression scenario (`run2/`, `fixtures/process/`)
```bash
cd tests; R=../dev/run.sh
RULE_CHECK_TARGET=test $R python /skill/tests/make_fixtures_process.py     # process_v1/v2.pdf|docx + expected_v2.json
$R python /skill/scripts/extract.py fixtures/process/process_v1.pdf fixtures/process/process_v2.pdf -o run2/ex
# starting model: fixtures/process/model_v1/ (process_model.yaml, invariants.yaml, rules.json)
M=fixtures/process/model_v1
$R python /skill/scripts/doc_diff.py fixtures/process/process_v1.pdf fixtures/process/process_v2.pdf -o run2/diff.json
$R python /skill/scripts/impact.py --model $M/process_model.yaml --diff run2/diff.json --rules $M/rules.json --invariants $M/invariants.yaml -o run2/impact
$R python /skill/scripts/model_check.py invariants $M/process_model.yaml $M/invariants.yaml --doc run2/ex/process_v2.txt -o run2/inv_v2.json
$R python /skill/tests/score_v2.py run2
```
Changes embedded in v2: 1 expected (SP-2.2 ✅), 1 unpropagated duration (SP-1.5 3→5 days, SP-2.3 still 3 days ⚠️), 1 broken order
(SP-1.4 before SP-1.3 ❌), 1 new step (SP-1.6 🆕), 1 pure line-wrap change (SP-1.2, noise).

## Honesty note
The rule-violation catch rate is contaminated: the model that wrote the answer key also ran the scenario. The deterministic
parts (xref, DOCX comment/tracked-change extraction, coverage verification, diff, impact, invariants) are independent
measurements; `classification.json` and `results.json` are the model's own judgements. For a blind test, give a fresh
session only `fixtures/*.pdf|docx` and run the skill.

## 3. Chat-environment replicas (no Docker wrapper inside)
`bash tests/chat_env_test.sh` (or `make chat-env-test`) builds two images and runs all scenarios in each, once per primary PDF engine
(`pdftotext`, `pypdf`), by calling `python3 scripts/x.py` directly (`tests/run_deterministic.sh`; no `dev/run.sh`, no `python` alias):

| image | Python | pypdf | PyYAML | pdfplumber | poppler | LibreOffice |
|---|---|---|---|---|---|---|
| `chat-env` (`dev/docker/chat-env.Dockerfile`, Debian 13) | 3.13.5 | 5.4.0 | 6.0.2 | – | 25.03.0 | – |
| `chat-env-v2` (`dev/docker/chat-env-v2.Dockerfile`, Ubuntu 24.04 + uv) | 3.13.18 | 6.17.0 | 6.0.3 | 0.11.10 | 24.02.0 | 24.2.7.2 |

`tests/compare_runs.py` classifies every output file: identical, expected environment difference (DOCX visual pass, `--tables`,
environment report, engine metadata), (a) text-extraction-only, (b) finding/verdict difference, (c) script error, and counts the
engine-disagreement warnings. Extra checks in `run_deterministic.sh`: a DOCX variant of the target (`fixtures/target_srs.docx`,
written by `make_docx_variant.py` with three embedded screenshots) is converted by LibreOffice and verified (`check_converted_pdf.py`:
pages, 3 unique images, caption text); tables are checked cell by cell (`check_tables.py`: pdfplumber path in v2, layout fallback in
`chat-env`); `fixtures/stress.fodt` (two columns, justified text, ligatures, bordered table; `make_stress_fodt.py`) is converted to a PDF
and extracted with both engines in both modes. `chat-env-v2` also installs `fonts-liberation` and `fonts-texgyre`, so LibreOffice embeds LiberationSerif (TrueType) + TeXGyreTermes (Type 1) like the Claude chat sandbox. With them the stress PDF reproduces a pypdf ligature problem (`eﬃcient` → `e cient`, and a stray `ffi` glued to `ağır`); `extract.py` repairs such damage using the other engine as evidence (only when the other engine has the correct word and not the damaged form), records every repair in the metadata (`repairs`), and `check_stress_ligatures.py` (plus the unit controls in `check_engine_warning.py`) verifies that the primary text of every engine/mode is clean.
`fixtures/target_srs.docx` and `stress.fodt` are generated separately from
`make_fixtures.py` on purpose, so the committed PDFs (which embed timestamps) are never regenerated.
