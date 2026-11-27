"""Checks on the JUDGEMENTS themselves (used by matrix.py coverage / verify). Standard library only.

R-, F-, TBD-, IF- below are the default own prefixes; the run's real ones come from work/prefixes.json (prefixes.py).

results.json extras:  "members": ["F-003", …]  on an aggregate finding ("section X is missing …"): every member has its own ❌/⚠️ row
                      result ⚖️ = reference contradiction / team decision (no change to the target can settle it); cites TBD-n
work/tbd.json         [{"id": "TBD-1", "text": "what the team has to decide"}]
work/internal.json    [{"id": "IF-1", "text": "…", "ids": ["UC-3.7.EX.2", "S-4.1"], "rules": ["R-012"], "no_rule_reason": "",
                        "param": "P:reminder:time"}]   contradictions inside the target, bound to the rules they concern
work/self_audit.json  written by matrix.py audit-plan / audit-record

Hard failures stop verify. Warnings are heuristics: they are counted and listed in the report and must be looked at.
"""
import hashlib, json, math, re, secrets
from pathlib import Path
from id_index import load_patterns, norm_id
import prefixes

DECISION = "⚖️"
BAD = ("❌", "⚠️", DECISION)
TEXT_FIELDS = ("evidence", "issue", "fix", "target_loc", "note")
NO_CHANGE = re.compile(r"^\W*(?:no\s+changes?\b|no\s+action\b|none\b|nothing\s+to\s+change|team\s+(?:to\s+)?decid\w*|team\s+decision|tbd\b|"
                       r"değişiklik\s+(?:yok|gerekmez|gerekmiyor|gerekli\s+değil)|(?:ekip|takım)\s+karar\w*)", re.I)
ABSENCE = re.compile(r"\bnot\s+(?:found|mentioned|present|addressed|covered|stated|in\s+the\s+target)\b|\bdoes\s+not\s+(?:occur|appear|mention|say|state|contain)\b|"
                     r"\b(?:says|states)\s+nothing\b|\bno\s+mention\b|\bnowhere\b|\babsent\b|\bhiç\s+(?:yok|geçmiyor|yer\s+almıyor)\b|\bgeçmiyor\b|\byer\s+almıyor\b|"
                     r"\bbulunamadı\b|\bbulunmuyor\b|\bbahsedilmiyor\b|hedefte\s+(?:hiç\s+)?yok", re.I)
AGGREGATE = re.compile(r"(?:\b(?:missing|lacks?|unanswered|not\s+answered|not\s+covered)\b|\beksik\w*|\bcevapsız\w*|\byanıtsız\w*)"
                       r"[^.;]{0,60}?(?::|\b(?:sections?|questions?|items?|fields?)\b|\b(?:bölüm|soru|madde|alan)\w*)[^.]{0,120}?(?:,|\band\b|\bve\b)", re.I)


class Own:
    """Regexes for the skill's own IDs under the run's prefixes (see prefixes.py)."""
    def __init__(self, p=None):
        self.p = p or dict(prefixes.DEFAULT)
        rf = f"(?:{re.escape(self.p['rule'])}|{re.escape(self.p['fact'])})"
        tbd = re.escape(self.p["tbd"])
        self.row_ref = re.compile(rf"(?<![\w-]){rf}-\d{{3}}\b|(?i:\b(?:see|bkz\.?)\s+)(?<![\w-])({rf}-\d+)\b")
        self.tbd_ref = re.compile(rf"(?<![\w-]){tbd}-\d+\b")
        self.any = re.compile(rf"(?<![\w-])(?:{rf}|{tbd}|{re.escape(self.p['finding'])})-\d+\b")
        self.tbd_first = re.compile(rf"^\W*{tbd}-\d")

    def is_fact(self, r):
        return r.get("kind") == "fact" or r["id"].startswith(self.p["fact"] + "-")


def sym(result):
    s = (result or {}).get("result", "") if isinstance(result, dict) else (result or "")
    s = s.replace("️", "")
    return {"✅": "✅", "❌": "❌", "⚠": "⚠️", "➖": "➖", "❓": "❓", "⚖": DECISION}.get(s, s)


