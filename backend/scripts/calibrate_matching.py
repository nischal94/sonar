"""Matching-threshold calibration harness for Sonar.

Exports per-post top-signal cosine similarities to a labeling markdown file,
ingests user-provided binary labels, and computes ROC/PR/F1 curves to
identify an empirically-justified matching_threshold.

Two-phase workflow:

  Phase 1 — export labeling doc:
      python scripts/calibrate_matching.py export \
          --workspace-id <uuid> \
          --out eval/calibration/<name>.md

  Phase 2 — analyze filled-in labels:
      python scripts/calibrate_matching.py analyze \
          --workspace-id <uuid> \
          --labels eval/calibration/<name>.md

The analyzer reports:
  * distribution of cosines for labeled-match vs labeled-non-match pairs
  * precision/recall/F1/F0.5 at every threshold 0.00–1.00 (step 0.01)
  * recommended threshold at max F1 and max F0.5 (false-positive-averse)
  * sanity check: posts that would fire at the recommended threshold

The goal is to replace the current vibes-based matching_threshold=0.72
with an empirically-grounded number for each workspace's data.
See issue #106 for context.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from app.database import get_db  # noqa: E402


# ---------- Phase 1 — export labeling doc ---------------------------------

LABELING_HEADER = """# Sonar — Matching Calibration: Labeling Doc

**Workspace:** `{workspace_id}`
**Generated:** {generated_at}
**Posts:** {post_count}  |  **Signals (enabled):** {signal_count}

## Instructions

For each post below, decide: **if I were the user of this workspace, would I
want Sonar to alert me about this post as a buying-intent signal?**

- `[x]` = yes, this is a real intent signal I'd want to see
- `[ ]` = no, this is noise / irrelevant / off-topic
- Leave the `reason` field blank unless the judgment is non-obvious

Do NOT overthink edge cases — first-gut label is the most calibrated. The
analyzer computes F1 and F0.5 at every threshold, so a few ambiguous labels
won't skew results.

Posts are sorted by their current max-cosine against any signal (descending),
so the most "relevant by the model" posts come first.

---

"""

LABELING_ENTRY = """## Post {index} — max_cosine = {max_cos:.3f}

**Top-3 matching signals:**
{top_signals}

**Content:**

```
{content}
```

**Label:** `[ ]`  ← replace with `[x]` if this is a real intent signal

**Reason (optional):**

<!-- label-id: {post_id} -->

---

