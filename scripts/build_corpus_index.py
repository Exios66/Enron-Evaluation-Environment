#!/usr/bin/env python3
"""Build the full-corpus index from the CMU Enron maildir.

Walks ``data/raw/maildir/<custodian>/<folder>/<thread>/<msg>``, parses every
message with the stdlib ``email`` package, and writes one JSONL row per
message to ``data/enron/index.jsonl`` (gitignored, regenerable).

Row fields:

- ``filename`` — maildir path relative to the maildir root (deterministic id)
- ``custodian`` / ``folder`` / ``thread`` — maildir provenance
- ``sender`` / ``sender_addr`` — display name + address (first From)
- ``recipients`` — list of {name, addr, role: to|cc|bcc}
- ``date`` — ISO-8601 date (UTC) when parseable, else raw header string
- ``subject`` — decoded subject
- ``message_id`` / ``references`` / ``in_reply_to`` — threading headers
- ``body`` — preferred text body (text/plain, else HTML stripped of tags)
- ``body_content_type`` — which part type supplied ``body``
- ``attachments`` — inline parts with a filename: [{name, mime, size}]
- ``sibling_files`` — files in the ``<msg>_files/`` sibling dir (if any)
- ``parseable`` — False when the file could not be parsed as an email

Output is deterministically ordered (sorted maildir paths), so rebuilds are
byte-identical.

Usage:
    python scripts/build_corpus_index.py --dry-run
    python scripts/build_corpus_index.py
    python scripts/build_corpus_index.py --limit 1000      # quick smoke
    python scripts/build_corpus_index.py --out /tmp/index.jsonl
"""

from __future__ import annotations

import argparse
import email
import email.policy
import html
import json
import os
import re
import sys
from email.utils import getaddresses, parsedate_to_datetime, unquote
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAILDIR = ROOT / "data" / "raw" / "maildir"
DEFAULT_OUT = ROOT / "data" / "enron" / "index.jsonl"

_SKIP_DIR_NAMES = {"__pycache__"}
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = _WS_RE.sub(" ", text)
    text = _NL_RE.sub("\n\n", text)
    return text.strip()


