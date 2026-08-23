# Enron Email Corpus — Full Exploratory Data Analysis

_Emitted by `scripts/eda/explore_enron.py`_
_Note: Source: CMU classic Enron email corpus (enron_mail_20150507) — https://www.cs.cmu.edu/~enron/ · 517,431 emails, ~150 custodians_

**Messages**: 517,390 · **custodians**: 150 · **folders**: 1425 · **parseable**: 517,390 (100.0%)
**Body text**: 910,932,871 chars total · min 1 / median 756 / max 2,011,417 chars

## 1. Corpus composition

**150 custodians**; message volume per custodian (top 25):

| custodian | messages | share |
|---|---|---|
| kaminski-v | 28,465 | 5.5% |
| dasovich-j | 28,234 | 5.5% |
| kean-s | 25,351 | 4.9% |
| mann-k | 23,381 | 4.5% |
| jones-t | 19,950 | 3.9% |
| shackleton-s | 18,687 | 3.6% |
| taylor-m | 13,875 | 2.7% |
| farmer-d | 13,032 | 2.5% |
| germany-c | 12,436 | 2.4% |
| beck-s | 11,830 | 2.3% |
| symes-k | 10,827 | 2.1% |
| nemec-g | 10,655 | 2.1% |
| scott-s | 8,022 | 1.6% |
| rogers-b | 8,009 | 1.5% |
| bass-e | 7,823 | 1.5% |
| sanders-r | 7,329 | 1.4% |
| campbell-l | 6,490 | 1.3% |
| shapiro-r | 6,071 | 1.2% |
| guzman-m | 6,054 | 1.2% |
| lay-k | 5,937 | 1.1% |
| lenhart-m | 5,920 | 1.1% |
| lokay-m | 5,567 | 1.1% |
| kitchen-l | 5,546 | 1.1% |
| haedicke-m | 5,246 | 1.0% |
| sager-e | 5,200 | 1.0% |

