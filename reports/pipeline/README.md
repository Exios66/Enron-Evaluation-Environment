# Enron Correspondence — Integration into llm-entity-extraction

This documents how the Enron corpus slots into the mailroom's document
taxonomy as the **`correspondence`** doc class, complementing CUAD
(`contract`), MAUD (`merger_agreement`), and EDGAR S-1 (`corporate_record`).
The handoff artifact is `data/enron/pipeline.jsonl` (gitignored here,
regenerable via `scripts/build_pipeline_dump.py`).

## What the dump is

- **~300–500 emails** (default `--n 400`) sampled from the full 517,431-message
  CMU corpus, stratified by custodian, internal/external sender,
  correspondence subclass, and attachment presence.
- Row shape (the flat streamer-dump shape the docclass eval runners consume):

```json
{ "filename": "maildir/kaminski-v/.../235.",
  "doc_text": "FROM: ...\nTO: ...\nDATE: ...\nSUBJECT: ...\n---\n<body>",
  "prompt": "",
  "expected": "correspondence",
  "expected_subclass": "attorney_demand",
  "metadata": { "sender_addr": "...", "recipients": [...], "date": "...",
                "subject": "...", "attachments": [...], "custodian": "...",
                "subclass_evidence": "demand markers + law-firm domain velaw.com",
                "source_dataset": "enron-cmu-20150507" } }
```

- `expected` is `correspondence` for every row; `expected_subclass` is the
  second-level dimension (see below). `metadata` carries the full header /
  attachment / provenance fields — usable as GT for the
  `correspondence_specialist`'s sender / recipient / date fields.

## Subclass dimension (comprehensive enum)

Every correspondence type present in the corpus has a key
(`scripts/correspondence_subclasses.py` — the EDA's §2 table lists the
corpus-wide distribution and the `other` residual, which is the coverage
measure):

| key | label | what it is |
|---|---|---|
| `email` | Email | ordinary email correspondence (the default) |
| `memo` | Memorandum | interoffice memoranda (TO/FROM/DATE/RE blocks) |
| `letter` | Letter | formal letters (salutation + closing, external sender) |
| `notice` | Notice | formal notices (litigation hold, termination, notice of ...) |
| `demand` | Demand | demands/demand letters from non-attorney senders |
| `attorney_demand` | Attorney Demand | demands sent by attorneys / law firms |
| `press_release` | Press Release | press/news releases distributed over email |
| `meeting_request` | Meeting Request | calendar invitations / meeting requests |
| `voicemail` | Voicemail | voicemail transcriptions |
| `other` | Other | unparseable / non-email files (control slice) |

`build_pipeline_dump.py` enforces the **coverage contract**: the sample's
subclass set must equal the corpus's present subclass set (exit code 2 +
explicit message on a miss), so the dump can never silently drop a
correspondence type the corpus contains.

## Wiring into llm-entity-extraction

1. **Copy the dump into the sibling repo** (gitignored there too):

   ```bash
   cp data/enron/pipeline.jsonl ../llm-entity-extraction/data/enron/correspondence.jsonl
   ```

2. **Add the corpus to the merged docclass surface** — `scripts/datasets/
   build_docclass_merged.py`:
   - add `ENRON_DUMP = Path("data/enron/correspondence.jsonl")`,
   - load it with the existing `load_dump_rows()` helper
     (rows already carry `expected` / `expected_subclass`),
   - append to `build_merged()` corpus order and the banner comment.
   - The merged surface grows ~676 → ~1,076 rows.

3. **Add the correspondence subclass dimension to the sorter** —
   `agents/sorter_agent.py`:
   - `CORRESPONDENCE_SUBCLASSES = [{key, label} for key, label in ...]`
     mirroring the enum above (labels from the EDA table),
   - add `"correspondence": CORRESPONDENCE_SUBCLASSES` to
     `SUBCLASS_DIMENSIONS` and extend `DOC_SUBCLASSES` +
     `DOCCLASS_SCHEMA`'s `doc_subclass` enum (the shared 6-class surface is
     untouched — this is the opt-in docclass path),
   - `normalize_doc_subclass()` already scopes the enum per doc_type, so a
     correspondence subclass can never leak into a merger-agreement row.
   - `config/taxonomy.yaml`: extend the `correspondence` entry with the
     `subclasses:` block + `field_types` note that sender/recipient/date GT
     comes from email headers.

4. **Langfuse mirror** — `scripts/eval/sync_langfuse_datasets.py`:
   add an `--enron` flag mirroring `data/enron/correspondence.jsonl` as
   `mailroom-enron-correspondence` (llm-dojo).

5. **Eval** — the docclass runner needs no changes:

   ```bash
   python scripts/datasets/build_docclass_merged.py
   python scripts/eval/run_langfuse_docclass_eval.py \
       --local-dumps data/datasets/docclass_merged.jsonl \
       --stratified 100 --seed 42 --prompt-version sorter_docclass_v3
   ```

## Ground truth notes

- **Header fields** (sender, recipient, additional_recipients, date) have
  objective GT in `metadata` — a genuine scored surface for the
  `correspondence_specialist` (unlike CUAD/MAUD, where GT is expert QA).
- **Subclass labels** are heuristic + human spot-checked: `data/spot_check.csv`
  (mirror `reports/eda/spot_check.csv`) is the review artifact; corrected
  `human_label` cells become the authoritative per-class GT subset.
- **demand_amount / key_points / action_items / urgency** have no GT — a
  judge-scored sample is the honest path if they are to be scored.

## Corpus provenance

CMU classic Enron email dataset (public domain-ish research corpus),
`enron_mail_20150507.tar.gz`, 517,431 messages, ~150 custodians, maildir
layout with `<msg>_files/` attachment stores. Attribution for reports:
"Source: CMU classic Enron email corpus (enron_mail_20150507) —
https://www.cs.cmu.edu/~enron/".