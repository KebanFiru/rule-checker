#!/usr/bin/env python3
"""Process model: structural validation, invariant checking, Mermaid generation, version bump.

  model_check.py check  process_model.yaml [--rules rules.json] [--mmd out.mmd]   structural validation (+ generates .mmd)
  model_check.py invariants process_model.yaml invariants.yaml [--doc extracted/yeni.txt] [-o inv_result.json]
        verifies every invariant on the model graph and, with --doc, on the new document text (ALL of them, not only the affected ones)
  model_check.py bump process_model.yaml --nodes SP-1.5,SP-2.2 --reason "..." [--doc-version Rev2] [--changelog changelog.md]
        model_version +1, writes a version entry to changelog.md (does not re-dump the YAML; formatting is preserved)
Exit code: 1 if there is an error (or a FAIL invariant).
"""
import argparse, datetime, json, re, sys
from collections import deque
from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).parent))
from id_index import load_patterns, blocks_by_id

SYMS = ("✅", "❌")


def load(p): return yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}


def steps_of(m):
    for p in m.get("processes", []) or []:
        for s in p.get("steps", []) or []:
            yield p, s


def edges(s):
    out = [(n, "next") for n in (s.get("next") or [])]
    out += [(e.get("goto"), "exc") for e in (s.get("on_exception") or []) if isinstance(e, dict)]
    return out


def graph(m):
    return {s["id"]: edges(s) for _, s in steps_of(m) if isinstance(s, dict) and s.get("id")}


def reach(g, start):
    seen, q = {start}, deque([start])
    while q:
        for n, _ in g.get(q.popleft(), []):
            if n in g and n not in seen: seen.add(n); q.append(n)
    return seen


def has_source(o):
    s = o.get("source") if isinstance(o, dict) else None
    return isinstance(s, dict) and any(s.get(k) for k in ("quote", "pages", "page", "ids", "doc"))


