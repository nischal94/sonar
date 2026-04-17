# Sonar Phase 2 Wizard — Implementation Decisions

**Date:** 2026-04-17
**Status:** Decisions locked, ready for implementation-plan generation
**Slice:** Phase 2 — Wizard (Signal Configuration)
**Builds on:** Phase 2 Foundation (`signals` table, Ring 1/2 matchers, pipeline refactor — shipped)
**Design spec:** `docs/phase-2/design.md` Section 4.1 (approved 2026-04-11)

This document captures the implementation-level decisions made during the 2026-04-17 brainstorming session, on top of the approved Phase 2 design spec. It is a companion to `docs/phase-2/design.md`, not a replacement. `writing-plans` should treat both as input when generating the task-level `docs/phase-2/implementation-wizard.md`.

---

## 1. Scope (Option B — wizard-only)

**In scope:**

- Signal Configuration Wizard at `/signals/setup` — the 5-step flow from design.md §4.1
- Two backend endpoints:
  - `POST /workspace/signals/propose` — LLM call, no DB write
  - `POST /workspace/signals/confirm` — computes embeddings, persists rows, marks profile active
- LLM-powered signal generation from free-form "what you sell" + optional ICP
- Embedding generation + persistence for confirmed signals
- Wizard completion marks the workspace's capability profile active

**Out of scope (deferred to a follow-up "Signal Management" slice):**

- `/signals` ongoing management page
- `GET /workspace/signals`
- `PATCH /workspace/signals/{signal_id}`
- `DELETE /workspace/signals/{signal_id}`
- `POST /workspace/signals/from-discovery` (depends on Ring 3)

**Rationale:** ship the onboarding hypothesis-tester first. The critical product question is *can the LLM generate useful signals from a user's 'what you sell' description?* Watching real users complete the wizard and use the resulting signals validates that. Any CRUD UI built for editing bad signals would have been work on the wrong problem.

---

## 2. LLM Model (Option A1 — bump project standard)

**Decision:** upgrade Sonar's "expensive tier" from `gpt-4o-mini` to `gpt-5.4-mini` across the project.

**Cost:** ~$0.007 per wizard invocation (500 input tokens + 1500 output at `gpt-5.4-mini` pricing). Negligible for a one-time-per-user flow.

**Why `gpt-5.4-mini` specifically:**

- OpenAI's own guidance (fetched via Context7 2026-04-17): *"For complex reasoning and coding tasks, gpt-5.4 is recommended. For optimizing latency and cost, consider smaller variants like gpt-5.4-mini or gpt-5.4-nano."*
- Signal proposal is structured-JSON generation with light creativity, not complex reasoning — mini-class is the right fit
- Nano is too small for nuanced semantic tasks (turning "I sell fractional CTO services" into 10 distinct buying signals)
- Full `gpt-5.4` reserved for tasks that actually need it (e.g., future outreach-draft quality tuning)

**Migration scope (part of this plan, not a separate PR):**

- `app/config.py`: new constant `OPENAI_MODEL_EXPENSIVE = "gpt-5.4-mini"`
- `app/services/llm.py`: default to the new constant
- `app/workers/context_generator.py`: migrate from hardcoded `gpt-4o-mini` to the new constant
- Wizard's propose-signals call uses the same constant
- `sonar/CLAUDE.md`: LLM-routing section updated to reference `gpt-5.4-mini`

**Single routing layer preserved.** No per-endpoint model overrides.

---

## 3. Quality Validation (Option D — hybrid, infrastructure for scale)

Neither pure offline evals (synthetic golden datasets with LLM-as-judge) nor pure online telemetry alone is right for a world-class long-horizon system. Pure offline encodes one human's taste at one moment and goes stale. Pure online lets regressions hit users before detection. The architecture that scales runs both, with production data flowing back into the offline eval set.

### In this Wizard plan

#### 3a. Telemetry (load-bearing; must ship day one)

New table `signal_proposal_events`:

```sql
id               UUID PK
workspace_id     UUID FK → workspaces.id
prompt_version   TEXT                      -- e.g. "v1"
what_you_sell    TEXT                      -- user input
icp              TEXT                      -- user input, nullable
proposed         JSONB                     -- full LLM output, all 8-10 signals
accepted_ids     TEXT[]                    -- indices of proposed that the user accepted as-is
edited_pairs     JSONB                     -- [{proposed_idx, final_phrase}] — proposed-vs-final diff
rejected_ids     TEXT[]                    -- indices of proposed that the user rejected
user_added       JSONB                     -- signals the user added manually after proposals
created_at       TIMESTAMPTZ
completed_at     TIMESTAMPTZ NULL          -- when the user hit Save on step 5

INDEX ON (workspace_id, created_at DESC)
INDEX ON (prompt_version, completed_at DESC)  -- for later v1 vs v2 comparisons
```

Emission points:

- `/propose` writes the partial event (proposed payload + inputs)
- `/confirm` updates the same row with acceptance breakdown + `completed_at`

**Why this is non-negotiable:** telemetry is the seed data for every future eval effort. It cannot be retroactively instrumented — users who onboard before this table exists are lost forever. Ship day one or never.

#### 3b. Structural pre-ship validation (cheap CI gate)

