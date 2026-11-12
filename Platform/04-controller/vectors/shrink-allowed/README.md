# Vectors: whether shrinking is allowed

This English text is the source; the Russian translation `ru/vectors/shrink-allowed/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is lesson P/04 ([norms](../../spec/04-controller.norms.md) N3 «shortage(), order(), withdraw the order, shrink()»:
`shrink (step 9a)` — `condition`, `victim`; `in_flight(s)`, `number above want`; N1.4 `SHRINK_AFTER`). The participant is `<s>controller`. The bytes are written by the Specification. One case is one label set of the role in one pass
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
- `distinct` — `servers: distinct` and the place from the heartbeat;
- `per` — the `per` of the set (N3 «per label set»), an integer ≥ 1; `null` — there is no estimate (`no positive capacity estimate`);
- `servers` — `[{server, want, live}]`: `want` — `want(s)`, an integer 1…99; `live` — the numbers of the live processes of the role on `s` by
  the heartbeats (live(s)), without repeats;
- `workers` — `[{name, free, load, placeless, holder}]`: the live workers suitable for the set, the name `<prefix>-<server>-<n>`
  of a server from `servers`; `free` — free (capacity − load), `load` — the load (Σ of the weights of its units), integers ≥ 0;
  `placeless` — a live one without a place (the field `place_by` of the heartbeat is empty), `holder` — the keeper of a place; both are bool, meaningful only
  with `distinct`.

**Output** — `{shrink, why, victim}`: `shrink` — `true` only with `why: "ok"`; `victim` — the name of the victim, named also on
a refusal (who would be the victim), `null` — only with `no_victim`. Comparison — JSON by value.

## Binding the vector to the shrink form

The vector uses its declared input and victim selection below; it adds no runtime field or check. Bind the variables of [the shrink checks](../../forms/README.md#shrink-checks) as follows (P/04-R051):

| Form variable | Vector input or computation |
|---|---|
| `victim_exists` | The victim selected by the existing `shrink-victim` rules is not null; only live tops `n = want(s) > 1` qualify. |
| `distinct` | Input `distinct`: servers: distinct and a place from the heartbeat. |
| `waiting` | Input `waiting`, with a group as one piece. |
| `placeless` | There is a live input worker with `placeless: true`; read this only with `distinct`. |
| `no_shortage_for`, `SHRINK_AFTER` | Inputs `no_shortage_for`, `shrink_after`; null means a shortage; equality is not longer than the hold time. |
| `in_flight` | Sum over servers of the missing live numbers in `2…want(s)`; the base is excluded. |
| `per` | Input `per`, including null for no estimate. |
| `remaining_free_after_move` | `Σ free − load(victims)`: sum free over suitable live workers without the selected victim and without numbers above their server's want, then subtract the victim load. With `distinct`, only workers with `holder: true` contribute to the sum. |

The last row is the original hysteresis test: `Σ free − load(victims) < per` refuses; equality passes. The vector’s existing consistency assumptions still hold. This binding does not add a wanted-place field to its closed input; the existing victim/protection cases and composed process seams retain their scopes.

## Order of the reasons

The first matching row of [the shrink checks](../../forms/README.md#shrink-checks) selects `why` (P/04-R051). The vector uses the same conditions; `victim: null` only for `no_victim`.

**The victim** is the same as in [`shrink-victim`](../shrink-victim/README.md): the largest number `n` (as an integer, not by the slot
order), with equal numbers on different servers — the smaller name of the server in UTF-8 bytes. Victim candidates are only live tops `n = want(s) > 1` of their own servers. The capacity of the other suitable workers in 1…want(s) still counts by the ordinary hysteresis rule. A number above want is never a victim and its free does not count (N3 number above want). This also applies to `shrink-victim`, whose input has `want` for each server; the candidates come from `live`.


## Input not by form

The executor of the vector answers with code 2 (the cell `expect` — `@exit 2`) exactly to an input from the list: not a JSON object; an extra or
missing field (of the input, of an element of `servers`, of an element of `workers`); `prefix` or the name of a server not by the grammar (P/03.2
N1.4, P/02.4 N1.2); the name of a worker not `<prefix>-<server>-<n>` of a server from `servers`, `n` — not an integer 1…99 or with a leading zero;
a repeat of the name of a worker, of a server or of a number in `live`; `want` — not an integer 1…99; a number — not an integer or < 0; `shrink_after` < 1;
`per` ≤ 0; `holder` — not bool (the field is mandatory). An integer — by the exact decimal value of the notation, as `x-integer` (LAYERS §3): `1.0`, `1e0` — 1; `1.5`, a boolean, a string, a number outside binary64 — not an integer; the number `n` in the name of a worker is a lexeme of the string, without a leading zero. The rest is outside the vector: the rows
keep the input consistent — the number of each worker is in the `live` of its server, the victim is in `workers`, with `distinct`
a keeper of a place is not without a place.

## Who executes

Who executes it is the controller (`04-controller`: the condition and the victim of shrinking, P/04 N3 «shrink (step 9a)») — all the rows. Only read the ready result: the server script (`02-installer`, stops a number above `want`, P/02.4 N1.5) and the worker (`03-worker`, the planned stop on `retiring`, P/03.4 N3 «stop by SIGTERM») (a row is executed by the role whose norm calls its function).

## Not covered

By reading or by an acceptance step: the drain (shrinking without the hold-off and the hysteresis); the transfer of the units of the victim and `SHRINK_BUDGET`;
`retiring` already written (one victim per role; `end`, `cancel`); «each unit of the victim passes choose()» — by an acceptance
step; the clock (the first pass without a shortage) — N1.4. There is no field of the reason of not shrinking in the pass report (N1.2): the order
of the reasons and their words are held by this vector, the pass report does not show them.

only live top n=want(s)>1 is eligible. places.wanted protection is covered by shrink-victim and composed s36/s37, without adding a field to this closed form.