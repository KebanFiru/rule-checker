#!/usr/bin/env python3
"""Generates fixtures/coverage/ (scenario 1c: nothing skipped silently). Run inside the Docker *test* image.
Deliberately separate from make_fixtures.py so the older committed PDFs are not regenerated; reportlab invariant=1 and
deterministic PNGs make a re-run reproduce the same files.

  target_ui.pdf   14 pages: 6 screens (S-1.1..S-1.6); the screens on pages 11 and 13 contradict the body text (date, amount);
                  one data-model drawing (vector only, page 10); the reminder period stated 3 times, once differently; its own Appendix B
  ref_policy.pdf  requirements, an AS-IS paragraph that says "must" and contains a fact the target contradicts, descriptive sections
  prompt.txt      the user names "Ek B", which is not provided as a file
  expected.json   answer key
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, Flowable

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures/coverage"); OUT.mkdir(parents=True, exist_ok=True)
FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", FD + "DejaVuSans.ttf")); pdfmetrics.registerFont(TTFont("DVB", FD + "DejaVuSans-Bold.ttf"))
N = ParagraphStyle("n", fontName="DV", fontSize=10, leading=14, spaceAfter=4)
H = ParagraphStyle("h", fontName="DVB", fontSize=13, leading=17, spaceBefore=8, spaceAfter=6)
FILLER = ("This part of the document describes the behaviour of the exchange portal in plain words so that readers from every "
          "department can follow it. It adds context to the requirements and names the people who take part in the work. "
          "Nothing in this paragraph states a value, a limit or an obligation of its own.")


def footer(c, d):
    c.setFont("DV", 8); c.drawString(9 * cm, 1 * cm, f"Page {d.page}")


def screen(name, lines):
    im = Image.new("RGB", (520, 60 + 34 * len(lines)), "white"); d = ImageDraw.Draw(im)
    d.rectangle([2, 2, im.width - 3, im.height - 3], outline="black", width=2)
    d.text((14, 12), lines[0], font=ImageFont.truetype(FD + "DejaVuSans-Bold.ttf", 20), fill="navy")
    for k, l in enumerate(lines[1:]):
        d.text((14, 56 + 34 * k), l, font=ImageFont.truetype(FD + "DejaVuSans.ttf", 16), fill="black")
    im.save(OUT / name)
    return RLImage(str(OUT / name), width=11 * cm, height=11 * cm * im.height / im.width)


class DataModel(Flowable):
    """Entities as boxes and relations as lines: a drawing with no embedded image."""
    def wrap(self, *_):
        return 15 * cm, 6 * cm

    def draw(self):
        c = self.canv; c.setFont("DV", 10)
        boxes = {"Student": (0, 4), "Application": (5, 4), "Course": (10, 4), "Payment": (5, 1)}
        for name, (x, y) in boxes.items():
            c.rect(x * cm, y * cm, 3.5 * cm, 1.2 * cm); c.drawString((x + .3) * cm, (y + .5) * cm, name)
        for a, b in (((3.5, 4.6), (5, 4.6)), ((8.5, 4.6), (10, 4.6)), ((6.75, 4), (6.75, 2.2))):
            c.line(a[0] * cm, a[1] * cm, b[0] * cm, b[1] * cm)


def para(t):
    return Paragraph(t, N)


def head(t):
    return Paragraph(t, H)


def page(*items):
    return [*items, PageBreak()]


SCREENS = {  # id -> (page, title, body sentence, image lines)
    "S-1.1": (4, "Sign in", "The sign-in screen offers the button Sign in.", ["Sign in", "Button: Sign in"]),
    "S-1.2": (5, "Application form", "The form shows the course code CS-101 with 6 ECTS.", ["Application form", "Course: CS-101", "Credits: 6 ECTS"]),
    "S-1.3": (7, "Application status", "The status label of a new application is Submitted.", ["Application status", "Status: Submitted"]),
    "S-1.4": (11, "Nomination", "The nomination deadline shown to the student is 15.03.2027.", ["Nomination", "Deadline: 22.03.2027", "Button: Confirm"]),
    "S-1.5": (12, "Profile", "The profile shows the coordinator Dr. Ada Demir.", ["Profile", "Coordinator: Dr. Ada Demir"]),
    "S-1.6": (13, "Payment", "The payment screen shows the confirmation fee of 40 €.", ["Payment", "Confirmation fee: 55 €", "Button: Pay"]),
}


def scr(sid):
    p, title, body, lines = SCREENS[sid]
    return page(head(f"Screen {sid} {title}"), para(body), para(FILLER), screen(f"{sid}.png", lines))


story = []
story += page(head("Software Requirements Specification: Exchange Portal"), para("Rev 3"), para(FILLER))
story += page(head("1. Introduction"), para(FILLER), para(FILLER))
story += page(head("2. Requirements"), para("FR-1 The system shall send a reminder to the student after 5 days without an answer."),
              para("FR-2 The system shall show the confirmation fee before payment."),
              para("FR-3 The confirmation fee is collected by the International Office."), para(FILLER))
story += scr("S-1.1") + scr("S-1.2")
story += page(head("3. Use cases"), para("UC-1.1 Remind student. The reminder is sent 5 days after the application was submitted (S-1.3)."), para(FILLER))
story += scr("S-1.3")
story += page(head("4. Notifications"), para(FILLER), para(FILLER))
story += page(head("5. Quality requirements"), para("QR-A.1 The system shall send the reminder to the student after 7 days without an answer."), para(FILLER))
story += page(head("6. Data"), para(FILLER), para("Figure 1 Data model of the portal"), DataModel())
story += scr("S-1.4") + scr("S-1.5") + scr("S-1.6")
tbl = Table([["Item", "Amount"], ["Confirmation fee", "40 €"], ["Late fee", "10 €"]], hAlign="LEFT")
tbl.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "DV"), ("GRID", (0, 0), (-1, -1), .5, colors.grey)]))
story += [head("Appendix B Fee table"), para("The fees below apply to every application."), tbl, Spacer(1, 6), para(FILLER)]
SimpleDocTemplate(str(OUT / "target_ui.pdf"), pagesize=A4, invariant=1).build(story, onFirstPage=footer, onLaterPages=footer)

ref = [head("Exchange Portal Policy"), para("This policy is the reference for the portal."),
       head("1. Purpose"), para("The policy explains why the portal is being built: staff and students asked for one place to work."),
       head("2. Functional requirements"), para("The system shall send a reminder after 5 days without an answer."),
       para("The system shall show the confirmation fee before payment."),
       head("3. Current situation (AS-IS)"),
       para("Today the paperwork travels by e-mail. The confirmation fee is collected by the Finance Office, and the student must keep the receipt."),
       head("4. Open questions"), para("It is not yet decided who answers questions outside office hours."),
       head("Appendix A Contacts"), para("The project team can be reached through the department office.")]
SimpleDocTemplate(str(OUT / "ref_policy.pdf"), pagesize=A4, invariant=1).build(ref)
(OUT / "prompt.txt").write_text("Check target_ui.pdf against ref_policy.pdf and Ek B (the fee table).\n", encoding="utf-8")
exp = {"pages": 14, "screen_pages": [p for p, *_ in SCREENS.values()], "data_model_page": 10,
       "screen_mismatches": {"11": ["22.03.2027", "15.03.2027"], "13": ["55", "40"]},
       "asis_section": "ref_policy#3", "fact_conflict": ["Finance Office", "International Office"],
       "param_conflict": {"id": "P:reminder:time", "target_values": ["5 day", "7 day"]},
       "identity": {"name": "Ek B", "status": "internal-section"}}
(OUT / "expected.json").write_text(json.dumps(exp, ensure_ascii=False, indent=2), encoding="utf-8")
print("fixtures ->", OUT)
