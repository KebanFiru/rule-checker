#!/usr/bin/env python3
"""Builds dist/rule-check.zip from an explicit include list (standard library only, deterministic order and timestamps).
Run through the Docker wrapper:  ./scripts/run.sh python3 /skill/scripts/package.py /work/dist/rule-check.zip
Top-level folder inside the zip: rule-check/ (SKILL.md is rule-check/SKILL.md). Tests are not shipped."""
import sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ["SKILL.md", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "scripts", "templates", "reference", "docker/Dockerfile"]
SKIP = {"__pycache__", ".git"}


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/rule-check.zip")
    out.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for item in INCLUDE:
        p = ROOT / item
        if p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.is_file() and not (SKIP & set(f.parts)) and f.suffix != ".pyc"]
        elif p.is_file():
            files.append(p)
        else:
            sys.exit(f"missing include: {item}")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            info = zipfile.ZipInfo(f"rule-check/{f.relative_to(ROOT).as_posix()}", date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = (0o755 if f.suffix in (".sh", ".py") else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, f.read_bytes())
    print(f"{out}: {len(files)} files")


if __name__ == "__main__":
    main()
