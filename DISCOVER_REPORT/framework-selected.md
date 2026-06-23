# DISCOVER — V: Framework Selected

**Primary: Pre-mortem + Munger Inversion.**
Rationale: this is a *money-critical, production, potentially-irreversible* (DB constraints + real payouts) decision — a Type-1 surface per FN8 router. The governing question is inverted: *"What would make this a catastrophe?"* → paying out more than collected, double-credits on webhook replay, losing a grandparent's royalty on GDPR erasure. Pre-mortem forces verification of the exact mechanisms that prevent those, rather than accepting a green dashboard.

**Secondary lens 1: OODA (verify-first).**
On cold-start the correct loop is Observe→ground-truth before Act. No edits to prod, no "apply migration" without Stefan ratification. First move is read-only introspection (low-risk, high-signal, reversible).

**Secondary lens 2: Eisenhower (triage theater vs. signal).**
The handoff bundles one urgent-important item (are the invariants live?) with a pile of not-important ceremony (team meeting, sign-off matrix, Day1/2/3). Triage: do the one verification, drop the ceremony, hand Stefan a decision.

## Operating constraints for this engagement
- **No Type-1 action without Stefan ratification.** Applying migration 004 to prod, rotating tokens, or any schema change = ratification gate. I verify and recommend; Stefan decides.
- **Deliverable = claimed-vs-verified table with real command output**, not a new markdown doc (the repo is already doc-saturated; pain #6).
- **Parallelizable slice (ultracode):** verify each section of `DEPLOYMENT_OPERATIONS_GUIDE.md` + `TESTING_QA_GUIDE.md` claim-by-claim against actual code/state — fan out (one agent per section). Keep the prod-DB introspection sequential (single source of truth, no benefit to fan-out).
- **Honesty rule:** if prod DB is unreachable, report "unverifiable + exact command," never an assumed verdict.
