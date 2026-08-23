#!/usr/bin/env python3
"""Exact-duplicate removal for the Enron corpus index.

The full-corpus EDA (``reports/eda/report.md`` §14) found that over half of
the non-empty message bodies in ``data/enron/index.jsonl`` are byte-exact
copies of another message (cross-custodian cc'ing, blast mails, saved
sent-folder copies). Sampling from the raw index therefore repeatedly draws
the same underlying text under different filenames.

This module is the single source of truth for deduplication:

- ``body_hash(text)`` — md5 over UTF-8 (errors="ignore"), **identical to the
  hash used by ``scripts/eda/explore_enron.py`` §14**, so EDA duplicate counts
  and sampler drop counts are directly comparable.
- ``dedupe_index(...)`` — streams an index JSONL and writes a copy containing
  at most one row per distinct non-empty body hash. Rows with an **empty
  body are never treated as duplicates of each other** (they carry distinct
  headers/paths and would otherwise be silently merged); this mirrors the
  EDA, which only hashes non-empty bodies. First occurrence wins; the index
  is sorted by maildir path, so output is deterministic.

Downstream consumers:
- ``build_pipeline_dump.py`` dedupes by construction while sampling (same
  ``body_hash``), so the stratified sample can never contain two rows with
  identical text.
- Regenerate a fully deduplicated index with::

    python scripts/dedupe.py \
        --index data/enron/index.jsonl \
        --out data/enron/index.unique.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def body_hash(text: str) -> str | None:
    """md5 over UTF-8 bytes (errors='ignore') — None for empty input.

    Must stay byte-compatible with the EDA engine's §14 duplicate counting,
    which hashes ``row['body']`` whenever it is truthy.
    """
    if not text:
        return None
    return hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()


def dedupe_index(
    index: Path,
    out: Path,
) -> dict:
    """Stream *index*, write first occurrences only to *out*, return stats.

    Returns a stats dict: ``total_rows``, ``written``, ``dropped_duplicates``
    (rows skipped because their body hash was seen), ``empty_body_rows``
    (passed through unconditionally), ``unique_texts`` (distinct hashes), and
    ``largest_group_copies`` (max copies of any single text in the source).
    """
    seen: set[str] = set()
    hash_counts: dict[str, int] = {}
    stats = {
        "total_rows": 0,
        "written": 0,
        "dropped_duplicates": 0,
        "empty_body_rows": 0,
        "unique_texts": 0,
        "largest_group_copies": 0,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with index.open(encoding="utf-8") as src, out.open("w", encoding="utf-8") as dst:
        for line in src:
            row = json.loads(line)
            stats["total_rows"] += 1
            h = body_hash(row.get("body") or "")
            if h is None:
                stats["empty_body_rows"] += 1
                dst.write(line if line.endswith("\n") else line + "\n")
                stats["written"] += 1
                continue
            hash_counts[h] = hash_counts.get(h, 0) + 1
            if h in seen:
                stats["dropped_duplicates"] += 1
                continue
            seen.add(h)
            dst.write(line if line.endswith("\n") else line + "\n")
            stats["written"] += 1

    stats["unique_texts"] = len(hash_counts)
    stats["largest_group_copies"] = max(hash_counts.values(), default=0)
    return stats


def main_with_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True,
                        help="Input index JSONL (e.g. data/enron/index.jsonl)")
    parser.add_argument("--out", type=Path, required=True,
                        help="Deduplicated output JSONL")
    args = parser.parse_args(argv)

    if not args.index.exists():
        parser.error(f"index not found: {args.index} — run build_corpus_index.py first")

    print(f"Deduplicating {args.index} -> {args.out} ...")
    stats = dedupe_index(args.index, args.out)
    total = stats["total_rows"]
    print(f"rows read:            {stats['total_rows']:,}")
    print(f"unique rows written:  {stats['written']:,}")
    print(f"duplicate rows dropped: {stats['dropped_duplicates']:,} "
          f"({stats['dropped_duplicates'] / max(1, total):.1%} of input)")
    print(f"empty-body rows passed through: {stats['empty_body_rows']:,}")
    print(f"distinct body texts:  {stats['unique_texts']:,}")
    print(f"largest duplicate group: {stats['largest_group_copies']:,} copies")
    return 0


def main() -> int:
    raise SystemExit(main_with_args(__import__("sys").argv[1:]))


if __name__ == "__main__":
    main()
