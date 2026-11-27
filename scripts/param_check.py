#!/usr/bin/env python3
"""Parameter consistency: number+unit values (EN + TR) bound to concepts, compared inside the target, with the references and with
the process model.

  param_check.py scan --target work/ex/target.txt [...] [--ref work/ex/ref.txt ...] [--model process_model.yaml]
                      [--concepts work/param_concepts.local.json] [-o work/params.json]       (also writes <out>.md)
  param_check.py verdict work/param_verdicts.json part.json
        part.json: {"P:reminder:time": {"verdict": "real|false-positive|legitimate-difference|tbd", "note": "evidence"}}

A conflict is a CANDIDATE: the model verifies each one in the document. Every conflict needs a verdict (matrix.py verify).
Concepts come from scripts/param_concepts.json; --concepts adds document-specific ones. Values that match no concept are listed,
not dropped. Limits: spelled-out numbers are recognised only up to twelve (EN) / on iki (TR) and only before time units.
"""
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from id_index import parse_lines, doc_stem
import progress

VERDICTS = ("real", "false-positive", "legitimate-difference", "tbd")
# (unit, dimension, regex). Longer / more specific forms first. Turkish suffixes are enumerated so "güncel" or "ayrı" do not match.
UNITS = [
    ("business-day", "time", r"(?:business|working)[\s-]+days?|iş[\s-]+gün(?:ü(?:nde|ne|dür)?|de|den|e|lük|ler(?:de|i)?|ün)?"),
    ("day", "time", r"(?:calendar[\s-]+)?days?|(?:takvim[\s-]+)?gün(?:ü(?:nde|ne|dür|nden)?|de|den|e|lük|lüğüne|ler(?:de|i)?|ün|dür)?"),
    ("week", "time", r"weeks?|hafta(?:da|dan|ya|yı|lık|lar(?:da)?|nın|sı(?:nda)?)?"),
    ("month", "time", r"months?|ay(?:da|dan|a|ı|ın|lık|lığına|lar(?:da)?|ında)?"),
    ("year", "time", r"years?|yıl(?:da|dan|a|ı|ın|lık|lığına|lar(?:da)?|ında)?"),
    ("hour", "time", r"hours?|saat(?:te|ten|e|i|in|lik|ler(?:de)?|inde)?"),
    ("minute", "time", r"minutes?|mins?|dakika(?:da|dan|ya|yı|lık|lar(?:da)?|nın)?|dk"),
    ("second", "time", r"seconds?|secs?|saniye(?:de|den|ye|lik)?|sn"),
    ("millisecond", "time", r"milliseconds?|milisaniye\w*|ms"),
    ("ECTS", "credits", r"ECTS|AKTS"),
    ("EUR", "money", r"€|EUR(?:O)?|euros?|avro(?:ya|luk)?"),
    ("USD", "money", r"\$|USD|dollars?"),
    ("TL", "money", r"₺|TL|lira(?:ya|lık)?"),
    ("%", "percent", r"%|percent"),
    ("MB", "size", r"MB"), ("GB", "size", r"GB"), ("KB", "size", r"KB"),
    ("character", "length", r"characters?|chars?|karakter(?:li|lik)?"),
]
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10, "on bir": 11, "on iki": 12}
NUM = r"\d+(?:[.,]\d+)*"
UNIT_ALT = "|".join(f"(?P<u{i}>(?:{rx})(?!\\w))" for i, (_, _, rx) in enumerate(UNITS))
POST = re.compile(rf"(?<![\w.,/-])(?P<num>{NUM}(?:\s*(?:-|–|to)\s*{NUM})?)\)?\s*(?:-\s*)?(?:{UNIT_ALT})", re.I)
PRE = re.compile(rf"(?:(?<![\w])(?P<sym>%|€|\$|₺)|\b(?P<code>EUR|USD|TL|yüzde)(?=\s))\s*(?P<num>{NUM})(?![\w])", re.I)
WORD_NUM = re.compile(r"(?<![\w-])(?P<num>" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")[\s-]+(?:" +
                      "|".join(f"(?P<u{i}>(?:{rx})(?!\\w))" for i, (_, d, rx) in enumerate(UNITS) if d == "time") + ")", re.I)
HARD_BREAK = re.compile(r"^\s*(?:[-•*]\s|\d+(?:\.\d+)*\.?\s+[A-ZÇĞİÖŞÜ]|[A-Z]{1,4}-[A-Z]?\.?\d|(?:Table|Tablo|Figure|Şekil|Screen|Ekran)\s+\d)")


def number(s):
    """'1.500,00' -> '1500'; '2,5' -> '2.5'; '3-5' stays a range."""
    parts = re.split(r"\s*(?:-|–|to)\s*", s)
    out = []
    for p in parts:
        if "." in p and "," in p:
            dec = "." if p.rfind(".") > p.rfind(",") else ","
            p = p.replace("," if dec == "." else ".", "").replace(dec, ".")
        elif re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", p):
            p = p.replace(".", "").replace(",", "")
        else:
            p = p.replace(",", ".")
        if "." in p:
            p = p.rstrip("0").rstrip(".")
        out.append(p)
    return "-".join(out)


