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
from collections import Counter
from pathlib import Path
from id_index import load_patterns, norm_id, parse_lines, doc_stem, current_path
import prefixes
import self_rules as self_rules_mod

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
        rf = "(?:" + "|".join(re.escape(self.p[k]) for k in ("rule", "fact", "self")) + ")"
        tbd = re.escape(self.p["tbd"])
        self.row_ref = re.compile(rf"(?<![\w-]){rf}-\d{{3}}\b|(?i:\b(?:see|bkz\.?)\s+)(?<![\w-])({rf}-\d+)\b")
        self.tbd_ref = re.compile(rf"(?<![\w-]){tbd}-\d+\b")
        self.any = re.compile(rf"(?<![\w-])(?:{rf}|{tbd}|{re.escape(self.p['finding'])})-\d+\b")
        self.tbd_first = re.compile(rf"^\W*{tbd}-\d")

    def kind(self, r):
        if r.get("kind") == "fact" or r["id"].startswith(self.p["fact"] + "-"):
            return "fact"
        return "self" if r.get("kind") == "self" or r["id"].startswith(self.p["self"] + "-") else "rule"

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


# ---------- meaningful keywords ----------
WARNING_LIMIT = 30
MONTH_WORDS = set(("january february march april may june july august september october november december jan feb mar apr jun jul aug sep sept "
                   "oct nov dec ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık").split())
NOT_A_WORD = re.compile(r"[\d\W_]*|\d+(?:st|nd|rd|th|[.:]?[a-zçğıöşü])?")          # numbers, dates, times, ordinals, "3a"
WORD_RX = re.compile(r"[^\W\d_]{2,}")


def common_words(files, rules, share=0.05):
    """The most frequent 5% of the words of the run (documents and register): they say nothing about which row a sentence belongs to."""
    count = Counter()
    for f in dict.fromkeys(current_path(f) for f in files):             # a current.txt and its original are read once
        for _, text in parse_lines(f):
            count.update(WORD_RX.findall(fold(text)))
    if not count:
        for r in rules:
            count.update(WORD_RX.findall(fold(rule_text(r))))
    top = sorted(count.items(), key=lambda x: (-x[1], x[0]))[:int(len(count) * share)]
    return {w for w, n in top if n >= 3}


def meaningful(words, common=()):
    """Keywords that can tell rows apart: no numbers, dates, month names, single letters or document-wide frequent words."""
    out = []
    for w in dict.fromkeys(fold(str(w)).strip() for w in words):
        if len(w) > 1 and not NOT_A_WORD.fullmatch(w) and w not in MONTH_WORDS and w not in common:
            out.append(w)
    return out


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
SENTENCES = re.compile(r"(?<=[.!?;])\s+(?=[\w«\"(])|\n+")


def terms_of(rule, patterns, keywords, own, common):
    """(document IDs of the rule, its meaningful keywords that are not just a piece of one of those IDs)."""
    ids = ids_in(own.any.sub(" ", rule_text(rule)), patterns)          # own row/finding IDs are not document IDs
    kws = keywords(rule)
    ids |= {i for k in kws for i in ids_in(own.any.sub(" ", str(k).upper()), patterns)}
    words = [w for w in meaningful(kws, common) if not own.any.fullmatch(w.upper()) and not any(w in i.lower() for i in ids)]
    return ids, words


