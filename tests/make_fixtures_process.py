#!/usr/bin/env python3
"""For the process-model/regression test: fixtures/process/process_v1.pdf|docx, process_v2.pdf|docx, expected_v2.json (run in the Docker test image)."""
import json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak
import sys
sys.path.insert(0, str(Path(__file__).parent))
from docx_mini import build_docx

OUT = Path("fixtures/process"); OUT.mkdir(parents=True, exist_ok=True)
FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", FD + "DejaVuSans.ttf")); pdfmetrics.registerFont(TTFont("DVB", FD + "DejaVuSans-Bold.ttf"))
N = ParagraphStyle("n", fontName="DV", fontSize=10, leading=14, spaceAfter=4)
NI = ParagraphStyle("ni", parent=N, leftIndent=4 * cm)           # in v2 only the line wrapping changes (noise)
H = ParagraphStyle("h", fontName="DVB", fontSize=13, leading=17, spaceBefore=8, spaceAfter=6)
LONG = "SP-1.2 The system validates the amount in € and checks all fields of the request and forwards the payment request to the coordinator."
S = {
 "t": "Payment and Notification Processes", "sp1": "SP-1 Payment Process",
 "11": "SP-1.1 The user creates a payment request.", "12": LONG,
 "13": "SP-1.3 The coordinator approves the payment within 2 days.", "14": "SP-1.4 The system generates the receipt.",
 "15": "SP-1.5 The system sends a reminder after 3 days.", "x1": "SP-1.X1 If the amount does not match, the system shows an error and returns to step SP-1.1.",
 "sp2": "SP-2 Notification Process", "21": "SP-2.1 The system adds the notification to the queue.", "22": "SP-2.2 The system sends the notification.",
 "23": "SP-2.3 The reminder period must be 3 days.",
}
V1 = ["t", "sp1", "11", "12", "13", "14", "15", "x1", "PB", "sp2", "21", "22", "23"]
S2 = dict(S); S2["15"] = "SP-1.5 The system sends a reminder after 5 days."; S2["22"] = "SP-2.2 The system sends the notification by e-mail."; S2["16"] = "SP-1.6 The system archives the receipt."
V2 = ["t", "sp1", "11", "12", "14", "13", "15", "16", "x1", "PB", "sp2", "21", "22", "23"]   # 14 and 13 swapped

def foot(c, d): c.setFont("DV", 8); c.drawString(9 * cm, 1 * cm, f"Page {d.page}")
def build(name, order, texts, indent12):
    st = []
    for k in order:
        if k == "PB": st.append(PageBreak())
        else: st.append(Paragraph(texts[k], H if k in ("sp1", "sp2", "t") else (NI if (k == "12" and indent12) else N)))
    SimpleDocTemplate(str(OUT / f"{name}.pdf"), pagesize=A4).build(st, onFirstPage=foot, onLaterPages=foot)
    build_docx(OUT / f"{name}.docx", [("p", texts[k]) for k in order if k != "PB"])
build("process_v1", V1, S, False); build("process_v2", V2, S2, True)
exp = {
 "diff": {"changed": ["SP-1.5", "SP-2.2"], "added": ["SP-1.6"], "moved_any_of": ["SP-1.3", "SP-1.4"], "format_only": ["SP-1.2"]},
 "invariants_on_v2": {"FAIL": ["I-01", "I-02"], "PASS": ["I-03", "I-04", "I-05", "I-06", "I-07", "I-08"]},
 "classification": {"SP-2.2": "✅", "SP-1.5": "⚠️", "SP-2.3": "⚠️", "SP-1.4": "❌", "SP-1.6": "🆕"},
 "impact_must_include": {"same_parameter": ["SP-2.3"], "invariants": ["I-02", "I-01"]},
 "changelog_must_mention": ["v2", "SP-1.5", "SP-2.2", "SP-1.6"],
}
(OUT / "expected_v2.json").write_text(json.dumps(exp, ensure_ascii=False, indent=2), encoding="utf-8")
print("process fixtures ->", OUT)
