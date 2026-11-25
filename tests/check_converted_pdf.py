#!/usr/bin/env python3
"""Checks the LibreOffice-converted PDF of target_srs.docx (pypdf): page count, unique embedded images, caption text.
Usage: check_converted_pdf.py <docx_pdf_dir>. Prints 'skipped' when no PDF exists (e.g. no LibreOffice)."""
import json, sys
from pathlib import Path
d = Path(sys.argv[1]); st = json.loads((d / "visual_status.json").read_text(encoding="utf-8"))
print(st["line"])
if st["status"] != "converted":
    sys.exit(0)
import pypdf
r = pypdf.PdfReader(st["pdf"])
# LibreOffice shares one resource dictionary across pages, so count UNIQUE image objects, not per-page listings
imgs = len({im.name for p in r.pages for im in p.images}); txt = " ".join(p.extract_text() for p in r.pages)
ok = len(r.pages) >= 1 and imgs == 3 and "Figure 2" in txt
print(f"converted PDF: pages={len(r.pages)} images={imgs} has 'Figure 2'={'Figure 2' in txt} -> {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
