#!/usr/bin/env python3
"""Tracked changes that are only VISIBLE in a PDF (used by extract.py; needs pdfplumber, no PyMuPDF).

Deleted  : text under a StrikeOut annotation, or crossed by a drawn horizontal line / thin rectangle through the middle of the glyphs
           that starts and ends with that text (a longer connector or border through a label is not a strike line).
Added    : (only when deletions exist) coloured, underlined text that is not a link.
Suspected: red or grey text with neither: it MAY be deleted text. It is reported, never removed.
Only deleted text is removed from <stem>.current.txt; whatever could not be removed is listed in <stem>.changes.json.
"""
import re
from collections import Counter
from difflib import SequenceMatcher

SKIP_CHARS = re.compile(r"[\s|]")


def colour(c):
    """'black' | 'red' | 'grey' | 'other' for a pdfplumber colour (grey / RGB / CMYK tuple)."""
    if c is None:
        return "black"
    v = [float(x) for x in (c if isinstance(c, (list, tuple)) else [c]) if isinstance(x, (int, float))]
    if len(v) == 4:
        k = v[3]; v = [(1 - x) * (1 - k) for x in v[:3]]
    if len(v) == 1:
        v = v * 3
    if len(v) != 3:
        return "black"
    r, g, b = v
    if max(v) - min(v) < 0.08:
        return "grey" if 0.3 <= r <= 0.75 else "black"
    if r >= 0.55 and g <= 0.35 and b <= 0.35:
        return "red"
    return "black" if max(v) < 0.25 else "other"


def segments(page):
    """Horizontal strokes of a page as (x0, x1, y) in top-down coordinates."""
    out = []
    for kind, limit in (("lines", 1.5), ("rects", 2.5), ("curves", 1.5)):
        for o in getattr(page, kind):
            if o["bottom"] - o["top"] <= limit and o["x1"] - o["x0"] >= 2:
                out.append((o["x0"], o["x1"], (o["top"] + o["bottom"]) / 2))
    return out


def fits_text(stroke, chars):
    """A strike line is drawn along its text: it starts and ends with the characters it crosses and spans no wide gap.
    A connector, border or rule that merely runs through a label overshoots it."""
    x0, x1, y = stroke
    hit = sorted((c for c in chars if x0 - 0.5 <= (c["x0"] + c["x1"]) / 2 <= x1 + 0.5
                  and c["top"] + 0.25 * (c["bottom"] - c["top"]) <= y <= c["top"] + 0.75 * (c["bottom"] - c["top"])), key=lambda c: c["x0"])
    if not hit:
        return False
    size = max(c["size"] for c in hit)
    return (x0 >= hit[0]["x0"] - 0.5 * size and x1 <= max(c["x1"] for c in hit) + 0.5 * size
            and all(b["x0"] - a["x1"] <= 1.5 * size for a, b in zip(hit, hit[1:])))


def annotation_boxes(page):
    """(x0, top, x1, bottom) of every StrikeOut annotation."""
    out = []
    for a in page.annots or []:
        data = a.get("data") or {}
        if str(getattr(data.get("Subtype"), "name", data.get("Subtype"))).strip("/'") != "StrikeOut":
            continue
        quads = data.get("QuadPoints") or []
        try:
            q = [float(x) for x in (quads.resolve() if hasattr(quads, "resolve") else quads)]
        except (TypeError, ValueError):
            q = []
        boxes = [(min(q[i:i + 8:2]), page.height - max(q[i + 1:i + 8:2]), max(q[i:i + 8:2]), page.height - min(q[i + 1:i + 8:2]))
                 for i in range(0, len(q) - 7, 8)]
        out += boxes or [(a["x0"], a["top"], a["x1"], a["bottom"])]
    return out


def visual_lines(chars):
    lines = []
    for c in sorted(chars, key=lambda c: (c["bottom"], c["x0"])):
        if lines and abs(c["bottom"] - lines[-1][-1]["bottom"]) <= max(2.0, c["size"] * 0.25):
            lines[-1].append(c)
        else:
            lines.append([c])
    return [sorted(l, key=lambda c: c["x0"]) for l in lines]


def mark(c, strokes, strikes, boxes, links):
    """Flags of one character."""
    cx, cy, h = (c["x0"] + c["x1"]) / 2, (c["top"] + c["bottom"]) / 2, c["bottom"] - c["top"]
    over = [y for x0, x1, y in strokes if x0 - 0.5 <= cx <= x1 + 0.5]
    return {"annotation": any(x0 <= cx <= x1 and top <= cy <= bottom for x0, top, x1, bottom in boxes),
            "struck": any(x0 - 0.5 <= cx <= x1 + 0.5 and c["top"] + 0.25 * h <= y <= c["top"] + 0.75 * h for x0, x1, y in strikes),
            "underlined": any(c["top"] + 0.8 * h <= y <= c["bottom"] + 0.25 * h for y in over),
            "colour": colour(c.get("non_stroking_color")),
            "link": any(l["x0"] <= cx <= l["x1"] and l["top"] <= cy <= l["bottom"] for l in links)}


