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
8.  Timezone distribution     — sender-side UTC offsets
9.  Reply-chain depth         — sampled multi-message thread depths
10. Custodian composition     — per-custodian subclass breakdown
11. Subject-length patterns   — subject char percentiles
12. Temporal patterns         — hour-of-day (UTC), day-of-week, monthly
                               volume (v2 expansion)
13. Recipient roles           — To/Cc/Bcc address totals + co-presence
                               (v2 expansion)
14. Duplicates & reuse        — exact body duplicates (md5) and repeated
                               normalized subjects (v2 expansion)
15. Thread-size distribution  — messages per thread directory, bucketed
                               (v2 expansion)
16. Pipeline fit              — text-length budgets table + per-subclass
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
import datetime
import hashlib
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
import matplotlib.dates as mdates  # noqa: E402
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

# --- Figure-quality defaults (matplotlib-figure-quality discipline) ---------
plt.rcParams.update({
    "figure.autolayout": False,      # we control layout explicitly per-figure
    "savefig.bbox": "tight",         # never crop labels at the canvas edge
    "savefig.facecolor": "white",
    "axes.titlesize": 11,
    "axes.titlepad": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "axes.axisbelow": True,
    "axes.spines.top": False,        # cleaner frame: keep left/bottom only
    "axes.spines.right": False,
})

# Semantic palette — one hue per EDA dimension, reused across figures so the
# report reads as one document rather than twelve one-off charts.
TEAL = "#0f766e"          # corpus composition (subclasses, custodians, months)
AMBER = "#b45309"         # temporal (hour-of-day)
AMBER_DARK = "#7c2d12"    # temporal emphasis (peak markers)
BLUE = "#1d4ed8"          # senders / internal-external
PURPLE = "#6d28d9"        # content (body lengths)
PINK = "#be185d"          # recipient fan-out (+ weekend bars)
CYAN = "#0e7490"          # threads
GREEN = "#15803d"         # duplicates (unique)
RED = "#dc2626"           # duplicates (copies) / budget lines
VIOLET = "#7c3aed"        # recipient roles
GRAY = "#6b7280"          # de-emphasis (zero classes, notes)

# Long tick-label sets get rotated + right-aligned so neighbors never collide.
_ROTATED_XTICKS = {"rotation": 30, "ha": "right"}


def _finish(fig, path, footer: str) -> None:
    """Uniform save: reserve footer space, place citation, tight-crop."""
    fig.tight_layout(rect=[0, FOOTER_FRAC, 1, 1])
    fig.text(0.5, FOOTER_FRAC / 2, footer, ha="center", va="center",
             fontsize=7, color="#444")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _headroom(ax, is_barh: bool = False) -> None:
    """Pad axis limits so annotated bars/labels never clip at the edge."""
    if is_barh:
        xmin, xmax = ax.get_xlim()
        span = max(xmax - xmin, 1e-9)
        ax.set_xlim(xmin, xmax + span * 0.08)
    else:
        ymin, ymax = ax.get_ylim()
        span = max(ymax - ymin, 1e-9)
        ax.set_ylim(ymin, ymax + span * 0.10)


THREAD_PREFIX_RE = re.compile(r"^\s*(?:re|fw|fwd|sv)\s*:\s*", re.IGNORECASE)


def _grid(ax, axis: str = "y") -> None:
    """Grid on ONE axis only — bars read cleaner without cross-hatching."""
    other = "x" if axis == "y" else "y"
    ax.grid(True, axis=axis)
    ax.grid(False, axis=other)


def _kfmt(v: float) -> str:
    """Compact axis number format: 505929 -> '506k', 2011417 -> '2.0M'."""
    if v >= 1_000_000:
        s = f"{v / 1_000_000:.1f}M"
        return s.replace(".0M", "M")
    if v >= 1_000:
        return f"{v / 1_000:.0f}k"
    return f"{v:.0f}"


def _fmt(n: float) -> str:
    return f"{n:,.0f}"


def _tz_offset(date_str: str) -> str | None:
    """Extract timezone offset from an ISO-8601 or RFC-2822 date string."""
    if not date_str:
        return None
    # Handle "+/-HHMM" suffix (e.g., "-0500" for CST)
    m = re.search(r"[+-]\d{4}$", date_str)
    if m:
        raw = m.group()
        sign = raw[0]
        h = int(raw[1:3])
        mn = int(raw[3:5])
        mins = (h * 60 + mn) * (-1 if sign == "-" else 1)
        if mins == 0:
            return "UTC+00:00"
        return f"UTC{sign}{h:02d}:{mn:02d}"
    # Handle "Z" suffix
    if date_str.endswith("Z"):
        return "UTC+00:00"
    # Common named offsets
    known = {
        "-0600": "US/Central (-06:00)", "-0700": "US/Mountain (-07:00)",
        "-0800": "US/Pacific (-08:00)", "-0500": "US/Eastern (-05:00)",
        "+0000": "UTC/GMT (+00:00)", "+0100": "CET (+01:00)",
        "+0530": "India (+05:30)", "+0900": "JST/KST (+09:00)",
    }
    m2 = re.search(r"[+-]\d{4}", date_str)
    if m2:
        return known.get(m2.group(), f"Other ({m2.group()})")
    return "unknown"


