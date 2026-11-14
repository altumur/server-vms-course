# Sealing vectors: case data and coverage

This English text is the source; the Russian translation `ru/vectors/sealing/README.cases.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of [the sealing contract](../../contracts/sealing.md): the AAD path, the envelope `enc:v2`, the opening and the ring file. The implementation
of every process that seals or opens (the installer — `w2cctl secrets`, the worker, the console, the domain processes)
passes them by its own function, without a stand. The keys and the nonce are deterministic: a key is 32 bytes `sha256("w2c test <word>")`,
a nonce is the first 12 bytes of `sha256("w2c test <word>")`; in operation a nonce is 12 random bytes, the vectors fix it. The table does not name
the words of derivation: the keys and the nonce are fixed in the tables as bytes (`key_hex`, `nonce_b64url`), an implementation
takes them from there and does not derive them anew (Kimi's addition to the review analysis of stage A 6–7, `SA67-B3`).

| File | Input → expectation |
|---|---|
| [`aad.tsv`](aad.tsv) | the row key and the path segments (a JSON array: a string — a key, a number — an index) → the JSON Pointer and the AAD bytes (hex) |
| [`envelope.tsv`](envelope.tsv) | the key, kid, nonce, the row key, the path, the value → the envelope `enc:v2`; opening the same envelope in the same place — the value |
| [`open.tsv`](open.tsv) | the key, the envelope, the row key, the path → the value or `sealed` (the envelope is not in its place, a foreign key, a path without the leading `/`, the envelope is not by the grammar, non-canonical base64url, a tampered tag); an empty `key_hex` — the ring has no key with the kid of the envelope |
| [`reseal.tsv`](reseal.tsv) | the ring (`k2` current, `k1` former; the keys — the same bytes as in `ring.tsv`), the row key, the row (the elements as text), the json fields → `row`: `changed` \| `same` \| `skip` and by the path of each secret: `{kid, plaintext}` — opening the new envelope with the key `kid` with the same AAD gives this text (the nonce is random, the bytes are not compared), `@same` — the bytes are the same, `@untouched` — the value is byte for byte untouched; 11 rows: k1→k2, already k2, nested in a json field, plain, empty, without secrets, enc:v1, not by the grammar, the kid is not in the ring, the tag does not open, a json field is not JSON ([the contract](../../contracts/sealing.md) «Reseal a value», C06-RESEAL-33-01) |
| [`ring.tsv`](ring.tsv) | the text of the ring file (a JSON string) → `current <kid>; keys <kid>, …` in the order of the file or `unreadable`; at the rows `rotate*` also `; rotate <kid>` — the name that `rotate` will give (`max+1` by the numbers N), or `; rotate refused` |

Invalid UTF-8 of the ring file (the contract: the ring is unreadable) and symbolic links (`link`) cannot be expressed as a JSON string — they
are checked by reading the file. The values in `plaintext`, `expect` (except `sealed`) and `file` are JSON strings (`\n`, `\t`, `﻿` — by JSON escaping).
The vectors are obtained by reference AES-256-GCM by the contract; on a discrepancy the contract is right, «Specification» corrects the vector.

Who performs it (the ring holders — P/06.2 N1.2 `holders`, the installer — P/02.4 N1.9): `aad.tsv`, `open.tsv` and the rows
of `ring.tsv` except `rotate*` — all who open: the installer (`02-installer`), the worker (`03-worker`), the console
(`06-console`), the process `domain` (`08-domain`), the agent (`09-agent`); `envelope.tsv` — the sealers: the installer,
the console, the process `domain` (the book at the holder), the agent (the member key, the book rows); the worker only opens (P/03.5);
`reseal.tsv` — the console (resealing at start) and the installer (`w2cctl secrets seal`); the rows `rotate*` —
the installer (`w2cctl secrets rotate`) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-26).

For reseal, the native labels `@same` and `@untouched` are observations: the adapter compares the actual before/after bytes produced by its regular reseal code. A `{kid, plaintext}` observation opens the actual new envelope with that key and the original AAD. It is not a copy of the expected marker or input plaintext. The expectation columns are judge-side data and never enter the call.

## Vector wire

The wire of `aad.tsv`, `envelope.tsv`, `open.tsv`, `reseal.tsv`, `ring.tsv` is set by the `common/sealing` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.

## Source metadata

This English text is the source; the Russian translation `ru/vectors/sealing/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

Source file `vectors/sealing/README.md`: [README](README.md).
