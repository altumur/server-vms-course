# The log mask contract: free log text with the mask

This English text is the source; the Russian translation `ru/contracts/log-mask.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): all processes of the platform write the mask into the log — the console,
the worker, the resource, the domain processes; a contract, not copies in chapters; the stage C guess C06-LOG-MASK-33-01, the
Architect's decision of 2026-10-25). The owner is chapter [P/06.2](../../06-console/spec/06.2-console.norms.md) of the console (N1.4 `never`
`log`). The participants are all processes of the platform that write a log (id-map: M10/7-08 → P/06.2-05, «all processes»). The parsing
of an address, of pairs and the field rule are [the address contract](url-credentials.md) (A1–A15); here is the function masking free text
as a whole.

Moved from P/06.2 N1.4 `log` and the lines of the address contract about free text (A1, A2) without a change of behaviour; P/06.2 and
the address contract refer here.

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Function

```yaml
mask_log:  mask(text, catalogue) → text: the input is free text, not the value of a field (a log line, an error, a JSON document,
           a connect string); the output is the same text where the credentials of headers, the values of pairs with a secret name and
           the passwords in addresses are replaced by the mask "***"; the rest — byte for byte
rule:      the catalogue rule is the union of the rules (credentials, secret_in) of all fields type: url of the manifest catalogue
           of the process with the common vocabulary common_words (the address contract «The field rule and the common vocabulary»): the names that
           a manifest adds are secret names too; at a process without a manifest catalogue (the store daemon, its CLI)
           the catalogue is empty — the rule = common_words and the address contract (userinfo, the headers Authorization and
           Proxy-Authorization); the vectors caller supplies the catalogue as input to the same function for all roles
```

## What is masked

```yaml
header:    the headers Authorization and Proxy-Authorization (the header name — case-insensitive) with the scheme Basic or Bearer
           (the scheme — case-insensitive): the credentials after the scheme → "***" (stage A review, SA1-18, SA1-23); another scheme
           (Digest) stays as it is; the credentials run to the first white-space character (space below) or the end of the line:
           what sticks to them (a comma, a quote right next to them) is masked together — masking too much is safe, masking too little
           is not (C06-LOG-MASK-33-01, the Architect's answer of 2026-10-25 (1))
pair:      a pair `name=value` with a secret name — by the address contract A1 (the name is letters, digits, `_ . - %` and non-ASCII characters
           before `=`; the value runs to `&`, `;`, `,` or a space), A5 (the secret before the login), A6 (the value of a secret pair
           is masked to the end of the value, an address in it too, `<` does not cut the value), A7 (a pair hidden by escaping
           — the whole value; a name decoded into pairs goes away with the value); an empty value stays empty
json:      a JSON pair `"name": value` with a secret name (spaces around `:` are admissible): the scalar of the value, a string — up to its
           closing unescaped quote, is replaced by "***"; an empty string stays empty; a scalar is one token
           of JSON (a number, true, false, null), the character after it stays: {"password": 1234;} → {"password": "***";} (reconciliation of python
           and go M10/6–11, S18)
address:   an address in the text — by the address contract A1–A15 (a password in userinfo, in a pair, in the head, in a nested address — the mask where
           it stands; the login is shown as written); in free text an address ends at a space, a quote, `\`, `<`
           or `>` (A2)
space:     a «space» at the ends of an address (A2) and of a pair value (A1) in the log mask is any character of the set white_space
           of [the person name contract](../person-name.md) «White space» (White_Space Unicode 15.0.0), as mask_in below and the person
           name (C06-LOG-MASK-33-01, the Architect's answer of 2026-10-25 (2); layout audit A-20)
```

## What stays as it is

Everything that is not the credentials of a Basic/Bearer header, not the value of a pair with a secret name and not the password of an address: the login, an empty
value, a Digest hash, pairs without a secret name, an address without a password — byte for byte.

## Where it applies

Every line of the journal (log) of a process of the platform. The places where there is no secret at all are the block `never` below, moved from
[P/06.2](../../06-console/spec/06.2-console.norms.md) N1.4 without a change (layout audit, the Architect's decision of 2026-10-25, B-30): the journal `audit`, the heartbeat, the snapshot,
argv and the text of a refusal contain no values — this is a rule of the places of writing, not a mask.

```yaml
never:
  reply:     201/200/GET — the mask at any depth; tables — the field is absent
  idem:      the copy of an answer for a repeat — with the mask
  snapshot:  addresses — with the mask; the exclusion of *_secret fields and the load refusal — P/02.1 N1.3a
  domain:    an edit of a member with *_secret at any depth — 400; the load refusal — P/02.1 N1.3a
  journal:   field names, not values
  heartbeat: the envelope, not the value; the status element of a unit tells by the field why "the password does not open: <cause
             open_without P/03.5 N1.2>", not the password (reconciliation of python and go M10/6–11, S19; when — P/03.5 N3 «open»)
  log:       the log mask — this contract: the headers Authorization and
             Proxy-Authorization (Basic/Bearer), pairs with a secret name (`name=value` and a JSON pair), addresses (moved
             there without a change of behaviour; C06-LOG-MASK-33-01)
  argv:      never
  refusal:   the text of a refusal does not repeat the value
```

## Mask at the input

From P/06.2 N1.1 `mask_in` without a change (layout audit, the Architect's decision of 2026-10-25, A-21); the white-space characters are [the person name contract](person-name.md)
«White space» (`white_space`). The refusal of a write with such a value is P/06.2 N4.

```yaml
mask_in: a value of ≥ 3 characters of the set «* ＊ ∗ ⁎ ✱ • ● ∙ · ⋅ ◦ ○ ⚫» (white-space characters at the edges do not count — any characters
         of the set white_space of the person name contract: space, tab, U+00A0 and others; "\t***" and " ***" — a mask) — a refusal;
         a***b — a password (reconciliation of python and go M10/6–11, S12)
```

## Vectors

The package [`log-mask`](../vectors/log-mask/README.md) supplies test text and field declarations to the masking function. The concrete field-catalogue fixture is not part of the model input; the caller supplies it at vector execution. The field declaration form is P/02.1 N1.2a; no fixture is required to implement the catalogue rule above. The store daemon and its CLI use the empty catalogue, not test field declarations. The value of a field `type: url` is the package
[`secret-in`](../vectors/secret-in/README.md) of the address contract. The journal, the heartbeat, the snapshot, argv without values — by reading
(P/06.2-05).