def read(work, name):
    p = Path(work) / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cell(s):
    return str(s or "").replace("|", "¦").replace("\n", " ")


def text_of(row):
    return " ".join(str((row or {}).get(k, "")) for k in TEXT_FIELDS)


def ids_in(text, patterns):
    return {norm_id(m.group(0)) for _, rx in patterns for m in rx.finditer(text)}


def rule_text(r):
    return " ".join([str(r.get("scope", "")), str((r.get("source") or {}).get("quote", "") or r.get("quote", "")),
                     " ".join(r.get("keywords") or []), str(r.get("interpretation", ""))])


def fold(s):
    return s.replace("İ", "i").lower()


def has_word(word, text):
    return re.search(r"(?<!\w)" + re.escape(fold(word)), fold(text)) is not None


def refs_in(text, own=None):
    return {m.group(1) or m.group(0) for m in (own or Own()).row_ref.finditer(text)}


# ---------- 1) aggregate findings, ➖ ----------
def check_aggregates(rules, res, sections, own):
    errors, warnings = [], []
    known = {r["id"] for r in rules}
    cls = {s["id"]: s.get("class") for s in (sections or {}).get("sections", [])}
    for r in rules:
        rid = r["id"]; v = res.get(rid)
        if not v:
            continue
        s = sym(v); members = v.get("members") or []
        for m in members:
            if m == rid:
                errors.append(f"{rid}: aggregate finding lists itself as a member")
            elif m not in known:
                errors.append(f"{rid}: aggregate member {m} is not in the register (every missing item needs its own rule/fact)")
            elif sym(res.get(m)) not in ("❌", "⚠️"):
                errors.append(f"{rid}: aggregate member {m} has no ❌/⚠️ row of its own (it is {sym(res.get(m)) or 'without a result'})")
        if s in ("❌", "⚠️") and not members and AGGREGATE.search(f"{v.get('issue', '')}. {v.get('evidence', '')}"):
            warnings.append(f"{rid}: reads like an aggregate finding (several missing items) but has no \"members\": give each item its own row")
        if s == "➖" and ABSENCE.search(text_of(v)):
            section = (r.get("source") or {}).get("section")
            fact = own.is_fact(r)
            if not fact:      # a conditional rule ("every screenshot …" with no screenshot) is a legitimate ➖: warn only
                warnings.append(f"{rid}: ➖ with 'absent' wording: correct only if the rule does not apply; an absent required item is ❌/⚠️")
            elif cls.get(section) in ("open-question", "rule-bearing"):
                errors.append(f"{rid}: ➖ for a fact absent from the target although its section {section} is {cls[section]}: it cannot be 'not applicable'")
    return errors, warnings


# ---------- 2) evidence fits the rule; references resolve ----------
def check_evidence(rules, res, patterns, keywords, own):
    """Warnings when a row's evidence looks like it belongs to another rule. Returns (warnings, checked, not_checkable)."""
    warnings, checked, blind = [], 0, 0
    kw = {r["id"]: keywords(r) for r in rules}
    for r in rules:
        rid = r["id"]; v = res.get(rid)
        if not v:
            continue
        ev = f"{v.get('evidence', '')} {v.get('target_loc', '')}"
        mine = ids_in(own.any.sub(" ", rule_text(r)), patterns)          # own row/finding IDs are not document IDs
        theirs = ids_in(own.any.sub(" ", ev), patterns)
        if not kw[rid] and not (mine and theirs):
            blind += 1; continue
        checked += 1
        if mine and theirs and not mine & theirs:
            warnings.append(f"{rid}: evidence IDs ({', '.join(sorted(theirs))}) do not overlap the rule's IDs ({', '.join(sorted(mine))})")
        low = f"{ev} {v.get('issue', '')}".lower()
        if kw[rid] and not any(has_word(w, low) for w in kw[rid]):
            scores = sorted(((sum(has_word(w, low) for w in set(kw[o]) - set(kw[rid])), o) for o in kw if o != rid), key=lambda x: (-x[0], x[1]))
            if scores and scores[0][0] >= 2:
                warnings.append(f"{rid}: evidence uses none of the rule's keywords but {scores[0][0]} of {scores[0][1]}'s: is it written on the wrong row?")
    return warnings, checked, blind


