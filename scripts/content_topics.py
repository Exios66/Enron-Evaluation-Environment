#!/usr/bin/env python3
"""Content-topic taxonomy + heuristic labeler for the Enron corpus.

The third-level ``content_topic`` dimension for correspondence rows
(KANBAN-079): WHAT the email body actually contains, independent of its
form (the ``correspondence_subclasses`` dimension answers what KIND of
document it is; this answers what it is ABOUT). The sorter and the
correspondence specialist use it as ground truth for content-aware routing;
the dataset viewer exposes it for human auditing.

Keys (first-match-wins — order is load-bearing, do not reorder):

- ``scheduling``        — meeting requests, calendar coordination, appointments
- ``hr_personnel``      — hiring, interviews, reviews, comp/benefits, terminations
- ``legal_contracts``   — contracts/agreements, NDAs, litigation, disputes
- ``finance_earnings``  — earnings/results, budgets, accounting, financial reports
- ``energy_market``     — trading, gas/power markets, deals, capacity, pipelines
- ``regulatory``        — FERC/SEC/regulator filings, compliance, tariffs
- ``it_systems``        — IT/systems, outages, access, software, hardware
- ``travel_logistics``  — flights, hotels, trips, expense reports
- ``marketing_clients`` — client relations, pitches, press/newsletters, events
- ``announcements``     — company-wide news, org changes, all-hands blasts
- ``general_business``  — default for ordinary business email

Labeling is a deterministic pure function of the row (subject + own-body,
forwarded-original tail stripped via the shared ``_strip_forwarded``) so
rebuilds are byte-for-byte reproducible.

Honest gaps (documented, not hidden):
- Single-topic assignment only: multi-topic emails get their highest-priority
  topic (priority = specificity: a scheduling request inside a legal thread
  labels ``legal_contracts`` when the legal markers dominate the head scan).
- Head-window scanning (first ~2000 chars of the stripped body + subject):
  topics introduced late in long bodies are missed.
- English corporate vocabulary of 2000-2001 Enron; modern slang/marketing
  phrasing may fall through to ``general_business``.
"""

from __future__ import annotations

import re

try:  # sibling import when run inside the repo scripts/ dir
    from correspondence_subclasses import _strip_forwarded  # noqa: F401
except ImportError:  # package-style import from publishers/tests
    import importlib.util
    from pathlib import Path

    _spec = importlib.util.spec_from_file_location(
        "correspondence_subclasses",
        Path(__file__).resolve().parent / "correspondence_subclasses.py")
    if _spec is None or _spec.loader is None:
        raise ImportError("cannot load sibling correspondence_subclasses.py")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _strip_forwarded = _mod._strip_forwarded

# ---------------------------------------------------------------------------
# Topic markers. Every pattern is anchored on distinctive vocabulary that
# survived spot-checking against the corpus; generic words ("meeting" alone)
# are deliberately avoided where they over-fire.
# ---------------------------------------------------------------------------

