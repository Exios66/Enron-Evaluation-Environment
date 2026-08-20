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
scripts/
  acquire_enron.py        # download + verify + extract the CMU tarball
  build_corpus_index.py   # parse the maildir -> data/enron/index.jsonl (full corpus)
  build_pipeline_dump.py  # stratified sample -> data/enron/pipeline.jsonl (pipeline-ready)
  spot_check.py           # draw the labeled review sample -> data/spot_check.csv
  eda/explore_enron.py    # full-corpus EDA -> reports/eda/{report.md,findings.md,figures/}
data/                     # gitignored: raw corpus + index + pipeline dump
reports/
  eda/                    # committed EDA reports + figures + spot-check artifacts
  pipeline/               # committed: dump-shape docs + wiring into llm-entity-extraction
```

## Corpus

CMU classic Enron email dataset (public, no license required):

- **Source**: https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
- **Contents**: 517,431 emails from ~150 Enron employees (maildir layout),
  including attachments (`<msg>_files/` sibling dirs).

## Pipeline dump

`data/enron/pipeline.jsonl` (gitignored, regenerable) is the handoff artifact.
Row shape is the flat streamer-dump shape the llm-entity-extraction docclass
eval runners consume:

```json
{ "filename": "...", "doc_text": "...", "prompt": "",
  "expected": "correspondence", "expected_subclass": "email",
  "metadata": { "sender": "...", "recipients": [...], "date": "...",
                "subject": "...", "thread": "...", "attachments": [...],
                "custodian": "...", "source_dataset": "enron-cmu-20150507" } }
```

See `reports/pipeline/README.md` for the wiring commands into
`llm-entity-extraction` (`build_docclass_merged.py`, sorter subclass
dimension, Langfuse mirror).

## Reproduce

```bash
python scripts/acquire_enron.py          # download + extract (~423 MB tarball)
python scripts/build_corpus_index.py     # parse maildir -> index.jsonl
python scripts/eda/explore_enron.py      # EDA -> reports/eda/
python scripts/build_pipeline_dump.py    # sample -> pipeline.jsonl (+ dry-run)
python scripts/spot_check.py             # review artifact -> reports/eda/spot_check.csv
```