def check_evidence(rules, res, patterns, keywords, own, common=()):
    """Warnings when a row's evidence (or one sentence of it) looks like it belongs to another rule.
    Returns ([(score, text)], checked, not_checkable)."""
    warnings, checked, blind = [], 0, 0
    terms = {r["id"]: terms_of(r, patterns, keywords, own, common) for r in rules}
    every = {r["id"]: meaningful(keywords(r)) for r in rules}                # own side: frequent words still count as "this rule"
    sources = {o: t for o, t in terms.items() if len(t[0]) + len(t[1]) >= 2}  # fewer than 2 terms: never a comparison source

    def foreign(rid, text):
        """Best other rule: (number of its terms in text that this rule does not have, rule id, the terms)."""
        found = ids_in(own.any.sub(" ", text), patterns)
        best = (0, "", [])
        for o in sorted(sources):
            if o == rid:
                continue
            ids, words = sources[o]
            hits = sorted(found & (ids - terms[rid][0])) + [w for w in words if w not in every[rid] and has_word(w, text)]
            if len(hits) > best[0]:
                best = (len(hits), o, hits)
        return best

    def mentions_own(rid, text):
        return bool(ids_in(own.any.sub(" ", text), patterns) & terms[rid][0]) or any(has_word(w, text) for w in every[rid])

    for r in rules:
        rid = r["id"]; v = res.get(rid)
        if not v:
            continue
        mine = terms[rid][0]
        ev = f"{v.get('evidence', '')} {v.get('target_loc', '')}"
        theirs = ids_in(own.any.sub(" ", ev), patterns)
        if not every[rid] and not (mine and theirs):
            blind += 1; continue
        checked += 1
        if mine and theirs and not mine & theirs:
            warnings.append((len(theirs) + 1, f"{rid}: evidence IDs ({', '.join(sorted(theirs))}) do not overlap the rule's IDs ({', '.join(sorted(mine))})"))
        if not every[rid] and not mine:
            continue
        whole = f"{ev} {v.get('issue', '')}"
        if not mentions_own(rid, whole):
            n, o, hits = foreign(rid, whole)
            if n >= 2:
                warnings.append((n + 10, f"{rid}: evidence uses none of the rule's keywords but {n} of {o}'s ({', '.join(hits[:5])}): is it written on the wrong row?"))
            continue
        parts = [x for k in ("evidence", "issue") for x in SENTENCES.split(str(v.get(k, ""))) if x.strip()]
        if len(parts) < 2:
            continue
        worst = max(((*foreign(rid, x), x) for x in parts if not mentions_own(rid, x)), key=lambda t: t[0], default=None)
        if worst and worst[0] >= 2:
            n, o, hits, sentence = worst
            warnings.append((n, f"{rid}: one sentence of the row has nothing of this rule but {n} term(s) of {o} ({', '.join(hits[:5])}): "
                                f"«{cell(sentence.strip())[:90]}» — does it belong to another row?"))
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
def check_internal(findings, rules, res, patterns, keywords, params, verdicts, own, self_rules=(), self_res=None, common=()):
    errors, warnings, seen = [], [], set()
    by = {r["id"]: r for r in rules}
    for f in findings:
        fid = f.get("id", "")
        if not re.fullmatch(re.escape(own.p["finding"]) + r"-\d+", fid) or not str(f.get("text", "")).strip():
            errors.append(f"internal.json: every finding needs an id {own.p['finding']}-n and a text ({fid or f})"); continue
        if fid in seen: errors.append(f"{fid}: duplicate internal finding id")
        seen.add(fid)
        listed = f.get("rules") or []
        mine = f.get("self_rules") or []
        if not listed and not mine and not str(f.get("no_rule_reason", "")).strip():
            errors.append(f"{fid}: list the rules it concerns (rules / self_rules), or give no_rule_reason")
        by_self = {r["id"]: r for r in self_rules}
        for sid in mine:
            if sid not in by_self:
                errors.append(f"{fid}: {sid} is not in self_rules.json")
            elif not re.search(r"(?<![\w-])" + re.escape(fid) + r"(?!\d)", text_of((self_res or {}).get(sid))):
                errors.append(f"{fid}: it concerns {sid} but the row of {sid} does not mention {fid}")
        said = f"{f.get('text', '')} {' '.join(f.get('ids') or [])}"
        for sid, r in by_self.items():
            if r.get("doc_id") and sid not in mine and self_rules_mod.occurs(r["doc_id"], said):
                errors.append(f"{fid}: mentions {r['doc_id']} (the target's own rule {sid}) but \"self_rules\" does not list {sid}")
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
                mine_words = meaningful(keywords(r), common)
                words = [w for w in mine_words if has_word(w, low)] if len(mine_words) >= 2 else []
                if shared or len(words) >= 2:
                    warnings.append((len(shared) * 2 + len(words), f"{fid}: may also concern {rid} ({', '.join(sorted(shared)) or ', '.join(words[:4])}); bind it or ignore after checking"))
    for r in self_rules:
        sid = r["id"]; v = (self_res or {}).get(sid)
        if sym(v) in ("❌", "⚠️") and not any(sid in (f.get("self_rules") or []) for f in findings):
            errors.append(f"{sid}: the target breaks its own rule ({r.get('doc_id', '')}) but no internal finding binds it (\"self_rules\": [\"{sid}\"])")
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


