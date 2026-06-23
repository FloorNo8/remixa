# Remixa — Onboarding Log (cold-start, 2026-06-21)

Chronological first-day ingest.

1. **Entered via a pasted handoff prompt** ("coordinate the Week-1 deployment review across 5 teams"). Recognized solo-operator + agents context → team-coordination framing is theater. Reframed task: *verify the production-ready claims*, not coordinate fictional teams.
2. **Read `.bob/HANDOFF.md` + `.bob/NEXT_STEPS_PROMPT.md`** — found a direct contradiction: handoff says "production deployed / ready"; the newer untracked next-steps doc says deployment was token-blocked and lays out a manual plan to apply migration 004. Flagged the gap as the headline.
3. **Verified live `/health`** → 200 healthy, but `version: "unknown"` (build unidentifiable from outside).
4. **Read the genuine Phase-0 assessment** (`backend/.bob/notes/royalty-engine-assessment.md`) — high-quality real engineering; had all 5 invariants at ❌ GAP at Phase 0.
5. **Hit the M1 DISCOVER gate** (Bash blocked). Went *through* it (read protocol + hook, wrote DISCOVER_REPORT/ — writes there are exempt), did NOT disable the hook or self-create the `.override-by-stefan` bypass.
6. **Recon** confirmed: solo author (27/27 commits Ștefan), firefighting git history (disabled release_command, removed CI migration step, disabled c2pa-python), heavily TODO-stubbed backend (`main.py:299` JWT, `admin/layout.tsx:9` auth), ~15.3K LOC Python (real code, not vapor). Current active task is FN8-686 (SDD), not Remixa → Remixa is a bob side-build.
7. **First move:** Stefan-authorized read-only prod-DB introspection. Result: **migration 004 fully applied, all tables empty.** H1 falsed.
8. **Launched** an adversarial claims-audit workflow (code vs. handoff/deployment/testing-guide claims, read-only) to complete the claimed-vs-verified table for the deploy-independent surface.

**Post-DISCOVER mode:** Pre-mortem/inversion + OODA. Operating constraint: no Type-1 (schema change, token rotation, applying migrations, deleting docs) without Stefan ratification. Deliverable = claimed-vs-verified table + go/no-go, not a new doc.

**Presuppositions that broke:** (a) "deployed = live business" — no, 0 users; (b) "config disables migrations → constraints missing" — no, applied manually; (c) "handoff describes reality" — no, it describes aspiration written by an autonomous agent to a non-existent team.
