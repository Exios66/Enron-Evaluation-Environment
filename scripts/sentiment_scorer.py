#!/usr/bin/env python3
"""Lexicon sentiment scorer for the Enron corpus (KANBAN-079).

Second enrichment ground-truth dimension beside ``content_topics``: a
per-email polarity score in [-1, 1] plus a derived label
(``negative`` / ``neutral`` / ``positive``). Deterministic, offline,
dependency-free — a pure function of the row's subject + own body
(forwarded-original tail stripped via the shared helper), so rebuilds are
reproducible byte-for-byte and every score has an audit trail.

Design (and its honest limits):
- Compact hand-weighted lexicon of business/finance English (~150 terms),
  tuned for 2000-era corporate email. NO learned model, NO external data —
  scores are transparent but shallow: sarcasm, long-range context and
  mixed-polarity nuance are out of reach for any lexicon method. Treat the
  score as a WEAK label / routing prior, not human judgment.
- Negation: a negator within the 2-token lookback flips the term's sign and
  damps magnitude x0.75 ("not good" < magnitude of "bad").
- Intensifiers/dampers in the same window scale magnitude
  ("very pleased", "slightly concerned").
- Normalization: raw sum s -> s / (|s| + 5), bounding to (-1, 1); ~5 net
  strong terms reaches +-0.5, ~15 reaches +-0.75. Zero lexicon hits -> 0.0.
- Label thresholds: >= +0.15 positive, <= -0.15 negative, else neutral
  (chosen so a single mild term cannot flip a mostly-informational email).

Politeness-formula control: ubiquitous corporate formulas ("thanks",
"regards") carry LOW weights (+0.25..+0.5) so ordinary courteous email stays
near zero instead of floating uniformly positive.
"""

from __future__ import annotations

import math
import re

try:  # sibling import when run inside the repo scripts/ dir
    from correspondence_subclasses import _strip_forwarded
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
# Lexicon: term -> weight in roughly [-3, 3]. Conservative weights on
# high-frequency polysemous words; strong weights only on unambiguous ones.
# ---------------------------------------------------------------------------

POSITIVE: dict[str, float] = {
    # strong, unambiguous
    "excellent": 3.0, "excellence": 2.0, "terrific": 3.0, "fantastic": 3.0,
    "wonderful": 3.0, "outstanding": 3.0, "superb": 3.0, "splendid": 2.5,
    "delighted": 3.0, "thrilled": 3.0, "congratulations": 3.0,
    "congrats": 3.0, "flawless": 3.0, "perfect": 2.5, "perfectly": 2.0,
    # moderately strong
    "great": 2.0, "pleased": 2.0, "happy": 2.0, "glad": 1.5,
    "appreciate": 1.5, "appreciated": 1.5, "appreciation": 1.5,
    "impressive": 2.0, "impressed": 2.0, "successful": 2.0,
    "successfully": 2.0, "succeeded": 2.0, "excited": 2.0, "exciting": 1.5,
    "good": 1.5, "nice": 1.5, "helpful": 1.5, "positive": 1.5,
    "confident": 1.5, "confidence": 1.0, "encouraging": 1.5,
    "favorable": 1.5, "profitable": 2.0, "profitability": 1.5,
    "growth": 1.5, "improved": 1.5, "improvement": 1.5, "improving": 1.5,
    "opportunity": 1.0, "opportunities": 1.0, "advantageous": 1.5,
    "valuable": 1.0, "win": 1.5, "winning": 1.5, "won": 1.5, "wins": 1.5,
    "agree": 1.0, "agreed": 1.0, "agreement": 0.5,  # "agreement" often just means contract
    "support": 0.5, "supported": 0.5,  # frequent neutral-ish usage
    "recommend": 1.0, "recommended": 1.0, "endorse": 1.5,
    # politeness formulas — deliberately weak
    "thanks": 0.25, "thank": 0.25, "thx": 0.25, "welcome": 0.5,
    "regards": 0.0,  # sign-off formula; present for completeness, zero weight
}