def self_register(work):
    """(the target's own rules, their results); empty when not used."""
    data, res = read(work, "self_rules.json"), read(work, "self_results.json")
    return (data["rules"] if isinstance(data, dict) else data) or [], res or {}


# ---------- mandatory steps ----------
MANDATORY = ("identity", "reference", "visual", "params", "self-rules", "internal", "self-audit")          # step names for progress.py


def skip_reason(state, step):
    """The recorded reason if the step was deliberately skipped, else '' (a skip without a reason does not count)."""
    v = (state.get("steps") or {}).get(step) or {}
    return str(v.get("reason", "")).strip() if v.get("state") == "skipped" else ""


def missing_step(state, step, label, command):
    """A mandatory step that left no result: (summary line, skipped entry, error or None)."""
    why = skip_reason(state, step)
    if why:
        return f"- {label}: SKIPPED ({why})", (label.lower(), why, 1), None
    return (f"- {label}: NOT RUN ({command})", (label.lower(), "step not run", 1),
            f"{label} not run: run {command}, or record why not: progress.py step work/progress.json {step} skipped --reason \"…\"")


def skip_conflicts(work, rules, res, mine, mine_res, own):
    """A recorded skip is rejected while any output needs the skipped step (its own, if it has content, or another step's)."""
    state = read(work, "progress.json") or {}
    findings, params, verdicts = read(work, "internal.json") or [], read(work, "params.json"), read(work, "param_verdicts.json") or {}
    inv, ref, declared = read(work, "visual_inventory.json"), read(work, "ref_sections.json"), read(work, "self_sections.json")
    ident, audit = read(work, "doc_identity.json"), read(work, "self_audit.json")
    reference = [r for r in rules if own.kind(r) != "self"]
    targets = {declared["doc"]} if declared else set()
    targets |= {o["doc"] for o in (params or {}).get("occurrences", []) if o["role"] == "target"} | {d["doc"] for d in (inv or {}).get("documents", [])}
    finding_ref = re.compile(rf"(?<![\w-]){re.escape(own.p['finding'])}-\d+")
    need = {k: [] for k in MANDATORY}

    # internal: broken own rules, real contradictions inside the target, rows that already cite a finding
    for r in mine:
        s = sym(mine_res.get(r["id"]))
        if s in ("❌", "⚠️"): need["internal"].append(f"{r['id']} {s} (own rule {r.get('doc_id') or (r.get('source') or {}).get('section')})")
    for c in (params or {}).get("conflicts", []):
        if "target-internal" in c["kinds"] and (verdicts.get(c["id"]) or {}).get("verdict") == "real":
            need["internal"].append(f"{c['id']} (parameter conflict inside the target, judged real)")
    for rid, v in {**res, **mine_res}.items():
        cited = sorted(set(finding_ref.findall(text_of(v))))
        if cited: need["internal"].append(f"{rid} cites {', '.join(cited)}")
    need["internal"] += [f"{f.get('id')} (already written in internal.json)" for f in findings]

    need["visual"] = [f"{p['doc']} p{p['page']} (in the visual inventory)" for p in (inv or {}).get("pages", [])]
    need["reference"] = [f"{s['id']} (in the section inventory)" for s in (ref or {}).get("sections", [])] \
        + [f"{r['id']} (comes from section {r['source']['section']})" for r in reference if (r.get("source") or {}).get("section")]
    need["params"] = [f"{c['id']} (conflict in params.json)" for c in (params or {}).get("conflicts", [])] \
        + [f"{k} (has a verdict)" for k in verdicts if not params] + [f"{f.get('id')} (binds {f['param']})" for f in findings if f.get("param")]
    need["identity"] = [f"«{e['name']}» (in doc_identity.json)" for e in (ident or {}).get("documents", [])] \
        + [f"{r['id']} (its source is the target itself)" for r in reference if doc_stem(str((r.get("source") or {}).get("doc", ""))) in targets]
    need["self-rules"] = [f"{c['id']} (candidate in self_sections.json)" for c in (declared or {}).get("candidates", [])] \
        + [f"{r['id']} (row in self_rules.json)" for r in mine] + [f"{i} (result in self_results.json)" for i in mine_res if i not in {r['id'] for r in mine}] \
        + [f"{f.get('id')} (binds {', '.join(f['self_rules'])})" for f in findings if f.get("self_rules")]
    need["self-audit"] = [f"{i} (planned in self_audit.json)" for i in (audit or {}).get("planned", [])]

    errors = []
    for step, waiting in need.items():
        if waiting and skip_reason(state, step):
            errors.append(f"the skip of step «{step}» is rejected, {len(waiting)} item(s) need it: " + "; ".join(waiting)
                          + f". Do the step, then: progress.py step work/progress.json {step} done")
    return errors


