# Rights evaluator — vector

This English text is the source; the Russian translation `ru/vectors/rights-evaluator/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The algorithm is [the common rights-evaluator contract](../../contracts/rights-evaluator.md); its use at the store doors is P/01.2 N1.2 `pattern`, N1.3 «Evaluator». The input fixture is `rights.json` (judge-only: fixture bytes). The case columns are `role action key expect`, where `expect` is `allow` or `deny`.

**Run.** The runner starts a fresh store with `rights.json` (judge-only: fixture bytes) as `{rights}` («Stand» of the [common acceptance README](../../acceptance/README.md)) and
for each row makes a probe through the socket of the role: `read` — `GET /v1/get?key=<key>`, `write` — `POST /v1/write` `put`, `delete` —
`POST /v1/write` `delete` (without `cas`; an absent row is deleted successfully, M10/1 N3). The outcome of the probe:
- `deny` — `403 forbidden`;
- `allow` — only a confirmed success: for a read 200 of the form `Row` (including `{items: null, index: ""}`), for a write and a
  delete 200 `Written`;
- 5xx, a transport error and any other answer — an undetermined outcome: the probe counts neither as `allow` nor as `deny`, the run
  is not green.

The meaning of the evaluator is checked, not the bytes of the file.

**What is covered:**
- an exact pattern, a prefix (`*` only as the last character);
- literal characters: `*` not last, `!` not first;
- a final wildcard after a literal star (P/01.2-R008);
- `!` — the negation of the empty key, takes nothing away; `!*` — the negation of everything;
- a negation wins regardless of its place in the list;
- the rights of one action do not give another (`write`, `delete`): `delete` is its own list, the evaluator has no `delete = write`;
  an empty or absent `delete` — no deletes (P/01.2 N1.2).

## Who executes

Who executes — the store (`01-store`: the evaluator of P/01.2 N1.3, and in the store in the process too, P/01.1-22) — all rows, through the door of its role sockets. Do not execute: the agent in the process (`09-agent`, P/09.1 N1.11 `rights`) — the rights of its components are checked by the store in the process; the installer's rights generator (`02-installer`, P/02.5 N3 «generate_rights» step 4) — its own rule of covering the patterns of secret rows, not an evaluator of actions; the console (`06-console`, P/06.3) only refers to P/01.2 (a row is executed by the role whose norm calls its function).

## Vector wire

The vector wire is set by the `common/rights-evaluator` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.

`{rights}` in «Run» above is the substitution of the command `stand.store` of that stand run ([substitutions](../../acceptance/PROFILE.md#substitutions)), not a name of the vector command. The vector target of the package is separate: the profile entry `vectors` `common/rights-evaluator` receives only `{input}`, and the rights file reaches its native function as the fixture `rights.json` (judge-only: fixture bytes) in `files` of the envelope ([unified vector command](../../acceptance/PROFILE.md#unified-vector-command)). Its native output is one JSON string, `allow` or `deny`.
