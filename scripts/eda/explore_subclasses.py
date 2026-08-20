#!/usr/bin/env python3
"""Exploratory pass: discover the natural correspondence-subclass clusters.

Reads ``data/enron/index.jsonl`` in one streaming pass and reports the
evidence that drives the subclass enum in ``scripts/correspondence_subclasses.py``
— subject-prefix clusters, body markers, sender classes, MIME shapes, and the
contents of any rows the labeler routes to ``other``. This is the artifact
that proves the enum fully covers the corpus.

Usage:
    python scripts/eda/explore_subclasses.py
    python scripts/eda/explore_subclasses.py --index /tmp/index.jsonl --limit 50000
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from correspondence_subclasses import (  # noqa: E402
    SUBCLASS_KEYS,
    label_correspondence,
)

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "data" / "enron" / "index.jsonl"
OUT = ROOT / "reports" / "eda"

SUBJECT_PREFIX_RE = re.compile(r"^([A-Z][A-Z0-9]{1,5}[\s:]+)")
BODY_OPENERS = [
    "MEMORANDUM", "INTEROFFICE", "INTER-OFFICE", "TO:", "FROM:", "DATE:",
    "NOTICE", "NOTICE OF", "LITIGATION HOLD", "DEMAND", "DEMAND FOR",
    "FOR IMMEDIATE RELEASE", "FOR RELEASE", "DEAR ", "THIS IS A VOICE MAIL",
    "VOICE MAIL", "MEETING REQUEST", "MEETING INVITATION", "ATTACHMENT",
]
RE_PREFIX_RE = re.compile(r"^\s*(?:re|fwd|fw|sv)\s*:\s*", re.IGNORECASE)
FWD_PREFIX_RE = re.compile(r"^\s*(?:fwd|fw)\s*:\s*", re.IGNORECASE)
URGENT_RE = re.compile(r"^\s*urgent", re.IGNORECASE)
ATTORNEY_NAME_RE = re.compile(r"\b(?:esq|attorney|counsel|lawyer|partner|j\.?\s?d\.?|atty)\b", re.IGNORECASE)


def main_with_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    if not args.index.exists():
        parser.error(f"index not found: {args.index}")

    subject_prefixes: Counter = Counter()
    body_opener_counts: Counter = Counter()
    domain_counts: Counter = Counter()
    attorney_name_counts: Counter = Counter()
    mime_counts: Counter = Counter()
    content_type_counts: Counter = Counter()
    other_examples: list[str] = []
    subclass_counts: Counter = Counter()
    n = 0
    with args.index.open(encoding="utf-8") as fh:
        for line in fh:
            if args.limit and n >= args.limit:
                break
            n += 1
            row = __import__("json").loads(line)
            subclass, _ = label_correspondence(row)
            subclass_counts[subclass] += 1

            subject = (row.get("subject") or "").strip()
            m = SUBJECT_PREFIX_RE.match(subject)
            if m:
                subject_prefixes[m.group(1).strip(": ").upper()] += 1
            if RE_PREFIX_RE.match(subject):
                subject_prefixes["RE:"] += 1
            if FWD_PREFIX_RE.match(subject):
                subject_prefixes["FWD:"] += 1
            if URGENT_RE.match(subject):
                subject_prefixes["URGENT"] += 1

            body = (row.get("body") or "")[:800]
            body_up = " ".join(body.split()).upper()
            for opener in BODY_OPENERS:
                if opener in body_up:
                    body_opener_counts[opener] += 1

            addr = (row.get("sender_addr") or "").strip().lower()
            if addr:
                domain = addr.rsplit("@", 1)[-1] if "@" in addr else addr
                domain_counts[domain] += 1
            name = (row.get("sender") or "").strip()
            if ATTORNEY_NAME_RE.search(name):
                attorney_name_counts[name] += 1

            for a in row.get("attachments") or []:
                mime_counts[a.get("mime") or "?"] += 1
            ct = row.get("body_content_type") or "none"
            content_type_counts[ct] += 1

            if subclass == "other":
                other_examples.append(row.get("filename") or "")

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    L = ["# Correspondence-subclass discovery evidence", ""]
    L.append(f"_Emitted by `scripts/eda/explore_subclasses.py`_")
    L.append(f"_Corpus: {n} messages from `data/enron/index.jsonl`_")
    L.append("")
    L.append("This pass surfaces the natural clusters that the subclass enum "
             "(`scripts/correspondence_subclasses.py`) was built to cover.")
    L.append("")

    L.append("## Subclass distribution (full corpus)")
    L.append("")
    L.append("| subclass | messages | share |")
    L.append("|---|---|---|")
    for k in SUBCLASS_KEYS:
        v = subclass_counts.get(k, 0)
        L.append(f"| `{k}` | {v} | {v / n:.1%} |")
    L.append("")

    L.append("## Subject-prefix clusters")
    L.append("")
    L.append("| prefix | messages |")
    L.append("|---|---|")
    for k, v in subject_prefixes.most_common(20):
        L.append(f"| {k} | {v} |")
    L.append("")

    L.append("## Body markers (first 800 chars)")
    L.append("")
    L.append("| marker | messages |")
    L.append("|---|---|")
    for k, v in body_opener_counts.most_common(20):
        L.append(f"| {k} | {v} |")
    L.append("")

    L.append("## Sender classes")
    L.append("")
    L.append(f"- Attorney markers in sender display names: "
             f"**{sum(attorney_name_counts.values())}** messages")
    L.append("")
    L.append("| sender | messages |")
    L.append("|---|---|")
    for k, v in attorney_name_counts.most_common(15):
        L.append(f"| {k} | {v} |")
    L.append("")
    L.append("Top sender domains (external):")
    L.append("")
    L.append("| domain | messages |")
    L.append("|---|---|")
    for k, v in domain_counts.most_common(25):
        L.append(f"| {k} | {v} |")
    L.append("")

    L.append("## MIME / content shapes")
    L.append("")
    L.append("| body content type | messages |")
    L.append("|---|---|")
    for k, v in content_type_counts.most_common():
        L.append(f"| {k} | {v} |")
    L.append("")
    L.append("Attachment MIME types:")
    L.append("")
    L.append("| mime | count |")
    L.append("|---|---|")
    for k, v in mime_counts.most_common(15):
        L.append(f"| {k} | {v} |")
    L.append("")

    L.append("## `other` residual (the coverage measure)")
    L.append("")
    L.append(f"Rows routed to `other`: **{subclass_counts.get('other', 0)}** "
             f"({subclass_counts.get('other', 0) / n:.2%})")
    if other_examples:
        L.append("Examples:")
        L.append("")
        for f in other_examples[:20]:
            L.append(f"- `{f}`")
    else:
        L.append("None — every parseable row maps to a real subclass.")
    L.append("")

    (out / "subclasses_discovery.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Wrote {out / 'subclasses_discovery.md'}")
    print(f"Subclasses: {dict(subclass_counts)}")
    print(f"Other residual: {subclass_counts.get('other', 0)} ({subclass_counts.get('other', 0) / n:.2%})")
    return 0


def main() -> int:
    raise SystemExit(main_with_args(sys.argv[1:]))


if __name__ == "__main__":
    main()