# ---------------- check ----------------
def check(m, rule_ids=None):
    E, W = [], []
    procs = m.get("processes") or []
    if not procs: E.append("processes is empty/missing")
    g = graph(m); ids = {}
    params = {}
    for i, p in enumerate(procs):
        pid = p.get("id", f"processes[{i}]")
        for f in ("id", "name", "source"):
            if not p.get(f): E.append(f"{pid}: '{f}' is required")
        if p.get("source") and not has_source(p): E.append(f"{pid}: source is empty")
        if not p.get("steps"): E.append(f"{pid}: steps yok")
        for s in p.get("steps") or []:
            sid = s.get("id", "?")
            for f in ("id", "actor", "action"):
                if not s.get(f): E.append(f"{pid}/{sid}: '{f}' is required")
            if not has_source(s): E.append(f"{sid}: node has NO SOURCE (source is required)")
            if sid in ids: E.append(f"{sid}: duplicate step ID (first defined in {ids[sid]})")
            ids[sid] = pid
            if p.get("actors") and s.get("actor") and s["actor"] not in p["actors"]:
                W.append(f"{sid}: actor '{s['actor']}' is not in the process actors list")
            for n, kind in edges(s):
                if not n: E.append(f"{sid}: empty {'next' if kind == 'next' else 'goto'}")
                elif n not in g: E.append(f"{sid}: TANIMSIZ {'next' if kind == 'next' else 'goto'} → {n}")
            if rule_ids is not None:
                for r in s.get("rules") or []:
                    if r not in rule_ids: E.append(f"{sid}: rule {r} is not in rules.json")
            if s.get("assumption") and not has_source(s): E.append(f"{sid}: assumption ise de source gerekli")
    for p in params_list(m):
        pid = p.get("id", "?")
        for f in ("id", "value", "unit"):
            if p.get(f) is None: E.append(f"parametre {pid}: '{f}' zorunlu")
        if not has_source(p): E.append(f"parametre {pid}: KAYNAKSIZ (source zorunlu)")
        if pid in params and params[pid].get("value") != p.get("value"):
            E.append(f"parameter {pid}: DIFFERENT VALUES {params[pid].get('value')} ≠ {p.get('value')}")
        elif pid in params: E.append(f"parameter {pid}: duplicate definition")
        params[pid] = p
    used = set()
    for p in params.values():
        for n in p.get("used_in") or []:
            used.add(p["id"])
            if n not in g and n not in {pp.get("id") for pp in procs}: W.append(f"parametre {p['id']}: used_in '{n}' modelde yok")
    for _, s in steps_of(m):
        d = s.get("duration") or {}
        if d.get("param"):
            used.add(d["param"])
            if d["param"] not in params: E.append(f"{s['id']}: duration.param {d['param']} parametre listesinde yok")
            elif d.get("value") != params[d["param"]].get("value"):
                E.append(f"{s['id']}: duration {d.get('value')} ≠ {d['param']}={params[d['param']].get('value')} (same parameter, different value)")
    for pid in params:
        if pid not in used: W.append(f"parametre {pid}: KULLANILMIYOR (used_in/duration.param yok)")
    # reachability and steps without an exit
    for p in procs:
        st = [s for s in p.get("steps") or [] if s.get("id")]
        if not st: continue
        entries = p.get("entry_points") or [st[0]["id"]]
        # edges coming from other processes also count as entries
        inc = {n for q in procs if q is not p for s in q.get("steps") or [] for n, _ in edges(s)}
        reached = set()
        for e in entries + [s["id"] for s in st if s["id"] in inc]:
            if e in g: reached |= reach(g, e)
        for s in st:
            if s["id"] not in reached: E.append(f"{s['id']}: UNREACHABLE step")
            if not edges(s) and not s.get("terminal") and s is not st[-1]:
                E.append(f"{s['id']}: NO EXIT (not the last step and not terminal:true)")
    # disallowed cycle (cycles through a step with allow_loop: true are allowed)
    allow = {s["id"] for _, s in steps_of(m) if s.get("allow_loop")}
    for cyc in cycles(g):
        if not (set(cyc) & allow): E.append("DISALLOWED CYCLE: " + " → ".join(cyc + [cyc[0]]) + "  (if intentional, set allow_loop: true on one step)")
    for t in m.get("tbd") or []:
        if not t.get("id"): E.append("tbd: id zorunlu")
        for b in t.get("blocks") or []:
            if b not in g: W.append(f"tbd {t.get('id')}: blocks '{b}' modelde yok")
    return E, W


def params_list(m): return m.get("parameters") or []


def cycles(g):
    out, state, stack = [], {}, []
    def dfs(u):
        state[u] = 1; stack.append(u)
        for v, _ in g.get(u, []):
            if v not in g: continue
            if state.get(v) == 1: out.append(stack[stack.index(v):])
            elif v not in state: dfs(v)
        stack.pop(); state[u] = 2
    for u in g:
        if u not in state: dfs(u)
    return out


def mermaid(m):
    san = lambda s: re.sub(r"\W", "_", s)
    q = lambda s: str(s).replace('"', "'")
    L = ["flowchart TD", "%% AUTO-GENERATED from process_model.yaml. Do not edit by hand."]
    for p in m.get("processes") or []:
        L.append(f'  subgraph {san(p["id"])}["{q(p["id"])} {q(p.get("name", ""))}"]')
        for s in p.get("steps") or []:
            L.append(f'    {san(s["id"])}["{q(s["id"])} · {q(s.get("actor", ""))}<br/>{q(s.get("action", ""))}"]')
        L.append("  end")
    for _, s in steps_of(m):
        for n in s.get("next") or []: L.append(f"  {san(s['id'])} --> {san(n)}")
        for e in s.get("on_exception") or []:
            L.append(f'  {san(s["id"])} -.->|"{q(e.get("when", ""))}"| {san(e.get("goto", "?"))}')
    return "\n".join(L) + "\n"


# ---------------- invariants ----------------
def doc_blocks(txt, pats):
    lines = [tuple(r.split("\t", 1)) for r in Path(txt).read_text(encoding="utf-8").splitlines() if "\t" in r]
    return blocks_by_id(lines, pats)


def node_block(node, blocks):
    ids = [node["id"]] + list((node.get("source") or {}).get("ids") or [])
    for b in blocks:
        if b["key"].split("#")[0] in ids: return b


