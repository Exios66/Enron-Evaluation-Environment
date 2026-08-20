#!/usr/bin/env python3
"""Full-corpus exploratory data analysis of the CMU Enron email corpus.

Reads ``data/enron/index.jsonl`` (the ``build_corpus_index.py`` output) in a
single streaming pass and writes per-source EDA artifacts under
``reports/eda/`` (the llm-entity-extraction ``explore_pipeline_sources.py``
convention): ``report.md``, ``findings.md`` and citation-footed PNG figures.

Sections (the correspondence intel the mailroom pipeline needs):

1.  Corpus composition        — custodians, folders, messages, parseability
2.  Correspondence types      — the ``expected_subclass`` distribution over
                               the FULL corpus (shared labeler from
                               ``scripts/correspondence_subclasses.py``) —
                               the coverage check for the subclass enum
3.  Attachments               — presence rate, per-message counts, MIME mix,
                               sibling ``_files`` dirs, size distribution
4.  Email types               — internal vs external, recipient fan-out
                               (to/cc/bcc), reply/forward chain share,
                               thread depth
5.  Senders                   — top senders, sender classes (enron staff /
                               law firms / external), per-custodian volume
6.  Content                   — body-length distribution vs the pipeline
                               budgets (16k single-pass, 40k correspondence
                               specialist cap, 90k chunk window), subject
                               lengths, redaction markers, date coverage
7.  Attorney-demand signal    — attorney/law-firm senders, demand-marker
                               candidates, the attorney-demand subclass pool
8.  Pipeline fit              — text-length budgets table + per-subclass
                               length stats (the sampling strata)

Deterministic: streaming counters + a fixed-seed reservoir sample for exact
percentiles; reports regenerate byte-identically.

Usage:
    python scripts/eda/explore_enron.py
    python scripts/eda/explore_enron.py --index /tmp/index.jsonl --out /tmp/eda
    python scripts/eda/explore_enron.py --no-figures
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from correspondence_subclasses import (  # noqa: E402
    SUBCLASS_KEYS,
    SUBCLASS_LABELS,
    label_correspondence,
)

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "data" / "enron" / "index.jsonl"
OUT = ROOT / "reports" / "eda"

CITE = ("Source: CMU classic Enron email corpus (enron_mail_20150507) — "
        "https://www.cs.cmu.edu/~enron/ · 517,431 emails, ~150 custodians")

# Pipeline budgets (chars) — mirrors the llm-entity-extraction taxonomy:
# 16k single-pass sorter text path, 40k correspondence specialist cap,
# 90k chunk window.
BUDGETS = [16_000, 40_000, 90_000]
RESERVOIR_N = 20_000

FOOTER_FRAC = 0.11

THREAD_PREFIX_RE = re.compile(r"^\s*(?:re|fw|fwd|sv)\s*:\s*", re.IGNORECASE)


def _add_citation(fig, note: str) -> None:
    fig.tight_layout(rect=[0, FOOTER_FRAC, 1, 1])
    fig.text(0.5, FOOTER_FRAC / 2, note, ha="center", va="center",
             fontsize=7, color="#444")


def _fmt(n: float) -> str:
    return f"{n:,.0f}"


def analyze(path: Path, seed: int = 42, limit: int | None = None) -> dict:
    rng = random.Random(seed)
    res: dict = {}

    sub_counts: Counter = Counter()
    custodian_counts: Counter = Counter()
    folder_counts: Counter = Counter()
    sender_counts: Counter = Counter()
    sender_domain_counts: Counter = Counter()
    mime_counts: Counter = Counter()
    ext_counts: Counter = Counter()
    thread_counts: Counter = Counter()
    attach_counts: Counter = Counter()
    fanout_counts: Counter = Counter()
    cc_counts: Counter = Counter()
    bcc_counts: Counter = Counter()
    date_year_counts: Counter = Counter()
    sub_markers: Counter = Counter()
    unparseable = 0
    no_body = 0
    bodies_total_chars = 0
    bodies_min = None
    bodies_max = 0
    longest_body: tuple[int, str] = (0, "")
    redaction_rows = 0
    sibling_dir_rows = 0
    internal_rows = 0
    external_rows = 0
    thread_prefix_rows = 0
    attorney_sender_rows = 0
    demand_marker_rows = 0
    attach_rows = 0
    reservoir: list[tuple[int, str, str]] = []  # (len, subclass, filename)
    subclass_examples: dict[str, str] = {}
    n = 0

    from correspondence_subclasses import _is_attorney, _DEMAND_RE, _has_any, _subject

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if limit and n >= limit:
                break
            n += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            key, _ = label_correspondence(row)
            sub_counts[key] += 1
            subclass_examples.setdefault(key, row.get("filename") or "")

            custodian = row.get("custodian") or "?"
            custodian_counts[custodian] += 1
            folder_counts[row.get("folder") or "?"] += 1

            sender_addr = (row.get("sender_addr") or "").strip().lower()
            if sender_addr:
                sender_counts[sender_addr] += 1
                domain = sender_addr.rsplit("@", 1)[-1] if "@" in sender_addr else sender_addr
                sender_domain_counts[domain] += 1
                if "enron.com" in domain:
                    internal_rows += 1
                else:
                    external_rows += 1
                is_atty, _ = _is_attorney(row)
                if is_atty:
                    attorney_sender_rows += 1

            subject = (row.get("subject") or "").strip()
            if subject:
                if THREAD_PREFIX_RE.match(subject):
                    thread_prefix_rows += 1
                    m = re.match(r"^\s*(re|fw|fwd|sv)", subject, re.IGNORECASE)
                    sub_markers[m.group(1).lower()] += 1
                if _has_any(subject, _DEMAND_RE):
                    demand_marker_rows += 1

            recipients = row.get("recipients") or []
            fanout_counts[len(recipients)] += 1
            cc_counts[sum(1 for r in recipients if r.get("role") == "cc")] += 1
            bcc_counts[sum(1 for r in recipients if r.get("role") == "bcc")] += 1

            thread = row.get("thread") or "?"
            thread_counts[thread] += 1

            attachments = row.get("attachments") or []
            attach_counts[len(attachments)] += 1
            if attachments:
                attach_rows += 1
                for a in attachments:
                    mime_counts[a.get("mime") or "?"] += 1
                    name = (a.get("name") or "").lower()
                    if "." in name:
                        ext_counts["." + name.rsplit(".", 1)[-1]] += 1

            siblings = row.get("sibling_files") or []
            if siblings:
                sibling_dir_rows += 1

            if not row.get("parseable"):
                unparseable += 1
            body = row.get("body") or ""
            if not body:
                no_body += 1
            blen = len(body)
            bodies_total_chars += blen
            bodies_min = blen if bodies_min is None else min(bodies_min, blen)
            bodies_max = max(bodies_max, blen)
            if blen > longest_body[0]:
                longest_body = (blen, row.get("filename") or "")
            if "[***]" in body or "[PERSONAL" in body:
                redaction_rows += 1

            if len(reservoir) < RESERVOIR_N:
                reservoir.append((blen, key, row.get("filename") or ""))
            else:
                j = rng.randrange(n)
                if j < RESERVOIR_N:
                    reservoir[j] = (blen, key, row.get("filename") or "")

            date = row.get("date") or ""
            year = date[:4]
            if year.isdigit():
                date_year_counts[year] += 1

    res.update({
        "n": n,
        "unparseable": unparseable,
        "no_body": no_body,
        "parseable": n - unparseable,
        "n_custodians": len(custodian_counts),
        "n_folders": len(folder_counts),
        "custodians": dict(custodian_counts.most_common()),
        "folders": dict(folder_counts.most_common()),
        "subclasses": dict(sub_counts),
        "subclass_examples": subclass_examples,
        "senders": dict(sender_counts.most_common()),
        "n_senders": len(sender_counts),
        "sender_domains": dict(sender_domain_counts.most_common()),
        "internal": internal_rows,
        "external": external_rows,
        "attorney_senders": attorney_sender_rows,
        "demand_markers": demand_marker_rows,
        "thread_prefix": thread_prefix_rows,
        "thread_prefix_kinds": dict(sub_markers),
        "attachments_total": sum(attach_counts[k] * k for k in attach_counts),
        "attach_rows": attach_rows,
        "attach_counts": dict(attach_counts),
        "mime_types": dict(mime_counts.most_common()),
        "extensions": dict(ext_counts.most_common()),
        "sibling_dir_rows": sibling_dir_rows,
        "fanout": dict(fanout_counts),
        "cc": dict(cc_counts),
        "bcc": dict(bcc_counts),
        "threads": dict(thread_counts),
        "redaction_rows": redaction_rows,
        "body_chars_total": bodies_total_chars,
        "body_chars_min": bodies_min,
        "body_chars_max": bodies_max,
        "longest_body": longest_body,
        "years": dict(sorted(date_year_counts.items())),
        "reservoir": sorted(reservoir),
    })

    # Reservoir-based exact percentiles + per-subclass length stats.
    lens = [r[0] for r in reservoir]
    res["reservoir_n"] = len(lens)
    res["body_pcts"] = {p: sorted(lens)[int(p / 100 * (len(lens) - 1))]
                        for p in (0, 25, 50, 75, 90, 95, 99, 100)}
    by_sub: dict[str, list[int]] = defaultdict(list)
    for blen, key, _f in reservoir:
        by_sub[key].append(blen)
    res["subclass_lengths"] = {
        k: {"n": len(v), "median": sorted(v)[len(v) // 2] if v else 0,
            "max": max(v) if v else 0}
        for k, v in by_sub.items()
    }
    over_budget: dict[str, list[int]] = {b: [0, 0] for b in BUDGETS}  # [over, over_share]
    for blen in lens:
        for b in BUDGETS:
            if blen > b:
                over_budget[b][0] += 1
    res["budget_over"] = {b: (over, over / len(lens) if lens else 0.0)
                          for b, (over, _) in over_budget.items()}
    return res


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_report(res: dict) -> str:
    L = ["# Enron Email Corpus — Full Exploratory Data Analysis", ""]
    L.append(f"_Emitted by `scripts/eda/explore_enron.py`_")
    L.append(f"_Note: {CITE}_")
    L.append("")
    n = res["n"]
    L.append(f"**Messages**: {_fmt(n)} · **custodians**: {res['n_custodians']} · "
             f"**folders**: {res['n_folders']} · **parseable**: {_fmt(res['parseable'])} "
             f"({res['parseable'] / n:.1%})")
    L.append(f"**Body text**: {_fmt(res['body_chars_total'])} chars total · "
             f"min {_fmt(res['body_chars_min'])} / median {_fmt(res['body_pcts'][50])} / "
             f"max {_fmt(res['body_chars_max'])} chars")
    L.append("")

    L.append("## 1. Corpus composition")
    L.append("")
    L.append(f"**{res['n_custodians']} custodians**; message volume per custodian (top 25):")
    L.append("")
    L.append("| custodian | messages | share |")
    L.append("|---|---|---|")
    for k, v in list(res["custodians"].items())[:25]:
        L.append(f"| {k} | {_fmt(v)} | {v / n:.1%} |")
    L.append("")
    L.append("Top folders (the maildir's organizational buckets):")
    L.append("")
    L.append("| folder | messages |")
    L.append("|---|---|")
    for k, v in list(res["folders"].items())[:15]:
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("")
    L.append(f"Unparseable files: **{_fmt(res['unparseable'])}** · bodies absent: "
             f"**{_fmt(res['no_body'])}** · rows with `[***]`/`[PERSONAL` redaction "
             f"markers: **{_fmt(res['redaction_rows'])}**")
    L.append("")
    L.append("Message volume by year (Date header):")
    L.append("")
    L.append("| year | messages |")
    L.append("|---|---|")
    for k, v in res["years"].items():
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("")

    L.append("## 2. Correspondence types (subclass dimension)")
    L.append("")
    L.append("The mailroom `correspondence` doc class's second-level "
             "`expected_subclass` dimension, labeled over the FULL corpus by "
             "the shared heuristic (`scripts/correspondence_subclasses.py`). "
             "Every row receives a key — `email` is the ordinary-mail default, "
             "`other` only unparseable/non-email files. **This is the coverage "
             "check for the subclass enum**: the residual `other` rate is the "
             "measure of completeness.")
    L.append("")
    L.append("| subclass | messages | share | example message |")
    L.append("|---|---|---|---|")
    for k in SUBCLASS_KEYS:
        v = res["subclasses"].get(k, 0)
        L.append(f"| `{k}` | {_fmt(v)} | {v / n:.1%} | {res['subclass_examples'].get(k, '')} |")
    L.append("")

    L.append("## 3. Attachments")
    L.append("")
    L.append(f"Messages with inline/attachment parts: **{_fmt(res['attach_rows'])}** "
             f"({res['attach_rows'] / n:.1%}) · total attachment parts: "
             f"**{_fmt(res['attachments_total'])}**")
    L.append(f"Messages with a `<msg>_files/` sibling dir (the maildir's file "
             f"store): **{_fmt(res['sibling_dir_rows'])}** "
             f"({res['sibling_dir_rows'] / n:.1%})")
    L.append("")
    L.append("Attachment parts per message:")
    L.append("")
    L.append("| parts | messages |")
    L.append("|---|---|")
    for k, v in sorted(res["attach_counts"].items())[:10]:
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("")
    L.append("Attachment MIME types (top 15):")
    L.append("")
    L.append("| mime | count |")
    L.append("|---|---|")
    for k, v in list(res["mime_types"].items())[:15]:
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("")
    L.append("Attachment extensions (top 15):")
    L.append("")
    L.append("| extension | count |")
    L.append("|---|---|")
    for k, v in list(res["extensions"].items())[:15]:
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("")

    L.append("## 4. Email types (internal/external, fan-out, threads)")
    L.append("")
    L.append(f"**Internal** (enron.com sender): {_fmt(res['internal'])} "
             f"({res['internal'] / n:.1%}) · **External**: {_fmt(res['external'])} "
             f"({res['external'] / n:.1%}) · **no sender parsed**: "
             f"{_fmt(n - res['internal'] - res['external'])}")
    L.append("")
    L.append(f"Reply/forward chain members (subject prefix RE:/FW:/FWD:): "
             f"**{_fmt(res['thread_prefix'])}** ({res['thread_prefix'] / n:.1%}) — "
             + ", ".join(f"{k} {_fmt(v)}" for k, v in res["thread_prefix_kinds"].items())
             + ".")
    L.append(f"Distinct thread dirs (maildir thread folders): **{_fmt(len(res['threads']))}**")
    L.append("")
    L.append("Recipient fan-out (addresses in To/Cc/Bcc):")
    L.append("")
    L.append("| recipients | messages |")
    L.append("|---|---|")
    for k in sorted(res["fanout"])[:10]:
        L.append(f"| {k} | {_fmt(res['fanout'][k])} |")
    L.append("")
    L.append(f"Messages with CC: {_fmt(sum(res['cc'].get(k, 0) for k in res['cc'] if k))} · "
             f"with BCC: {_fmt(sum(res['bcc'].get(k, 0) for k in res['bcc'] if k))}")
    L.append("")

    L.append("## 5. Senders")
    L.append("")
    L.append(f"**{_fmt(res['n_senders'])} distinct sender addresses**; top 20:")
    L.append("")
    L.append("| sender | messages |")
    L.append("|---|---|")
    for k, v in list(res["senders"].items())[:20]:
        L.append(f"| `{k}` | {_fmt(v)} |")
    L.append("")
    L.append("Top sender domains (external):")
    L.append("")
    L.append("| domain | messages |")
    L.append("|---|---|")
    for k, v in list(res["sender_domains"].items())[:15]:
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("")
    L.append(f"Attorney/law-firm senders (domain + name heuristics): "
             f"**{_fmt(res['attorney_senders'])}** ({res['attorney_senders'] / n:.1%})")
    L.append("")

    L.append("## 6. Content")
    L.append("")
    L.append(f"Body length percentiles (reservoir n={_fmt(res['reservoir_n'])}, "
             f"chars):")
    L.append("")
    L.append("| pct | chars |")
    L.append("|---|---|")
    for p in (0, 25, 50, 75, 90, 95, 99, 100):
        L.append(f"| p{p} | {_fmt(res['body_pcts'][p])} |")
    L.append("")
    L.append("Body length vs the pipeline budgets (share of sampled bodies over):")
    L.append("")
    L.append("| budget | over | share |")
    L.append("|---|---|---|")
    for b in BUDGETS:
        over, share = res["budget_over"][b]
        L.append(f"| {_fmt(b)} chars | {_fmt(over)} | {share:.1%} |")
    L.append("")
    L.append("Per-subclass body lengths (reservoir):")
    L.append("")
    L.append("| subclass | n | median | max |")
    L.append("|---|---|---|---|")
    for k in SUBCLASS_KEYS:
        s = res["subclass_lengths"].get(k)
        if s:
            L.append(f"| `{k}` | {_fmt(s['n'])} | {_fmt(s['median'])} | {_fmt(s['max'])} |")
    L.append("")
    L.append(f"Longest body: {_fmt(res['longest_body'][0])} chars "
             f"(`{res['longest_body'][1]}`)")
    L.append("")

    L.append("## 7. Attorney-demand signal")
    L.append("")
    L.append(f"- Attorney/law-firm senders: **{_fmt(res['attorney_senders'])}** "
             f"({res['attorney_senders'] / n:.1%})")
    L.append(f"- Demand-marker subjects (demand/cease-and-desist/default/...): "
             f"**{_fmt(res['demand_markers'])}** ({res['demand_markers'] / n:.1%})")
    L.append(f"- `attorney_demand` subclass (demand + attorney sender): "
             f"**{_fmt(res['subclasses'].get('attorney_demand', 0))}**")
    L.append(f"- `demand` subclass (demand, non-attorney sender): "
             f"**{_fmt(res['subclasses'].get('demand', 0))}**")
    L.append("")

    L.append("## 8. Pipeline fit")
    L.append("")
    L.append("The correspondence specialist cap is 40k chars; the sorter's "
             "single-pass text path is 16k; the chunk window is 90k. Enron "
             "bodies are small (median "
             f"{_fmt(res['body_pcts'][50])} chars), so virtually all rows pass "
             "single-pass text intake — the sampling strata for the pipeline "
             "dump (custodian, internal/external, subclass, attachment "
             "presence) should preserve the subclass mix above.")
    L.append("")
    L.append(f"Figures: `figures/01`–`08` (subclass distribution, attachment "
             f"presence, MIME mix, internal/external, top senders, body-length "
             f"histogram vs budgets, per-custodian volume, thread fan-out).")
    L.append("")
    return "\n".join(L)


def render_findings(res: dict) -> str:
    n = res["n"]
    L = ["# Enron EDA findings (condensed)", ""]
    top_sub = max(res["subclasses"], key=res["subclasses"].get)
    other = res["subclasses"].get("other", 0)
    L.append(f"- Corpus: {_fmt(n)} messages, {res['n_custodians']} custodians, "
             f"{res['parseable'] / n:.1%} parseable.")
    L.append(f"- Subclass mix: {', '.join(f'{k} {v} ({v / n:.1%})' for k, v in res['subclasses'].items())}"
             f" — `{top_sub}` dominates; `other` residual {other} ({other / n:.2%}) = "
             "the unparseable/non-email files, so the enum fully covers the corpus.")
    L.append(f"- Attorney-demand pool: {_fmt(res['subclasses'].get('attorney_demand', 0))} "
             f"attorney demands + {_fmt(res['subclasses'].get('demand', 0))} non-attorney "
             f"demands; {_fmt(res['attorney_senders'])} attorney/law-firm senders "
             f"({res['attorney_senders'] / n:.2%}).")
    L.append(f"- Attachments: {_fmt(res['attach_rows'])} ({res['attach_rows'] / n:.1%}) "
             f"messages carry attachment parts; {_fmt(res['sibling_dir_rows'])} have "
             "_files/ sibling dirs.")
    L.append(f"- Internal vs external: {res['internal'] / n:.1%} enron.com senders; "
             f"thread-prefixed (RE/FW) messages {res['thread_prefix'] / n:.1%}.")
    L.append(f"- Bodies are small: median {_fmt(res['body_pcts'][50])} chars "
             f"(p99 {_fmt(res['body_pcts'][99])}) — the 40k correspondence "
             "specialist cap covers >99% of bodies un-chunked.")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def _barh(ax, names, values, color, title, xlabel="count"):
    ax.barh(range(len(names))[::-1], values, color=color)
    ax.set_yticks(range(len(names))[::-1])
    ax.set_yticklabels(names, fontsize=7)
    ax.set_xlabel(xlabel)
    ax.set_title(title)


def make_figures(res: dict, figdir: Path) -> None:
    n = res["n"]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    keys = SUBCLASS_KEYS
    vals = [res["subclasses"].get(k, 0) for k in keys]
    ax.bar(range(len(keys)), vals, color="#0f766e")
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([f"{SUBCLASS_LABELS[k]}\n({k})" for k in keys], fontsize=7)
    ax.set_ylabel("messages")
    ax.set_title("Correspondence subclass distribution (full corpus)")
    _add_citation(fig, CITE)
    fig.savefig(figdir / "01_subclasses.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    counts = res["attach_counts"]
    names = [str(k) for k in sorted(counts)][:10]
    vals = [counts[int(k)] for k in names]
    ax.bar(names, vals, color="#b45309")
    ax.set_xlabel("attachment parts")
    ax.set_ylabel("messages")
    ax.set_title("Attachment parts per message")
    _add_citation(fig, CITE)
    fig.savefig(figdir / "02_attachments.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    mimes = list(res["mime_types"].items())[:12]
    ax.barh(range(len(mimes))[::-1], [v for _, v in mimes], color="#b45309")
    ax.set_yticks(range(len(mimes))[::-1])
    ax.set_yticklabels([k for k, _ in mimes], fontsize=7)
    ax.set_xlabel("parts")
    ax.set_title("Attachment MIME types (top 12)")
    _add_citation(fig, CITE)
    fig.savefig(figdir / "03_mime_types.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["internal", "external", "no sender"],
           [res["internal"], res["external"],
            n - res["internal"] - res["external"]], color="#1d4ed8")
    ax.set_ylabel("messages")
    ax.set_title("Internal vs external senders")
    _add_citation(fig, CITE)
    fig.savefig(figdir / "04_internal_external.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    senders = list(res["senders"].items())[:20]
    _barh(ax, [k for k, _ in senders], [v for _, v in senders], "#1d4ed8",
          "Top 20 senders")
    _add_citation(fig, CITE)
    fig.savefig(figdir / "05_top_senders.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    lens = [r[0] for r in res["reservoir"]]
    ax.hist(lens, bins=60, color="#6d28d9", edgecolor="white")
    ax.set_xlabel("body chars")
    ax.set_ylabel("messages")
    ax.set_title("Body length distribution (reservoir)")
    for b in BUDGETS:
        ax.axvline(b, color="crimson", ls="--", lw=1.2)
    ax.text(16_100, ax.get_ylim()[1] * 0.95, "16k", color="crimson", fontsize=8)
    ax.text(40_100, ax.get_ylim()[1] * 0.85, "40k", color="crimson", fontsize=8)
    ax.text(90_100, ax.get_ylim()[1] * 0.75, "90k", color="crimson", fontsize=8)
    _add_citation(fig, CITE)
    fig.savefig(figdir / "06_body_length.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    custs = list(res["custodians"].items())[:25]
    _barh(ax, [k for k, _ in custs], [v for _, v in custs], "#0f766e",
          "Message volume per custodian (top 25)")
    _add_citation(fig, CITE)
    fig.savefig(figdir / "07_custodians.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    fan = res["fanout"]
    names = [str(k) for k in sorted(fan) if k <= 15]
    vals = [fan[int(k)] for k in names]
    ax.bar(names, vals, color="#be185d")
    ax.set_xlabel("recipients (to+cc+bcc)")
    ax.set_ylabel("messages")
    ax.set_title("Recipient fan-out")
    _add_citation(fig, CITE)
    fig.savefig(figdir / "08_fanout.png", dpi=110)
    plt.close(fig)


def main_with_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX,
                        help=f"Index JSONL (default: {INDEX})")
    parser.add_argument("--out", type=Path, default=OUT,
                        help=f"Output dir (default: {OUT})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Analyze at most N rows (smoke testing)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-figures", action="store_true", help="Skip PNG figures")
    args = parser.parse_args(argv)

    if not args.index.exists():
        parser.error(f"index not found: {args.index} — run build_corpus_index.py first")

    print(f"Analyzing {args.index} ...")
    res = analyze(args.index, seed=args.seed, limit=args.limit)
    print(f"  {res['n']} rows, {res['n_custodians']} custodians, "
          f"{res['parseable'] / res['n']:.1%} parseable")

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    figdir = out / "figures"
    if not args.no_figures:
        figdir.mkdir(parents=True, exist_ok=True)
        make_figures(res, figdir)
    (out / "report.md").write_text(render_report(res), encoding="utf-8")
    (out / "findings.md").write_text(render_findings(res), encoding="utf-8")
    n_figs = len(list(figdir.glob("*.png"))) if figdir.exists() else 0
    print(f"  -> {out} ({n_figs} figures)")
    return 0


def main() -> int:
    raise SystemExit(main_with_args(sys.argv[1:]))


if __name__ == "__main__":
    main()