# Correspondence-subclass discovery evidence

_Emitted by `scripts/eda/explore_subclasses.py`_
_Corpus: 517390 messages from `data/enron/index.jsonl`_

This pass surfaces the natural clusters that the subclass enum (`scripts/correspondence_subclasses.py`) was built to cover.

## Subclass distribution (full corpus)

| subclass | messages | share |
|---|---|---|
| `email` | 505929 | 97.8% |
| `memo` | 3568 | 0.7% |
| `letter` | 2077 | 0.4% |
| `notice` | 2842 | 0.5% |
| `demand` | 315 | 0.1% |
| `attorney_demand` | 4 | 0.0% |
| `press_release` | 2520 | 0.5% |
| `meeting_request` | 135 | 0.0% |
| `voicemail` | 0 | 0.0% |
| `other` | 0 | 0.0% |

## Subject-prefix clusters

| prefix | messages |
|---|---|
| RE: | 189099 |
| RE | 49483 |
| FWD: | 35806 |
| FW | 29913 |
| EOL | 1863 |
| TW | 1074 |
| HPL | 983 |
| FERC | 974 |
| TRV | 926 |
| ENA | 889 |
| URGENT | 810 |
| CAISO | 777 |
| ISDA | 744 |
| EES | 739 |
| CA | 726 |
| CES | 682 |
| ERV | 516 |
| GE | 462 |
| ETS | 434 |
| NYISO | 422 |

## Body markers (first 800 chars)

| marker | messages |
|---|---|
| TO: | 216863 |
| FROM: | 112720 |
| DATE: | 21403 |
| DEAR  | 15861 |
| NOTICE | 13728 |
| ATTACHMENT | 7900 |
| DEMAND | 5790 |
| VOICE MAIL | 3387 |
| MEMORANDUM | 1496 |
| NOTICE OF | 1382 |
| DEMAND FOR | 630 |
| INTEROFFICE | 397 |
| FOR IMMEDIATE RELEASE | 321 |
| FOR RELEASE | 122 |
| MEETING REQUEST | 100 |
| INTER-OFFICE | 50 |
| MEETING INVITATION | 35 |

## Sender classes

- Attorney markers in sender display names: **0** messages

| sender | messages |
|---|---|

Top sender domains (external):

| domain | messages |
|---|---|
| enron.com | 427777 |
| aol.com | 2801 |
| hotmail.com | 2427 |
| mailman.enron.com | 1775 |
| txu.com | 1653 |
| nymex.com | 1438 |
| haas.berkeley.edu | 1317 |
| yahoo.com | 1309 |
| carrfut.com | 1303 |
| ccomad3.uu.commissioner.com | 877 |
| caiso.com | 838 |
| bracepatt.com | 821 |
| columbiaenergygroup.com | 776 |
| lists.thebiz.net | 716 |
| nyiso.com | 715 |
| intcx.com | 671 |
| govadv.com | 654 |
| earthlink.net | 647 |
| duke-energy.com | 623 |
| williams.com | 618 |
| gmssr.com | 604 |
| akllp.com | 553 |
| concureworkplace.com | 531 |
| kslaw.com | 525 |
| houston.rr.com | 485 |

## MIME / content shapes

| body content type | messages |
|---|---|
| text/plain | 517390 |

Attachment MIME types:

| mime | count |
|---|---|

## `other` residual (the coverage measure)

Rows routed to `other`: **0** (0.00%)
None — every parseable row maps to a real subclass.
