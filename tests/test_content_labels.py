#!/usr/bin/env python3
"""Tests for the KANBAN-079 enrichment labelers.

Covers ``content_topics`` (topic taxonomy) and ``sentiment_scorer``
(lexicon polarity). Data-independent pure-function tests with synthetic
rows, matching the house harness pattern in ``test_labeler.py``.

Usage:
    pytest tests/test_content_labels.py -v
"""

from __future__ import annotations

import pathlib
import sys

# Allow importing sibling scripts regardless of cwd.
_repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_repo_root / "scripts"))

from content_topics import (
    TOPIC_KEYS,
    TOPIC_PRIORITY,
    classify_topics,
    label_content_topic,
)
from sentiment_scorer import (
    LABEL_THRESHOLD,
    SENTIMENT_LABELS,
    analyze_sentiment,
    sentiment_for_row,
)


# ---------------------------------------------------------------------------
# Helpers — tiny index-row builders (same shape as test_labeler._row)
# ---------------------------------------------------------------------------

def _row(subject: str = "", body: str = "", parseable: bool = True) -> dict:
    return {
        "parseable": parseable,
        "sender": "",
        "sender_addr": "",
        "subject": subject,
        "body": body,
        "attachments": [],
    }


# ===========================================================================
# Content topics
# ===========================================================================


class TestTopicCoverage:
    """Every topic key must be reachable by at least one synthetic row."""

    def test_scheduling(self):
        key, _ = label_content_topic(_row(
            subject="Lunch Thursday?",
            body="Can we get on your calendar next week? Does 2pm work for you?"))
        assert key == "scheduling"

    def test_hr_personnel(self):
        key, _ = label_content_topic(_row(
            subject="Interview schedule",
            body="The candidate will be on site Tuesday; please review his resume "
                 "before the interview."))
        assert key == "hr_personnel"

    def test_legal_contracts(self):
        key, _ = label_content_topic(_row(
            subject="NDA for the Miller deal",
            body="Legal counsel reviewed the mutual non-disclosure agreement; "
                 "litigation risk looks low."))
        assert key == "legal_contracts"

    def test_finance_earnings(self):
        key, _ = label_content_topic(_row(
            subject="Q1 2001 earnings",
            body="Draft earnings release attached; revenue grew 12% and EPS beat "
                 "the street."))
        assert key == "finance_earnings"

    def test_energy_market(self):
        key, _ = label_content_topic(_row(
            subject="Daily gas nomination",
            body="Natural gas prices moved at the spot market; capacity on the "
                 "pipeline is tight ahead of TCF flows."))
        assert key == "energy_market"

    def test_regulatory(self):
        key, _ = label_content_topic(_row(
            subject="FERC filing",
            body="The regulatory filing for the tariff change is due Friday; "
                 "compliance needs sign-off."))
        assert key == "regulatory"

    def test_it_systems(self):
        key, _ = label_content_topic(_row(
            subject="Password reset",
            body="My login fails after the server upgrade; can IT help desk "
                 "reset my access?"))
        assert key == "it_systems"

    def test_travel_logistics(self):
        key, _ = label_content_topic(_row(
            subject="Portland trip",
            body="Flight lands at 3; hotel reservation is confirmed and I'll "
                 "file the expense report after travel."))
        assert key == "travel_logistics"

    def test_marketing_clients(self):
        key, _ = label_content_topic(_row(
            subject="Client visit",
            body="The customer account team wants a press release draft before "
                 "the trade show booth walkthrough."))
        assert key == "marketing_clients"

    def test_announcements(self):
        key, _ = label_content_topic(_row(
            subject="Org news",
            body="We are pleased to announce a company-wide organizational "
                 "change effective Monday."))
        assert key == "announcements"

    def test_general_business_default(self):
        key, ev = label_content_topic(_row(
            subject="Notes from this morning",
            body="Sharing my notes from the discussion. Nothing urgent here."))
        assert key == "general_business"
        assert "no specific topic markers" in ev

    def test_unparseable_is_general(self):
        key, ev = label_content_topic(_row(parseable=False))
        assert key == "general_business"
        assert "unparseable" in ev