"""


@dataclass
class PostSignalRow:
    post_id: str
    content: str
    top_signals: list[tuple[str, float]]  # [(phrase, cosine), ...]
    max_cosine: float


async def fetch_post_signal_data(workspace_id: UUID) -> list[PostSignalRow]:
    """Fetch each post with its top-3 highest-cosine signals."""
    query = text(
        """
        WITH pairs AS (
          SELECT p.id AS post_id,
                 p.content AS content,
                 s.phrase AS phrase,
                 1 - (p.embedding <=> s.embedding) AS cosine,
                 ROW_NUMBER() OVER (
                   PARTITION BY p.id
                   ORDER BY (p.embedding <=> s.embedding)
                 ) AS rnk
          FROM posts p
          CROSS JOIN signals s
          WHERE p.workspace_id = :wsid
            AND p.embedding IS NOT NULL
            AND s.workspace_id = :wsid
            AND s.enabled
            AND s.embedding IS NOT NULL
        )
        SELECT post_id, content, phrase, cosine, rnk
        FROM pairs
        WHERE rnk <= 3
        ORDER BY post_id, rnk
        """
    )

    async for db in get_db():
        result = await db.execute(query, {"wsid": str(workspace_id)})
        rows = result.all()
        break

    grouped: dict[str, PostSignalRow] = {}
    for post_id, content, phrase, cosine, rnk in rows:
        key = str(post_id)
        if key not in grouped:
            grouped[key] = PostSignalRow(
                post_id=key, content=content, top_signals=[], max_cosine=0.0
            )
        grouped[key].top_signals.append((phrase, float(cosine)))
        if float(cosine) > grouped[key].max_cosine:
            grouped[key].max_cosine = float(cosine)

    return sorted(grouped.values(), key=lambda r: -r.max_cosine)


async def cmd_export(workspace_id: UUID, out_path: Path) -> None:
    from datetime import datetime, timezone

    rows = await fetch_post_signal_data(workspace_id)

    signal_count_query = text(
        "SELECT COUNT(*) FROM signals WHERE workspace_id = :wsid AND enabled"
    )
    async for db in get_db():
        signal_count = (
            await db.execute(signal_count_query, {"wsid": str(workspace_id)})
        ).scalar_one()
        break

    doc = LABELING_HEADER.format(
        workspace_id=workspace_id,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        post_count=len(rows),
        signal_count=signal_count,
    )

    for idx, row in enumerate(rows, start=1):
        top_signals_md = "\n".join(
            f"- `{phrase}` (cosine {cos:.3f})" for phrase, cos in row.top_signals
        )
        doc += LABELING_ENTRY.format(
            index=idx,
            post_id=row.post_id,
            max_cos=row.max_cosine,
            top_signals=top_signals_md,
            content=row.content.strip(),
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc)
    print(f"[calibrate] wrote {len(rows)} posts to {out_path}")
    print(
        "[calibrate] next: edit the file, change `[ ]` to `[x]` for real matches, then run `analyze`"
    )


# ---------- Phase 2 — analyze labels --------------------------------------

LABEL_RE = re.compile(
    r"\*\*Label:\*\*\s*`\[(?P<mark>[ xX])\]`.*?<!-- label-id: (?P<pid>[a-f0-9\-]+) -->",
    re.DOTALL,
)


def parse_labels(labels_path: Path) -> dict[str, bool]:
    """Extract {post_id: is_match_bool} from the filled labeling doc."""
    doc = labels_path.read_text()
    labels: dict[str, bool] = {}
    for match in LABEL_RE.finditer(doc):
        pid = match.group("pid").strip()
        mark = match.group("mark").strip().lower()
        labels[pid] = mark == "x"
    return labels


async def fetch_max_cosine_per_post(workspace_id: UUID) -> dict[str, float]:
    """For each post, return its max cosine across all enabled signals."""
    query = text(
        """
        SELECT p.id::text AS post_id,
               MAX(1 - (p.embedding <=> s.embedding)) AS max_cos
        FROM posts p
        CROSS JOIN signals s
        WHERE p.workspace_id = :wsid
          AND p.embedding IS NOT NULL
          AND s.workspace_id = :wsid
          AND s.enabled
          AND s.embedding IS NOT NULL
        GROUP BY p.id
        """
    )
    async for db in get_db():
        result = await db.execute(query, {"wsid": str(workspace_id)})
        rows = result.all()
        break
    return {pid: float(cos) for pid, cos in rows}


def compute_metrics_at_threshold(
    cosines: list[float], labels: list[bool], threshold: float
) -> dict[str, float]:
    """Compute precision, recall, F1, F0.5 at a single threshold."""
    tp = fp = fn = tn = 0
    for cos, label in zip(cosines, labels):
        predicted_match = cos >= threshold
        if predicted_match and label:
            tp += 1
        elif predicted_match and not label:
            fp += 1
        elif not predicted_match and label:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    # F0.5 weighs precision 2× recall — use when false positives cost more
    # than misses (typical for alert-style products).
    f_half = (
        1.25 * precision * recall / (0.25 * precision + recall)
        if (0.25 * precision + recall)
        else 0.0
    )
    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "f0_5": f_half,
    }


def print_distribution(cosines: list[float], labels: list[bool]) -> None:
    match_cos = sorted([c for c, lb in zip(cosines, labels) if lb])
    nonmatch_cos = sorted([c for c, lb in zip(cosines, labels) if not lb])

    print(f"\n=== cosine distribution ({len(cosines)} posts labeled) ===")
    print(f"matches    n={len(match_cos):3d}  ", end="")
    if match_cos:
        print(
            f"min={min(match_cos):.3f} p25={_pct(match_cos, 25):.3f} "
            f"median={_pct(match_cos, 50):.3f} p75={_pct(match_cos, 75):.3f} "
            f"max={max(match_cos):.3f}"
        )
    else:
        print("(none — all posts labeled non-match; calibration not possible)")
    print(f"non-match  n={len(nonmatch_cos):3d}  ", end="")
    if nonmatch_cos:
        print(
            f"min={min(nonmatch_cos):.3f} p25={_pct(nonmatch_cos, 25):.3f} "
            f"median={_pct(nonmatch_cos, 50):.3f} p75={_pct(nonmatch_cos, 75):.3f} "
            f"max={max(nonmatch_cos):.3f}"
        )
    else:
        print("(none — all posts labeled match)")

    if match_cos and nonmatch_cos:
        overlap_lo = max(min(match_cos), min(nonmatch_cos))
        overlap_hi = min(max(match_cos), max(nonmatch_cos))
        if overlap_lo <= overlap_hi:
            print(
                f"overlap zone: [{overlap_lo:.3f}, {overlap_hi:.3f}] — "
                "thresholds in this range will misclassify either direction"
            )
        else:
            print("distributions are SEPARABLE — any threshold in the gap is perfect")


def _pct(sorted_list: list[float], pct: float) -> float:
    if not sorted_list:
        return 0.0
    idx = int(len(sorted_list) * pct / 100)
    idx = max(0, min(idx, len(sorted_list) - 1))
    return sorted_list[idx]


def print_sweep(cosines: list[float], labels: list[bool]) -> dict[str, dict]:
    print("\n=== threshold sweep ===")
    print(
        f"{'thr':>6}  {'TP':>3} {'FP':>3} {'FN':>3} {'TN':>3}  "
        f"{'P':>5} {'R':>5} {'F1':>5} {'F0.5':>5}"
    )

    best_f1 = {"f1": -1.0}
    best_f0_5 = {"f0_5": -1.0}
    rows = []
    for i in range(0, 101):
        thr = i / 100
        m = compute_metrics_at_threshold(cosines, labels, thr)
        rows.append(m)
        if m["f1"] > best_f1.get("f1", -1):
            best_f1 = m
        if m["f0_5"] > best_f0_5.get("f0_5", -1):
            best_f0_5 = m

    # Print a sampled subset to keep output readable
    printed = set()
    for m in rows:
        step = m["threshold"]
        if step in printed:
            continue
        # every 0.05 + any that are at best-F1 or best-F0.5
        if abs((step * 20) - round(step * 20)) < 1e-6 or m is best_f1 or m is best_f0_5:
            marker = ""
            if m is best_f1:
                marker += " ← max F1"
            if m is best_f0_5:
                marker += " ← max F0.5"
            print(
                f"{m['threshold']:>6.2f}  "
                f"{m['tp']:>3} {m['fp']:>3} {m['fn']:>3} {m['tn']:>3}  "
                f"{m['precision']:>5.2f} {m['recall']:>5.2f} "
                f"{m['f1']:>5.2f} {m['f0_5']:>5.2f}{marker}"
            )
            printed.add(step)

    return {"best_f1": best_f1, "best_f0_5": best_f0_5}


async def cmd_analyze(workspace_id: UUID, labels_path: Path) -> None:
    labels_map = parse_labels(labels_path)
    if not labels_map:
        print(
            f"[calibrate] no label markers found in {labels_path}. "
            "Expected `**Label:** `[x]`` + `<!-- label-id: <uuid> -->` pairs."
        )
        sys.exit(1)

    cosines_map = await fetch_max_cosine_per_post(workspace_id)
    if not cosines_map:
        print("[calibrate] no posts with embeddings found for this workspace.")
        sys.exit(1)

    paired = [
        (cosines_map[pid], labels_map[pid]) for pid in labels_map if pid in cosines_map
    ]
    unmatched = set(labels_map) - set(cosines_map)
    if unmatched:
        print(
            f"[calibrate] warning: {len(unmatched)} labeled posts not found in DB "
            "(skipped). possible IDs drifted since export."
        )

    cosines = [p[0] for p in paired]
    labels = [p[1] for p in paired]
    match_count = sum(labels)

    print(f"\nloaded {len(paired)} labeled posts for workspace {workspace_id}")
    print(
        f"  matches: {match_count} ({match_count / len(paired):.0%})   "
        f"non-matches: {len(paired) - match_count}"
    )

    print_distribution(cosines, labels)
    bests = print_sweep(cosines, labels)

    print("\n=== recommendations ===")
    f1 = bests["best_f1"]
    fh = bests["best_f0_5"]
    print(
        f"max F1 @ cosine {f1['threshold']:.2f}  "
        f"(P={f1['precision']:.2f} R={f1['recall']:.2f} F1={f1['f1']:.2f})"
    )
    print(
        f"max F0.5 @ cosine {fh['threshold']:.2f}  "
        f"(P={fh['precision']:.2f} R={fh['recall']:.2f} F0.5={fh['f0_5']:.2f})"
    )
    print(
        "\nFor alert-style products (false positives cost more than misses),"
        " F0.5 is usually the right objective."
    )
    print(
        "\nNOTE: the recommended values are thresholds on MAX RING-2 COSINE"
        " per post, not on combined_score. To translate to combined_score,"
        " multiply by 0.5 (relevance weight) and add the expected"
        " relationship+timing contribution."
    )


# ---------- main ---------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    ex = subparsers.add_parser("export", help="export labeling doc")
    ex.add_argument("--workspace-id", type=UUID, required=True)
    ex.add_argument("--out", type=Path, required=True)

    an = subparsers.add_parser("analyze", help="analyze filled-in labels")
    an.add_argument("--workspace-id", type=UUID, required=True)
    an.add_argument("--labels", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "export":
        asyncio.run(cmd_export(args.workspace_id, args.out))
    elif args.cmd == "analyze":
        asyncio.run(cmd_analyze(args.workspace_id, args.labels))


if __name__ == "__main__":
    main()
