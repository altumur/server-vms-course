# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/3/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

[`02.3-installer.norms.md`](../../spec/02.3-installer.norms.md) N5. `puts.tsv` has 87 installations (9 after `near_*` — the coverage audit P/02 of 2026-10-30, the next 16 — its second pass, below; the 11 next ones — ADR-0094 B7; 3 `calls_*` — the callback list at a subsystem of the catalogue, ADR-0094 B1; 3 `calls_requests_*` — the entry `<s>/requests` of another subsystem (it is in the catalogue without `requests` — accepted; it is absent — a deferral) and of the own one, P/06.3 N1.9 (review of lesson P/02, S5); 3 `calls_first_*`, `calls_second_kind` — ADR-0112 addendum (3) item 2; the last two `calls_pulse_ok`, `calls_pulse_bad` — the declared heartbeat callback); the installation files are in `puts/`.
