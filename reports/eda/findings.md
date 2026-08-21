# Enron EDA findings (condensed)

- Corpus: 436,960 messages, 128 custodians, 100.0% parseable.
- Subclass mix: email 427098 (97.7%), notice 2266 (0.5%), memo 3062 (0.7%), letter 1817 (0.4%), press_release 2315 (0.5%), demand 270 (0.1%), meeting_request 128 (0.0%), attorney_demand 4 (0.0%) — `email` dominates; `other` residual 0 (0.00%) = the unparseable/non-email files, so the enum fully covers the corpus.
- Attorney-demand pool: 4 attorney demands + 270 non-attorney demands; 1,127 attorney/law-firm senders (0.26%).
- Attachments: 0 (0.0%) messages carry attachment parts; 0 have _files/ sibling dirs. **This CMU dump is text-only** (verified: 60,019 sampled messages are 100% text/plain, 0 multipart) — no attachment handling is needed for the correspondence intake.
- Internal vs external: 83.0% enron.com senders; thread-prefixed (RE/FW) messages 36.0%.
- Bodies are small: median 744 chars (p99 15,699) — the 40k correspondence specialist cap covers >99% of bodies un-chunked.
