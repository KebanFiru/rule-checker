# 4. Internal consistency pass (outside the rules but mandatory)

Broken references, undefined/duplicate IDs and numbering gaps from xref_check; the same value appearing differently in different places (durations, amounts, codes, ECTS, dates; start from the judged parameter conflicts); the same concept under different names; text inside screens/figures vs body text. Write findings to `work/internal.md`.

Every contradiction INSIDE the target also goes into `work/internal.json` as `IF-n` (this includes screen-vs-body differences from step 5: add them when found, and parameter conflicts judged `real`, with `"param"`):
```json
[{"id":"IF-1","text":"UC-3.7.EX.2 says …, screen S-4.1 says …","ids":["UC-3.7.EX.2","S-4.1"],"rules":["R-012"],"param":"P:reminder:time"},
 {"id":"IF-2","text":"…","ids":["S-1.4"],"rules":[],"no_rule_reason":"no reference rule covers this"}]
```
For each finding ask which rules its topic falls under. Each listed rule's row must mention the `IF-n` (set-bulk it again); broken rules of the target itself go in `"self_rules"` (see `4-self-rules.md`); a finding with neither needs `no_rule_reason`. The report warns about rules that share IDs or keywords but are not listed. (`IF-` is the skill's own prefix; the documents' IDs such as `IC-3` are ordinary document IDs.)
