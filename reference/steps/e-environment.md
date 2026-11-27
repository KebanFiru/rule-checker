# E. Environment check

Basic principle: **nothing is skipped silently.** Whatever is skipped appears in the report with a count and a reason, and `matrix.py verify` checks it. Goal: check TARGET documents against the rules in REFERENCE documents in ONE pass, exhaustively. This fixes the "finds a few obvious problems, finds new ones every round" failure mode with a **rule register + traceability matrix + coverage verification**: the work is not finished until every rule has an explicit result. "Finished" means `matrix.py verify` passes.

## Running
The scripts are plain Python 3 (standard library only) and run directly: `python3 <skill-dir>/scripts/<script>.py …`, where `<skill-dir>` is the directory that contains this SKILL.md. Set once, then use it in every command below:
```bash
S=<skill-dir>/scripts
```
Optional pieces degrade gracefully (step E reports what is missing): PyYAML (process model), pypdf and/or poppler's `pdftotext` (PDF text), pdfplumber (cell-level tables), LibreOffice (DOCX visual pass). Never `pip install` anything on the host or in the sandbox, and use `python3`, never `python`. (Developers of this repository run everything in Docker through `dev/run.sh`; that is not needed to use the skill.)

## Resuming and `work/progress.json`
`matrix.py set-bulk`, `visual_inventory.py record`, `section_inventory.py classify` and `param_check.py verdict` record their checkpoints in `work/progress.json`. Record the other steps yourself: `progress.py step work/progress.json <step> done`. A step you deliberately do not do: `… <step> skipped --reason "…"` (counted in the report). Four steps are mandatory: `reference` (`section_inventory.py scan`), `visual` (`visual_inventory.py scan`), `self-rules` (`self_rules.py scan`) and `self-audit`; without their result `verify` fails unless that exact step name is recorded as skipped with a reason. After a context summary or in a new session run `progress.py show work/progress.json` and `matrix.py status` FIRST, then continue where they stop.

## The check (always first, one command)
```bash
python3 $S/env_check.py --json work/env.json
```
It reports the Python, pypdf, pdfplumber, PyYAML, `pdftotext` and LibreOffice (`soffice`) versions and lists the checks that CANNOT be done here (no second PDF engine, no cell-level tables, no DOCX visual pass, no process model). Tell the user up front which checks will be skipped, and pass `--env work/env.json` to `matrix.py coverage` so the report's "Environment" section states it.
