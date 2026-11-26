# 3. Traceability

Process the rules ONE BY ONE (never in groups); for each, read the whole rule and the relevant part of the target side by side and give ONE result:
✅ Compliant (evidence: page/ID in target) | ❌ Violation | ⚠️ Partial | ➖ Not applicable (reason) | ❓ Cannot verify (what is missing)

Work in **blocks of 20** rules. Get the candidates of a whole block with one command (`search.py … --rules work/rules.json --block N`, or `--all-blocks` once) and read `work/candidates_part_NN.md`; collect further search terms and run them in ONE `search.py -t … -t …` call instead of one grep per term. After each block write the part as JSON and record it (checkpoint; work can resume even if the context fills up):
```json
{"R-001":{"result":"✅","evidence":"p4 UC-2.1 heading present"},
 "R-002":{"result":"❌","evidence":"…","target_loc":"p7 UC-3.8","issue":"…","fix":"…","severity":"high"}}
```
When resuming (new session/context) run `status` first and continue with the remaining rules. Empty `evidence` is rejected. For "absence" violations write where you looked. `matrix.py skeleton work/rules.json work/ex/target.txt -o work/matrix` gives the same hints as one CSV/MD matrix for all rules. The candidate list (skeleton / search.py) is only a hint; even with no candidate, search the target for the rule.
