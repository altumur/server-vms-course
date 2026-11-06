# The ask signature contract: the headers `X-W2C-Member`, `X-W2C-Time`, `X-W2C-Signature`, the function `ask-sig`, refusal words

This English text is the source; the Russian translation `ru/contracts/ask-sig.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13): a common algorithm of several processes is a contract,
not copies in chapters; analysis of the review of stage A 8–10, № 13 / decision 2). The owner is lesson P/08, chapter [8.8](../../08-domain/spec/08.8-domain.norms.md) (moved from
M11/10 N3 «ask-sig»): the signature of asks without a member on the path.

| Ask | Signs | Checks |
|---|---|---|
| `backup` — `GET /api/backup` (P/06.7 N1.13) | the process `domain` of the target cluster on an emergency move, with the member key `domain/member-key` (P/08.8 N1.8 `order` step 5) | the console of the cluster that keeps the backup copy ([P/06.7](../../06-console/spec/06.7-console.norms.md) N1.13) |
| `prepare` — `POST /api/prepare` (P/08.8 N1.7 step 4) | the process `domain` of the holder with the token key `current` of the set (8.8) | the process `domain` of the target (8.8); the target console passes the ask on without a check (P/06.7 N1.8) |
| `move` — `POST /domain/move` (P/08.8 N1.8 by_file) | the command `w2cctl domain move` with the root of the recovery file, when there is no token | the console of the target cluster (P/06.7 N1.8) and the process `domain` (8.8) |

Moved from M11/10 N3 «ask-sig — the ask signature» (the block `message`, `time`, `signature`, `check`) and N4 (the words of `ask-sig`)
without a change of behaviour. What a door answers to a refusal (401 at `/api/backup` with `detail` — the word; 400 and 403 at `/api/prepare`),
who the member is and whose key — are the norms of the doors (P/08.8 N1.7, N2; P/06.7 N1.13). The agent signature `X-Agent-Signature` is another contract
([the agent signature contract](agent-signature.md)). References in the moved text are of lesson M11/10 (N1.7, N1.8 — the same numbers of chapter P/08.8; N1.9 — P/06.7 N1.13).

Normative keywords follow [the course canon](../../../NORMATIVE-TERMS.md).

## Form

`pub` is the member key `domain/member-key` (backup), the key `current` of the set `domain/keys` (prepare) or `root_pub` of the row `domain/root` (move): `Platform/09-agent/data/member-key.schema.json`, `Platform/09-agent/data/member-key.outcomes.tsv`; `Platform/08-domain/data/keys.schema.json`, `Platform/08-domain/data/keys.outcomes.tsv`. The doors where `X-W2C-*` is checked are `Platform/06-console/spec/06-console.api.openapi.yaml` (`/api/backup`, `/domain/move`) and `Platform/08-domain/spec/08-domain.api.openapi.yaml` (`/api/prepare`) (layout audit, V-07, V-08; the Architect's decision of 2026-10-25).

## Signature and check

From M11/10 N3 «ask-sig — the ask signature»:

```
message:  backup|<cluster>|<member>|<time>   (the backup ask; the member key)
          prepare|<target>|<time>            (preparation of a handover; the token key current of the set)
          move|<cluster>|<time>|<sha256 of the body>   (a move by the recovery file; root_key; <sha256 of the body> — 64 lowercase hex; P/08.8 N1.8 by_file; C08-MOVE-BY-FILE-01)
time:     X-W2C-Time — the decimal notation of wall seconds with three digits after the dot: (0|[1-9][0-9]*)\.[0-9]{3}
signature: X-W2C-Signature — base64url without «=» of an Ed25519 signature over UTF-8(message)
check:    in order: the header is absent or empty — missing (prepare and move — X-W2C-Time, X-W2C-Signature; backup — also
          X-W2C-Member; empty — added by the reconciliation of M11, H13);
          the time is out of form — bad_time; |now − time| > 300 — skew; the signature is not base64url without «=», not 64 bytes or does not
          verify — bad_signature; otherwise ok
```

`<member>` of the ask `backup` is the value of `X-W2C-Member`; `<cluster>` is the cluster at whose console the copy is asked for; `<target>`
of the ask `prepare` is the member to which the domain is handed over (P/08.8 N1.7 `to`); `<time>` is the value of `X-W2C-Time` as it came.
The form of the function is the input of the command `ask-sig` of [P/08.8](../../08-domain/spec/08.8-domain.norms.md) N5:
`{ask: backup | prepare | move, cluster, pub, header: {member?, time?, signature?}, now, body_sha256?}` → `{result: ok}` |
`{result: refused, reason}`. The fields of the input (the reading of M11/10 N5 and of the acceptance README of M11/10 «Inputs»; analysis of the review of stage B
8–10, № 4, Claude S-7):

```yaml
cluster:   <cluster> of the messages backup and move and <target> of the message prepare — the cluster of the checker: the console at which the copy is asked for,
           or the target of the handover; a signature over another name — bad_signature (the package row ask-sig-08)
pub:       the public key of the signer that the checker trusts: the member key (backup), the token key current of the set (prepare) or root_pub of its own domain/root (move)
body_sha256: only at move, and required: <sha256 of the body> of the message, 64 lowercase hex, computed by the checker
header:    the headers X-W2C-Member, X-W2C-Time, X-W2C-Signature without the prefix (member, time, signature) as they came;
           <member> of the message backup — header.member
member:    there is no field member at the top level of the input: the member of the message is only header.member; an input with the field member is
           an extra field, the input is out of form, code 2 (P/08.8 N5 exit; the Architect's decision of 2026-10-20 on the open questions of the analysis of the review of stage B 8–10, question 2; formerly the field was admitted and not read)
now:       the wall seconds of the checker
exit:      0 — computed; 2 — the input is out of form; the exit codes follow the principle of the vocabulary of the «Domain stand» («Exit codes of vector commands»: 2 — the form
           of a trusted input, 0 with a word — a document of another cluster; the Architect's decision on the reconciliation of M11, H14) (a copy of P/08.8 N5 exit; layout audit, the Architect's decision of 2026-10-25, B-14):
           at ask-sig pub is not hex of 32 bytes, cluster is not a cluster name, ask is not backup | prepare | move, body_sha256 is out of form, it is absent at move or present at another ask, now is not a number or absent, there is no header,
           header is not an object, header.time is not a string, an extra field in header or in the input — 2
```

## Refusal words

From M11/10 N4: the words of `ask-sig`: `missing`, `bad_time`, `skew`, `bad_signature`.

## Vectors

The package [`ask-sig`](../vectors/ask-sig/README.md) (analysis of the review of stage A 8–10, № 13): 27 rows — 12 inputs of the command `ask-sig`
of the acceptance of M11/10 (sc. 07) without a change of bytes; one of them is an input out of form (`@exit 2`; analysis of the review of stage B 8–10, № 22); row 13 — the field `member` at the top level, `@exit 2` (question 2 of the same analysis). The scenario and the inputs were removed
by the move of lesson 8 — the table is the only source of these cases. Rows 14–26 — `move`, row 27 — `backup` with an extra `body_sha256`.

## Correspondence to former lessons

From M11/10 (analysis of the review of stage A 8–10, № 13 / decision 2): N3 «ask-sig» whole (here «Signature and check»; in M11/10 —
a pointer) and the phrase of N4 on the words of `ask-sig` (here «Refusal words»). The norm M11/10-10 (`ask-sig` and `GET /api/backup`; the door —
6.7) — by `note` of [id-map](../id-map.tsv).