def param_nodes(m, pid):
    p = next((x for x in params_list(m) if x.get("id") == pid), None)
    names = set((p or {}).get("used_in") or [])
    names |= {s["id"] for _, s in steps_of(m) if (s.get("duration") or {}).get("param") == pid}
    return p, sorted(names)


def run_invariants(m, invs, blocks=None):
    g = graph(m); nodes = {s["id"]: s for _, s in steps_of(m)}; out = []
    for inv in invs.get("invariants", invs) if isinstance(invs, dict) else invs:
        t, iid = inv.get("check"), inv.get("id"); msgs = []; status = "PASS"
        def fail(x): 
            nonlocal status; status = "FAIL"; msgs.append(x)
        def unver(x):
            nonlocal status
            if status != "FAIL": status = "UNVERIFIED"
            msgs.append(x)
        if t == "order":
            ns = inv["nodes"]
            for a, b in zip(ns, ns[1:]):
                if a not in g or b not in g: fail(f"modelde yok: {a if a not in g else b}"); continue
                if b not in reach(g, a): fail(f"model: {b}, {a}'dan sonra gelmiyor")
                if blocks is not None:
                    ba, bb = node_block(nodes[a], blocks), node_block(nodes[b], blocks)
                    if not ba or not bb: fail(f"block not found in the document: {a if not ba else b}")
                    elif ba["pos"] > bb["pos"]: fail(f"DOCUMENT: {b} ({bb['loc']}) comes BEFORE {a} ({ba['loc']})")
        elif t == "param_equal":
            p, names = param_nodes(m, inv["param"])
            if not p: fail(f"parametre yok: {inv['param']}")
            else:
                if not names: unver("no node uses the parameter")
                if blocks is not None:
                    unit = p.get("doc_unit") or str(p.get("unit"))
                    rx = re.compile(rf"(\d+(?:[.,]\d+)?)\s*(?:{unit})", re.I)
                    for n in names:
                        b = node_block(nodes[n], blocks) if n in nodes else None
                        if not b: unver(f"{n}: belgede blok yok"); continue
                        vals = [float(x.replace(",", ".")) for x in rx.findall(b["text"])]
                        if not vals: unver(f"{n} ({b['loc']}): no value with unit '{unit}' found")
                        elif float(p["value"]) not in vals: fail(f"DOCUMENT: {n} ({b['loc']}) value {vals} ≠ {inv['param']}={p['value']}")
        elif t == "reachability":
            a, b = inv["from"], inv["to"]
            if a not in g or b not in g: fail("node missing")
            elif b not in reach(g, a): fail(f"{b} is not reachable from {a}")
        elif t == "exists":
            for n in inv.get("nodes", []):
                if n not in g: fail(f"modelde yok: {n}")
                elif blocks is not None and not node_block(nodes[n], blocks): fail(f"belgede yok: {n}")
        elif t == "absent":
            if blocks is None: unver("document required (--doc)")
            else:
                rx = re.compile(inv["pattern"], re.I)
                scope = inv.get("scope")
                bl = [node_block(nodes[n], blocks) for n in scope if n in nodes] if scope else blocks
                for b in filter(None, bl):
                    if rx.search(b["text"]): fail(f"DOCUMENT: {b['key']} ({b['loc']}) contains '{inv['pattern']}'")
        elif t == "cardinality":
            of = inv["of"]; c = sum(1 for p, s in steps_of(m) if (not of.get("process") or p["id"] == of["process"]) and (not of.get("actor") or s.get("actor") == of["actor"]))
            ok = {"==": c == inv["n"], ">=": c >= inv["n"], "<=": c <= inv["n"]}[inv.get("op", "==")]
            if not ok: fail(f"count {c} does not satisfy {inv.get('op', '==')} {inv['n']}")
        elif t == "cross_ref":
            bad = [f"{s['id']}→{n}" for _, s in steps_of(m) for n, _ in edges(s) if n not in g]
            if bad: fail("undefined in the model: " + ", ".join(bad))
            if blocks is not None and inv.get("pattern"):
                rx = re.compile(inv["pattern"]); defined = {b["key"].split("#")[0] for b in blocks}
                for b in blocks:
                    for r in rx.findall(b["text"]):
                        if r not in defined: fail(f"DOCUMENT: reference {r} ({b['loc']}) is undefined")
        else: fail(f"bilinmeyen check tipi: {t}")
        out.append({"id": iid, "text": inv.get("text", ""), "check": t, "status": status, "detail": msgs, "source": inv.get("source")})
    return out


