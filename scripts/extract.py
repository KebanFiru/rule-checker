#!/usr/bin/env python3
"""PDF/DOCX/TXT/MD -> text with page/line numbers. No third-party Python packages: PDF via poppler (`pdftotext`),
DOCX via the standard library (zipfile + ElementTree); .txt/.md/.csv are passed through line by line (no PDF tooling involved).

Output line format:  <location>\t<text>
  PDF  location: p<page>:L<line>   (table cells of one row are joined with ' | ')
  DOCX location: P<paragraph>  |  T<table>R<row>  (table row, cells joined with ' | ')
  TXT/MD location: L<line>
For DOCX also <stem>.json: tracked changes (ins/del, author) and comments (author, date, anchored text, location).
For PDF also <stem>.second.txt: the output of the other engine (pypdf or pdftotext), used as an independent second opinion.

Usage:
  extract.py FILE [FILE...] [-o OUT] [--engine pdftotext|pypdf] [--tables] [--docx-source SRC.docx] [--reading-order]
--docx-source:   the source DOCX of a PDF; verifies suspicious merged words from the PDF against the DOCX vocabulary.
--reading-order: use pdftotext's reading-order mode instead of -layout (better for multi-column pages, worse for tables).
--tables:        cell-level tables via pdfplumber when importable (page, table, row, column); otherwise a -layout fallback, reported as such.
"""
import argparse, json, re, shutil, subprocess, sys, unicodedata, zipfile
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


LIGATURES = str.maketrans({"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
                           "\ufb05": "st", "\ufb06": "st", "\u00ad": ""})


SPACES = str.maketrans({"\u00a0": " ", "\u2007": " ", "\u2009": " ", "\u202f": " ", "\t": " "})
CHUNK = re.compile(r"\S+(?: {1,2}\S+)*")        # words separated by at most 2 spaces form one cell


def clean(s):
    """Expand typographic ligatures, drop soft hyphens, turn exotic spaces into plain ones, NFC-compose accents
    (so searches and diffs behave identically across engines and versions)."""
    return unicodedata.normalize("NFC", s.translate(LIGATURES).translate(SPACES))


def layout_page_lines(text):
    """Lines of one page of -layout style text. Runs of 3+ spaces mean 'table cell boundary' ONLY when a neighbouring line has the
    same number of cells and every later cell lines up (same start or same end column, +-2). Elsewhere they are justification or
    indentation spacing (pdftotext and different pypdf versions emit different amounts of it) and collapse to one space, so all
    engines/versions agree."""
    cells = [[(m.start(), m.end(), m.group()) for m in CHUNK.finditer(l)] for l in text.splitlines()]

    def aligned(a, b):
        return len(a) == len(b) and all(abs(x[0] - y[0]) <= 2 or abs(x[1] - y[1]) <= 2 for x, y in zip(a[1:], b[1:]))

    out = []
    for i, cs in enumerate(cells):
        if not cs:
            continue
        tabular = len(cs) >= 2 and any(0 <= j < len(cells) and aligned(cs, cells[j]) for j in (i - 1, i + 1))
        out.append((" | " if tabular else " ").join(c[2] for c in cs))
    return out


def pdftotext(path, *flags):
    r = subprocess.run(["pdftotext", *flags, str(path), "-"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"pdftotext failed for {path}: {r.stderr.strip()}")
    return clean(r.stdout).split("\f")[:-1] or [""]


def pdf_pages(path, mode="layout"):
    """List of pages; each page is a list of non-empty lines. In layout mode aligned table columns are joined with ' | '."""
    out = []
    for pg in pdftotext(path, *(["-layout"] if mode == "layout" else []), "-enc", "UTF-8"):
        if mode == "layout":
            out.append(layout_page_lines(pg))
        else:
            out.append([" ".join(l.split()) for l in pg.splitlines() if l.strip()])
    return out


def pypdf_pages(path, layout=True):
    """Pure-Python engine (pypdf; layout mode, or the default content-order mode when layout=False). Returns (pages, errors) or (None, reason) when pypdf is unavailable/unusable."""
    try:
        import pypdf
    except ImportError:
        return None, "pypdf is not installed"
    try:
        r = pypdf.PdfReader(str(path))
        if r.is_encrypted and not r.decrypt(""):
            return None, "PDF is encrypted"
        pages, errors = [], []
        for i, pg in enumerate(r.pages, 1):
            try:
                txt = clean((pg.extract_text(extraction_mode="layout") if layout else pg.extract_text()) or "")
            except Exception as e:                      # one broken page must not kill the run
                txt, _ = "", errors.append(f"page {i}: {type(e).__name__}")
            pages.append(layout_page_lines(txt) if layout else [" ".join(l.split()) for l in txt.splitlines() if l.strip()])
        return pages, errors
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def engine_versions():
    """Versions of the available PDF engines (recorded in the metadata so runs on different environments can be compared)."""
    v = {}
    try:
        import importlib.metadata as md
        v["pypdf"] = md.version("pypdf")
    except Exception:
        pass
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True)
        v["pdftotext"] = ((r.stderr or r.stdout).strip().splitlines() or ["?"])[0].replace("pdftotext version ", "")
    return v


