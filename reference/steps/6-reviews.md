# 6. Review documents

If review documents are given (`extract.py` puts comments + tracked changes in the DOCX json):
Make EACH comment its own item (person + comment no.). Give one value per item: Valid (per which rule/evidence) | Partially valid | Invalid (why) | Team decision needed (options) | Already fixed | Requires touching an immutable document. If different people give conflicting suggestions on the same topic, merge them and propose a middle path but DO NOT decide; ask.
