#!/usr/bin/env python3
"""Generates the test scenario (run inside the Docker *test* image): fixtures/rules.pdf, target_srs.pdf,
review.docx, expected.json (answer key). The deliberate defects are defined here."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib import colors

sys.path.insert(0, str(Path(__file__).parent))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures"); OUT.mkdir(parents=True, exist_ok=True)
FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", FD + "DejaVuSans.ttf")); pdfmetrics.registerFont(TTFont("DVB", FD + "DejaVuSans-Bold.ttf"))
N = ParagraphStyle("n", fontName="DV", fontSize=10, leading=14, spaceAfter=4)
H = ParagraphStyle("h", fontName="DVB", fontSize=13, leading=17, spaceBefore=8, spaceAfter=6)
T = ParagraphStyle("t", fontName="DVB", fontSize=18, leading=22, spaceAfter=8)

def footer(c, d):
    c.setFont("DV", 8); c.drawString(9 * cm, 1 * cm, f"Page {d.page}")
def footer_none(c, d): pass

# ---------- 1) Rules PDF (25 rules) ----------
RULES = [
 ('The document title must be "Software Requirements Specification".', "template section"),
 ('The first page must show the version number in the form "Version X.Y".', "format"),
 ('The first page must show the author\'s name with the label "Author:".', "required content"),
 ("The date on the first page must be written as DD.MM.YYYY.", "format"),
 ('The document must contain an "Introduction" section.', "template section"),
 ('The document must contain a "Scope" section.', "template section"),
 ('The document must contain a "Glossary" section.', "template section"),
 ("Every requirement must carry an identifier of the form FR-N.", "format"),
 ("Every use case must carry an identifier of the form UC-N.M.", "format"),
 ('Requirements must not use optional wording such as "can" or "may".', "prohibition"),
 ('Vague terms ("appropriate", "if needed", "etc.") must not be used.', "prohibition"),
 ("A password must be at least 8 characters long.", "numeric value"),
 ("The session timeout must be 15 minutes.", "numeric value"),
 ("The system response time must be at most 3 seconds.", "numeric value"),
 ("Every use case must have a Priority field with the value High, Medium or Low.", "required content"),
 ('Every screenshot must carry a numbered caption of the form "Figure N".', "format"),
 ('Tables must be numbered with "Table N".', "format"),
 ("Quality requirements must carry an identifier of the form QR-X.N.", "format"),
 ("Passwords must not be stored in plain text.", "prohibition"),
 ("Monetary amounts must be shown in euros (€).", "numeric value"),
 ('The document must end with an "Appendices" section.', "process order"),
 ("Every requirement must be traceable to at least one use case (UC).", "required content"),
 ("The document must contain a revision history table.", "template section"),
 ('The term "customer" must not be used; the term "user" must be used.', "terminology"),
 ('Every page must show the page number at the bottom in the form "Page N".', "format"),
]
assert len(RULES) == 25
st = [Paragraph("SRS Template Rules v1", T), Paragraph("This document contains the mandatory rules for a Software Requirements Specification (SRS).", N)]
for i, (t, _) in enumerate(RULES, 1):
    st.append(Paragraph(f"Rule {i}. {t}", N))
    if i == 13: st.append(PageBreak())
SimpleDocTemplate(str(OUT / "rules.pdf"), pagesize=A4).build(st, onFirstPage=footer_none, onLaterPages=footer_none)

# ---------- 2) Images ----------
def img(name, lines, w=520, h=190):
    im = Image.new("RGB", (w, h), "white"); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FD + "DejaVuSans-Bold.ttf", 20); f2 = ImageFont.truetype(FD + "DejaVuSans.ttf", 16)
    d.rectangle([2, 2, w - 3, h - 3], outline="black", width=2)
    d.text((14, 12), lines[0], font=f, fill="navy")
    for k, l in enumerate(lines[1:]): d.text((14, 56 + 34 * k), l, font=f2, fill="black")
    im.save(OUT / name)
img("s1.png", ["UC-1.2 Change Password", "Old password: ********", "New password: ********"])   # body: UC-1.1 Sign-in screen -> MISMATCH
img("s2.png", ["Payment Screen", "Amount: 120 €", "Date: 14.03.2026"])                          # body: 100 € -> MISMATCH
img("s3.png", ["Report Screen", "Report type: Monthly", "Format: PDF"])                            # no caption (violation)

# ---------- 3) Target SRS ----------
from srs_content import srs_blocks

pdf_text = lambda s: s.split("@@")[0]
docx_text = lambda s: s.split("@@")[-1]

story = []
for k, v in srs_blocks():
    if k == "title": story.append(Paragraph(v, T))
    elif k == "h": story.append(Paragraph(v, H))
    elif k == "p": story.append(Paragraph(pdf_text(v), N))
    elif k == "img": story += [RLImage(str(OUT / v), width=11 * cm, height=11 * cm * 190 / 520), Spacer(1, 6)]
    elif k == "table":
        t = Table(v, hAlign="LEFT"); t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "DV"), ("GRID", (0, 0), (-1, -1), .5, colors.grey)])); story += [t, Spacer(1, 6)]
SimpleDocTemplate(str(OUT / "target_srs.pdf"), pagesize=A4).build(story, onFirstPage=footer, onLaterPages=footer)

# ---------- 4) Review DOCX (real Word comments + tracked changes; standard-library writer) ----------
sys.path.insert(0, str(Path(__file__).parent))
from docx_mini import build_docx
COMMENTS = [  # (person, paragraph prefix, comment, expected label)
 ("Alice Smith", "Rev 2", "The version number format is wrong; it should read 'Version 2.0'.", "Valid"),
 ("Alice Smith", "FR-2", "The password is 6 characters; it must be at least 8.", "Valid"),
 ("Alice Smith", "Software Requirements", "The title should be translated to German.", "Invalid"),
 ("Alice Smith", "FR-4", "FR-4 refers to UC-9.9 but no such use case exists.", "Valid"),
 ("Bob Jones", "FR-3", "The session timeout should be 15 minutes.", "Valid"),
 ("Bob Jones", "User:", "The glossary should also define the term 'customer'.", "Invalid"),
 ("Bob Jones", "Table 2", "Fees should be shown in USD instead of euros.", "Invalid"),
 ("Bob Jones", "QR-A.2", "The response time should be 1 second.", "Team decision needed"),
]
blocks = [("table", v) if k == "table" else ("p", docx_text(v)) for k, v in srs_blocks() if k in ("title", "h", "p", "table")]
build_docx(OUT / "review.docx", blocks,
           comments=[(w, text, pre) for w, pre, text, _ in COMMENTS],
           tracked=[("FR-6", [("ins", "Bob Jones", " (in emergencies)"), ("del", "Bob Jones", " etc.")])])

# ---------- 5) Answer key ----------
exp = {
 "rule_count": 25,
 "rules": [{"n": i, "text": t, "type": ty} for i, (t, ty) in enumerate(RULES, 1)],
 "planted_rule_violations": [  # rule number -> defect in the target
   {"rule_n": 2, "what": "version 'Rev 2' (no 'Version X.Y')"}, {"rule_n": 4, "what": "date 2026-03-14 format"},
   {"rule_n": 6, "what": "no Scope section"}, {"rule_n": 10, "what": "FR-5 'can'"},
   {"rule_n": 11, "what": "FR-6 'appropriate', 'if needed', 'etc.'"}, {"rule_n": 12, "what": "FR-2 password 6 characters"},
   {"rule_n": 13, "what": "FR-3 session 30 minutes"}, {"rule_n": 15, "what": "UC-2.2 Priority: Urgent"},
   {"rule_n": 16, "what": "third image has no Figure caption"}, {"rule_n": 19, "what": "QR-A.1 plain-text passwords"},
   {"rule_n": 20, "what": "Table 2 '250 USD'"}, {"rule_n": 22, "what": "FR-5 has no UC reference"}],
 "broken_xrefs": ["UC-9.9", "FR-14", "Table 5"],
 "screenshot_mismatches": [
   {"name": "Figure 1", "patterns": ["Change Password", "UC-1\\.2"], "note": "body says UC-1.1 Sign-in screen; image shows UC-1.2 Change Password"},
   {"name": "Figure 2", "patterns": ["120"], "note": "body says 100 €; image shows 120 €"}],
 "extraction_artifact": {"word": "userdata", "must_be_flagged_as": "extraction warning"},
 "comments": [{"person": w, "n": [c[0] for c in COMMENTS[:i + 1]].count(w), "expected": e, "text": t} for i, (w, _, t, e) in enumerate(COMMENTS)],
 "tracked_changes": 2,
}
(OUT / "expected.json").write_text(json.dumps(exp, ensure_ascii=False, indent=2), encoding="utf-8")
print("fixtures ->", OUT)
