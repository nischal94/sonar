# Phase 2.6 Evidence Pool

Concrete cases from the session-8 labeling pass that illustrate why **post-only Ring 2 cosine similarity cannot distinguish buying intent from noise in a real user network.** These cases ground the Phase 2.6 (Fit × Intent) design discussion — they are real posts, real authors, real (non-)matches.

Every case is from the dogfood workspace `eb23b44f-88ea-4a94-88ae-b9aca2d66345`. Author details are labeler-visible information only (LinkedIn headlines), nothing scraped or private.

---

## Category A — Author is strong ICP, but the post content is thin / brand-copy

These are *misses* of the current model: labeler marked **n** under strict post-level, but the author is exactly the person a martech agency would want to be alerted about.

### A1. Divya Prakash Singhal — Utkarsh Small Finance Bank

**Headline:** "Brand, Marketing & AI Strategy | Building Scalable Growth Engines in BFSI"

Three posts in the dataset:
- **Post 7** — "Experience unparalleled! ✨ Lumiere™ by RBL Bank #InspiredByYou". One-line brand promo. Labeled **n**.
- **Post 26** — "Had a great shoot today with the legend Sunil Chhetri. … Something exciting is coming soon… stay tuned! #UtkarshSFB". Teaser. Labeled **n**.
- **Post 29** — "Yeh sirf cricket nahi… yeh connection hai. Utkarsh Small Finance Bank x Mumbai Indians". Brand cricket-sponsorship promo. Labeled **n**.

**Why this matters:** Divya's headline is nearly a textbook martech-agency ICP — brand + marketing + AI strategy leader in a regulated, growth-motivated vertical (BFSI). The three posts are her doing her job (amplifying brand work). The current model correctly gives each low cosine, but the model has no way to see the author context that would flag her as a person worth reaching out to *at all times*, independent of post content.

In a hybrid model: high fit × low intent per post = low-priority persistent nurture, not silent drop.

### A2. Akhilendra Pandey — RBL Bank

**Headline:** "AVP - Product Marketing, RBL Bank | Symbiosis Institute of International Business"

Three posts in the dataset:
- **Post 4** — Long personal essay on AI + product marketing + stack consolidation. Thoughtful, explicit about rethinking tools. **Labeled y.** cosine 0.424.
- **Post 20** — "Experience unparalleled! ✨ Lumiere™ by RBL Bank". One-liner. Labeled **n**. cosine 0.245.
- **Post 22** — "You can't miss this! Super engaging and insightful." Thin amplification. Labeled **n**. cosine 0.242.

**Why this matters:** Same author, three posts. One is a real buying-intent signal; two are brand-copy noise. The current model scores them roughly proportionally but treats each post independently — **no memory that this author already demonstrated high intent on a prior post.** In a hybrid model: Post 4 establishes a high fit score for Akhilendra; Posts 20 and 22 ride that fit score upward because they come from the same verified-ICP author.

---

## Category B — Post content is highly relevant, but the author is anti-ICP

These are *false positives* of the current model: the top cosines in the entire 300-pair dataset, all correctly labeled **n** by the labeler for reasons the current model cannot see.

### B1. Lipi Mittal — NotifyVisitors (martech vendor)

**Headline:** "5x 🚀 AI Driven Ecom Growth | CPO | 2x Revenue & Conversion, 3x MAU, 2x Orders | **Powering 1000+ Global D2C Brands** | Driving Retention & Data-Led Personalization"

Two posts in the dataset, ranked **#1 and #2 by cosine** across all 300 pairs:
- **Post 1** — NotifyVisitors Acer cart-abandonment case study. **Cosine 0.475 (highest in the entire dataset).** Labeled **n**.
- **Post 2** — NotifyVisitors Just Herbs engagement case study. **Cosine 0.470.** Labeled **n**.

**Why this matters:** Lipi's "Powering 1000+ Global D2C Brands" language is vendor-speak: she works AT a martech SaaS. Her posts are the company's marketing content. The martech agency labeling is the correct answer — she is a competitor, not a buyer. **If the product shipped today, these two posts would be the first two alerts the user sees**, and they are the worst possible alerts: "your competitor posted about their wins." Not just a missed opportunity — an actively trust-burning alert.

### B2. Gaurav Taparia — MoEngage (martech vendor)

**Headline:** "Director Sales at MoEngage | Ex-IBM, HP"

One post in the dataset:
- **Post 11** — "Glad to share that I made it to the President's Club at MoEngage for the 4th year in a row!" Career milestone at a competing vendor. Labeled **n**. cosine 0.335.

**Why this matters:** Gaurav is a senior sales person at *the exact martech product* (MoEngage) the user considered as a positioning alternative during the session. His LinkedIn activity will skew heavily toward martech content for obvious reasons — he sells it for a living. Under hybrid scoring: **fit ≈ 0** (he is a vendor selling a competing product) **× intent > 0** = filtered out regardless of content cosine.

---

## Category C — Author is a buyer-ICP founder actively investing in marketing

These are *correct positives* that the current model surfaces weakly or not at all because the cosine on brand-campaign posts is moderate, not high.

### C1. Amit Sah — OZi (modern parenting brand founder)

- **Post 15** — "Welcoming Parineeti Chopra as OZi's brand ambassador". Brand-ambassador campaign launch. **Labeled y.** cosine 0.279.

**Why this matters:** A founder announcing their first brand ambassador is investing real money in marketing. Martech agency alarm should ring here. Current model: cosine 0.279 puts this below the workspace's own threshold of 0.30; the product would go silent on exactly the moment the customer becomes alert-worthy.

### C2. Akriti Gupta — Loopie (modern parenting brand founder)

- **Post 18** — "Meet the Loopieheads" 1-year brand campaign. **Labeled y.** cosine 0.261.
- **Post 27** — "Pune's first Baby Rave Party — Loopie brand activation". **Labeled y.** cosine 0.228.

**Why this matters:** Same founder, actively running *multiple* brand marketing investments in parallel. Two posts labeled y; both below cosine 0.3. Same silent failure as C1.

---

## Implications for Phase 2.6 design

The six cases above cover the two failure modes the hybrid Fit × Intent scoring must fix:

1. **Fit lookup must persist and influence per-post scoring even when post content is thin** (Category A).
2. **Fit lookup must down-rank posts from ICP-opposites** (competitors, vendors selling the same thing as the user) (Category B).
3. **Fit boost must lift "brand-investing buyer" posts above the dominated intent-only ranking** (Category C).

Concrete Phase 2.6 requirements the evidence justifies:

- **Per-connection fit_score** derived from headline + company + role, stored on the connection (not computed per-post). Refreshes when headline changes.
- **fit_score inputs:** positive examples (labeler's target ICP description), negative examples (competitors, vendors selling same category). Matches the industry standard of "ICP fit with disqualifier rules."
- **Combined score:** multiplicative. `final_score = fit_score × intent_score`. Fit ≈ 0 (a vendor) × any intent = near-zero.
- **Persistence of prior-post evidence:** if an author has produced one strong intent post, subsequent posts from the same author should get a fit-score bump. (Think of it as a Bayesian prior update.)
- **Threshold calibration AFTER the architecture lands** — not before. This calibration run is the "before" baseline; the next calibration run will be the "after."

The specific encoder / prompting / model choices for the fit model are open questions worth a dedicated design session. The product requirement is settled by the evidence above.