def pdf_tables(path, layout_pages):
    """Cell-level tables. With pdfplumber: real cells per table (page, table, row, column). Without it: fall back to the rows of the
    -layout text that contain ' | ' (cells are separated by runs of spaces in the PDF) and say so."""
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None
    if pdfplumber is not None:
        try:
            tables = []
            with pdfplumber.open(str(path)) as pdf:
                for pi, page in enumerate(pdf.pages, 1):
                    for ti, tb in enumerate(page.extract_tables(), 1):
                        tables.append({"page": pi, "table": ti, "rows": [[clean((c or "").replace("\n", " ")).strip() for c in row] for row in tb]})
            return {"engine": "pdfplumber", "tables": tables}
        except Exception as e:
            reason = f"pdfplumber failed ({type(e).__name__}: {e})"
    else:
        reason = "pdfplumber is not available"
    rows = [{"page": pi, "line": li, "cells": l.split(" | ")}
            for pi, lines in enumerate(layout_pages, 1) for li, l in enumerate(lines, 1) if " | " in l]
    return {"engine": "layout-fallback", "reason": reason,
            "note": "rows reconstructed from -layout text (cells separated by runs of spaces); cell boundaries are heuristic", "rows": rows}


def pdf_raw_pages(path):
    return [[l.strip() for l in pg.splitlines() if l.strip()] for pg in pdftotext(path, "-raw", "-enc", "UTF-8")]


def norm_tokens(lines):
    """Tokens for the engine comparison. Hyphens are removed first: pdftotext's non-layout modes join end-of-line hyphenation
    ("e-" + "mail" -> "email") while pypdf keeps "e-mail"; that is normalization, not a content difference."""
    s = ""
    for l in lines:                                   # a line ending in "-" continues without a space: "e-" + "mail" -> "email"
        s += l if s.endswith("-") else (" " + l)
    return re.findall(r"\w+", s.lower().replace("-", ""))


SPLIT_RX = re.compile(r"\b([A-Z]) ([a-z]{2,})\b")


def repair_splits(pages, other_pages):
    """Re-join kerning artifacts like 'T able' -> 'Table' (seen with pypdf 5.4 in content-order mode on LibreOffice PDFs; fixed in
    pypdf 6.x) using the OTHER engine as evidence: only when the other engine has the joined word and does not contain the split form,
    so text on which both engines agree is never touched. Returns a list of {page, from, to}."""
    repairs = []
    for pi, lines in enumerate(pages):
        other = " ".join(other_pages[pi]) if pi < len(other_pages) else ""
        vocab = set(re.findall(r"[^\W\d_]+", other.lower()))
        for li, line in enumerate(lines):
            def fix(m):
                joined = m.group(1) + m.group(2)
                if joined.lower() in vocab and m.group(0) not in other:
                    repairs.append({"page": pi + 1, "from": m.group(0), "to": joined})
                    return joined
                return m.group(0)
            lines[li] = SPLIT_RX.sub(fix, line)
    return repairs


def compare_engines(a, b):
    """Ignore reading-order differences; warn when the per-page token multisets differ (merged/split/missing words)."""
    warns = []
    for i in range(max(len(a), len(b))):
        ca = Counter(norm_tokens(a[i])) if i < len(a) else Counter()
        cb = Counter(norm_tokens(b[i])) if i < len(b) else Counter()
        if ca != cb:
            warns.append({"page": i + 1, "only_primary": sorted((ca - cb).elements())[:15],
                          "only_second": sorted((cb - ca).elements())[:15]})
    return warns


def docx_vocab(path):
    vocab = set()
    for blk in docx_blocks(path)[0]:
        vocab.update(w.lower() for w in WORD.findall(blk["text"]))
    return vocab


