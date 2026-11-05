# The domain backup key contract: derivation from the root

This English text is the source; the Russian translation `ru/contracts/domain-backup-key.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes is a contract, not copies
in chapters; the stage C guess I02-BACKUP-HMAC, the Architect's decision of 2026-10-23). The owner is lesson P/08, chapter
[8.8](../../08-domain/spec/08.8-domain.norms.md) N1.5 (the backup copy of the holder: the secret envelopes, `kid`, reading).
Participants: the installer — the command «domain installation» ([P/02.4](../../02-installer/spec/02.4-installer.norms.md) N3 step 8)
derives the key with `backup_key_rev` 1 and writes it into `domain/signer`; the process `domain` of the holder — seals the backup
copy and derives the key on reading a copy by its `backup_key_rev`. Moved from P/08.8 N1.5 (the line `backup_key`) without
a change of behaviour.

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

```yaml
backup_key:      HMAC-SHA256(key: root_key of the recovery file — 32 bytes written as hex (the domain founding contract),
                 data: the ASCII bytes "w2c domain backup secrets", the byte 0x00, the ASCII bytes of the decimal notation of backup_key_rev)
                 — 32 bytes
backup_key_rev:  the domain of the function is pos53: a decimal notation [1-9][0-9]* not greater than 2^53 − 1; at installation 1; outside the domain —
                 a derivation refusal, not only by the form of the document (the stage C guess DBK-G01, the Architect's decision of 2026-10-23)
root_key:        the input of the function is exactly 64 ASCII hex characters, without the prefix 0x and spaces; the case A–F is admissible on reading,
                 the writer writes lowercase (DBK-G02); anything else — a derivation refusal
```

Where the key is kept at the holder (`domain/signer.backup_key_secret`), the envelope `enc:v2` with this key, the `kid` `b<backup_key_rev>` and
the reading of a copy are P/08.8 N1.5.

## Form

The installer writes the key into `domain/signer.backup_key_secret`: `Platform/08-domain/data/signer.schema.json`, `Platform/08-domain/data/signer.outcomes.tsv` (layout audit, V-09; the Architect's decision of 2026-10-25).

## Vectors

The package [`domain-backup-key`](../vectors/domain-backup-key/README.md): the derivation of the backup key (`root_key`, `backup_key_rev`) → the key; outside the domain — a refusal. (ADR-0083 addendum (32) item 2)