# ---------- root findings ----------
def root_findings(rows, findings, own):
    """rows: [(id, result)] of the violating rows. A root finding is ONE internal finding (IF-n); rows bound to no finding are grouped
    by identical target location and issue text. Groups never chain: a row bound to two findings is listed under each.
    Returns [{"findings": [IF-n] or [], "rows": [ids], "label": str}] in order of the first row."""
    known = {str(f.get("id")) for f in findings}
    rx = re.compile(rf"(?<![\w-]){re.escape(own.p['finding'])}-\d+(?!\d)")

    def norm(s):
        return " ".join(re.findall(r"\w+", fold(own.any.sub(" ", str(s or "")))))

    groups = {}
    for rid, v in rows:
        mine = {f["id"] for f in findings if rid in (f.get("rules") or []) + (f.get("self_rules") or [])} | (set(rx.findall(text_of(v))) & known)
        loc, issue = norm(v.get("target_loc")), norm(v.get("issue"))
        keys = sorted(mine, key=lambda x: int(x.rsplit("-", 1)[1])) or [(loc, issue) if loc and issue else (rid,)]
        for k in keys:
            groups.setdefault(k, []).append(rid)
    out = []
    for key, members in groups.items():          # insertion order: first row, then finding number
        finding = key if isinstance(key, str) else None
        head = finding or ("same location and issue" if len(members) > 1 else "")
        out.append({"findings": [finding] if finding else [], "rows": members,
                    "label": f"{head} → {', '.join(members)}" if head else members[0]})
    return out


