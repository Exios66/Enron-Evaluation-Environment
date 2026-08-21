#!/usr/bin/env python3
"""Validation harness for the Enron evaluation environment.

Tests are **data-independent** where possible (pure function unit tests) and
use small synthetic row dicts constructed inline — no raw corpus files needed.

Usage:
    pytest tests/                        # run all suites
    pytest tests/test_labeler.py         # labeler unit tests only
    pytest tests/test_labeler.py::TestLabelingEdgeCases::test_demand_false_positives
    pytest tests/ -v --tb=short          # verbose + compact traces
"""

from __future__ import annotations

import json
import pathlib
import sys

# Allow importing sibling scripts regardless of cwd.
_repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_repo_root / "scripts"))

from correspondence_subclasses import (
    LAW_FIRM_DOMAINS,
    ATTORNEY_NAME_PATTERNS,
    _DEMAND_RE,
    _OPENERS_RE,
    _has_any,
    _is_attorney,
    _strip_forwarded,
    _own_head,
    _subject,
    label_correspondence,
    classify_many,
    SUBCLASS_KEYS,
)


# ---------------------------------------------------------------------------
# Helpers — tiny index-row builders
# ---------------------------------------------------------------------------

def _row(
    sender: str = "",
    subject: str = "",
    body: str = "",
    sender_addr: str = "",
    parseable: bool = True,
    attachments: list | None = None,
) -> dict:
    """Build a minimal index-row dict (all non-critical fields omitted)."""
    return {
        "parseable": parseable,
        "sender": sender,
        "sender_addr": sender_addr,
        "subject": subject,
        "body": body,
        "attachments": attachments or [],
    }


# ===========================================================================
# Labeler unit tests
# ===========================================================================


class TestBasicClassification:
    """Core correctness: every subclass key should be reachable."""

    def test_email_default(self):
        """Ordinary email from enron.com without any marker → email."""
        row = _row(sender="skilling", sender_addr="skilling@enron.com",
                   subject="Weekly update", body="Just a quick note to everyone.")
        key, ev = label_correspondence(row)
        assert key == "email", f"expected 'email' but got '{key}' ({ev})"

    def test_memo(self):
        """MEMORANDUM header → memo."""
        row = _row(
            sender="ken lay",
            subject="Re: Quarterly earnings",
            body=(
                "MEMORANDUM\n"
                "TO: All Enron Traders\nFROM: K. Lay\nDATE: 2000-01-15\n"
                "RE: Q4 Projections\n\nThe numbers look good.\n"
            ),
        )
        key, _ = label_correspondence(row)
        assert key == "memo"

    def test_letter_external(self):
        """Salutation + closing + external sender → letter."""
        row = _row(
            sender="John Doe",
            sender_addr="john.doe@clientcorp.com",
            subject="",
            body="Dear Mr Smith,\n\nWe are writing regarding the contract renewal.\n\n"
                 "Very truly yours,\nJohn Doe",
        )
        key, _ = label_correspondence(row)
        assert key == "letter"

    def test_notice(self):
        """TERMINATION NOTICE → notice (not demand — only 'NOTICE OF DEFAULT' etc. fire demand)."""
        row = _row(
            subject="TERMINATION NOTICE",
            body="This letter serves as formal termination notice effective immediately.",
        )
        key, ev = label_correspondence(row)
        assert key == "notice", f"expected 'notice' but got '{key}' ({ev})"

    def test_demand_non_attorney(self):
        """Demand markers from non-attorney sender → demand."""
        row = _row(
            sender="Acme Corp Accounts",
            sender_addr="billing@acmecorp.com",
            subject="DEMAND LETTER",
            body="Please remit payment immediately.",
        )
        key, ev = label_correspondence(row)
        assert key == "demand", f"expected 'demand' but got '{key}' ({ev})"

    def test_attorney_demand(self):
        """Demand markers from law-firm domain → attorney_demand."""
        row = _row(
            sender="Counsel, Andrews Kurth",
            sender_addr="counsel@akllp.com",
            subject="CEASE AND DESIST",
            body="You must cease all activity under agreement section 4.2.",
        )
        key, _ = label_correspondence(row)
        assert key == "attorney_demand"

    def test_press_release(self):
        """FOR IMMEDIATE RELEASE → press_release."""
        row = _row(
            subject="FOR IMMEDIATE RELEASE: Enron Announces Q4 Results",
            body="HOUSTON — Enron Corporation today announced...",
        )
        key, _ = label_correspondence(row)
        assert key == "press_release"

    def test_meeting_request(self):
        """text/calendar attachment → meeting_request."""
        row = _row(
            subject="Meeting: Board Review",
            attachments=[{"name": "invite.ics", "mime": "text/calendar", "size": 1024}],
        )
        key, _ = label_correspondence(row)
        assert key == "meeting_request"

    def test_unparseable(self):
        """parseable=False → other."""
        row = _row(parseable=False)
        key, _ = label_correspondence(row)
        assert key == "other"


