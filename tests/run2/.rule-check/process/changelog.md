# Changelog

## v1 — 2026-11-24 (document Rev 1)
- Changed nodes: (initial model) SP-1.1…SP-1.5, SP-1.X1, SP-2.1…SP-2.3; P-reminder, P-approval; invariants I-01…I-08
- Reason: first run (flow A); model_check 0 errors, all invariants PASS

## v2 — 2026-11-24 (document Rev 2)
- Changed nodes: SP-1.5, SP-1.6, SP-2.2
- Reason: Rev 2 diff: SP-2.2 expected change (✅), SP-1.6 new step (🆕, assumption), SP-1.5 next linked. Regression SP-1.4 order (❌) and unpropagated P-reminder 3→5 (⚠️) await a decision: not written to the model, TBD D-order/D-reminder.

