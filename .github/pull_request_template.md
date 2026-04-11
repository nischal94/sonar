## Summary

<!-- What does this PR do, and why? Link the issue it closes. -->

Closes #

## Changes

<!-- Bullet list of notable changes. Match the level of detail to the blast radius. -->

-

## Test plan

<!-- Exact commands you ran, and what you observed. Replace the placeholders. -->

- [ ] `docker compose exec -T api pytest -q` → X passed / Y failed
- [ ] Manually verified the happy path
- [ ] Edge cases considered:

## Checklist

- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org) (`feat(scope):`, `fix(scope):`, …)
- [ ] PR title uses a Conventional Commits prefix so release-drafter labels it automatically
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if this is a substantive change
- [ ] New or updated tests cover the behavior I touched (no "I manually verified" for non-trivial logic)
- [ ] No secrets, API keys, or personal data committed — `.env`, credentials, PII all clean
- [ ] If this is security-sensitive (auth, crypto, user input, LLM output used for execution), `superpowers:code-reviewer` was run before requesting merge

## Deployment notes

<!-- Migration dependencies, env var changes, rollout order, rollback plan. Delete this section if not applicable. -->
