#!/usr/bin/env python3
"""Draw the human spot-check sample for the subclass ground truth.

Reads ``data/enron/pipeline.jsonl``, draws a per-subclass review sample
(``--per-class`` rows each, capped), and writes two CSVs:

- ``data/spot_check.csv`` — the working copy the human edits
- ``reports/eda/spot_check.csv`` — the committed review artifact

Columns: ``filename``, ``subclass`` (heuristic), ``evidence``, ``subject``,
``sender_addr``, ``date``, ``body_head`` (first 200 chars), ``human_label``
(empty — the human's corrected subclass key), ``notes`` (empty).

After review, the corrected CSV is the authoritative subclass GT subset for
the ``attorney_demand``/``demand``/... dimensions (feed it back into
llm-entity-extraction's docclass eval as per-class GT where needed).

Usage:
    python scripts/spot_check.py
    python scripts/spot_check.py --per-class 5 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "data" / "enron" / "pipeline.jsonl"
DATA_OUT = ROOT / "data" / "spot_check.csv"
REPORT_OUT = ROOT / "reports" / "eda" / "spot_check.csv"

FIELDS = ["filename", "subclass", "evidence", "subject", "sender_addr",
          "date", "body_head", "human_label", "notes"]


def draw_sample(pipeline: Path, per_class: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_class: dict[str, list[dict]] = defaultdict(list)
    with pipeline.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if "expected_subclass" not in row:
                raise ValueError(
                    "rows must be pipeline-dump shape {filename, doc_text, "
                    "prompt, expected, expected_subclass, metadata} — run "
                    "build_pipeline_dump.py first")
            by_class[row["expected_subclass"]].append(row)
    out = []
    for key in sorted(by_class):
        pool = by_class[key]
        rng.shuffle(pool)
        for row in pool[:per_class]:
            md = row["metadata"]
            out.append({
                "filename": row["filename"],
                "subclass": row["expected_subclass"],
                "evidence": md.get("subclass_evidence") or "",
                "subject": md.get("subject") or "",
                "sender_addr": md.get("sender_addr") or "",
                "date": md.get("date") or "",
                "body_head": " ".join((row["doc_text"] or "").split())[:200],
                "human_label": "",
                "notes": "",
            })
    out.sort(key=lambda r: (r["subclass"], r["filename"]))
    return out


def main_with_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", type=Path, default=PIPELINE,
                        help=f"Pipeline dump (default: {PIPELINE})")
    parser.add_argument("--per-class", type=int, default=5,
                        help="Rows per subclass (default: 5)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=None,
                        help="Override the data/ output path")
    args = parser.parse_args(argv)

    if not args.pipeline.exists():
        parser.error(f"pipeline dump not found: {args.pipeline} — "
                     f"run build_pipeline_dump.py first")

    rows = draw_sample(args.pipeline, args.per_class, args.seed)
    out = args.out or DATA_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with REPORT_OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    from collections import Counter

    per = Counter(r["subclass"] for r in rows)
    print(f"Wrote {len(rows)} review rows -> {out}")
    print(f"  (mirror -> {REPORT_OUT})")
    print(f"Per-class: {dict(per)}")
    return 0


def main() -> int:
    raise SystemExit(main_with_args(sys.argv[1:]))


if __name__ == "__main__":
    main()