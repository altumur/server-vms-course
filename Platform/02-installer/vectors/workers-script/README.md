# Vectors: the on-demand workers script

This English text is the source; the Russian translation `ru/vectors/workers-script/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter [P/02.4](../../spec/02.4-installer.norms.md) of the installer (N1.5 «Workers on demand», `rules` 2–4). The participant is `w2c-workers.sh` of the server. The bytes are written by the Specification.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header. A cell is read byte for
byte. Fields: `case`, `input` and `expect` — JSON text, `note`.

**Input** — one role of the server: `{want, running, console?, reconcile_age?, memory?}`:
- `want` — the text of the value of the series `<sub>_workers_wanted{server}` or `null` (there is no series);
- `running` — the numbers of the running instances `n ≥ 2` (the base `-1` is not included);
- `console` — `"ok"` (the last successful scrape of `/metrics` is no older than a minute) or `"silent"` (the scrape failed or is older than
  a minute by the monotonic clock of the script); no field — `"ok"`;
- `reconcile_age` — the text of the value of the series `<sub>_reconcile_last_success_age_seconds` by the value form of P/06.5 N3 «/metrics — text»
  (the canonical JCS notation: a fraction is allowed — `60.5`, `0.5`; `-1`; another notation — `1e1`, `60.50`, `+5` — not by form, do nothing);
  the comparison with 60 — by value; no field — the series is in order;
- `memory` — the values of `roles/<role>.env` as strings as written: `{HOST_MEMORY_MB, WORKER_MEMORY_MB, CAPACITY}`; `null` —
  there is no file; no field — the memory ceiling does not limit.

**Output** — `{start: [<n>…], stop: [<n>…]}` in ascending order: the target is exactly the numbers `{2…want}`: start the missing ones
(the smallest first), stop the running ones with a number greater than `want` (the largest first); a number — as an integer (numbers,
not a count). The memory ceiling
`floor(HOST_MEMORY_MB / WORKER_MEMORY_MB)` is the number of processes of the role on the server together with the base `-1`: no more than
`ceiling − 1 − running n ≥ 2` are started. Start nothing and stop nothing (`{start: [], stop: []}`) if: there is no series,
the value is not by the metric form of P/06.5 N3 «/metrics — text» (an integer without leading zeros, sign and fraction — `02`, `2.0` are not read) or outside 1…99
(rules 2); the console is silent or `reconcile_age` is greater than 60 or `-1` (rules 2); there is no role file, the budget is not a positive
integer, `CAPACITY` is not an integer > 0 or the divisor is zero (rules 4). Comparison — JSON by value.

Not covered by the vectors: the serialization of passes and the reservation of numbers (rules 5) — by the stand acceptance (`@grow`, [the common acceptance README](../../../common/acceptance/README.md))
and by reading; a single execution mechanism (rules 6) — by reading.

## Who executes

Who executes — the installer (`02-installer`: the server script `w2c-workers.sh`, P/02.4 N1.5 `rules` 2–4). Only read the ready result: the controller (`04-controller`, writes `want` of the order row, P/04 N1.1) and the console (`06-console`, the series `workers_wanted{server}`, P/06.5 N3 «/metrics — text»); the worker (`03-worker`) only accepts the stop (a row is executed by the role whose norm calls its function).

## Vector wire

The wire of `cases.tsv` (judge-only: the table itself) is set by the `02-installer/workers-script` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
