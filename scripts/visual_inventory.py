#!/usr/bin/env python3
"""Which pages MUST be looked at in the visual pass, and the log that proves they were.

  visual_inventory.py scan target.pdf [more.pdf] [-o work/visual_inventory.json] [--patterns P] [--min-draw 6] [--min-text 200]
        per page: embedded images (pypdf), vector drawing density, very short text, Figure/Screen/Şekil/Ekran/S-x.y/Diagram
        captions -> type (screen|diagram|data-model|table|other), related IDs, priority. Prints Read-tool batches (<= 20 pages).
        Also creates work/visual_log.json with one unchecked row per inventory page (existing rows are kept).
  visual_inventory.py record work/visual_log.json part.json      merge rows (checkpoint after every Read batch)
  visual_inventory.py status work/visual_inventory.json work/visual_log.json

Log row: {"page": 11, "doc": "target", "ids": ["S-1.5"], "checked": true, "method": "Read pages 1-20",
          "findings": "...", "skipped_reason": ""}   ("doc" is only needed when the inventory has several documents)
A checked row needs method and findings; an unchecked row is only accepted with a skipped_reason (it is counted in the report).
"""
import argparse, json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from id_index import load_patterns, norm_id
import progress

PAINT = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
CAPTION = re.compile(r"^\s*(?:(?:Figure|Fig\.|Screen|Şekil|Ekran|Diagram|Diyagram)\s*[-:]?\s*(?:[A-Z]{1,3}[-.]?)?\d|S-\d+(?:\.\d+)*\b)", re.I)
TABLE_CAPTION = re.compile(r"^\s*(?:Table|Tablo)\s+[A-Z]?\d", re.I)
KINDS = [("data-model", r"data[\s-]model|veri\s+model|entity[\s-]relationship|\bER\s+diagram|class\s+diagram|sınıf\s+diyagram|varlık[\s-]ilişki"),
         ("diagram", r"diagram|diyagram|flow\s?chart|process\s+flow|akış\s+(?:şema|diyagram)|\bBPMN\b|sequence"),
         ("screen", r"\bscreen|\bekran|wire\s?frame|mock-?up|^\s*S-\d")]


def walk(stream_owner, resources, reader, ContentStream, seen):
    """(image object keys drawn, number of path-painting operators); recurses into form XObjects."""
    images, paint = [], 0
    if stream_owner is None:
        return images, paint
    xobjects = {}
    if resources is not None and "/XObject" in resources.get_object():
        xobjects = resources.get_object()["/XObject"].get_object()
    for operands, op in ContentStream(stream_owner, reader).operations:
        if op in PAINT:
            paint += 1
        elif op == b"INLINE IMAGE":
            images.append("inline")
        elif op == b"Do" and operands and operands[0] in xobjects:
            ref = xobjects.raw_get(operands[0]); obj = ref.get_object()
            key = str(getattr(ref, "idnum", operands[0]))
            if obj.get("/Subtype") == "/Image":
                images.append(key)
            elif obj.get("/Subtype") == "/Form" and key not in seen:
                i, p = walk(obj, obj.get("/Resources", resources), reader, ContentStream, seen | {key})
                images += i; paint += p
    return images, paint


def read_pdf(path):
    """[{text, images (list or None), paint (int or None), error}], warnings."""
    try:
        import pypdf
        from pypdf.generic import ContentStream
    except ImportError:
        import shutil, subprocess
        if not shutil.which("pdftotext"):
            sys.exit("neither pypdf nor pdftotext is available: the visual inventory cannot be built; read every page with the Read tool")
        r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, text=True)
        pages = [{"text": t, "images": None, "paint": None, "error": ""} for t in r.stdout.split("\f")[:-1]]
        return pages, [f"{path.name}: pypdf is not available, embedded images and drawings were NOT detected (only captions and short pages)"]
    reader = pypdf.PdfReader(str(path))
    if reader.is_encrypted:
        reader.decrypt("")
    pages, warnings = [], []
    for n, page in enumerate(reader.pages, 1):
        row = {"text": "", "images": [], "paint": 0, "error": ""}
        try:
            row["text"] = page.extract_text() or ""
            row["images"], row["paint"] = walk(page.get_contents(), page.get("/Resources"), reader, ContentStream, set())
        except Exception as e:                      # an unreadable page goes INTO the inventory, never silently out
            row["error"] = type(e).__name__
            warnings.append(f"{path.name} page {n}: could not be analysed ({type(e).__name__}); added to the inventory")
        pages.append(row)
    return pages, warnings


