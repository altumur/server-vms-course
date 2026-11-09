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
