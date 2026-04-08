# Contributing to Sonar

## Development Setup

### Prerequisites

- Docker and Docker Compose
- Git
- Node 20+ (for frontend work without Docker)
- Python 3.12+ (for backend work without Docker)

### First-time setup

```bash
git clone https://github.com/nischal94/sonar.git
cd sonar
cp .env.example .env
# Edit .env with your API keys
docker compose up --build
docker compose exec api alembic upgrade head
```

Verify everything is running:
- `http://localhost:8000/health` → `{"status": "ok"}`
- `http://localhost:8000/docs` → Swagger UI
- `http://localhost:5173` → React onboarding page

---

## Branch Naming

```
feat/description      # new feature
fix/description       # bug fix
refactor/description  # refactoring (no behavior change)
docs/description      # documentation only
test/description      # tests only
chore/description     # build, deps, tooling
```

Examples:
- `feat/slack-thread-replies`
- `fix/embedding-timeout`
- `docs/api-reference`

---

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add weekly intelligence digest email
fix: handle missing timezone on posted_at field
refactor: extract threshold constants to config
test: add unit test for timing score decay
docs: update extension install instructions
chore: bump openai to 1.50.0
```

The subject line should explain **why**, not just what changed. Keep it under 72 characters.

---

## Making Changes

### Backend

1. Run the test suite before you start — make sure you have a clean baseline:
   ```bash
   docker compose exec api pytest tests/ -v
   ```

2. Make your changes. Write or update tests for any new behavior.

3. Run tests again:
   ```bash
   docker compose exec api pytest tests/ -v --tb=short
   ```

4. If you changed models, create a migration:
   ```bash
   docker compose exec api alembic revision --autogenerate -m "describe the change"
   ```
   Review the generated migration file before committing — autogenerate misses some things (e.g. pgvector columns, raw index types).

### Frontend

1. Start the dev server:
   ```bash
   docker compose up frontend
   # or: cd frontend && npm install && npm run dev
   ```

2. Make changes. The dev server hot-reloads.

3. Verify the TypeScript build passes:
   ```bash
   cd frontend && npm run build
   ```

### Chrome Extension

1. Load the unpacked extension from `extension/` in Chrome dev mode.
2. After editing JS files, click the **reload** button on `chrome://extensions`.
3. Test on a real LinkedIn feed.

---

## Code Standards

### Python (backend)

- Always use `get_settings()`, never module-level `settings = Settings()`
- Use `sqlalchemy.text()` for all raw SQL — never f-strings
- Use pydantic v2 style: `model_config = {"from_attributes": True}`, not inner `class Config`
- Handle errors explicitly — no bare `except:` or silent swallows
- Keep Celery tasks thin: they should call `asyncio.run(_async_implementation())`
- Log errors with context: `[Module] Operation failed: reason. context_key: value`

### TypeScript (frontend)

- Use typed API interfaces (see `src/api/client.ts`) — no `any`
- Keep components small and focused
- Error states must be visible to the user — don't swallow API errors silently

### JavaScript (extension)

- No external dependencies — the extension is self-contained
- All async operations use `async/await`
- `chrome.storage.local` access goes through `SonarStorage` (don't call chrome APIs directly in business logic)

---

## Pull Requests

- One logical change per PR
- Include a short description of **what changed and why**
- Link any related issues
- Ensure tests pass before requesting review
- The PR description should answer: what problem does this solve? How did you verify it works?

---

## Project Structure Overview

```
sonar/
├── backend/         # FastAPI + Celery + PostgreSQL (see backend/README.md)
├── extension/       # Chrome MV3 extension (see extension/README.md)
├── frontend/        # React 18 + Vite dashboard (see frontend/README.md)
├── docker-compose.yml
├── .env.example
├── README.md
└── CONTRIBUTING.md
```

Each subdirectory has its own README with detailed documentation.
