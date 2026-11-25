## Cross-reference and internal-consistency findings
(xref_check.py output verified in the document)
1. **UC-9.9** — FR-4 (p1:L17) «see UC-9.9»; UC-9.9 is not defined in the document. Fix: link to the right UC (probably UC-2.2 Make payment — ASSUMPTION, team must confirm).
2. **FR-14** — FR-6 (p1:L20) «see FR-14»; FR-1…FR-6 exist, FR-14 does not.
3. **Table 5** — Table 2 caption (p1:L23) «see Table 5»; only Table 1 and 2 exist.
4. **Mixed currencies** — p1:L25 «250 USD» ↔ p2:L3 «100 €» (same root cause as R-020).
5. Numbering gaps / duplicate definitions: none (xref_check).

## Visual pass findings (PDF page 2, read with the Read tool)
1. **Figure 1** — caption/body say «UC-1.1 Sign-in screen» but the image title is «UC-1.2 Change Password» and the fields are password-change fields. Body ↔ image mismatch.
2. **Figure 2** — body says «amount 100 €», the image shows «Amount: 120 €». Mismatch.
3. The third image «Report Screen» has no caption (R-016).
Note: the date in the screens, 14.03.2026, is the same day as the document date (2026-03-14), only the format differs.

## Extraction warnings
- p1:L10 «userdata»: extract.py flagged a suspicious merged word; the source DOCX has «user data» (separate). Treated as an extraction artifact, not a document error. (Test note: in the fixture the PDF was deliberately written merged; in real life you confirm by reading the page with the Read tool.)
- Tracked changes (Bob Jones, P16/FR-6): insertion « (in emergencies)», deletion « etc.». The deletion fixes part of R-011; the added «in emergencies» may be a new vague phrase (team decision).

## Assumptions / TBD
- Content of the Scope section, UC-2.2 priority, password hashing algorithm, the € amount in Table 2: not in the reference → TBD / team decision.
