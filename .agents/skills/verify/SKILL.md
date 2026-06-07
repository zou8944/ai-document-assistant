---
name: verify
description: Run lint and type checks across the backend and frontend to verify code quality before marking work as done.
---

# /verify

Run the full verification suite across the codebase.

## Backend checks

```bash
cd backend && uv run ruff check . && uv run mypy .
```

## Frontend checks

```bash
cd frontend && npm run lint && npm run type-check
```

## Workflow

1. Run backend checks first. If they fail, stop and report the errors.
2. Run frontend checks. If they fail, stop and report the errors.
3. If everything passes, report success.

## Notes

- Backend tests are not currently prioritized, so this skill only runs lint and type checks.
- The backend uses `uv` for dependency management and script execution.
- If `ruff check` reports auto-fixable issues, you may run `uv run ruff check --fix .` before re-running.