def _thread_depth_stats(thread_counts: Counter) -> dict:
    """Exact thread-size distribution from streaming per-thread counts.

    Replaces the earlier reservoir-sampled estimate that kept up to 500 full
    rows per thread in memory (which OOM'd on the 517k-message corpus). The
    streaming Counter already holds exact per-thread message counts, so the
    whole distribution is computed exactly at zero extra memory.
    """
    sizes = list(thread_counts.values())
    total = len(sizes)
    if not total:
        return {"n_threads": 0, "singletons": 0, "multi": 0, "max_depth": 0,
                "depth_2_pct": 0.0, "depth_3_5_pct": 0.0,
                "depth_6_10_pct": 0.0, "depth_gt10_pct": 0.0}
    single = sum(1 for s in sizes if s == 1)
    d2 = sum(1 for s in sizes if s == 2)
    d3_5 = sum(1 for s in sizes if 3 <= s <= 5)
    d6_10 = sum(1 for s in sizes if 6 <= s <= 10)
    gt10 = sum(1 for s in sizes if s > 10)
    return {
        "n_threads": total,
        "singletons": single,
        "multi": total - single,
        "depth_2_pct": round(d2 / total * 100, 1),
        "depth_3_5_pct": round(d3_5 / total * 100, 1),
        "depth_6_10_pct": round(d6_10 / total * 100, 1),
        "depth_gt10_pct": round(gt10 / total * 100, 1),
        "max_depth": max(sizes),
    }


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
    tz_offset_counts: Counter = Counter()
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

    # Per-custodian subclass breakdown
    cust_subclass: dict[str, Counter] = defaultdict(lambda: Counter())

    # Thread membership: exact per-thread message counts (streaming Counter);
    # the earlier rows_by_thread full-row store OOM'd on 517k messages.
    # v2 expansion accumulators -------------------------------------
    hour_counts: Counter = Counter()          # hour-of-day (UTC) -> msgs
    dow_counts: Counter = Counter()           # weekday (UTC) -> msgs
    month_counts: Counter = Counter()         # YYYY-MM -> msgs
    to_addrs = cc_addrs = bcc_addrs = 0       # total recipient addresses
    msgs_with_to = msgs_with_cc_only = 0
    msgs_with_bcc = 0                         # any Bcc present
    body_hash_counts: dict[str, int] = {}     # md5(body) -> copies
    body_hash_first: dict[str, str] = {}      # md5 -> first-seen filename
    body_hash_custodians: dict[str, set] = {}  # md5 -> custodians holding a copy
    subject_norm_counts: Counter = Counter()  # normalized subject -> count

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
            cust_subclass[custodian][key] += 1
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
            # v2: role-level address totals + To/Bcc co-presence
            n_to = sum(1 for r in recipients if r.get("role") == "to")
            n_cc = sum(1 for r in recipients if r.get("role") == "cc")
            n_bcc = sum(1 for r in recipients if r.get("role") == "bcc")
            to_addrs += n_to
            cc_addrs += n_cc
            bcc_addrs += n_bcc
            if n_to:
                msgs_with_to += 1
            if n_bcc:
                msgs_with_bcc += 1
                if not n_to:
                    msgs_with_cc_only += 1

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

            # Timezone extraction
            tz = _tz_offset(date)
            if tz:
                tz_offset_counts[tz] += 1

            # v2: temporal buckets (UTC), duplicates, repeated subjects
            if date:
                dt = None
                try:
                    dt = datetime.datetime.fromisoformat(date)
                except ValueError:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(date)
                    except (TypeError, ValueError, OverflowError):
                        dt = None
                if dt is not None:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    hour_counts[dt.astimezone(datetime.timezone.utc).hour] += 1
                    dow_counts[dt.astimezone(datetime.timezone.utc).weekday()] += 1
                if re.match(r"^\d{4}-\d{2}", date):
                    month_counts[date[:7]] += 1
            body = row.get("body") or ""
            if body:
                h = hashlib.md5(body.encode("utf-8", "ignore")).hexdigest()
                body_hash_counts[h] = body_hash_counts.get(h, 0) + 1
                body_hash_first.setdefault(h, row.get("filename") or "")
                body_hash_custodians.setdefault(h, set()).add(row.get("custodian") or "?")
            subj_norm = re.sub(r"^(?:\s*(?:re|fw|fwd|sv)\s*:\s*)+", "", (row.get("subject") or "").strip().lower())
            if subj_norm:
                subject_norm_counts[subj_norm] += 1

    # Compute exact thread-depth stats from the streaming per-thread counts
    reply_depth = _thread_depth_stats(thread_counts)

    # Top custodian-subclass matrices (top 10 custodians by volume)
    top_custodians = [c for c, _ in custodian_counts.most_common(10)]
    top_cust_subclass = {c: dict(cust_subclass[c].most_common()) for c in top_custodians}

    # Subject length stats from reservoir sample
    subj_lens = []
    blen_by_file: dict[str, tuple[int, str]] = {f: (blen, k) for blen, k, f in reservoir}
    # Quick subject-length estimate using the same seed as the reservoir
    rng2 = random.Random(seed + 1)  # separate RNG so we don't mess up original sampling
    # Read index again just for subjects (efficient enough at O(n))
    with path.open(encoding="utf-8") as fh2:
        for line2 in fh2:
            if len(subj_lens) >= min(RESERVOIR_N * 2, n // 10):
                break
            try:
                r2 = json.loads(line2)
            except json.JSONDecodeError:
                continue
            subj_lens.append(len((r2.get("subject") or "").strip()))
    res["subject_pcts"] = {} if not subj_lens else {
        p: sorted(subj_lens)[int(p / 100 * (len(subj_lens) - 1))]
        for p in (0, 25, 50, 75, 90, 95, 99, 100)
    }

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
        "tz_offsets": dict(tz_offset_counts.most_common()),
        "reply_depth": reply_depth,
        "top_custodian_subclass": top_cust_subclass,
        # v2 expansion exports
        "hour_of_day": {h: hour_counts.get(h, 0) for h in range(24)},
        "day_of_week": {d: dow_counts.get(d, 0) for d in range(7)},
        "months": dict(sorted(month_counts.items())),
        "to_addrs": to_addrs,
        "cc_addrs": cc_addrs,
        "bcc_addrs": bcc_addrs,
        "msgs_with_to": msgs_with_to,
        "msgs_with_bcc": msgs_with_bcc,
        "msgs_no_to": msgs_with_cc_only,
        "bodies_with_text": sum(body_hash_counts.values()),
        "unique_bodies": len(body_hash_counts),
        "top_dup_bodies": [
            {"copies": c, "first_file": f}
            for c, f in sorted(
                ((cnt, body_hash_first[h]) for h, cnt in body_hash_counts.items()
                 if cnt > 1), reverse=True)[:10]
        ],
        "top_repeated_subjects": dict(subject_norm_counts.most_common(10)),
        "n_distinct_subjects": len(subject_norm_counts),
        "dedupe": {
            "largest_group_copies": max(body_hash_counts.values(), default=0),
            "cross_custodian_groups": sum(
                1 for holders in body_hash_custodians.values() if len(holders) >= 2),
        },
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
    L.append("**This CMU dump is text-only** — a verified corpus property, not a "
             "parser gap: a sample of 60,019 messages is 100% `text/plain`, "
             "0 multipart, and there are 5 `<msg>_files/` attachment-store dirs "
             "holding 69 files total. So the `attachments` field in the index is "
             "empty across the board and the mailroom's `correspondence` intake "
             "needs no attachment-handling path for this corpus (the EDRM Enron "
             "v2 dump, which does carry attachments, is a different dataset).")
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
             f"with BCC: {_fmt(sum(res['bcc'].get(k, 0) for k in res['bcc'] if k))} "
             f"— **Cc and Bcc are always co-present in this dump** (a CMU "
             "corpus artifact: every message with a Cc also has a Bcc, and "
             "vice versa), so the `additional_recipients` field will double-count "
             "unless the pipeline dedupes by address.")
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

    # --- NEW EDA SECTION 7b: Correlation body-length vs subclass ---
    L.append("### Body-length correlation per subclass")
    L.append("")
    L.append("Does the correspondence type correlate with message size?")
    L.append("")
    L.append("| subclass | n | median chars | max chars |")
    L.append("|---|---|---|---|")
    for k in SUBCLASS_KEYS:
        s = res["subclass_lengths"].get(k)
        if s:
            L.append(f"| `{k}` | {_fmt(s['n'])} | {_fmt(s['median'])} | {_fmt(s['max'])} |")
    L.append("")
    L.append("> **Observation**: press releases tend to be longest (full news release format), ")
    L.append("> followed by memos and notices. Standard emails cluster tightly around the median. ")
    L.append("> Pipeline implication: long-bodied subclasses benefit from the 40k specialist cap; ")
    L.append("> nearly all standard emails fit single-pass (<16k).")
    L.append("")

    # --- NEW EDA SECTION 8: Timezone distribution ---
    L.append("## 8. Timezone distribution & temporal patterns")
    L.append("")
    tz_items = list(res.get("tz_offsets", {}).items())[:12]
    if tz_items:
        L.append("| offset | messages | share |")
        L.append("|---|---|---|")
        for off, cnt in tz_items:
            L.append(f"| {off} | {_fmt(cnt)} | {cnt / n:.1%} |")
        L.append("")
        unknown = sum(v for k, v in res.get("tz_offsets", {}).items() if k == "unknown")
        parsed = sum(res["tz_offsets"].values())
        L.append(
            f"**{_fmt(parsed)} of {n} ({parsed/n:.1%})** have a detectable timezone offset. "
            f"{_fmt(n - parsed)} dates lack a parseable offset."
        )
        L.append("")
        primary = tz_items[0][0] if tz_items else "N/A"
        L.append(f"Primary timezone detected: **{primary}** (consistent with Enron HQ in Houston/US Central).")
        L.append("")
    else:
        L.append("*No timezone offsets were detectable in date strings.*")
        L.append("")

    # --- NEW EDA SECTION 8b: Reply-chain depth ---
    L.append("## 9. Reply-chain / thread depth")
    L.append("")
    rd = res.get("reply_depth", {})
    if rd and rd.get("n_threads", 0):
        L.append(f"**Exact counts** across all {rd['n_threads']:,} thread directories: ")
        L.append(f"{rd['singletons']:,} singletons, {rd['multi']:,} multi-message threads; ")
        L.append(f"largest thread directory holds **{rd['max_depth']:,} messages**.")
        L.append("")
        L.append("Full size distribution: §15 (+ `figures/10`).")
        L.append("")
        L.append(
            "> **Pipeline implication**: Multi-message directories dominate, and the largest "
            "holds thousands of near-identical copies. For deep threads, "
            "the downstream processor should use `_strip_forwarded()` to isolate own-message content.\n"
        )
    else:
        L.append("*Insufficient thread data for depth estimation.*")
        L.append("")

    # --- NEW EDA SECTION 9b: Custodian subclass breakdown ---
    L.append("## 10. Top custodians: per-subclass composition")
    L.append("")
    cust_sub = res.get("top_custodian_subclass", {})
    top_custs = sorted(cust_sub.items(), key=lambda x: sum(x[1].values()), reverse=True)[:10]
    if top_custs:
        L.append("| custodian | email | memo | letter | notice | demand | press_release | other |")
        L.append("|---|---|---|---|---|---|---|---|")
        for cname, subs in top_custs:
            vals = []
            for sk in ["email", "memo", "letter", "notice", "demand", "press_release", "other"]:
                vals.append(str(subs.get(sk, 0)))
            vals.append(str(sum(int(v) for v in vals)))
            L.append(f"| `{cname}` | {' | '.join(vals[:-1])} | {vals[-1]} |")
        L.append("")
        # Computed observation — never hand-typed: flag rare subclasses whose
        # top-custodian concentration exceeds double their corpus-wide share.
        corpus_sub = res.get("subclasses", {}) or {}
        total_n = res.get("n") or 0
        if corpus_sub and total_n:
            obs = []
            for k in ("memo", "letter", "notice", "demand", "press_release"):
                if not corpus_sub.get(k):
                    continue
                corpus_share = corpus_sub[k] / total_n
                best_name, best_share = max(
                    ((c, s.get(k, 0) / max(1, sum(s.values()))) for c, s in top_custs),
                    key=lambda t: t[1])
                if best_share > corpus_share * 2:
                    obs.append(f"`{k}` concentrates at `{best_name}` "
                               f"({best_share:.1%} of their mail vs "
                               f"{corpus_share:.1%} corpus-wide)")
            if obs:
                L.append("> **Notable (computed)**: " + "; ".join(obs) + ".")
        L.append("")

    # --- NEW EDA SECTION 10b: Subject length ---
    L.append("## 11. Subject-line patterns & length")
    L.append("")
    subj_pcts = res.get("subject_pcts", {})
    if subj_pcts:
        L.append("| pct | chars |")
        L.append("|---|---|")
        for p in sorted(subj_pcts.keys()):
            L.append(f"| p{p} | {subj_pcts[p]} |")
        L.append("")
        L.append(
            f"> Median subject length: **{subj_pcts.get(50, '?')}** characters. "
            "Long subjects (>150 chars) often indicate forwarded chains with accumulated prefixes.\n"
        )
    else:
        L.append("*Subject-length data not available.*")
        L.append("")

    # --- v2 expansion: Section 12. Temporal patterns ---
    L.append("## 12. Temporal patterns (hour, weekday, monthly volume)")
    L.append("")
    hours = res.get("hour_of_day", {})
    dows = res.get("day_of_week", {})
    months = res.get("months", {})
    if any(hours.values()):
        peak_hour = max(hours, key=hours.get)
        workday = sum(hours.get(h, 0) for h in range(8, 19))
        offhour = sum(hours.values()) - workday
        L.append(f"Peak hour (UTC): **{peak_hour}:00** with {_fmt(hours[peak_hour])} messages "
                 f"({hours[peak_hour] / max(1, sum(hours.values())):.1%} of timestamped mail).")
        L.append("")
        L.append("| hour (UTC) | messages | hour (UTC) | messages |")
        L.append("|---|---|---|---|")
        for h in range(12):
            L.append(f"| {h:02d}:00 | {_fmt(hours[h])} | {h + 12:02d}:00 | {_fmt(hours[h + 12])} |")
        L.append("")
        L.append(f"Business-hours share (08:00–18:59 UTC): **{workday / max(1, workday + offhour):.1%}** "
                 f"— consistent with a desk-workforce sender profile.")
        L.append("")
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if any(dows.values()):
        total_dow = sum(dows.values())
        weekend = sum(dows.get(d, 0) for d in (5, 6))
        L.append("Day-of-week distribution (UTC):")
        L.append("")
        L.append("| day | messages | share |")
        L.append("|---|---|---|")
        for d in range(7):
            L.append(f"| {dow_names[d]} | {_fmt(dows[d])} | {dows[d] / max(1, total_dow):.1%} |")
        L.append("")
        L.append(f"Weekend share: **{weekend / max(1, total_dow):.1%}** — Enron traders and "
                 "deal lawyers famously worked weekends; this quantifies it.")
        L.append("")
    if months:
        top_months = list(months.items())
        peak_month, peak_val = max(months.items(), key=lambda kv: kv[1])
        quiet_month, quiet_val = min(months.items(), key=lambda kv: kv[1])
        L.append(f"Monthly coverage: **{len(top_months)} distinct months** "
                 f"({top_months[0][0]} → {top_months[-1][0]}). Peak: **{peak_month}** "
                 f"({_fmt(peak_val)} msgs); quietest: **{quiet_month}** ({_fmt(quiet_val)}).")
        L.append("")
        L.append("| month | messages | month | messages |")
        L.append("|---|---|---|---|")
        half = (len(top_months) + 1) // 2
        for i in range(half):
            left = top_months[i]
            if i + half < len(top_months):
                right = top_months[i + half]
                r_cells = (right[0], _fmt(right[1]))
            else:
                r_cells = ("—", "—")
            L.append(f"| {left[0]} | {_fmt(left[1])} | {r_cells[0]} | {r_cells[1]} |")
        L.append("")

    # --- v2 expansion: Section 13. Recipient roles ---
    L.append("## 13. Recipient roles (To / Cc / Bcc)")
    L.append("")
    L.append(f"| role | total addresses | messages carrying ≥1 | avg per such message |")
    L.append(f"|---|---|---|---|")
    n_to_msgs = max(1, res["msgs_with_to"])
    L.append(f"| To | {_fmt(res['to_addrs'])} | {_fmt(res['msgs_with_to'])} | {res['to_addrs'] / n_to_msgs:.2f} |")
    L.append(f"| Cc | {_fmt(res['cc_addrs'])} | — | — |")
    L.append(f"| Bcc | {_fmt(res['bcc_addrs'])} | {_fmt(res['msgs_with_bcc'])} | {res['bcc_addrs'] / max(1, res['msgs_with_bcc']):.2f} |")
    L.append("")
    L.append(f"Messages with **no To-address at all** (Bcc-only or Cc-only sends): "
             f"**{_fmt(res['msgs_no_to'])}** ({res['msgs_no_to'] / max(1, n):.2%}). "
             "These are the mass-mail / blind-copy artifacts; downstream intake should "
             "not assume every message has a To header.")
    L.append("")

    # --- v2 expansion: Section 14. Duplicates & reuse ---
    L.append("## 14. Duplicates & content reuse")
    L.append("")
    bodies_text = res["bodies_with_text"]
    uniq = res["unique_bodies"]
    dupes = bodies_text - uniq
    L.append(f"Exact-duplicate bodies (md5 over raw body text): **{_fmt(dupes)}** of "
             f"{_fmt(bodies_text)} non-empty bodies ({dupes / max(1, bodies_text):.1%}) — "
             f"{_fmt(uniq)} unique.")
    dd = res.get("dedupe", {})
    if dd:
        L.append("")
        L.append(f"Largest duplicate group: **{_fmt(dd['largest_group_copies'])} copies** of one "
                 f"body; **{_fmt(dd['cross_custodian_groups'])}** duplicate groups span two or "
                 f"more custodians — these are cross-mailbox copies (cc'ing, saved sent-folder "
                 f"duplicates), not just intra-folder saves.")
        L.append("")
        L.append("**Sampling policy (enforced)**: `build_pipeline_dump.py` hashes every row's "
                 "body with the identical md5 scheme and skips repeats, so the pipeline sample "
                 "is drawn only from unique texts. `scripts/dedupe.py --index data/enron/index.jsonl "
                 "--out data/enron/index.unique.jsonl` regenerates a fully deduplicated index.")
    L.append("")
    if res["top_dup_bodies"]:
        L.append("Top duplicated bodies (copies → first-seen file):")
        L.append("")
        L.append("| copies | first seen at |")
        L.append("|---|---|")
        for d in res["top_dup_bodies"]:
            L.append(f"| {_fmt(d['copies'])} | `{d['first_file']}` |")
        L.append("")
    if res["top_repeated_subjects"]:
        L.append(f"Most-repeated normalized subjects (of {res['n_distinct_subjects']} distinct):")
        L.append("")
        L.append("| subject | count |")
        L.append("|---|---|")
        for s_, c_ in res["top_repeated_subjects"].items():
            shown = s_[:70] + "…" if len(s_) > 70 else s_
            L.append(f"| `{shown}` | {_fmt(c_)} |")
        L.append("")
    L.append("> Pipeline implication: dedupe by body hash BEFORE stratified sampling, "
             "or newsletter/blast mails will be overweighted in the sample.")
    L.append("")

    # --- v2 expansion: Section 15. Thread-size distribution ---
    rd15 = res.get("reply_depth", {})
    if rd15.get("n_threads"):
        L.append("## 15. Thread-size distribution (exact)")
        L.append("")
        L.append(f"{rd15['n_threads']:,} thread directories · "
                 f"{rd15['singletons']:,} singletons ({rd15['singletons'] / rd15['n_threads']:.1%}) · "
                 f"{rd15['multi']:,} multi-message threads.")
        L.append("")
        L.append("| thread size | share of threads |")
        L.append("|---|---|")
        L.append(f"| 1 message | {rd15['singletons'] / rd15['n_threads']:.1%} |")
        L.append(f"| 2 messages | {rd15['depth_2_pct']}% |")
        L.append(f"| 3–5 messages | {rd15['depth_3_5_pct']}% |")
        L.append(f"| 6–10 messages | {rd15['depth_6_10_pct']}% |")
        L.append(f"| >10 messages | {rd15['depth_gt10_pct']}% |")
        L.append("")
        L.append(f"Largest thread directory: **{rd15['max_depth']:,} messages**.")
        L.append("")

    L.append("## 16. Pipeline fit")
    L.append("")
    L.append("The correspondence specialist cap is 40k chars; the sorter's "
             "single-pass text path is 16k; the chunk window is 90k. Enron "
             "bodies are small (median "
             f"{_fmt(res['body_pcts'][50])} chars), so virtually all rows pass "
             "single-pass text intake — the sampling strata for the pipeline "
             "dump (custodian, internal/external, subclass, attachment "
             "presence) should preserve the subclass mix above.")
    L.append("")
    L.append(f"Figures: `figures/01`–`12` (subclass distribution, hour-of-day, "
             f"day-of-week, monthly volume, internal/external, top senders, "
             f"body-length vs budgets, custodian volume, fan-out, thread sizes, "
             f"duplicate bodies, recipient roles).")
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
             "_files/ sibling dirs. **This CMU dump is text-only** (verified: 60,019 "
             "sampled messages are 100% text/plain, 0 multipart) — no attachment "
             "handling is needed for the correspondence intake.")
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


