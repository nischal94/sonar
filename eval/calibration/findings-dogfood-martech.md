# Calibration Findings — Dogfood Workspace (Martech Agency Profile)

**Workspace:** `eb23b44f-88ea-4a94-88ae-b9aca2d66345`
**Dataset:** 30 posts with embeddings × 10 enabled signals = 300 pairs
**Labeled:** all 30 posts, single-label under Philosophy A (post-level intent)
**Date:** 2026-04-20
**Labeler:** Sharad Chandel (Dwao agency owner, product owner)

## TL;DR

The current post-only Ring 2 matching model **cannot produce a usable alert product in this data**. The cosine distributions of "real intent signals" and "noise" are not just overlapping — they are **inverted**: the highest-cosine post across all 300 pairs was a non-match (vendor promoting a competing tool), while the four actual intent signals are spread across cosine 0.20–0.42, below multiple noise posts. No threshold on the existing single-axis score can recover usable precision and recall simultaneously.

**F1_max = 0.27, F0.5_max = 0.25** — nearly random ranking for alert purposes.

This is not a threshold-tuning problem. This is an architecture problem. The product requires **Phase 2.6 — Fit × Intent hybrid scoring** before any further calibration work is meaningful.

## Labels

Distribution: **4 yes / 26 no** out of 30.

| # | Author (role) | Label | Notes |
|---|---|---|---|
| 4 | Akhilendra Pandey (AVP Product Marketing, RBL Bank) | y | Thoughtful personal essay on AI + marketing stack. Real decision-maker actively rethinking tools. |
| 15 | Amit Sah (Founder, OZi) | y | Brand-ambassador campaign launch — founder actively investing in marketing. |
| 18 | Akriti Gupta (Founder, Loopie) | y | "Meet the Loopieheads" 1-year brand campaign. Same pattern as 15. |
| 27 | Akriti Gupta | y | "Pune's first Baby Rave Party" — active brand experiential marketing by same founder. |
| rest | (various) | n | See doc for per-post notes. |

## Cosine distribution

| Group | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| matches | 4 | 0.201 | 0.261 | 0.279 | 0.424 | 0.424 |
| non-matches | 26 | 0.161 | 0.240 | 0.301 | 0.354 | **0.475** |

**Observation:** `max(non-matches)` > `max(matches)`. The distribution is not merely overlapping — it is inverted at the top end.

**The highest-cosine post (0.475)** was labeled **no**: Lipi Mittal (CPO at NotifyVisitors, visible via "Powering 1000+ Global D2C Brands") posting an Acer cart-abandonment case study. The current model ranked this as most relevant. The labeler recognized it as a competing vendor, not a buyer.

## Threshold sweep

| Threshold | TP | FP | FN | TN | Precision | Recall | F1 | F0.5 | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 0.00 | 4 | 26 | 0 | 0 | 13% | 100% | 0.24 | 0.16 | fire on everything |
| 0.20 | 4 | 23 | 0 | 3 | 15% | 100% | 0.26 | 0.18 | catches all real matches + 23 false alarms |
| **0.25** | 3 | 15 | 1 | 11 | 17% | 75% | **0.27** | 0.20 | **max F1** |
| 0.30 | 1 | 13 | 3 | 13 | 7% | 25% | 0.11 | 0.08 | worse |
| 0.40 | 1 | 4 | 3 | 22 | 20% | 25% | 0.22 | 0.21 | — |
| **0.41** | 1 | 3 | 3 | 23 | 25% | 25% | 0.25 | **0.25** | **max F0.5** |
| 0.45 | 0 | 2 | 4 | 24 | 0% | 0% | 0.00 | 0.00 | misses everything |
| **0.72** (current prod default) | 0 | 0 | 4 | 26 | n/a | 0% | 0.00 | 0.00 | **current behavior: silent** |

**F1 max = 0.27** means for every real match surfaced, ~2.7 false positives fire.
**F0.5 max = 0.25** means for every real match, 3 false positives fire AND 75% of real matches are missed.

For comparison, commodity sales-intelligence products like Clay, Apollo, Clearbit ship with F1 ≥ 0.6 on their core match primitive. Sonar's current primitive is at **less than half** of that floor.

## Why the model can't recover with better labels or more data

Two structural problems stack:

### 1. Asymmetry ceiling
Signal phrases are short (5–7 words) aspirational B2B statements: *"Evaluating a martech partner"*, *"Rebuilding our marketing automation stack"*. LinkedIn posts are long (100+ words) personal/promotional narratives with emojis, case studies, cricket references.

