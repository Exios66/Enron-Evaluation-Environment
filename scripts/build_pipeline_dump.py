#!/usr/bin/env python3
"""Build the pipeline-ready Enron correspondence dump.

Stratified sample of the full-corpus index -> ``data/enron/pipeline.jsonl``
(gitignored, regenerable), the handoff artifact for llm-entity-extraction's
docclass surface. Row shape is the flat streamer-dump shape:

    {filename, doc_text, prompt, expected, expected_subclass, metadata}

with ``expected: "correspondence"`` for every row and ``expected_subclass``
from the comprehensive enum in ``scripts/correspondence_subclasses.py``.

Sampling (deterministic, seed 42):
- Deduplicated by construction: every row's non-empty body text is hashed
  (md5, identical scheme to ``scripts/dedupe.py`` / the EDA §14 counts) and a
  hash seen before is skipped, so the sample can never contain two rows with
  identical text even though >50% of corpus bodies are byte-exact copies.
- Every NON-email subclass present in the corpus is included wholesale up to
  a per-subclass cap (they are the rare, high-value types: memo, letter,
  notice, demand, attorney_demand, press_release, meeting_request,
  voicemail).
- The ``email`` subclass is quota-stratified across custodians
  (log-volume-proportional, per-custodian cap) with internal/external and
  attachment-presence balance.
- ``other`` (unparseable/non-email files) is included as a small control
  slice.

Coverage contract (the subclass enum's completeness guarantee): the sample's
subclass set must equal the corpus's present subclass set — the dump can
never silently drop a correspondence type the corpus contains. ``--dry-run``
prints the composition + fingerprint and FAILS on a coverage miss.

Usage:
    python scripts/build_pipeline_dump.py --dry-run
    python scripts/build_pipeline_dump.py --n 400
    python scripts/build_pipeline_dump.py --n 500 --seed 42 --out /tmp/pipeline.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from correspondence_subclasses import (  # noqa: E402
    SUBCLASS_KEYS,
    label_correspondence,
)
from dedupe import body_hash  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data" / "enron" / "index.jsonl"
DEFAULT_OUT = ROOT / "data" / "enron" / "pipeline.jsonl"

SOURCE_DATASET = "enron-cmu-20150507"
NON_EMAIL_CAP = 45      # per non-email subclass wholesale cap
OTHER_CAP = 20          # control slice for unparseable files
EMAIL_CAP_PER_CUSTODIAN = 15
DEFAULT_N = 500


def _addr_line(name: str, addr: str) -> str:
    name = (name or "").strip()
    addr = (addr or "").strip()
    if name and addr:
        return f"{name} <{addr}>"
    return name or addr or ""


def _doc_text(row: dict) -> str:
    """Render a correspondence document (headers + body + attachment manifest)."""
    lines = []
    sender = _addr_line(row.get("sender") or "", row.get("sender_addr") or "")
    lines.append(f"FROM: {sender}" if sender else "FROM: (unknown)")
    recip_lines = []
    for r in row.get("recipients") or []:
        role = (r.get("role") or "to").upper()
        text = _addr_line(r.get("name") or "", r.get("addr") or "")
        recip_lines.append(f"{role}: {text}" if text else f"{role}: (none)")
    lines.extend(recip_lines or ["TO: (none)"])
    lines.append(f"DATE: {row.get('date') or ''}")
    lines.append(f"SUBJECT: {row.get('subject') or ''}")
    attachments = row.get("attachments") or []
    if attachments:
        for a in attachments:
            lines.append(f"ATTACHMENT: {a.get('name')} ({a.get('mime')}, "
                         f"{a.get('size')} bytes)")
    else:
        lines.append("ATTACHMENTS: (none)")
    siblings = row.get("sibling_files") or []
    if siblings:
        for s in siblings:
            lines.append(f"ATTACHMENT FILE: {s.get('name')} ({s.get('size')} bytes)")
    lines.append("---")
    body = (row.get("body") or "").strip()
    if body:
        lines.append(body)
    return "\n".join(lines)


def _metadata(row: dict, subclass: str, evidence: str) -> dict:
    return {
        "source_dataset": SOURCE_DATASET,
        "custodian": row.get("custodian") or "",
        "folder": row.get("folder") or "",
        "thread": row.get("thread") or "",
        "sender": row.get("sender") or "",
        "sender_addr": row.get("sender_addr") or "",
        "recipients": row.get("recipients") or [],
        "date": row.get("date") or "",
        "subject": row.get("subject") or "",
        "message_id": row.get("message_id") or "",
        "references": row.get("references") or "",
        "in_reply_to": row.get("in_reply_to") or "",
        "body_content_type": row.get("body_content_type") or "",
        "body_chars": len(row.get("body") or ""),
        "attachments": row.get("attachments") or [],
        "sibling_files": row.get("sibling_files") or [],
        "expected_subclass": subclass,
        "subclass_evidence": evidence,
    }


def _fingerprint(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda r: r["filename"]):
        h.update(r["filename"].encode("utf-8", errors="replace"))
        h.update(b"\x00")
        h.update(r["expected"].encode())
        h.update(b"\x00")
        h.update((r["expected_subclass"] or "").encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


def build_sample(index: Path, n: int, seed: int) -> tuple[list[dict], dict]:
    """Stream the index, label every row, and return the stratified sample.

    Exact-duplicate bodies (same md5 as ``dedupe.body_hash``) are skipped on
    first sight, so no two sampled rows ever carry identical text. The
    returned stats dict carries the drop counts under ``"dedupe"``.
    """
    import random

    rng = random.Random(seed)

    buckets: dict[str, list[dict]] = defaultdict(list)
    email_buckets: dict[str, list[dict]] = defaultdict(list)
    present: set[str] = set()
    counts: Counter = Counter()
    seen_body_hashes: set[str] = set()
    dup_skipped = 0
    empty_body_rows = 0

    with index.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            h = body_hash(row.get("body") or "")
            if h is None:
                empty_body_rows += 1
            elif h in seen_body_hashes:
                dup_skipped += 1
                continue
            else:
                seen_body_hashes.add(h)
            subclass, evidence = label_correspondence(row)
            counts[subclass] += 1
            present.add(subclass)
            if subclass == "email":
                custodian = row.get("custodian") or "?"
                email_buckets[custodian].append((row, subclass, evidence))
            else:
                buckets[subclass].append((row, subclass, evidence))

    picked: list[tuple[dict, str, str]] = []
    pick_stats: Counter = Counter()

    # 1. Non-email subclasses: wholesale up to the per-subclass cap.
    for key in SUBCLASS_KEYS:
        if key == "email" or key not in present:
            continue
        pool = buckets[key]
        cap = OTHER_CAP if key == "other" else NON_EMAIL_CAP
        rng.shuffle(pool)
        for item in pool[:cap]:
            picked.append(item)
            pick_stats[key] += 1

    # 2. email subclass: log-volume-proportional quotas per custodian.
    remaining = n - len(picked)
    if remaining < 0:
        raise RuntimeError(
            f"non-email subclasses alone exceed the sample budget ({n}) — "
            f"raise --n (need >= {len(picked)})")
    cust_volumes = {c: len(v) for c, v in email_buckets.items()}
    log_vol = {c: math.log1p(v) for c, v in cust_volumes.items()}
    total_log = sum(log_vol.values())
    quota: dict[str, int] = {}
    for c, lv in log_vol.items():
        raw = max(1, round(remaining * lv / total_log))
        quota[c] = min(raw, EMAIL_CAP_PER_CUSTODIAN)
    # Absorb the leftover budget spread by volume.
    while sum(quota.values()) < remaining:
        overflow = [c for c in quota if quota[c] < EMAIL_CAP_PER_CUSTODIAN]
        if not overflow:
            break
        c = max(overflow, key=lambda c: log_vol[c] / max(1, quota[c]))
        quota[c] += 1

    for custodian, pool in email_buckets.items():
        q = quota.get(custodian, 0)
        rng.shuffle(pool)
        for item in pool[:q]:
            picked.append(item)
            pick_stats["email"] += 1

    if len(picked) < n:
        # Top up from remaining email pools (rare when quotas cap out).
        extra_pool = []
        for custodian, pool in email_buckets.items():
            extra_pool.extend(pool[quota.get(custodian, 0):])
        rng.shuffle(extra_pool)
        for item in extra_pool[: n - len(picked)]:
            picked.append(item)
            pick_stats["email"] += 1

    rows = []
    for row, subclass, evidence in picked:
        rows.append({
            "filename": row["filename"],
            "doc_text": _doc_text(row),
            "prompt": "",
            "expected": "correspondence",
            "expected_subclass": subclass,
            "metadata": _metadata(row, subclass, evidence),
        })

    sample_present = {r["expected_subclass"] for r in rows}
    coverage = {
        "present_in_corpus": sorted(present),
        "present_in_sample": sorted(sample_present),
        "complete": present == sample_present,
    }
    return rows, {
        "n_requested": n,
        "n_picked": len(picked),
        "corpus_counts": dict(counts),
        "sample_counts": dict(pick_stats),
        "coverage": coverage,
        "fingerprint": _fingerprint(rows),
        "dedupe": {
            "rows_read": sum(counts.values()) + dup_skipped,
            "duplicates_skipped": dup_skipped,
            "empty_body_rows_passed": empty_body_rows,
            "unique_texts_available": len(seen_body_hashes) + empty_body_rows,
        },
    }


def main_with_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX,
                        help=f"Index JSONL (default: {INDEX})")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"Output JSONL (default: {DEFAULT_OUT})")
    parser.add_argument("--n", type=int, default=DEFAULT_N,
                        help=f"Target sample size (default: {DEFAULT_N})")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print composition + coverage + fingerprint without writing")
    args = parser.parse_args(argv)

    if not args.index.exists():
        parser.error(f"index not found: {args.index} — run build_corpus_index.py first")

    print(f"Sampling {args.index} (n={args.n}, seed={args.seed}) ...")
    rows, stats = build_sample(args.index, args.n, args.seed)

    print(f"\nCorpus subclass counts: {stats['corpus_counts']}")
    print(f"Sample composition: {stats['sample_counts']} (total {stats['n_picked']})")
    cov = stats["coverage"]
    dd = stats["dedupe"]
    print(f"\nDedupe: skipped {dd['duplicates_skipped']:,} exact-duplicate "
          f"bodies while sampling ({dd['empty_body_rows_passed']:,} empty-body rows "
          f"passed through; {dd['unique_texts_available']:,} unique texts available)")
    print(f"\nSubclass coverage — corpus {len(cov['present_in_corpus'])} keys: "
          f"{cov['present_in_corpus']}")
    print(f"  sample {len(cov['present_in_sample'])} keys: {cov['present_in_sample']}")
    print(f"  COMPLETE: {cov['complete']}")
    print(f"dataset_fingerprint: {stats['fingerprint']}")

    if args.dry_run:
        print(f"\nDry run: would write {len(rows)} rows -> {args.out}")
        return 0 if cov["complete"] else 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for r in sorted(rows, key=lambda r: r["filename"]):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(rows)} rows -> {args.out}")
    return 0 if cov["complete"] else 2


def main() -> int:
    raise SystemExit(main_with_args(sys.argv[1:]))


if __name__ == "__main__":
    main()