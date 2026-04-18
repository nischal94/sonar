# Backfill — Apify Actor Research

**Date:** 2026-04-18 (session 6 follow-up)
**Status:** Decision locked — MVP pick is `harvestapi/linkedin-profile-posts`
**Closes:** [issue #76](https://github.com/nischal94/sonar/issues/76) (1st-degree half; 2nd-degree is a separate slice)

This spike fulfills Task 1 of `docs/phase-2/implementation-backfill.md`. The
code change that accompanies it lives in
`backend/app/services/apify.py::RealApifyService` — the normalized
`ApifyProfilePost` Pydantic model is unchanged; only the raw-field mapping
and actor ID moved.

---

## 1. Candidates evaluated

| Actor | Price / 1k posts | Cookies? | Input shape | Output schema | Notes |
|---|---|---|---|---|---|
| **`harvestapi/linkedin-profile-posts`** ✅ MVP pick | **$1.50** | No | `targetUrls[]` + `postedLimitDate` | Top-level `id`, `content`, `postedAt`, nested `author.linkedinUrl`, `engagement.{likes,comments,shares}` | 6 profiles concurrent; LinkedIn-specialist maintainer |
| `apimaestro/linkedin-profile-posts` | $5.00 | No | Profile URL + pagination tokens | `urn`, `text`, `posted_at`, `author.profile_url`, `stats.*` | Cleanest schema, 4.7/5 rating — but **3.3× too expensive for MVP budget** |
| `supreme_coder/linkedin-post` | $1.00 | No | Profile URLs + others | Field names not surfaced in marketplace listing (requires a trial run to confirm) | Cheapest, but schema opacity makes it risky without a paid trial |
| `curious_coder/linkedin-post-search-scraper` | $30/mo + usage | **Yes** | Profile URL + search URLs | `postedAtISO`, `numLikes`, `numComments`, `numShares` | Subscription model + cookie requirement → higher compliance risk; not a fit |

**Why `harvestapi` wins:**
1. **No cookies required.** Uses no-login scraping infrastructure, so we're
   not asking users to hand over their LinkedIn session and we're not
   risking our own account if we self-host a run. This is a hard
   requirement — any cookie-based actor is off the table for a
   multi-tenant SaaS.
2. **`postedLimitDate` maps cleanly to our 60-day window.** Compute
   `datetime.now(UTC) - timedelta(days=60)` and pass as ISO.
3. **Price sits in the affordable band** (next paragraph). `supreme_coder`
   is technically cheaper but the schema isn't documented publicly;
   swapping actors mid-dogfood would waste a day of debugging.
4. **LinkedIn-specialist maintainer.** `harvestapi` publishes a family of
   LinkedIn actors, which means the schema stays internally consistent if
   we later add a profile-search or company-posts actor.

---

## 2. Cost reality check — revision to `backfill-decisions.md §4`

**Original estimate in the decisions doc:** ~$0.40 / workspace.
**Re-derived estimate with a real actor:** $1.50–$3.00 / workspace.

**What happened.** The original $0.40 figure assumed a flat `~500 posts /
run` upper bound at a hypothetical $0.80 / 1k. Nothing checked against a
real actor. The worker today sets `maxPostsPerProfile: 30`, so the
theoretical ceiling is `200 profiles × 30 posts = 6000 posts / run` —
15× the original assumption. Real LinkedIn power users post less than
30× / 60-day window, so real pulls land ~1000–2000 posts per workspace.

**Two levers to get back near $0.40:**

1. **Lower `maxPostsPerProfile` from 30 → 10.** 200 profiles × 10 = 2000
   post ceiling → ~$3.00 / workspace at `harvestapi` pricing. Typical real
   pull will be much lower (most profiles don't have 10 posts in 60 days).
2. **Lower the connections cap from 200 → 100.** Halves the cost ceiling.

**MVP decision:** keep 200 profiles, lower `maxPostsPerProfile` to **10**.
Most profiles won't hit the ceiling anyway (the median LinkedIn connection
posts ~2–5 times per 60 days), and we keep the "pull from your top 200
connections" framing that makes the product feel complete. Realistic
per-workspace cost: **$0.75–$1.50**, ceiling $3.00.

**This is a real budget change.** `backfill-decisions.md §4` should be
updated from "~$0.40/workspace" to "~$1.50/workspace, ceiling $3.00." Dogfood
runs during the build phase are now $15–$45 instead of $5–$15. Still
tolerable, but call it out before burning through budget.

---

## 3. Schema mapping

Source-of-truth Pydantic model in `app/services/apify.py`:

```python
class ApifyProfilePost(BaseModel):
    profile_url: str
    linkedin_post_id: str
    content: str
    posted_at: datetime
    reaction_count: int = 0
    comment_count: int = 0
    share_count: int = 0
```

Mapping from `harvestapi` output to our normalized model:

| Our field | `harvestapi` path | Fallback if missing |
|---|---|---|
| `profile_url` | `author.linkedinUrl` (or `author.profileUrl`) | skip row |
| `linkedin_post_id` | `id` | skip row |
| `content` | `content` | `""` |
| `posted_at` | `postedAt.timestamp` (parse ISO) | skip row |
| `reaction_count` | `engagement.likes` (or `engagement.totalReactions`) | `0` |
| `comment_count` | `engagement.comments` | `0` |
| `share_count` | `engagement.shares` | `0` |

Missing-field rows are skipped rather than raised — one malformed row from
Apify shouldn't kill the whole batch. This matches what the original code
did and is consistent with the worker's partial-success handling.

---

## 4. 2nd-degree ICP-filtered actor — not evaluated

Out of scope for this spike. Issue #76 also covers the 2nd-degree research
but that's tied to the deferred 2nd-degree Backfill slice, not MVP. When
that slice is planned, search the Apify marketplace for
"linkedin people search" or "linkedin sales navigator" actors and run the
same comparison. Known candidates to start from:

- `harvestapi/linkedin-profile-search` (no cookies, appears in marketplace)
- `bebity/linkedin-premium-actor` (bulk profiles + companies)

---

## 5. Verification before first real run

Before the first dogfood Backfill with a real `APIFY_API_TOKEN`:

1. In the Apify console, run `harvestapi/linkedin-profile-posts` once
   manually against **3 of your own 1st-degree connection URLs** with
   `maxPosts: 5`, `postedLimitDate: 60 days ago`. Verify actual output
   JSON matches the mapping in §3 — Apify marketplace docs can lag
   actual API response by a rev.
2. If any of the mapped paths above are wrong, update
   `RealApifyService.scrape_profile_posts` field-access lines (not the
   Pydantic model — keep the normalized shape stable).
3. Once verified, run the full 200-profile pipeline with a real workspace.

Sources consulted:

- [Apify marketplace search — LinkedIn profile posts](https://apify.com/store?search=linkedin+profile+posts)
- [`harvestapi/linkedin-profile-posts`](https://apify.com/harvestapi/linkedin-profile-posts)
- [`apimaestro/linkedin-profile-posts`](https://apify.com/apimaestro/linkedin-profile-posts)
- [`supreme_coder/linkedin-post`](https://apify.com/supreme_coder/linkedin-post)
- [`curious_coder/linkedin-post-search-scraper`](https://apify.com/curious_coder/linkedin-post-search-scraper)
- [Apify pricing](https://apify.com/pricing)
