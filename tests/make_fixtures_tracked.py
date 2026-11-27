#!/usr/bin/env python3
"""Synthetic PDF with every visible kind of tracked change (needs ReportLab; test image only). Usage: make_fixtures_tracked.py OUTDIR"""
import sys
from pathlib import Path
from reportlab.lib.colors import black, red, blue, Color
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfdoc import PDFDictionary, PDFName, PDFArray, PDFString

F, S = "Helvetica", 11


def main():
    OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures/tracked")
    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT / "tracked.pdf"), pagesize=A4, invariant=1)

    def line(y, parts):
        """parts: (text, colour, style) with style in '', 'line', 'rect', 'annot', 'under'."""
        x = 72
        for text, col, style in parts:
            c.setFont(F, S); c.setFillColor(col); c.drawString(x, y, text)
            w = stringWidth(text.rstrip(), F, S)
            c.setStrokeColor(col); c.setLineWidth(0.6)
            if style == "line":
                c.line(x, y + S * 0.3, x + w, y + S * 0.3)
            elif style == "rect":
                c.rect(x, y + S * 0.28, w, 0.7, stroke=0, fill=1)
            elif style == "under":
                c.line(x, y - 1.5, x + w, y - 1.5)
            elif style == "annot":
                x0, y0, x1, y1 = x, y - 2, x + w, y + S * 0.8
                c._addAnnotation(PDFDictionary({"Type": PDFName("Annot"), "Subtype": PDFName("StrikeOut"), "Rect": PDFArray([x0, y0, x1, y1]),
                                                "QuadPoints": PDFArray([x0, y1, x1, y1, x0, y0, x1, y0]), "Contents": PDFString("deleted")}))
            x += stringWidth(text, F, S)

    line(780, [("1 Enrolment", black, "")])
    line(760, [("Students shall register within ", black, ""), ("30 ", red, "line"), ("60 ", red, "under"), ("days.", black, "")])
    line(744, [("The fee is 30 EUR and the form has 30 fields.", black, "")])
    line(728, [("Late requests are ", black, ""), ("always ", black, "rect"), ("rejected.", black, "")])
    line(712, [("A paper copy is ", black, ""), ("also ", black, "annot"), ("required.", black, "")])
    line(696, [("Paper forms are accepted at the front desk.", Color(0.5, 0.5, 0.5), "line")])
    line(680, [("Underlined black words stay: ", black, ""), ("important", black, "under")])
    line(664, [("Warning in red: ", black, ""), ("check the deadline", red, "")])
    line(648, [("See ", black, ""), ("the portal", blue, "under"), (" for details.", black, "")])
    c.linkURL("https://example.org", (72 + stringWidth("See ", F, S), 646, 72 + stringWidth("See the portal", F, S), 660))
    for y in (632, 616, 600, 584):
        line(y, [("Ordinary body text keeps black the usual colour of this document for the colour test.", black, "")])
    c.line(72, 570, 400, 570)                                    # a rule between paragraphs, not through text
    c.setFillColor(black); c.drawString(200, 548, "Enrolment record")
    c.setStrokeColor(black); c.line(50, 548 + S * 0.3, 500, 548 + S * 0.3)       # a diagram connector through a label: not a deletion
    c.drawString(200, 528, "Course"); c.drawString(420, 528, "Student")
    c.line(205, 528 + S * 0.3, 445, 528 + S * 0.3)                              # a connector from one label into another
    c.showPage(); c.save()
    print(OUT / "tracked.pdf")


if __name__ == "__main__":
    main()
