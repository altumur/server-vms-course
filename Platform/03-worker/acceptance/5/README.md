# P/03.5 — SDK seams

This English text is the source; `ru/acceptance/5/README.md` is its Russian translation for people, not in the export (ADR-0121).

[seams.tsv](seams.tsv) contains kit tests through the real SDK, with the normalized ports of [forms/README.md](../../forms/README.md). The chapter norms are [03.5-worker.norms.md](../../spec/03.5-worker.norms.md). These are SDK witnesses, not process-runner scenarios; the chapter still has no separate process acceptance catalogue.

s2-plain-unit supplies a value written by current development mode without SECRETS_KEY: the recipient gets development-plain. It adds no old-format opening; s1 and the AAD/kid/key/envelope failures remain required.