def suspicious_joined(pages, vocab):
    """PDF token missing from the DOCX vocabulary but splittable into two vocabulary words -> extraction artifact (merged words)."""
    found = {}
    for pi, lines in enumerate(pages, 1):
        for li, line in enumerate(lines, 1):
            for tok in WORD.findall(line):
                t = tok.lower()
                if len(t) < 7 or t in vocab:
                    continue
                for k in range(3, len(t) - 2):
                    if t[:k] in vocab and t[k:] in vocab:
                        found.setdefault(t, {"split": f"{t[:k]} {t[k:]}", "at": []})["at"].append(f"p{pi}:L{li}")
                        break
    return found


def docx_blocks(path):
    """(blocks, changes, comments). Blocks: {loc,text,style}."""
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
        comments = {}
        if "word/comments.xml" in z.namelist():
            for c in ET.fromstring(z.read("word/comments.xml")).iter(W + "comment"):
                cid = c.get(W + "id")
                txt = " ".join("".join(t.text or "" for t in p.iter(W + "t")) for p in c.iter(W + "p")).strip()
                comments[cid] = {"id": cid, "author": c.get(W + "author"), "date": c.get(W + "date"),
                                 "text": txt, "anchor_text": "", "loc": None}
    blocks, changes, open_c = [], [], set()

    def para_text(p, loc):
        out = []
        for el in p.iter():
            if el.tag == W + "commentRangeStart":
                cid = el.get(W + "id"); open_c.add(cid)
                if cid in comments and not comments[cid]["loc"]:
                    comments[cid]["loc"] = loc
            elif el.tag == W + "commentRangeEnd":
                open_c.discard(el.get(W + "id"))
            elif el.tag == W + "t":
                out.append(el.text or "")
                for cid in open_c:
                    if cid in comments:
                        comments[cid]["anchor_text"] += el.text or ""
            elif el.tag == W + "tab":
                out.append("\t")
        for kind in ("ins", "del"):
            for ch in p.iter(W + kind):
                txt = "".join((t.text or "") for t in ch.iter() if t.tag in (W + "t", W + "delText"))
                if txt.strip():
                    changes.append({"type": kind, "author": ch.get(W + "author"), "date": ch.get(W + "date"),
                                    "text": txt, "loc": loc})
        return "".join(out)

    pn = tn = 0
    for child in body:
        if child.tag == W + "p":
            pn += 1; loc = f"P{pn}"
            ps = child.find(f"{W}pPr/{W}pStyle")
            t = para_text(child, loc)
            if t.strip():
                blocks.append({"loc": loc, "text": t, "style": ps.get(W + "val") if ps is not None else ""})
        elif child.tag == W + "tbl":
            tn += 1
            for ri, tr in enumerate(child.iter(W + "tr"), 1):
                loc = f"T{tn}R{ri}"
                cells = [" ".join(para_text(p, loc) for p in tc.iter(W + "p")).strip() for tc in tr.findall(W + "tc")]
                blocks.append({"loc": loc, "text": " | ".join(cells), "style": "table"})
    return blocks, changes, list(comments.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", default="extracted")
    ap.add_argument("--docx-source", help="source DOCX of the PDF (merged-word verification)")
    ap.add_argument("--reading-order", action="store_true",
                    help="reading-order mode instead of layout mode, for BOTH engines (use it for multi-column pages; tables then come out cell by cell)")
    ap.add_argument("--tables", action="store_true",
                    help="also write <stem>.tables.json/.tables.txt (pdfplumber cells; falls back to -layout rows and says so)")
    ap.add_argument("--engine", choices=("pdftotext", "pypdf"), default="pdftotext",
                    help="primary PDF engine; the other one (if available) is used as an independent second opinion")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for f in a.files:
        f = Path(f); stem = f.stem
        meta = {"file": str(f), "warnings": []}
        if f.suffix.lower() == ".pdf":
            have_pdftotext = shutil.which("pdftotext") is not None
            if a.engine == "pdftotext":
                if not have_pdftotext:
                    sys.exit("pdftotext not found; use --engine pypdf")
                pages = pdf_pages(f, "reading" if a.reading_order else "layout")
                second, why = pypdf_pages(f, layout=not a.reading_order)
                second_name = "pypdf"
                if second is None:                       # no independent engine available: fall back to pdftotext -raw
                    second, second_name = pdf_raw_pages(f), "pdftotext-raw"
                    meta["warnings"].append(f"pypdf second opinion unavailable ({why}); compared with pdftotext -raw instead (not independent)")
            else:
                pages, why = pypdf_pages(f, layout=not a.reading_order)
                if pages is None:
                    sys.exit(f"pypdf failed for {f}: {why}")
                for e in why:
                    meta["warnings"].append(f"pypdf error on {e}")
                second_name = "pdftotext" if have_pdftotext else None
                second = pdf_pages(f, "reading" if a.reading_order else "layout") if have_pdftotext else None
            meta["engines"] = {"primary": a.engine, "second_opinion": second_name, "versions": engine_versions()}
            if second is not None:
                rep_p, rep_s = repair_splits(pages, second), repair_splits(second, pages)
                if rep_p or rep_s:
                    meta["repairs"] = {"primary": rep_p, "second_opinion": rep_s}
                    print(f"  NOTE: re-joined {len(rep_p)} split word(s) in the {a.engine} text and {len(rep_s)} in the {second_name} text using the other engine as evidence (e.g. {(rep_p + rep_s)[0]['from']!r} -> {(rep_p + rep_s)[0]['to']!r}); see meta 'repairs'")
            meta["pages"] = len(pages)
            empty = [i + 1 for i, p in enumerate(pages) if not p]
            if empty:
                meta["warnings"].append(f"Page(s) {empty} have no text layer (blank or scanned/image-only): read those pages with the Read tool (pages parameter)")
            if second is not None:
                diffs = compare_engines(pages, second)
                if len(second) != len(pages):
                    meta["warnings"].append(f"Page count differs between engines: {a.engine}={len(pages)} {second_name}={len(second)}")
                if diffs:
                    meta["engine_diffs"] = diffs
                    meta["warnings"].append(f"{a.engine} and {second_name} produced different word sets on {len(diffs)} page(s) (merge/split possible); see engine_diffs")
                with open(out / f"{stem}.second.txt", "w", encoding="utf-8") as fh:
                    for pi, lines in enumerate(second, 1):
                        for li, l in enumerate(lines, 1):
                            fh.write(f"p{pi}:L{li}\t{l}\n")
            with open(out / f"{stem}.txt", "w", encoding="utf-8") as fh:
                for pi, lines in enumerate(pages, 1):
                    for li, l in enumerate(lines, 1):
                        fh.write(f"p{pi}:L{li}\t{l}\n")
            if a.tables:
                tb = pdf_tables(f, pages)
                meta["tables"] = {k: v for k, v in tb.items() if k not in ("tables", "rows")}
                (out / f"{stem}.tables.json").write_text(json.dumps(tb, ensure_ascii=False, indent=1), encoding="utf-8")
                with open(out / f"{stem}.tables.txt", "w", encoding="utf-8") as fh:
                    if tb["engine"] == "pdfplumber":
                        for T in tb["tables"]:
                            for ri, row in enumerate(T["rows"], 1):
                                for ci, c in enumerate(row, 1):
                                    fh.write(f"p{T['page']}:T{T['table']}R{ri}C{ci}\t{c}\n")
                    else:
                        for r in tb["rows"]:
                            fh.write(f"p{r['page']}:L{r['line']}\t{' | '.join(r['cells'])}\n")
                if tb["engine"] != "pdfplumber":
                    meta["warnings"].append(f"--tables: {tb['reason']}; table rows come from the -layout text (cells split by runs of spaces)")
            if a.docx_source:
                sj = suspicious_joined(pages, docx_vocab(a.docx_source))
                meta["joined_words_extraction_artifacts"] = sj
                if sj:
                    meta["warnings"].append(
                        f"{len(sj)} suspicious merged word(s): the source DOCX may spell them separately -> do not report as a document error, verify against the DOCX")
        elif f.suffix.lower() == ".docx":
            blocks, changes, comments = docx_blocks(f)
            with open(out / f"{stem}.txt", "w", encoding="utf-8") as fh:
                for b in blocks:
                    fh.write(f"{b['loc']}\t{b['text']}\n")
            meta.update({"tracked_changes": changes, "comments": comments, "blocks": len(blocks)})
        elif f.suffix.lower() in (".txt", ".md", ".csv"):
            lines = [l.rstrip() for l in f.read_text(encoding="utf-8", errors="replace").splitlines()]
            with open(out / f"{stem}.txt", "w", encoding="utf-8") as fh:
                for i, l in enumerate(lines, 1):
                    if l.strip():
                        fh.write(f"L{i}\t{l.strip()}\n")
            meta["lines"] = len(lines)
        else:
            print(f"Unsupported type: {f}", file=sys.stderr); continue
        (out / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{f} -> {out/stem}.txt  warnings={len(meta['warnings'])}"
              + (f" tracked_changes={len(meta.get('tracked_changes', []))} comments={len(meta.get('comments', []))}" if f.suffix.lower() == '.docx' else ""))
        for w in meta["warnings"]:
            print("  WARNING:", w)


if __name__ == "__main__":
    main()