NEGATIVE: dict[str, float] = {
    # strong, unambiguous
    "unacceptable": -3.0, "outraged": -3.0, "furious": -3.0, "appalled": -3.0,
    "disgusted": -3.0, "betrayal": -3.0, "catastrophic": -3.0,
    "disaster": -3.0, "disastrous": -3.0, "fired": -2.5, "terminated": -1.5,
    "bankruptcy": -3.0, "bankrupt": -3.0, "fraud": -3.0, "fraudulent": -3.0,
    # moderately strong
    "terrible": -3.0, "horrible": -3.0, "awful": -3.0, "worst": -2.5,
    "bad": -1.5,
    "angry": -2.5, "upset": -2.0, "frustrated": -2.0, "frustrating": -2.0,
    "disappointed": -2.0, "disappointing": -2.0, "disappointment": -2.0,
    "concerned": -1.0, "concerns": -1.0, "concern": -0.75,  # corporate-speak frequency
    "worried": -1.5, "worry": -1.5, "worrying": -1.5, "afraid": -1.0,
    "problem": -1.0, "problems": -1.0, "difficulty": -1.0, "difficulties": -1.0,
    "trouble": -1.5, "issue": -0.75, "issues": -0.75,  # extremely frequent; kept mild
    "error": -1.0, "errors": -1.0, "mistake": -1.5, "mistakes": -1.5,
    "failed": -1.5, "failure": -2.0, "failures": -2.0, "failing": -1.5,
    "delay": -1.0, "delayed": -1.0, "delays": -1.0,
    "denied": -1.5, "rejected": -1.5, "refused": -1.5, "refusal": -1.5,
    "cancelled": -0.75, "canceled": -0.75, "postponed": -0.75,
    "overdue": -1.5, "penalty": -1.5, "penalties": -1.5,
    "violation": -2.0, "violations": -2.0, "breach": -2.0, "breached": -2.0,
    "lawsuit": -2.0, "litigation": -1.0, "complaint": -1.0,
    "complaints": -1.0, "complained": -1.0, "apologize": -0.75,
    "apology": -0.75, "apologized": -0.75, "regret": -1.5,
    "unfortunately": -0.75, "unable": -1.0, "shortfall": -2.0,
    "loss": -1.5, "losses": -1.5, "lost": -1.0, "layoff": -2.5,
    "layoffs": -2.5, "downsizing": -2.5, "crisis": -2.5, "deficit": -1.5,
    "decline": -0.75, "declined": -0.75, "declining": -1.0,
    "risk": -0.5, "risky": -1.0, "threat": -1.0,
}

# Multi-word phrases scanned on the whitespace-collapsed text.
PHRASES: dict[str, float] = {
    "look forward": 1.0,       # warm closing formula, mildly positive
    "well done": 2.5,
    "job well done": 3.0,
    "many thanks": 0.5,
    "good news": 1.5,
    "bad news": -1.5,
    "on track": 1.0,
    "behind schedule": -1.5,
    "ahead of schedule": 1.5,
    "meets expectations": 0.75,
    "exceeds expectations": 2.0,
    "below expectations": -2.0,
    "not acceptable": -3.0,    # explicit phrase (negation would catch it, be explicit)
    "no longer employed": -2.0,
    "please note that we have not received": -1.5,
}

NEGATORS = frozenset({
    "not", "no", "never", "cannot", "can't", "can't", "won't", "wouldn't",
    "didn't", "doesn't", "don't", "isn't", "wasn't", "aren't", "weren't",
    "haven't", "hasn't", "hadn't", "without", "hardly", "barely",
    "neither", "nor", "lack", "lacks", "lacking", "fails", "fail", "failed_to",
})