class TestTopicOrdering:
    """Priority + tie-break behavior."""

    def test_legal_outranks_scheduling(self):
        # scheduling markers present but legal dominates via specificity tie:
        # give legal 2 hits, scheduling 2 hits -> priority puts legal first.
        key, _ = label_content_topic(_row(
            subject="Deposition calendar",
            body="Litigation team needs the court filing date on the calendar; "
                 "please confirm the appointment works for you."))
        assert key == "legal_contracts"

    def test_higher_count_wins_within_priority_gap(self):
        # energy_market gets 3 hits, finance gets 1 -> energy wins despite
        # finance sitting earlier in TOPIC_PRIORITY? No: finance IS earlier;
        # max-count gating means finance (1) loses to energy (3).
        key, _ = label_content_topic(_row(
            subject="Gas daily",
            body="Natural gas nominations, power market spreads, pipeline "
                 "capacity — plus one budget note."))
        assert key == "energy_market"

    def test_forwarded_tail_stripped(self):
        # A reply whose OWN text is scheduling, quoting an original that was
        # a legal demand — the legal markers sit in the forwarded tail and
        # must not fire.
        body = ("Let's put the deposition prep on your calendar — does Tuesday "
                "at 2pm work for you? I'll confirm the appointment.\n"
                "-----Original Message-----\n"
                "CEASE AND DESIST. This letter constitutes DEMAND FOR PAYMENT "
                "and NOTICE OF DEFAULT regarding breach of contract.")
        key, _ = label_content_topic(_row(subject="RE: Meeting", body=body))
        assert key == "scheduling", "forwarded legal tail leaked into scoring"

    def test_deterministic(self):
        row = _row(subject="NDA review",
                   body="Legal counsel flagged litigation exposure.")
        first = label_content_topic(row)
        second = label_content_topic(dict(row))
        assert first == second

    def test_evidence_names_hits(self):
        _, ev = label_content_topic(_row(
            subject="", body="FERC filing due; compliance sign-off needed."))
        assert "ferc" in ev.lower()

    def test_key_set_complete_and_consistent(self):
        # TOPIC_KEYS == priority list + default; labels cover all keys.
        from content_topics import TOPIC_LABELS
        assert set(TOPIC_KEYS) == set(TOPIC_LABELS.keys())
        assert len(TOPIC_KEYS) == len(set(TOPIC_KEYS))

    def test_classify_topics_all_keys_present(self):
        counts = classify_topics([
            _row(body="FERC filing"),
            _row(body="Natural gas spot market"),
            _row(body="plain note"),
        ])
        assert sum(counts.values()) == 3
        assert set(counts.keys()) == set(TOPIC_KEYS)


# ===========================================================================
# Sentiment scorer
# ===========================================================================


class TestSentimentPolarity:
    def test_strong_positive(self):
        res = analyze_sentiment("Excellent work — absolutely thrilled with the "
                                "outstanding results!")
        assert res["label"] == "positive"
        assert res["score"] >= LABEL_THRESHOLD

    def test_strong_negative(self):
        res = analyze_sentiment("This is unacceptable. A complete disaster — "
                                "I'm furious about the breach.")
        assert res["label"] == "negative"
        assert res["score"] <= -LABEL_THRESHOLD

    def test_informational_neutral(self):
        res = analyze_sentiment(
            "The meeting is at 3pm in the conference room on the fourth floor.")
        assert res["label"] == "neutral"
        assert res["score"] == 0.0

    def test_politeness_formula_stays_neutral(self):
        # ubiquitous courteous formula must NOT float ordinary mail positive
        res = analyze_sentiment("Thanks for the update, regards.")
        assert abs(res["raw_sum"]) / (abs(res["raw_sum"]) + 5) < LABEL_THRESHOLD
        assert res["label"] == "neutral"

    def test_empty_text(self):
        res = analyze_sentiment("")
        assert res["score"] == 0.0 and res["label"] == "neutral"


class TestSentimentModifiers:
    def test_negation_flips_sign(self):
        good = analyze_sentiment("good")
        not_good = analyze_sentiment("not good")
        assert good["raw_sum"] > 0 > not_good["raw_sum"]

    def test_negation_damps_magnitude(self):
        plain_bad = analyze_sentiment("bad")
        not_good = analyze_sentiment("not good")   # same |weight| 1.5, negated
        assert (abs(not_good["raw_sum"])
                < abs(plain_bad["raw_sum"]) * 0.75 + 1e-9)

    def test_intensifier_scales(self):
        pleased = analyze_sentiment("pleased")
        very_pleased = analyze_sentiment("very pleased")
        assert abs(very_pleased["raw_sum"]) > abs(pleased["raw_sum"])

    def test_damper_shrinks(self):
        concerned = analyze_sentiment("concerned")
        slightly_concerned = analyze_sentiment("slightly concerned")
        assert abs(slightly_concerned["raw_sum"]) < abs(concerned["raw_sum"])

    def test_phrases_fire(self):
        res = analyze_sentiment("Well done on the launch — good news all around.")
        assert res["hits"] >= 2 and res["label"] == "positive"


class TestSentimentBoundsAndAPI:
    def test_always_bounded(self):
        texts = [
            "excellent perfect wonderful fantastic terrific outstanding",
            "disaster catastrophe fraud bankruptcy unacceptable outraged",
            "good bad good bad good bad",
        ]
        for t in texts:
            res = analyze_sentiment(t)
            assert -1.0 <= res["score"] <= 1.0

    def test_labels_are_the_canonical_triple(self):
        assert set(SENTIMENT_LABELS) == {"negative", "neutral", "positive"}

    def test_row_api_tuple_shape(self):
        row = {"subject": "Update", "body": "Delighted to report we won."}
        score, label, ev = sentiment_for_row(row)
        assert isinstance(score, float) and -1.0 <= score <= 1.0
        assert label in SENTIMENT_LABELS
        assert isinstance(ev, str) and ev

    def test_forwarded_tail_does_not_dominate(self):
        body = ("Sounds good to me.\n"
                "-----Original Message-----\n"
                "This is unacceptable, a disaster and an outrage. Fraud! "
                "Bankruptcy! Furious!")
        score, label, _ = sentiment_for_row({"subject": "RE: ok", "body": body})
        assert label != "negative", (
            f"forwarded angry tail leaked into own-message scoring: {score}")

    def test_deterministic_dict(self):
        t = "Very disappointed with the delay; unfortunately we missed it."
        first = analyze_sentiment(t)
        second = analyze_sentiment(t)
        assert first == second