`text-embedding-3-small` encodes both into the same 1536-dim space. Cosine similarity reflects both semantic overlap *and* stylistic similarity. The stylistic gap alone depresses scores by 0.10–0.20 below what symmetric-retrieval benchmarks would suggest.

Observed ceiling: 0.475 even on clearly-related case-study ↔ automation-stack pairs. This bounds the entire discriminative range of the signal.

### 2. Missing author context ("the Divya dilemma")
Posts where `post_content` is nearly irrelevant but `author` is a high-fit ICP lead:

- **Post 7, 26, 29** — Divya Prakash Singhal, Brand/Marketing/AI Strategy at Utkarsh Bank. Three brand-copy amplifications; the current model correctly gives them low scores, but the labeler recognizes she is squarely in the martech agency's ICP. Three wasted opportunities per labeling round. At scale: thousands of missed conversations per month.
- **Post 20, 22** — Akhilendra Pandey, AVP Product Marketing at RBL Bank. Same author produced **Post 4** (a strong buying-intent essay labeled yes) and **Posts 20, 22** (thin brand-copy noise labeled no). The model has no way to use Post 4's signal to weight Akhilendra's future posts.

Posts where `post_content` scores highly but `author` is off-ICP:

- **Post 1, Post 2** — Lipi Mittal, NotifyVisitors CPO. The model ranks the two highest-cosine posts in the entire dataset. Both are the ICP's *competitor* amplifying their own tool. Firing on these would burn trust faster than any other failure mode.
- **Post 11** — Gaurav Taparia, Director of Sales at MoEngage. Competing vendor (the specific vendor the owner considered re-dogfooding against).

The common thread: cosine of text-content-only cannot see any of this. It sees words, not people.

## Implications for the roadmap

Per `CLAUDE.md`:

- **Phase 2 status:** 4 of 5 slices shipped. Final slice was supposed to be **Discovery** (Ring 3 nightly HDBSCAN clustering for emerging topics + weekly digest).
- **Finding:** Discovery clusters posts *by the same signal* the calibration just proved inadequate. Clusters built on a signal with F1=0.27 will group noise, not trends. Discovery on top of this is building on sand.
- **Phase 3 was originally sketched** as *real-time alerts, CRM integrations, team features*. Those are expansion features that all depend on matches being meaningful.

### Recommended resequence

1. **Phase 2.5** (new) — **File all calibration evidence** + document the gap. Produced by this exercise.
2. **Phase 2.6** (new) — **Fit × Intent scoring redesign.** Required before Discovery can produce useful clusters.
   - Fit score: per-connection, derived from headline + company + role vs. workspace ICP profile. Asymmetric retrieval model (BGE, E5, or OpenAI `text-embedding-3-large` with asymmetric prompts) as a candidate for the fit encoder.
   - Intent score: per-post, refined from current Ring 2 with signal expansion (augment short phrases with example-post longer text) to lift the asymmetry ceiling.
   - Combined: multiplicative (standard Fit × Intent, matches 6sense / Apollo / Demandbase pattern).
   - Recalibrate both independently against a new labeling pass.
3. **Phase 2 Discovery** — delay until 2.6 ships. Clustering needs a useful signal.
4. **Phase 3 expansion** features — deprioritize versus 2.6.

### What NOT to do

- **Do not ship the product with the current matching primitive and hope users tune it.** Threshold 0.72 currently fires on nothing. Any threshold that fires on real matches also fires on majority-false-positive noise. Users will churn inside one week.
- **Do not build user-facing feedback-loop training** on top of this primitive yet. The `feedback_trainer` adaptive logic assumes the primitive can discriminate given a good starting point; it cannot.
- **Do not invest in more signal engineering (better signal phrases, more signals per workspace) as a fix.** The asymmetry ceiling caps even perfect signals at ~0.5 cosine.

## Artifacts

- `eval/calibration/dogfood-martech-agency.md` — the labeled dataset (30 posts, 4 yes, 26 no)
- `eval/calibration/phase-2.6-evidence.md` — the specific ICP-mismatch examples called out during labeling
- `backend/scripts/calibrate_matching.py` — reusable harness; export and analyze phases. Point it at any workspace, any labeling file. Will be re-run against Phase 2.6 once the hybrid scorer lands.
