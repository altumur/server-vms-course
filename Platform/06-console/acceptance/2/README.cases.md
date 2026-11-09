# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/2/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

The units door of `testsub2` (the rows `tallies`; the tables door `shelves` — sc. 10; the console root `CONSOLE_ROOT=testsub2`, the common acceptance README «Stand») and the store door; the format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) (`console`, `store`, `@key`, `@as`, a subset of fields). The implementation is started with a key ring (`SECRETS_KEY`), the manifests `testsub` and `testsub2`, an empty store; the resource `srv-a` is the first step of sc. 01, 05, 09 (the processes are restarted between scenarios; `@start resource`: `GET /tallies` reads the heartbeats through the objects door of the resource of its server; C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29); the store rows are read by a role with the right to read `testsub2/` (for example, `testsub2worker`), sc. 06 — by a role without the right (`testsubworker`). The field `of` of `tallies` is the name of a counter of `testsub`; before the scenarios the runner creates the counter `c1` in `testsub`.

Scenario boundaries: the processes are restarted between scenarios, the variables are reset, and **the store is kept** within the file — the scenarios run in order, and sc. 05 reads rows written earlier; the file begins with an empty store.

The file has 11 scenarios / 65 steps (sc. 10 — the coverage audit of P/06, sc. 11 — its second pass, Gemini). Before a full repeat a new instance gets empty

  the ordinary happy repeat of scenario 01 does not replace it.