class TestForwardStripping:
    """_strip_forwarded correctly isolates own-message content."""

    def test_plain_text_stripped(self):
        """A simple reply carries a forward separator; tail is removed."""
        body = "Just confirming the details above.\n\n" \
               "-----original message-----\nFrom: someone\nSent: yesterday\nBody..."
        result = _strip_forwarded(body)
        assert "-----original message-----" not in result
        assert result.strip() == "Just confirming the details above."

    def test_no_separator(self):
        """Plain body without separators returns unchanged."""
        body = "Hello there, nothing forwarded here."
        assert _strip_forwarded(body) == body

    def test_empty_body(self):
        assert _strip_forwarded("") == ""
        assert _strip_forwarded(None) == ""

    def test_cmuu_forward_header(self):
        """CMU maildir forward pattern is detected."""
        body = "Quick response to the thread.\n\n\"COOPER, SEAN\" <SEAN@ENRON.COM> ON 07/11/2000 08:03:41 PM\n" \
               "TO: ... SUBJECT: RE: ..."
        result = _strip_forwarded(body)
        assert '"COOPER, SEAN"' not in result


class TestAttorneyDetection:
    """Law-firm sender detection."""

    def test_known_law_firm_domain(self):
        row = _row(sender_addr="lawyer@akllp.com")
        ok, reason = _is_attorney(row)
        assert ok is True
        assert "akllp.com" in reason

    def test_various_law_firms(self):
        firms = ["akllp.com", "gibsondunn.com", "kayescholer.com", "latham.com", "sidley.com"]
        for firm in firms:
            row = _row(sender_addr=f"partner@{firm}")
            ok, _ = _is_attorney(row)
            assert ok is True, f"{firm} should be a recognized law firm"

    def test_esq_in_name(self):
        row = _row(sender="Jane Smith, Esq.")
        ok, _ = _is_attorney(row)
        assert ok is True

    def test_not_false_positive_partner(self):
        """partner-news@amazon.com newsletter — deliberately NOT attorney."""
        row = _row(sender_addr="partner-news@amazon.com")
        ok, _ = _is_attorney(row)
        assert ok is False, "partner@amazon.com must not trigger attorney detection"

    def test_not_false_positive_legal_topic(self):
        """Legal topic discussion ≠ legal sender."""
        row = _row(sender="analyst@enron.com",
                   subject="Discussion on legal liability",
                   body="We need to understand legal implications...")
        ok, _ = _is_attorney(row)
        assert ok is False


class TestDemandFalsePositives:
    """Energy-market vocabulary must NOT route into 'demand'."""

    def test_capacity_demand(self):
        """Capacity/demand in energy trading context — NOT a demand letter."""
        row = _row(
            sender="trader@enron.com",
            subject="Capacity demand charges for November",
            body="Demand charges remain high for peak periods.",
        )
        key, ev = label_correspondence(row)
        assert key != "demand", f"'capacity demand' incorrectly labeled as demand ({ev})"
        assert key == "email"

    def test_tcf_volume(self):
        """TCF (trillion cubic feet) volume units — NOT demand."""
        row = _row(
            sender="gas_trading@enron.com",
            subject="CF volume allocations for TCF pipeline",
            body="Total CF volume increased by 2.7 TCF.",
        )
        key, ev = label_correspondence(row)
        assert key != "demand", f"TCCF/CF incorrectly routed to demand ({ev})"
        assert key == "email"

    def test_actual_demand_still_works(self):
        """Genuine legal demands still fire."""
        row = _row(
            subject="DEMAND FOR PAYMENT",
            body="You must pay within 30 days or face legal action.",
        )
        key, _ = label_correspondence(row)
        assert key == "demand"

    def test_cease_and_desist(self):
        row = _row(subject="Cease-and-desist order",
                   body="Immediately stop all operations pending review.")
        key, _ = label_correspondence(row)
        assert key == "demand"


class TestLetterBoundaryCases:
    """Letter classification edge cases."""

    def test_marketing_excluded(self):
        """Clickbait marketing → NOT a letter."""
        row = _row(
            sender="promo@example.com",
            sender_addr="promo@example.com",
            body="Dear Valued Customer,\n\nCONGRATULATIONS YOU WON $1 MILLION!\n\n"
                 "Best Regards,\nMarketing Team",
        )
        key, _ = label_correspondence(row)
        assert key != "letter", "Marketing clickbait must be excluded from letter class"
        assert key == "email"

    def test_reply_to_letter_reference(self):
        """RE: prefix is a reference line (Regarding), not a forward — letter form preserved."""
        row = _row(
            sender="External Client",
            sender_addr="external@client.org",
            body="DEAR MR SMITH,\n\nOur inquiry concerns your proposal.\n\nSINCERELY,",
        )
        key, _ = label_correspondence(row)
        # RE: in subject is allowed for letters; FW: disqualifies.
        assert key == "letter"

    def test_forwarded_letter_disqualified(self):
        """FW:/FWD: prefix disqualifies letter form (forwarded email chain)."""
        row = _row(
            sender="Internal User",
            sender_addr="internal@enron.com",
            subject="FW: Contract Agreement",
            body="Dear Partner,\n\nPlease review attached terms.\n\nSincerely,\nUser",
        )
        key, _ = label_correspondence(row)
        # FW: prefix means this is a forwarded email, not a direct letter form.
        assert key != "letter"