def find_values(text):
    """[(start, end, value, unit, dimension)] without overlaps."""
    found = []

    def free(s, e):
        return all(e <= a or s >= b for a, b, *_ in found)

    for m in POST.finditer(text):
        i = next(int(k[1:]) for k, v in m.groupdict().items() if k.startswith("u") and v)
        found.append((m.start(), m.end(), number(m.group("num")), UNITS[i][0], UNITS[i][1]))
    for m in PRE.finditer(text):
        if free(m.start(), m.end()):
            token = (m.group("sym") or m.group("code")).lower()
            unit, dim = {"%": ("%", "percent"), "yüzde": ("%", "percent"), "€": ("EUR", "money"), "eur": ("EUR", "money"),
                         "$": ("USD", "money"), "usd": ("USD", "money"), "₺": ("TL", "money"), "tl": ("TL", "money")}[token]
            found.append((m.start(), m.end(), number(m.group("num")), unit, dim))
    for m in WORD_NUM.finditer(text):
        if free(m.start(), m.end()):
            i = next(int(k[1:]) for k, v in m.groupdict().items() if k.startswith("u") and v)
            found.append((m.start(), m.end(), str(WORDS[" ".join(m.group("num").lower().split())]), UNITS[i][0], UNITS[i][1]))
    return sorted(found)


def sentences(path):
    """[(text, [(offset, loc)])]: wrapped lines are joined; headings, bullets, ID lines and table rows start a new segment."""
    segs, text, marks = [], "", []

    def flush():
        nonlocal text, marks
        if text:
            start = 0
            for m in list(re.finditer(r"(?<=[.!?;])\s+(?=[A-ZÇĞİÖŞÜ])", text)) + [None]:
                end = m.start() if m else len(text)
                mk = [(max(o - start, 0), l) for i, (o, l) in enumerate(marks)
                      if o < end and (i + 1 == len(marks) or marks[i + 1][0] > start)]
                segs.append((text[start:end], mk))
                if m:
                    start = m.end()
        text, marks = "", []

    prev_page = None
    for loc, line in parse_lines(path):
        line = line.strip()
        page = loc.split(":")[0] if ":" in loc else None
        table = " | " in line
        if page != prev_page or table or HARD_BREAK.match(line) or re.fullmatch(r"(?:Page|Sayfa)\s+\d+", line):
            flush()
        prev_page = page
        if text:
            text += " "
        marks.append((len(text), loc)); text += line
        if table:
            flush()
    flush()
    return segs


def fold(s):
    return s.replace("İ", "i").lower()


def bind(sentence, start, end, concepts):
    """Concept whose keyword is nearest to the value inside the sentence (ties: longer keyword), or None."""
    low = fold(sentence); best = None
    for concept, words in concepts.items():
        for w in words:
            for m in re.finditer(r"(?<!\w)" + re.escape(fold(w)), low):
                dist = start - m.end() if m.end() <= start else m.start() - end if m.start() >= end else 0
                cand = (max(dist, 0), -len(w), concept)
                if best is None or cand < best:
                    best = cand
    return best[2] if best and best[0] <= 120 else None


def load_concepts(extra):
    base = json.loads((Path(__file__).parent / "param_concepts.json").read_text(encoding="utf-8"))["concepts"]
    for f in extra or []:
        for k, v in json.loads(Path(f).read_text(encoding="utf-8"))["concepts"].items():
            base[k] = sorted(set(base.get(k, [])) | set(v))
    return base


def occurrences(files, role, concepts):
    out = []
    for f in files:
        for sent, marks in sentences(f):
            for s, e, value, unit, dim in find_values(sent):
                loc = [l for o, l in marks if o <= s]
                out.append({"role": role, "doc": doc_stem(f), "loc": loc[-1] if loc else (marks[0][1] if marks else "?"), "value": value,
                            "unit": unit, "dimension": dim, "concept": bind(sent, s, e, concepts), "context": " ".join(sent.split())[:160]})
    return out


def model_parameters(path, concepts):
    try:
        import yaml
    except ImportError:
        return [], ["process model not compared: PyYAML is not available"]
    model = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    out, notes = [], []
    for p in model.get("parameters", []) or []:
        pid, quote = str(p.get("id", "")), str((p.get("source") or {}).get("quote", ""))
        unit = str(p.get("unit", ""))
        sample = find_values(f"{p.get('value')} {unit.replace('_', ' ')}")
        if sample:
            _, _, value, unit, dim = sample[0]
        else:
            value, dim = str(p.get("value")), ""
        named = re.sub(r"[-_]", " ", re.sub(r"^P-", "", pid))
        concept = bind(named, 0, 0, concepts) or bind(quote, 0, len(quote), concepts)
        if concept is None or not dim:
            notes.append(f"model parameter {pid} = {p.get('value')} {p.get('unit')} not matched to a concept/unit: compare by hand")
        else:
            out.append({"id": pid, "value": value, "unit": unit, "dimension": dim, "concept": concept})
    return out, notes


