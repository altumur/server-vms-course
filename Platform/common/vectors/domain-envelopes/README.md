# Domain envelope vectors

This English text is the source; the Russian translation `ru/vectors/domain-envelopes/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The vectors of [the domain envelopes contract](../../contracts/domain-envelopes.md): the opening and the round of the envelopes `x25519:v1` (the contribution
of a member to the book acceptance key) and `m1` (the holder's answer to a member). The package is common: one process seals, another opens
(the agent and the holder are different lessons and, on the matrix stand, different implementations; review analysis of stage A 8–10, № 12; ADR-0083
addendum (13)). The bytes are written by «Specification» (ADR-0083); the conformance of the product is by its acceptance against these tables (ADR-0080 addendum 16).

The rows were transferred from the inputs of the vector commands of the acceptance of M11 without a change of bytes: `x25519-*` — from
M11/2 (`inputs/seal-*.json`, sc. 08–11), `m1-*` — from
M11/3 (`inputs/seal-member-*.json`, sc. 11–12); `case` is
the name of the input file. The scenarios M11/02 sc. 08–11 and M11/03 sc. 11, 12 and their inputs were removed by the move of lesson 8 (ADR-0083 addendum (14)
item 17; the logs — [the README of the package `domain-token`](../domain-token/README.cases.md#source-log) (M11/02), the acceptance of chapter P/08.3 (`corrections-3.tsv` (historical correction record), a log, not in the export)): the tables are the only source of these cases.

## Run

Without a stand, by the function of an implementation: the opening (`x25519-open.tsv`, `m1-open.tsv`) gives a value or a refusal word; the round
(`x25519-round.tsv`, `m1-round.tsv`) — the implementation seals twice by its own sealing and opens its own envelopes. The opening vector does not check the form
of sealing: it is non-deterministic (new `eph` and `nonce`), it is checked by the round and by the opening of
foreign envelopes. Who performs it — by the table (the contract, the table of participants): the opening — the opener: `x25519-open.tsv` —
the process `domain` (`08-domain`: the assembly of a book, the target of the transfer), `m1-open.tsv` — the agent of a member (`09-agent`); the round —
the sealer: `x25519-round.tsv` — the agent of a member (`09-agent`) and the process `domain` (`08-domain`, `keys_sealed`),
`m1-round.tsv` — the process `domain` (`08-domain`); the relay only carries envelopes — it performs no tables (ACC-VECTORS-CONNECT-02, the Architect's decision 2026-10-26).

The commands and the output forms are the same as at the former acceptance of M11: `seal`, `seal-round` — [P/08.2](../../../08-domain/spec/08.2-domain.norms.md)
N5 (formerly M11/2 N5); `seal-member`, `seal-member-round` — the table below (formerly M11/3 N5, removed by the move of lesson 8; the input
of `seal-member` — `{seed, sealed}`, of `seal-member-round` — `{key, seed, plain}`; review analysis of stage B 8–10, № 22, Claude
M-1); the comparison — a subset of fields, the cell `expect` sets `result` (and the value or the refusal word) (the reading of the commits
of «cammeta-acceptance» 2026-10-20):

| Table | Command | Output |
|---|---|---|
| `x25519-open.tsv` | `seal` | `{result: ok, plain}` or `{result: refused, reason}` |
| `x25519-round.tsv` | `seal-round` | `{result: ok, envelopes: [<envelope>, <envelope>], opened: [<plain>, <plain>], distinct}` or `{result: refused, reason}` |
| `m1-open.tsv` | `seal-member` | `{result: ok, plain}` or `{result: refused, reason}` |
| `m1-round.tsv` | `seal-member-round` | `{result: ok, sealed: [<m1>, <m1>], opened: [<plain>, <plain>], distinct}` |

At the rounds `ok` — both envelopes opened into `plain` and differ (`distinct: true`); the form of the envelopes — by the contract: `envelopes` —
«Envelope `x25519:v1`», `sealed` — «Envelope m1».

## Keys

The seeds are 32 bytes `sha256("w2c test <word>")` (as the keys of [the sealing vectors](../sealing/README.md) and
of [the door token](../door-token/README.md)); the table does not name the words of derivation — the bytes are fixed here, an implementation
takes them from here. The envelopes of the opening vectors are sealed with the one-time seeds `eph 1…3` and `nonce` — the bytes 0…11 only for
reproducibility; in operation `eph` and `nonce` are random (the contract, `seal`).

| Key | Seed (seed_hex) | Public key |
|---|---|---|
| book intake 1 | `1eb2dc62053b3f42b95612f6a2d1b20c9b60097dd9b46e1325457e39ffc5be8a` | `book_seal` `bcd5fdec0a3585c7b8793b352a0322a72c6aa1801c1874dac9e7cebfc2c8f970` |
| book intake 2 | `7aa6f54ef18e05f623a4a0b502b1d177683400a6c087bda5fbe5d0404f28eb1f` | `book_seal` `57bf48000f17919375a83a26f7b2064ade5a0b8ee1c29f9a3bbdd87c28434603` |
| member `m1` | `c27e2aa35b5905de643148195bc7c476e5c8dabaf63a2e9bb2dd17ac6d5cac39` | Ed25519 `b7b1b2708888b80495bdee35906cdbf0143b649eb92b6cf1f95d8108a3533b62`; the X25519 recipient `e674744cfa9b0175d178e25c5d960eada81d66f5e6f45271e74abe8041239f23` |
| member `m2` | `8d4d3ebc0a45db1c1eb5d097be76dbf0e324a2a3d489cfa4afc50f6fe64e44ef` | Ed25519 `88cae557b9e5d4285769289b5af9d27cfdee0092823f38993912feae4b0c92c7` |

The X25519 recipient of a member is computed by the line `recipient` of the contract; the table `m1-open.tsv` checks it by opening.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header; `case` is the name of the row
(the name of the acceptance input file), `note` — why the row exists. The values `plain` and the opened value in `expect` are JSON strings.

| File | Input → expectation |
|---|---|
| [`x25519-open.tsv`](x25519-open.tsv), 16 rows | `seed_hex` (the seed of the book acceptance key), `envelope`, the AAD context `member`, `source_path`, `item`, `pointer` → a value or `not_v1`, `not_an_envelope`, `does_not_open`. Cases: it opens, an empty value, Cyrillic and `~`/`/` in the context; another intake key, another `member`, `source_path`, `item`, `pointer`, a tampered `ct`; another version, `=`, four parts, short `nonce` and `ct`, a zero `eph`, non-canonical base64url |
| [`x25519-round.tsv`](x25519-round.tsv), 2 rows | `book_seal_hex`, `seed_hex`, `plain`, the context → `ok` (both opened, the envelopes differ) or `not_an_envelope` (a `book_seal` of small order) |
| [`m1-open.tsv`](m1-open.tsv), 11 rows | `seed_hex` (the seed of the member key), `sealed` → a value or `not_m1`, `not_an_envelope`, `does_not_open`. Cases: it opens, empty; another member, the AAD of another key, a tampered `ct`; the tag `m2:`, the form with dots; three parts, `=`, a short `nonce`, a zero `eph` |
| [`m1-round.tsv`](m1-round.tsv), 1 row | `key_hex` (the public Ed25519 of the member), `seed_hex`, `plain` → `ok` |

## Candidates

- `keys_sealed` of the holder's transfer (`x25519:v1` to the `seal` of the target with AAD `take|<to>`, [P/08.8](../../../08-domain/spec/08.8-domain.norms.md) N1.7 step 5) —
  there are no vectors, it is checked by the stand of chapter 8.8; a package candidate.
- The sealing of `m1` by the holder with the answer `carry` (the content of `sealed`) — there are no vectors: the round and the stand of chapter 8.3.

The vectors are checked by reference X25519 (RFC 7748), HKDF-SHA256 (RFC 5869) and AES-256-GCM by the text of the contract, not by the code
of implementations; on a discrepancy the contract is right, «Specification» corrects the vector.

Public additional phase/race and existing-norm probe inputs are declared in [production obligation sequences](../production-obligations/README.md). They require Runner binding and do not change this package's existing command forms or historical rows; missing execution is NOTEXEC.
