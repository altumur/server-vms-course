# The domain founding contract: the root, the recovery file, pinning, installation, term record 1

This English text is the source; the Russian translation `ru/contracts/domain-founding.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes is a contract, not copies
in chapters; the Architect's decision of 2026-10-23 on the finding of the Specification I02-FOUND). The owner is lesson P/08: chapter [8.2](../../08-domain/spec/08.2-domain.norms.md) (the root, the forms, the keys of the holder
and of book acceptance) and chapter [8.8](../../08-domain/spec/08.8-domain.norms.md) (the term record). Participants: the installer — the command
«domain installation» ([P/02.4](../../02-installer/spec/02.4-installer.norms.md) N3) and the change commands that read the recovery
file; the holder's process `domain` — term record 1; the member's agent — pinning at `join`
([P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.1). Moved from P/08.2 N1 («Common to all forms of the chapter», «Completeness
of forms»), P/08.2 N1.1 (`recovery_file`, `pin`) and P/02.4 N3 «domain installation» without a change of behaviour; one thing is clarified —
where the installation puts the backup key (step 4, the row `domain/signer`: only the installation creates it).

The forms of the rows that this contract names are in the families of lesson P/08 and in the common contracts, not here (the files — by name, DF-READ-73):
`domain/root` — the family `root` (`Platform/08-domain/data/root.schema.json`, `Platform/08-domain/data/root.outcomes.tsv`);
`domain/signer` — `signer` (`Platform/08-domain/data/signer.schema.json`, `Platform/08-domain/data/signer.outcomes.tsv`);
`domain/book-seal` — `book-seal` (`Platform/08-domain/data/book-seal.schema.json`,
`Platform/08-domain/data/book-seal.outcomes.tsv`); `domain/keys` — the family `keys` (`Platform/08-domain/data/keys.schema.json`,
`Platform/08-domain/data/keys.outcomes.tsv`) and [the domain key set contract](keys.md); `domain/holder` — the family `holder`
(`Platform/08-domain/data/holder.schema.json`, `Platform/08-domain/data/holder.outcomes.tsv`) and [the term
record contract](record.md).

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Common rules of forms

Common to all forms of the chapter (and of the chapters of the lesson and the domain contracts that refer to it): hex is lowercase `0-9a-f`; base64url
is the alphabet of RFC 4648 §5 without `=`, the notation is canonical: length ≢ 1 (mod 4), the extra bits of the last character are zeros, re-encoding
the bytes gives the same text; otherwise it is not base64url; JCS is RFC 8785 (ADR-0072); «wall-clock seconds» are Unix seconds
by the clock of the process that checks or signs. Signing keys are Ed25519 (RFC 8032), a public key is 32 bytes;
the book acceptance key is X25519 (RFC 7748), 32 bytes.

Completeness of forms. Every JSON form of the chapter is closed: a field outside the list — the form is not that one (what follows from this is said at the form);
a mandatory field is marked without `?`, an optional one with `?`, the absence of an optional one is its default. The order of the keys
of an object means nothing; the order of arrays is at the form, otherwise (P/08.0 N0 «Order of output arrays», a copy; layout audit, the Architect's decision of
2026-10-25, B-28): an array of names — of members, clusters, keys, `kid`, `ref`, fingerprints, words — in ascending order of UTF-8 bytes,
unless the form explicitly names another key; an array of objects — by the key that is named at the form; the order of selection is not the order
of output. A repeated key in a JSON object — the form is not that one. A number is
a JSON number (not a string, not `true`/`false`); «whole» is a number without a fractional part by value (`2` and `2.0` are one integer; the output
writes it without a fraction) within ±(2^53−1); «finite» is not NaN and not infinity. Strings are UTF-8 without normalization.

## Root and recovery file

The root is the Ed25519 pair of the domain, one for the whole life of the domain; what it signs, what makes its theft dangerous and who does not keep it — P/08.2
N1.1 (`signs`, `limit`, `needed_for`, `not_on`); the fingerprint — P/08.2 N1.1 `fingerprint` (a copy — the domain key set contract).

```yaml
recovery_file: JSON {domain, root_key, root_pub}       # the private half of the root — only here; all three are mandatory;
                                                      # an extra field or another type — the file is not read
  domain:      the domain name, 1–64 characters [a-z0-9-]
  root_key:    hex of 32 bytes — the seed of the Ed25519 private key (RFC 8032 §5.1.5)
  root_pub:    hex of 32 bytes — the public key; not the one derived from root_key — the file is not read (a refusal, nothing changes)
  place:       at the operator, outside the platform directory as a whole (PLATFORM_DIR — the ring is in it too, the sealing contract) and outside the directories of the store,
               the objects and their copies; mode 0600; the path is named by the call of the operation (outside PLATFORM_DIR — added by the reconciliation of M11, I2);
               a regular file, not a symbolic link, links in the directories of the path are resolved before the check «outside …», an unresolvable
               directory is a refusal: [the secret files placement contract](secret-files.md) (guess of stage C DF-G01)
  mode:        the mode is checked at every reading of the file (the changes of N3, the move of chapter 8.8, any command that takes from the file
               root_pub): wider than 0600 — a refusal, nothing changes (added by the reconciliation of M11, I3)