# ---------- everything, for gates.collect ----------
def collect(work, rules, res, patterns_file=None, report_text=None):
    """{summary, sections, required, errors, skipped}"""
    from matrix import keywords
    if patterns_file is None and (Path(work) / "id_patterns.json").exists():
        patterns_file = Path(work) / "id_patterns.json"
    patterns, _ = load_patterns(patterns_file)
    chosen, prefix_data = prefixes.load(work); own = Own(chosen)
    out = {"summary": [], "sections": [], "required": [], "errors": [], "skipped": [], "warnings": [], "roots": []}
    sections, tbd, findings = read(work, "ref_sections.json"), read(work, "tbd.json"), read(work, "internal.json")
    mine, mine_res = self_register(work)
    files, errs = prefixes.texts(work); out["errors"] += errs
    params, verdicts = read(work, "params.json"), read(work, "param_verdicts.json")

    if prefix_data is None:
        out["summary"].append("- ID prefixes: NOT RUN (prefixes.py)")
        out["errors"].append("ID prefixes not chosen: run prefixes.py on the extracted target and references (work/prefixes.json)")
    else:
        out["summary"].append(prefixes.describe(prefix_data))
        for kind, p in chosen.items():
            used = prefixes.first_use(p, files)
            if used: out["errors"].append(f"the {prefixes.LABEL[kind]} prefix {p}- collides with the documents ({used}): run prefixes.py again and renumber")
    for r, kind in [(r, own.kind(r)) for r in rules] + [(r, "self") for r in mine]:
        want = chosen[kind]
        if not re.fullmatch(re.escape(want) + r"-\d+", r["id"]):
            out["errors"].append(f"{r['id']}: register IDs must use the chosen prefix {want}-")
    for r in rules:
        if own.kind(r) == "self":
            out["errors"].append(f"{r['id']}: the target's own rules belong in self_rules.json, not in the reference register")
    for t in tbd or []:
        if not re.fullmatch(re.escape(chosen["tbd"]) + r"-\d+", str(t.get("id", ""))):
            out["errors"].append(f"tbd.json {t.get('id')}: decision IDs must use the chosen prefix {chosen['tbd']}-")
    for rid, v in {**res, **mine_res}.items():
        problem = verdict_problem(v, own)
        if problem: out["errors"].append(f"{rid}: {problem}")
    errs, warnings = check_aggregates(rules + mine, {**res, **mine_res}, sections, own); out["errors"] += errs
    common = common_words(files, rules)
    warnings = [(100, x) for x in warnings]                                  # structural warnings come first
    w, checked, blind = check_evidence(rules, res, patterns, keywords, own, common); warnings += w

    texts = [(f"results of {rid}", text_of(v)) for rid, v in {**res, **mine_res}.items()]
    texts += [(f"internal finding {f.get('id')}", str(f.get("text", ""))) for f in findings or []]
    if report_text: texts.append(("the report", report_text))
    out["errors"] += check_references(rules + mine, texts, tbd, own)

    out["errors"] += skip_conflicts(work, rules, res, mine, mine_res, own)

    # ---------- the target's own rules ----------
    declared = read(work, "self_sections.json")
    if declared is None:
        line, entry, error = missing_step(read(work, "progress.json") or {}, "self-rules", "Target's own rules", "self_rules.py scan")
        out["summary"].append(line); out["skipped"].append(entry)
        if error: out["errors"].append(error)
        if mine: out["errors"].append("self_rules.json exists but self_rules.py scan was not run (self_sections.json)")
    else:
        target = next((f for f in files if doc_stem(f) == declared["doc"]), None)
        if target is None: out["errors"].append(f"target's own rules: the extracted target {declared['doc']}.txt was not found")
        out["errors"] += self_rules_mod.check(declared, mine, mine_res, "\n".join(f"{l}\t{t}" for l, t in parse_lines(target)) if target else None)
        copied = {r.get("doc_id") for r in mine if r.get("doc_id")}
        for r in rules:
            src = r.get("source") or {}; quote = str(src.get("quote", ""))
            hit = next((d for d in sorted(copied) if quote.startswith(d) and self_rules_mod.occurs(d, quote)), None)
            if hit and doc_stem(str(src.get("doc", ""))) == declared["doc"]:
                out["errors"].append(f"{r['id']}: {hit} is the target's own rule: register it only in self_rules.json (the target would verify itself)")
        done = sum(1 for c in declared["candidates"] if c.get("class") in self_rules_mod.CLASSES)
        tally = ", ".join(f"{k} {n}" for k in ("✅", "❌", "⚠️", "➖", "❓", DECISION) if (n := sum(1 for r in mine if sym(mine_res.get(r["id"])) == k)))
        out["summary"].append(f"- Target's own rules: {len(mine)} (judged separately, not part of reference coverage): {tally or 'none'}; candidates classified {done}/{len(declared['candidates'])}")
        out["sections"] += ["## Target's own rules (self-declared)", "| Candidate | Kind | Declared IDs | Class | Reason |", "|---|---|---|---|---|"]
        for c in declared["candidates"]:
            line = f"| {cell(c['id'])} | {c['kind']} | {cell(', '.join(c['ids']))} | {c.get('class') or '**UNCLASSIFIED**'} | {cell(c.get('reason'))} |"
            out["sections"].append(line); out["required"].append(line)
        out["sections"] += ["", "| Own rule | Declared as | Result | Evidence | Issue | Suggested fix |", "|---|---|---|---|---|---|"]
        for r in mine:
            v = mine_res.get(r["id"]) or {}; src = r.get("source") or {}
            line = (f"| {r['id']} | {cell(r.get('doc_id') or src.get('section'))} p{src.get('page', '?')} | {sym(v) or '**NO RESULT**'} | {cell(v.get('evidence'))} | "
                    f"{cell(v.get('issue'))} | {cell(v.get('fix'))} |")
            out["sections"].append(line); out["required"].append(line)
        out["sections"].append("")

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
        line, entry, error = missing_step(read(work, "progress.json") or {}, "internal", "Internal findings", "step 4 (work/internal.json, [] if there are none)")
        out["summary"].append(line); out["skipped"].append(entry)
        if error: out["errors"].append(error)
    else:
        errs, w = check_internal(findings, rules, res, patterns, keywords, params, verdicts, own, mine, mine_res, common); out["errors"] += errs; warnings += w
        bound = sum(1 for f in findings if f.get("rules") or f.get("self_rules"))
        out["summary"].append(f"- Internal findings: {len(findings)} (bound to rules: {bound}, without a rule: {len(findings) - bound})")
        out["sections"] += ["## Internal findings bound to rules", "| Finding | IDs | Rules | Text |", "|---|---|---|---|"]
        for f in findings:
            line = f"| {f.get('id')} | {cell(', '.join(f.get('ids') or []))} | {cell(', '.join((f.get('rules') or []) + (f.get('self_rules') or [])) or 'none: ' + str(f.get('no_rule_reason', '')))} | {cell(f.get('text'))} |"
            out["sections"].append(line); out["required"].append(line)
        out["sections"].append("")

    audit = read(work, "self_audit.json")
    state = read(work, "progress.json") or {}
    skip = bool(skip_reason(state, "self-audit"))
    if audit is not None and not skip:
        if not audit.get("seed") or audit.get("seed") != state.get("audit_seed"):
            out["errors"].append("self-audit seed does not match progress.json: the selection must come from the seed created when the step started")
            audit = {**audit, "seed": audit.get("seed") or ""}
    if audit is None or skip:
        line, entry, error = missing_step(state, "self-audit", "Self-audit", "matrix.py audit-plan / audit-record")
        out["summary"].append(line); out["skipped"].append(entry)
        if error: out["errors"].append(error)
    else:
        errs, need, done, changed = check_audit(rules + mine, {**res, **mine_res}, audit)
        out["errors"] += errs
        line = f"- Self-audit: re-checked {len(done)}/{len(need)} planned rows (all ❌/⚠️/{DECISION} and a random 10% of ✅; seed {audit['seed']}, {audit.get('seed_source', '?')}); changed: {len(changed)}"
        out["summary"].append(line)
        block = ["## Changed in self-audit (öz-denetimde değişti)", *(changed or ["- (no verdict changed)"])]
        out["sections"] += block + [""]; out["required"] += block

    ranked = [t for _, t in sorted(warnings, key=lambda x: -x[0])]          # highest score first, ties keep their order
    out["warnings"] = ranked
    rest = len(ranked) - WARNING_LIMIT
    out["summary"].append(f"- Judgement warnings: {len(ranked)} (evidence fit checked on {checked} rows, not checkable on {blind})"
                          + (f"; the {WARNING_LIMIT} highest-scoring are listed, {rest} more only counted" if rest > 0 else ""))
    if ranked:
        lines = [f"- {x}" for x in ranked[:WARNING_LIMIT]]
        if rest > 0:
            lines.append(f"- … plus {rest} more warning(s) with a lower score (all of them: judgement_warnings.txt in the work folder)")
        out["sections"] += ["## Judgement warnings (check each one)", *lines, ""]; out["required"] += lines

    bad = [(r["id"], v) for r in rules + mine if sym(v := {**res, **mine_res}.get(r["id"])) in ("❌", "⚠️")]
    out["roots"] = root_findings(bad, findings or [], own)
    own_bad = sum(1 for i, _ in bad if i in {r["id"] for r in mine})
    out["summary"].append(f"- Violations: {len(bad)} rows (❌/⚠️, {own_bad} of them the target's own rules), {len(out['roots'])} root findings")
    out["required"] += out["summary"]
    return out