def runs(line, key):
    """Consecutive characters of a visual line with the same non-empty key -> [(key, text, [index])]."""
    out, prev = [], None
    for i, c in enumerate(line):
        k = key(c)
        if not c["text"].strip():
            continue
        if k and out and prev is not None and out[-1][0] == k and all(not line[j]["text"].strip() for j in range(prev + 1, i)):
            gap = c["x0"] - line[prev]["x1"] > c["size"] * 0.15 or i > prev + 1
            out[-1] = (k, out[-1][1] + (" " if gap else "") + c["text"], out[-1][2] + [i])
        elif k:
            out.append((k, c["text"], [i]))
        prev = i if k else None
    return out


def analyse(path, clean):
    """[{page, lines: [[char + flags]]}] for every page. Raises ImportError without pdfplumber."""
    import pdfplumber
    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            strokes, boxes, links = segments(page), annotation_boxes(page), page.hyperlinks
            lines = visual_lines(page.chars)
            strikes = [s for s in strokes if fits_text(s, page.chars)]
            for l in lines:
                for c in l:
                    c["text"] = clean(c["text"])
                    c.update(mark(c, strokes, strikes, boxes, links))
            pages.append({"page": number, "lines": lines})
    return pages


def changes_of(pages):
    chars = [c for p in pages for l in p["lines"] for c in l if c["text"].strip()]
    if not chars:
        return []
    deleted_any = any(c["struck"] or c["annotation"] for c in chars)
    median = sorted(c["size"] for c in chars)[len(chars) // 2]
    share = Counter(c["colour"] for c in chars)
    usual = {k for k, n in share.items() if n > 0.3 * len(chars)}                 # body text colour: says nothing
    text_of_line = lambda l: re.sub(r"\d+", "#", "".join(c["text"] for c in l))
    repeated = Counter(t for p in pages for t in {text_of_line(l) for l in p["lines"]})
    running = {t for t, n in repeated.items() if len(pages) > 1 and n >= max(2, len(pages) / 2)}          # headers / footers

    def kind(c, line):
        if c["annotation"]:
            return ("deleted", "strikeout annotation")
        if c["struck"]:
            return ("deleted", "line through the text")
        if c["colour"] in usual or c["colour"] == "black" or c["link"]:
            return None
        if c["underlined"]:
            return ("added", "coloured underlined text") if deleted_any and c["colour"] != "grey" else None
        if c["colour"] in ("red", "grey") and c["size"] <= median * 1.15 and text_of_line(line) not in running:
            return ("suspected", f"{c['colour']} text without strike line")
        return None

    out = []
    for p in pages:
        for li, line in enumerate(p["lines"]):
            for (typ, method), text, index in runs(line, lambda c: kind(c, line)):
                out.append({"page": p["page"], "type": typ, "method": method, "text": text, "_line": li, "_index": index})
    return out


def remove(primary, pages, changes):
    """primary: list of pages (lists of text lines). Returns (current pages as {line number: text}, changes that could not be removed)."""
    current = [dict(enumerate(lines, 1)) for lines in primary]
    failed = []
    for pi, p in enumerate(pages):
        wanted = {}
        for c in changes:
            if c["page"] == p["page"] and c["type"] == "deleted":
                wanted.setdefault(c["_line"], []).append(c)
        if not wanted:
            continue
        lines = primary[pi] if pi < len(primary) else []
        keys = [[i for i, ch in enumerate(l) if not SKIP_CHARS.match(ch)] for l in lines]
        texts = ["".join(l[i] for i in k) for l, k in zip(lines, keys)]
        gone = [set() for _ in lines]
        for li, found in sorted(wanted.items()):
            source, owner = [], []
            for ci, c in enumerate(p["lines"][li]):
                for ch in c["text"]:
                    if not SKIP_CHARS.match(ch):
                        source.append(ch); owner.append(ci)
            a = "".join(source)
            at = li / max(1, len(p["lines"])) * len(lines)
            scored = []
            for j, b in enumerate(texts):
                blocks = SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
                size = sum(m.size for m in blocks)
                if a and b and size >= 0.8 * min(len(a), len(b)):
                    scored.append((-size, bool(gone[j]), abs(j - at), j, blocks))
            todo = list(found)
            for *_, j, blocks in sorted(scored, key=lambda s: s[:4]):
                where = {m.a + k: m.b + k for m in blocks for k in range(m.size)}
                for c in list(todo):
                    spots = [n for n, ci in enumerate(owner) if ci in c["_index"]]
                    hit = [where.get(n) for n in spots]
                    if spots and None not in hit and hit[-1] - hit[0] == len(hit) - 1 and not set(hit) & gone[j]:
                        gone[j].update(hit); todo.remove(c)
                if not todo:
                    break
            failed += todo
        for j, spots in enumerate(gone):
            if not spots:
                continue
            drop = {keys[j][n] for n in spots}
            left = "".join(ch for i, ch in enumerate(lines[j]) if i not in drop)
            left = " | ".join(x for x in (" ".join(cell.split()) for cell in left.split("|")) if x)
            left = re.sub(r" +([.,;:)])", r"\1", left)
            if re.search(r"\w", left):
                current[pi][j + 1] = left
            else:
                del current[pi][j + 1]
    return current, failed


def public(change):
    return {k: v for k, v in change.items() if not k.startswith("_")}
