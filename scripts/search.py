#!/usr/bin/env python3
"""Many searches in ONE call (instead of one grep per term).

  search.py work/ex/target.txt [...] -t "term one" -t "term two" [-f terms.txt] [--regex] [--max 8]
        for every term/regex: location, the matching line and one line of context on each side.
  search.py work/ex/target.txt --rules work/rules.json --block 1 [--size 20]       candidates for rules 1-20 (by their keywords)
  search.py work/ex/target.txt --rules work/rules.json --all-blocks
        writes work/candidates_part_NN.md next to rules.json (or into --out-dir). Candidates are hints, never results.

Matches beyond --max are counted and reported, not silently dropped. Case-insensitive (Turkish İ handled).
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from id_index import parse_lines
from matrix import keywords, load_rules


def fold(s):
    return s.replace("İ", "i").lower()


def load(files):
    return [(Path(f).stem, list(parse_lines(f))) for f in files]


def hits(docs, rx):
    for doc, lines in docs:
        for i, (loc, text) in enumerate(lines):
            if rx.search(fold(text)):
                yield doc, lines, i


def show(doc, lines, i, mark=True):
    out = []
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(lines):
            loc, text = lines[j]
            out.append(f"  {'>' if j == i else ' '} {doc} {loc}  {text[:200]}")
    return out


def search_terms(docs, terms, regex, limit):
    out = []
    for t in terms:
        try:
            rx = re.compile(fold(t) if not regex else t, re.I) if regex else re.compile(re.escape(fold(t)))
        except re.error as e:
            out.append(f"## {t!r}: invalid regex ({e})"); continue
        found = list(hits(docs, rx))
        out.append(f"## {t!r}: {len(found)} hit(s)" + (f", showing {limit}" if len(found) > limit else ""))
        for h in found[:limit]:
            out += show(*h)
    return out


def rule_block(docs, rules, limit):
    out = []
    for r in rules:
        kws = keywords(r); scored = []
        for doc, lines in docs:
            for i, (loc, text) in enumerate(lines):
                low = fold(text); got = [k for k in kws if fold(k) in low]
                if got:
                    scored.append((len(got), doc, lines, i, got))
        scored.sort(key=lambda x: -x[0])
        quote = (r.get("source") or {}).get("quote") or r.get("quote", "")
        out += ["", f"## {r['id']} — {quote}", f"keywords: {', '.join(kws)} | matching lines: {len(scored)}" + (f", showing {limit}" if len(scored) > limit else "")]
        if not scored:
            out.append("  (NO CANDIDATE — absence may be a violation; search with other words)")
        for _, doc, lines, i, got in scored[:limit]:
            out.append(f"  [{', '.join(got)}]"); out += show(doc, lines, i)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-t", "--term", action="append", default=[])
    ap.add_argument("-f", "--terms-file", help="one term per line")
    ap.add_argument("--regex", action="store_true")
    ap.add_argument("--max", type=int, default=8, help="hits shown per term / rule")
    ap.add_argument("--rules"); ap.add_argument("--block", type=int); ap.add_argument("--all-blocks", action="store_true")
    ap.add_argument("--size", type=int, default=20); ap.add_argument("--out-dir")
    a = ap.parse_args()
    docs = load(a.files)
    if a.rules:
        rules = load_rules(a.rules)
        n = (len(rules) + a.size - 1) // a.size
        blocks = range(1, n + 1) if a.all_blocks else [a.block or 1]
        outdir = Path(a.out_dir or Path(a.rules).parent); outdir.mkdir(parents=True, exist_ok=True)
        for b in blocks:
            part = rules[(b - 1) * a.size:b * a.size]
            if not part:
                sys.exit(f"block {b} is empty ({len(rules)} rules, {n} blocks)")
            path = outdir / f"candidates_part_{b:02d}.md"
            path.write_text("\n".join([f"# Candidates, rules {part[0]['id']}..{part[-1]['id']} (block {b}/{n}). Hints only."] + rule_block(docs, part, a.max)) + "\n", encoding="utf-8")
            print(f"{path}: {len(part)} rules")
        return
    terms = a.term + ([l.strip() for l in Path(a.terms_file).read_text(encoding="utf-8").splitlines() if l.strip()] if a.terms_file else [])
    if not terms:
        sys.exit("give terms with -t / -f, or --rules")
    print("\n".join(search_terms(docs, terms, a.regex, a.max)))


if __name__ == "__main__":
    main()
