# Vectors: whether shrinking is allowed

This English text is the source; the Russian translation `ru/vectors/shrink-allowed/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson P/04 ([norms](../../spec/04-controller.norms.md) N3 «shortage(), order(), withdraw the order, shrink()»:
`shrink (step 9a)` — `condition`, `victim`; `in_flight(s)`, `number above want`; N1.4 `SHRINK_AFTER`; ADR-0084 addendum (1) R3,
addendum (3) R13′, R16′, addendum (4) R28, addendum (5) R16‴). The participant is `<s>controller`. The bytes are written by the Specification (ADR-0083;
the Architect's decision of 2026-10-20, № 12 of the analysis of the review of stage B 3–5). One case is one label set of the role in one pass
(as [`order`](../order/README.md)).

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header. A cell is read byte for
byte. Fields: `case`, `input` and `expect` — JSON text, `note`. There are 53 rows: `ok` — 7, `no_victim` — 5, `placeless_with_waiting` —
2, `no_shortage_long_enough` — 7, `in_flight` — 3, `hysteresis` — 5, `@exit 2` — 24.

**Input** — `{prefix, shrink_after, no_shortage_for, waiting, distinct, per, servers, workers}`:
- `prefix` — the prefix of the names of the role (P/03.2 N1.4); `shrink_after` — `SHRINK_AFTER`, s, an integer ≥ 1;
- `no_shortage_for` — s, how long the set has had no shortage (from the first pass without a shortage, N1.4 deadlines), an integer ≥ 0;
  `null` — there is a shortage in this pass;
- `waiting` — the waiting units of the set (a group is one piece), an integer ≥ 0;
- `distinct` — `servers: distinct` and the place from the heartbeat (R16′, R16‴);
- `per` — the `per` of the set (N3 «per label set»), an integer ≥ 1; `null` — there is no estimate (`no positive capacity estimate`);
- `servers` — `[{server, want, live}]`: `want` — `want(s)`, an integer 1…99; `live` — the numbers of the live processes of the role on `s` by
  the heartbeats (live(s)), without repeats;
- `workers` — `[{name, free, load, placeless, holder}]`: the live workers suitable for the set, the name `<prefix>-<server>-<n>`
  of a server from `servers`; `free` — free (capacity − load), `load` — the load (Σ of the weights of its units), integers ≥ 0;
  `placeless` — a live one without a place (the field `place_by` of the heartbeat is empty), `holder` — the keeper of a place; both are bool, meaningful only
  with `distinct` (the Architect's decision of 2026-10-20).

**Output** — `{shrink, why, victim}`: `shrink` — `true` only with `why: "ok"`; `victim` — the name of the victim, named also on
a refusal (who would be the victim), `null` — only with `no_victim`. Comparison — JSON by value.

## Order of the reasons

The check goes in order, `why` is the first reason that fired (P/04 N3 «shrink (step 9a)», `condition`):

1. `no_victim` — there is no live top number `n = want(s) > 1` on any server (only the base ones; a number above want is not in the pool,
   R28); `victim: null`;
2. `placeless_with_waiting` — `distinct`, `waiting > 0` and there is a live one without a place: the live ones without a place are not shrunk while there are
   waiting ones (R16′, R16‴); without `distinct` `placeless` is not read;
3. `no_shortage_long_enough` — `waiting > 0` («no shortage» — there are no waiting ones), or `no_shortage_for` `null`, or
   `no_shortage_for ≤ shrink_after`: the norm is «no shortage for **longer** than SHRINK_AFTER», equality is not yet «longer»
   (the Architect's decision of 2026-10-20);
4. `in_flight` — at some server `|{2…want(s)} ∖ live(s)| > 0`: in flight — by numbers by the heartbeats, not by a count (R13′);
5. `hysteresis` — `per` `null` or `Σ free` of the workers without the victim and without the numbers above the want of their server `− load(victims) < per`:
   after the transfer of the units of the victim the remaining ones have less free than `per` (R3); equality to `per` passes; with `distinct` only the keepers of places (`holder: true`)
   enter `Σ free` — as «free at suitable live workers» of N3 «per label set» (R16′; the Architect's decision of 2026-10-20);
6. `ok` — shrink, `victim` — the victim.

**The victim** is the same as in [`shrink-victim`](../shrink-victim/README.md): the largest number `n` (as an integer, not by the slot
order), with equal numbers on different servers — the smaller name of the server in UTF-8 bytes. Victim candidates are only live tops `n = want(s) > 1` of their own servers. The capacity of the other suitable workers in 1…want(s) still counts by the ordinary hysteresis rule. A number above want is never a victim and its free does not count (N3 number above want, R28). This also applies to `shrink-victim`, whose input has `want` for each server; the candidates come from `live` (review of stage B 6–7, no. 42; reading of cammeta-acceptance commits, 2026-10-20).


## Input not by form (R22)

The executor of the vector answers with code 2 (the cell `expect` — `@exit 2`) exactly to an input from the list: not a JSON object; an extra or
missing field (of the input, of an element of `servers`, of an element of `workers`); `prefix` or the name of a server not by the grammar (P/03.2
N1.4, P/02.4 N1.2); the name of a worker not `<prefix>-<server>-<n>` of a server from `servers`, `n` — not an integer 1…99 or with a leading zero;
a repeat of the name of a worker, of a server or of a number in `live`; `want` — not an integer 1…99; a number — not an integer or < 0; `shrink_after` < 1;
`per` ≤ 0; `holder` — not bool (the field is mandatory, the Architect's decision of 2026-10-20). An integer — by the exact decimal value of the notation, as `x-integer` (LAYERS §3): `1.0`, `1e0` — 1; `1.5`, a boolean, a string, a number outside binary64 — not an integer; the number `n` in the name of a worker is a lexeme of the string, without a leading zero (C04-VECTOR-INT-VALUE-01). The rest is outside the vector (ADR-0084 addendum (2) R22): the rows
keep the input consistent — the number of each worker is in the `live` of its server, the victim is in `workers`, with `distinct`
a keeper of a place is not without a place.

## Who executes

Who executes it is the controller (`04-controller`: the condition and the victim of shrinking, P/04 N3 «shrink (step 9a)») — all the rows. Only read the ready result: the server script (`02-installer`, stops a number above `want`, P/02.4 N1.5) and the worker (`03-worker`, the planned stop on `retiring`, P/03.4 N3 «stop by SIGTERM») (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Not covered

By reading or by an acceptance step: the drain (shrinking without the hold-off and the hysteresis, R7); the transfer of the units of the victim and `SHRINK_BUDGET`;
`retiring` already written (one victim per role; `end`, `cancel`); «each unit of the victim passes choose()» — by an acceptance
step; the clock (the first pass without a shortage) — N1.4. There is no field of the reason of not shrinking in the pass report (N1.2): the order
of the reasons and their words are held by this vector, the pass report does not show them (the Architect's decision of 2026-10-20).

ADR-0127 P/04 C1: only live top n=want(s)>1 is eligible. places.wanted protection is covered by shrink-victim and composed s36/s37, without adding a field to this closed form.
 Named-input-to-outcome associations are in [judge-only case data](README.cases.md).