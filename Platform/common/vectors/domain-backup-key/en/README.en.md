# Vectors: the domain backup copy key

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the domain backup copy key contract](../../../contracts/domain-backup-key.md) (stage C guesses I02-BACKUP-HMAC,
DBK-G01/G02, the Architect's decision 2026-10-23). The participants are the installer (P/02.4 Н3 «domain installation» step 8) and the process `domain`
of the holder (P/08.8 Н1.5). The bytes are written by «Спецификация».

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line not skipped is the header
`case<TAB>root_key<TAB>backup_key_rev<TAB>expect<TAB>note`.

| Field | Meaning |
|---|---|
| `case` | the name of the row |
| `root_key` | the record `root_key` as it came (text): 64 hex characters, the case A–F is admissible at reading |
| `backup_key_rev` | the record `backup_key_rev` as it came (text) |
| `expect` | the key — the hex of 32 bytes in lowercase; `@refuse` — an input outside the domain of the function (`backup_key_rev` not pos53 `[1-9][0-9]*` ≤ 2^53 − 1, `root_key` not 64 hex characters): a refusal of the derivation |
| `note` | the rule |

## Run

A side derives the key by its own code from `root_key` and `backup_key_rev` and compares with `expect`, or a refusal at `@refuse`.
Who performs it — the installer (`02-installer`, the command «domain installation» of P/02.4 Н3: the key at `backup_key_rev` 1, step 4 of the domain founding contract) and the process `domain` of the holder (`08-domain`, P/08.8 Н1.5 `backup_key`: the sealing and the reading of a copy by its `backup_key_rev`) — all rows. They only read the ready one and do not derive the key: the keeper's agent (`09-agent`, P/09.1 Н3 «check the backup copy») and the cluster console (`06-console`, `GET /api/backup` as read, P/06.7) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Native outcome

The package has no separate command contract — the common rule «Vectors» of [the common acceptance README](../../../acceptance/README.md)
(ACC-VECTORS-CONNECT-04, the Architect's decision 2026-10-26): the function answers with code 0 and one JSON value. The key — a JSON string with hex (`"<64 hex>"`), a refusal of the derivation — the JSON string `"@refuse"`.