TOPIC_MARKERS: dict[str, list[str]] = {
    # Scheduling: calendar/appointment machinery. "meet" alone over-fires
    # ("quarterly meeting results") so require meeting + logistics verbs/nouns.
    "scheduling": [
        r"\b(?:calendar|appointment|reschedul\w+|schedul\w+ (?:a|the|our) )",
        r"\b(?:set up|arrange|book)\b.{0,20}\b(?:call|conference|meeting|visit)\b",
        r"\b(?:meeting|call|visit)\b.{0,30}\b(?:time|date|slot|works? for you|confirm)",
        r"\bat your convenience\b|\boffice hours\b|\bi'?ll be in (?:town|the office)\b",
    ],
    # HR: people-processes. "review" alone is banned (perf review vs document
    # review vs market review); anchor on HR nouns.
    "hr_personnel": [
        r"\b(?:resume[sv]?|c\.?v\.?s?|cover letter|interview\w*|candidate[s]?\b|job (?:opening|posting|offer))",
        r"\b(?:performance|salary|compensation|benefits?|401\(k\)|payroll|bonus)\b.{0,30}\b(?:review|plan|increase|package|enroll)",
        r"\bnew hire[s]?\b|\bonboarding\b|\bhiring\b|\btermination\b|\bgave notice\b|\btwo weeks notice\b",
        r"\b(?:vacation|pto|personal time|sick leave)\b|\bopen enrollment\b|\bees?\b (?=.*enrol)",
    ],
    # Legal: contracts & disputes. "agreement" needs a qualifier to avoid
    # ordinary usage; NDA/litigation markers are distinctive enough alone.
    "legal_contracts": [
        r"\bnon-?disclosure\b|\bNDA\b|\bmutual confidentiality\b",
        r"\blitigation\b|\blawsuit\b|\bplaintiff[s]?\b|\bdefendant[s]?\b|\bcourt (?:order|ruling|filing)\b",
        r"\bmaster agreement\b|\bpurchase agreement\b|\bcontract(?:ual)? (?:terms|dispute|obligation|negotiation)",
        r"\blegal (?:department|counsel|opinion|advice|issue|matter)\b",
        r"\bterms and conditions\b|\bindemnif\w+|\bbreach(?:ed)? (?:of )?(?:the )?(?:contract|agreement)\b",
    ],
    # Finance/earnings. "budget" + business context; EPS/revenue are strong.
    "finance_earnings": [
        r"\b(?:q[1-4]|first|second|third|fourth|full[- ]year) (?:19|20)\d{2} (?:earnings|results|revenue)",
        r"\bearnings (?:release|report|announcement|per share)\b|\bEPS\b",
        r"\brevenue[s]? (?:grew|growth|declined|forecast|projection|target)",
        r"\b(?:annual|operating|capital|departmental) budget\b|\bbudget (?:process|cycle|forecast|review|cut)\b",
        r"\baccounts? (?:receivable|payable)\b|\bbalance sheet\b|\bincome statement\b|\bcash flow\b",
    ],
    # Energy market: THE Enron bulk topic — trading, gas/power, deals.
    "energy_market": [
        r"\bnatural gas\b|\bgas (?:market|price|supply|daily|nomination|transport)\b|\bpower market\b",
        r"\b(?:electricity|power|gas) (?:trading|trader|desk|deal|swap|forward|future)",
        r"\bcapacity\b|\bTCF\b|\bBtu\b|\bmmbtu\b|\bpipeline\b|\btap\b.{0,20}\bexpansion\b",
        r"\b(?:long|short) position\b|\bhedg(?:e|ing)\b|\bspot (?:market|price)\b",
        r"\bwestern (?:power|markets?)\b|\bcalifornia (?:power|iso|px)\b|\bwholesale (?:power|gas)\b",
        r"\b(?:enron|ews|ena) (?:north america|global|wholesale|energy services)\b",
    ],
    # Regulatory: agencies & filings.
    "regulatory": [
        r"\bFERC\b|\bSEC filing\b|\bCFTC\b|\bPUCT\b|\bpublic utility commission\b",
        r"\bcompliance (?:issue|matters?|requirement|filing)\b|\bregulat\w+ (?:filing|approval|proceeding|tariff)",
        r"\bform (?:10-?k|10-?q|8-?k|3|4|13[dD])\b",
    ],
    # IT/systems.
    "it_systems": [
        r"\b(?:server|network|laptop|desktop|printer|blackberry|palm pilot)s?\b.{0,30}\b(?:down|outage|upgrade|issue|problem|install|replace)",
        r"\bpassword\s*(?:reset|change|expire)\b|\blog ?in (?:problem|issue|fail)|\baccess (?:request|card|denied|revoked)",
        r"\b(?:outlook|lotus notes|windows nt|excel|powerpoint|access database)\b.{0,25}\b(?:crash|error|install|upgrade|training|help)\b",
        r"\bit (?:help ?desk|support|ticket)\b|\bsystem (?:maintenance|migration|outage|downtime)\b",
        r"\bhelp ?desk\b|\btech(nical)? support\b",
    ],
    # Travel/logistics.
    "travel_logistics": [
        r"\bflight\b|\bairfare\b|\bhotel reservation\b|\brental car\b|\b(?:check|fly)(?:ed|ing)? in(?:to)?\b.{0,15}\b(?:hotel|airport)",
        r"\bexpense report\b|\bexpenses?\b.{0,20}\b(?:submit|receipt|reimburse)",
        r"\btrip (?:to|itinerary|agenda)\b|\bitinerary\b|\btravel (?:plans?|arrangements?|authorization)\b",
    ],
    # Marketing/clients/events.
    "marketing_clients": [
        r"\b(?:client|customer) (?:relationship|meeting|visit|account|service)\b",
        r"\bpress release\b|\bmedia (?:inquiry|coverage|contact)\b|\bnewslett?er\b",
        r"\b(?:marketing|advertising|branding) (?:campaign|material|effort|plan)\b",
        r"\bsponsor(?:ship|ed by)\b|\btrade show\b|\bconference (?:sponsor|registration|booth)\b",
    ],
    # Announcements: company-wide news blasts.
    "announcements": [
        r"\b(?:pleased|excited|proud) to announce\b",
        r"\bcompany[- ]wide\b|\ball (?:enron|employee|staff|hands)\b|\b(?:organi[sz]ational|management) (?:change|structure|announcement)\b",
        r"\bwelcome (?:our|your) new\b.{0,30}\b(?:to the team|joining)\b",
        r"\bnew (?:vice president|vp|ceo|cfo|president)\b.{0,40}\b(?:effective|appointed|named)\b",
    ],
}

