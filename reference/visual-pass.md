# Visual pass

Claude reads the pages itself; the scripts decide WHICH pages and prove that each one was handled.

## Which pages
```bash
python3 $S/visual_inventory.py scan target.pdf -o work/visual_inventory.json
```
It lists every page with an embedded image, dense vector drawing, very short text, a Figure/Screen/Şekil/Ekran/S-x.y/Diagram caption or a table caption, with a type (screen / diagram / data-model / table / other), related IDs and a priority, prints Read batches and creates `work/visual_log.json` (one unchecked row per page). Also add by hand any page `extract.py` warned about and any table page the inventory missed (append the row to both files). Repeated header/logo images are treated as decoration; the report names the pages that had nothing else. Without pypdf, images and drawings are NOT detected (the inventory says so): read all pages.
If the target is a DOCX, convert it first: `python3 $S/docx_to_pdf.py target.docx -o work/docx_pdf` (headless LibreOffice, 60 s limit; works without network and with a read-only filesystem), then scan and read `work/docx_pdf/<name>.pdf`. The script prints either `Visual pass: DOCX→PDF (LibreOffice …)` or `⏭️ visual pass skipped (<reason>)` (no LibreOffice, timeout …) and never fails the run: if it is skipped, ask the user for a PDF export, or continue without the visual pass and record `progress.py step work/progress.json visual skipped --reason "…"`. Pass `--visual work/docx_pdf/visual_status.json` to `matrix.py coverage` so the report states which of the two happened.

## Reading
Use the **Read tool with its `pages` parameter** on the printed batches (`pages: "11-30"`; max 20 pages per call), never one page per call. LOOK at each page: text, dates, codes and amounts inside images are not in the text layer. Do not stop after the first pages: high-priority pages are often at the end. Compare what you see with the body and the rules. Read table rows that split across a page break as one table.

## Checklist
- **Screens:** every date, amount, ECTS value, course code, person name, status label and button name on the screen against the body text, the UI table of the linked use case and the parameter values.
- **Diagrams and data models:** entities, relations and flow steps against the process model and the use cases (missing, extra or renamed entities; order and actors of steps).
- **Tables:** values against the body and the rules.

## Record (after every batch)
```bash
python3 $S/visual_inventory.py record work/visual_log.json work/visual_part_01.json
python3 $S/visual_inventory.py status work/visual_inventory.json work/visual_log.json
```
```json
[{"page":11,"ids":["S-1.4"],"checked":true,"method":"Read pages 11-30","findings":"deadline on screen 22.03., body 15.03.","skipped_reason":""},
 {"page":12,"checked":false,"skipped_reason":"decorative cover page"}]
```
(add `"doc"` when the inventory covers several PDFs). `checked: true` needs method and findings ("no differences: <what you compared>"). A page you did not look at may only be recorded with `skipped_reason`; the report counts skips at the top. Do not mark a page checked unless it was in a Read call. Write the differences under "Visual pass findings" in the report.
