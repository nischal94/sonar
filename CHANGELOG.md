# Changelog

All notable changes to Sonar are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [0.5.0](https://github.com/nischal94/sonar/compare/v0.4.0...v0.5.0) (2026-04-18)


### Added

* **dashboard:** Phase 2 Dashboard — Ranked People List MVP (Tasks 1-11) ([#73](https://github.com/nischal94/sonar/issues/73)) ([80491b2](https://github.com/nischal94/sonar/commit/80491b208f5fc4d82f3e7808fc9a92072f193ea6))


### Documentation

* **phase-2:** dashboard implementation decisions (brainstorm output) ([79005b3](https://github.com/nischal94/sonar/commit/79005b3ae9b90dd437516c8d5ee3acc3844f6e8e))
* **phase-2:** dashboard implementation plan (11 tasks) ([1cdc8db](https://github.com/nischal94/sonar/commit/1cdc8db260f400fb10cf5c2f395e1aaff888b218))

## [0.4.0](https://github.com/nischal94/sonar/compare/v0.3.0...v0.4.0) (2026-04-17)


### Added

* **wizard:** frontend — Tasks 10-12 of Phase 2 Wizard plan ([#70](https://github.com/nischal94/sonar/issues/70)) ([ce0f958](https://github.com/nischal94/sonar/commit/ce0f9582692781c8e2ce6513c4697825d468a706))

## [0.3.0](https://github.com/nischal94/sonar/compare/v0.2.4...v0.3.0) (2026-04-17)


### Added

* **auth:** rate limit /auth/token to 5/min per IP ([#61](https://github.com/nischal94/sonar/issues/61)) ([71a868e](https://github.com/nischal94/sonar/commit/71a868efa8635ac68ce6c59ad245f4d52b77dd8b))
* **auth:** rate limit /workspace/register to 3/min per IP ([#67](https://github.com/nischal94/sonar/issues/67)) ([735ca5b](https://github.com/nischal94/sonar/commit/735ca5bb24417a679e08a7418e67f1ad7b864b32))
* **infra+wizard:** testing ladder + Wizard Task 1 (LLM tier bump) ([#64](https://github.com/nischal94/sonar/issues/64)) ([fd79644](https://github.com/nischal94/sonar/commit/fd796449ebc04840aae17572f072e1d5823c63cb))
* **wizard:** backend — Tasks 2-9 of Phase 2 Wizard plan ([#68](https://github.com/nischal94/sonar/issues/68)) ([a9ef017](https://github.com/nischal94/sonar/commit/a9ef01763897192e7ee8fee0599f96fcd536cf58))


### Documentation

* **phase-2:** wizard implementation decisions (brainstorm output) ([6a67e91](https://github.com/nischal94/sonar/commit/6a67e91dd507ebe2b33bfd28f5e27cb9befe1ed5))
* **phase-2:** wizard implementation plan (12 tasks) ([faee435](https://github.com/nischal94/sonar/commit/faee4355d14f32a15af73640e37a3f2fa3ee607d))
* **todo:** session-3 continued — rate limit shipped, Priority 8 done ([0d564a1](https://github.com/nischal94/sonar/commit/0d564a17e0115493639d4cb0d5509d840cc355d4))
* **todo:** session-3 sync — 9 PRs merged, v0.2.4 shipped, fix stale path ([3c559af](https://github.com/nischal94/sonar/commit/3c559afb6a5b38b9cb44dca6ff1c3f95adc65f74))
* **todo:** surface pre-launch gaps in Resume Here block ([2cbe830](https://github.com/nischal94/sonar/commit/2cbe83007e4cf2627d9c9e1626dcc75759f7fd9e))

## [0.2.4](https://github.com/nischal94/sonar/compare/v0.2.3...v0.2.4) (2026-04-17)


### Documentation

* **todo:** final session-2 sync — v0.2.3 shipped, Node 24 action bumps landed ([4b435ac](https://github.com/nischal94/sonar/commit/4b435ac30eabfbe7116d2c6680161c1624329f05))


### Chores

* **deps-dev:** bump typescript 5.9.3 → 6.0.2 in /frontend ([#55](https://github.com/nischal94/sonar/issues/55)) ([ade26a6](https://github.com/nischal94/sonar/commit/ade26a6fb8b4c64664262f028b2bc03b52afee48))
* **deps:** bump follow-redirects 1.15.11 → 1.16.0 in /frontend ([#58](https://github.com/nischal94/sonar/issues/58)) ([4ce2202](https://github.com/nischal94/sonar/commit/4ce2202c53709a52c9f29bfc140d1f6b81d12182))
* **deps:** bump mako 1.3.10 → 1.3.11 ([#59](https://github.com/nischal94/sonar/issues/59)) ([f8b47c7](https://github.com/nischal94/sonar/commit/f8b47c76f31ddb741da3c442e91073b1d26e9c46))
* **deps:** email-validator floor &gt;=2.2.0 → &gt;=2.3.0 (codify lock) ([#54](https://github.com/nischal94/sonar/issues/54)) ([d12891d](https://github.com/nischal94/sonar/commit/d12891d454099cf773aceb628e36081a7f36aa4e))
* **deps:** openai floor ^1.40 → ^2.31 (codify already-resolved lock) ([#57](https://github.com/nischal94/sonar/issues/57)) ([f43e3ac](https://github.com/nischal94/sonar/commit/f43e3ac8b147e1ac87ef9872b323fd5598cede60))
* **deps:** python-multipart floor &gt;=0.0.9 → &gt;=0.0.26 (codify lock) ([#52](https://github.com/nischal94/sonar/issues/52)) ([00af92b](https://github.com/nischal94/sonar/commit/00af92bc152565affe44b7cc0d7ec20d9c8c0561))
* **deps:** python-telegram-bot floor &gt;=21.5 → &gt;=22.7 (codify lock) ([#53](https://github.com/nischal94/sonar/issues/53)) ([3eddd09](https://github.com/nischal94/sonar/commit/3eddd0990a5ace0ddec8fc60cba07c7e7ce22dec))
* **deps:** twilio floor &gt;=9.3.0 → &gt;=9.10.4 (codify lock) ([#56](https://github.com/nischal94/sonar/issues/56)) ([8555ecc](https://github.com/nischal94/sonar/commit/8555ecc087a7881be5bfebc0792f3ccb28cb91d4))

## [0.2.3](https://github.com/nischal94/sonar/compare/v0.2.2...v0.2.3) (2026-04-13)


### Documentation

* **todo:** end-of-session-2 sync — Priority 2 complete, v0.2.2 shipped ([00db5ed](https://github.com/nischal94/sonar/commit/00db5ed1a66af8e447aa2f8545382877676f5f40))


### CI/CD

* bump all workflow actions to Node-24-compatible majors ([#50](https://github.com/nischal94/sonar/issues/50)) ([4d54da0](https://github.com/nischal94/sonar/commit/4d54da059fc28acd527bc6573d4d5f418cc90730))

## [0.2.2](https://github.com/nischal94/sonar/compare/v0.2.1...v0.2.2) (2026-04-13)


### Chores

* **deps:** pin pgvector to 0.4.x (already running 0.4.2) ([#48](https://github.com/nischal94/sonar/issues/48)) ([3cddee0](https://github.com/nischal94/sonar/commit/3cddee0d4c8eee6ba719a439aa63ee9655577ecf))
* **release:** strip emojis, attach SBOM/extension zip, add trust footer ([#46](https://github.com/nischal94/sonar/issues/46)) ([0863b80](https://github.com/nischal94/sonar/commit/0863b80336986e4ee49007a9ec71033a3f8e515e))

## [0.2.1](https://github.com/nischal94/sonar/compare/v0.2.0...v0.2.1) (2026-04-13)


### 🐛 Fixed

* **ci:** unblock alembic + frontend CI on GitHub Actions ([#45](https://github.com/nischal94/sonar/issues/45)) ([086d757](https://github.com/nischal94/sonar/commit/086d7578b307b8eddd8f3ecfc3eb9afdb375b576))


### 📚 Documentation

* **todo:** mark redis 7 bump blocked upstream; reorder numpy/pgvector ([c522c00](https://github.com/nischal94/sonar/commit/c522c009b3853940358244620f6cd6bcaafac693))
* **todo:** sync state to 2026-04-13 ([a9b5e4b](https://github.com/nischal94/sonar/commit/a9b5e4b0f76ed4f64f81506d62347fe379ad9aee))


### 🔧 CI/CD

* add CI workflow, CodeQL, PR title lint, CODEOWNERS, pre-commit config ([d4f7837](https://github.com/nischal94/sonar/commit/d4f7837d9735a4e3a70f1658220dec3f50213a7f))


### 🔧 Chores

* **deps:** pin numpy to 2.x major (already running 2.4.4) ([#44](https://github.com/nischal94/sonar/issues/44)) ([2401fd6](https://github.com/nischal94/sonar/commit/2401fd6b7410c9da0051d4d747095fb97e9d98b7))

## [0.2.0](https://github.com/nischal94/sonar/compare/v0.1.0...v0.2.0) (2026-04-11)


### 🚀 Added

* add 3-dimension scoring engine with priority bucketing ([2313f8c](https://github.com/nischal94/sonar/commit/2313f8cda2bae411b48436054984f83e94bb7a98))
* add alerts API with feedback endpoint and threshold adjustment ([3ac74f8](https://github.com/nischal94/sonar/commit/3ac74f887e2ed8bf8a1fbb289942db174af150db))
* add Apify public post poller and email digest sender ([1c6c448](https://github.com/nischal94/sonar/commit/1c6c448a5e438e75f46e484224e387d5732b8cd3))
* add capability profile extraction with LLM and embedding storage ([9c44b99](https://github.com/nischal94/sonar/commit/9c44b995a4a591d8488319e730b384e7000ecaab))
* add Celery pipeline and ingest API endpoint ([7e80494](https://github.com/nischal94/sonar/commit/7e80494be78aeb7354e6c42df3d25097abf3e6b4))
* add Chrome extension with LinkedIn feed sync and popup UI ([4543d86](https://github.com/nischal94/sonar/commit/4543d86a37b0c5c47159bfb3c4b178de520c96fd))
* add database models and initial Alembic migration ([9aa295d](https://github.com/nischal94/sonar/commit/9aa295d0410a449f204192a222f927ba6d172cd3))
* add delivery router with Slack, email, Telegram, and WhatsApp channels ([7030b41](https://github.com/nischal94/sonar/commit/7030b41318414b16435086ecb6af898fd86087a0))
* add JWT auth with workspace registration and login ([b18c4eb](https://github.com/nischal94/sonar/commit/b18c4ebc85b65e06b72f622f5cc29734e505aca6))
* add keyword pre-filter and semantic similarity matcher ([138e021](https://github.com/nischal94/sonar/commit/138e021049986b909ea4905da1c0d3ef10b578cb))
* add LLM context generator with model routing by priority ([38b9afb](https://github.com/nischal94/sonar/commit/38b9afbe3e5f2e9839b119da7730e3eea87912ff))
* add React dashboard with alert feed, opportunity board, and settings ([329eec2](https://github.com/nischal94/sonar/commit/329eec2fefafe58a85a0503a437989912bb45a47))
* complete Sonar Phase 1 MVP — full stack end-to-end ([6efe1b0](https://github.com/nischal94/sonar/commit/6efe1b041fcf2ddd98722ec7551a2333d9e416fd))
* initial Sonar project — spec and implementation plan ([be01318](https://github.com/nischal94/sonar/commit/be013188571abd72ff0e270babc9218eea84498b))
* Phase 2 Foundation — data model, Ring 1/2 matching, pipeline refactor ([#10](https://github.com/nischal94/sonar/issues/10)) ([f62d6cb](https://github.com/nischal94/sonar/commit/f62d6cbc14a2d9a414e73a7fc79392db8ab6315b))
* scaffold project with Docker Compose and FastAPI ([5621de0](https://github.com/nischal94/sonar/commit/5621de0c76c9f0a50541e3b7dae981c80d0f9369))


### 🐛 Fixed

* add postgres healthcheck and use lru_cache settings pattern ([20a6f68](https://github.com/nischal94/sonar/commit/20a6f689f0b2ea684ed8cfd9765add6ea34618c1))
* **auth:** require explicit exp/sub claims in jwt.decode ([#15](https://github.com/nischal94/sonar/issues/15)) ([bf709c4](https://github.com/nischal94/sonar/commit/bf709c446a3845f4d205671650904463f70402cb)), closes [#7](https://github.com/nischal94/sonar/issues/7)
* bump axios to 1.15.0 to patch CVE-2026-40175 and CVE-2025-62718 ([b4cd498](https://github.com/nischal94/sonar/commit/b4cd498ea34c8e9c30d5e03bc589158749966e13))
* bump vite to 6.4.2 to patch path traversal vulnerability (CVE moderate) ([182c9ed](https://github.com/nischal94/sonar/commit/182c9ed66c0ffd4aaccb430e8f956e54b4a5ea26))
* **db:** add missing FK on connections.user_id ([#19](https://github.com/nischal94/sonar/issues/19)) ([5f2b367](https://github.com/nischal94/sonar/commit/5f2b3673bbe0208323cfbf1deaf06c2b41c7f41f))
* **delivery:** log asyncio.gather failures in DeliveryRouter.deliver ([#24](https://github.com/nischal94/sonar/issues/24)) ([560e282](https://github.com/nischal94/sonar/commit/560e2822e79249b2c789085e1d2618e6fdc63dbf))
* **deps:** pin bcrypt&lt;4.1 to work around passlib incompatibility ([#12](https://github.com/nischal94/sonar/issues/12)) ([34d2add](https://github.com/nischal94/sonar/commit/34d2adda2c0dd9aeeb4f8cb629e51753a7091caa)), closes [#5](https://github.com/nischal94/sonar/issues/5)
* make Phase 1 dev environment actually runnable ([5e190f9](https://github.com/nischal94/sonar/commit/5e190f95345e6aabd447e1642c373437fe997cf8))
* migrate JWT from python-jose to PyJWT to drop ecdsa timing attack dep ([#4](https://github.com/nischal94/sonar/issues/4)) ([935e330](https://github.com/nischal94/sonar/commit/935e3307a56f023331fb777d91813b915ab18fe3))
* **models:** add ForeignKey constraints to Connection.workspace_id and user_id ([#13](https://github.com/nischal94/sonar/issues/13)) ([207b207](https://github.com/nischal94/sonar/commit/207b207b5a8533e763e20ab96119aeb1ee6b56b2)), closes [#8](https://github.com/nischal94/sonar/issues/8)
* regenerate frontend lockfile to resolve axios CVEs ([1959c2b](https://github.com/nischal94/sonar/commit/1959c2bcc473459f1d41fc2c8a53225e2378d12e))
* resolve all Phase 1 blockers and critical bugs from code review ([2075568](https://github.com/nischal94/sonar/commit/2075568e33f78226b764bf22824c8c5b5e2d9f74))
* **tests:** patch CHANNEL_SENDERS dict for Slack router tests ([#16](https://github.com/nischal94/sonar/issues/16)) ([398c3db](https://github.com/nischal94/sonar/commit/398c3db74b5a7cb5799da8778f9af008d8e0f497)), closes [#6](https://github.com/nischal94/sonar/issues/6)
* **tests:** patch embedding_provider where it is looked up in profile router ([#20](https://github.com/nischal94/sonar/issues/20)) ([1da10a9](https://github.com/nischal94/sonar/commit/1da10a9f363dc617be6d353c25c63f1df58d376c)), closes [#11](https://github.com/nischal94/sonar/issues/11)


### 🧹 Changed

* **delivery:** constructor-inject sender registry into DeliveryRouter ([#23](https://github.com/nischal94/sonar/issues/23)) ([79af5bb](https://github.com/nischal94/sonar/commit/79af5bb48885aaf049a83aa641851c82e90b020d))


### 📚 Documentation

* add comprehensive project documentation ([e9f512c](https://github.com/nischal94/sonar/commit/e9f512c6540204f0ff9ab8d03e95bbd3d2afb479))
* add Phase 2 network intelligence design spec ([fda9a25](https://github.com/nischal94/sonar/commit/fda9a2551a0ce125c96cc46646d3fbbcd81aa5f8))
* **changelog:** backfill PRs [#10](https://github.com/nischal94/sonar/issues/10), [#12](https://github.com/nischal94/sonar/issues/12)-[#24](https://github.com/nischal94/sonar/issues/24) under [Unreleased] ([#26](https://github.com/nischal94/sonar/issues/26)) ([334904b](https://github.com/nischal94/sonar/commit/334904b1cb28fd259a54d7d606ba01546098b687))
* **claude.md:** add Engineering Standards section + link known bugs to issues ([1b2d350](https://github.com/nischal94/sonar/commit/1b2d3503cd998d734f3ccf157549fa356c3702d2))
* **claude.md:** add Lessons Learned — Python DI, asyncio.gather, frontend deps ([ab91c1f](https://github.com/nischal94/sonar/commit/ab91c1f5bbaac62c2d4365fa6ca75f112da87a21))
* **phase-2/foundation:** add FK constraints on person_signal_summary.recent_post_id and recent_signal_id per design spec ([7ea63dc](https://github.com/nischal94/sonar/commit/7ea63dcc1cc863a04f765356dd70cc9a917592ae))
* **phase-2/foundation:** switch shell commands to docker compose exec ([0c012ce](https://github.com/nischal94/sonar/commit/0c012ced45bab924b7e7e2ffb0de0ed035f55e93))
* **phase-2:** Foundation implementation plan ([#3](https://github.com/nischal94/sonar/issues/3)) ([385eade](https://github.com/nischal94/sonar/commit/385eade9b30676b83eaeed8129972578332b3f0e))
* polish README with badges, why section, correct URLs, and self-hosting note ([fbf715b](https://github.com/nischal94/sonar/commit/fbf715b4527830a420a0ba3a90b12ff1fb9281b5))
* rebuild CLAUDE.md comprehensively + add CHANGELOG ([1a2ae5d](https://github.com/nischal94/sonar/commit/1a2ae5d2480219a16abb83393ccd4ef438e5b5b4))
* refresh README + add SECURITY.md (full audit fixes) ([f261842](https://github.com/nischal94/sonar/commit/f2618420b6a4cd223d7025becd525e35371ec6a0))
* rename Phase 2 plans to implementation-&lt;feature&gt;.md for nomenclature consistency with Phase 1 ([27ddf06](https://github.com/nischal94/sonar/commit/27ddf063e4603786f7503c2ac86bbfbd9c44f048))
* restore archived Sonar product design and Phase 1 plan ([29f4751](https://github.com/nischal94/sonar/commit/29f47514a081881ad243a428d62e9f447d73ab7e))
* **todo:** rewrite as comprehensive session-handoff doc ([4ef0fa1](https://github.com/nischal94/sonar/commit/4ef0fa1cbf80a9edddfca87aeb8adf7e33f0dd61))


### 🧪 Tests

* add end-to-end integration test for full pipeline ([36531e1](https://github.com/nischal94/sonar/commit/36531e18286d850746f297e212c8cfa729c78aef))


### 🔧 CI/CD

* replace release-drafter with release-please for in-repo CHANGELOG automation ([96b2338](https://github.com/nischal94/sonar/commit/96b2338d2c6d16e6d28049f8f93569eb1c59e4e1))


### 🔧 Chores

* add .gitignore with .worktrees exclusion ([8d8332c](https://github.com/nischal94/sonar/commit/8d8332c7f32e2c99438d6e9b9de93dc4ccc14e54))
* add CLAUDE.md and flatten docs structure ([80006ca](https://github.com/nischal94/sonar/commit/80006cab212e6584f472d3cf17c116f2742e9400))
* add MIT license file ([a4c49a7](https://github.com/nischal94/sonar/commit/a4c49a793d57711989f04f77ae9fe80011636296))
* add package-lock.json with vite 6.4.2 resolved ([22ce318](https://github.com/nischal94/sonar/commit/22ce31895c5dbcd9b7ec940600b9062881bc71dd))
* add TODO.md with env setup checklist ([6fcee4f](https://github.com/nischal94/sonar/commit/6fcee4f7580b3b3088b4b09243d77a04d0634eae))
* **ci:** scaffold .github — release-drafter, PR/issue templates, dependabot ([#27](https://github.com/nischal94/sonar/issues/27)) ([e1dd79f](https://github.com/nischal94/sonar/commit/e1dd79f4cc286392e29276a9686e11b639d6e102))
* clear follow-up issues [#21](https://github.com/nischal94/sonar/issues/21), [#22](https://github.com/nischal94/sonar/issues/22), [#25](https://github.com/nischal94/sonar/issues/25) ([#39](https://github.com/nischal94/sonar/issues/39)) ([b9b26c8](https://github.com/nischal94/sonar/commit/b9b26c8f5a398967eaca2386b141448918dc4216))
* **deps:** sync uv.lock with pyjwt/pydantic-settings lower-bound bumps (PRs [#31](https://github.com/nischal94/sonar/issues/31), [#32](https://github.com/nischal94/sonar/issues/32)) ([12af60d](https://github.com/nischal94/sonar/commit/12af60d13459027e9cd2099fde6fdb7b77b36989))
* exclude internal docs from public repo ([58526ab](https://github.com/nischal94/sonar/commit/58526ab342fbb7f0025dff3315cf54fe1b5d8fb2))
* gitignore .superpowers/ brainstorming session directory ([5122e39](https://github.com/nischal94/sonar/commit/5122e393f4b04bf75378f1dd35ded353f3e3b436))

## [Unreleased]

### Added
- `CHANGELOG.md` — running log of notable changes across the project
- `CLAUDE.md` — comprehensive project instructions for AI agents, rebuilt to reflect actual project state
- `docs/phase-2/design.md` — Phase 2 Network Intelligence design spec (Signal Configuration Wizard, Day-One Backfill, Network Intelligence Dashboard, Three-Ring Trending Topics, Weekly Digest Email)
- `docs/phase-2/implementation-foundation.md` — Phase 2 Foundation implementation plan (14 tasks, TDD-structured)
- `docs/phase-1/design.md` — Original Phase 1 product design (restored from deleted history)
- `docs/phase-1/implementation.md` — Original Phase 1 implementation plan (restored from deleted history)
- Minimal branch protection on `main` — blocks force-pushes and branch deletion, but does NOT require PRs for small changes (direct pushes still allowed)
- Dependabot alerts monitoring via `gh api repos/nischal94/sonar/dependabot/alerts`
- **Phase 2 Foundation (PR #10):** data model, matchers, and pipeline refactor. Adds Alembic migration 002 with new tables `signals` (pgvector + HNSW index), `person_signal_summary`, `company_signal_summary`, `trends`; JSONB columns on `posts` (`ring1_matches`, `ring2_matches`, `themes`, `engagement_counts`); `connections.mutual_count`; `workspaces.backfill_used`. Four new ORM models mirroring the migration. Two new services: `app/services/ring1_matcher.py` (pure-function keyword matching) and `app/services/ring2_matcher.py` (pgvector cosine-similarity query with configurable cutoff). `AlertContext` dataclass gains `themes: list[str]`. `scorer.compute_combined_score` gains `keyword_match_strength: float = 0.0` boosting relevance by up to +0.15. One-shot `scripts/backfill_signals_from_keywords.py` migrates existing `signal_keywords` arrays into the new `signals` table. 24 new tests across 5 files.
- **Regression test (PR #24):** `test_router_logs_channel_failure_and_continues_siblings` pins three guarantees — failing channels don't cancel siblings, failures log once with correlated context (channel, alert id, workspace id), `exc_info=result` kwarg preserved so stack traces aren't silently dropped.
- **Provider DI via FastAPI `Depends()` (closes #21):** `get_embedding_provider()` and `get_llm_client()` factories in `app/services/embedding.py` and `app/services/llm.py`. `app/routers/profile.py` uses `Depends(get_embedding_provider)` and `Depends(get_llm_client)`; `extract_capability_profile` accepts an optional `llm_override` parameter. Tests now swap providers via `app.dependency_overrides`, which sits above Python's import binding and cannot be defeated by `from ... import ...`. `test_e2e.py` migrated from `patch()` to `dependency_overrides`. Also lands `Sender` + `SenderFactory` Protocols in `app/delivery/router.py` so `DeliveryRouter(senders=...)`'s type hint documents the real contract instead of the loose `dict[str, type]`.
- **Autouse provider-singleton reset fixture (closes #22):** `conftest.py::_reset_provider_singletons` clears `embedding._provider`, `llm._openai`, `llm._groq` after each test so a real client accidentally populated by one test cannot leak into another. Four lines of cross-test state hygiene.
- **`DeliveryRouter` re-raises `CancelledError` (closes #25):** `gather` results loop now checks `isinstance(result, asyncio.CancelledError)` before the `Exception` branch and re-raises. `CancelledError` inherits from `BaseException` so the existing `Exception` check was already skipping it — but swallowing cancellation violates structured concurrency. New regression test `test_router_propagates_cancellation` asserts `CancelledError` propagates out of `deliver()`.
- **`.github/` project infrastructure:** first `.github/` scaffold for the repo.
  - `.github/workflows/release-drafter.yml` + `.github/release-drafter.yml` — release-drafter v6 runs on every push to `main` and every PR event. An autolabeler parses Conventional Commits prefixes in PR titles (`feat`, `fix`, `refactor`, `docs`, `chore`, `security`, …) and tags PRs automatically. A GitHub Release draft is continuously updated with merged PRs grouped into Keep-a-Changelog categories (Added / Changed / Fixed / Security / Docs / Tests / Chores). Releases are *drafted*, never auto-published.
  - `.github/pull_request_template.md` — summary/changes/test-plan/checklist layout, including an explicit reminder to update `CHANGELOG.md` under `[Unreleased]` and to run `superpowers:code-reviewer` for security-sensitive PRs.
  - `.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md` + `config.yml` — structured issue templates; blank issues disabled.
  - `.github/dependabot.yml` — weekly updates for backend (`pip` ecosystem against `/backend/pyproject.toml`) and frontend (`npm` against `/frontend`), plus monthly updates for `github-actions`. Labels `dependencies` + ecosystem tag, commit prefix `chore(deps)` / `chore(ci)`.

### Fixed
- `backend/Dockerfile` — created (did not exist, was blocking `docker compose up --build`)
- `backend/alembic.ini` — fixed DB hostname from `localhost` to `postgres` (service name) so alembic works inside the `api` container
- `backend/alembic/versions/001_initial_schema.py` — replaced non-existent `postgresql.TIMESTAMPTZ()` with `postgresql.TIMESTAMP(timezone=True)` in 18 places
- `backend/app/models/_types.py` — new type shim providing a `TIMESTAMPTZ` subclass of `TIMESTAMP(timezone=True)` so existing `Column(TIMESTAMPTZ)` usage sites keep working
- `backend/app/models/{alert,connection,feedback,outreach,post,user,workspace}.py` — import `TIMESTAMPTZ` from the new `_types` shim instead of the non-existent `sqlalchemy.dialects.postgresql.TIMESTAMPTZ`
- `backend/pyproject.toml` — added `pydantic[email]`, `email-validator`, and `python-multipart` (required for `EmailStr` schemas and FastAPI form-data parsing, respectively)
- `backend/uv.lock` — tracked lockfile for reproducible builds (previously untracked, hiding Phase 1 deps)
- `frontend/package-lock.json` — regenerated to resolve axios CVE-2026-40175 and CVE-2025-62718 (Dependabot alerts #2 and #3)
- **Security (PR #4):** migrated JWT handling from `python-jose` to `PyJWT` to drop transitively-included `ecdsa` (Dependabot alert #4 — Minerva timing attack on P-256, no upstream fix available). Exception handling equivalence: `jose.JWTError` → `jwt.PyJWTError`. Tokens remain wire-compatible (HS256 + identical claim layout). Manually verified via round-trip testing; reviewer approved for security-sensitive correctness.
- **`bcrypt<4.1` pin (PR #12, closes #5):** `passlib` 1.7.4 references `bcrypt.__about__`, which was removed in bcrypt 4.1+, causing three Phase 1 tests to fail at import time. Pinned `bcrypt<4.1` in `pyproject.toml` and regenerated `uv.lock`. Chose this over swapping `passlib` for `bcrypt`/`argon2-cffi` directly as the smallest-blast-radius fix; long-term migration tracked separately. Test baseline: 45 pass / 5 fail → 48 pass / 2 fail.
- **Connection ORM foreign keys (PR #13, closes #8):** `Connection.workspace_id` and `Connection.user_id` were bare `Column(UUID)` without `ForeignKey(...)`. The DB-level FK on `workspace_id` already existed; on `user_id` it did not. This PR declared both on the ORM side so `Base.metadata.create_all` (used by the test DB) would stop creating orphan-tolerant tables. Matches the pattern applied earlier to `Post.connection_id`. No schema change.
- **Slack router test mock target (PR #16, closes #6):** `test_router_calls_slack_for_configured_workspace` patched `app.delivery.router.SlackSender`, but `CHANNEL_SENDERS` held a direct reference to the original class captured at import time, so the patch did nothing. The real sender ran, `.send()` raised, `asyncio.gather(..., return_exceptions=True)` swallowed it silently, and the mock assertion failed with a confusing "not called" error. Fixed by switching to `patch.dict("app.delivery.router.CHANNEL_SENDERS", {"slack": mock_class})`. Root cause for both this and PR #20: patch where the name is looked up, not where it's defined.
- **JWT claim enforcement (PR #15, closes #7):** `jwt.decode` in `get_current_user` now passes `options={"require": ["exp", "sub"]}`, so tokens missing either claim fail loudly with a `PyJWTError` at decode time instead of sneaking through to a later `KeyError` catch. Two new regression tests (`test_get_current_user_rejects_token_missing_sub`, `test_get_current_user_rejects_token_missing_exp`) hit `/workspace/channels` with hand-crafted tokens and assert 401. Defense-in-depth hardening flagged by the PR #4 security reviewer.
- **`connections.user_id` DB-level FK (PR #19, closes #14):** migration 003 adds `connections_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`. Uses the two-phase `ADD CONSTRAINT ... NOT VALID` + `VALIDATE CONSTRAINT` pattern so the migration is safe against a large production table — phase 1 holds `ACCESS EXCLUSIVE` only for the catalog update; phase 2 scans under `SHARE UPDATE EXCLUSIVE`, which does not block reads or writes. Explicit `ON DELETE RESTRICT` declared on both migration and ORM (`Connection.user_id`) to prevent default-drift between the two. Includes a pre-flight orphan check that raises a repairable error with counts + repair query if any orphan rows exist. Test baseline: 51 pass / 1 fail (test_e2e only).
- **`test_e2e` mock path (PR #20, closes #11):** `test_full_pipeline_end_to_end` patched `app.services.embedding.embedding_provider`, but `app.routers.profile:11` does `from app.services.embedding import embedding_provider` at import time — the router had its own local binding that the patch never touched. The real `_LazyEmbeddingProvider` instantiated an `AsyncOpenAI` client with the placeholder API key and returned a 401. Fixed by switching the patch target to `app.routers.profile.embedding_provider` — the site where the name is actually looked up. Added an inline comment naming the rule so future contributors don't repeat the mistake. Test baseline flipped from 51 pass / 1 fail → **52 pass / 0 fail**, the first fully-green `main` in the repo's history.
- **`DeliveryRouter.deliver` gather failure logging (PR #24, closes #18):** `await asyncio.gather(*tasks, return_exceptions=True)` was discarding its results entirely — every exception raised inside a sender's `.send()` was silently swallowed with no log, no metric, no breadcrumb. This was the systemic weakness that let issue #6 hide for months. Fix: track `invoked_channels` alongside `tasks`, iterate `gather` results after the call, and `logger.error(...)` each exception with `channel`, `alert_id`, `workspace_id`, and `exc_info=result` (stack trace preserved). `return_exceptions=True` is intentionally preserved so one failing channel never cancels siblings — only visibility changes. New regression test `test_router_logs_channel_failure_and_continues_siblings`.

### Changed
- Docs structure flattened: removed `docs/superpowers/specs/`, `docs/superpowers/plans/`, `docs/archive/` in favor of per-phase directories under `docs/phase-N/`
- Plan file naming convention: Phase 2's multi-plan slice uses `implementation-<feature>.md` (e.g., `implementation-foundation.md`) to stay consistent with Phase 1's single `implementation.md`
- `.superpowers/` (brainstorming session directory) added to `.gitignore`
- **Pipeline flow (PR #10):** keyword filter is no longer a gate that drops posts; it contributes to scoring via `keyword_match_strength`. All posts now flow through embedding + Ring 1 + Ring 2 + scoring, so semantic matches on posts without exact keyword hits are no longer silently dropped. Workspace `anti_keywords` still act as a spam pre-check. Ring matches and embeddings are persisted before the alert-threshold check so non-alerted posts still record signal hits for analytics.
- **`DeliveryRouter` sender registry is constructor-injected (PR #23, closes #17):** `DeliveryRouter.__init__(senders: dict[str, type] | None = None)` defaults to the module-level `CHANNEL_SENDERS` so production call sites (`pipeline.py:233 → DeliveryRouter()`) are unchanged. Tests now pass `DeliveryRouter(senders={"slack": mock_class})` instead of monkey-patching globals. The sentinel pattern `if senders is not None else CHANNEL_SENDERS` (not `senders or CHANNEL_SENDERS`) preserves the `{}` = "deliberately disable all" semantic. Type annotation tightening (proper `Sender` / `SenderFactory` Protocols) tracked as part of issue #21.

### Security
- **JWT claim enforcement (PR #15, closes #7):** see "Fixed" — `jwt.decode` now requires `exp` and `sub` at decode time, rather than depending on a downstream `KeyError` catch to reject malformed tokens. Explicit > implicit for security-critical contracts.

---

## Pre-changelog commits (for reference — everything before the changelog was introduced)

The commits below predate this changelog. They are summarized for context; future changes will be logged inline under `[Unreleased]` as they happen.

### Phase 2 Foundation — Implementation in progress on `feat/phase-2-foundation-impl`

- `2720f44` — feat(models): add Trend ORM model
- `3b802a2` — feat(models): add CompanySignalSummary ORM model
- `77ae6dd` — feat(models): add PersonSignalSummary ORM model
- `4b05098` — feat(models): add Signal ORM model with pgvector embedding
- `b29afa5` — fix(tests): repair async fixture registration and test db URL parsing (conftest.py made `db_session` unusable under pytest-asyncio 1.x strict mode)
- `15a5e31` — fix(models): sync ORM with migration 002 — Workspace.backfill_used + Post.connection_id FK
- `cd656b0` — feat(db): phase 2 foundation schema migration + pgvector ORM support

### Phase 1 — Shipped

- Ingest pipeline, capability profile extraction, keyword + embedding matching, 3-dimension scorer, context generator (LLM-based outreach drafts), delivery router (Slack, email, WhatsApp, Telegram), Chrome extension, React dashboard, auth (JWT + bcrypt)
- See `docs/phase-1/implementation.md` for the original 4,700-line implementation plan

---

## Changelog maintenance policy

Going forward, every substantive PR or direct-to-main commit adds a line to this file under `[Unreleased]`. When a release is cut, the `[Unreleased]` block becomes a versioned block with a release date. Entries are grouped by `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

**What counts as "substantive":**
- New features
- Bug fixes
- Schema changes
- Dependency additions/swaps
- Security fixes
- Breaking changes
- Notable docs changes (like CLAUDE.md rebuilds)

**What does NOT need a changelog entry:**
- Typo fixes in docs
- Comment-only changes
- Internal-only test additions that don't affect behavior
- Dependency version bumps within a minor range (unless security-relevant)