```

## Root pinning

```yaml
pin:           domain/root {pub, domain}       # at every member, the holder included; create-once
  pub:         mandatory; hex of the public root
  domain:      mandatory; the domain name
  not_a_pin:   a row out of form (an extra element, a missing field, not hex) — there is no pinning: keys → no_pin; the pinning is not repaired
               by itself, the member is admitted anew (chapter 8.3)
  when:        the holder — at installation (P/02.4 N3); a member — at the admission by the operator by the fingerprint (chapter 8.3; join — chapter 9.1); otherwise it is not written
  never:       the root is not pinned by the first set that arrives; a pinned one is not replaced — to change the root = to found
               the domain anew (a new installation and admission of every member)
```

## Domain installation

An operator command, once per domain (the owner of the command is P/02.4 N3 «domain installation»; the name and arguments — P/02.4 «Implementation
decides» item 8).

```
1. the store of the holder cluster answers, the ring ([the sealing contract](sealing.md) «Ring file») is read; otherwise a refusal, nothing is written
2. domain/keys or domain/root already exists                          → a refusal, nothing changes (domain/root —
   added by the reconciliation of M11, I1: an installation over someone else's pinned root would get stuck)
3. a new root; the recovery file is created first, only if the path does not exist, mode 0600,
   outside PLATFORM_DIR and the store directories (place — «Root and recovery file») → otherwise a refusal, nothing is written to the store
4. the holder keys (the token key, the issuing key) and the backup key at backup_key_rev 1 ([the domain backup key
   contract](domain-backup-key.md)) → domain/signer, the secrets — as ring envelopes (the form — the family signer)
5. a new seed → domain/book-seal {seed_secret} as a ring envelope
6. the set rev 1 (keys = {kid: the token key}, current, issuing = [serial], revoked_issuing = [], book_seal) signed
   by the root → domain/keys create-once
7. domain/root {pub, domain} create-once (the holder is a member too)
8. term record 1 — «Term record 1» below (it is signed by the issuing key, not the root; written by the holder's process domain)
```

The interface of step 8 before chapter 8.8: an installation without chapter 8.8 executes steps 1–7 and ends there successfully; the term record
(`domain/holder`) is read by no one without chapter 8.8: the holder in the list of members — [P/08.3](../../08-domain/spec/08.3-domain.norms.md)
N3 «the holder in the list», the holder's answer without `holder` — P/08.3 N1.5. Chapter [8.8](../../08-domain/spec/08.8-domain.norms.md)
adds step 8: term record 1 is written by the holder's process `domain` after the installation («Term record 1»).

**The operator window.** A premise: there is one operator window per domain — the domain installation and the change commands that read the recovery
file are executed by one operator sequentially. A second such command started while the first is running on the same
installation — code 2 with the word `busy` before any changes (the way of local exclusion — a lock, a marker file — is the choice of the
implementation); the platform does not claim a distributed lock between servers and installations (guess of stage C I02-DOMAIN-WINDOW, the Architect's decision of 2026-10-23).

An installation interrupted before step 6 is repeated after the operator removes the recovery file: the members do not trust anything
yet, the rows of steps 4–5 are overwritten. The process `domain` does not found the domain — [P/08.2](../../08-domain/spec/08.2-domain.norms.md)
N3 «the process `domain` does not found the domain»; the cold start — P/08.2 N3 «cold start».

## Term record 1

```yaml
claim_1:     the holder's process domain at the first start after the installation — when the absence of domain/holder and domain/member-rows/<part>
             of its own store is confirmed; one of them is unreadable or the store did not answer — claim_1 is not written; its own
             term record 1 already lying there is not rewritten (C08-CLAIM-1-01, P/08.8 N1.1) — writes domain/holder {doc} (P/08.8 N1.1 claim;
             the writer of the row is only domain, the installer does not write it): doc {domain, term: 1, holder, url, ca?, at, issuer,
             kid, sig} by the term record contract — domain from domain/root, holder — the name of the holder member, url — SIGNER_URL
             (without it http://localhost:8445), ca — the fingerprints of the holder's CA (P/08.3 N1.6), at — the wall seconds of the signature,
             no restored_from; issuer, kid, sig — the issuing key from domain/signer (issuing_key_secret); one equal to the lying one is not
             written; then the holder enters itself into the list of members (P/08.3 N3 «the holder in the list»)
```

## Vectors

The package [`domain-founding`](../vectors/domain-founding/README.md): founding the domain — the root, the recovery file, pinning. (ADR-0083 addendum (32) item 2)

The table `recovery.tsv`: the cell `input` is `{file, mode}` — the content of the recovery file JSON and its mode (octal, as a string); the native outcome is `{domain, root_pub, fingerprint}` of the read file or `@refuse` — the file is not read, nothing changes. The table `claim.tsv` (outside the wire form of the package): the cell `input` is `{issuing_key_secret, domain, holder, url, at}`; the native outcome is the object of the row `domain/holder` `{doc}`, where `doc` is the JCS text of the document of the term record 1 with `issuer`, `kid`, `sig` (Ed25519 is deterministic, RFC 8032).

The canonical JSON (RFC 8785, ADR-0072) on which the contract rests is the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → RFC 8785 form → sha256; ADR-0083 addendum (33) item 2).