def check_references(rules, texts, tbd, own):
    """texts: [(where, text)]. Every rule/fact reference must be in the register, every decision reference in tbd.json."""
    known = {r["id"] for r in rules}; defined = {t.get("id") for t in tbd or []}
    errors = []
    for where, t in texts:
        errors += [f"broken reference in {where}: {x} is not a row of the register" for x in sorted(refs_in(t, own) - known)]
        errors += [f"broken reference in {where}: {x} is not defined in tbd.json" for x in sorted(set(own.tbd_ref.findall(t)) - defined)]
    return errors


# ---------- 4) result type ----------
def verdict_problem(v, own):
    if sym(v) == "❌":
        fix = str(v.get("fix", "")).strip()
        if not fix:
            return "a ❌ row needs a fix (what has to change in the target)"
        if NO_CHANGE.search(fix) or own.tbd_first.search(fix):
            return f"❌ with fix «{fix[:60]}»: if nothing in the target has to change, or the team has to decide, use {DECISION} and cite {own.p['tbd']}-n"
    if sym(v) == DECISION and not own.tbd_ref.search(text_of(v)):
        return f"a {DECISION} row must cite the open decision as {own.p['tbd']}-n (defined in tbd.json)"
    return None


# ---------- 3) internal contradictions ----------
def check_internal(findings, rules, res, patterns, keywords, params, verdicts, own):
    errors, warnings, seen = [], [], set()
    by = {r["id"]: r for r in rules}
    for f in findings:
        fid = f.get("id", "")
        if not re.fullmatch(re.escape(own.p["finding"]) + r"-\d+", fid) or not str(f.get("text", "")).strip():
            errors.append(f"internal.json: every finding needs an id {own.p['finding']}-n and a text ({fid or f})"); continue
        if fid in seen: errors.append(f"{fid}: duplicate internal finding id")
        seen.add(fid)
        listed = f.get("rules") or []
        if not listed and not str(f.get("no_rule_reason", "")).strip():
            errors.append(f"{fid}: list the rules it concerns, or give no_rule_reason")
        for rid in listed:
            if rid not in by:
                errors.append(f"{fid}: rule {rid} is not in the register")
            elif not re.search(r"(?<![\w-])" + re.escape(fid) + r"(?!\d)", text_of(res.get(rid))):
                errors.append(f"{fid}: it concerns {rid} but the row of {rid} does not mention {fid}")
        fids = {norm_id(i) for i in f.get("ids") or []} | ids_in(own.any.sub(" ", f.get("text", "")), patterns)
        low = f.get("text", "").lower()
        for rid, r in by.items():
            if rid not in listed:
                shared = fids & ids_in(rule_text(r), patterns)
                words = [w for w in keywords(r) if has_word(w, low)]
                if shared or len(words) >= 2:
                    warnings.append(f"{fid}: may also concern {rid} ({', '.join(sorted(shared)) or ', '.join(words[:4])}); bind it or ignore after checking")
    if params:
        covered = {f.get("param") for f in findings}
        for c in params["conflicts"]:
            if "target-internal" in c["kinds"] and (verdicts or {}).get(c["id"], {}).get("verdict") == "real" and c["id"] not in covered:
                errors.append(f"parameter conflict {c['id']} is a real contradiction inside the target but no internal finding has \"param\": \"{c['id']}\"")
    return errors, warnings


# ---------- 5) self-audit ----------
def row_hash(v):
    return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def new_seed():
    return secrets.token_hex(8)


