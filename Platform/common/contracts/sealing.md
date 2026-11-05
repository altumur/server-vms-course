# The sealing contract: the ring, the envelope `enc:v2`, AAD

This English text is the source; the Russian translation `ru/contracts/sealing.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5): a contract that several processes read lies in
`Platform/common/`; the Architect's decision on the review of stage B 1–2, item 4). The owner is lesson [P/06](../../06-console/spec/06.2-console.norms.md),
chapter 6.2 Н1.2 «The envelope and the key ring» (moved from М10/7 Н1.2; ADR-0083 addendum (29) item 9: the line names the owner lesson of the norm; the library by the contract is written by the session `common` of the generation). Readers: the installer — the commands `w2cctl secrets`
([P/02.4 Н1.9](../../02-installer/spec/02.4-installer.norms.md)), the worker — opening (chapter P/03.5), the console —
sealing and resealing ([chapter P/06.2](../../06-console/spec/06.2-console.norms.md)),
the domain processes (М11). Moved from М10/7 Н1.2 without a change of behaviour: what to seal, who holds the key, rotation, the mode
without a key and the idempotency fingerprint stay in the norms of the reading lessons.

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Envelope

```yaml
envelope:  enc:v2:<kid>:<nonce>:<ct>
  kid:     a non-empty string without `:`, without blanks and without U+FEFF, does not begin with `#`; blanks are exactly U+0020, U+0009,
           U+000D, U+000A (not `\s` of a library; NBSP U+00A0 and the other Unicode spaces are ordinary characters of kid); new → k1;
           rotate → k<max+1> (analysis of the review of stage A 6–7, B7); U+FEFF is nowhere in a kid — the kid of the first entry is not to be confused with
           a BOM at re-reading (guess of stage C S-006, the Architect's decision of 2026-10-23)
  nonce:   12 random bytes, base64url without =
  ct:      AES-256-GCM(key, nonce, plaintext, aad) with the tag (16 bytes), base64url without =
  b64:     nonce and ct — only the canonical notation of base64url (RFC 4648 § 5, without =): the residual bits of the last character are zeros;
           another notation is Sealed before the cryptographic operation, although a non-strict decoder would give the same bytes (the vector
           open.tsv noncanonical_ct; guess of stage C S-001, the Architect's decision of 2026-10-23)
  aad:     UTF-8(<row key>) + the byte 0x00 + UTF-8(<the full JSON Pointer to the secret from the root of the row>)
  plain:   the UTF-8 bytes of the value as given, without normalization; an empty one and an already sealed one are not sealed
  looks:   everything that begins with enc: is taken for an envelope (at the input — a refusal)
  seal:    the observable behaviour of sealing: an empty value stays empty, there is no envelope; a value that begins
           with enc: — a refusal; a wrong context (a row key with NUL, a path that is not a JSON Pointer with a leading /) — a refusal before
           the cryptographic operation; the form of errors and of library calls — «Implementation decides» (guess of stage C S-002,
           the Architect's decision of 2026-10-23)
  strict:  at opening, an envelope not by the grammar — not enc:v2, not five parts separated by `:`, a kid not by the grammar, a nonce not
           12 bytes or a ct not base64url without `=` (with `=` included), a ct shorter than the tag — Sealed without the cryptographic
           operation; there is no default that weakens the cut-off (the Architect's decision, analysis of the review of stage A 6–7, B6)
```

## AAD path

The AAD path is unambiguous: every key/index is a separate JSON Pointer segment, `~` is replaced by `~0`, `/` by `~1`, the segments are separated by `/` with a leading `/`; an array index is decimal without leading zeros. An example of a top-level field: `/password_secret`; of a nested one: `/settings/a~1b/0/password_secret`. The whole path is used, not only the name of the last key; no normalization or joining through `#`. In the sealing profile the row key contains no NUL: with NUL, seal/open are rejected before the cryptographic operation. This is an additional condition of the contract, not a general ban of P/01.1. Therefore the first 0x00 unambiguously separates it from the path, even if a JSON key inside the path contains NUL.

This corrects the AAD bytes of the former profile; the form of the envelope `enc:v2` is kept. Trying former ways of AAD at opening is forbidden: an envelope that does not open with this single context gives Sealed. The migration of rows already sealed the old way is outside the contract; introducing it requires a coordinated transition of the ring holders and a repeated sealing from a trusted source.

## Ring file

```yaml
ring_file:                                   # SECRETS_KEY=<path>; the default is the installer layout: the unit is given
                                             # <PLATFORM_DIR>/etc/secrets/platform.key (P/02.4 Н1.1); not set for a process —
                                             # development mode (no_key below; analysis of the review of stage A 6–7, № 19)
  line:    <kid> <64 hex>                    # 32 bytes of key; the first key entry is the current one; empty lines and separate comment lines are skipped;
                                             # a BOM U+FEFF at the start of the file is skipped and does not enter the kid (reconciliation of python and go М10/6–11, agreed)
  mode:    0640 root:w2c-secrets; the directory is not accessible to others; the file is NOT inside a directory of the store, of the objects or of their copies
           (the list — the secret files contract forbidden layout: copies — only the given ones; STAND-FORBIDDEN-DIRS-01, the Architect's decision of 2026-10-27)
  link:    the placement — [the secret files placement contract](secret-files.md): the file itself is a regular one, not a symbolic link;
           links in the directories of the path are resolved before the check of mode «NOT inside»; an unresolvable directory is a refusal (guess of stage C
           S-005, the Architect's decision of 2026-10-23)
```

Three states of the ring at a holder (from P/06.2 Н1.2 `no_key` without change; layout audit, the Architect's decision of 2026-10-25, B-22); what the door
of the holder does with each is the norm of its lesson (the console — P/06.2 Н1.2, Н4; the common row check — [the row check contract](row-check.md) «Ring boundary»;
the worker — P/03.5 Н1.2 `open_without`):

```yaml
no_key:
  unset:       SECRETS_KEY is not set → development mode with a loud log line (not an envelope, the values are open — by the norm of the lesson);
               SECRETS_KEY="" (set empty) is not development mode but unreadable below (reconciliation of python and go М10/6–11, S11)
  unreadable:  set but not readable (an empty or a wrong file included — «Ring file» below) — this is not the mode without a key;
               what refuses is at the lesson (the console: all POST/PUT of units — 503 unavailable, P/06.2 Н1.2)
  open:        set and readable — the envelope enc:v2 by this contract
```

The file is strictly UTF-8: an invalid UTF-8 sequence makes the ring unreadable; one leading BOM U+FEFF is allowed —
it is skipped (guess of stage C S-003, the Architect's decision of 2026-10-23); a U+FEFF in the kid of an entry — the kid is not by the grammar,
the ring is wrong (S-006).
The blank characters of the file are exactly the space U+0020 and the tab U+0009; lines are separated by LF, a CR before LF is part of the end
of the line (CRLF is allowed); NBSP U+00A0 and the other Unicode spaces are ordinary characters of kid; hex digits are `0-9`, `a-f`, `A-F`
(analysis of the review of stage A 6–7, B7). A line whose first non-blank character is `#` is a comment as a whole. A kid does not begin
with `#`; a `#` inside a kid is allowed. An entry contains exactly two fields separated by a space
or a tab; the second is exactly 64 hex digits. Inline comments after a key entry
are not allowed. Spaces/tabs at the edges of a line are ignored.
The ring contains at least one key, all `kid` are distinct; an empty or wrong file is considered
unreadable, not unset. `new` and `rotate` create the names `kN`, where N is a positive
decimal integer without leading zeros. For `rotate` only a ring with such names is allowed:
another name is a refusal of the command without a change of the file. Reading an envelope and `seal` keep the common
grammar of `kid` above. `max+1` is computed by the numbers N, without machine overflow; if
the implementation cannot represent the result, the command refuses before changing the file.

## Reseal a value

Moved from [P/06.2](../../06-console/spec/06.2-console.norms.md) Н3 «reseal at start» (what is done with one value)
without new behaviour; which rows are walked, `cas` by the read version, races and the order of the ring holders — there and in
[P/02.5](../../02-installer/spec/02.5-installer.norms.md) Н1.3, by reference (guess of stage C C06-RESEAL-33-01, the Architect's decision of 2026-10-25). The walk at
the console (its own rows at start, P/06.2 Н3) and at the installer (`w2cctl secrets seal` by prefixes, [P/02.4](../../02-installer/spec/02.4-installer.norms.md) Н1.9) differs —
there is no common rule of the walk, it stays with each; what is common is what is done with one value, below (layout audit B-22).

```yaml
walk:      the fields of a row whose name is *_secret by the sealing rule: at the top level and nested in the text of a json field value
           (at any depth); the AAD path is the full JSON Pointer from the root of the row (the section «AAD path»)
current:   an envelope enc:v2 under the current kid of the ring — the bytes are the same
old:       an envelope enc:v2 under another kid of the ring — open with the key of this kid with the full AAD, seal with the current one with the same AAD
plain:     a value in the clear — seal with the current one; an empty one — without change (seal)
none:      a field without envelopes and open values — without change; a row where nothing changed is not written
untouched: enc:v1 (a dead format, ADR-0003; at the reader «?»), enc:v2 not by the grammar (strict), a kid that is not in the ring,
           and an envelope under a former kid that does not open (the tag) — do not touch the value, byte for byte, a log line with the row
           key and the field path (without the value); reseal the other fields of the row, do not skip the row, do not interrupt the start
           (the Architect's decision of 2026-10-25)
unreadable: the value of a json field is not JSON or the row is out of form — skip the row: a log line with the key and the cause, the row does not
           change (P/06.2 Н3, reconciliation S8)
```

## Vectors

The package [`sealing`](../vectors/sealing/README.md): the envelope `enc:v2`, AAD, the ring file, resealing a value (`reseal.tsv`,
C06-RESEAL-33-01). (ADR-0083 addendum (32) item 2)

## Correspondence to former lessons

From М10/7 Н1.2 (stage B, review of stage B 1–2 item 4): the blocks `envelope` and `ring_file` (`line`, `mode`), the paragraphs about the AAD path
and about the grammar of the ring file. Parts of the norms М10/7-03 (the envelope and AAD; chapter P/03.5) and М10/7-04 (the form of the ring file — here; the ring, `rotate` and
resealing — chapter P/06.2) — by `note` of [id-map](../id-map.tsv) (analysis of the review of stage B 6–7, № 23).
