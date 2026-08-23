#!/usr/bin/env python3
"""Publish the CLEANED ENRON CORRESPONDENCE corpus to the Hugging Face Hub.

Local port of llm-entity-extraction's ``publish_enron_correspondence.py``
(KANBAN-074 pattern): consumes the full-corpus index built by
``scripts/build_corpus_index.py`` (CMU maildir -> one JSONL row per parsed
message, 517,390 rows, deterministic order), labels every row with the SHARED
labeler (``correspondence_subclasses.label_correspondence``), applies the
family-wide deterministic split rule, and publishes:

    {HF_USERNAME}/enron-correspondence      (default: Lucius-Morningstar/enron-correspondence)

Every row carries:
- ``filename``           maildir path relative to the root (deterministic id)
- ``text``               the cleaned email body (text/plain or HTML-stripped)
- ``subject``            decoded subject header
- ``expected``           ``correspondence`` (family doc_type)
- ``expected_subclass``  ground truth from the SHARED labeler (10-key taxonomy)
- ``label_evidence``     why the labeler fired (audit trail, on-row)
- ``split``              md5(filename) % 10 == 0 -> test (~10%) — SAME rule as
                         the whole Lucius-Morningstar dataset family
- ``metadata``           provenance: custodian, folder, date, sender/message
                         ids, recipient/attachment facts, source + license

Schema guard (KANBAN-073 lesson): rows lacking filename/subclass/split/text
refuse to publish — all-null leading batches crash the Hub viewer's JSON->
parquet conversion (string->null cast). Rows with an EMPTY body AND empty
subject are dropped (counted honestly in the manifest).

Staging (always runs): data/hf_export/<name>.jsonl + manifest.json + card.
Publish (requires HF_TOKEN env var or cached hub credentials):
    python scripts/publish_hf_dataset.py [--dry-run] [--limit N]

Post-upload the LFS sha256 on the Hub is compared against the local file
hash and a publish summary JSON is written for the evidence trail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.correspondence_subclasses import SUBCLASS_KEYS, label_correspondence  # noqa: E402

DEFAULT_INDEX = REPO_ROOT / "data" / "enron" / "index.jsonl"
OUT_DIR = REPO_ROOT / "data" / "hf_export"
STAGED_NAME = "enron_correspondence.jsonl"
HF_USERNAME = os.environ.get("HF_USERNAME", "Lucius-Morningstar")
REPO_ID = f"{HF_USERNAME}/enron-correspondence"
LABELER_TESTS = "40"


def assign_split(filename: str) -> str:
    """Family-wide split rule — identical to build_docclass_merged.assign_split.

    md5 hex digest mod 10 == 0 -> test (10%), else train (90%). Stable across
    rebuilds and machines, independent of row order.
    """
    digest = int(hashlib.md5(filename.strip().encode("utf-8")).hexdigest(), 16)
    return "test" if digest % 10 == 0 else "train"


CARD = """---
license: other
task_categories:
- text-classification
language:
- en
tags:
- legal
- enron
- email
- correspondence
- document-classification
- evaluation
- llm-mailroom
pretty_name: "Enron Correspondence (Cleaned, Subclass-Labeled)"
size_categories:
- 100K<n<1M
---

# Enron Correspondence (Cleaned, Subclass-Labeled)

