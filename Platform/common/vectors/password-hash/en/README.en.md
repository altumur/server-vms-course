# Vectors: the password hash

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is chapter P/08.4 through [the password hash contract](../../../contracts/password-hash.md) (the guess of stage C GP-G06, the Architect's decision
of 2026-10-23). The participants are the process `domain` (writes and checks) and the cluster console (the break-glass entry). The bytes are written by
«Спецификация»; the expectations were computed by two independent implementations of PBKDF2-HMAC-SHA256.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line without `#` is the header. Four fields: `case`;
`input` — a JSON object: `{password, salt}` (a hash: the salt is 32 lowercase hex) or `{hash, password}` (a check); `expect` — a JSON
value: the hash string or `true`/`false`; `note`.

13 cases: 3 hashes, 10 checks (2 `true`, 8 `false`, of them 6 — a string not of the form; the count was corrected by the generator's finding PH-G01).

## Stand command `password-hash`

The key `stand` of the profiles `08-domain` and `06-console` (the section «Layout by processes» of [the common acceptance
README](../../../acceptance/README.md)), by the general rule of the vector commands: a template with `{input}` — the path of a file into which the runner
writes the cell `input` byte for byte; stdout — a JSON value and LF (the hash string or `true`/`false`), compared with `expect` by
value; code 0 — computed, 2 — an input not of the form (not one of the two objects, the salt not 32 lowercase hex; the input is strict JSON in UTF-8 without
BOM: a repeated key, an extra field, a field not a string, a lone surrogate — also not of the form), stdout empty; a hash string not of the form
at a check — `false`, code 0 (the guess of stage C PH-G02, ADR-0087 addendum (12) item 7).

## Who performs

Who performs is by the form of `input`: `{password, salt}` (the rows `hash-*`) — the process `domain` (`08-domain`, writes the hash of people and of the break-glass account, P/08.4 Н1.1, Н1.6); `{hash, password}` (the rows `verify-*`) — the process `domain` (the login of people, P/08.4 Н1.2) and the console (`06-console`, the break-glass entry, P/06.7 Н1.10, the gate-and-pass contract «Аварийный вход»). The console does not write the hash; the agent (`09-agent`, `carry`) and the installer (`02-installer`, `secrets seal`) carry the string and seal it ready-made (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).