INTENSIFIERS = {
    "very": 1.5, "really": 1.4, "extremely": 2.0, "highly": 1.5,
    "incredibly": 1.8, "deeply": 1.6, "severely": 1.8, "totally": 1.5,
    "absolutely": 1.7, "completely": 1.6, "utterly": 1.8, "quite": 1.2,
    "particularly": 1.3, "especially": 1.3, "seriously": 1.5,
}

DAMPERS = {
    "slightly": 0.5, "somewhat": 0.6, "marginally": 0.5, "mildly": 0.5,
    "fairly": 0.7, "rather": 0.8, "possibly": 0.7, "perhaps": 0.7,
    "potentially": 0.7, "somewhat_of": 0.6,
}

_MODIFIER_WINDOW = 2          # tokens looked back for negators/intensifiers
_NEGATION_DAMP = 0.75         # magnitude multiplier when negated
_NORM_SMOOTHING = 5.0         # s / (|s| + k) normalizer
LABEL_THRESHOLD = 0.15

SENTIMENT_LABELS = ("negative", "neutral", "positive")

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z'’\-]*")


def _score_text(text: str) -> tuple[float, int, list[str]]:
    """Score one text. Returns (raw_sum, n_hits, matched_terms)."""
    tokens = _TOKEN_RE.findall(text.lower())
    total = 0.0
    hits = 0
    matched: list[str] = []

    def _apply(weight: float, idx: int) -> float:
        nonlocal hits, matched
        hits += 1
        matched.append(tokens[idx])
        mag = abs(weight)
        sign = 1.0 if weight > 0 else -1.0
        mult = 1.0
        for back in range(1, _MODIFIER_WINDOW + 1):
            j = idx - back
            if j < 0:
                break
            tok = tokens[j]
            if tok in NEGATORS:
                sign *= -1.0
                mult *= _NEGATION_DAMP
            elif tok in INTENSIFIERS:
                mult *= INTENSIFIERS[tok]
            elif tok in DAMPERS:
                mult *= DAMPERS[tok]
        return sign * mag * mult

    for i, tok in enumerate(tokens):
        w = POSITIVE.get(tok)
        if w is None:
            w = NEGATIVE.get(tok)
        if w:
            total += _apply(w, i)

    # phrase pass on the collapsed text (no negation window across phrases;
    # phrases carry their own polarity and were chosen to be self-contained)
    flat = " ".join(tokens)
    for phrase, w in PHRASES.items():
        if phrase in flat:
            hits += 1
            matched.append(f"'{phrase}'")
            total += w

    return total, hits, matched


def analyze_sentiment(text: str) -> dict:
    """Full analysis dict for one text: score, label, hit stats."""
    stripped = _strip_forwarded(text or "")
    raw, hits, matched = _score_text(stripped)
    if hits == 0 or raw == 0.0:
        score = round(0.0, 4)
        label = "neutral"
    else:
        score = round(raw / (abs(raw) + _NORM_SMOOTHING), 4)
        label = ("positive" if score >= LABEL_THRESHOLD
                 else "negative" if score <= -LABEL_THRESHOLD else "neutral")
    top = sorted(set(matched))[:6]
    return {
        "score": score,
        "label": label,
        "hits": hits,
        "raw_sum": round(raw, 3),
        "top_terms": top,
    }


def sentiment_for_row(row: dict) -> tuple[float, str, str]:
    """Public API for index/pipeline rows. Returns (score, label, evidence)."""
    body = (row.get("body") or "")
    head = " ".join(((row.get("subject") or ""), body))
    res = analyze_sentiment(head)
    ev = (f"{res['hits']} lexicon hit(s), net {res['raw_sum']:+.1f} "
          f"[{', '.join(res['top_terms'])}]" if res["hits"]
          else "no sentiment lexicon hits")
    return res["score"], res["label"], ev


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            row = json.loads(fh.readline())
        score, label, ev = sentiment_for_row(row)
        print(f"{score:+.4f} [{label}] — {ev}")
