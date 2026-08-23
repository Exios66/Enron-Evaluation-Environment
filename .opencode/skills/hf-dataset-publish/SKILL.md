---
name: hf-dataset-publish
description: "USE WHEN publishing any dataset from this repo to the Hugging Face Hub, updating the Lucius-Morningstar/enron-correspondence dataset, or when a task mentions HF upload, dataset card, LFS verification, or the KANBAN-074 publish pattern. Encodes the family-wide publish discipline: stage → schema-guard → card → upload_folder → sha256 verify."
---

# Hugging Face Dataset Publication — Enron Correspondence

This repo owns the **correspondence data-production node** of the
Lucius-Morningstar governed dataset family. The canonical Hub artifact is:

```
Lucius-Morningstar/enron-correspondence
https://huggingface.co/datasets/Lucius-Morningstar/enron-correspondence
```

The publisher is `scripts/publish_hf_dataset.py`. It is row-compatible with
`llm-entity-extraction`'s `scripts/datasets/publish_enron_correspondence.py`
(same schema, same shared labeler, same split rule) — either may be used; do
not fork the spec.

## Prerequisites

| Need | Source |
|---|---|
| Corpus index | `data/enron/index.jsonl` — build first: `python scripts/build_corpus_index.py` |
| `huggingface_hub` | `pip install huggingface_hub` (v1.x) |
| Write token | `HF_TOKEN` env var with **write** scope on the `Lucius-Morningstar` org/user account. Without it staging/dry-run work but publish fails at `whoami()`. |

## Procedure (in order — never skip a step)

### 1. Stage and validate (no network)

```bash
# Full corpus (~517k rows → ~1 GB staged JSONL)
python scripts/publish_hf_dataset.py --dry-run

# Smoke test first — always
python scripts/publish_hf_dataset.py --dry-run --limit 5000
```

Check the printed counts against expectations before proceeding:
- ~517k published rows, 150 custodians
- subclass mix ≈ email 505,929 / memo 3,568 / notice 2,842 / press_release 2,520 /
  letter 2,077 / demand 315 / meeting_request 135 / attorney_demand 4
  (`voicemail` and `other` are structurally 0 — see AGENTS.md known limitations)
- split ≈ 90/10 train/test

### 2. Publish

```bash
export HF_TOKEN=hf_...          # write-scoped token; never commit it
python scripts/publish_hf_dataset.py
```

What it does, in sequence:
1. Re-streams the index, labels every row via the SHARED labeler
   (`scripts/correspondence_subclasses.py` — the single taxonomy source of truth)
2. **Schema guard**: refuses to publish if ANY row lacks a non-empty
   `filename`, a valid `expected_subclass` (must be in `SUBCLASS_KEYS`),
   a valid `split`, or has non-string `text`. Rationale: all-null leading
   batches crash the Hub viewer's JSON→parquet conversion (KANBAN-073 lesson).
   Rows with empty body AND empty subject are dropped and counted in the manifest.
3. Stages `data/hf_export/`: `<name>.jsonl` + `manifest.json` + rendered card
4. `create_repo(exist_ok=True)` then `upload_folder` (README.md card, manifest, JSONL)
5. **Verify**: compares Hub LFS sha256 vs local file sha256 → prints GREEN/RED
   and writes `data/hf_export/PUBLISH_SUMMARY.json`

### 3. Post-upload checks (mandatory)

- Publisher output ends with `VERIFY: GREEN`. RED = inspect before anything else.
- Open the Hub URL: dataset card renders, row count matches, train/test split
  slices load without parquet errors.
- `data/hf_export/PUBLISH_SUMMARY.json` is the evidence trail — keep its
  sha256 prefixes consistent with any board/report claims.

## Non-negotiable invariants

1. **Split rule is family-wide**: `int(md5(filename.strip()), 16) % 10 == 0 → test`
   (~10%). Never invent a different split — every dataset in the family
   (docclass-merged, enron-correspondence) must recompute identical splits.
2. **One taxonomy source**: labels come from
   `scripts/correspondence_subclasses.label_correspondence` only. If this
   repo's enum changes, the sibling publisher picks it up automatically here;
   `llm-entity-extraction`'s sorter needs a manual mirror (see AGENTS.md
   sync obligations).
3. **Never ship partial-null schemas** — the schema guard exists because the
   Hub viewer hard-crashes on them. Extend the guard when adding fields.
4. **Cards are honest**: heuristic GT is labeled as heuristic; the card lists
   known gaps (attorney detection not exhaustive, voicemail impossible in
   text-only corpus, cross-custodian duplicates NOT merged — group by
   `metadata.message_id`). Update gap list if the corpus handling changes.
5. **License framing**: "Enron corpus — released for research use; treat PII
   accordingly" on every row's `metadata.license` and in the card.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `index not found` | Build it: `python scripts/build_corpus_index.py` (needs `data/raw/maildir/`) |
| Publish step fails at `whoami()` | No/expired `HF_TOKEN`, or token lacks write scope |
| 429 / slow upload | ~1 GB payload; retry is safe — `create_repo(exist_ok=True)` makes reruns idempotent |
| Hub viewer shows parquet conversion error | A partial-null schema shipped historically — republish with current guard |
| Subclass counts differ from this skill's table | Index was rebuilt after a labeler change or corpus change — re-run EDA, reconcile, then publish |

## Related

- Sibling implementation: `llm-entity-extraction/scripts/datasets/publish_enron_correspondence.py`
- Family mirror state (other datasets): `llm-entity-extraction/data/hf_export/README.md`
- Downstream eval consumption: `reports/pipeline/README.md`