The **full cleaned CMU Enron corpus** ({rows} parsed messages from the classic
maildir, {custodians} custodians) prepared for the llm-mailroom
document-classification pipeline: one row per message, every row carrying a
heuristic ground-truth subclass label from the shared
[`correspondence_subclasses`](https://github.com/Exios66/Enron-Evaluation-Environment)
labeler (10-key taxonomy: {taxonomy}) plus a deterministic train/test split.

## Row shape

One JSON object per line:

| Field | Meaning |
|---|---|
| `filename` | maildir path relative to the root (stable row id) |
| `text` | cleaned email body (text/plain, else HTML-stripped) |
| `subject` | decoded subject header |
| `expected` | gold doc_type — always `correspondence` |
| `expected_subclass` | heuristic ground truth: `{taxonomy}` |
| `label_evidence` | which marker/rule fired (on-row audit trail) |
| `split` | `train` / `test` — md5(filename) mod 10 == 0 → test (~10%) |
| `metadata` | custodian, folder, date, sender, message/thread ids, recipient + attachment facts, source/license |

Labels are HEURISTIC ground truth (regex/marker rules, human-reviewed via
spot checks in the source repo) — not hand annotations. They are exactly the
labels the production pipeline scores against; `other` means no specific
marker matched. Known honest gaps (from the source repo's AGENTS.md):
attorney detection relies on domain/name lists and is not exhaustive;
`voicemail` cannot occur in this text-only corpus (0% by construction);
cross-custodian duplicate copies of the same message are NOT merged — use
`metadata.message_id` to group or dedupe.

## Splits

Per-row `split`: `train` / `test` assigned by `md5(filename) mod 10 == 0`
(~10% test). Deterministic and order-independent — rebuilds and consumers
recompute identical splits without shipping separate files.

## Provenance

Built by [`Enron-Evaluation-Environment`](https://github.com/Exios66/Enron-Evaluation-Environment)
`scripts/publish_hf_dataset.py` ({built_utc}) from its full-corpus index
(`build_corpus_index.py`, {parseable}/{total} messages parseable, sorted
maildir walk — rebuilds byte-identical); row-compatible with
[`llm-entity-extraction`](https://github.com/Exios66/llm-entity-extraction)'s
KANBAN-074 publisher (same schema, labeler, and split rule). Source: CMU Enron
Email Dataset (cleaned maildir). Distribution restrictions: the Enron corpus is
released for RESEARCH use — treat personally identifying content accordingly.
Subclass labels: heuristic ruleset documented + regression-tested in the
source repo ({labeler_tests} labeler tests).
"""


def main_with_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--out", type=Path, default=OUT_DIR / STAGED_NAME)
    parser.add_argument("--repo-id", default=REPO_ID,
                        help=f"HF dataset repo (default: {REPO_ID})")
    parser.add_argument("--limit", type=int, default=None,
                        help="smoke-test cap on rows processed")
    parser.add_argument("--private", action="store_true",
                        help="create/update the Hub repo as private")
    parser.add_argument("--dry-run", action="store_true",
                        help="stage + validate only; never touch the network")
    args = parser.parse_args(argv)

    if not args.index.exists():
        parser.error(f"index not found: {args.index} — run "
                     f"scripts/build_corpus_index.py first")

    rows: list[dict] = []
    total = dropped_empty = unparseable = 0
    sub_counts: Counter = Counter()
    custodians: set[str] = set()
    with args.index.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            if args.limit and len(rows) >= args.limit:
                break
            r = json.loads(line)
            if not r.get("parseable"):
                unparseable += 1
                continue
            body = str(r.get("body") or "")
            subject = str(r.get("subject") or "")
            if not body.strip() and not subject.strip():
                dropped_empty += 1
                continue
            key, evidence = label_correspondence(r)
            fn = str(r.get("filename") or "")
            recips = r.get("recipients") or []
            meta = {
                "source": "cmu_enron_maildir",
                "license": "Enron corpus — released for research use",
                "built_by": "Enron-Evaluation-Environment scripts/publish_hf_dataset.py",
                "custodian": str(r.get("custodian") or ""),
                "folder": str(r.get("folder") or ""),
                "date": str(r.get("date") or ""),
                "sender_addr": str(r.get("sender_addr") or ""),
                "message_id": str(r.get("message_id") or ""),
                "in_reply_to": str(r.get("in_reply_to") or ""),
                "n_recipients": len(recips),
                "has_attachments": bool(r.get("attachments")),
                "body_content_type": str(r.get("body_content_type") or ""),
            }
            rows.append({
                "filename": fn,
                "text": body,
                "subject": subject,
                "expected": "correspondence",
                "expected_subclass": key,
                "label_evidence": str(evidence or ""),
                "split": assign_split(fn),
                "metadata": meta,
            })
            sub_counts[key] += 1
            custodians.add(str(r.get("custodian") or ""))

    print(f"index rows read: {total} (unparseable skipped: {unparseable}, "
          f"empty body+subject dropped: {dropped_empty})")
    print(f"published rows: {len(rows)} | custodians: {len(custodians)}")
    print(f"subclass GT: {dict(sub_counts.most_common())}")

    # schema guard — never ship a partial-null schema to the Hub viewer.
    bad = [i for i, r in enumerate(rows)
           if not (isinstance(r["filename"], str) and r["filename"].strip())
           or not (isinstance(r["expected_subclass"], str) and r["expected_subclass"].strip())
           or r["expected_subclass"] not in SUBCLASS_KEYS
           or r["split"] not in ("train", "test")
           or not isinstance(r["text"], str)]
    if bad:
        parser.error(f"{len(bad)} rows fail the schema guard "
                     f"(first: {bad[0]}) — refusing to publish")
    train_n = sum(1 for r in rows if r["split"] == "train")
    test_n = len(rows) - train_n

    if args.dry_run:
        print(f"\nDry run: would write {len(rows)} rows -> {args.out} "
              f"(train {train_n} / test {test_n}); no network calls.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    local_sha = hashlib.sha256(args.out.read_bytes()).hexdigest()

    manifest = {
        "name": "enron-correspondence",
        "schema_version": 1,
        "rows": len(rows),
        "index_rows_read": total,
        "unparseable_skipped": unparseable,
        "empty_dropped": dropped_empty,
        "custodians": len(custodians),
        "subclass_counts": dict(sub_counts),
        "split_coverage": {"train": train_n, "test": test_n,
                           "rule": "md5(filename) % 10 == 0 -> test (10%); "
                                   "same family rule as docclass-merged"},
        "local_sha256": local_sha,
        "labeler": "Enron-Evaluation-Environment scripts/correspondence_subclasses.py "
                   "(shared 10-key taxonomy, first-match-wins)",
        "sources": {
            "corpus": "CMU Enron Email Dataset — cleaned maildir via "
                      "Enron-Evaluation-Environment build_corpus_index.py",
            "license": "research-use distribution; treat PII accordingly",
        },
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (args.out.parent / "enron_correspondence.manifest.json").write_text(
        json.dumps(manifest, indent=2))
    print(f"\nWrote {len(rows)} rows -> {args.out}\nsha256: {local_sha[:12]}…")

    # ---- publish ----
    token = os.environ.get("HF_TOKEN") or None
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    print(f"HF account: {api.whoami()['name']}")
    api.create_repo(repo_id=args.repo_id, repo_type="dataset",
                    private=args.private, exist_ok=True)

    taxonomy = ", ".join(SUBCLASS_KEYS)
    card_ctx = {
        "rows": len(rows),
        "custodians": len(custodians),
        "taxonomy": taxonomy,
        "built_utc": manifest["built_utc"],
        "parseable": total - unparseable,
        "total": total,
        "labeler_tests": LABELER_TESTS,
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "README.md").write_text(CARD.format(**card_ctx),
                                          encoding="utf-8")
        (tmpdir / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                              encoding="utf-8")
        (tmpdir / STAGED_NAME).write_bytes(args.out.read_bytes())
        print(f"uploading {args.repo_id} "
              f"({args.out.stat().st_size >> 20} MB, {len(rows)} rows) ...")
        api.upload_folder(folder_path=str(tmpdir), repo_id=args.repo_id,
                          repo_type="dataset",
                          commit_message=(f"Cleaned Enron correspondence corpus — "
                                          f"subclass GT + deterministic splits "
                                          f"({len(rows)} rows)"))

    # ---- verify: LFS sha256 vs local ----
    tree = list(api.list_repo_tree(args.repo_id, repo_type="dataset", recursive=True))
    entry = next((f for f in tree if f.path == STAGED_NAME), None)
    lfs = getattr(entry, "lfs", None)
    hub_sha = lfs.sha256 if lfs else None
    result = {
        "repo": f"https://huggingface.co/datasets/{args.repo_id}",
        "rows": len(rows),
        "train": train_n,
        "test": test_n,
        "custodians": len(custodians),
        "subclass_counts": dict(sub_counts),
        "local_sha256": local_sha[:12],
        "hub_lfs_sha256": (hub_sha or "")[:12],
        "verified": bool(hub_sha and hub_sha == local_sha),
    }
    out = OUT_DIR / "PUBLISH_SUMMARY.json"
    out.write_text(json.dumps({"enron_correspondence": result}, indent=2))
    print("\n" + json.dumps(result, indent=1))
    print("VERIFY:", "GREEN" if result["verified"] else "RED — inspect!")
    return 0


def main() -> int:
    return main_with_args(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
