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
# ``partner`` and ``legal`` are deliberately EXCLUDED: they are ordinary
# corporate vocabulary (a "partner-news@amazon.com" newsletter, or an Enron
# analyst's emails about "legal" topics) and produced false-positive
# attorney-demand rows.
ATTORNEY_NAME_PATTERNS = [
    r"\besq\.?\b",
    r"\battorney",
    r"\bcounsel",
    r"\blaw\s+offices?\b",
    r"\blawyer",
    r"\bj\.?\s?d\.?\b",
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

# Demand forms (subject or body). These are LEGAL demand markers — the
# generic energy-market word "demand" (e.g. "demand charges", "demand
# reduction", "demand for computers", "demand for petro products") is
# deliberately excluded: it is ordinary market content, not a demand letter,
# and routing ~15k market emails into `demand` was the original over-fire.
# Billing-reminder vocabulary (OVERDUE, PAST DUE, DELINQUENT, DEBT
# COLLECTION, PAYMENT IS DUE) is also excluded: an "access request approval
# is overdue" email is an internal reminder, not a demand. A legal demand is
# a demand FOR something actionable (payment / arbitration / damages /
# performance / relief), a demand letter, a cease-and-desist, a
# litigation/notice-of-default form, or an explicit payment demand.
DEMAND_MARKERS = [
    "DEMAND LETTER",
    "LETTER OF DEMAND",
    "DEMAND FOR PAYMENT",
    "DEMAND FOR ARBITRATION",
    "DEMAND FOR DAMAGES",
    "DEMAND FOR SPECIFIC PERFORMANCE",
    "DEMAND FOR RELIEF",
    "CEASE AND DESIST",
    "CEASE-AND-DESIST",
    "LITIGATION HOLD",
    "LEGAL HOLD",
    "NOTICE OF DEFAULT",
    "NOTICE OF BREACH",
    "NOTICE TO CURE",
    "FINAL NOTICE",
    "FINAL DEMAND",
    "IMMEDIATE PAYMENT",
    "IMMEDIATE PAYMENT IS REQUIRED",
    "REMIT PAYMENT",
    "ULTIMATUM",
    "BREACH OF CONTRACT",
    "BREACH OF THE AGREEMENT",
]

# Press-release forms. Matched on the SUBJECT or on the message's own opening
# lines (first 200 chars) — a forward/reply whose BODY carries a forwarded
# "FOR IMMEDIATE RELEASE" original is NOT a press release, it is a reply.
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

# Voicemail transcription markers — the message's OWN transcription header.
# "voice message" / "voice mail" references inside ordinary emails (e.g.
# "the voice message you left me") are not voicemails, so only the
# transcription-header forms count. "MESSAGE FROM" is deliberately excluded:
# a "Message from John and Louise" reply is an email, not a voicemail.
VOICEMAIL_MARKERS = [
    "THIS IS A VOICE MAIL",
    "VOICEMAIL TRANSCRIPTION",
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
# Marketing-clickbait markers (Dear + Sincerely is the form, but the
# "CONGRATULATIONS YOU WON" / "CLICK HERE NOW" body is a marketing blast, not
# a letter). Kept out of `letter` so the subclass stays meaningful.
_MARKETING_RE = [
    re.compile(r"\bCLICK HERE NOW\b", re.IGNORECASE),
    re.compile(r"\bCONGRATULATIONS YOU (WON|HAVE WON)\b", re.IGNORECASE),
    re.compile(r"\bYOU HAVE BEEN SELECTED\b", re.IGNORECASE),
    re.compile(r"\bFREE TRIAL ISSUE\b", re.IGNORECASE),
    re.compile(r"\bACT NOW\b", re.IGNORECASE),
]
# "DEMAND FOR" needs a word boundary: "DEMAND FOR" is a legal demand, but
# "CAPACITY" contains "CAP" + "ACITY" and "2.7 TCF" contains "CF" — the
# plain substring matched "AP" inside "CAPACITY" (capacity, receipt point
# capacity, ...) and "CF" inside "TCF" (a natural-gas volume unit), routing
# ~1.5k market emails into `demand`. The \b boundary fixes both.
_DEMAND_RE = [re.compile(r"\b" + re.escape(m) + r"\b", re.IGNORECASE) for m in DEMAND_MARKERS]

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


_FORWARD_MARKERS = [
    "-----original message-----",
    "-----forwarded by",
    "=======================",
    "-----original email-----",
    # The CMU corpus' own forward/reply separator is a 30-dash line —
    # "---------------------- FORWARDED BY ... ON <date> ---------------------------".
    "---------------------- forwarded by",
    "---------------------- forwarded by",
]
# Outlook's "inline attachment follows" forward header:
#   "COOPER, SEAN" <COOPERS@EPENERGY.COM> ON 07/11/2000 08:03:41 PM
#   TO: ...
#   CC: ...
#   SUBJECT: ...
_FORWARD_HEADER_RE = re.compile(
    r'^\s*"[^"]+"\s+.*\bON\s+\d{1,2}/\d{1,2}/\d{4}\b',
    re.IGNORECASE | re.MULTILINE)


def _strip_forwarded(body: str) -> str:
    """Drop the forwarded-original tail of a reply/forward.

    A reply that carries a forwarded memorandum / demand letter / press
    release / notice is a reply, not a memo / demand / release / notice —
    the markers belong to the original, not this message.
    """
    if not body:
        return ""
    low = body.lower()
    cut = len(body)
    for m in _FORWARD_MARKERS:
        idx = low.find(m)
        if idx != -1:
            cut = min(cut, idx)
    mh = _FORWARD_HEADER_RE.search(body)
    if mh:
        cut = min(cut, mh.start())
    return body[:cut]


def _own_head(row: dict, limit: int = 1500) -> str:
    """Subject + the message's OWN body, forwarded-original tail stripped."""
    body = _strip_forwarded(row.get("body") or "")
    return " ".join((_subject(row), body[:limit])).upper()


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
    own_head = _own_head(row)

    # Meeting requests (calendar content type wins over everything).
    ctypes = {a.get("mime") for a in row.get("attachments") or []}
    if "text/calendar" in ctypes or _has_any(own_head, _OPENERS_RE["meeting"]):
        return "meeting_request", "calendar content-type or meeting markers"

    if _has_any(own_head, _OPENERS_RE["voicemail"]):
        return "voicemail", "voicemail transcription markers"

    if _has_any(own_head, _OPENERS_RE["press"]):
        return "press_release", "press-release forms"

    # Demands — checked before notices because demands often self-identify
    # as notices (e.g. "NOTICE OF DEFAULT" is a demand).
    if _has_any(own_head, _DEMAND_RE) or _has_any(subject, _DEMAND_RE):
        is_atty, evidence = _is_attorney(row)
        if is_atty:
            return "attorney_demand", f"demand markers + {evidence}"
        return "demand", "demand markers"

    if _has_any(own_head, _OPENERS_RE["notice"]) or _has_any(subject, _OPENERS_RE["notice"]):
        return "notice", "notice forms"

    # Memoranda. Matched on the SUBJECT or on the message's OWN opening
    # (forwarded-original tail stripped) — a forwarded memorandum buried in
    # a reply's body is a reply, not a memo.
    memo_open = any(_has_any(own_head, [r]) for r in _OPENERS_RE["memo"]) or \
        _has_any(subject, _OPENERS_RE["memo"])
    memo_block = bool(MEMO_HEADER_BLOCK_RE.search(own_head))
    if memo_open or memo_block:
        return "memo", "memorandum header block or openers"

    # Formal letters: salutation + closing + external sender. A "RE:" subject
    # is a letter reference line ("Regarding"), not a reply, so only FW:/FWD:
    # prefixes disqualify the letter form (a forwarded email chain).
    # Marketing spam is also letter-form (Dear + Sincerely), so clickbait
    # markers are excluded: "CONGRATULATIONS YOU WON", "CLICK HERE NOW" etc.
    # are marketing, not a letter — and keeping them out of `letter` keeps
    # the subclass meaningful for the pipeline's attorney-correspondence use.
    sender_addr = (row.get("sender_addr") or "").lower()
    external = "enron.com" not in sender_addr and not sender_addr.endswith("@enron")
    letter_open = _has_any(own_head, _OPENERS_RE["letter"])
    letter_close = _has_any(own_head, _LETTER_CLOSERS_RE)
    marketing = _has_any(own_head, _MARKETING_RE)
    if letter_open and letter_close and external and not marketing and not re.match(
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