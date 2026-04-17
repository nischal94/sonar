---
description: Run the full Sonar verification ladder (fastest-signal order) and report per-step results
---

Run the Sonar verification ladder in the exact order below. Stop at the first failure — there's no point running slower checks if faster ones are broken.

Report pass/fail per step. At the end, print a single-line summary.

## 1. Frontend type check (~5 sec)
```bash
cd frontend && npx --no-install tsc --noEmit
```

## 2. Backend lint (~2 sec, advisory — don't block on this)
```bash
docker compose exec -T api uv tool run --from ruff ruff check backend/app backend/tests
```

## 3. Frontend build (~10 sec)
```bash
cd frontend && npm run build
```

## 4. Backend unit tests (~10 sec)
```bash
docker compose exec -T api pytest -q --tb=short
```

## 5. Frontend unit tests (if configured)
```bash
cd frontend && npm run test -- --run 2>&1 || echo "no vitest configured yet"
```

## 6. Backend docker image build (~30-60 sec, optional unless Dockerfile changed)
Only run if the user explicitly asked for the full ladder, or if `git diff --name-only` shows `backend/Dockerfile` changed.
```bash
docker compose build api
```

## Final report format

```
Verification ladder:
  1. Frontend tsc    : PASS / FAIL (N errors)
  2. Backend ruff    : PASS / FAIL (advisory, not blocking)
  3. Frontend build  : PASS / FAIL
  4. Backend pytest  : PASS / FAIL (X passed, Y failed)
  5. Frontend tests  : PASS / FAIL / SKIPPED (N passed, M failed)
  6. Docker build    : PASS / FAIL / SKIPPED

Summary: PASS | FAIL at step N
```

If any step FAILS, stop there and output the last ~20 lines of that step's output so the user (or Claude in a subsequent turn) can see what broke.

## Notes

- The Stop hook at `.claude/hooks/verify.sh` runs steps 4 + 1 automatically whenever Claude ends a turn with code changes. `/verify` is for when you want the full ladder manually or Claude needs to run it mid-session before reporting "done."
- Docker stack must be up: `docker compose up -d api postgres redis` — the `/verify` runner does NOT start services, it assumes they're already running.
- If `frontend/node_modules` is missing, run `cd frontend && npm ci` first.
