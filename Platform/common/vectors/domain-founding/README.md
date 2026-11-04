# Vectors: the founding of a domain

This English text is the source; the Russian translation `ru/vectors/domain-founding/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the domain founding contract](../../contracts/domain-founding.md) (the finding of «Спецификация» I02-FOUND, the Architect's decision
of 2026-10-23). The participants are the installer (P/02.4 Н3 «domain installation», the change commands) and the process `domain`
of the holder (the term record 1). The keys are derived from constant bytes (`sha256("w2c test <слово>")`); the bytes are written by «Спецификация».

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first non-skipped one is the header `case<TAB>…<TAB>expect<TAB>note`.

| File | Input → expectation |
|---|---|
| [`recovery.tsv`](recovery.tsv) | `input` — `{file, mode}`: the content of the recovery file JSON and its mode (octal, as a string) → `{domain, root_pub, fingerprint}` of the read file or `@refuse` — the file is not read, nothing changes |
| [`book-seal.tsv`](book-seal.tsv) | `seed_secret` hex of 32 bytes → `book_seal` = X25519(seed, 9) hex |
| [`claim.tsv`](claim.tsv) | `input` — `{issuing_key_secret, domain, holder, url, at}` → the row `domain/holder` `{doc}`, where `doc` is the JCS text of the document of the term record 1 with `issuer`, `kid`, `sig` (Ed25519 is deterministic, RFC 8032) |

Who performs: `recovery.tsv` and `book-seal.tsv` — the installer (`02-installer`, the installation and change commands); `claim.tsv` —
the process `domain` of the holder (`08-domain`): only it writes the term record 1 (ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26).

A side computes by its own code and compares: `recovery.tsv` and `claim.tsv` — JSON by value (`doc` — byte for byte), `book-seal.tsv` — the string.

## Native outcome

The package has no separate command contract — the general rule «Vectors» of [the common acceptance README](../../acceptance/README.md)
(ACC-VECTORS-CONNECT-04, the Architect's decision of 2026-10-26): the function answers with code 0 and one JSON value. `recovery.tsv` — the object `{domain, root_pub, fingerprint}` or the JSON string `"@refuse"`; `book-seal.tsv` — a JSON string with
the hex `book_seal`; `claim.tsv` — the object of the row `domain/holder`.
