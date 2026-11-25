#!/usr/bin/env python3
"""Maps changed paragraphs (doc_diff.json) to model nodes; lists graph neighbours, nodes using the same parameter,
linked rules and invariants. Mapping: key == node ID / source.ids; otherwise whether source.quote occurs in the text.
Usage: impact.py --model process_model.yaml --diff diff.json [--rules rules.json] [--invariants invariants.yaml] [-o impact]
PRE-CHANGE use (before Claude edits the document): --keys SP-1.5,SP-2.3  (manual key list instead of a diff)
"""
import argparse, json, sys
from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).parent))
from model_check import load, steps_of, edges, params_list, param_nodes
from doc_diff import norm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--diff"); ap.add_argument("--keys")
    ap.add_argument("--rules"); ap.add_argument("--invariants"); ap.add_argument("-o", "--out", default="impact")
    a = ap.parse_args()
    m = load(a.model); nodes = {s["id"]: s for _, s in steps_of(m)}; procs = {p["id"]: p for p in m.get("processes") or []}
    items = []  # (key, kind, oldtext)
    if a.keys: items = [(k, "will-change", "") for k in a.keys.split(",")]
    else:
        d = json.loads(Path(a.diff).read_text(encoding="utf-8"))
        items += [(c["key"], "changed", c["old"]) for c in d["changed"]]
        items += [(c["key"], "removed", c["text"]) for c in d["removed"]]
        items += [(c["key"], "added", c["text"]) for c in d["added"]]
        items += [(c["key"], "moved", "") for c in d["moved"]]
    direct, unmapped, procs_hit, kinds = set(), [], set(), {}
    for key, kind, old in items:
        k = key.split("#")[0]; hit = {n for n, s in nodes.items() if k == n or k in ((s.get("source") or {}).get("ids") or [])}
        if not hit and old:
            hit = {n for n, s in nodes.items() if (s.get("source") or {}).get("quote") and norm(s["source"]["quote"]) in norm(old)}
        if k in procs: procs_hit.add(k)
        if hit:
            direct |= hit
            for n in hit: kinds.setdefault(n, []).append(kind)
        elif k not in procs and not k.startswith("H:") and k != "(preamble)": unmapped.append((key, kind))
    neigh = set()
    for n in direct:
        for t, _ in edges(nodes[n]):
            if t in nodes: neigh.add(t)
        for q, s in nodes.items():
            if any(t == n for t, _ in edges(s)): neigh.add(q)
    pids = {p["id"] for p in params_list(m) if set(param_nodes(m, p["id"])[1]) & direct}
    same_param = set()
    for pid in pids: same_param |= set(param_nodes(m, pid)[1])
    affected = (direct | neigh | same_param)
    for pr in procs_hit: affected |= {s["id"] for s in procs[pr].get("steps") or []}
    rules = sorted({r for n in affected if n in nodes for r in nodes[n].get("rules") or []})
    invs = []
    if a.invariants:
        iv = load(a.invariants); iv = iv.get("invariants", iv) if isinstance(iv, dict) else iv
        for i in iv:
            keys = set(i.get("nodes") or []) | {i.get("from"), i.get("to")} | set(i.get("scope") or []) | set(((i.get("of") or {}).get("process"),))
            why = []
            if keys & affected: why.append("node overlap " + ",".join(sorted(k for k in keys & affected if k)))
            if i.get("param") in pids: why.append(f"parameter {i['param']}")
            if i.get("check") in ("absent", "cross_ref") and not i.get("scope"): why.append("scope: whole document")
            if why: invs.append({"id": i["id"], "text": i.get("text", ""), "why": "; ".join(why)})
    res = {"direct": sorted(direct), "neighbors": sorted(neigh - direct), "same_parameter": sorted(same_param - direct), "parameters": sorted(pids),
           "rules": rules, "invariants": invs, "unmapped": unmapped, "kinds": kinds,
           "note": "Only affected invariants are listed; on a version change ALL invariants must be re-verified (model_check.py invariants)."}
    Path(a.out + ".json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    L = ["# Impact analysis", f"- Directly affected nodes: {res['direct']}  (what happened: {kinds})",
         f"- Neighbours (next/exception): {res['neighbors']}", f"- Using the same parameter: {res['same_parameter']}  (parameters: {res['parameters']})",
         f"- Linked rules: {rules}", "- Linked invariants:"] + [f"  - {i['id']}: {i['text']}  ← {i['why']}" for i in invs]
    L.append(f"- Changes with NO counterpart in the model (🆕 new process/step or ❓ model needs updating): {unmapped}")
    L.append("- " + res["note"])
    Path(a.out + ".md").write_text("\n".join(L) + "\n", encoding="utf-8"); print("\n".join(L))


if __name__ == "__main__":
    main()