def conflicts(occ, params):
    groups = defaultdict(list)
    for o in occ:
        if o["concept"]:
            groups[(o["concept"], o["dimension"])].append(o)
    out = []
    fmt = lambda vals: sorted(f"{v} {u}" for v, u in vals)
    for (concept, dim), rows in sorted(groups.items()):
        t = {(o["value"], o["unit"]) for o in rows if o["role"] == "target"}
        r = {(o["value"], o["unit"]) for o in rows if o["role"] == "reference"}
        m = {(p["value"], p["unit"]) for p in params if p["concept"] == concept and p["dimension"] == dim}
        kinds = []
        if len(t) > 1: kinds.append("target-internal")
        if len(r) > 1: kinds.append("reference-internal")
        if t and r and t - r: kinds.append("target-vs-reference")
        if t and m and t - m: kinds.append("target-vs-model")
        if kinds:
            out.append({"id": f"P:{concept}:{dim}", "concept": concept, "dimension": dim, "kinds": kinds, "target_values": fmt(t),
                        "reference_values": fmt(r), "model_values": fmt(m),
                        "places": [f"{o['role']} {o['doc']} {o['loc']}: {o['value']} {o['unit']}" for o in rows]})
    return out


def evaluate(data, verdicts):
    """(rows, errors): every conflict needs a verdict with a note."""
    rows, errors = [], []
    for c in data["conflicts"]:
        v = (verdicts or {}).get(c["id"]) or {}
        if v.get("verdict") not in VERDICTS or not str(v.get("note", "")).strip():
            errors.append(f"parameter conflict without verdict: {c['id']} (target {c['target_values']}, reference {c['reference_values']})")
        rows.append({**c, "verdict": v.get("verdict", ""), "note": v.get("note", "")})
    return rows, errors


def cmd_scan(a):
    concepts = load_concepts(a.concepts)
    occ = occurrences(a.target, "target", concepts) + occurrences(a.ref or [], "reference", concepts)
    params, notes = model_parameters(a.model, concepts) if a.model else ([], [])
    data = {"conflicts": conflicts(occ, params), "occurrences": occ, "model_parameters": params, "notes": notes,
            "unassigned": sum(1 for o in occ if not o["concept"])}
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"# Parameter check: {len(occ)} values, {len(data['conflicts'])} conflict candidate(s), {data['unassigned']} value(s) without a concept", "", "## Conflicts (verify each one)"]
    for c in data["conflicts"]:
        L.append(f"- `{c['id']}` [{', '.join(c['kinds'])}] target: {', '.join(c['target_values']) or '—'} | reference: {', '.join(c['reference_values']) or '—'}"
                 + (f" | model: {', '.join(c['model_values'])}" if c["model_values"] else ""))
        L += [f"  - {p}" for p in c["places"]]
    if not data["conflicts"]: L.append("- (none)")
    L += ["", "## Values per concept"]
    per = defaultdict(list)
    for o in occ:
        if o["concept"]: per[o["concept"]].append(f"{o['value']} {o['unit']} ({o['role'][0]}:{o['doc']} {o['loc']})")
    L += [f"- **{k}**: " + "; ".join(v) for k, v in sorted(per.items())] or ["- (none)"]
    L += ["", "## Values without a concept (add concepts with --concepts if any of these is a parameter)"]
    L += [f"- {o['value']} {o['unit']} ({o['role']} {o['doc']} {o['loc']}): {o['context']}" for o in occ if not o["concept"]] or ["- (none)"]
    if notes: L += ["", "## Notes"] + [f"- {n}" for n in notes]
    out.with_suffix(".md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:L.index("## Values per concept")]))
    for n in notes: print("NOTE:", n)
    print(f"-> {out} (+ {out.with_suffix('.md').name})")


def cmd_verdict(a):
    cur = json.loads(Path(a.verdicts).read_text(encoding="utf-8")) if Path(a.verdicts).exists() else {}
    part = json.loads(Path(a.part).read_text(encoding="utf-8"))
    bad, done = [], []
    for k, v in part.items():
        if v.get("verdict") not in VERDICTS or not str(v.get("note", "")).strip():
            bad.append(f"{k}: verdict must be one of {VERDICTS} with a non-empty note"); continue
        cur[k] = v; done.append(k)
    Path(a.verdicts).write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    progress.checkpoint(Path(a.verdicts).parent, "param_verdicts", done)
    print(f"{len(done)} verdict(s) recorded")
    if bad:
        print("REJECTED:\n  " + "\n  ".join(bad)); sys.exit(1)


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("scan"); p.add_argument("--target", nargs="+", required=True); p.add_argument("--ref", nargs="*"); p.add_argument("--model")
    p.add_argument("--concepts", action="append"); p.add_argument("-o", "--out", default="work/params.json"); p.set_defaults(f=cmd_scan)
    p = sp.add_parser("verdict"); p.add_argument("verdicts"); p.add_argument("part"); p.set_defaults(f=cmd_verdict)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
