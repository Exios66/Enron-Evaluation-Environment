# Enron-Evaluation-Environment

Exploratory data analysis of the CMU classic Enron email corpus, and the
production of a pipeline-ready **correspondence** dataset for the
llm-mailroom document-processing pipeline (sibling repo
[`llm-entity-extraction`](https://github.com/Exios66/llm-entity-extraction),
which ingests CUAD contracts + MAUD merger agreements + EDGAR S-1 corporate
records into its doc-class taxonomy).

The Enron corpus stands in for the mailroom taxonomy's **`correspondence`**
doc class (emails, memos, letters, notices, demands), with a second-level
**`expected_subclass`** dimension covering every correspondence type present
in the corpus.

## Repo layout

```
├── AGENTS.md                           # Agent-facing operational guide
├── README.md                           # This file
├── tests/                              # ✅ 36/36 validation harness
│   ├── __init__.py                     # Unit tests (no corpus data needed)
│   └── conftest.py                     # pytest fixtures
├── scripts/                            # Core pipeline & analysis tools
│   ├── correspondence_subclasses.py    # Shared heuristic labeler (10-key taxonomy)
│   ├── acquire_enron.py                # Download + verify + extract CMU tarball
│   ├── build_corpus_index.py           # Parse maildir → data/enron/index.jsonl
│   ├── dedupe.py                       # Exact-duplicate removal → data/enron/index.unique.jsonl
│   ├── build_pipeline_dump.py          # Stratified sample → data/enron/pipeline.jsonl
│   ├── spot_check.py                   # Labeled review sample → reports/eda/spot_check.csv
│   └── eda/
│       ├── explore_enron.py            # Full-corpus EDA → reports/eda/{report.md, findings.md}
│       └── explore_subclasses.py       # Subclass discovery & edge-case analysis
├── reports/
│   ├── eda/                            # Committed EDA output
│   │   ├── final_report.md             # ✅ Updated: correct numbers, 16 sections, new analysis
│   │   ├── report.md                   # Original detailed EDA report
│   │   ├── findings.md                 # Condensed key findings
│   │   ├── subclasses_discovery.md     # Taxonomy exploration notes
│   │   ├── spot_check.csv              # Human review artifacts
│   │   └── figures/                    # 12 published PNG charts
│   │       ├── 01_subclasses.png       # Subclass distribution (horizontal bars)
│   │       ├── 02_hour_of_day.png      # Message volume by hour (UTC)
│   │       ├── 03_day_of_week.png      # Message volume by weekday
│   │       ├── 04_monthly_volume.png   # Monthly volume timeline
│   │       ├── 05_internal_external.png # Internal vs external senders
│   │       ├── 06_top_senders.png      # Top 20 senders
│   │       ├── 07_body_length.png      # Body length histogram w/ budget lines
│   │       ├── 08_custodians.png       # Message volume per custodian
│   │       ├── 09_fanout.png           # Recipient fan-out
│   │       ├── 10_thread_sizes.png     # Thread-size distribution (exact)
│   │       ├── 11_duplicates.png       # Exact-duplicate bodies (md5)
│   │       └── 12_recipient_roles.png  # To/Cc/Bcc address totals
│   └── pipeline/                       # Pipeline integration docs
│       └── README.md                   # Wiring into llm-entity-extraction
├── .gitignore                          # Data dirs, artifacts, env vars
├── .gitattributes                      # Encoding / CRLF config
└── pyproject.toml                      # Project metadata & tool config
```

## Corpus

CMU classic Enron email dataset (public, no license required):

- **Source**: https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
- **Contents**: 517,390 parseable emails from ~150 Enron employees (maildir layout),
  including attachments (`<msg>_files/` sibling dirs).
- **Taxonomy**: 10-key `expected_subclass` dimension covering all correspondence types found in the corpus.

## Quick Start

Get the corpus and reproduce the full EDA:

```bash
# 1. Acquire the raw corpus (~423 MB tarball, auto-extracts to data/raw/maildir/)
python scripts/acquire_enron.py

# 2. Build the full-corpus index (JSONL stream of parsed messages)
python scripts/build_corpus_index.py

# 3. Run the full EDA — generates reports + 12 figures
python scripts/eda/explore_enron.py

# 4. Build the pipeline-ready stratified sample (skips exact-duplicate bodies)
python scripts/build_pipeline_dump.py

# 5. (Optional) Regenerate a fully deduplicated corpus index
python scripts/dedupe.py --index data/enron/index.jsonl --out data/enron/index.unique.jsonl

# 6. Draw a labeled spot-check sample for human review
python scripts/spot_check.py

# 7. Validate correctness with the test harness (no corpus data needed)
pytest tests/ -v
```

Dry-run mode for each script:

```bash
python scripts/acquire_enron.py --dry-run
python scripts/build_corpus_index.py --dry-run
python scripts/build_corpus_index.py --limit 1000   # smoke test with subset
```

## Test Harness

A comprehensive **36-test** validation suite verifies the entire labeler pipeline
without requiring corpus data. Tests cover:

| Category | Tests | What they validate |
|----------|-------|--------------------|
| Basic classification | 9 | All 10 subclass keys reachable via representative samples |
| Forward stripping | 4 | `_strip_forwarded()` correctly isolates own-message content |
| Attorney detection | 5 | Law-firm domains fire; false positives (`partner`, `legal`) blocked |
| Demand false positives | 4 | Energy-market "demand" terms (capacity, TCF) stay in `email` |
| Letter boundary cases | 3 | Salutation+closing works; marketing spam excluded; FW: disqualifies |
| Subject analysis | 3 | Length extraction, whitespace handling, empty strings |
| Taxonomy invariants | 3 | Key enum integrity, classify_many safety, no spurious `other` |
| Determinism | 1 | Same input always yields same output |
| Index row schema | 3 | Required fields, recipient structure, ISO-8601 dates |
| Pipeline dump integrity | 1 | Expected doc-class fields present |

```bash
# Run everything
pytest tests/ -v

# Run just the labeler tests (fastest path)
pytest tests/ -k labeler -v

# See coverage
pip install pytest-cov && pytest tests/ --cov=scripts/correspondence_subclasses
```

## Pipeline Output

`data/enron/pipeline.jsonl` (gitignored, regenerable) is the handoff artifact.
Row shape matches the flat streamer-dump format consumed by
`llm-entity-extraction`'s doc-class eval runners:

```json
{
  "filename": "...",
  "doc_text": "...",
  "prompt": "",
  "expected": "correspondence",
  "expected_subclass": "email",
  "metadata": {
    "sender": "...",
    "recipients": [...],
    "date": "...",
    "subject": "...",
    "thread": "...",
    "attachments": [...],
    "custodian": "...",
    "source_dataset": "enron-cmu-20150507"
  }
}
```

See [`reports/pipeline/README.md`](reports/pipeline/README.md) for the wiring commands
into `llm-entity-extraction` (`build_docclass_merged.py`, sorter subclass dimension,
Langfuse mirror).

## New Analysis Sections (v2 Update)

The EDA engine (`explore_enron.py`) now produces **12 analysis sections** instead of 8,
adding previously-missing dimensions:

| Section | What it adds |
|---------|-------------|
| §7b | Body-length correlation per subclass (does doc type correlate with size?) |
| §8 | Timezone distribution & temporal patterns across all date headers |
| §9 | Reply-chain / thread depth estimation via sampled multi-message threads |
| §10 | Per-custodian subclass composition matrix (top 10 custodians) |
| §11 | Subject-line length percentiles (p0–p100) |
| §12 | Pipeline fit assessment (all budgets updated to reflect new corpus stats) |

See [`reports/eda/final_report.md`](reports/eda/final_report.md) for the complete updated report.

## Deduplication (v2.1)

The full-corpus EDA found **52.2% of non-empty bodies are byte-exact duplicates**
(md5 over raw body text) — cross-custodian cc'ing, saved sent-folder copies, and
mass-mail blasts. Sampling from the raw index would repeatedly draw the same
underlying text under different filenames.

- **`scripts/dedupe.py`** — standalone tool; streams the index and keeps the
  first occurrence per distinct body hash (`data/enron/index.unique.jsonl`).
- **`build_pipeline_dump.py`** — dedupes *by construction*: every candidate
  row's body is hashed with the identical scheme and repeats are skipped, so no
  stratified sample can ever contain two rows with identical text.
- Empty-body rows are never treated as duplicates of each other (they carry
  distinct headers/paths), mirroring the EDA's hashing rule.
- One shared hash function feeds the EDA's §14 duplicate counts, the sampler,
  and the dedupe tool, so all three report directly comparable numbers.
  Unit-tested in `tests/test_labeler.py::TestDedupe` (40 tests total).

## Key Design Decisions

### Labeler Heuristics
- The taxonomy is **data-necessitated**, not theoretical — derived from actual Enron corpus patterns.
- **False positive mitigation** is built-in: energy-market "demand" vocabulary (capacity, TCF volumes) deliberately excluded; marketing clickbait filtered from `letter`; reply/forward chains don't masquerade as memos/demands/releases.
- Labeling is **deterministic** — pure function of index-row fields; rebuilds produce identical results byte-for-byte.

### Correlation vs Classification
- The `notice`/`demand` overlap is the trickiest classification boundary. `DEMAND FOR PAYMENT` can be a demand letter AND itself serve as a notice. Priority order in the labeler ensures legal-demand semantics take precedence.

### Attachment Handling
- This CMU text-only dump contains zero attachment email parts. Binary files exist only in `<msg>_files/` sibling directories (Excel spreadsheets, PDFs) — separate from message content. No attachment-handling path needed for the current correspondence intake.

## Reproduction Log

```bash
# Full pipeline reproduction
python scripts/acquire_enron.py          # download + extract (~423 MB tarball)
python scripts/build_corpus_index.py     # parse maildir -> index.jsonl
python scripts/eda/explore_enron.py      # EDA -> reports/eda/
python scripts/build_pipeline_dump.py    # sample -> pipeline.jsonl (+ dry-run)
python scripts/spot_check.py             # review artifact -> reports/eda/spot_check.csv
pytest tests/ -v                         # 36/36 validation pass
```
