#!/usr/bin/env python3
"""Render a bounded, stratified set of Enron correspondence messages as
cleanly formatted Markdown into ``samples/`` (human directive 2026-09-04).

Selection law:

- Stratified by the SHARED 10-key correspondence taxonomy
  (``correspondence_subclasses.label_correspondence``) — the samples folder
  doubles as a human-readable taxonomy showcase.
- Deterministic: candidates are gathered in sorted maildir order, then
  chosen by a seeded RNG (default seed = the CMU tarball date, 20150507).
  Same corpus + same seed ⇒ byte-identical output.
- Bounded: ``--per-subclass`` files per subclass key (default 2), a
  ``--limit`` parse cap, and a per-message body cap. The raw corpus and the
  index are gitignored — samples are the ONLY corpus text committed, so the
  selection stays small by design.

Rendering law (clean formatting):

- H1 subject, header metadata table (from/to/cc/date/message-id), maildir
  provenance, subclass label + labeler evidence, attachment names.
- Reply/forward quoting: ``>``-prefixed lines render as Markdown blockquotes
  (one level per ``>``); when the shared ``_strip_forwarded`` helper detects
  forwarded/quoted content, own-message content renders first and forwarded
  content under an explicit section.

Usage:
    python scripts/build_samples.py --dry-run          # plan, no files
    python scripts/build_samples.py                    # render samples/
    python scripts/build_samples.py --per-subclass 3
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_corpus_index import iter_messages, parse_message  # noqa: E402
from correspondence_subclasses import (  # noqa: E402
    SUBCLASS_KEYS,
    SUBCLASS_LABELS,
    _strip_forwarded,
    label_correspondence,
)

SAMPLES_DIR = ROOT / "samples"
DEFAULT_SEED = 20150507  # the CMU tarball date — provenance, not magic
DEFAULT_BODY_CAP = 6000
_QUOTE_RE = re.compile(r"^(>*)(.*)$")
_MD_TABLE_ESC = re.compile(r"\|")
_NL_RE = re.compile(r"\n{3,}")


def _esc_cell(text: str) -> str:
    return _MD_TABLE_ESC.sub("\\|", text).strip()


def _render_body(body: str) -> str:
    """Body → Markdown: tidy paragraphs, ``>`` quoting → blockquotes."""
    body = _NL_RE.sub("\n\n", body)
    out: list[str] = []
    prev_level = 0
    for line in body.splitlines():
        m = _QUOTE_RE.match(line.rstrip())
        level, content = len(m.group(1)), m.group(2).strip()
        if level > prev_level and out and out[-1]:
            pass  # blockquote continuation handled below
        if level == 0:
            out.append(content)
        else:
            out.append("> " * level + content)
        prev_level = level
    return "\n".join(out).strip()


def _people(recipients: list[dict], role: str) -> str:
    cells = []
    for r in recipients or []:
        if r.get("role") == role:
            who = r.get("name") or r.get("addr") or "(unknown)"
            addr = r.get("addr") or ""
            cells.append(f"{who} <{addr}>" if addr and addr not in who else str(who))
    return "; ".join(cells)


def render_markdown(row: dict, key: str, evidence: str) -> str:
    """One parsed index row → a cleanly formatted Markdown document."""
    subject = row.get("subject") or "(no subject)"
    date = row.get("date") or "(undated)"
    from_who = _people([{"name": row.get("sender", ""), "addr": row.get("sender_addr", ""), "role": "from"}], "from")
    lines: list[str] = [
        f"# {subject}",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| From | {_esc_cell(from_who)} |",
    ]
    for role, label in (("to", "To"), ("cc", "Cc"), ("bcc", "Bcc")):
        people = _people(row.get("recipients", []), role)
        if people:
            lines.append(f"| {label} | {_esc_cell(people)} |")
    lines += [
        f"| Date | {_esc_cell(date)} |",
        f"| Message-ID | {_esc_cell(str(row.get('message_id') or '').strip('<>'))} |",
        f"| Subclass | **{SUBCLASS_LABELS.get(key, key)}** (`{key}`) |",
        f"| Labeler evidence | {_esc_cell(evidence)} |",
        f"| Custodian | {_esc_cell(str(row.get('custodian') or ''))} |",
        f"| Folder | {_esc_cell(str(row.get('folder') or ''))} |",
        f"| Thread | {_esc_cell(str(row.get('thread') or ''))} |",
    ]
    atts = row.get("attachments") or []
    if atts:
        names = "; ".join(f"{a.get('name')} ({a.get('mime')})" for a in atts[:8])
        more = f" (+{len(atts) - 8} more)" if len(atts) > 8 else ""
        lines.append(f"| Attachments | {_esc_cell(names)}{more} |")

    lines.append("")
    lines.append("## Body")
    lines.append("")

    body = str(row.get("body") or "").strip()
    own = _strip_forwarded(body)
    forwarded = body[len(own):].strip() if own and own != body else ""
    if forwarded:
        lines.append(_render_body(own))
        lines.append("")
        lines.append("### Forwarded / quoted content")
        lines.append("")
        lines.append(_render_body(forwarded))
    else:
        lines.append(_render_body(body))
    return "\n".join(lines).rstrip() + "\n"


def _slug(row: dict) -> str:
    parts = [str(row.get(k) or "") for k in ("custodian", "folder", "thread")]
    name = Path(str(row.get("filename") or "msg")).name
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", "/".join(p for p in parts if p) + "/" + name)
    return slug.strip("-").lower()[:120] or "sample"


def _plan(argv: list[str]):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maildir", type=Path, default=ROOT / "data" / "raw" / "maildir")
    parser.add_argument("--out", type=Path, default=SAMPLES_DIR)
    parser.add_argument("--per-subclass", type=int, default=2,
                        help="Files per subclass key (default 2)")
    parser.add_argument("--candidates", type=int, default=120,
                        help="Reservoir size per subclass before seeded choice")
    parser.add_argument("--limit", type=int, default=40000,
                        help="Max messages walked (parse cap)")
    parser.add_argument("--body-cap", type=int, default=DEFAULT_BODY_CAP)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def build_samples(args) -> int:
    if not args.maildir.is_dir():
        print(f"maildir not found: {args.maildir} — run acquire_enron.py first")
        return 1
    print(f"Maildir: {args.maildir}")
    print(f"Selection: {args.per_subclass}/subclass, seed={args.seed}, "
          f"limit={args.limit}, body-cap={args.body_cap}")

    reservoirs: dict[str, list[dict]] = {key: [] for key in SUBCLASS_KEYS}
    n_unlabeled = 0
    walked = 0
    for custodian, folder, msg_path, rel in iter_messages(args.maildir, args.limit):
        walked += 1
        row = parse_message(msg_path, rel)
        if not row.get("parseable"):
            continue
        row["custodian"], row["folder"] = custodian, folder
        parts = rel.split("/")
        row["thread"] = "/".join(parts[:-1])
        body = row.get("body") or ""
        if not body.strip():
            continue
        key, evidence = label_correspondence(row)
        if key not in reservoirs:
            n_unlabeled += 1
            continue
        res = reservoirs[key]
        if len(res) < args.candidates:
            res.append(row)
        # Early stop: every stratum's reservoir holds at least
        # per_subclass*4 candidates and we've walked a sane floor —
        # custodian diversity comes from the reservoir, not from walking
        # longer. The floor also lets slow strata keep accumulating.
        if walked >= 400 and all(
            len(r) >= min(args.candidates, max(args.per_subclass * 4, 40))
            for r in reservoirs.values()
        ):
            break
    print(f"Walked {walked} messages; reservoir sizes: "
          + ", ".join(f"{k}={len(v)}" for k, v in reservoirs.items()))

    rng = random.Random(args.seed)
    chosen: list[tuple[str, dict, str]] = []
    for key in SUBCLASS_KEYS:
        res = reservoirs[key][:]
        rng.shuffle(res)
        for row in res[: args.per_subclass]:
            key2, evidence = label_correspondence(row)
            chosen.append((key, row, evidence))
    if not chosen:
        print("No labeled candidates — nothing to render.")
        return 1

    if args.dry_run:
        for key, row, _ in sorted(chosen, key=lambda c: (c[0], c[1]["filename"])):
            print(f"  [{key}] {_slug(row)}  “{row.get('subject')[:60]}”")
        print(f"Dry run — {len(chosen)} files planned, no files written.")
        return 0

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    index_rows = []
    for key, row, evidence in sorted(chosen, key=lambda c: (c[0], c[1]["filename"])):
        text = render_markdown(row, key, evidence)
        if len(text) > args.body_cap + 4000:
            text = text[: args.body_cap + 4000] + (
                "\n\n---\n*…truncated at the samples body cap "
                f"({args.body_cap} body characters) — full text in the corpus.*\n"
            )
        fname = f"{key}-{_slug(row)}.md"
        (out / fname).write_text(text, encoding="utf-8")
        index_rows.append((fname, key, row))

    # Generated index — the samples README doubles as a taxonomy showcase.
    lines = [
        "# Enron correspondence samples (cleanly formatted Markdown)",
        "",
        "Human-readable, taxonomy-stratified selection of the CMU Enron",
        "corpus. The raw maildir and the index are gitignored — THIS folder",
        "is the only committed corpus text, so the selection stays bounded.",
        "",
        "| Sample | Subclass | From | Date | Subject |",
        "| --- | --- | --- | --- | --- |",
    ]
    for fname, key, row in index_rows:
        subject = str(row.get("subject") or "(no subject)")
        lines.append(
            f"| [`{fname}`]({fname}) | {SUBCLASS_LABELS.get(key, key)} "
            f"| {_esc_cell(row.get('sender') or row.get('sender_addr') or '')} "
            f"| {_esc_cell(str(row.get('date') or '')[:10])} "
            f"| {_esc_cell(subject[:70])} |"
        )
    lines += [
        "",
        "## Regenerating",
        "",
        "```bash",
        "python scripts/acquire_enron.py     # corpus (gitignored)",
        "python scripts/build_samples.py     # deterministic (seed 20150507)",
        "```",
        "",
        f"Selection law: {args.per_subclass} per subclass key, reservoir "
        f"{args.candidates}, walk cap {args.limit}, body cap {args.body_cap}, "
        f"seed {args.seed}. Same corpus + seed ⇒ byte-identical output.",
        "",
        "## Source & scope",
        "",
        "Text is verbatim from the public CMU Enron email corpus",
        "(tarball 2015-05-07), rendered read-only for human orientation.",
        "Subclass labels come from the shared labeler "
        "(`scripts/correspondence_subclasses.py`) with per-file evidence.",
        "",
    ]
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(index_rows)} samples + README -> {out}")
    return 0


def main() -> int:
    return build_samples(_plan(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