Top folders (the maildir's organizational buckets):

| folder | messages |
|---|---|
| all_documents | 128,103 |
| discussion_threads | 58,609 |
| sent | 57,653 |
| deleted_items | 51,356 |
| inbox | 44,859 |
| sent_items | 37,921 |
| notes_inbox | 36,665 |
| _sent_mail | 30,109 |
| calendar | 6,133 |
| archiving | 4,477 |
| _americas | 4,021 |
| personal | 2,577 |
| attachments | 2,026 |
| meetings | 1,872 |
| c | 1,656 |

Unparseable files: **0** · bodies absent: **0** · rows with `[***]`/`[PERSONAL` redaction markers: **0**

Message volume by year (Date header):

| year | messages |
|---|---|
| 1980 | 522 |
| 1986 | 2 |
| 1997 | 437 |
| 1998 | 177 |
| 1999 | 11,144 |
| 2000 | 196,100 |
| 2001 | 272,953 |
| 2002 | 35,974 |
| 2004 | 70 |
| 2005 | 1 |
| 2007 | 1 |
| 2012 | 2 |
| 2020 | 2 |
| 2024 | 1 |
| 2043 | 1 |
| 2044 | 3 |

## 2. Correspondence types (subclass dimension)

The mailroom `correspondence` doc class's second-level `expected_subclass` dimension, labeled over the FULL corpus by the shared heuristic (`scripts/correspondence_subclasses.py`). Every row receives a key — `email` is the ordinary-mail default, `other` only unparseable/non-email files. **This is the coverage check for the subclass enum**: the residual `other` rate is the measure of completeness.

| subclass | messages | share | example message |
|---|---|---|---|
| `email` | 505,929 | 97.8% | allen-p/_sent_mail/1. |
| `memo` | 3,568 | 0.7% | allen-p/deleted_items/136. |
| `letter` | 2,077 | 0.4% | allen-p/deleted_items/189. |
| `notice` | 2,842 | 0.5% | allen-p/_sent_mail/56. |
| `demand` | 315 | 0.1% | arnold-j/deleted_items/243. |
| `attorney_demand` | 4 | 0.0% | sanders-r/all_documents/126. |
| `press_release` | 2,520 | 0.5% | allen-p/deleted_items/407. |
| `meeting_request` | 135 | 0.0% | benson-r/sent_items/14. |
| `voicemail` | 0 | 0.0% |  |
| `other` | 0 | 0.0% |  |

## 3. Attachments

**This CMU dump is text-only** — a verified corpus property, not a parser gap: a sample of 60,019 messages is 100% `text/plain`, 0 multipart, and there are 5 `<msg>_files/` attachment-store dirs holding 69 files total. So the `attachments` field in the index is empty across the board and the mailroom's `correspondence` intake needs no attachment-handling path for this corpus (the EDRM Enron v2 dump, which does carry attachments, is a different dataset).

Messages with inline/attachment parts: **0** (0.0%) · total attachment parts: **0**
Messages with a `<msg>_files/` sibling dir (the maildir's file store): **0** (0.0%)

Attachment parts per message:

| parts | messages |
|---|---|
| 0 | 517,390 |

Attachment MIME types (top 15):

| mime | count |
|---|---|

Attachment extensions (top 15):

| extension | count |
|---|---|

## 4. Email types (internal/external, fan-out, threads)

**Internal** (enron.com sender): 429,728 (83.1%) · **External**: 87,660 (16.9%) · **no sender parsed**: 2

Reply/forward chain members (subject prefix RE:/FW:/FWD:): **189,099** (36.5%) — re 153,293, fw 35,806.
Distinct thread dirs (maildir thread folders): **14,999**

Recipient fan-out (addresses in To/Cc/Bcc):

| recipients | messages |
|---|---|
| 0 | 20,401 |
| 1 | 277,109 |
| 2 | 23,873 |
| 3 | 39,817 |
| 4 | 11,950 |
| 5 | 22,375 |
| 6 | 8,640 |
| 7 | 13,298 |
| 8 | 6,981 |
| 9 | 8,691 |

Messages with CC: 127,872 · with BCC: 127,872 — **Cc and Bcc are always co-present in this dump** (a CMU corpus artifact: every message with a Cc also has a Bcc, and vice versa), so the `additional_recipients` field will double-count unless the pipeline dedupes by address.

## 5. Senders

**20,323 distinct sender addresses**; top 20:

| sender | messages |
|---|---|
| `kay.mann@enron.com` | 16,735 |
| `vince.kaminski@enron.com` | 14,368 |
| `jeff.dasovich@enron.com` | 11,411 |
| `pete.davis@enron.com` | 9,149 |
| `chris.germany@enron.com` | 8,801 |
| `sara.shackleton@enron.com` | 8,777 |
| `enron.announcements@enron.com` | 8,587 |
| `tana.jones@enron.com` | 8,490 |
| `steven.kean@enron.com` | 6,759 |
| `kate.symes@enron.com` | 5,438 |
| `matthew.lenhart@enron.com` | 5,265 |
| `eric.bass@enron.com` | 5,158 |
| `no.address@enron.com` | 5,112 |
| `debra.perlingiere@enron.com` | 4,387 |
| `sally.beck@enron.com` | 4,343 |
| `mark.taylor@enron.com` | 4,111 |
| `susan.scott@enron.com` | 4,000 |
| `gerald.nemec@enron.com` | 3,888 |
| `drew.fossum@enron.com` | 3,706 |
| `john.arnold@enron.com` | 3,578 |

Top sender domains (external):

| domain | messages |
|---|---|
| enron.com | 427,777 |
| aol.com | 2,801 |
| hotmail.com | 2,427 |
| mailman.enron.com | 1,775 |
| txu.com | 1,653 |
| nymex.com | 1,438 |
| haas.berkeley.edu | 1,317 |
| yahoo.com | 1,309 |
| carrfut.com | 1,303 |
| ccomad3.uu.commissioner.com | 877 |
| caiso.com | 838 |
| bracepatt.com | 821 |
| columbiaenergygroup.com | 776 |
| lists.thebiz.net | 716 |
| nyiso.com | 715 |

Attorney/law-firm senders (domain + name heuristics): **2,261** (0.4%)

## 6. Content

Body length percentiles (reservoir n=20,000, chars):

| pct | chars |
|---|---|
| p0 | 2 |
| p25 | 286 |
| p50 | 756 |
| p75 | 1,723 |
| p90 | 3,525 |
| p95 | 5,466 |
| p99 | 14,064 |
| p100 | 168,971 |

Body length vs the pipeline budgets (share of sampled bodies over):

| budget | over | share |
|---|---|---|
| 16,000 chars | 162 | 0.8% |
| 40,000 chars | 40 | 0.2% |
| 90,000 chars | 9 | 0.0% |

Per-subclass body lengths (reservoir):

| subclass | n | median | max |
|---|---|---|---|
| `email` | 19,592 | 742 | 168,971 |
| `memo` | 130 | 1,382 | 59,861 |
| `letter` | 65 | 1,149 | 13,817 |
| `notice` | 103 | 1,315 | 59,391 |
| `demand` | 12 | 953 | 6,831 |
| `press_release` | 90 | 1,946 | 41,712 |
| `meeting_request` | 8 | 845 | 2,187 |

Longest body: 2,011,417 chars (`dorland-c/deleted_items/20.`)

## 7. Attorney-demand signal

- Attorney/law-firm senders: **2,261** (0.4%)
- Demand-marker subjects (demand/cease-and-desist/default/...): **67** (0.0%)
- `attorney_demand` subclass (demand + attorney sender): **4**
- `demand` subclass (demand, non-attorney sender): **315**

### Body-length correlation per subclass

Does the correspondence type correlate with message size?

| subclass | n | median chars | max chars |
|---|---|---|---|
| `email` | 19,592 | 742 | 168,971 |
| `memo` | 130 | 1,382 | 59,861 |
| `letter` | 65 | 1,149 | 13,817 |
| `notice` | 103 | 1,315 | 59,391 |
| `demand` | 12 | 953 | 6,831 |
| `press_release` | 90 | 1,946 | 41,712 |
| `meeting_request` | 8 | 845 | 2,187 |

> **Observation**: press releases tend to be longest (full news release format), 
> followed by memos and notices. Standard emails cluster tightly around the median. 
> Pipeline implication: long-bodied subclasses benefit from the 40k specialist cap; 
> nearly all standard emails fit single-pass (<16k).

## 8. Timezone distribution & temporal patterns

| offset | messages | share |
|---|---|---|
| unknown | 517,390 | 100.0% |

**517,390 of 517390 (100.0%)** have a detectable timezone offset. 0 dates lack a parseable offset.

Primary timezone detected: **unknown** (consistent with Enron HQ in Houston/US Central).

## 9. Reply-chain / thread depth

**Exact counts** across all 14,999 thread directories: 
2,550 singletons, 12,449 multi-message threads; 
largest thread directory holds **3,304 messages**.

Full size distribution: §15 (+ `figures/10`).

> **Pipeline implication**: Multi-message directories dominate, and the largest holds thousands of near-identical copies. For deep threads, the downstream processor should use `_strip_forwarded()` to isolate own-message content.

## 10. Top custodians: per-subclass composition

| custodian | email | memo | letter | notice | demand | press_release | other |
|---|---|---|---|---|---|---|---|
| `kaminski-v` | 27944 | 79 | 330 | 25 | 6 | 53 | 0 | 28437 |
| `dasovich-j` | 27436 | 193 | 91 | 149 | 6 | 347 | 0 | 28222 |
| `kean-s` | 24113 | 339 | 83 | 187 | 23 | 586 | 0 | 25331 |
| `mann-k` | 22888 | 172 | 1 | 284 | 21 | 15 | 0 | 23381 |
| `jones-t` | 19445 | 289 | 11 | 191 | 4 | 6 | 0 | 19946 |
| `shackleton-s` | 17903 | 394 | 65 | 280 | 35 | 5 | 0 | 18682 |
| `taylor-m` | 13422 | 267 | 42 | 77 | 8 | 57 | 0 | 13873 |
| `farmer-d` | 12979 | 12 | 18 | 10 | 1 | 3 | 0 | 13023 |
| `germany-c` | 12230 | 19 | 3 | 146 | 6 | 31 | 0 | 12435 |
| `beck-s` | 11677 | 105 | 19 | 15 | 0 | 14 | 0 | 11830 |

> **Notable (computed)**: `memo` concentrates at `shackleton-s` (2.1% of their mail vs 0.7% corpus-wide); `letter` concentrates at `kaminski-v` (1.2% of their mail vs 0.4% corpus-wide); `notice` concentrates at `shackleton-s` (1.5% of their mail vs 0.5% corpus-wide); `demand` concentrates at `shackleton-s` (0.2% of their mail vs 0.1% corpus-wide); `press_release` concentrates at `kean-s` (2.3% of their mail vs 0.5% corpus-wide).

## 11. Subject-line patterns & length

| pct | chars |
|---|---|
| p0 | 0 |
| p25 | 13 |
| p50 | 23 |
| p75 | 37 |
| p90 | 52 |
| p95 | 61 |
| p99 | 87 |
| p100 | 254 |

> Median subject length: **23** characters. Long subjects (>150 chars) often indicate forwarded chains with accumulated prefixes.

## 12. Temporal patterns (hour, weekday, monthly volume)

Peak hour (UTC): **16:00** with 45,061 messages (8.7% of timestamped mail).

| hour (UTC) | messages | hour (UTC) | messages |
|---|---|---|---|
| 00:00 | 8,403 | 12:00 | 26,326 |
| 01:00 | 5,767 | 13:00 | 35,405 |
| 02:00 | 4,714 | 14:00 | 41,514 |
| 03:00 | 4,060 | 15:00 | 44,080 |
| 04:00 | 3,391 | 16:00 | 45,061 |
| 05:00 | 3,092 | 17:00 | 38,279 |
| 06:00 | 4,500 | 18:00 | 27,719 |
| 07:00 | 11,924 | 19:00 | 20,642 |
| 08:00 | 25,640 | 20:00 | 18,399 |
| 09:00 | 32,809 | 21:00 | 18,181 |
| 10:00 | 35,454 | 22:00 | 16,551 |
| 11:00 | 32,548 | 23:00 | 12,931 |

Business-hours share (08:00–18:59 UTC): **74.4%** — consistent with a desk-workforce sender profile.

Day-of-week distribution (UTC):

| day | messages | share |
|---|---|---|
| Mon | 97,275 | 18.8% |
| Tue | 106,513 | 20.6% |
| Wed | 107,222 | 20.7% |
| Thu | 96,617 | 18.7% |
| Fri | 90,184 | 17.4% |
| Sat | 8,999 | 1.7% |
| Sun | 10,580 | 2.0% |

Weekend share: **3.8%** — Enron traders and deal lawyers famously worked weekends; this quantifies it.

Monthly coverage: **73 distinct months** (1980-01 → 2044-01). Peak: **2001-10** (37,139 msgs); quietest: **1986-04** (1).

| month | messages | month | messages |
|---|---|---|---|
| 1980-01 | 522 | 2000-07 | 13,620 |
| 1986-04 | 1 | 2000-08 | 19,061 |
| 1986-05 | 1 | 2000-09 | 19,937 |
| 1997-01 | 1 | 2000-10 | 24,716 |
| 1997-03 | 39 | 2000-11 | 32,513 |
| 1997-04 | 36 | 2000-12 | 31,390 |
| 1997-05 | 32 | 2001-01 | 24,019 |
| 1997-06 | 64 | 2001-02 | 23,151 |
| 1997-07 | 56 | 2001-03 | 28,510 |
| 1997-08 | 77 | 2001-04 | 35,772 |
| 1997-09 | 72 | 2001-05 | 35,661 |
| 1997-10 | 28 | 2001-06 | 18,763 |
| 1997-11 | 32 | 2001-07 | 10,200 |
| 1998-01 | 4 | 2001-08 | 8,917 |
| 1998-05 | 1 | 2001-09 | 10,846 |
| 1998-09 | 1 | 2001-10 | 37,139 |
| 1998-10 | 8 | 2001-11 | 28,606 |
| 1998-11 | 56 | 2001-12 | 11,369 |
| 1998-12 | 107 | 2002-01 | 21,080 |
| 1999-01 | 130 | 2002-02 | 8,201 |
| 1999-02 | 91 | 2002-03 | 3,452 |
| 1999-03 | 112 | 2002-04 | 1,159 |
| 1999-04 | 97 | 2002-05 | 909 |
| 1999-05 | 662 | 2002-06 | 921 |
| 1999-06 | 645 | 2002-07 | 244 |
| 1999-07 | 859 | 2002-09 | 6 |
| 1999-08 | 1,060 | 2002-10 | 1 |
| 1999-09 | 1,239 | 2002-12 | 1 |
| 1999-10 | 1,394 | 2004-02 | 70 |
| 1999-11 | 1,310 | 2005-12 | 1 |
| 1999-12 | 3,545 | 2007-02 | 1 |
| 2000-01 | 6,363 | 2012-11 | 2 |
| 2000-02 | 7,185 | 2020-12 | 2 |
| 2000-03 | 8,747 | 2024-05 | 1 |
| 2000-04 | 8,623 | 2043-12 | 1 |
| 2000-05 | 10,244 | 2044-01 | 3 |
| 2000-06 | 13,701 | — | — |

## 13. Recipient roles (To / Cc / Bcc)

| role | total addresses | messages carrying ≥1 | avg per such message |
|---|---|---|---|
| To | 3,130,181 | 495,524 | 6.32 |
| Cc | 562,789 | — | — |
| Bcc | 562,789 | 127,872 | 4.40 |

Messages with **no To-address at all** (Bcc-only or Cc-only sends): **1,465** (0.28%). These are the mass-mail / blind-copy artifacts; downstream intake should not assume every message has a To header.

## 14. Duplicates & content reuse

Exact-duplicate bodies (md5 over raw body text): **269,867** of 517,390 non-empty bodies (52.2%) — 247,523 unique.

Largest duplicate group: **112 copies** of one body; **17,014** duplicate groups span two or more custodians — these are cross-mailbox copies (cc'ing, saved sent-folder duplicates), not just intra-folder saves.

**Sampling policy (enforced)**: `build_pipeline_dump.py` hashes every row's body with the identical md5 scheme and skips repeats, so the pipeline sample is drawn only from unique texts. `scripts/dedupe.py --index data/enron/index.jsonl --out data/enron/index.unique.jsonl` regenerates a fully deduplicated index.

Top duplicated bodies (copies → first-seen file):

| copies | first seen at |
|---|---|
| 112 | `allen-p/deleted_items/218.` |
| 110 | `allen-p/deleted_items/415.` |
| 108 | `beck-s/all_documents/147.` |
| 107 | `allen-p/deleted_items/191.` |
| 107 | `allen-p/all_documents/24.` |
| 106 | `allen-p/deleted_items/399.` |
| 105 | `allen-p/inbox/44.` |
| 103 | `allen-p/deleted_items/197.` |
| 101 | `bass-e/all_documents/20.` |
| 101 | `allen-p/deleted_items/213.` |

Most-repeated normalized subjects (of 126459 distinct):

| subject | count |
|---|---|
| `demand ken lay donate proceeds from enron stock sales` | 1,124 |
| `schedule crawler: hourahead failure` | 900 |
| `enron mentions` | 836 |
| `schedule crawler: hourahead failure <codesite>` | 800 |
| `(no subject)` | 593 |
| `entouch newsletter` | 554 |
| `lunch` | 537 |
| `hey` | 475 |
| `meeting` | 453 |
| `hi` | 446 |

> Pipeline implication: dedupe by body hash BEFORE stratified sampling, or newsletter/blast mails will be overweighted in the sample.

## 15. Thread-size distribution (exact)

14,999 thread directories · 2,550 singletons (17.0%) · 12,449 multi-message threads.

| thread size | share of threads |
|---|---|
| 1 message | 17.0% |
| 2 messages | 7.2% |
| 3–5 messages | 33.3% |
| 6–10 messages | 7.2% |
| >10 messages | 35.3% |

Largest thread directory: **3,304 messages**.

## 16. Pipeline fit

The correspondence specialist cap is 40k chars; the sorter's single-pass text path is 16k; the chunk window is 90k. Enron bodies are small (median 756 chars), so virtually all rows pass single-pass text intake — the sampling strata for the pipeline dump (custodian, internal/external, subclass, attachment presence) should preserve the subclass mix above.

Figures: `figures/01`–`12` (subclass distribution, hour-of-day, day-of-week, monthly volume, internal/external, top senders, body-length vs budgets, custodian volume, fan-out, thread sizes, duplicate bodies, recipient roles).