_TOPIC_RES = {k: [re.compile(p, re.IGNORECASE) for p in v]
              for k, v in TOPIC_MARKERS.items()}

# Priority order for tie-breaks: most specific/domain-critical wins. This is
# ALSO the iteration order for counting matches — a legal marker inside a
# scheduling-heavy legal thread still lands on legal_contracts.
TOPIC_PRIORITY = [
    "legal_contracts",       # litigation/disputes outrank everything they touch
    "regulatory",            # regulator-facing beats commercial
    "finance_earnings",
    "energy_market",
    "hr_personnel",
    "it_systems",
    "travel_logistics",
    "marketing_clients",
    "announcements",
    "scheduling",
]

TOPIC_KEYS = TOPIC_PRIORITY + ["general_business"]  # full key set incl. default

TOPIC_LABELS = {
    "scheduling": "Scheduling & Calendar Coordination",
    "hr_personnel": "HR & Personnel",
    "legal_contracts": "Legal & Contracts",
    "finance_earnings": "Finance & Earnings",
    "energy_market": "Energy Markets & Trading",
    "regulatory": "Regulatory & Compliance",
    "it_systems": "IT & Systems",
    "travel_logistics": "Travel & Logistics",
    "marketing_clients": "Marketing, Clients & Events",
    "announcements": "Company Announcements",
    "general_business": "General Business Correspondence",
}

_HEAD_WINDOW = 2000


def _own_body_head(row: dict, limit: int = _HEAD_WINDOW) -> str:
    """Subject + forwarded-tail-stripped body head, whitespace-collapsed."""
    body = _strip_forwarded(row.get("body") or "")[:limit]
    head = " ".join(((row.get("subject") or ""), body))
    return " ".join(head.split())


def label_content_topic(row: dict) -> tuple[str, str]:
    """Assign the content topic for an index/pipeline row.

    Ordered scoring (NOT first-marker-wins like subclasses): count distinct
    marker hits per topic across subject+body head, pick the highest-priority
    topic whose hit-count equals the max. Ties break toward the more specific
    domain (earlier in TOPIC_PRIORITY). Zero hits -> ``general_business``.

    Returns (topic_key, evidence).
    """
    if not row.get("parseable", True):
        return "general_business", "unparseable file"

    head = _own_body_head(row)

    hits: dict[str, int] = {}
    evidence_parts: dict[str, str] = {}
    for topic in TOPIC_PRIORITY:
        matched = []
        for pat in _TOPIC_RES[topic]:
            m = pat.search(head)
            if m:
                matched.append(m.group(0)[:40].lower())
        if matched:
            hits[topic] = len(matched)
            evidence_parts[topic] = "; ".join(sorted(set(matched))[:3])

    if not hits:
        return "general_business", "no specific topic markers; ordinary business content"

    best = max(hits.values())
    for topic in TOPIC_PRIORITY:  # priority-ordered tie-break
        if hits.get(topic) == best:
            return topic, f"{hits[topic]} marker hit(s): {evidence_parts[topic]}"

    raise AssertionError("unreachable: TOPIC_PRIORITY covers all hit keys")


def classify_topics(rows: list[dict]) -> dict[str, int]:
    """Label many rows; returns {topic_key: count} (all keys present)."""
    counts = {k: 0 for k in TOPIC_KEYS}
    for row in rows:
        counts[label_content_topic(row)[0]] += 1
    return counts


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            row = json.loads(fh.readline())
        key, ev = label_content_topic(row)
        print(f"{key} — {ev}")
