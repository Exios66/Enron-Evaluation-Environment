<div align="center">

# ⚙️ Enron Scripts

**Utility scripts for the Enron Evaluation Environment.**

</div>

---

## Functional index

| Group | Script | Purpose |
|:---|:---|:---|
| **Acquire** | `acquire_enron.py` | Acquire the CMU classic Enron email corpus |
| **Build** | `build_corpus_index.py` | Build the full-corpus index from the CMU maildir |
| | `build_pipeline_dump.py` | Build the pipeline-ready Enron correspondence dump |
| | `build_samples.py` | Render a bounded, stratified set of messages as samples |
| | `dedupe.py` | Exact-duplicate removal for the corpus index |
| **Labeler library** | `correspondence_subclasses.py` | Correspondance subclass taxonomy + heuristic labeler (**imported by llm-entity-extraction publishers**) |
| | `content_topics.py` | Content-topic taxonomy + heuristic labeler (shared) |
| | `sentiment_scorer.py` | Lexicon sentiment scorer for the corpus (KANBAN-079, shared) |
| **Publish** | `publish_hf_dataset.py` | Publish the CLEANED Enron correspondence corpus to the Hub |
| **QA** | `spot_check.py` | Draw the human spot-check sample for subclass GT |
| **EDA** | `eda/explore_enron.py` | Corpus EDA notebook-style exploration |
| | `eda/explore_subclasses.py` | Subclass-distribution EDA |

> **Shared-labeler note:** `correspondence_subclasses.py`, `content_topics.py`,
> and `sentiment_scorer.py` are imported by dataset publishers in
> `llm-entity-extraction/scripts/datasets/` and by the dojo corpus module.
> Do not move or rename without updating those consumers.

## Usage

```bash
cd packages/Enron-Evaluation-Environment

# Typical pipeline: acquire → index → dedupe → dump → samples
python scripts/acquire_enron.py
python scripts/build_corpus_index.py
python scripts/dedupe.py
python scripts/build_pipeline_dump.py
python scripts/build_samples.py

# Publish the cleaned corpus
python scripts/publish_hf_dataset.py
```

## Related Files

- `data/` — Acquired index + dumps (gitignored)
- `samples/` — Rendered sample documents
- `reports/eda/` — EDA figures and reports