def _decode_part(part: email.message.Message) -> str | None:
    """Best-effort decode of a text part's payload (charset-aware)."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return None
    charset = part.get_content_charset() or "utf-8"
    for enc in (charset, "utf-8", "latin-1", "ascii"):
        try:
            return payload.decode(enc, errors="replace")
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="replace")


def _strip_html(body: str) -> str:
    body = _HTML_TAG_RE.sub(" ", body)
    body = html.unescape(body)
    return _clean(body)


def _split_addrs(header: str) -> list[tuple[str, str]]:
    """Return [(display_name, addr)] from a To/Cc/Bcc header."""
    pairs = getaddresses([header or ""])
    out = []
    for name, addr in pairs:
        name = _clean(name).strip('"')
        addr = addr.strip().strip("<>")
        if addr or name:
            out.append((name, addr))
    return out


def _parse_date(raw: str) -> str:
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is not None:
            dt = dt.astimezone(__import__("datetime").timezone.utc)
        return dt.isoformat()
    except (TypeError, ValueError, OverflowError):
        return _clean(raw) or ""


def _hdr(msg: email.message.Message, name: str) -> str:
    """Header value as str, tolerating malformed headers.

    The CMU Enron maildir contains messages whose headers crash the strict
    ``email.policy.default`` parser at *access* time (e.g. ``TypeError:
    'ValueTerminal' object does not support item assignment`` from
    address-list parsing). Header access is lazy, so those failures happen
    outside the guarded file-open below. One bad header must not abort a
    517k-message walk.
    """
    try:
        return str(msg.get(name, "") or "")
    except Exception:  # noqa: BLE001 - malformed header -> treat as absent
        return ""


def parse_message(path: Path, rel: str) -> dict:
    """Parse one maildir message file into an index row (never raises)."""
    try:
        with path.open("rb") as fh:
            msg = email.message_from_binary_file(fh, policy=email.policy.default)
    except Exception:  # noqa: BLE001 - one bad file must not abort the walk
        return {"filename": rel, "parseable": False}

    from_header = _hdr(msg, "From")
    from_pairs = _split_addrs(from_header)
    sender, sender_addr = (from_pairs[0] if from_pairs else ("", ""))
    sender = _clean(sender)

    recipients = []
    for role in ("to", "cc", "bcc"):
        for name, addr in _split_addrs(_hdr(msg, role)):
            recipients.append({"name": name, "addr": addr, "role": role})

    # Body: preferred text/plain, else text/html (tags stripped).
    body = ""
    body_content_type = ""
    attachments = []
    for part in msg.walk():
        ctype = part.get_content_type()
        try:
            filename = part.get_filename()
            disposition = str(part.get_content_disposition() or "").lower()
        except Exception:  # noqa: BLE001 - malformed MIME headers
            filename, disposition = None, ""
        if ctype == "multipart/*" or not filename and ctype in ("multipart/alternative", "multipart/mixed"):
            continue
        if ctype in ("text/plain", "text/html"):
            if not body and disposition != "attachment":
                decoded = _decode_part(part)
                if decoded is None:
                    continue
                body = _strip_html(decoded) if ctype == "text/html" else _clean(decoded)
                body_content_type = ctype
            continue
        # Anything else with a filename (or an attachment disposition) is an
        # attachment entry.
        if filename or disposition == "attachment":
            payload = part.get_payload(decode=True)
            size = len(payload) if payload else 0
            attachments.append({
                "name": _clean(unquote(str(filename))) or "(unnamed)",
                "mime": ctype,
                "size": size,
            })

    # Sibling `<msg>_files/` directory (the maildir's attachment store).
    sibling_files = []
    files_dir = path.with_name(path.name + "_files")
    if files_dir.is_dir():
        for f in sorted(files_dir.iterdir()):
            sibling_files.append({
                "name": f.name,
                "size": f.stat().st_size if f.is_file() else 0,
            })

    subject = _clean(_hdr(msg, "Subject"))
    references = _clean(_hdr(msg, "References"))
    in_reply_to = _clean(_hdr(msg, "In-Reply-To"))
    return {
        "filename": rel,
        "sender": sender,
        "sender_addr": sender_addr,
        "recipients": recipients,
        "date": _parse_date(_hdr(msg, "Date")),
        "subject": subject,
        "message_id": _clean(_hdr(msg, "Message-ID")),
        "references": references,
        "in_reply_to": in_reply_to,
        "body": body,
        "body_content_type": body_content_type,
        "attachments": attachments,
        "sibling_files": sibling_files,
        "parseable": True,
    }


def parse_one(item):
    """Pool worker: unpack the (custodian, folder, msg_path, rel) tuple."""
    custodian, folder, msg_path, rel = item
    row = parse_message(msg_path, rel)
    row["custodian"] = custodian
    row["folder"] = folder
    parts = rel.split("/")
    # Thread provenance: the full directory chain containing the message
    # (<custodian>/<folder>/<subdirs>), globally unique per directory.
    # Previously this was msg_path.name — the message FILE name — which made
    # every "thread" a singleton and broke thread-level analysis.
    row["thread"] = "/".join(parts[:-1])
    return row


def iter_messages(maildir: Path, limit: int | None = None):
    """Yield (custodian, folder, msg_path, rel_path) in sorted order.

    The CMU maildir is ``maildir/<custodian>/<folder>/<...nested...>/<msg>``
    — messages sit at *variable* depths (3..7 levels below the root), so the
    walk recurses through every subfolder. Files inside ``<msg>_files/``
    attachment stores are skipped (they are recorded as sibling_files in the
    message's own row instead).
    """
    if not maildir.is_dir():
        return
    count = 0
    for custodian in sorted(p for p in maildir.iterdir() if p.is_dir()):
        for folder in sorted(p for p in custodian.iterdir() if p.is_dir()):
            for msg_path in _walk_files(folder):
                if not msg_path.is_file():
                    continue
                rel = msg_path.relative_to(maildir).as_posix()
                yield custodian.name, folder.name, msg_path, rel
                count += 1
                if limit and count >= limit:
                    return


def _walk_files(folder: Path):
    """Yield every message file under a custodian's folder, sorted."""
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        # Skip attachment stores (their files are the message's sibling_files).
        dirs[:] = [d for d in dirs if not d.endswith("_files")]
        for f in sorted(files):
            yield Path(root) / f


def main_with_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maildir", type=Path, default=MAILDIR,
                        help=f"Maildir root (default: {MAILDIR})")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"Output JSONL (default: {DEFAULT_OUT})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Parse at most N messages (smoke testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count messages and print the plan without writing")
    args = parser.parse_args(argv)

    if not args.maildir.is_dir():
        parser.error(f"maildir not found: {args.maildir} — run acquire_enron.py first")

    total = sum(1 for _ in iter_messages(args.maildir, args.limit))
    print(f"Maildir: {args.maildir}")
    print(f"Messages (limit {args.limit if args.limit else 'none'}): {total}")
    if args.dry_run:
        print("Dry run — no index written.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    n_procs = int(os.environ.get("CORPUS_PROCS", "8"))
    with args.out.open("w", encoding="utf-8") as fh:
        if n_procs <= 1:
            for custodian, folder, msg_path, rel in iter_messages(args.maildir, args.limit):
                row = parse_one((custodian, folder, msg_path, rel))
                if row.get("parseable"):
                    n_ok += 1
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        else:
            with Pool(n_procs) as pool:
                for row in pool.imap(
                        parse_one, iter_messages(args.maildir, args.limit),
                        chunksize=200):
                    if row.get("parseable"):
                        n_ok += 1
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {total} rows -> {args.out} ({n_ok} parseable)")
    return 0


def main() -> int:
    return main_with_args(sys.argv[1:])


if __name__ == "__main__":
    main()