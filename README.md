<div align="center">

# ✉️ Enron-Evaluation-Environment

**Exploratory data analysis of the CMU classic Enron email corpus, and the
production of a pipeline-ready `correspondence` dataset for the llm-mailroom
document-processing pipeline.**

The Enron corpus stands in for the mailroom taxonomy's **`correspondence`**
doc class (emails, memos, letters, notices, demands), with a second-level
**`expected_subclass`** dimension covering every correspondence type present
in the corpus.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/pytest-74%2F74_passing-brightgreen)](tests/)
[![Status](https://img.shields.io/badge/status-production-success)](reports/eda/final_report.md)
[![Last Commit](https://img.shields.io/github/last-commit/Exios66/Enron-Evaluation-Environment?logo=github&label=updated)](https://github.com/Exios66/Enron-Evaluation-Environment/commits/main)
[![Repo Size](https://img.shields.io/github/repo-size/Exios66/Enron-Evaluation-Environment?logo=github)](https://github.com/Exios66/Enron-Evaluation-Environment)

[![Corpus](https://img.shields.io/badge/corpus-517%2C390_emails-2563eb)](reports/eda/report.md)
[![Custodians](https://img.shields.io/badge/custodians-~150-059669)](reports/eda/report.md)
[![Taxonomy](https://img.shields.io/badge/subclasses-10_keys-8b5cf6)](reports/pipeline/README.md)
[![🤗 Dataset](https://img.shields.io/badge/%F0%9F%A4%97_Dataset-enron--correspondence--dedup-fbe425?logo=huggingface&logoColor=black)](https://huggingface.co/datasets/Lucius-Morningstar/enron-correspondence-dedup)
[![Sibling Node](https://img.shields.io/badge/sibling-claims--data--eda-0ea5e9)](https://github.com/Exios66/claims-data-eda)

<img src="reports/eda/figures/01_subclasses.png" alt="Correspondence subclass distribution across the 517,390-message Enron corpus" width="720"/>

</div>

---

## 📊 Corpus at a Glance

| Metric | Value |
|---|---|
| Parseable emails (CMU maildir, 20150507 tarball) | **517,390** |
| Custodians (~150 Enron employees) | ~150 |
| Byte-exact duplicate bodies (md5) | **52.2%** — deduped by construction in sampling |
| Subclass taxonomy | 10 keys, corpus-complete |
| Pipeline sample (`data/enron/pipeline.jsonl`) | ~400 stratified, duplicate-free |
| HF mirror split | `md5(filename) % 10 == 0` → test (~10%) |

## 🌐 Governed Repository Ecosystem

This repo is the **correspondence data-production node** of a governed
evaluation family under [@Exios66](https://github.com/Exios66). Artifacts flow
downstream; nothing flows back without a versioned handoff.

| Repository | Role | Coupling |
|---|---|---|
| [`llm-mailroom`](https://github.com/Exios66/llm-mailroom) | Multi-agent legal-document intake pipeline; owns the doc-class taxonomy (`correspondence`, `contract`, `merger_agreement`, `corporate_record`, …) this repo labels against | ⬆️ Upstream taxonomy governor |
| **Enron-Evaluation-Environment** (this repo) | Full-corpus EDA + stratified `correspondence` dataset production for the CMU Enron corpus | — |
| [`llm-entity-extraction`](https://github.com/Exios66/llm-entity-extraction) | Training & eval environment for legal-document entity extraction / classification / summarization; consumes `data/enron/pipeline.jsonl` via `build_docclass_merged.py` + the sorter's subclass dimension | ⬇️ Primary downstream consumer |
| [`llm-dojo-scoring`](https://github.com/Exios66/llm-dojo-scoring) | Scoring environment + Langfuse dataset mirror (`mailroom-enron-correspondence`) | ⬇️ Downstream scoring mirror |
| [`claims-data-eda`](https://github.com/Exios66/claims-data-eda) | Sibling **insurance-claims** data-production node (CMS DE-SynPUF) — feeds the mailroom's `insurance_claim` doc class | ↔️ Sibling node |
| [`atticus-investigation`](https://github.com/Exios66/atticus-investigation) | LegalBench prompt-engineering evaluation pipeline (prompt versions × models via OpenRouter + Braintrust) | ↔️ Adjacent evaluation environment |

Handoff contract and wiring commands: [`reports/pipeline/README.md`](reports/pipeline/README.md).

## 🔍 Headline Findings

<table>
<tr><td width="50%">

### 52.2% of bodies are byte-exact duplicates
Cross-custodian cc'ing, saved sent-folder copies, mass-mail blasts. Sampling
from the raw index would repeatedly draw the same text — so the sampler
**dedupes by construction** and a standalone
[`dedupe.py`](scripts/dedupe.py) produces a fully deduplicated index.

</td><td width="50%">

### A 10-key taxonomy, data-necessitated
The `expected_subclass` enum was derived from actual corpus patterns —
with **false-positive mitigation** built in (energy-market "demand"
vocabulary excluded; reply/forward chains can't masquerade as memos).

</td></tr>
<tr><td width="50%">

### Deterministic labeling
Classification is a pure function of index-row fields — rebuilds produce
byte-identical results, verified by the 74-test harness.

</td><td width="50%">

### Zero attachment parts
This CMU text-only dump contains no inline attachment parts; binaries live
only in `<msg>_files/` sibling directories — no attachment-handling path
needed for correspondence intake.

</td></tr>
</table>

<p align="center">
  <img src="reports/eda/figures/02_hour_of_day.png" alt="Message volume by hour (UTC)" width="49%"/>
  <img src="reports/eda/figures/04_monthly_volume.png" alt="Monthly volume timeline" width="49%"/>
</p>
<p align="center">
  <img src="reports/eda/figures/07_body_length.png" alt="Body length histogram with budget lines" width="49%"/>
  <img src="reports/eda/figures/11_duplicates.png" alt="Exact-duplicate bodies" width="49%"/>
</p>

<details>
<summary><b>🖼️ Full figure gallery (12 charts)</b></summary>

| # | Figure | Insight |
|---|---|---|
| 01 | [Subclasses](reports/eda/figures/01_subclasses.png) | 10-key subclass distribution (horizontal bars) |
| 02 | [Hour of day](reports/eda/figures/02_hour_of_day.png) | Message volume by hour (UTC) |
| 03 | [Day of week](reports/eda/figures/03_day_of_week.png) | Volume by weekday |
| 04 | [Monthly volume](reports/eda/figures/04_monthly_volume.png) | Timeline across the corpus window |
| 05 | [Internal vs external](reports/eda/figures/05_internal_external.png) | Sender domain split |
| 06 | [Top senders](reports/eda/figures/06_top_senders.png) | Top 20 senders |
| 07 | [Body length](reports/eda/figures/07_body_length.png) | Histogram w/ token-budget lines |
| 08 | [Custodians](reports/eda/figures/08_custodians.png) | Volume per custodian |
| 09 | [Fan-out](reports/eda/figures/09_fanout.png) | Recipient fan-out distribution |
| 10 | [Thread sizes](reports/eda/figures/10_thread_sizes.png) | Thread-size distribution (exact) |
| 11 | [Duplicates](reports/eda/figures/11_duplicates.png) | Byte-exact duplicate bodies (md5) |
| 12 | [Recipient roles](reports/eda/figures/12_recipient_roles.png) | To/Cc/Bcc address totals |

</details>

Full analysis: **[`reports/eda/final_report.md`](reports/eda/final_report.md)** (16 sections) · condensed: **[`reports/eda/findings.md`](reports/eda/findings.md)**

## 🚀 Quick Start

```bash
git clone https://github.com/Exios66/Enron-Evaluation-Environment.git
cd Enron-Evaluation-Environment

# 1️⃣ Acquire the raw corpus (~423 MB tarball, auto-extracts to data/raw/maildir/)
python scripts/acquire_enron.py

# 2️⃣ Build the full-corpus index (JSONL stream of parsed messages)
python scripts/build_corpus_index.py

# 3️⃣ Run the full EDA — generates reports + 12 figures
python scripts/eda/explore_enron.py

# 4️⃣ Build the pipeline-ready stratified sample (skips exact-duplicate bodies)
python scripts/build_pipeline_dump.py

# 5️⃣ (Optional) Regenerate a fully deduplicated corpus index
python scripts/dedupe.py --index data/enron/index.jsonl --out data/enron/index.unique.jsonl

# 6️⃣ Draw a labeled spot-check sample for human review
python scripts/spot_check.py

# 7️⃣ Render the Markdown correspondence samples (samples/)
python scripts/build_samples.py

# 8️⃣ Validate correctness with the test harness (no corpus data needed)
pytest tests/ -v                       # 74/74 passing
```

<details>
<summary><b>Smoke-test flags</b></summary>

```bash
python scripts/acquire_enron.py --dry-run
python scripts/build_corpus_index.py --dry-run
python scripts/build_corpus_index.py --limit 1000   # subset smoke test
```

</details>

## 🧾 Subclass Dimension (comprehensive enum)

Every correspondence type present in the corpus has a key
([`scripts/correspondence_subclasses.py`](scripts/correspondence_subclasses.py) —
the EDA's §2 table lists the corpus-wide distribution; the `other` residual is
the coverage measure):

| key | label | what it is |
|---|---|---|
| `email` | Email | ordinary email correspondence (the default) |
| `memo` | Memorandum | interoffice memoranda (TO/FROM/DATE/RE blocks) |
| `letter` | Letter | formal letters (salutation + closing, external sender) |
| `notice` | Notice | formal notices (litigation hold, termination, notice of …) |
| `demand` | Demand | demands/demand letters from non-attorney senders |
| `attorney_demand` | Attorney Demand | demands sent by attorneys / law firms |
| `press_release` | Press Release | press/news releases distributed over email |
| `meeting_request` | Meeting Request | calendar invitations / meeting requests |
| `voicemail` | Voicemail | voicemail transcriptions |
| `other` | Other | unparseable / non-email files (control slice) |

`build_pipeline_dump.py` enforces the **coverage contract**: the sample's
subclass set must equal the corpus's present subclass set (exit code 2 +
explicit message on a miss), so the dump can never silently drop a
correspondence type.

## 📦 Pipeline Output Shape

`data/enron/pipeline.jsonl` (gitignored, regenerable) — the flat
streamer-dump format consumed by
[`llm-entity-extraction`](https://github.com/Exios66/llm-entity-extraction)'s
doc-class eval runners:

```jsonc
{
  "filename": "maildir/kaminski-v/.../235.",
  "doc_text": "FROM: ...\nTO: ...\nDATE: ...\nSUBJECT: ...\n---\n<body>",
  "prompt": "",
  "expected": "correspondence",
  "expected_subclass": "attorney_demand",
  "metadata": {
    "sender_addr": "...",
    "recipients": ["..."],
    "date": "...",
    "subject": "...",
    "attachments": [],
    "custodian": "kaminski-v",
    "subclass_evidence": "demand markers + law-firm domain velaw.com",
    "source_dataset": "enron-cmu-20150507"
  }
}
```

`metadata` carries the full header/attachment/provenance fields — usable as
GT for the `correspondence_specialist`'s sender/recipient/date fields.

## 🧪 Test Harness

A **74-test** validation suite verifies the entire labeler pipeline without
requiring corpus data:

| Category | Coverage |
|----------|----------|
| Basic classification | all 10 subclass keys reachable via representative samples |
| Forward stripping | `_strip_forwarded()` isolates own-message content |
| Attorney detection | law-firm domains fire; `partner`/`legal` false positives blocked |
| Demand false positives | energy-market "demand" terms (capacity, TCF) stay in `email` |
| Letter boundary cases | salutation+closing works; marketing spam excluded; FW: disqualifies |
| Subject analysis | length extraction, whitespace handling, empty strings |
| Taxonomy invariants | key enum integrity, `classify_many` safety, no spurious `other` |
| Determinism | same input → same output, byte-for-byte |
| Index row schema | required fields, recipient structure, ISO-8601 dates |
| Pipeline dump integrity | expected doc-class fields present |
| Dedupe integrity | shared body-hash semantics, first-occurrence-wins, no dup bodies in samples |
| Content topics & sentiment | KANBAN-079 enrichment labelers |

```bash
pytest tests/ -v                                   # everything
pytest tests/ -k labeler -v                        # labeler only (fastest)
pip install pytest-cov && pytest tests/ --cov=scripts/correspondence_subclasses
```

## 🤗 Hugging Face Publication

The full cleaned corpus publishes to the Hub as
[**`Lucius-Morningstar/enron-correspondence-dedup`**](https://huggingface.co/datasets/Lucius-Morningstar/enron-correspondence-dedup)
— one row per message with heuristic subclass GT (`expected_subclass` +
on-row `label_evidence`) and the family-wide deterministic split
(`md5(filename) % 10 == 0` → test, ~10%):

```bash
# Smoke-test staging (no network)
python scripts/publish_hf_dataset.py --dry-run --limit 5000

# Full publish (~517k rows; requires HF_TOKEN with write scope)
export HF_TOKEN=hf_...
python scripts/publish_hf_dataset.py
```

The publisher enforces a **schema guard** (no partial-null schemas — they
crash the Hub viewer), stages an honest manifest + dataset card into
gitignored `data/hf_export/`, uploads via `huggingface_hub`, then verifies the
Hub LFS sha256 against the local file (`VERIFY: GREEN`). Agents: load
[`.opencode/skills/hf-dataset-publish/SKILL.md`](.opencode/skills/hf-dataset-publish/SKILL.md)
before publishing. Row-compatible sibling implementation:
[`llm-entity-extraction/scripts/datasets/publish_enron_correspondence.py`](https://github.com/Exios66/llm-entity-extraction).

## 🧩 Key Design Decisions

- **Labeler heuristics are data-necessitated, not theoretical** — derived from
  actual Enron corpus patterns, deterministic, with built-in false-positive
  mitigation.
- **Correlation vs classification**: the `notice`/`demand` overlap is the
  trickiest boundary (`DEMAND FOR PAYMENT` can be both); priority order in the
  labeler ensures legal-demand semantics take precedence.
- **Shared hash, three consumers**: one body-hash function feeds the EDA's
  duplicate counts, the sampler, and the dedupe tool — all three report
  directly comparable numbers.
- **Attachment handling**: none needed for this text-only dump (see findings).

<details>
<summary><b>📁 Repo layout</b></summary>

```
├── AGENTS.md                           # Agent-facing operational guide
├── tests/                              # ✅ 74/74 validation harness
├── scripts/
│   ├── correspondence_subclasses.py    # Shared heuristic labeler (10-key taxonomy)
│   ├── acquire_enron.py                # Download + verify + extract CMU tarball
│   ├── build_corpus_index.py           # Parse maildir → data/enron/index.jsonl
│   ├── dedupe.py                       # Exact-duplicate removal → index.unique.jsonl
│   ├── build_pipeline_dump.py          # Stratified sample → data/enron/pipeline.jsonl
│   ├── spot_check.py                   # Labeled review sample → reports/eda/spot_check.csv
│   ├── build_samples.py                # Taxonomy-stratified Markdown samples → samples/
│   ├── publish_hf_dataset.py           # HF Hub publisher → Lucius-Morningstar/enron-correspondence
│   └── eda/
│       ├── explore_enron.py            # Full-corpus EDA → reports/eda/{report.md, findings.md}
│       └── explore_subclasses.py       # Subclass discovery & edge-case analysis
├── reports/
│   ├── eda/                            # Committed EDA output (final_report, findings, 12 figures)
│   └── pipeline/README.md              # Wiring into llm-entity-extraction
└── .opencode/skills/hf-dataset-publish/SKILL.md   # Agent runbook for the Hub upload
```

</details>

## 🔁 Reproduction Log

```bash
python scripts/acquire_enron.py          # download + extract (~423 MB tarball)
python scripts/build_corpus_index.py     # parse maildir -> index.jsonl
python scripts/eda/explore_enron.py      # EDA -> reports/eda/
python scripts/build_pipeline_dump.py    # sample -> pipeline.jsonl (+ dry-run)
python scripts/spot_check.py             # review artifact -> reports/eda/spot_check.csv
pytest tests/ -v                         # 74/74 validation pass
```

---

<div align="center">

**[llm-mailroom](https://github.com/Exios66/llm-mailroom)** ·
**[llm-entity-extraction](https://github.com/Exios66/llm-entity-extraction)** ·
**[llm-dojo-scoring](https://github.com/Exios66/llm-dojo-scoring)** ·
**[claims-data-eda](https://github.com/Exios66/claims-data-eda)** ·
**[atticus-investigation](https://github.com/Exios66/atticus-investigation)**

<sub>Built by the governed evaluation family under <a href="https://github.com/Exios66">@Exios66</a> · 2026</sub>

</div>
