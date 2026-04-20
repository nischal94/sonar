# Sonar Phase 2.6 — Fit × Intent Hybrid Scoring

**Status:** Design proposal — awaiting user review
**Date:** 2026-04-20 (session 9 brainstorm)
**Supersedes:** issue [#106](https://github.com/nischal94/sonar/issues/106) (narrow "threshold calibration" framing)
**Evidence base:** issue [#113](https://github.com/nischal94/sonar/issues/113), [PR #114](https://github.com/nischal94/sonar/pull/114), `eval/calibration/findings-dogfood-martech.md`, `eval/calibration/phase-2.6-evidence.md`

---

## 1. Problem

Session 8's calibration (PR #114) proved empirically that the current post-only Ring 2 cosine-similarity matching model cannot discriminate buying intent from noise on real user data. On a 30-post hand-labeled dogfood dataset:

- F1_max = 0.27 (random-ish baseline for binary classification)
- Match cosine range: 0.201 – 0.424
- Non-match cosine range: 0.161 – **0.475**
- **max(non-match) > max(match)** — the distributions are inverted at the top. The two highest-cosine posts in the entire dataset are from competing vendors (NotifyVisitors CPO, MoEngage sales director). If the product shipped today, these would be the first two alerts the user saw.

Two structural causes confirmed by the evidence:

1. **Asymmetry ceiling.** 7-word signal phrases vs. 100-word promotional posts. Cosine similarity conflates stylistic with semantic distance. Observed ceiling: ~0.47 even on clearly-related pairs. Signal and noise compress into a ~0.0–0.5 band, half the nominal space.

2. **Missing author context.** The model sees words, not people. A competing vendor's promo post outranks an ICP-target's brand announcement because both mention "D2C brands" or "marketing automation" — the model has no signal that the first author is a seller and the second is a buyer.

The remedy: move from single-axis scoring (post content similarity alone) to two-axis scoring where the identity of the poster is a first-class input.

---

## 2. Solution in one paragraph

Replace the current `combined_score` with a multiplicative hybrid:

```
final_score = fit_score × intent_score
```

`fit_score` is a new per-connection score (0 to 1) that captures whether the *author* looks like the workspace's ICP, based on their LinkedIn headline + company compared to an ICP description extracted from the workspace URL. `intent_score` is the existing Ring 2 + timing + keyword signal, repurposed as the "does this post express intent" component. The multiplicative combination ensures low fit zeros out any intent regardless of post content — fixing the Lipi Mittal class of failure directly. One ICP input, no separate disqualifier list: the ICP text is phrased contrastively ("buyers of martech, not other martech vendors") so a single cosine encodes both positive ICP and implicit anti-ICP.

---

## 3. Decisions, with reasoning

Every decision below is locked. Plan-B escape hatches are noted where relevant but are not built in v1.

### 3.1 ICP input — tiered, URL-first

| Tier | Input | Produces |
|---|---|---|
| **1 (default)** | Workspace URL | LLM-extracted ICP paragraph |
| **2** | Uploaded doc (sales playbook, pitch deck) | LLM-normalized ICP paragraph |
| **3** | Manually typed text in wizard | ICP paragraph verbatim |

**Why:** matches the "just a URL and go" onboarding promise. All three tiers converge on the same downstream object (a paragraph of ICP text), so downstream code is tier-agnostic.

### 3.2 Two-term fit: contrastive ICP + subtractive seller-mirror (both v1)

Fit score combines a positive term and a negative term:

```
fit_score = cos(ICP_embedding, connection_embedding)
          − λ × cos(seller_mirror_embedding, connection_embedding)
```

- **ICP paragraph (positive term):** LLM-extracted from the workspace input. Phrased contrastively — it names who you *do* sell to AND explicitly names who you do *not* (e.g. *"…Not employees of martech SaaS vendors or competing agencies"*).
- **Seller-mirror paragraph (negative term):** LLM-extracted from the same input, describing *"what other sellers of this capability look like on LinkedIn"* — the linguistic mirror of the workspace's own capability. Subtracted with a small positive weight `λ` (default `0.3`, tunable during calibration).

**Why both, not contrastive alone:** embedding models handle negation imperfectly. A string like *"Not employees of martech SaaS vendors"* often scores *closer* to competing-vendor language in embedding space because the tokens `employees / martech / SaaS / vendors` still appear. The subtractive term removes this dependency on the embedding model understanding negation — it explicitly subtracts a seller-shape signal.

**Why this is cheap:** one additional LLM call per workspace (seller-mirror extraction, amortized across all connections), one additional embedding per connection at backfill time (~$0.00002 each), one subtraction at scoring time. No new infra.

**Why keep the contrastive ICP too:** the contrastive phrasing can't hurt, and calibration will tell us which term (ICP-positive, seller-mirror-negative, or both) actually carries the load. If one term dominates, we can simplify in a follow-on.

### 3.3 Connection-side fit input — headline + company

Concatenate `Connection.headline` + `" "` + `Connection.company` at score-time. Already stored on `Connection`. No new enrichment API, no new storage.

**Why:** every case in `eval/calibration/phase-2.6-evidence.md` is discriminable with only headline + company. LinkedIn headlines are weirdly information-dense (people cram role + specialty + value prop into ~150 chars). Lipi Mittal's headline literally contains "Powering 1000+ Global D2C Brands" (self-identifying as seller). Divya's is "Brand, Marketing & AI Strategy in BFSI" (self-identifying as buyer).

If company is null (some connections don't surface a company field), fall back to headline alone. No padding or synthetic filler.

**Deferred:** per-connection aggregated post history (stateful, heavy), LinkedIn profile enrichment via Apify/RocketReach (paid, couples to third-party). Reopen these only if v1 data shows the headline+company input is the bottleneck.

### 3.4 Fit encoder — text-embedding-3-small

Same model used for intent side today. Already deployed, cached, paid-for. No new infra.

**Why:** we don't know yet that the asymmetric ICP-paragraph vs. short-headline comparison will be the bottleneck, so don't pre-buy infrastructure change. If calibration shows it is, **Plan B** is to switch to `text-embedding-3-large` (longer context, higher quality, 3x cost — still trivial at fit-side volume) or an asymmetric retrieval model (BGE / E5) in a follow-on slice.

### 3.5 Combination — multiplicative

```
final_score = fit_score × intent_score
```

**Why:** matches industry standard (6sense, Apollo, Demandbase all use fit × intent multiplicative). The Lipi Mittal fix depends on multiplicativity: a 0.2 fit × 0.9 intent = 0.18 (correctly suppressed); whereas additive `0.4 × fit + 0.6 × intent = 0.62` would promote the same post. Multiplicativity is the math that zeros out sellers.

**Intent score composition** — same inputs as today's `combined_score` except relationship axis removed:

- Ring 2 cosine relevance (with Ring 1 keyword boost): weight 0.7
- Timing decay (linear over 24h): weight 0.3

**Relationship degree moves to display layer.** It already exists as a 1st/2nd degree filter on the dashboard — that's the right home. Keeping it in the scoring math double-counted; degree is about the user's *access* to the person (can you DM them?), not about whether the person is a buyer showing intent. A 3rd-degree connection showing high fit × high intent should rank above a 1st-degree connection showing low fit × low intent — the current scorer does the opposite. Degree filtering on the dashboard already lets the user restrict to their reachable set.

### 3.6 Prior-post memory — not in v1

No Bayesian author-bump across posts. Fit is a stateless function of the connection's current headline + company. Intent is a stateless function of the post.

**Why:** adds state, refresh logic, edge cases (which post window to aggregate, how to weight recent vs. older posts, how to handle connections who post rarely). We haven't proven the base stateless case needs it. Defer until post-launch data shows stateless demonstrably misses and stateful would catch.

### 3.7 Migration — feature-flag parallel deployment

New column: `Workspace.use_hybrid_scoring: bool` (default `FALSE`). Pipeline branches at scoring:

```python
if workspace.use_hybrid_scoring:
    scoring = compute_hybrid_score(...)
else:
    scoring = compute_combined_score(...)  # existing, unchanged
```

Flip per-workspace after ICP extraction + fit backfill. New workspaces default to True once Phase 2.6 is validated on the dogfood workspace. Old `compute_combined_score` kept as dead code for one release cycle, then deleted.

**Why:** zero breaking changes. Existing workspaces keep current behavior until explicitly migrated. A/B comparison runs live. Rollback is a single config flag flip per workspace.

### 3.8 Definition of Done — three constraints on calibration output

All three must hold on *both* the Dwao and CleverTap labeled sets:

1. **Precision@top-5 ≥ 0.6** — of the 5 highest-scored posts, ≥ 3 are real matches. (This is the actual user experience; F1 hides it.)
2. **Recall ≥ 0.5** — the system catches ≥ half of real matches. Safety net against silent categorical failures.
3. **Zero competitor posts in top-5** — hard gate. Lipi/Gaurav-type leakage is trust-destroying; one leak is a ship-blocker on its own.

**Why not F1 ≥ 0.6:** F1 is the wrong metric for alert UX. Users care about what they see (precision in top-K), not harmonic-mean-of-P-and-R. A 0.8 precision × 0.3 recall product (narrow but trustworthy) is better than a 0.5/0.5 product (broadly mediocre), and F1 ranks them wrong.

---

## 4. Architecture

### Component graph

```
                              ┌──► ICP paragraph ───► embed ───► workspace.icp_embedding
Workspace input ──► LLM ──────┤                                              │
(URL / doc / text)            └──► Seller-mirror ───► embed ───► workspace.seller_mirror_embedding
                                                                             │
                                                                             ▼
Connection.headline + .company ──► embed ──► pos − λ·neg ──► connection.fit_score
                                                                             │
Post.content ──► Ring 1 keyword + Ring 2 cosine ──► intent_score             │
                                                          │                  │
                                                          ▼                  │
                                         final_score = fit_score × intent_score
                                                          │
                                                          ▼
                                                 alert / dashboard
```

### Schema changes (three non-breaking migrations)

```sql
-- Migration 008
ALTER TABLE connections ADD COLUMN fit_score REAL NULL;

-- Migration 009
ALTER TABLE workspaces ADD COLUMN use_hybrid_scoring BOOLEAN NOT NULL DEFAULT FALSE;

-- Migration 010 — ICP + seller-mirror text and their embeddings
ALTER TABLE capability_profile_versions ADD COLUMN icp TEXT NULL;
ALTER TABLE capability_profile_versions ADD COLUMN seller_mirror TEXT NULL;
ALTER TABLE capability_profile_versions ADD COLUMN icp_embedding vector(1536) NULL;
ALTER TABLE capability_profile_versions ADD COLUMN seller_mirror_embedding vector(1536) NULL;
```

No data loss, no downtime, no breaking changes. Existing workspaces run the existing scorer until explicitly flipped.

### Code changes (rough map)

- **New:** `app/prompts/extract_icp.py` and `app/prompts/extract_seller_mirror.py` (LLM prompt modules, versioned like `propose_signals.py`; can be combined into a single dual-output prompt if that proves more reliable)
- **New:** `app/services/fit_scorer.py` (`compute_fit_score`, `compute_hybrid_score`)
- **Extended:** `app/routers/profile.py` `extract()` endpoint — return `icp` alongside `capability`
- **Extended:** `app/workers/pipeline.py` — branch on `workspace.use_hybrid_scoring`
- **Extended:** `frontend/src/pages/SignalConfig.tsx` (wizard) — add tier-2/3 ICP inputs and an ICP review step
- **New script:** `backend/scripts/backfill_fit_scores.py` — one-shot to compute fit for existing connections when a workspace opts in
- **Unchanged:** `scorer.py::compute_combined_score` — left in place behind the flag for one release cycle

---

## 5. Calibration plan

Re-use `backend/scripts/calibrate_matching.py` against the session-8 dataset:

1. Extract Dwao ICP + seller-mirror via Tier 1 (URL). Review/tighten the ICP via Tier 2/3 if obviously weak.
2. Compute `fit_score` (positive − λ·negative) for each of the 49 dogfood connections. Sweep λ ∈ {0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0} to find the value that best separates buyer from seller connections.
3. Compute `intent_score` for each of the 30 labeled posts (same cosines as session 8, minus the relationship axis).
4. Compute `final_score = fit_score × intent_score` for each `(post, connection)` pair.
5. Run analyzer, measure Precision@5, Recall, and top-5 competitor count at each λ. Pick the λ that maximizes Precision@5 while holding Recall ≥ 0.5.
6. Repeat 1–5 with CleverTap ICP + seller-mirror (extracted from `clevertap.com`), re-labeling the same 30 posts under the CleverTap lens (~15 min of labeling time).
7. If both pass the DoD at the chosen λ: flip `use_hybrid_scoring=True` for the dogfood workspace, ship Phase 2.6.
8. If either fails: diagnose via top-N analysis. Likely culprits and their fixes: (a) encoder asymmetry — upgrade to `text-embedding-3-large`; (b) weak ICP extraction — improve the prompt or add a tier-2 review step in the wizard; (c) λ sweep finds no usable value — indicates seller-mirror and ICP embeddings aren't discriminating; try asymmetric retrieval model (BGE / E5) in a follow-on slice.

---

## 6. Non-goals (explicitly deferred)

- Prior-post memory / Bayesian author-bump (§3.6)
- External enrichment of connection data (Apify/RocketReach person-profile)
- Per-signal ICP (one ICP per workspace for v1)
- Continuous re-calibration via user feedback loop (`feedback_trainer` integration)
- True third-party product-company dogfood pre-launch — calibration via re-labeling is sufficient to ship
- Post-level intent model improvements (signal expansion, asymmetric retrieval models) — Ring 2 stays as intent_score for v1; revisit in Phase 2.7 if calibration shows the intent side is the bottleneck
- Multi-workspace ICP transfer learning
- Real-time LinkedIn headline change detection

---

## 7. Risks

1. **Asymmetric fit comparison.** ICP paragraph (~50–100 words) vs. headline+company (~20 words) is asymmetric in the same direction that hurt intent scoring. Mitigation: Precision@K is less sensitive to absolute-score compression than F1. Seller-mirror subtraction also helps because it's computed on the same asymmetric space — both terms compress similarly and the difference is preserved. If the comparison *does* fail DoD, fall back is `text-embedding-3-large` or an asymmetric retrieval model.
2. **LLM ICP extraction quality.** A site with generic copy produces a generic ICP. Tier 2 review step in the wizard surfaces the extracted ICP for user correction, but users who don't customize get the generic version. Mitigated by the contrastive-phrasing convention, the seller-mirror subtraction (which compensates for a weak positive ICP), and the review step.
3. **Thin LinkedIn headlines.** "Professional at [Company]", "CEO" etc. produce noisy fit scores. Data-quality issue, not a model issue — the scorer correctly reflects genuine uncertainty. Eventual mitigation: per-connection "enrichment nudge" prompting user to manually tag ICP status for thin-headline people (deferred).
4. **Finding the right λ.** The subtractive weight `λ` on the seller-mirror term is a new tuning knob. Calibration sweeps it ({0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0}). If no λ produces a usable Precision@5 / Recall curve, the seller-mirror isn't carrying its weight — that's a signal to rethink the negative term (different prompt, different input) rather than scrap it.

---

## 8. Implementation sequence (feeder for writing-plans)

Not the full plan — just the slicing shape:

1. Migration 008+009+010 + model updates
2. `app/prompts/extract_icp.py` + `app/prompts/extract_seller_mirror.py` (or one shared prompt module producing both outputs) + extended `profile/extract` endpoint returning both
3. `app/services/fit_scorer.py` (`compute_fit_score` with positive − λ·negative, `compute_hybrid_score`)
4. `backend/scripts/backfill_fit_scores.py` one-shot (runs for every workspace that flips to hybrid, re-embeds existing connections)
5. Pipeline branch in `app/workers/pipeline.py` on `workspace.use_hybrid_scoring`
6. Wizard frontend updates (tier-2/3 ICP inputs + review step showing both extracted ICP and seller-mirror)
7. Calibration run #1 (Dwao) with λ sweep + CleverTap re-label + findings
8. If DoD passes: flip flag for new workspaces, retire `compute_combined_score` after one release
9. If DoD fails: diagnose per §5 step 8, ship the indicated fix (encoder upgrade, prompt improvement, or retrieval model swap)

Each step ships as its own PR with its own review. The full plan (per-task dependency graph, test matrix, rollout sequencing) is the output of the `superpowers:writing-plans` invocation that follows this design's approval.
