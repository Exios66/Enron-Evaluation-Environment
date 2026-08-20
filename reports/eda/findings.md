# Enron EDA findings (condensed)

- Corpus: 517,390 messages, 150 custodians, 100.0% parseable.
- Subclass mix: email 505929 (97.8%), notice 2842 (0.5%), memo 3568 (0.7%), letter 2077 (0.4%), press_release 2520 (0.5%), demand 315 (0.1%), meeting_request 135 (0.0%), attorney_demand 4 (0.0%) — `email` dominates; `other` residual 0 (0.00%) = the unparseable/non-email files, so the enum fully covers the corpus.
- Attorney-demand pool: 4 attorney demands + 315 non-attorney demands; 2,261 attorney/law-firm senders (0.44%).
- Attachments: 0 (0.0%) messages carry attachment parts; 0 have _files/ sibling dirs. **This CMU dump is text-only** (verified: 60,019 sampled messages are 100% text/plain, 0 multipart) — no attachment handling is needed for the correspondence intake.
- Internal vs external: 83.1% enron.com senders; thread-prefixed (RE/FW) messages 36.5%.
- Bodies are small: median 756 chars (p99 14,064) — the 40k correspondence specialist cap covers >99% of bodies un-chunked.
