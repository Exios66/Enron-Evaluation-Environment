"""Tests for scripts/build_samples.py — the Markdown sample renderer.

No corpus data needed: synthetic index rows only (repo test law).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_samples import _esc_cell, _render_body, _slug, render_markdown


def _row(**overrides):
    row = {
        "filename": "allen-p/deleted_items/12.",
        "custodian": "allen-p",
        "folder": "deleted_items",
        "thread": "allen-p/deleted_items",
        "sender": "Phillip Allen",
        "sender_addr": "phillip.allen@enron.com",
        "recipients": [
            {"name": "Tracy Schuch", "addr": "tracy.schuch@enron.com", "role": "to"},
            {"name": "Marie Heard", "addr": "marie.heard@enron.com", "role": "cc"},
        ],
        "date": "2001-03-02T08:55:00-06:00",
        "subject": "Meeting request for Tuesday",
        "message_id": "<12345@enron.com>",
        "body": "Can we meet at 2pm on Tuesday?\n\nPhillip",
        "attachments": [],
        "parseable": True,
    }
    row.update(overrides)
    return row


class TestRenderBody:
    def test_plain_paragraphs_tidy(self):
        out = _render_body("line one\n\n\n\nline two")
        assert "line one\n\nline two" in out

    def test_quote_lines_become_blockquotes(self):
        out = _render_body("my reply\n> quoted from them\n>> nested")
        assert "> quoted from them" in out
        # Two quote levels render as "> > nested" (valid CommonMark nesting).
        assert "> > nested" in out
        assert out.startswith("my reply")

    def test_empty_body(self):
        assert _render_body("") == ""


class TestEscCell:
    def test_pipe_escaped(self):
        assert _esc_cell("a | b") == "a \\| b"

    def test_stripped(self):
        assert _esc_cell("  x  ") == "x"


class TestSlug:
    def test_keeps_maildir_provenance(self):
        row = _row()
        slug = _slug(row)
        assert slug.startswith("allen-p")
        assert " " not in slug and "/" not in slug


class TestRenderMarkdown:
    def test_header_table_complete(self):
        text = render_markdown(_row(), "email", "own-message in deleted_items")
        assert text.startswith("# Meeting request for Tuesday")
        assert "| From | Phillip Allen <phillip.allen@enron.com> |" in text
        assert "| To | Tracy Schuch <tracy.schuch@enron.com> |" in text
        assert "| Cc | Marie Heard <marie.heard@enron.com> |" in text
        assert "`email`" in text
        assert "| Custodian | allen-p |" in text
        assert "12345@enron.com" in text

    def test_cc_bcc_omitted_when_absent(self):
        row = _row(recipients=[{"name": "T", "addr": "t@x.com", "role": "to"}])
        text = render_markdown(row, "email", "ev")
        assert "| Cc |" not in text
        assert "| Bcc |" not in text

    def test_attachments_row(self):
        row = _row(attachments=[{"name": "plan.pdf", "mime": "application/pdf", "size": 10}])
        text = render_markdown(row, "email", "ev")
        assert "plan.pdf (application/pdf)" in text

    def test_body_section_renders(self):
        text = render_markdown(_row(), "email", "ev")
        assert "## Body" in text
        assert "meet at 2pm on Tuesday" in text

    def test_forwarded_section_split(self):
        # Outlook-style no-space marker — the shared labeler's convention.
        row = _row(body="My answer here.\n\n-----Forwarded by X\n> their quoted text")
        text = render_markdown(row, "email", "ev")
        assert "### Forwarded / quoted content" in text
        assert "their quoted text" in text
        assert "My answer here." in text
