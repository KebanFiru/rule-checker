# 0. Classify the documents and settle their identity

Classify each file: target / reference / review. If unsure, ask the user; if the user is unavailable, write your guess at the top of the report. Identify which documents are IMMUTABLE (e.g. a Project Report) and use them as reference only. Create a working folder `work/`; intermediate files live there.

**Document identity.** Run `section_inventory.py identity` with EVERY document name the user used ("Ek B", "PAR", "charter"), after `extract.py` has produced the target text. Possible outcomes:
- `file`: matched to an uploaded file (correct a wrong or ambiguous match with `--map "name=file"`). If it is the target itself, that is a circular check.
- `internal-section`: no such file, but the target has a section of that name. Never treat this as the same thing silently. ASK the user whether a separate document exists. If the user is unavailable, the note ("«Ek B» was not provided as a separate file; the section «Appendix B» of the target was used") stays at the top of the report; use `--lang tr` for a Turkish report; record an answer with `--confirmed "name=answer"`. Add the section to the section inventory (`scan … "work/ex/target.txt@Appendix B"`). Rules taken from it keep their normal result (do not turn them into ❓): the report marks them `⚑ source assumption` and lists them as a circular check (the target verifies itself).
- `missing`: neither. Ask; otherwise it is counted as a skipped check.