def sample(ids, seed, share=0.10):
    """Seeded random selection: unknown until the seed exists, reproducible with it in every environment."""
    ranked = sorted(ids, key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
    return sorted(ranked[:max(1, math.ceil(len(ids) * share - 1e-9))]) if ids else []


def planned(rules, res, audit):
    """Rows that must be re-checked: every ❌/⚠️/⚖️ (now or when first planned) plus 10% of the rows first planned as ✅."""
    snap = (audit or {}).get("snapshot", {})
    ids = [r["id"] for r in rules]
    need = {i for i in ids if sym(res.get(i)) in BAD or snap.get(i) in BAD}
    need |= set(sample([i for i in ids if snap.get(i, sym(res.get(i))) == "✅"], audit["seed"]))
    return [i for i in ids if i in need]


def audit_plan(rules, res, audit, seed, source):
    audit = audit or {"seed": seed, "seed_source": source, "snapshot": {}, "checks": {}}
    for r in rules:
        if r["id"] in res:
            audit["snapshot"].setdefault(r["id"], sym(res[r["id"]]))
    audit["planned"] = planned(rules, res, audit)
    return audit


def check_audit(rules, res, audit):
    """(errors, planned ids, checked ids, changed lines)."""
    need = planned(rules, res, audit); checks = audit.get("checks", {})
    errors, done, changed = [], [], []
    for rid in need:
        c = checks.get(rid)
        if not c or not str(c.get("source", "")).strip():
            errors.append(f"self-audit: {rid} not re-checked against the source")
        elif c.get("row") != row_hash(res.get(rid)):
            errors.append(f"self-audit: {rid} changed after it was re-checked: re-check it and run audit-record again")
        else:
            done.append(rid)
    for r in rules:
        before = audit.get("snapshot", {}).get(r["id"]); now = sym(res.get(r["id"]))
        if before and before != now:
            why = checks.get(r["id"], {}).get("note") or checks.get(r["id"], {}).get("source", "")
            changed.append(f"- {r['id']}: {before} → {now} ({cell(why)})")
    return errors, need, done, changed


# ---------- everything, for gates.collect ----------
def collect(work, rules, res, patterns_file=None, report_text=None):
    """{summary, sections, required, errors, skipped}"""
    from matrix import keywords
    if patterns_file is None and (Path(work) / "id_patterns.json").exists():
        patterns_file = Path(work) / "id_patterns.json"
    patterns, _ = load_patterns(patterns_file)
    chosen, prefix_data = prefixes.load(work); own = Own(chosen)
    out = {"summary": [], "sections": [], "required": [], "errors": [], "skipped": []}
    sections, tbd, findings = read(work, "ref_sections.json"), read(work, "tbd.json"), read(work, "internal.json")
    params, verdicts = read(work, "params.json"), read(work, "param_verdicts.json")

    if prefix_data is None:
        out["summary"].append("- ID prefixes: NOT RUN (prefixes.py)")
        out["errors"].append("ID prefixes not chosen: run prefixes.py on the extracted target and references (work/prefixes.json)")
    else:
        out["summary"].append(prefixes.describe(prefix_data))
        texts_now = sorted(str(p) for p in (Path(work) / "ex").glob("*.txt") if not p.name.endswith((".second.txt", ".tables.txt")))
        for kind, p in chosen.items():
            used = prefixes.first_use(p, texts_now)
            if used: out["errors"].append(f"the {prefixes.LABEL[kind]} prefix {p}- collides with the documents ({used}): run prefixes.py again and renumber")
    for r in rules:
        want = chosen["fact" if r.get("kind") == "fact" or r["id"].startswith(chosen["fact"] + "-") else "rule"]
        if not re.fullmatch(re.escape(want) + r"-\d+", r["id"]):
            out["errors"].append(f"{r['id']}: register IDs must use the chosen prefix {want}-")
    for t in tbd or []:
        if not re.fullmatch(re.escape(chosen["tbd"]) + r"-\d+", str(t.get("id", ""))):
            out["errors"].append(f"tbd.json {t.get('id')}: decision IDs must use the chosen prefix {chosen['tbd']}-")
    for rid, v in res.items():
        problem = verdict_problem(v, own)
        if problem: out["errors"].append(f"{rid}: {problem}")
    errs, warnings = check_aggregates(rules, res, sections, own); out["errors"] += errs
    w, checked, blind = check_evidence(rules, res, patterns, keywords, own); warnings += w

    texts = [(f"results of {rid}", text_of(v)) for rid, v in res.items()]
    texts += [(f"internal finding {f.get('id')}", str(f.get("text", ""))) for f in findings or []]
    if report_text: texts.append(("the report", report_text))
    out["errors"] += check_references(rules, texts, tbd, own)

    decisions = [r["id"] for r in rules if sym(res.get(r["id"])) == DECISION]
    if decisions:
        out["sections"] += ["## Reference conflicts / team decisions", "| Rule | Evidence | Decision needed |", "|---|---|---|"]
        for rid in decisions:
            v = res[rid]; line = f"| {rid} {DECISION} | {cell(v.get('evidence'))} | {cell(v.get('fix') or v.get('issue') or ', '.join(own.tbd_ref.findall(text_of(v))))} |"
            out["sections"].append(line); out["required"].append(line)
        out["sections"].append("")
    if tbd:
        lines = [f"- {t.get('id')}: {cell(t.get('text'))}" for t in tbd]
        out["sections"] += ["## Open decisions (TBD)", *lines, ""]; out["required"] += lines

    if findings is None:
        out["summary"].append("- Internal findings: NOT RUN (work/internal.json)"); out["skipped"].append(("internal findings bound to rules", "step not run", 1))
    else:
        errs, w = check_internal(findings, rules, res, patterns, keywords, params, verdicts, own); out["errors"] += errs; warnings += w
        bound = sum(1 for f in findings if f.get("rules"))
        out["summary"].append(f"- Internal findings: {len(findings)} (bound to rules: {bound}, without a rule: {len(findings) - bound})")
        out["sections"] += ["## Internal findings bound to rules", "| Finding | IDs | Rules | Text |", "|---|---|---|---|"]
        for f in findings:
            line = f"| {f.get('id')} | {cell(', '.join(f.get('ids') or []))} | {cell(', '.join(f.get('rules') or []) or 'none: ' + str(f.get('no_rule_reason', '')))} | {cell(f.get('text'))} |"
            out["sections"].append(line); out["required"].append(line)
        out["sections"].append("")

    audit = read(work, "self_audit.json")
    state = read(work, "progress.json") or {}
    skip = state.get("steps", {}).get("self-audit", {}).get("state") == "skipped"
    if audit is not None and not skip:
        if not audit.get("seed") or audit.get("seed") != state.get("audit_seed"):
            out["errors"].append("self-audit seed does not match progress.json: the selection must come from the seed created when the step started")
            audit = {**audit, "seed": audit.get("seed") or ""}
    if audit is None:
        out["summary"].append("- Self-audit: NOT RUN (matrix.py audit-plan / audit-record)")
        if not skip:
            out["errors"].append("self-audit not run: matrix.py audit-plan, re-check the rows, audit-record (or record the step as skipped with a reason)")
            out["skipped"].append(("self-audit", "step not run", 1))
    else:
        errs, need, done, changed = check_audit(rules, res, audit)
        if not skip: out["errors"] += errs
        line = f"- Self-audit: re-checked {len(done)}/{len(need)} planned rows (all ❌/⚠️/{DECISION} and a random 10% of ✅; seed {audit['seed']}, {audit.get('seed_source', '?')}); changed: {len(changed)}"
        out["summary"].append(line)
        block = ["## Changed in self-audit (öz-denetimde değişti)", *(changed or ["- (no verdict changed)"])]
        out["sections"] += block + [""]; out["required"] += block

    out["summary"].append(f"- Judgement warnings: {len(warnings)} (evidence fit checked on {checked} rows, not checkable on {blind})")
    if warnings:
        lines = [f"- {x}" for x in warnings]
        out["sections"] += ["## Judgement warnings (check each one)", *lines, ""]; out["required"] += lines
    out["required"] += out["summary"]
    return out