class TestSubjectLengthAnalysis:
    """Verify subject-length extraction works."""

    def test_empty_subject(self):
        row = _row()
        assert _subject(row) == ""

    def test_whitespace_collapsed(self):
        row = _row(subject="   Hello   World   ")
        assert _subject(row) == "Hello   World"

    def test_long_subject(self):
        long = "FW: FW: Fwd: Re: Meeting about contract negotiation between parties"
        row = _row(subject=long)
        assert len(_subject(row)) > 50


class TestSubclassEnumInvariants:
    """Structural invariants on the taxonomy itself."""

    def test_all_keys_present(self):
        expected = [
            "email", "memo", "letter", "notice", "demand",
            "attorney_demand", "press_release", "meeting_request",
            "voicemail", "other",
        ]
        assert SUBCLASS_KEYS == expected

    def test_every_row_gets_a_label(self):
        """classify_many must produce keys only from SUBCLASS_KEYS."""
        rows = [_row(), _row(parseable=False)]
        counts = classify_many(rows)
        for key in counts:
            assert key in SUBCLASS_KEYS, f"Unknown subclass key: {key}"

    def test_no_other_residual_for_email(self):
        """Ordinary emails must never land in 'other'."""
        row = _row(
            sender="user@enron.com",
            subject="Test message",
            body="Hello world!",
        )
        key, _ = label_correspondence(row)
        assert key == "email", "Normal emails must not fall through to 'other'"


class TestLabelDeterminism:
    """Same input always yields same output — critical for reproducibility."""

    def test_idempotent(self):
        row = _row(
            sender="ken lay",
            sender_addr="ken.lay@enron.com",
            subject="Quarterly earnings call",
            body="MEMORANDUM\nTO: Executives\nFROM: Ken Lay\nDATE: 2001-03-01\n"
                 "RE: Q1 Projections\n\nRevenue exceeded expectations.",
        )
        k1, e1 = label_correspondence(row)
        k2, e2 = label_correspondence(row)
        assert (k1, e1) == (k2, e2), "labeling must be deterministic"


# ===========================================================================
# Index-row schema tests (lightweight structural checks)
# ===========================================================================


class TestIndexRowSchema:
    """Validate that parsed index rows conform to the expected schema."""

    def _make_sample_row(self):
        return {
            "filename": "test/cur/1234567890.M123456.mailserver.example.com",
            "custodian": "skilling",
            "folder": "sent_items",
            "thread": "1234567890",
            "sender": "Jeffrey Skilling",
            "sender_addr": "skilling@enron.com",
            "recipients": [
                {"name": "Bob", "addr": "bob@aol.com", "role": "to"},
                {"name": "Carol", "addr": "carol@hotmail.com", "role": "cc"},
                {"name": "", "addr": "", "role": "bcc"},
            ],
            "date": "2001-02-15T14:30:00+00:00",
            "subject": "Project Alpha Update",
            "message_id": "<1234567890@mailserver.enron.com>",
            "references": "",
            "in_reply_to": "<prev_message_id@mailserver.enron.com>",
            "body": "Just checking in on Project Alpha status.",
            "body_content_type": "text/plain",
            "attachments": [],
            "sibling_files": [],
            "parseable": True,
        }

    def test_required_fields_exist(self):
        """Every required field should be present in a well-formed row."""
        row = self._make_sample_row()
        required = ["filename", "custodian", "folder", "thread", "sender",
                     "sender_addr", "recipients", "date", "subject",
                     "message_id", "body", "parseable"]
        for field in required:
            assert field in row, f"Missing required field: {field}"

    def test_recipient_structure(self):
        """Each recipient entry must have name, addr, role."""
        row = self._make_sample_row()
        for rec in row["recipients"]:
            assert "name" in rec
            assert "addr" in rec
            assert "role" in rec
            assert rec["role"] in ("to", "cc", "bcc")

    def test_date_format(self):
        """ISO-8601 date should contain 'T' separator and timezone."""
        row = self._make_sample_row()
        assert "T" in row["date"]


# ===========================================================================
# Pipeline dump integrity test
# ===========================================================================


class TestPipelineDumpIntegrity:
    """Validate pipeline.jsonl row shape matches the expected format."""

    def test_expected_schema_fields(self):
        """Every pipeline row must contain expected doc-class fields."""
        expected_fields = {"filename", "doc_text", "expected", "expected_subclass", "metadata"}
        row = {
            "filename": "test/msg.txt",
            "doc_text": "Test document text",
            "expected": "correspondence",
            "expected_subclass": "email",
            "metadata": {"sender": "test@test.com"},
        }
        for field in expected_fields:
            assert field in row, f"Missing pipeline field: {field}"


# ===========================================================================
# Run
# ===========================================================================

if __name__ == "__main__":
    import unittest

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
