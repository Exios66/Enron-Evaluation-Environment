# Enron correspondence samples (cleanly formatted Markdown)

Human-readable, taxonomy-stratified selection of the CMU Enron
corpus. The raw maildir and the index are gitignored — THIS folder
is the only committed corpus text, so the selection stays bounded.

| Sample | Subclass | From | Date | Subject |
| --- | --- | --- | --- | --- |
| [`attorney_demand-sanders-r-all_documents-sanders-r-all_documents-126..md`](attorney_demand-sanders-r-all_documents-sanders-r-all_documents-126..md) | Attorney Demand | showard@milbank.com | 2000-05-22 | Ecogas |
| [`attorney_demand-sanders-r-ecogas-sanders-r-ecogas-26..md`](attorney_demand-sanders-r-ecogas-sanders-r-ecogas-26..md) | Attorney Demand | showard@milbank.com | 2000-05-22 | Ecogas |
| [`demand-bailey-s-deleted_items-bailey-s-deleted_items-294..md`](demand-bailey-s-deleted_items-bailey-s-deleted_items-294..md) | Demand | louis.dicarlo@enron.com | 2002-03-11 | Cross Oil & Refining |
| [`demand-delainey-d-all_documents-delainey-d-all_documents-897..md`](demand-delainey-d-all_documents-delainey-d-all_documents-897..md) | Demand | david.delainey@enron.com | 2000-12-19 | Elektrobolt DASH - EE&CC Questions/Comments |
| [`email-allen-p-_sent_mail-allen-p-_sent_mail-1003..md`](email-allen-p-_sent_mail-allen-p-_sent_mail-1003..md) | Email | phillip.allen@enron.com | 2000-08-22 | (no subject) |
| [`email-allen-p-_sent_mail-allen-p-_sent_mail-193..md`](email-allen-p-_sent_mail-allen-p-_sent_mail-193..md) | Email | phillip.allen@enron.com | 2000-08-09 | Re: TRANSPORTATION MODEL |
| [`letter-arnold-j-notes_inbox-arnold-j-notes_inbox-74..md`](letter-arnold-j-notes_inbox-arnold-j-notes_inbox-74..md) | Letter | thanks@amazon.com | 2001-05-11 | Free Shipping for Your Amazoniversary |
| [`letter-buy-r-inbox-buy-r-inbox-832..md`](letter-buy-r-inbox-buy-r-inbox-832..md) | Letter | ellen_prendergast@america.hypovereinsbank.com | 2001-09-07 | Reception & Dinner, October 24, 01 |
| [`meeting_request-farmer-d-discussion_threads-farmer-d-discussion_threads-1164..md`](meeting_request-farmer-d-discussion_threads-farmer-d-discussion_threads-1164..md) | Meeting Request | heather.choate@enron.com | 2000-05-19 | Customer Meeting Invitation |
| [`meeting_request-germany-c-inbox-germany-c-inbox-94..md`](meeting_request-germany-c-inbox-germany-c-inbox-94..md) | Meeting Request | judy.townsend@enron.com | 2001-05-18 | FW: Meeting Invitation from Steve Westgate |
| [`memo-beck-s-all_documents-beck-s-all_documents-257..md`](memo-beck-s-all_documents-beck-s-all_documents-257..md) | Memorandum | bob.hall@enron.com | 2001-01-23 | Re: 2001 Anticipated Budget Adjustments for HPL Sale |
| [`memo-beck-s-discussion_threads-beck-s-discussion_threads-1255..md`](memo-beck-s-discussion_threads-beck-s-discussion_threads-1255..md) | Memorandum | gary.stadler@enron.com | 2000-06-26 | May Curve Validation Memorandum |
| [`notice-arnold-j-deleted_items-arnold-j-deleted_items-701..md`](notice-arnold-j-deleted_items-arnold-j-deleted_items-701..md) | Notice | m..schmidt@enron.com | 2001-11-19 | Enron Mentions - 11/19/01 |
| [`notice-bass-e-deleted_items-bass-e-deleted_items-225..md`](notice-bass-e-deleted_items-bass-e-deleted_items-225..md) | Notice | no.address@enron.com | 2002-01-03 | NOTICE TO: All Current Enron Employees who Participate in the Enron Co |
| [`press_release-bass-e-notes_inbox-bass-e-notes_inbox-89..md`](press_release-bass-e-notes_inbox-bass-e-notes_inbox-89..md) | Press Release | newsletters@newsletters.dallasnews.com | 2000-12-07 | Inside UT Football: December 7, 2000 |
| [`press_release-dasovich-j-all_documents-dasovich-j-all_documents-10826..md`](press_release-dasovich-j-all_documents-dasovich-j-all_documents-10826..md) | Press Release | jmunoz@mcnallytemple.com | 2001-04-09 | Congressional Hearing Schedule/State Senate Hearing Rescheduled |

## Regenerating

```bash
python scripts/acquire_enron.py     # corpus (gitignored)
python scripts/build_samples.py     # deterministic (seed 20150507)
```

Selection law: 2 per subclass key, reservoir 120, walk cap 517401, body cap 6000, seed 20150507. Same corpus + seed ⇒ byte-identical output.

## Source & scope

Text is verbatim from the public CMU Enron email corpus
(tarball 2015-05-07), rendered read-only for human orientation.
Subclass labels come from the shared labeler (`scripts/correspondence_subclasses.py`) with per-file evidence.
