# Vectors: the shortage of a label set and the order by servers

This English text is the source; the Russian translation `ru/vectors/order/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is lesson P/04 ([norms](../../spec/04-controller.norms.md) N3 «shortage(), order(), withdraw the order, shrink()»: `in_flight`, `per`, `need`, `candidate`,
`order`, `order_row`). The participant is `<s>controller`. The bytes are written by
the Specification.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header. A cell is read byte for
byte, nothing is expanded. Four fields: `case`, `input` and `expect` — JSON text, `note` — why the row is there.

**Input** — one label set; all the servers and workers of the input suit it (the labels, `requires` and the resource are not the subject of the vector;
`servers: distinct` — only by the fields `place_by` of the set and `placeless` of a server below):
- `default` — `placement.capacity.default` of the manifest (an integer ≥ 0);
- `workers` — the suitable live workers: `capacity` (an integer or `null` — the capacity is not named) and `free` (free);
- `waiting` — the exact nonnegative integer sum of the weights of the waiting ones, `groups` — the number of groups for which there is no place anywhere;
- `servers` — `{<server>: {want, live, room, base?, numbers?, door?, placeless?, drained?, quiet?}}`: `want` — the order row, `live` — live(s)
  by the heartbeats (with the base and the victim), `room` — `room.<sub>`, `base` — the base `-1` is alive (no field — `true`), `drained` —
  a drain or a decommission, `quiet` — «failed to raise» in the window `RAISE_QUIET`. `numbers` — the numbers of the live processes of the role by the heartbeats
  (the base `1` if it is alive; `live` of them); no field — consecutive: `1…live` with `base: true`, otherwise `2…live + 1`. `in_flight(s)` =
  `|{2…want} ∖ numbers|` — by numbers, not by a count; with consecutive numbers —
  `max(0, (want − 1) − ordered)`. `door` — the list `live.<sub>` of the door row: the numbers n ≥ 2 of the live locks; no field —
  the numbers n ≥ 2 from `numbers` (the door coincides with the heartbeats), `null` — the door has no `live.<sub>`: the server is not a candidate; `free(s)` = `room −
  |{2…want} ∖ door|`, once per pass, minus each share;
- `place_by` of the set and `placeless` of a server — only with `servers: distinct` and the place from the heartbeat: `place_by` — the name of the place field,
  `placeless` — the number of suitable live processes without a place on this server (no field — 0; their free does not enter
  `workers`: only the keepers are there); a candidate is a server with `placeless` 0 and without a probe in flight (`in_flight(s)` 0); the growth of the set is no
  more than one trial process per pass; the rest — `withheld` with `why: "no free <place_by>"`.
  A caveat: the capacity of a process without a place enters `per` (N3 `per` — over all the suitable live ones), but it is not in `workers` of the vector;
  the rows with `placeless` take it no less than the `per` of the keepers (equal to `default`). A case where the capacity of a worker without a place is less than
  the capacities of the keepers and therefore sets `per`, the vector does not express — by reading.

**Output** — `{per, processes, in_flight, need, orders, withheld}`: `in_flight` — Σ `in_flight(s)`, `need` — needed,
`orders` — the new `want` of the servers that got a share, `withheld` — the remainder without a candidate, a number of processes (as the series
`workers_withheld{labels}` of P/06.5). `in_flight` — how much in flight the set took: `min(Σ in_flight, processes)`. The capacity of
a worker without a named one is `default`; `per` is the smallest positive one over all `workers`, named or `default`; a named 0
is not replaced with `default`. Without a computable `per` — an element of the same fields: `{per: null, processes: 0, in_flight: 0,
need: 0, orders: {}, withheld: 0, why: "no positive capacity estimate"}` (`why` — the words of `short.withheld` of the report, N1.2).

**Several sets** — an input with `sets: [{labels, waiting, groups}]` instead of `waiting` and `groups`; all the servers and workers
of the input suit each set. A label set is a set: the canonical writing is the unique labels in ascending order separated by
commas, a repeat collapses. The sets go in the order of the UTF-8 bytes of the canonical writing (the empty one first); a set takes the free, `in_flight` and `room` only up to its need, the rest goes to the next one (N3 «set order»). The output — `{sets: {<canonical record>: {per, processes, in_flight, need,
withheld}}, orders, withheld}`: the `in_flight` of a set — how much capacity in flight it took, `orders` — the final `want` of the servers,
`withheld` — the sum over the sets.

**Comparison** — JSON by value; `orders` is an object, the order of the keys does not matter.

## Input not by form

The executor of the vector answers with code 2 (the cell `expect` — `@exit 2`) exactly to an input from the list: not a JSON object; a field of the wrong
type (numbers — integers ≥ 0, `capacity` — an integer ≥ 0 or `null`, `base`, `drained`, `quiet` — booleans, labels — strings by [the label
alphabet](../../../common/contracts/labels.md)); `want` outside 1…99; `live` outside 0…99; `door` — not a list or `null`, a number in it outside 2…99 or a repeat;
the name of a server not by the grammar of a server (P/02.4 N1.2); two sets with one canonical writing; `placeless` at a server without `place_by` of the set;
`numbers` — not a list of integers 1…99, with a repeat or not `live` of them. An input by form with an inadmissible metric is not a refusal: the capacity of a heartbeat not as a number (P/04 N1.3) — the worker accepts
no units and does not enter `workers`; an unreadable door row — `door: null`. For fields other than the aggregate waiting/sets[].waiting, an integer is by the exact decimal value of the notation, as `x-integer` (LAYERS §3): `1.0`, `1e0` — 1; `1.5`, a boolean, a string, a number outside binary64 — not an integer; the number `n` in the name of a worker is a lexeme of the string, without a leading zero. The rest is outside the vector.

## Who executes

Who executes it is the controller (`04-controller`: the shortage, `in_flight`, `free(s)`, the candidates and the shares, P/04 N3 «shortage(), order()») — all the rows. Only read the ready result: the resource (`05-resource`, writes `room`/`live` of the door row, P/05 N1.4 `door_row`), the server script (`02-installer`, P/02.4 N1.5) and the console (`06-console`, the series `workers_wanted`/`workers_withheld`, P/06.5 N3 «/metrics — text») (a row is executed by the role whose norm calls its function).

## What the vector does not cover

The withdrawal by the deadline,
a number above want and the shrinking — by time, acceptance steps.

The aggregate waiting/sets[].waiting keeps integer-by-value spellings, but has no common.uint53 ceiling or binary64/int64 conversion. Compute sums and ceil division exactly; individual weight/capacity and all other input domains remain unchanged.