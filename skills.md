# Remixa — guidance for Linear Coding Sessions

Full guidance: see AGENTS.md (architecture, conventions, gotchas). Essentials:

- Backend tests: `cd backend && pytest` (the `--cov-fail-under=70` gate must pass)
- Frontend: `cd frontend && npm run lint && npm run type-check && npm run build`
- Run: backend `uvicorn main:app --reload`; frontend `npm run dev`
- Migrations are a MANUAL list (`apply_migrations.py` runs only database.sql/002/004) — apply new ones with psql.
- Branch `floorno8/fn8-NNN-slug` so Linear native GitHub linking binds the issue.
