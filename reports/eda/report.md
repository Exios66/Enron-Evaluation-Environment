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

## 8. Pipeline fit

The correspondence specialist cap is 40k chars; the sorter's single-pass text path is 16k; the chunk window is 90k. Enron bodies are small (median 756 chars), so virtually all rows pass single-pass text intake — the sampling strata for the pipeline dump (custodian, internal/external, subclass, attachment presence) should preserve the subclass mix above.

Figures: `figures/01`–`08` (subclass distribution, attachment presence, MIME mix, internal/external, top senders, body-length histogram vs budgets, per-custodian volume, thread fan-out).
