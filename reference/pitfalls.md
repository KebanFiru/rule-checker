# Pitfalls

## 1. PDF text extraction: merged/split words, ligatures, hyphens
- End-of-line hyphenation ("require-\nment") and column layout split words; lost spaces on adjacent lines produce merges like "monthbefore".
- Ligatures (ﬁ, ﬂ), the soft hyphen (U+00AD) and decomposed accented characters (e.g. i + U+0307) break searching: extract.py already expands ligatures, drops soft hyphens and NFC-normalizes PDF text; the DOCX/TXT paths are not normalized.
- If the two independent engines (pdftotext vs pypdf) disagree, or a page has no text layer (scanned), extract.py warns; verify the suspicious word against the DOCX source or by reading the PDF page natively with the Read tool (`pages` parameter). Never report it as a typo without verifying.
- Multi-column pages: `-layout` reads across columns (left and right column text end up on one line); rerun `extract.py --reading-order` for those documents (tables then come out cell by cell). In layout mode, runs of spaces are table-cell boundaries (` | `) only where columns line up on neighbouring lines; elsewhere (justified text, indentation) they collapse to one space, because pdftotext and different pypdf versions emit different amounts of such spacing. Residual: at a two-column gutter, pypdf 5.4 and 6.x can differ in whether a ` | ` appears (the words are identical); `--reading-order` is identical across all engine versions tested.
- Text-layer PDFs only: scanned pages give empty text (extract.py warns); read them with the Read tool.
- If a source DOCX exists, use `--docx-source` to list merged-word candidates.

## 2. Text inside a screenshot differs from the body
- Text inside an image is NOT in the text layer: it is visible only when the page is rendered: open it with the Read tool (`pages` parameter). Compare dates, codes, amounts, user names, button labels and status values with the body and the rules.
- Typical: body says "3 days", screen shows "5 days"; body says UC-2.1, screen title says UC-2.2; body amount ≠ screen amount.
- If the image will not change, do NOT propose "redraw the image"; make it a team decision. Proposals that make something look done that nobody did (e.g. "show it as if it had been done in Figma") are FORBIDDEN.

## 3. Table rows split across a page break
- A row that spans two pages splits its cells in two: the first part has the ID, the second part has none; wrongly reported as "missing cell" or "duplicate row".
- Do not count repeated header rows twice. Join the table across the page boundary (last rows of p_n + first rows of p_n+1) and read the page with the Read tool.

## 4. The same rule worded differently in two places of the reference
- Register BOTH as separate rules (R-0xx, R-0yy) and list them under "Conflicting references" in rule_register.md. Never silently pick one.
- If the target agrees with one but not the other: one ✅, one ❌, and report the conflict; "which one is valid" is a team decision (TBD).

## 5. Other
- Out of scope ≠ compliant: write ➖ and the reason. No ✅ without evidence.
- Evidence for an "absence" violation: write where you looked (sections, page range, search words).
- Verify numeric values yourself (sums, percentages, date order).
- Never invent a value for something the reference does not answer: TBD / team decision.
- Keyword candidates (matrix.py skeleton) are only hints; if the candidate list is empty the rule may be violated.

## 6. Silent gaps (the report looks complete but is not)
- Looking at the first few screen pages and stopping: the visual inventory lists them all; every one needs a log row.
- Turning only the "FR" lines into rules: AS-IS text and interview notes hold facts, TO-BE lists hold one rule per item, and "must" hides in descriptive paragraphs.
- Assuming "Appendix B" / "Ek B" named by the user is the target's own appendix: check the files, ask, and say so.
- Checking durations by eye: use `param_check.py`, then judge each conflict.