`backend/tests/test_propose_signals_shape.py`:

- Runs the prompt against 3 sanity-check inputs (e.g., SaaS, agency, e-commerce)
- Assertions on **shape, not semantic quality**:
  - Response parses as valid JSON
  - `signals` array has length 8-10
  - Each signal has `phrase` (non-empty string), `example_post` (non-empty string), `intent_strength` (float in [0, 1])
  - No duplicate phrases within a response
- Hits the real OpenAI API (with test API key), not mocked
- Runs on every PR that touches the prompt module or the propose endpoint
- **Does NOT judge semantic quality.** Catches regression failures (malformed output, dropped fields, model-swap breakage) without pretending to encode "correct" signals.

#### 3c. Prompt versioning

- Prompt lives in `app/prompts/propose_signals.py` (new module — first entry under `app/prompts/`, matching `sonar/CLAUDE.md` "Prompts are code" rule)
- Module exports `PROMPT_VERSION: str = "v1"`, the system-prompt template, the user-message template, and the expected JSON schema
- Every call to `/propose` logs `prompt_version` alongside the event
- Enables later comparison of v1 vs v2 acceptance rates from production telemetry without any schema migration

### Deferred to a later plan (triggered when production data exists, approximately 100+ completed wizards)

- Offline eval set sourced from `signal_proposal_events` — real user inputs as prompts, real accepted/edited signals as ground truth
- LLM-as-judge scoring against production-derived dataset
- A/B routing rail (`prompt_version` already logged — just need routing logic)

---

## 4. Implementation Assumptions (routine choices made in brainstorming)

- **Frontend UX pattern:** single-page `<SignalConfig>` component with step-state machine, not multi-step routes. Simpler, matches Sonar's existing page-level React patterns.
- **Implementation order:** backend-first. Endpoints + tests land and are callable via curl before the frontend wires to them. Matches how Foundation shipped.
- **New direct deps beyond slowapi (already in from PR #61):** none anticipated. Existing OpenAI SDK, existing embedding provider, existing ORM patterns.
- **Rate limit on `/propose`:** TBD during implementation (initial guess: 3/minute per IP, tunable based on OpenAI response latency).

---

## 5. Task Outline (~12 tasks, subject to refinement by `writing-plans`)

1. Alembic migration 003 — create `signal_proposal_events` table
2. ORM model `SignalProposalEvent` in `app/models/` + model unit test
3. New prompt module `app/prompts/propose_signals.py` with `PROMPT_VERSION = "v1"`, system/user templates, expected JSON schema
4. Migrate `app/services/llm.py` + `app/workers/context_generator.py` from hardcoded `gpt-4o-mini` to `OPENAI_MODEL_EXPENSIVE` constant; update any existing tests that assert model name
5. `POST /workspace/signals/propose` endpoint — calls LLM, emits partial telemetry event, returns proposed signals (no persistence)
6. `POST /workspace/signals/confirm` endpoint — accepts final signal list, computes embeddings, persists `Signal` rows, completes telemetry event, marks profile active
7. Structural CI test `test_propose_signals_shape.py` — prompt runs against 3 sanity inputs, asserts shape (not quality)
8. Integration test for the wizard flow: register workspace → propose → confirm → assert `Signal` rows persisted + `SignalProposalEvent` row logged with correct breakdown
9. Rate-limit `/propose` via slowapi (reuse the `limiter` from PR #61)
10. Frontend `SignalConfig.tsx` — single-page component with 5-step state machine, Tailwind styled
11. Frontend routing: add `/signals/setup` route to `App.tsx`; update `Onboarding.tsx` to redirect there on first login
12. Update `sonar/CLAUDE.md` — LLM routing rule to `gpt-5.4-mini`, add `app/prompts/` convention note, bump prompt-versioning rule

---

## 6. Success Criteria

1. A new user signs up → is redirected to `/signals/setup` → completes all 5 steps in under 90 seconds median
2. LLM produces 8-10 structurally-valid signal candidates on every invocation (verified by the structural CI test)
3. Telemetry event written to `signal_proposal_events` with full proposed / accepted / edited / rejected / user_added breakdown
4. On confirm, new rows appear in `signals` table with embeddings populated
5. Capability profile marked active so the Phase 2 pipeline's Ring 1 + Ring 2 matchers can find them
6. All existing 55 tests still pass; new tests are deterministic (mock LLM in unit tests, real LLM only in the structural CI test with fixed inputs)
7. `prompt_version` logged on every call — no architectural change needed to begin comparing v1 → v2 once real data exists

---

## 7. Open Questions (to resolve during implementation, not blocking plan generation)

- Rate-limit value for `/propose` (3/min? 5/min?) — tune based on observed OpenAI response latency
- Whether `SignalProposalEvent.edited_pairs` is computed frontend-side (cleaner) or backend-side (more robust to client bugs)
- Exact JSON schema shape for OpenAI Structured Outputs — `strict: true` vs non-strict, impact on refusal behavior
- Error-handling UX when the LLM call fails (retry button? graceful error message? fallback to manual signal entry?)
- Whether the structural CI test should run on every PR or only on PRs touching the prompt / endpoint (cost-benefit TBD)
