# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/1/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

A change of `key`, `cas`, `guard`, `not_after` and `not_before` on a replay of `delete` is now scenario 30 (below).

### Original passage 2

## Coverage audit of P/01, second pass (sc. 30–32)

The coverage audit session, second pass (Gemini, 2026-10-30, commit 6a5817f88, `coverage audit Gemini P01 (for people)`, G01–G03):
- Sc. 30 — the replay fingerprint by value (N3 «write», «delete»): for `put` a reversed order of the fields of `items` and an absent
  `cas` instead of `cas: null` give the same fingerprint (`again`); `delete` under the `id` of a `put` write — 400. For `delete` under one `id`
  (`cas`, `guard`, `not_before`, `not_after`): `items` as an array and `1.0` instead of `1` — `again`; a different `key`, `cas` `""` and no
  `cas`, a different key and version of the guard and no guard, a different `not_after` and `not_before` — 400; `put` under this `id` — 400; the row is
  deleted once.
- Sc. 31 — steps 1–4: deleting an absent row with `cas: ""` — 200 and a new version, the row is still `null, ""`,
  creation with `cas: ""` after it passes (N3 «delete», «Races»); steps 5–7: a replay of a write for which by the time of the replay both
  `cas` and the guard are violated — its answer with `again` (the `id` memory before the guard and CAS); steps 8–13: after the refusals `early`, `guard` and
  `conflict`, the same write with the same `id` and a corrected condition — a new write without `again` (N3: a refusal does not occupy the `id`).
- Sc. 32 — the order of the checks of a command of N2.1 on pairs of violations; each pair tells adjacent steps apart by the kind of refusal: `op`
  before the key; the socket of `floor` before the form of `floor` and `id`; the form of the key before the guard; the rules of the key before `items`;
  `items` and `cas` before the guard (`badrequest`, not `badkey`); `id` and `not_after` before the weight and the rights (`400`, not `413` and not
  `403`); `id: null` and `not_after: 1e400` (not finite in binary64) — 400; a lone surrogate in `guard.key` — `badkey`, in a
  value of `items` — `badrequest`. Steps 13–14 see that nothing is written either under `acc/` or under `other/`.

### Original passage 3

## Batch (sc. 33–40; ADR-0094 B9)

- Sc. 33 — all or nothing: step 6 — the `cas` of the second row is stale, steps 7–8 see both rows as before; steps 4 and 10 — one version for all rows.
- Sc. 34 — creation, edit and removal in one batch; step 7 — delete of an absent row; steps 10, 12 — `items` of delete is not read; step 11 — the `cas` of the removed row is stale.
- Sc. 35 — guards: step 3 — the guard is not written; step 7 — the guard before `cas`; steps 8–9 and 10–11 — the first violation in the order of `guards` and `writes`.
- Sc. 36 — the fingerprint: steps 2–4 — the order of `guards` and of the fields of `items`, `cas: null` give the same; steps 5–9 — a different one; steps 10–12 — the memory is shared with the write; step 14 — the memory before the guard;
  steps 15–16 — a refusal does not occupy the `id`; steps 17–21 — `items` of delete is not included, `cas` is.
- Sc. 37 — deadlines: steps 5–6 — before the guards and `cas`, steps 7–8 — a refusal does not occupy the `id`.
- Sc. 38 — the form; steps 26–30 — the order of the checks of N2.1 on pairs of violations; steps 31–32 — one over the limit, steps 35–36 — exactly at the limit; step 37 — extra top-level fields, among them the fields of a single write, are not read.
- Sc. 39 — the weight: two rows of 400000 bytes each are together heavier than the ceiling, each is lighter; a row heavier than the ceiling — 413 with its `key`. The weight of `@big`: the field name plus the value.
- Sc. 40 — rights: 403 before deadlines (step 5), a refusal does not occupy the `id` (steps 6, 8).

The role `console` does not know the limit on the number of rows — sc. 16 of chapter 1.2. Restart and the group — sc. 30, 31 of chapter 1.3. The refusal of a body over the limit is a common refusal before JSON parsing, sc. 22.