def classify(text, has_image, has_drawing):
    lines = text.splitlines()
    captions = [" ".join(l.split()) for l in lines if CAPTION.match(l)]
    tables = [" ".join(l.split()) for l in lines if TABLE_CAPTION.match(l)]
    scope = "\n".join(captions) if captions else (text if has_image or has_drawing else "")
    kind = next((k for k, rx in KINDS if re.search(rx, scope, re.I | re.M)), None)
    if kind is None:
        kind = "table" if tables and not has_image else "screen" if has_image else "other"
    return kind, captions, tables


def scan_doc(path, patterns, min_draw, min_text):
    raw, warnings = read_pdf(path)
    uses = Counter(k for r in raw for k in set(r["images"] or []) if k != "inline")
    limit = max(5, int(0.6 * len(raw) + 0.999))
    decorative = {k for k, n in uses.items() if n >= limit}       # logos / header graphics repeated on most pages
    out, deco_only = [], []
    for n, r in enumerate(raw, 1):
        imgs = None if r["images"] is None else [k for k in r["images"] if k not in decorative]
        n_img = None if imgs is None else len(imgs)
        drawing = None if r["paint"] is None else r["paint"] >= min_draw
        kind, captions, tables = classify(r["text"], bool(n_img), bool(drawing))
        short = len("".join(r["text"].split())) < min_text
        reasons = ([f"images:{n_img}"] if n_img else []) + (["vector-drawing"] if drawing else []) + (["short-text"] if short else []) \
            + (["caption"] if captions else []) + (["table-caption"] if tables else []) + (["unreadable"] if r["error"] else [])
        if not reasons:
            if r["images"]:
                deco_only.append(n)
            continue
        ids = sorted({norm_id(m.group(0)) for _, rx in patterns for m in rx.finditer(r["text"])})
        priority = "high" if kind in ("screen", "diagram", "data-model") else "medium" if kind == "table" or n_img or drawing else "low"
        out.append({"doc": path.stem, "page": n, "type": kind, "priority": priority, "ids": ids, "image_count": n_img,
                    "drawing": drawing, "short_text": short, "captions": captions, "reasons": reasons})
    info = {"doc": path.stem, "file": path.name, "pages_total": len(raw), "decorative_images": len(decorative), "decorative_only_pages": deco_only,
            "images_detected": all(r["images"] is not None for r in raw)}
    return info, out, warnings


def batches(pages, size=20):
    """Greedy windows of at most `size` consecutive page numbers covering all wanted pages: ["1-12", "31-49"]."""
    out, todo = [], sorted(set(pages))
    while todo:
        first = todo[0]; inside = [p for p in todo if p < first + size]
        out.append(str(first) if len(inside) == 1 else f"{first}-{inside[-1]}")
        todo = todo[len(inside):]
    return out


def key(row, docs):
    return (row.get("doc") or (docs[0] if len(docs) == 1 else None), int(row["page"]))


def evaluate(inv, log):
    """(checked, skipped, missing, errors) over the inventory pages. missing/errors make verify fail."""
    docs = [d["doc"] for d in inv["documents"]]
    rows = {}
    errors = []
    for r in log or []:
        try:
            rows[key(r, docs)] = r
        except (KeyError, TypeError, ValueError):
            errors.append(f"visual log row without a usable page number: {r}")
    checked, skipped, missing = [], [], []
    for p in inv["pages"]:
        k = (p["doc"], p["page"]); r = rows.get(k); name = f"{p['doc']} p{p['page']}"
        if r is None:
            missing.append(name); continue
        if r.get("checked") is True:
            if "read" not in str(r.get("method", "")).lower() or not str(r.get("findings", "")).strip():
                errors.append(f"{name}: checked pages need method 'Read pages …' and non-empty findings (write 'no differences: …' if none)")
                missing.append(name)
            else:
                checked.append(name)
        elif str(r.get("skipped_reason", "")).strip():
            skipped.append((name, r["skipped_reason"].strip()))
        else:
            missing.append(name)
    return checked, skipped, missing, errors


