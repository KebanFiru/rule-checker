# 1. Reference coverage and the rule register

Run `extract.py` on the references and READ them page by page (all of it). Before or during reading run `section_inventory.py scan` on all references; after reading, classify EVERY section BEFORE writing rules (`section_inventory.py classify work/ref_sections.json classes.json`):

| class | typical content | what to do |
|---|---|---|
| `rule-bearing` | functional requirements, constraints, TO-BE functions, table values | EVERY checkable statement becomes an atomic rule; every item of a TO-BE list is its own rule |
| `fact` | AS-IS description, interview notes | not a rule, but a fact `F-001…` to check in the target: does anything there contradict it (an AS-IS duration, fee, actor responsibility, system name)? Same result symbols as rules |
| `open-question` | undecided points | one-line reason; list under TBD |
| `descriptive-only` | motivation, introduction | one-line reason; the report warns if such a section contains numbers, durations or "shall/must/zorunlu/gerekir": re-read those |

The script's heading detection is heuristic: check its list against the table of contents. If it merged sections, read the merged section as a whole and give it the strictest class that applies (rule-bearing before fact); if a section needs both rules and facts, class it rule-bearing and add the facts too.

Split every checkable statement into an atomic rule (if one sentence has two conditions joined by "and", make two rules) and number them `R-001…`. Per rule: source document + page + **section id** (`source.section`) + short quote (original language), type (required content / prohibition / format / numeric value / process order / terminology / template section), scope (which parts of the target it applies to), optional `keywords`. Facts additionally carry `"kind": "fact"`. Put interpretation in a separate field (`interpretation`), never mixed into the rule itself. If the same rule is worded differently in two places, register both. Output: `work/rules.json` + `work/rule_register.md` (see `templates/rule_register.md`). Never invent a rule or value that has no source; what the reference does not answer becomes "TBD / team decision". Mark your own assumptions with "ASSUMPTION:".
