# DISCOVER — O: First Hypothesis (≥2 divergent paths)

**Observation:** A money-critical platform is asserted "production-ready" by its autonomous builder (bob), live `/health` is green, but the build is unstamped and the only path that applies the money-correctness migration to prod is a manual step whose plan sits incomplete and untracked.

### H1 (leading) — "Claimed, not verified": money invariants are NOT in prod
Migration 004 was written, tested in code, committed (`abdde15`), but **never manually applied to the production DB**. `/health` is green only because it tests connectivity, not schema. The platform would silently violate conservation/idempotency on real payouts. **The real blocker is correctness, and the deliverable is: prove the gap, then either apply 004 (Type-1, needs Stefan ratification) or declare NO-GO.**
*Predicts:* psql introspection shows `check_conservation_invariant` etc. ABSENT.

### H2 (alternative) — "Applied but unobservable": invariants ARE in prod, ungoverned
bob (or a prior session) manually ran 004 via `fly ssh`; constraints exist. The real gap is **observability/governance**: no version stamping, no constraint-health endpoint, no FN8 ledger entry recording the Type-1 schema change. **The deliverable is then: stamp reality, add a constraint-health check, close the version:unknown gap.**
*Predicts:* psql introspection shows all 5 objects PRESENT.

### The tie-breaker is a single read-only query
Both hypotheses are resolved by the same `pg_constraint`/`information_schema` introspection. Do not build on either until that query runs. If prod DB is unreachable (Fly token invalid per NEXT_STEPS_PROMPT), the honest output is "unverifiable from here — exact command handed to Stefan," NOT an assumed verdict.

### Divergent secondary lens
Even under H2 (constraints present), items #3 (auth stubs) and #4 (C2PA disabled) mean the broader "production-ready" claim is still false. So the go/no-go has two layers: (a) money-correctness (sharp, binary, verifiable) and (b) general production-readiness (clearly NO given stubbed auth + disabled C2PA).
