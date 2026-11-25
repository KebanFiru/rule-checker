## Summary
Total rules: 25 — ✅ 13, ❌ 12, ⚠️ 0, ➖ 0, ❓ 0

## Coverage table
| Rule | Source | Result | Evidence / Reason |
|---|---|---|---|
| R-001 | rules.pdf s.1 | ✅ | target p1:L1 «Software Requirements Specification» |
| R-002 | rules.pdf s.1 | ❌ | p1:L2 only «Rev 2»; no «Version X.Y» |
| R-003 | rules.pdf s.1 | ✅ | p1:L3 «Author: Ali Veli» |
| R-004 | rules.pdf s.1 | ❌ | p1:L4 «Date: 2026-03-14» (YYYY-MM-DD) |
| R-005 | rules.pdf s.1 | ✅ | p1:L9 «1. Introduction» |
| R-006 | rules.pdf s.1 | ❌ | Headings 1–6 (Introduction, Glossary, Requirements, Use Cases, Screen Designs, Appendices); the word 'scope' does not occur anywhere in the document |
| R-007 | rules.pdf s.1 | ✅ | p1:L11 «2. Glossary» |
| R-008 | rules.pdf s.1 | ✅ | FR-1…FR-6 (p1:L10-20) all carry FR-N identifiers |
| R-009 | rules.pdf s.1 | ✅ | UC-1.1, UC-1.2, UC-2.1, UC-2.2 (p1:L23-33) |
| R-010 | rules.pdf s.1 | ❌ | p1:L18 FR-5 «The system can provide reports» |
| R-011 | rules.pdf s.1 | ❌ | p1:L19 FR-6 «appropriate format … if needed … etc.» |
| R-012 | rules.pdf s.1 | ❌ | p1:L15 FR-2 «at least 6 characters» ≠ 8 |
| R-013 | rules.pdf s.1 | ❌ | p1:L16 FR-3 «30 minutes» ≠ 15 |
| R-014 | rules.pdf s.2 | ✅ | p1:L22 QR-A.2 «at most 3 seconds» |
| R-015 | rules.pdf s.2 | ❌ | p1:L34 UC-2.2 «Priority: Urgent» (allowed: High/Medium/Low) |
| R-016 | rules.pdf s.2 | ❌ | p2 has three images; Figure 1 (p2:L2) and Figure 2 (p2:L3) have captions, the «Report Screen» image has none (PDF page 2) |
| R-017 | rules.pdf s.2 | ✅ | Table 1 (p1:L5), Table 2 (p1:L23) are numbered |
| R-018 | rules.pdf s.2 | ✅ | QR-A.1, QR-A.2 (p1:L17-22) |
| R-019 | rules.pdf s.2 | ❌ | p1:L21 QR-A.1 «Passwords shall be stored in plain text» — the opposite of the rule |
| R-020 | rules.pdf s.2 | ❌ | p1:L25 Table 2 «250 USD»; p2:L3 uses € (mixed) |
| R-021 | rules.pdf s.2 | ✅ | Last section p2:L4 «6. Appendices» (the document ends with it) |
| R-022 | rules.pdf s.2 | ❌ | FR-5 (p1:L18) has no UC reference; FR-4 points to UC-9.9, which does not exist (see internal consistency) |
| R-023 | rules.pdf s.2 | ✅ | Table 1 Revision history (p1:L5) |
| R-024 | rules.pdf s.2 | ✅ | 'customer' does not occur in the document; 'User' is in the glossary p1:L12 |
| R-025 | rules.pdf s.2 | ✅ | Page 1 (p1:L35), Page 2 (p2:L6) footer |

## Violations

| # | Rule | Source | Target location | Issue | Suggested fix | Severity |
|---|---|---|---|---|---|---|
| 1 | R-002 ❌ | rules.pdf s.1 | p1:L2 | Version is written «Rev 2» | Write «Version 2.0» | medium |
| 2 | R-004 ❌ | rules.pdf s.1 | p1:L4 | Date format is not DD.MM.YYYY | 14.03.2026 | low |
| 3 | R-006 ❌ | rules.pdf s.1 | whole document | No Scope section | Add a «Scope» section after the Introduction (content: TBD, team decides) | high |
| 4 | R-010 ❌ | rules.pdf s.1 | p1:L18 FR-5 | «can» is optional wording | «shall provide» | high |
| 5 | R-011 ❌ | rules.pdf s.1 | p1:L19 FR-6 | 3 vague terms: appropriate/if needed/etc. | Write concrete format and condition (content: TBD team decision) | medium |
| 6 | R-012 ❌ | rules.pdf s.1 | p1:L15 FR-2 | Password length is 6 | Make it 8 | high |
| 7 | R-013 ❌ | rules.pdf s.1 | p1:L16 FR-3 | Session timeout is 30 min | Make it 15 minutes | high |
| 8 | R-015 ❌ | rules.pdf s.2 | p1:L34 UC-2.2 | Invalid priority value | One of High/Medium/Low (team chooses: TBD) | medium |
| 9 | R-016 ❌ | rules.pdf s.2 | p2 third image | No Figure caption/number | Add a «Figure 3 Report screen» caption | medium |
| 10 | R-019 ❌ | rules.pdf s.2 | p1:L21 QR-A.1 | Plain-text storage is mandated | «…shall be stored hashed» (algorithm: TBD) | high |
| 11 | R-020 ❌ | rules.pdf s.2 | p1:L25 Table 2 | Amount is in USD | Show in € (amount: TBD, do not invent an exchange rate) | medium |
| 12 | R-022 ❌ | rules.pdf s.2 | p1:L18 FR-5 | No UC traceability | Link FR-5 to the relevant UC (add the UC if missing: TBD) | medium |
