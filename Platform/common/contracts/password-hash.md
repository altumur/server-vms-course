# The password hash contract: `pbkdf2-sha256`

This English text is the source; the Russian translation `ru/contracts/password-hash.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes is a contract, not copies
in chapters; the stage C guess GP-G06, the Architect's decision of 2026-10-23). The owner is chapter
[P/08.4](../../08-domain/spec/08.4-domain.norms.md) (N1.1 `pwhash_secret` of a person row, N1.6 — of the break-glass account).
Participants: the process `domain` — writes the hash (people, the break-glass account) and checks the login of people (P/08.4 N1.2); the cluster console —
checks the password of the break-glass login ([the gate-and-pass contract](gate-and-pass.md) «Break-glass entry»). Moved from P/08.4
N1.1 without a change of behaviour.

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

`PBKDF2_ITERATIONS` has exactly one binding: its uniquely named row in the [P/08 form](../../08-domain/forms/runtime-constants.tsv). In `form`, the metavariable `<PBKDF2_ITERATIONS>` expands only to that row value as unpadded ASCII decimal digits; the `hash` operand uses the same value. Neither brackets nor the identifier are emitted on the wire; no other iteration count, alias, setting or additional accepted format is introduced.

```yaml
form:     pbkdf2-sha256$<PBKDF2_ITERATIONS>$<salt: 32 lowercase hex>$<key: 64 lowercase hex>
hash:     key = PBKDF2-HMAC-SHA256(the password — UTF-8 bytes, the salt — 16 random bytes, PBKDF2_ITERATIONS iterations, length 32 bytes);
          the writer writes hex in lowercase
verify:   a string by form — compute the key from the password and the salt of the string and compare it with the key of the string in constant time: equal —
          the password fits; a string not by form (another algorithm or number of iterations, uppercase hex, another length, an extra part,
          an empty string) — the password does not fit, not an error
secret:   in a store row the field *_secret is sealed by the holder's ring (the sealing contract); the hash is of the open value
```

## Form

`pwhash_secret` is a field of the person rows and of the break-glass account: `Platform/08-domain/data/users.schema.json`, `Platform/08-domain/data/users.outcomes.tsv`; `Platform/08-domain/data/break-glass.schema.json`, `Platform/08-domain/data/break-glass.outcomes.tsv` (layout audit, V-41; the Architect's decision of 2026-10-25).

## Vectors

The package [`password-hash`](../vectors/password-hash/README.md): the hash and the check of a password. (ADR-0083 addendum (32) item 2)