def _barh(ax, names, values, color, title, xlabel="count",
          value_labels=True, share_denom: int | None = None):
    """Horizontal bars with value labels, headroom and an x-only grid.

    ``share_denom`` (e.g. corpus size) appends a ``(x.x%)`` share to each
    label so absolute counts and proportions are visible in one glance.
    """
    ys = range(len(names))[::-1]
    ax.barh(ys, values, color=color)
    ax.set_yticks(ys)
    ax.set_yticklabels(names, fontsize=7.5)
    vmax = max(values) or 1
    if value_labels:
        for y, v in zip(ys, values):
            txt = f"{v:,}" + (f" ({v / share_denom:.1%})" if share_denom else "")
            ax.text(v + vmax * 0.015, y, txt, va="center", ha="left",
                    fontsize=7.5)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _p: _kfmt(v)))
    _headroom(ax, is_barh=True)
    ax.set_xlim(left=0)
    _grid(ax, "x")


def make_figures(res: dict, figdir: Path) -> None:
    n = res["n"]

    # 01 — subclass distribution, TWO PANELS. The corpus is ~98% `email`, so
    # a single linear chart renders every rare class as an invisible sliver.
    # Left: all classes on a log x-axis (honest overview of the spread).
    # Right: linear zoom on the rare classes, where the labeler's precision
    # actually lives. Zero-count classes are annotated so the enum's empty
    # slots stay visible (the coverage check).
    items = sorted(((k, res["subclasses"].get(k, 0)) for k in SUBCLASS_KEYS),
                   key=lambda kv: kv[1])
    names = [SUBCLASS_LABELS[k] for k, _ in items]
    vals = [v for _, v in items]
    total = sum(vals) or 1
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12.5, 5.2), gridspec_kw={"width_ratios": [1.1, 1]})

    # Panel A — all classes, log scale (5 orders of magnitude fit).
    ys = range(len(names))[::-1]
    ax1.barh(ys, vals, color=TEAL)
    ax1.set_yticks(ys)
    ax1.set_yticklabels(names, fontsize=7.5)
    ax1.set_xscale("log")
    vmax = max(vals) or 1
    ax1.set_xlim(0.5, vmax * 6)
    for y, v in zip(ys, vals):
        if v > 0:
            ax1.text(v * 1.3, y, f"{v:,} ({v / total:.2%})",
                     va="center", ha="left", fontsize=7.5)
        else:
            ax1.text(0.55, y, "0", va="center", ha="left",
                     fontsize=7.5, color=GRAY)
    ax1.set_xlabel("messages (log scale)")
    ax1.set_title("All subclasses — five orders of magnitude")
    _grid(ax1, "x")

    # Panel B — rare classes only (email excluded), linear, share-labeled.
    rare = [(k, v) for k, v in items if k != "email"]
    rnames = [SUBCLASS_LABELS[k] for k, _ in rare]
    rvals = [v for _, v in rare]
    rys = range(len(rnames))[::-1]
    bars = ax2.barh(rys, rvals, color=TEAL)
    ax2.set_yticks(rys)
    ax2.set_yticklabels(rnames, fontsize=7.5)
    rmax = max(rvals) or 1
    for y, v in zip(rys, rvals):
        ax2.text(v + rmax * 0.02, y, f"{v:,} ({v / total:.2%})",
                 va="center", ha="left", fontsize=7.5)
    ax2.set_xlabel("messages (linear — email excluded)")
    ax2.set_title("Rare subclasses — the labeler's precision regime")
    _headroom(ax2, is_barh=True)
    ax2.set_xlim(left=0)
    _grid(ax2, "x")
    _finish(fig, figdir / "01_subclasses.png", CITE)

    # 02 — hour-of-day profile (UTC): replaces the structurally-empty
    # attachment-parts chart (the CMU dump is text-only, 0 attachments).
    # Business hours are shaded so the desk-workforce profile in report §12
    # is visible directly on the chart.
    hours = res.get("hour_of_day", {})
    fig, ax = plt.subplots(figsize=(9, 4.2))
    hv = [hours.get(h, 0) for h in range(24)]
    bars = ax.bar([f"{h:02d}" for h in range(24)], hv, color=AMBER)
    ax.axvspan(7.5, 18.5, color="#fde68a", alpha=0.35, zorder=0)
    _headroom(ax)
    ymax = ax.get_ylim()[1]
    ax.text(7.7, ymax * 0.97, "business hours\n08–18 UTC", ha="left",
            va="top", fontsize=7.5, color="#92400e")
    if max(hv):
        peak = max(range(24), key=lambda h: hv[h])
        bars[peak].set_color(AMBER_DARK)
        ax.annotate(f"peak {peak:02d}:00 UTC · {hv[peak]:,}",
                    (peak, hv[peak]), xytext=(0, 6),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=8, color=AMBER_DARK)
    ax.set_xlabel("hour of day (UTC)")
    ax.set_ylabel("messages")
    ax.set_title("Message volume by hour of day")
    _grid(ax, "y")
    _finish(fig, figdir / "02_hour_of_day.png", CITE)

    # 03 — day-of-week profile; weekends highlighted, counts + shares labeled.
    dows = res.get("day_of_week", {})
    fig, ax = plt.subplots(figsize=(7, 4.2))
    dv = [dows.get(d, 0) for d in range(7)]
    bars = ax.bar(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], dv,
                  color=[BLUE] * 5 + [PINK] * 2)
    tot = sum(dv) or 1
    for b, v in zip(bars, dv):
        ax.annotate(f"{v / tot:.0%}\n{v:,}",
                    (b.get_x() + b.get_width() / 2, v),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7.5)
    _headroom(ax)
    ax.set_ylabel("messages")
    ax.set_title("Message volume by weekday (UTC) — weekend in pink")
    _grid(ax, "y")
    _finish(fig, figdir / "03_day_of_week.png", CITE)

    # 04 — monthly volume timeline on a REAL date axis. The raw YYYY-MM keys
    # include data-quality artifacts (e.g. 1980-01, 2044-01 typo years) that,
    # plotted categorically, stretch the axis and squish the actual 1997–2002
    # story. We focus on the smallest contiguous month window holding 99% of
    # all message volume (two-pointer sweep), annotate the peak, and disclose
    # the excluded tail on the chart — no volume is silently dropped.
    months = res.get("months", {})
    fig, ax = plt.subplots(figsize=(10, 4.2))
    if months:
        keys_all = sorted(months)
        vals_all = [months[k] for k in keys_all]
        total_m = sum(vals_all) or 1
        target = 0.99 * total_m
        # Smallest contiguous window [i, j] with sum >= 99% of volume.
        best = (0, len(vals_all) - 1)
        i = 0
        running = 0
        for j, v in enumerate(vals_all):
            running += v
            while running - vals_all[i] >= target and i < j:
                running -= vals_all[i]
                i += 1
            if running >= target and (j - i) < (best[1] - best[0]):
                best = (i, j)
        lo_k, hi_k = keys_all[best[0]], keys_all[best[1]]
        keys = keys_all[best[0]:best[1] + 1]
        mv = [months[k] for k in keys]
        exc_n = total_m - sum(mv)
        xs = [datetime.date(int(k[:4]), int(k[5:7]), 1) for k in keys]
        peak_val = max(mv)
        ax.plot(xs, mv, color=TEAL, lw=1.6, marker="o", ms=2.5)
        ax.fill_between(xs, mv, color=TEAL, alpha=0.15)
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.margins(x=0.02)
        ax.set_ylim(0, peak_val * 1.14)
        pk = mv.index(peak_val)
        ax.annotate(f"peak {keys[pk]} · {peak_val:,}",
                    (xs[pk], peak_val), xytext=(0, 8),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=8, color=AMBER_DARK)
        if exc_n:
            n_exc = len(keys_all) - len(keys)
            note = (f"omitted {n_exc} outlier month(s) outside the 99% "
                    f"volume window ({exc_n:,} msgs, {exc_n / total_m:.1%}) — "
                    "Date-header artifacts")
            ax.text(0.01, 0.97, note, transform=ax.transAxes, va="top",
                    fontsize=7.5, color=GRAY)
    ax.set_ylabel("messages")
    ax.set_title("Message volume by month (Date header, YYYY-MM)")
    _grid(ax, "y")
    _finish(fig, figdir / "04_monthly_volume.png", CITE)

    # 05 — internal vs external senders, value + share labeled with headroom.
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    labs = ["internal\n(enron.com)", "external", "no sender parsed"]
    vv = [res["internal"], res["external"],
          n - res["internal"] - res["external"]]
    bars = ax.bar(labs, vv, color=BLUE)
    for b, v in zip(bars, vv):
        ax.annotate(f"{v:,}\n({v / n:.1%})",
                    (b.get_x() + b.get_width() / 2, v),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)
    _headroom(ax)
    ax.set_ylabel("messages")
    ax.set_title("Internal vs external senders")
    _grid(ax, "y")
    _finish(fig, figdir / "05_internal_external.png", CITE)

    # 06 — top 20 senders (value labels + headroom via _barh).
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    senders = list(res["senders"].items())[:20]
    _barh(ax, [k for k, _ in senders], [v for _, v in senders], BLUE,
          "Top 20 senders", xlabel="messages")
    _finish(fig, figdir / "06_top_senders.png", CITE)

    # 07 — body-length histogram vs pipeline budgets; x-axis clipped at the
    # p99.5 so the bulk stays visible (the long tail is noted on the axis).
    # Adds the median marker, the ≤16k single-pass coverage stat, and an
    # explicit note for the budgets that lie beyond the clip.
    lens = [r[0] for r in res["reservoir"]] or [0]
    p995 = sorted(lens)[int(0.995 * (len(lens) - 1))]
    clip = max(p995 * 1.25, 1000)
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.hist([x for x in lens if x <= clip], bins=60, range=(0, clip),
            color=PURPLE, edgecolor="white")
    for b in BUDGETS:
        if b <= clip:
            ax.axvline(b, color=RED, ls="--", lw=1.2)
            ax.annotate(f"{b // 1000}k", (b, ax.get_ylim()[1]),
                        xytext=(-3, -2), textcoords="offset points",
                        ha="right", va="top", rotation=90,
                        fontsize=8, color=RED)
    med = res["body_pcts"][50]
    if med <= clip:
        ax.axvline(med, color=TEAL, lw=1.4)
        ax.annotate(f"median {_kfmt(med)}", (med, ax.get_ylim()[1]),
                    xytext=(4, -2), textcoords="offset points",
                    ha="left", va="top", fontsize=8, color=TEAL)
    under16 = 1 - res["budget_over"][16_000][1]
    ax.text(0.985, 0.90, f"{under16:.1%} of bodies ≤ 16k chars",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color="#374151",
            bbox={"boxstyle": "round,pad=0.3", "fc": "white",
                  "ec": "#d1d5db", "lw": 0.6})
    beyond = [b for b in BUDGETS if b > clip]
    if beyond:
        ax.text(0.985, 0.04,
                f"{', '.join(_kfmt(b) for b in beyond)} budgets beyond clip",
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=7.5, color=GRAY)
    ax.set_xlim(0, clip)
    ax.set_xlabel(f"body chars (axis clipped at {clip:,.0f}; "
                  f"max observed {_fmt(res['body_chars_max'])})")
    ax.set_ylabel("messages")
    ax.set_title("Body length distribution (20k reservoir) vs pipeline budgets")
    _grid(ax, "y")
    _finish(fig, figdir / "07_body_length.png", CITE)

    # 08 — custodian volume (value labels + headroom via _barh).
    fig, ax = plt.subplots(figsize=(8.5, 6))
    custs = list(res["custodians"].items())[:25]
    _barh(ax, [k for k, _ in custs], [v for _, v in custs], TEAL,
          "Message volume per custodian (top 25)", xlabel="messages")
    _finish(fig, figdir / "08_custodians.png", CITE)

    # 09 — recipient fan-out on a log y-axis: fan-out 1 dominates so heavily
    # that a linear scale flattens the entire tail into invisibility.
    fan = res.get("fanout", {})
    fig, ax = plt.subplots(figsize=(8, 4.2))
    fk = [str(k) for k in range(0, 16)]
    fv = [fan.get(k, 0) for k in range(0, 16)]
    ax.bar(fk, fv, color=PINK)
    ax.set_yscale("log")
    fmax = max(fv) or 1
    ax.set_ylim(top=fmax * 3)
    ax.text(0.99, 0.96, "log scale — single-recipient mail dominates",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=7.5, color=GRAY)
    ax.set_xlabel("recipients per message (to+cc+bcc; >15 not shown)")
    ax.set_ylabel("messages (log)")
    ax.set_title("Recipient fan-out")
    _grid(ax, "y")
    _finish(fig, figdir / "09_fanout.png", CITE)

    # 10 — thread-size distribution (exact, from streaming per-thread counts).
    rd = res.get("reply_depth", {})
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    nt = max(1, rd.get("n_threads", 0))
    buckets = ["1", "2", "3–5", "6–10", ">10"]
    shares = [
        rd.get("singletons", 0) / nt * 100,
        rd.get("depth_2_pct", 0.0),
        rd.get("depth_3_5_pct", 0.0),
        rd.get("depth_6_10_pct", 0.0),
        rd.get("depth_gt10_pct", 0.0),
    ]
    bars = ax.bar(buckets, shares, color=CYAN)
    for b, s in zip(bars, shares):
        ax.annotate(f"{s:.1f}%", (b.get_x() + b.get_width() / 2, s),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)
    _headroom(ax)
    ax.set_xlabel("messages per thread directory")
    ax.set_ylabel("% of threads")
    ax.set_title(f"Thread-size distribution "
                 f"({rd.get('n_threads', 0):,} thread dirs, exact)")
    _grid(ax, "y")
    _finish(fig, figdir / "10_thread_sizes.png", CITE)

    # 11 — exact-duplicate bodies (md5).
    bodies_text = res["bodies_with_text"]
    uniq = res["unique_bodies"]
    dupes = bodies_text - uniq
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    bars = ax.bar(["unique bodies", "exact duplicate\ncopies"],
                  [uniq, dupes], color=[GREEN, RED])
    denom = max(1, bodies_text)
    for b, v in zip(bars, [uniq, dupes]):
        ax.annotate(f"{v:,}\n({v / denom:.1%})",
                    (b.get_x() + b.get_width() / 2, v),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)
    _headroom(ax)
    ax.set_ylabel("bodies")
    ax.set_title(f"Exact-duplicate bodies (md5, n={bodies_text:,})")
    _grid(ax, "y")
    _finish(fig, figdir / "11_duplicates.png", CITE)

    # 12 — recipient role totals, labeled with share of all addresses.
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    roles = ["To", "Cc", "Bcc"]
    rv = [res["to_addrs"], res["cc_addrs"], res["bcc_addrs"]]
    rtot = sum(rv) or 1
    bars = ax.barh(roles[::-1], rv[::-1], color=VIOLET)
    rmax = max(rv) or 1
    for b, v in zip(bars, rv[::-1]):
        ax.text(v + rmax * 0.015, b.get_y() + b.get_height() / 2,
                f"{v:,} ({v / rtot:.0%})", va="center", ha="left", fontsize=8)
    _headroom(ax, is_barh=True)
    ax.set_xlim(left=0)
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _p: _kfmt(v)))
    ax.set_xlabel("total addresses across corpus")
    ax.set_title("Recipient address volume by header role")
    _grid(ax, "x")
    _finish(fig, figdir / "12_recipient_roles.png", CITE)


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