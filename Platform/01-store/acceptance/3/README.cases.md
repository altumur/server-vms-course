# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/3/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

## Reconciliation of python and go M10/6–11 (sc. 08 steps 10–12, sc. 14, 15)

- Sc. 08 steps 10–12: `floor` that is not an integer JSON (`2.0e1`) — 400 before the write, not 409 «only upwards»; the largest uint64 is
  out of the floor form and gives 400; the upper bound of N1.3 floor `form` itself is admissible (B5).
- Sc. 14: the `id` replay memory is not part of the copy (N1.3 `copy`). A write with `id` `b1` on the stand store, a copy, a transfer:
  a replay of the same `id` at the transferred store — a new write without `again`, the next replay — `again` (B10). The key `other/b10` is
  outside the stand families; `admin` writes it.
- Sc. 15: service doors (N2). Steps 1–2 — `@as console`: `join` and `leave` from a role socket — 403 before the membership (B1); steps
  3–4 — the body `@big(1048577)` is larger than the 1 MiB limit — 413, for `PUT /v1/status` before 405 (framing → route, B2, B3); step 6 —
  empty `raft`/`api` — 400 (B4); steps 7–8 — `HEAD`. Step 9 of sc. 15 (`door.pass` `testsub2` without a worker with a door — 503,
  B26) was moved to step 1 of sc. 15 of [the acceptance of chapter 6.5](../../../06-console/acceptance/5/README.md): it needs the console.
