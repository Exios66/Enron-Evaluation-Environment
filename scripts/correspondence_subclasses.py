#!/usr/bin/env python3
"""Correspondence subclass taxonomy + heuristic labeler for the Enron corpus.

The second-level ``expected_subclass`` dimension for the mailroom's
``correspondence`` doc class. The key set is DATA-NECESSITATED: it was
derived from the actual Enron corpus contents (subject-prefix clusters,
body markers, sender classes, MIME shapes) so that every correspondence in
the corpus maps to a key — ``email`` is the default for ordinary mail and
``other`` only catches genuinely unparseable/non-email files.

Keys:

- ``email``            — ordinary email correspondence (default for parseable mail)
- ``memo``             — interoffice memoranda (MEMORANDUM header blocks, TO/FROM/DATE/RE layouts)
- ``letter``           — formal letters (salutation/sign-off letter forms)
- ``notice``           — formal notices (litigation hold, termination, notice of ...)
- ``demand``           — demands / demand letters (payment, cease-and-desist, default)
- ``attorney_demand``  — demands sent by an attorney or law firm (the attorney-demand class)
- ``press_release``    — press/news releases distributed over email
- ``meeting_request``  — calendar invitations / meeting requests
- ``voicemail``        — voicemail transcriptions
- ``other``            — unparseable / not an email message

Labeling is deterministic (pure function of the index row) so rebuilds and
the spot-check sample agree byte-for-byte.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Law-firm / attorney sender detection (address domains + name patterns)
# ---------------------------------------------------------------------------

# Known law firms in the Enron corpus (domains seen in sender addresses).
LAW_FIRM_DOMAINS = {
    "akllp.com",            # Andrews Kurth
    "akingump.com",         # Akin Gump
    "bakermckenzie.com",
    "bakerbotts.com",       # Baker Botts
    "bfmllp.com",           # Bracewell & Patterson
    "bracewell.com",
    "chadbourne.com",
    "cravath.com",
    "davispolk.com",
    "dlapiper.com",
    "ey.com",               # (Ernst & Young legal arm — keep, marginal)
    "friedfrank.com",
    "gibsondunn.com",
    "goodwinlaw.com",
    "howrey.com",
    "hunton.com",           # Hunton & Williams
    "jacksonwalker.com",
    "jonesday.com",
    "kayescholer.com",
    "kirkland.com",
    "kslaw.com",            # King & Spalding
    "latham.com",           # Latham & Watkins
    "lw.com",
    "mayerbrown.com",
    "meyerfaller.com",      # Meyer, Faller, Weisman & Greenburg
    "mfwg.com",
    "milbank.com",
    "morganlewis.com",
    "omelveny.com",
    "orrick.com",
    "paulhastings.com",
    "porterhedges.com",     # Porter & Hedges
    "satterfieldlaw.com",
    "schiffhardin.com",
    "severson.com",
    "shearman.com",
    "sidley.com",
    "skadden.com",
    "sprlaw.com",           # Shook Hardy
    "ssd.com",
    "velaw.com",            # Vinson & Elkins
    "vinson-elkins.com",
    "whitecase.com",
    "winstead.com",
    "winston.com",
}

# Generic attorney markers in the sender display name or address local part.
ATTORNEY_NAME_PATTERNS = [
    r"\besq\.?\b",
    r"\battorney",
    r"\bcounsel",
    r"\blaw\s+offices?\b",
    r"\blawyer",
    r"\bpartner\b",
    r"\bj\.?\s?d\.?\b",
    r"\blegal\b",
    r"atty\b",
]

# ---------------------------------------------------------------------------
# Form / content markers
# ---------------------------------------------------------------------------

# Subject-line prefixes that mark the message as a reply/forward chain member.
THREAD_PREFIX_RE = re.compile(
    r"^\s*(?:re|fw|fwd|sv|r\s*:\s*fwd)\s*:\s*", re.IGNORECASE)

# Subject or body opens that identify a memorandum.
MEMO_OPENERS = [
    "MEMORANDUM",
    "INTEROFFICE MEMORANDUM",
    "INTER-OFFICE MEMORANDUM",
    "INTEROFFICE CORRESPONDENCE",
    "MEMO TO",
    "TO: ALL",
    "TO: ALL ENRON",
    "TO ALL ENRON",
]
MEMO_HEADER_BLOCK_RE = re.compile(
    r"^\s*TO:\s*.{0,80}\n\s*FROM:\s*.{0,120}\n\s*(?:CC|DATE|RE|SUBJECT):",
    re.MULTILINE | re.IGNORECASE)

# Formal-letter forms.
LETTER_OPENERS = [
    "DEAR ",
    "DEAR MR",
    "DEAR MS",
    "DEAR MRS",
    "DEAR DR",
]
LETTER_CLOSERS = [
    "VERY TRULY YOURS",
    "YOURS TRULY",
    "SINCERELY YOURS",
    "SINCERELY,",
    "REGARDS,",
    "BEST REGARDS,",
    "CORDIALLY,",
    "RESPECTFULLY,",
    "RESPECTFULLY SUBMITTED",
    "FAITHFULLY",
]

# Notice forms.
NOTICE_OPENERS = [
    "NOTICE OF",
    "LITIGATION HOLD",
    "LEGAL HOLD",
    "TERMINATION NOTICE",
    "NOTICE TO",
    "ADVICE OF",
    "FINAL NOTICE",
    "OFFICIAL NOTICE",
]

# Demand forms (subject or body).
DEMAND_MARKERS = [
    "DEMAND",
    "CEASE AND DESIST",
    "CEASE-AND-DESIST",
    "PAYMENT DEMAND",
    "DEMAND FOR",
    "LETTER OF DEMAND",
    "NOTICE OF DEFAULT",
    "NOTICE OF BREACH",
    "FINAL DEMAND",
    "IMMEDIATE PAYMENT",
    "IMMEDIATE PAYMENT IS REQUIRED",
    "PAYMENT IS DUE",
    "AMOUNT DUE",
    "OVERDUE",
    "PAST DUE",
    "DELINQUENT ACCOUNT",
    "COLLECTION",
    "ULTIMATUM",
    "REMEDY THIS",
    "BREACH OF CONTRACT",
    "BREACH OF THE AGREEMENT",
]

# Press-release forms.
PRESS_RELEASE_OPENERS = [
    "FOR IMMEDIATE RELEASE",
    "FOR RELEASE",
    "NEWS RELEASE",
    "PRESS RELEASE",
]

# Meeting / calendar markers.
MEETING_MARKERS = [
    "MEETING REQUEST",
    "MEETING INVITATION",
    "CALENDAR INVITATION",
    "OUTLOOK MEETING",
]

# Voicemail transcription markers.
VOICEMAIL_MARKERS = [
    "THIS IS A VOICE MAIL",
    "VOICEMAIL TRANSCRIPTION",
    "VOICE MAIL MESSAGE",
    "VOICE MESSAGE",
]

_OPENERS_RE = {name: [re.compile(re.escape(m), re.IGNORECASE) for m in ms]
               for name, ms in {
                   "memo": MEMO_OPENERS,
                   "letter": LETTER_OPENERS,
                   "notice": NOTICE_OPENERS,
                   "press": PRESS_RELEASE_OPENERS,
                   "meeting": MEETING_MARKERS,
                   "voicemail": VOICEMAIL_MARKERS,
               }.items()}
_LETTER_CLOSERS_RE = [re.compile(re.escape(m), re.IGNORECASE) for m in LETTER_CLOSERS]
_DEMAND_RE = [re.compile(re.escape(m), re.IGNORECASE) for m in DEMAND_MARKERS]

SUBCLASS_KEYS = [
    "email",
    "memo",
    "letter",
    "notice",
    "demand",
    "attorney_demand",
    "press_release",
    "meeting_request",
    "voicemail",
    "other",
]
SUBCLASS_LABELS = {
    "email": "Email",
    "memo": "Memorandum",
    "letter": "Letter",
    "notice": "Notice",
    "demand": "Demand",
    "attorney_demand": "Attorney Demand",
    "press_release": "Press Release",
    "meeting_request": "Meeting Request",
    "voicemail": "Voicemail",
    "other": "Other",
}


def _is_attorney(row: dict) -> tuple[bool, str]:
    """Attorney/law-firm sender detection from the index row."""
    addr = (row.get("sender_addr") or "").strip().lower()
    if addr:
        domain = addr.rsplit("@", 1)[-1] if "@" in addr else ""
        if domain in LAW_FIRM_DOMAINS:
            return True, f"law-firm domain {domain}"
        local = addr.split("@", 1)[0]
        for pat in ATTORNEY_NAME_PATTERNS:
            if re.search(pat, local):
                return True, f"attorney address pattern {pat}"
    name = (row.get("sender") or "").strip()
    for pat in ATTORNEY_NAME_PATTERNS:
        if re.search(pat, name):
            return True, f"attorney name pattern {pat}"
    return False, ""


def _subject(row: dict) -> str:
    return (row.get("subject") or "").strip()


def _head(row: dict, limit: int = 1500) -> str:
    """Subject + body head, whitespace-collapsed, for marker scanning."""
    body = (row.get("body") or "")[:limit]
    head = " ".join((_subject(row), body))
    return " ".join(head.split()).upper()


def _body_head(row: dict, limit: int = 1200) -> str:
    body = (row.get("body") or "")[:limit]
    return " ".join(body.split()).upper()


def _has_any(head: str, patterns: list) -> bool:
    return any(p.search(head) for p in patterns)


def label_correspondence(row: dict) -> tuple[str, str]:
    """Assign the correspondence subclass for an index row.

    Ordered checks (first match wins — the mailroom sorter convention):
    1. unparseable / empty -> ``other``
    2. meeting request (calendar content-type or meeting markers)
    3. voicemail transcription markers
    4. press-release forms
    5. demand markers -> ``attorney_demand`` when the sender is an attorney
       or law firm, else ``demand``
    6. notice forms
    7. memorandum forms (subject openers or the TO/FROM/RE header block)
    8. letter forms (salutation + closing) — but only when the message is
       not an ordinary email (no email-thread prefix, no enron-address
       sender) and the body is short/letter-like
    9. default ``email``

    Returns (key, evidence).
    """
    if not row.get("parseable"):
        return "other", "unparseable file"

    subject = _subject(row)
    body_head = _body_head(row)
    head = _head(row)

    # Meeting requests (calendar content type wins over everything).
    ctypes = {a.get("mime") for a in row.get("attachments") or []}
    if "text/calendar" in ctypes or _has_any(head, _OPENERS_RE["meeting"]):
        return "meeting_request", "calendar content-type or meeting markers"

    if _has_any(head, _OPENERS_RE["voicemail"]):
        return "voicemail", "voicemail transcription markers"

    if _has_any(head, _OPENERS_RE["press"]):
        return "press_release", "press-release forms"

    # Demands — checked before notices because demands often self-identify
    # as notices (e.g. "NOTICE OF DEFAULT" is a demand).
    if _has_any(head, _DEMAND_RE) or _has_any(subject, _DEMAND_RE):
        is_atty, evidence = _is_attorney(row)
        if is_atty:
            return "attorney_demand", f"demand markers + {evidence}"
        return "demand", "demand markers"

    if _has_any(head, _OPENERS_RE["notice"]) or _has_any(subject, _OPENERS_RE["notice"]):
        return "notice", "notice forms"

    # Memoranda.
    memo_open = any(_has_any(body_head, [r]) for r in _OPENERS_RE["memo"]) or \
        _has_any(subject, _OPENERS_RE["memo"])
    memo_block = bool(MEMO_HEADER_BLOCK_RE.search(body_head))
    if memo_open or memo_block:
        return "memo", "memorandum header block or openers"

    # Formal letters: salutation + closing + external sender. A "RE:" subject
    # is a letter reference line ("Regarding"), not a reply, so only FW:/FWD:
    # prefixes disqualify the letter form (a forwarded email chain).
    sender_addr = (row.get("sender_addr") or "").lower()
    external = "enron.com" not in sender_addr and not sender_addr.endswith("@enron")
    letter_open = _has_any(body_head, _OPENERS_RE["letter"])
    letter_close = _has_any(body_head, _LETTER_CLOSERS_RE)
    if letter_open and letter_close and external and not re.match(
            r"^\s*(?:fw|fwd)\s*:\s*", subject, re.IGNORECASE):
        return "letter", "salutation + closing, external sender"

    return "email", "ordinary email correspondence"


def classify_many(rows: list[dict]) -> dict:
    """Label a list of index rows; returns {key: count}."""
    from collections import Counter

    counts: Counter = Counter()
    for row in rows:
        key, _ = label_correspondence(row)
        counts[key] += 1
    return dict(counts)


def evidence_for(row: dict) -> tuple[str, str]:
    """Public wrapper returning (key, evidence) — used by the spot-check."""
    return label_correspondence(row)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        import json

        with open(sys.argv[1], encoding="utf-8") as fh:
            row = json.loads(fh.readline())
        key, ev = label_correspondence(row)
        print(f"{key} — {ev}")