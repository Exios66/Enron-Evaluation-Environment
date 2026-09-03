# AGENTS.md — Agent Operational Guide

**Repository:** Enron-Evaluation-Environment
**Purpose:** EDA and pipeline dataset production for the CMU Enron email corpus.
**Last updated:** 2026-08-23

---

## 🏛️ Governed Repositories (Ecosystem)

This repo is the **correspondence data-production node** of a governed evaluation
family under [Exios66](https://github.com/Exios66). Artifacts flow downstream;
nothing flows back without a versioned handoff.

| Repo | Role | Coupling |
|---|---|---|
| [`llm-mailroom`](https://github.com/Exios66/llm-mailroom) | Multi-agent legal-document intake pipeline; owns the doc-class taxonomy (`correspondence`, `contract`, `merger_agreement`, `corporate_record`) this repo labels against | Upstream taxonomy governor |
| **Enron-Evaluation-Environment** (this repo) | Full-corpus EDA + stratified `correspondence` dataset production for the CMU Enron corpus | — |
| [`llm-entity-extraction`](https://github.com/Exios66/llm-entity-extraction) | Training/eval environment for legal document entity extraction & classification; consumes `pipeline.jsonl` via `build_docclass_merged.py` + the sorter's subclass dimension | Direct downstream consumer |
| [`llm-dojo-scoring`](https://github.com/Exios66/llm-dojo-scoring) | Scoring environment; Langfuse mirror hosts the `mailroom-enron-correspondence` dataset | Downstream scoring mirror |
| [`atticus-investigation`](https://github.com/Exios66/atticus-investigation) | LegalBench prompt-engineering eval pipeline (prompt versions × models via OpenRouter + Braintrust) | Adjacent eval environment |

**Sync obligation:** when the labeler taxonomy (`correspondence_subclasses.py`)
changes here, mirror the enum into `llm-entity-extraction`'s sorter
(`SUBCLASS_DIMENSIONS`) and re-run its Langfuse sync — see
[`reports/pipeline/README.md`](reports/pipeline/README.md).

---

## 🚀 First-Time Setup (One Shot)

```bash
# 1. Clone & enter
git clone https://github.com/Exios66/Enron-Evaluation-Environment.git
cd Enron-Evaluation-Environment

# 2. Acquire the raw corpus (~423 MB tarball, auto-extracts to data/raw/maildir/)
python scripts/acquire_enron.py

# 3. Build the corpus index
python scripts/build_corpus_index.py

# 4. Run EDA → reports/eda/
python scripts/eda/explore_enron.py

# 5. Build pipeline sample
python scripts/build_pipeline_dump.py

# 6. Validate
pytest tests/ -v    # 74/74 expected
```

All data files live in `data/` which is gitignored. Index is ~500MB+ JSONL; pipeline dump is a stratified sample subset.

---

## Repo Structure (Quick Reference)

```
scripts/
├── correspondence_subclasses.py    ← SHARED labeler (imported by all tools)
├── acquire_enron.py                ← Download + extract CMU tarball
├── build_corpus_index.py           ← Parse maildir → data/enron/index.jsonl
├── dedupe.py                       ← Exact-duplicate removal → index.unique.jsonl
├── build_pipeline_dump.py          ← Stratified sample → pipeline.jsonl
├── spot_check.py                   ← Draw review sample → CSV
├── publish_hf_dataset.py           ← HF Hub publisher → Lucius-Morningstar/enron-correspondence
└── eda/
    ├── explore_enron.py            ← Full EDA → reports/eda/{report.md, findings.md}
    └── explore_subclasses.py       ← Subclass discovery analysis
.opencode/skills/hf-dataset-publish/ ← SKILL.md runbook for the Hub upload (agents: load it first)
tests/                              ← 74 unit tests in tests/test_labeler.py + tests/test_content_labels.py (no corpus data needed)
reports/
├── eda/                            ← EDA reports + figures (committed)
│   ├── final_report.md             ← STATIC copy of report.md — sync manually (16 sections)
│   ├── report.md                   ← Original detailed report
│   ├── findings.md                 ← Condensed findings
│   ├── subclasses_discovery.md     ← Taxonomy exploration notes
│   ├── spot_check.csv              ← Human review artifacts
│   └── figures/                    ← 12 PNG charts (01–12)
└── pipeline/
    └── README.md                   ← Pipeline integration wiring doc
```

---

## 🔑 Key Files — What You Need to Know

### `scripts/correspondence_subclasses.py` (SHARED DEPENDENCY)
The single source of truth for the 10-key taxonomy. Imported by ALL downstream tools.

**Public API:**
```python
from correspondence_subclasses import (
    SUBCLASS_KEYS,               # List[Literal["email", "memo", ...]]
    SUBCLASS_LABELS,             # Dict[str, str] — human-readable labels
    label_correspondence(row),   # tuple[str, str] — (key, evidence)
    classify_many(rows),         # Dict[str, int] — subclass counts
    evidence_for(row),           # tuple[str, str] — alias for label_correspondence
    _strip_forwarded(body),      # str — isolate own-message content from forwards
)
```

**How to modify it safely:**
1. **Do NOT change the enum order.** The first-match-wins logic depends on ordering. Current order: `meeting_request > voicemail > press_release > demand/attorney_demand > notice > memo > letter > email > other`.
2. **Add new keys only at the end.** Never insert before existing keys.
3. **Test false positives.** Any new marker must survive: energy-market terms (`demand`, `capacity`, `TCF`), marketing clickbait (`CLICK HERE NOW`), and ordinary corporate vocabulary (`legal`, `partner`).
4. **Run the test suite after every change.** `pytest tests/ -v` — if any test fails, revert or fix before committing.
5. **Document every heuristic change.** Add inline comments explaining what pattern fires, why, and what edge cases are known.

**Known limitations:**
- Attorney detection relies on domain lists + name patterns. Not exhaustive.
- `voicemail` is currently 0% in this text-only dump. Would need EDRM v2 audio-transcript format.
- The `_is_attorney()` function was missing `re.IGNORECASE` on sender-name matching — patched 2026-08-21.

### `scripts/eda/explore_enron.py` (EDA ENGINE)
Reads `data/enron/index.jsonl` and produces reports + figures.

**Output destinations:**
- `reports/eda/report.md` — Full narrative EDA report
- `reports/eda/findings.md` — Condensed bullet-point summary
- `reports/eda/figures/` — 12 PNG charts (01–12)
- `reports/eda/final_report.md` — Pre-computed final report (committed static copy)

**Important:** `final_report.md` is STATIC — it does not regenerate when you run `explore_enron.py`. After making changes to the analysis engine that would affect the final report's numbers, manually verify `final_report.md` matches the live output. Last synced: 2026-08-23.

**To generate fresh reports without figures:**
```bash
python scripts/eda/explore_enron.py --no-figures
```

**To analyze a subset (smoke testing):**
```bash
python scripts/eda/explore_enron.py --limit 1000
```

### `scripts/build_corpus_index.py`
Walks `data/raw/maildir/<custodian>/<folder>/<thread>/<msg>`, parses each message with stdlib `email`, writes JSONL row per message.

**Determinism guarantee:** Output is sorted by maildir path. Rebuilds are byte-identical.

**Parallelism:** Spawns worker pool via `multiprocessing.Pool` with `CORPUS_PROCS` env var (default: 8).

### `scripts/build_pipeline_dump.py`
Stratified sampling from `index.jsonl` into `pipeline.jsonl`. Preserves:
- Custodian distribution
- Internal/external ratio  
- Subclass proportions
- Attachment presence

### `scripts/spot_check.py`
Draws a labeled review sample from the index. Outputs a CSV where a human (Jack) reviews subclass assignments for quality validation. Spot-check samples are deterministic given the same seed.

---

## 🧪 Testing

Tests require NO corpus data. They construct minimal synthetic index-row dicts inline.

```bash
# Run everything (expected: 74 passed)
pytest tests/ -v

# Run just classification tests
pytest tests/ -k TestBasicClassification -v

# Run just forward-stripping tests
pytest tests/ -k ForwardStripping -v

# Run demand false-positive regression tests (critical!)
pytest tests/ -k DemandFalsePositives -v

# Coverage (requires pytest-cov)
pip install pytest-cov && pytest tests/ --cov=scripts/correspondence_subclasses --cov-report=term-missing
```

**Adding new tests:** Add them as methods inside an existing test class, or create a new `class TestXxx:` class. Follow the `_row(...)` helper pattern.

---

## 📊 EDA Report Generation Checklist

When updating EDA analysis code, follow this checklist:

1. **Run the analyzer** against a test subset:
   ```bash
   python scripts/eda/explore_enron.py --limit 5000 --no-figures
   ```

2. **Inspect the generated `findings.md`** — it should summarize the new dimensions.

3. **Verify all new sections render correctly** in `report.md`:
   - Timezone distribution (§8)
   - Reply-chain depth (§9)
   - Top custodians by subclass (§10)
   - Subject-length percentiles (§11)

4. **Update `final_report.md`** if the new analysis materially changes reported numbers.

5. **Regenerate figures** if adding/changing chart types:
   ```bash
   python scripts/eda/explore_enron.py  # default includes figures
   ```

6. **Commit figure updates alongside report updates** — don't forget either half.

---

## 🔄 Common Workflows

### Adding a new correlation dimension to EDA
1. Add helper functions to `explore_enron.py` (e.g., `def _tz_offset(date_str)`).
2. Collect stats in the `analyze()` function loop using new counters.
3. Add new sections to `render_report()` via `L.append(...)`.
4. Optionally add new figure generation calls in `make_figures()`.
5. Increment figure count references in the report header.
6. Update `README.md` → "New Analysis Sections" table.

### Updating the labeler taxonomy
1. Edit `correspondence_subclasses.py` — add constants, regexes, or enum entries.
2. Write a corresponding test in `tests/test_labeler.py` BEFORE merging.
3. Verify no existing tests break.
4. If changing enum order, document the rationale.
5. Update this AGENTS.md § "Key Files" section noting the change.

### Generating fresh pipeline dumps
```bash
# Regenerate from scratch
python scripts/build_pipeline_dump.py --dry-run   # preview plan
python scripts/build_pipeline_dump.py              # execute
```

### Publishing to Hugging Face Hub

**Agents must load `.opencode/skills/hf-dataset-publish/SKILL.md` before
publishing.** Condensed version:

1. Build the index if missing (`python scripts/build_corpus_index.py`).
2. Smoke test staging: `python scripts/publish_hf_dataset.py --dry-run --limit 5000`
3. Publish with a write-scoped `HF_TOKEN`: `python scripts/publish_hf_dataset.py`
4. Require `VERIFY: GREEN` (Hub LFS sha256 == local sha256) before claiming success.

Invariants: family split rule `md5(filename) % 10 == 0 → test`; labels ONLY from
the shared labeler; schema guard may never be bypassed (Hub viewer crashes on
partial-null schemas); card must keep the honest known-gaps list. Staging in
`data/hf_export/` is gitignored and ephemeral — regenerate, never commit.
The sibling repo's `publish_enron_correspondence.py` is row-compatible;
do not fork the spec — sync changes both ways.

---

## ⚠️ Pitfalls to Avoid

| Pitfall | Consequence | How to avoid |
|---------|-------------|--------------|
| Modifying `correspondence_subclasses.py` without running tests | False positive/negative labels silently deployed | Always run `pytest tests/` before committing labeler changes |
| Forgetting `final_report.md` is STATIC | Numbers drift from live analysis | Check final_report.md after any labeler/analyzer change |
| Committing `data/*.jsonl` files | Bloated repo, merge conflicts | These are gitignored — if committed, untrack immediately |
| Changing SUBCLASS_KEYS order | Breaking first-match-wins logic | Never reorder existing keys; append new ones at end |
| Assuming `notice = demand` overlap is resolved | Misclassification on boundary types | See `subclasses_discovery.md` for edge-case mapping |
| Running `acquire_enron.py` mid-pipeline | Overwrites partial work | Use `--dry-run` first; script is resume-safe anyway |
| Editing `.env` files directly | Shell appends trigger security approval | Use proper config management, never shell-appended env vars |

---

## 📁 Data Flow Diagram

```
raw_maildir/                    data/enron/index.jsonl          data/enron/pipeline.jsonl
┌─────────────────────┐         ┌──────────────────────────┐    ┌───────────────────────┐
│ CMU tarball         │  ──►   │ parse_messages()          │    │ stratified_sample()   │
│ enron_mail_20150507 │  ──►   │ .parseable=True          │ ──►│ subclass labeling   │
└─────────────────────┘         │ Sender/recipients        │    │ custodian/size bins │
                                │ Body (text/plain/html)   │    └───────────────────────┘
                                │ Attachments metadata     │                  │
                                └──────────────────────────┘                  │
                                             │                                │
                                             ▼                                ▼
                                   reports/eda/*                    pipeline.jsonl
                                   ├─ report.md                     ↓
                                   ├─ findings.md              llm-entity-extraction
                                   ├─ figures/*.png               (doc-class eval)
                                   ├─ final_report.md
                                   └─ subclasses_discovery.md
```

---

## 🆘 Troubleshooting

**"index not found" error from `explore_enron.py`:**
→ Run `python scripts/build_corpus_index.py` first.

**Labeler classifies `"DEMAND FOR"` market emails as `demand`:**
→ This was fixed by adding `\b` word-boundary guards in `_DEMAND_RE`. Test with `pytest tests/ -k DemandFalsePositives`.

**Missing timezone data in EDA report:**
→ The `_tz_offset()` helper now parses RFC-2822 offsets like `-0600`. Ensure date headers are ISO-8601 or RFC-2822 formatted.

**Figure count says "01–08" but only 8 exist:**
→ All 8 figures are present. The old README mentioned "01–08" which is correct. Just ensure `final_report.md` also cites 08 figures.

**Test failures after edit:**
→ Most likely cause: changed labeler heuristic without adjusting test expectations. Review which assertion failed and check if the behavior changed intentionally. If intentional, update the test. If accidental, fix the labeler.
