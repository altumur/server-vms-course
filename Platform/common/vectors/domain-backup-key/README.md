# Vectors: the domain backup copy key

This English text is the source; the Russian translation `ru/vectors/domain-backup-key/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the domain backup copy key contract](../../contracts/domain-backup-key.md) (stage C guesses I02-BACKUP-HMAC,
DBK-G01/G02, the Architect's decision 2026-10-23). The participants are the installer (P/02.4 N3 «domain installation» step 8) and the process `domain`
of the holder (P/08.8 N1.5). The bytes are written by «Спецификация».

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
Who performs it — the installer (`02-installer`, the command «domain installation» of P/02.4 N3: the key at `backup_key_rev` 1, step 4 of the domain founding contract) and the process `domain` of the holder (`08-domain`, P/08.8 N1.5 `backup_key`: the sealing and the reading of a copy by its `backup_key_rev`) — all rows. They only read the ready one and do not derive the key: the keeper's agent (`09-agent`, P/09.1 N3 «check the backup copy») and the cluster console (`06-console`, `GET /api/backup` as read, P/06.7) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Vector wire

The wire of `cases.tsv` is set by the `common/domain-backup-key` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