def cmd_scan(a):
    pats, _ = load_patterns(a.patterns)
    inv = {"documents": [], "pages": [], "warnings": []}
    for f in a.pdfs:
        info, pages, warnings = scan_doc(Path(f), pats, a.min_draw, a.min_text)
        inv["documents"].append(info); inv["pages"] += pages; inv["warnings"] += warnings
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    log_path = out.with_name("visual_log.json")
    old = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    docs = [d["doc"] for d in inv["documents"]]
    have = {key(r, docs) for r in old}
    new = [{"doc": p["doc"], "page": p["page"], "ids": p["ids"], "checked": False, "method": "", "findings": "", "skipped_reason": ""}
           for p in inv["pages"] if (p["doc"], p["page"]) not in have]
    log_path.write_text(json.dumps(old + new, ensure_ascii=False, indent=1), encoding="utf-8")
    for d in inv["documents"]:
        mine = [p for p in inv["pages"] if p["doc"] == d["doc"]]
        kinds = Counter(p["type"] for p in mine)
        print(f"{d['file']}: {len(mine)}/{d['pages_total']} pages need the visual pass — " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))
        print("  Read batches (pages parameter): " + (" ; ".join(batches([p['page'] for p in mine])) or "(none)"))
        for p in mine:
            print(f"  p{p['page']:<4} {p['type']:<10} {p['priority']:<6} {','.join(p['reasons'])}  {' '.join(p['ids'][:8])}")
        if d["decorative_images"]:
            print(f"  note: {d['decorative_images']} image(s) repeated on most pages treated as decoration; pages with nothing else: {d['decorative_only_pages']}")
    for w in inv["warnings"]:
        print("  WARNING:", w)
    print(f"-> {out} ; {log_path} ({len(new)} new unchecked row(s))")


def cmd_record(a):
    log = json.loads(Path(a.log).read_text(encoding="utf-8")) if Path(a.log).exists() else []
    part = json.loads(Path(a.part).read_text(encoding="utf-8"))
    docs = sorted({r["doc"] for r in log if r.get("doc")})
    index = {key(r, docs): i for i, r in enumerate(log)}
    bad, done = [], []
    for r in part:
        if "page" not in r:
            bad.append(f"row without page: {r}"); continue
        k = key(r, docs)
        if k not in index:
            bad.append(f"page {r['page']} (doc {k[0]}) is not in the log/inventory"); continue
        if r.get("checked") is True and not (str(r.get("method", "")).strip() and str(r.get("findings", "")).strip()):
            bad.append(f"page {r['page']}: checked rows need method and findings"); continue
        if r.get("checked") is not True and not str(r.get("skipped_reason", "")).strip():
            bad.append(f"page {r['page']}: unchecked rows need skipped_reason"); continue
        log[index[k]] = {**log[index[k]], **r}; done.append(f"{k[0]}:p{k[1]}")
    Path(a.log).write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    progress.checkpoint(Path(a.log).parent, "visual_pages", done)
    print(f"{len(done)} page(s) recorded")
    if bad:
        print("REJECTED:\n  " + "\n  ".join(bad)); sys.exit(1)


def cmd_status(a):
    inv = json.loads(Path(a.inventory).read_text(encoding="utf-8"))
    log = json.loads(Path(a.log).read_text(encoding="utf-8")) if Path(a.log).exists() else []
    checked, skipped, missing, errors = evaluate(inv, log)
    print(f"Visual coverage: {len(checked)}/{len(inv['pages'])} pages; skipped with reason: {len(skipped)}; still open: {len(missing)}")
    for doc in [d["doc"] for d in inv["documents"]]:
        todo = [int(m.rsplit(" p", 1)[1]) for m in missing if m.rsplit(" p", 1)[0] == doc]
        if todo:
            print(f"  {doc}: next Read batches: " + " ; ".join(batches(todo)))
    for e in errors:
        print("  " + e)


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("scan"); p.add_argument("pdfs", nargs="+"); p.add_argument("-o", "--out", default="work/visual_inventory.json"); p.add_argument("--patterns")
    p.add_argument("--min-draw", type=int, default=6); p.add_argument("--min-text", type=int, default=200); p.set_defaults(f=cmd_scan)
    p = sp.add_parser("record"); p.add_argument("log"); p.add_argument("part"); p.set_defaults(f=cmd_record)
    p = sp.add_parser("status"); p.add_argument("inventory"); p.add_argument("log"); p.set_defaults(f=cmd_status)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