# ---------------- bump ----------------
def bump(path, nodes, reason, doc_version, changelog):
    txt = Path(path).read_text(encoding="utf-8")
    m = re.search(r"model_version:\s*(\d+)", txt)       # both block-style and inline (flow) meta are supported
    if not m: sys.exit("meta.model_version not found")
    new = int(m.group(1)) + 1; today = datetime.date.today().isoformat()
    txt = txt[:m.start()] + f"model_version: {new}" + txt[m.end():]
    txt = re.sub(r"updated:\s*[\d-]+", f"updated: {today}", txt, count=1)
    if doc_version: txt = re.sub(r'doc_version:\s*"[^"]*"', f'doc_version: "{doc_version}"', txt, count=1)
    Path(path).write_text(txt, encoding="utf-8")
    cl = Path(changelog); head = "# Changelog\n\n"
    body = cl.read_text(encoding="utf-8") if cl.exists() else head
    entry = f"## v{new} — {today}" + (f" (document {doc_version})" if doc_version else "") + f"\n- Changed nodes: {', '.join(nodes) or '-'}\n- Reason: {reason}\n\n"
    cl.write_text(body.rstrip("\n") + "\n\n" + entry if body.strip() != head.strip() else head + entry, encoding="utf-8")
    print(f"model_version {new}; {changelog} updated")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("check"); c.add_argument("model"); c.add_argument("--rules"); c.add_argument("--mmd")
    i = sp.add_parser("invariants"); i.add_argument("model"); i.add_argument("invariants"); i.add_argument("--doc"); i.add_argument("--patterns"); i.add_argument("-o", "--out")
    b = sp.add_parser("bump"); b.add_argument("model"); b.add_argument("--nodes", default=""); b.add_argument("--reason", required=True)
    b.add_argument("--doc-version"); b.add_argument("--changelog", default=None)
    a = ap.parse_args()
    if a.cmd == "check":
        m = load(a.model)
        rids = None
        if a.rules:
            r = json.loads(Path(a.rules).read_text(encoding="utf-8")); rids = {x["id"] for x in (r["rules"] if isinstance(r, dict) else r)}
        E, W = check(m, rids)
        mmd = Path(a.mmd) if a.mmd else Path(a.model).with_suffix(".mmd")
        mmd.write_text(mermaid(m), encoding="utf-8")
        for e in E: print("ERROR  :", e)
        for w in W: print("WARNING:", w)
        nsteps = sum(1 for _ in steps_of(m))
        print(f"{len(m.get('processes') or [])} processes, {nsteps} steps, {len(params_list(m))} parameters, {len(m.get('tbd') or [])} TBD → {len(E)} errors, {len(W)} warnings; {mmd} written")
        sys.exit(1 if E else 0)
    if a.cmd == "invariants":
        m = load(a.model); invs = load(a.invariants); pats, _ = load_patterns(a.patterns)
        bl = doc_blocks(a.doc, pats) if a.doc else None
        res = run_invariants(m, invs, bl)
        for r in res:
            sym = {"PASS": "✅", "FAIL": "❌", "UNVERIFIED": "❓"}[r["status"]]
            print(f"{sym} {r['id']} [{r['check']}] {r['text']}" + ("".join(f"\n     - {d}" for d in r["detail"])))
        if a.out: Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{sum(r['status'] == 'PASS' for r in res)}/{len(res)} PASS, {sum(r['status'] == 'FAIL' for r in res)} FAIL, {sum(r['status'] == 'UNVERIFIED' for r in res)} unverified")
        sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)
    if a.cmd == "bump":
        bump(a.model, [x for x in a.nodes.split(",") if x], a.reason, a.doc_version, a.changelog or str(Path(a.model).with_name("changelog.md")))


if __name__ == "__main__":
    main()
