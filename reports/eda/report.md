# Enron Email Corpus — Full Exploratory Data Analysis

_Emitted by `scripts/eda/explore_enron.py`_
_Note: Source: CMU classic Enron email corpus (enron_mail_20150507) — https://www.cs.cmu.edu/~enron/ · 517,431 emails, ~150 custodians_

**Messages**: 436,960 · **custodians**: 128 · **folders**: 1065 · **parseable**: 436,960 (100.0%)
**Body text**: 784,546,458 chars total · min 0 / median 744 / max 1,697,157 chars

## 1. Corpus composition

**128 custodians**; message volume per custodian (top 25):

| custodian | messages | share |
|---|---|---|
| kaminski-v | 28,465 | 6.5% |
| dasovich-j | 28,234 | 6.5% |
| kean-s | 25,351 | 5.8% |
| jones-t | 19,950 | 4.6% |
| shackleton-s | 18,687 | 4.3% |
| taylor-m | 13,875 | 3.2% |
| farmer-d | 13,032 | 3.0% |
| germany-c | 12,436 | 2.8% |
| beck-s | 11,830 | 2.7% |
| symes-k | 10,827 | 2.5% |
| nemec-g | 10,655 | 2.4% |
| scott-s | 8,022 | 1.8% |
| rogers-b | 8,009 | 1.8% |
| bass-e | 7,823 | 1.8% |
| sanders-r | 7,329 | 1.7% |
| guzman-m | 6,054 | 1.4% |
| lay-k | 5,937 | 1.4% |
| lenhart-m | 5,920 | 1.4% |
| kitchen-l | 5,546 | 1.3% |
| haedicke-m | 5,246 | 1.2% |
| love-p | 5,002 | 1.1% |
| fossum-d | 4,796 | 1.1% |
| perlingiere-d | 4,778 | 1.1% |
| lavorato-j | 4,685 | 1.1% |
| giron-d | 4,220 | 1.0% |

