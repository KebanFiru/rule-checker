#!/usr/bin/env python3
"""Generates ONLY fixtures/target_srs.docx: the same content as target_srs.pdf, as a DOCX with the three screenshots embedded.
Deliberately separate from make_fixtures.py so the committed PDFs (which embed timestamps) are not regenerated.
Standard library only (docx_mini.py). Usage: make_docx_variant.py [fixtures_dir]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from srs_content import srs_blocks
from docx_mini import build_docx

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures")
blocks = []
for k, v in srs_blocks():
    if k in ("title", "h", "p"):
        blocks.append(("p", v.split("@@")[-1]))
    elif k == "table":
        blocks.append(("table", v))
    elif k == "img":
        blocks.append(("img", OUT / v, 520, 190))
build_docx(OUT / "target_srs.docx", blocks)
print("wrote", OUT / "target_srs.docx")
