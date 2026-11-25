#!/usr/bin/env python3
"""For tests: rules.txt (extract output) -> rules.json. Turns the 'Rule N.' lines (with line-wrap continuations) into atomic rules.
In real use this step is the model reading the reference and building the register; here it is scripted for test determinism."""
import json, re, sys
src, out, doc = sys.argv[1], sys.argv[2], sys.argv[3]
cur = None; rules = []
for raw in open(src, encoding="utf-8"):
    loc, t = raw.rstrip("\n").split("\t", 1); page = int(re.match(r"p(\d+)", loc).group(1))
    m = re.match(r"Rule (\d+)\.\s*(.*)", t)
    if m:
        cur = {"id": f"R-{int(m.group(1)):03d}", "source": {"doc": doc, "page": page, "quote": m.group(2)}}; rules.append(cur)
    elif cur and not t.startswith("SRS") and not re.match(r"Page \d+$", t):
        cur["source"]["quote"] += " " + t
for r in rules:
    q = r["source"]["quote"].lower()
    r["type"] = ("prohibition" if "must not" in q else "numeric value" if re.search(r"\d|at least|at most|€", q) else "template section" if "section" in q or "table" in q and "history" in q
                 else "format" if "form of" in q or "numbered" in q else "required content")
    r["scope"] = "whole document"; r["interpretation"] = ""
json.dump({"rules": rules}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(rules), "rules ->", out)