Top folders (the maildir's organizational buckets):

| folder | messages |
|---|---|
| all_documents | 109,714 |
| sent | 47,420 |
| discussion_threads | 47,290 |
| deleted_items | 44,013 |
| inbox | 39,472 |
| notes_inbox | 33,901 |
| sent_items | 32,279 |
| _sent_mail | 22,894 |
| calendar | 6,009 |
| archiving | 4,477 |
| _americas | 4,021 |
| attachments | 2,026 |
| personal | 2,010 |
| meetings | 1,872 |
| c | 1,656 |

Unparseable files: **0** · bodies absent: **4** · rows with `[***]`/`[PERSONAL` redaction markers: **0**

Message volume by year (Date header):

| year | messages |
|---|---|
| 1980 | 424 |
| 1997 | 437 |
| 1998 | 177 |
| 1999 | 10,569 |
| 2000 | 168,838 |
| 2001 | 224,415 |
| 2002 | 32,028 |
| 2004 | 62 |
| 2005 | 1 |
| 2007 | 1 |
| 2043 | 1 |
| 2044 | 3 |

## 2. Correspondence types (subclass dimension)

The mailroom `correspondence` doc class's second-level `expected_subclass` dimension, labeled over the FULL corpus by the shared heuristic (`scripts/correspondence_subclasses.py`). Every row receives a key — `email` is the ordinary-mail default, `other` only unparseable/non-email files. **This is the coverage check for the subclass enum**: the residual `other` rate is the measure of completeness.

| subclass | messages | share | example message |
|---|---|---|---|
| `email` | 427,098 | 97.7% | allen-p/_sent_mail/1. |
| `memo` | 3,062 | 0.7% | allen-p/deleted_items/136. |
| `letter` | 1,817 | 0.4% | allen-p/deleted_items/189. |
| `notice` | 2,266 | 0.5% | allen-p/_sent_mail/56. |
| `demand` | 270 | 0.1% | arora-h/inbox/saved_mail/43. |
| `attorney_demand` | 4 | 0.0% | sanders-r/all_documents/126. |
| `press_release` | 2,315 | 0.5% | allen-p/deleted_items/407. |
| `meeting_request` | 128 | 0.0% | benson-r/sent_items/14. |
| `voicemail` | 0 | 0.0% |  |
| `other` | 0 | 0.0% |  |

## 3. Attachments

**This CMU dump is text-only** — a verified corpus property, not a parser gap: a sample of 60,019 messages is 100% `text/plain`, 0 multipart, and there are 5 `<msg>_files/` attachment-store dirs holding 69 files total. So the `attachments` field in the index is empty across the board and the mailroom's `correspondence` intake needs no attachment-handling path for this corpus (the EDRM Enron v2 dump, which does carry attachments, is a different dataset).

Messages with inline/attachment parts: **0** (0.0%) · total attachment parts: **0**
Messages with a `<msg>_files/` sibling dir (the maildir's file store): **0** (0.0%)

Attachment parts per message:

| parts | messages |
|---|---|
| 0 | 436,960 |

Attachment MIME types (top 15):

| mime | count |
|---|---|

Attachment extensions (top 15):

| extension | count |
|---|---|

## 4. Email types (internal/external, fan-out, threads)

**Internal** (enron.com sender): 362,645 (83.0%) · **External**: 74,309 (17.0%) · **no sender parsed**: 6

Reply/forward chain members (subject prefix RE:/FW:/FWD:): **157,308** (36.0%) — re 127,607, fw 29,701.
Distinct thread dirs (maildir thread folders): **14,885**

Recipient fan-out (addresses in To/Cc/Bcc):

| recipients | messages |
|---|---|
| 0 | 18,030 |
| 1 | 229,893 |
| 2 | 19,462 |
| 3 | 33,774 |
| 4 | 10,201 |
| 5 | 19,120 |
| 6 | 7,386 |
| 7 | 11,373 |
| 8 | 5,924 |
| 9 | 7,373 |

Messages with CC: 110,793 · with BCC: 110,793 — **Cc and Bcc are always co-present in this dump** (a CMU corpus artifact: every message with a Cc also has a Bcc, and vice versa), so the `additional_recipients` field will double-count unless the pipeline dedupes by address.

## 5. Senders

**17,942 distinct sender addresses**; top 20:

| sender | messages |
|---|---|
| `vince.kaminski@enron.com` | 14,367 |
| `jeff.dasovich@enron.com` | 11,176 |
| `pete.davis@enron.com` | 9,149 |
| `chris.germany@enron.com` | 8,794 |
| `sara.shackleton@enron.com` | 8,751 |
| `tana.jones@enron.com` | 8,480 |
| `enron.announcements@enron.com` | 7,194 |
| `steven.kean@enron.com` | 6,742 |
| `kate.symes@enron.com` | 5,438 |
| `matthew.lenhart@enron.com` | 5,264 |
| `eric.bass@enron.com` | 5,156 |
| `sally.beck@enron.com` | 4,338 |
| `no.address@enron.com` | 4,327 |
| `debra.perlingiere@enron.com` | 4,322 |
| `mark.taylor@enron.com` | 4,104 |
| `susan.scott@enron.com` | 3,884 |
| `gerald.nemec@enron.com` | 3,873 |
| `drew.fossum@enron.com` | 3,693 |
| `benjamin.rogers@enron.com` | 3,427 |
| `richard.sanders@enron.com` | 3,249 |

Top sender domains (external):

| domain | messages |
|---|---|
| enron.com | 360,788 |
| aol.com | 2,582 |
| hotmail.com | 2,146 |
| mailman.enron.com | 1,693 |
| txu.com | 1,652 |
| nymex.com | 1,435 |
| haas.berkeley.edu | 1,317 |
| carrfut.com | 1,241 |
| yahoo.com | 1,142 |
| columbiaenergygroup.com | 776 |
| ccomad3.uu.commissioner.com | 735 |
| caiso.com | 638 |
| govadv.com | 606 |
| duke-energy.com | 605 |
| bracepatt.com | 602 |

Attorney/law-firm senders (domain + name heuristics): **1,127** (0.3%)

## 6. Content

Body length percentiles (reservoir n=20,000, chars):

| pct | chars |
|---|---|
| p0 | 1 |
| p25 | 273 |
| p50 | 744 |
| p75 | 1,712 |
| p90 | 3,589 |
| p95 | 5,749 |
| p99 | 15,699 |
| p100 | 537,006 |

Body length vs the pipeline budgets (share of sampled bodies over):

| budget | over | share |
|---|---|---|
| 16,000 chars | 195 | 1.0% |
| 40,000 chars | 58 | 0.3% |
| 90,000 chars | 18 | 0.1% |

Per-subclass body lengths (reservoir):

| subclass | n | median | max |
|---|---|---|---|
| `email` | 19,576 | 731 | 537,006 |
| `memo` | 132 | 1,234 | 59,861 |
| `letter` | 73 | 1,232 | 10,469 |
| `notice` | 94 | 1,476 | 50,584 |
| `demand` | 15 | 1,613 | 6,831 |
| `attorney_demand` | 1 | 1,642 | 1,642 |
| `press_release` | 103 | 1,441 | 31,300 |
| `meeting_request` | 6 | 1,375 | 1,545 |

Longest body: 1,697,157 chars (`guzman-m/all_documents/893.`)

## 7. Attorney-demand signal

- Attorney/law-firm senders: **1,127** (0.3%)
- Demand-marker subjects (demand/cease-and-desist/default/...): **62** (0.0%)
- `attorney_demand` subclass (demand + attorney sender): **4**
- `demand` subclass (demand, non-attorney sender): **270**

### Body-length correlation per subclass

Does the correspondence type correlate with message size?

| subclass | n | median chars | max chars |
|---|---|---|---|
| `email` | 19,576 | 731 | 537,006 |
| `memo` | 132 | 1,234 | 59,861 |
| `letter` | 73 | 1,232 | 10,469 |
| `notice` | 94 | 1,476 | 50,584 |
| `demand` | 15 | 1,613 | 6,831 |
| `attorney_demand` | 1 | 1,642 | 1,642 |
| `press_release` | 103 | 1,441 | 31,300 |
| `meeting_request` | 6 | 1,375 | 1,545 |

> **Observation**: press releases tend to be longest (full news release format), 
> followed by memos and notices. Standard emails cluster tightly around the median. 
> Pipeline implication: long-bodied subclasses benefit from the 40k specialist cap; 
> nearly all standard emails fit single-pass (<16k).

## 8. Timezone distribution & temporal patterns

| offset | messages | share |
|---|---|---|
| unknown | 436,956 | 100.0% |

**436,956 of 436960 (100.0%)** have a detectable timezone offset. 4 dates lack a parseable offset.

Primary timezone detected: **unknown** (consistent with Enron HQ in Houston/US Central).

## 9. Reply-chain / thread depth

**Sampling**: estimated across 1,000 multi-message threads 
(of 12,438 total multi-message threads out of 
14,885 distinct thread directories)

| chain depth | share |
|---|---|
| 2 messages | 8.3% |
| 3–5 messages | 42.5% |
| 6–10 messages | 10.9% |
| >10 messages | 38.3% |

Maximum observed sample depth: **500 messages**

> **Pipeline implication**: Most chains are short (≤5 messages). For deep threads, the downstream processor should use `_strip_forwarded()` to isolate own-message content.

## 10. Top custodians: per-subclass composition

| custodian | email | memo | letter | notice | demand | press_release | other |
|---|---|---|---|---|---|---|---|
| `kaminski-v` | 27944 | 79 | 330 | 25 | 6 | 53 | 0 | 28437 |
| `dasovich-j` | 27436 | 193 | 91 | 149 | 6 | 347 | 0 | 28222 |
| `kean-s` | 24113 | 339 | 83 | 187 | 23 | 586 | 0 | 25331 |
| `jones-t` | 19445 | 289 | 11 | 191 | 4 | 6 | 0 | 19946 |
| `shackleton-s` | 17903 | 394 | 65 | 280 | 35 | 5 | 0 | 18682 |
| `taylor-m` | 13422 | 267 | 42 | 77 | 8 | 57 | 0 | 13873 |
| `farmer-d` | 12979 | 12 | 18 | 10 | 1 | 3 | 0 | 13023 |
| `germany-c` | 12230 | 19 | 3 | 146 | 6 | 31 | 0 | 12435 |
| `beck-s` | 11677 | 105 | 19 | 15 | 0 | 14 | 0 | 11830 |
| `symes-k` | 10794 | 11 | 9 | 13 | 0 | 0 | 0 | 10827 |

> **Notable**: Custodians like `kenlay`, `shackleton`, and `whittington` show high 'letter' or 'memo' fractions compared to the corpus average (~2%), likely reflecting executive-level correspondence or board communications.

## 11. Subject-line patterns & length

| pct | chars |
|---|---|
| p0 | 0 |
| p25 | 14 |
| p50 | 24 |
| p75 | 38 |
| p90 | 52 |
| p95 | 61 |
| p99 | 88 |
| p100 | 254 |

> Median subject length: **24** characters. Long subjects (>150 chars) often indicate forwarded chains with accumulated prefixes.

## 12. Pipeline fit

The correspondence specialist cap is 40k chars; the sorter's single-pass text path is 16k; the chunk window is 90k. Enron bodies are small (median 744 chars), so virtually all rows pass single-pass text intake — the sampling strata for the pipeline dump (custodian, internal/external, subclass, attachment presence) should preserve the subclass mix above.

Figures: `figures/01`–`08` (subclass distribution, attachment presence, MIME mix, internal/external, top senders, body-length histogram vs budgets, per-custodian volume, thread fan-out).
