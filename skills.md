# Remixa — guidance for Linear Coding Sessions

Full guidance: see AGENTS.md (architecture, conventions, gotchas). Essentials:

- Backend tests: `cd backend && pytest` (the `--cov-fail-under=70` gate must pass)
- Frontend: `cd frontend && npm run lint && npm run type-check && npm run build`
- Run: backend `uvicorn main:app --reload`; frontend `npm run dev`
- Migrations are tracked dynamically. Apply Type-1 migrations in production via `flyctl ssh console -a eu-sound-lab -C "sh -c 'cd /app && python3 apply_migrations.py --apply-ratified <filename>'"` rather than blocking for manual developer execution.
- Branch `floorno8/fn8-NNN-slug` so Linear native GitHub linking binds the issue.
