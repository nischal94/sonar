# Security Policy

## Supported Versions

Sonar is pre-launch and has no production users yet. The `main` branch is the only "supported" version. Once we cut a `v1.0.0` release, this section will list specific supported versions.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, use GitHub's private vulnerability reporting feature:

→ [**Report a vulnerability**](https://github.com/nischal94/sonar/security/advisories/new)

Include:
- Clear reproduction steps
- Impact assessment (what does an attacker gain?)
- Affected component (backend, extension, frontend, infrastructure)
- Suggested fix if you have one

We aim to acknowledge reports within 48 hours and provide a remediation timeline within 7 days.

## In Scope

Sonar processes the following data, and vulnerabilities affecting any of it are in scope:

- **LinkedIn post content** — passively observed via the Chrome extension from the user's own logged-in feed
- **User-supplied capability profile** — text or URLs the user submits to define what they sell
- **LLM-generated outreach drafts** — AI-generated content delivered to users
- **JWT-protected workspace data** — multi-tenant SaaS with workspace-level isolation
- **Delivery channel credentials** — Slack webhooks, SendGrid keys, Twilio tokens, Telegram bot tokens (per workspace)

Specific vulnerability classes we want to know about:

- Authentication / authorization bypasses (JWT handling, workspace isolation, cross-tenant data leakage)
- SQL injection or ORM injection
- Command injection (LLM output reaching shell, file paths, or SQL)
- XSS in the React dashboard, alert content, or extension UI
- CSRF on state-changing endpoints
- Secrets exposure in logs, error messages, commit history, or API responses
- **Prompt injection** in LLM-facing endpoints (`/profile/extract`, alert context generation, future signal proposal wizard) — see [`CLAUDE.md`](CLAUDE.md) "AI-Native Code" section for the controls we already have in place
- Insecure direct object reference (IDOR) on alerts, workspaces, connections
- Server-side request forgery (SSRF) in the URL profile extractor
- Dependency vulnerabilities not yet caught by Dependabot

## Out of Scope

Please do not report:

- Self-XSS via the user's own browser DevTools
- Theoretical issues without a proof of concept
- Issues in third-party services (LinkedIn, OpenAI, Groq, SendGrid, Twilio) — report those upstream
- Dependency CVEs already opened as Dependabot PRs (handled separately)
- Missing security headers without demonstrated impact (we'll batch-fix these as part of the launch hardening checklist in [`CLAUDE.md`](CLAUDE.md))
- Lack of rate limiting on dev endpoints (rate limiting on `/auth/token` is tracked as a launch-blocker in `CLAUDE.md` Engineering Standards)
- Vulnerabilities requiring root access to the server, physical access to the user's machine, or stolen credentials

## Existing Security Controls

These are already in place and documented in [`CLAUDE.md`](CLAUDE.md) Engineering Standards → Security:

- **JWT handled by PyJWT** with explicit `algorithms=[...]` and `options={"require": ["exp", "sub"]}` (no `alg: none` accepted, no missing-claim bypass) — see PRs [#4](https://github.com/nischal94/sonar/pull/4) and [#15](https://github.com/nischal94/sonar/pull/15)
- **Parameterized SQL everywhere** — never f-string a query
- **Pydantic validation at every system boundary** — user input, webhook payloads, and (critically) **LLM output**
- **User-controlled input is never interpolated into LLM system prompts** — all user content goes in the user-message position only
- **`max_tokens` set on every LLM call** — no unbounded cost exposure from prompt-injection-driven loops
- **Foreign key constraints enforced at the database level**, not just the ORM, with explicit `ON DELETE` semantics — see migration 003 ([PR #19](https://github.com/nischal94/sonar/pull/19))
- **Secrets in `.env` (gitignored)** for dev; production secrets injected from a secrets manager at deploy time
- **Dependabot enabled** for backend (`pip`), frontend (`npm`), and `github-actions` ecosystems

## Required Before Launch (tracked in CLAUDE.md "Engineering Standards")

The following are documented as launch-blockers and not yet in place. They are NOT vulnerabilities to report — they are known gaps with a remediation plan:

- Rate limiting on `/auth/token` and any credential-checking endpoint
- CI gates: ruff + mypy + pytest + coverage on every PR
- Structured logging via `structlog` with request-ID correlation
- Error tracking (Sentry) for unhandled exceptions in production
- Health check split (liveness vs readiness)
- Database backups with documented restore drill
- LLM cost metrics per workspace + hard daily caps
- PII / GDPR retention policy + data export and deletion endpoints
- Eval datasets + CI gates for every prompt-dependent feature

## Hall of Fame

We'll list responsible disclosures here once Sonar is in production.
