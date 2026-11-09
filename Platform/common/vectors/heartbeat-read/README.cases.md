# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/heartbeat-read/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing case data as judge-only provenance.

### Original passage 1

P/05). The participants are the observers of `resource_state`: the controller and the console. The bytes are written by «Specification»; the expectations are obtained by the judge
of the family schemas of the skill (the reader mode, LAYERS.md §§ 6–7), not by the code of implementations.

### Original passage 2

19 rows: 11 readable (7 of them with a field outcome), 8 unreadable. The lexemes of time and of integers (OBS154-RAW-TIME-EXACT-01, the Architect's decision
2026-10-26): the time `ts`, `usage_at` with `1e0`, `1e-400`, `-0` — not of the form (`codec.tsv` `time`, the reader); `usage` `100.0` is
the integer 100, `100.00000000000000001` is not an integer by the exact decimal value of the lexeme, not after binary64; `schema` `1.0`
(`x-whole`) — a field outcome.

### Original passage 3

20 rows: of the form; not an object, no `instance`, `status` not a list, `worker` ≠ the name in the key (the prose rule of P/03.4 N1.1, the outcome
«the whole object») — unreadable; an element without `phase`, with a non-integer `epoch`, `sealed` with `epoch`, `id` not by the grammar — a skip at
`GET /{rows}`, unreadable to the others; `unreadable` with `why` — of the form; the field outcomes `build`, `schema`, `pending_writes`; the path `""`
before `/status` — unreadable to all. The expectations — by the judge of the family schemas of the skill (the reader mode), the rule `worker` — by the prose.
The lexemes (OBS154-RAW-TIME-EXACT-01): `ts`, `started`, `previous_hb` with `1e0`, `1e-400`, `-0` — unreadable to all; `freeing` `100.0` —
readable, `100.00000000000000001` — unreadable to all (`freeing` has no field outcome); `pending_writes` `1.0` (`x-whole`) — a field outcome.

End of judge-only case data.
