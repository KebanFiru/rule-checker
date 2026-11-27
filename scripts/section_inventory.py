#!/usr/bin/env python3
"""Section structure of the reference documents (what must be classified BEFORE rules are extracted) and document identity.

  section_inventory.py scan ref.txt [...] ["target.txt@Appendix B"] [-o work/ref_sections.json]   ("@name": only that section and its
        subsections, for a section of the target used as a reference). From extract.py output (.txt): numbered / appendix /
        markdown headings, table captions, page ranges, and signals (numbers, durations, shall/must/zorunlu/gerekir).
        Text before the first heading is its own section; a document without headings gets one section per page.
  section_inventory.py classify work/ref_sections.json classes.json
        classes.json: {"<section id>": {"class": "rule-bearing|fact|open-question|descriptive-only", "reason": "one line"}}
        reason is required for descriptive-only and open-question. A re-scan keeps existing classifications.
  section_inventory.py identity --target work/ex/target.txt --files FILE... --names "Ek B" "PAR" [--map "charter=file.pdf"]
        [--confirmed "Ek B=user's answer"] [--lang en|tr] [-o work/doc_identity.json]
        matches every document the USER NAMED with an uploaded file; if there is none but the target has a section of that name,
        says so (the note must appear at the top of the report) and flags the circular check.

Rules and facts point to their section with source.section = "<section id>"; the report counts them per section.
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from id_index import parse_lines
import progress

CLASSES = ("rule-bearing", "fact", "open-question", "descriptive-only")
NUMBERED = re.compile(r"^(\d{1,3}(?:\.\d{1,3})*)\.?\s+([A-ZÇĞİÖŞÜ\"«(].*)$")
APPENDIX = re.compile(r"^(Appendix|Annex|EK|Ek)\s*[-:]?\s*([A-Z]|\d{1,2})\b\s*[-:.–—]?\s*(.*)$")
MARKDOWN = re.compile(r"^(#{1,6})\s+(.*)$")
TABLE = re.compile(r"^(?:Table|Tablo)\s+[A-Z]?\d+(?:\.\d+)*\b.*$")
MODAL = re.compile(r"\b(?:shall|must|required|mandatory|zorunlu\w*|gerekir|gerekmektedir|gerekli\w*|şarttır)\b|\b\w+m[ae]l[ıi](?:dır|dir)?\b", re.I)
DURATION = re.compile(r"\b(?:\d+|one|two|three|four|five|six|seven|ten|iki|üç|dört|beş|on)\s*[-)]?\s*(?:business\s+|working\s+|iş\s+)?(?:days?|weeks?|months?|years?|hours?|minutes?|gün\w*|hafta\w*|ay\b|yıl\w*|saat\w*|dakika\w*)", re.I)


def heading(text):
    """(number, title, kind, level) or None."""
    if len(text) > 100 or "...." in text or " | " in text:
        return None
    m = MARKDOWN.match(text)
    if m:
        return "", m.group(2).strip(), "heading", len(m.group(1))
    m = APPENDIX.match(text)
    if m and not text.rstrip().endswith((".", ";", ",")):
        return f"Appendix {m.group(2)}", m.group(3).strip() or text.strip(), "appendix", 1
    m = NUMBERED.match(text)
    if m and not text.rstrip().endswith((".", ";", ":", ",")) and not re.search(r"\s\d+$", text):
        return m.group(1), m.group(2).strip(), "heading", m.group(1).count(".") + 1
    return None


def page_of(loc):
    m = re.match(r"p(\d+):", loc)
    return int(m.group(1)) if m else None


def signals(body):
    text = " ".join(body)
    plain = re.sub(r"\b[A-Z]{1,4}-[A-Z]?\.?\d+(?:\.\d+)*\b", " ", text)          # digits inside IDs are not values
    plain = re.sub(r"\b(?:Page|Sayfa)\s+\d+\b", " ", plain)
    return {"numbers": len(re.findall(r"\d+(?:[.,]\d+)*", plain)), "durations": len(DURATION.findall(text)),
            "modal": sorted({m.group(0).lower() for m in MODAL.finditer(text)})}


def scan_doc(path):
    doc = Path(path).stem
    lines = list(parse_lines(path))
    secs, cur, used = [], None, {}

    def start(number, title, kind, level, loc):
        nonlocal cur
        base = f"{doc}#{number or title[:40]}"
        used[base] = used.get(base, 0) + 1
        sid = base if used[base] == 1 else f"{base}~{used[base]}"
        cur = {"id": sid, "doc": doc, "number": number, "title": title, "kind": kind, "level": level, "start": loc, "end": loc,
               "pages": [], "tables": [], "_body": []}
        secs.append(cur)

    has_headings = any(heading(t) for _, t in lines)
    for loc, text in lines:
        text = text.strip()
        h = heading(text) if has_headings else None
        pg = page_of(loc)
        if h:
            start(*h, loc)
        elif not has_headings and pg is not None and (cur is None or pg not in cur["pages"]):
            start(f"p{pg}", f"page {pg} (document has no headings)", "page", 1, loc)
        elif cur is None:
            start("(preamble)", "text before the first heading", "preamble", 1, loc)
        if not h:
            if TABLE.match(text):
                cur["tables"].append(text)
            cur["_body"].append(text)
        cur["end"] = loc
        if pg is not None and pg not in cur["pages"]:
            cur["pages"].append(pg)
    for s in secs:
        body = [t for t in s.pop("_body") if not re.fullmatch(r"(?:Page|Sayfa)\s+\d+|\d+", t)]
        s["lines"] = len(body); s["signals"] = signals(body + ([s["title"]] if s["kind"] != "page" else []))
        s["class"], s["reason"] = ("descriptive-only", "heading only, no body text of its own") if not body else ("", "")
    return secs


def only_section(secs, name):
    """The section called `name` (e.g. 'Appendix B', 'Ek B') plus the deeper sections that follow it."""
    want = tokens(name)
    for i, s in enumerate(secs):
        if tokens(f"{s['number']} {s['title']}")[:len(want)] == want:
            out = [s]
            for t in secs[i + 1:]:
                if t["level"] <= s["level"]:
                    break
                out.append(t)
            return out
    sys.exit(f"section {name!r} not found; headings: " + "; ".join(f"{s['number']} {s['title']}" for s in secs))


def evaluate(data, rules, fact_prefix="F"):
    """(per-section rows, errors, warnings). rules: the rule/fact register (list)."""
    secs = data["sections"]; ids = {s["id"] for s in secs}
    by = {}
    errors, warnings = [], []
    for r in rules:
        sid = (r.get("source") or {}).get("section")
        kind = "fact" if r.get("kind") == "fact" or r["id"].startswith(fact_prefix + "-") else "rule"
        if not sid:
            errors.append(f"{r['id']}: source.section is missing (which reference section does it come from?)"); continue
        if sid not in ids:
            errors.append(f"{r['id']}: source.section {sid!r} is not in the section inventory"); continue
        by.setdefault(sid, {"rule": [], "fact": []})[kind].append(r["id"])
    rows = []
    for s in secs:
        got = by.get(s["id"], {"rule": [], "fact": []}); c = s.get("class", "")
        if c not in CLASSES:
            errors.append(f"reference section not classified: {s['id']} «{s['title'][:50]}»")
        elif c == "rule-bearing" and not got["rule"]:
            errors.append(f"{s['id']}: rule-bearing but no rule was extracted from it")
        elif c == "fact" and not got["fact"]:
            errors.append(f"{s['id']}: class 'fact' but no fact record points to it")
        elif c in ("descriptive-only", "open-question") and not str(s.get("reason", "")).strip():
            errors.append(f"{s['id']}: {c} needs a one-line reason")
        sg = s["signals"]
        if c == "descriptive-only" and (sg["numbers"] or sg["durations"] or sg["modal"]):
            what = ([f"{sg['numbers']} number(s)"] if sg["numbers"] else []) + ([f"{sg['durations']} duration(s)"] if sg["durations"] else []) \
                + ([", ".join(sg["modal"])] if sg["modal"] else [])
            warnings.append(f"{s['id']} is 'descriptive-only' but contains {'; '.join(what)}")
        rows.append({**s, "rules": got["rule"], "facts": got["fact"]})
    return rows, errors, warnings


def cmd_scan(a):
    out = Path(a.out)
    old = {s["id"]: s for s in json.loads(out.read_text(encoding="utf-8"))["sections"]} if out.exists() else {}
    secs = []
    for f in a.files:
        path, _, name = f.partition("@")
        secs += only_section(scan_doc(path), name) if name else scan_doc(path)
    for s in secs:
        o = old.get(s["id"])
        if o and o.get("class"):
            s["class"], s["reason"] = o["class"], o.get("reason", "")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"sections": secs}, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in secs:
        sg = s["signals"]
        pg = f"p{s['pages'][0]}-{s['pages'][-1]}" if s["pages"] else s["start"]
        print(f"{s['id']:<34} {pg:<8} lines={s['lines']:<3} num={sg['numbers']:<3} dur={sg['durations']:<2} modal={','.join(sg['modal'])[:30]:<30} {s['class'] or '(classify)'}  «{s['title'][:50]}»")
    print(f"{len(secs)} sections, {sum(1 for s in secs if not s['class'])} to classify -> {out}")


def cmd_classify(a):
    data = json.loads(Path(a.sections).read_text(encoding="utf-8"))
    part = json.loads(Path(a.classes).read_text(encoding="utf-8"))
    by = {s["id"]: s for s in data["sections"]}
    bad, done = [], []
    for sid, v in part.items():
        if sid not in by:
            bad.append(f"{sid}: unknown section"); continue
        if v.get("class") not in CLASSES:
            bad.append(f"{sid}: class must be one of {CLASSES}"); continue
        if v["class"] in ("descriptive-only", "open-question") and not str(v.get("reason", "")).strip():
            bad.append(f"{sid}: {v['class']} needs a one-line reason"); continue
        by[sid]["class"], by[sid]["reason"] = v["class"], str(v.get("reason", "")).strip(); done.append(sid)
    Path(a.sections).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    progress.checkpoint(Path(a.sections).parent, "sections", done)
    left = [s["id"] for s in data["sections"] if s.get("class") not in CLASSES]
    print(f"{len(done)} classified; still unclassified: {len(left)}" + (f" ({', '.join(left[:10])}{' …' if len(left) > 10 else ''})" if left else ""))
    if bad:
        print("REJECTED:\n  " + "\n  ".join(bad)); sys.exit(1)


# ---------- document identity ----------
SYN = {"ek": "appendix", "annex": "appendix", "lahika": "appendix"}


def tokens(s):
    s = re.sub(r"([a-zçğıöşü])([A-ZÇĞİÖŞÜ])", r"\1 \2", s)
    return [SYN.get(t, t) for t in re.findall(r"[^\W_]+", s.replace("İ", "i").lower())]


def matches_file(name, path):
    n, f = tokens(name), tokens(Path(path).stem)
    if not n:
        return False
    contiguous = any(f[i:i + len(n)] == n for i in range(len(f) - len(n) + 1))
    compact = "".join(n)
    return contiguous or compact in f or (len(compact) >= 5 and compact in "".join(f))


def internal_section(name, target_lines):
    n = tokens(name)
    for loc, text in target_lines:
        h = heading(text.strip())
        if not h:
            continue
        number, title, kind, _ = h
        t = tokens(f"{number} {title}") if kind == "appendix" else tokens(title)
        if t[:len(n)] == n:
            return {"loc": loc, "heading": text.strip()}
    return None


def note_for(e, target, lang):
    name, sec = e["name"], (e.get("internal_section") or {}).get("heading", "")
    tr = lang == "tr"
    if e["status"] == "file":
        return f"«{name}» → {e['file']}" + (" (hedef belgenin kendisi: döngüsel kontrol)" if tr and e["self_reference"] else " (the target itself: circular check)" if e["self_reference"] else "")
    if e["status"] == "internal-section":
        return (f"«{name}» ayrı dosya olarak verilmedi; {target} belgesinin kendi «{sec}» bölümü kullanıldı (kaynak varsayımı; döngüsel kontrol: hedef kendini doğruluyor)." if tr else
                f"«{name}» was not provided as a separate file; the section «{sec}» of {target} itself was used (source assumption; circular check: the target is verifying itself).")
    return (f"«{name}» ayrı dosya olarak verilmedi ve hedefte aynı adlı bölüm yok; bu belgeye dayanan kontroller yapılamadı." if tr else
            f"«{name}» was not provided as a file and the target has no section of that name; checks that depend on it could not be done.")


def cmd_identity(a):
    mapping = dict(x.split("=", 1) for x in a.map or [])
    confirmed = dict(x.split("=", 1) for x in a.confirmed or [])
    target = Path(a.target).stem
    lines = list(parse_lines(a.target))
    docs = []
    for name in a.names:
        files = [mapping[name]] if name in mapping else [f for f in a.files if matches_file(name, f)]
        e = {"name": name, "file": None, "internal_section": None, "self_reference": False, "status": "missing", "candidates": [Path(f).name for f in files]}
        if len(files) > 1:
            sys.exit(f"«{name}» matches several files ({', '.join(e['candidates'])}): ask the user, then pass --map \"{name}=<file>\"")
        if files:
            e.update(status="file", file=Path(files[0]).name, self_reference=Path(files[0]).stem == target)
        else:
            sec = internal_section(name, lines)
            if sec:
                e.update(status="internal-section", internal_section=sec, self_reference=True)
        e["user_answer"] = confirmed.get(name, "")
        e["note"] = note_for(e, target, a.lang) + (f" [{'kullanıcı yanıtı' if a.lang == 'tr' else 'user answer'}: {e['user_answer']}]" if e["user_answer"] else "")
        docs.append(e)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"target": target, "documents": docs}, ensure_ascii=False, indent=1), encoding="utf-8")
    for e in docs:
        ask = e["status"] != "file" and not e["user_answer"]
        print(f"{e['status']:<16} {e['note']}" + ("\n  -> ASK the user now; if unavailable keep this note at the top of the report" if ask else ""))
        if e["status"] == "internal-section":
            print(f"  -> add it to the section inventory: section_inventory.py scan <refs> \"{a.target}@{e['internal_section']['heading']}\"")
    print(f"-> {out}")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("scan"); p.add_argument("files", nargs="+"); p.add_argument("-o", "--out", default="work/ref_sections.json"); p.set_defaults(f=cmd_scan)
    p = sp.add_parser("classify"); p.add_argument("sections"); p.add_argument("classes"); p.set_defaults(f=cmd_classify)
    p = sp.add_parser("identity"); p.add_argument("--target", required=True); p.add_argument("--files", nargs="+", required=True); p.add_argument("--names", nargs="+", required=True)
    p.add_argument("--map", action="append"); p.add_argument("--confirmed", action="append"); p.add_argument("--lang", choices=("en", "tr"), default="en")
    p.add_argument("-o", "--out", default="work/doc_identity.json"); p.set_defaults(f=cmd_identity)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
