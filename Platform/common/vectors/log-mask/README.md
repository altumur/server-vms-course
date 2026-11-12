# Vectors: the log mask

This English text is the source; the Russian translation `ru/vectors/log-mask/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the log mask contract](../../contracts/log-mask.md) (chapter [P/06.2](../../../06-console/spec/06.2-console.norms.md) N1.4 `never.log`; the pairs and the addresses — [the address contract](../../contracts/url-credentials.md)).
The participants are all processes of the platform that write a log (id-map: M10/7-08 → P/06.2-05, «all processes»). The bytes are written by
«Specification»; the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16, ADR-0083).

The concrete `fields.yaml` fixture is absent from the model input. The vector caller supplies its contents through `files`; the public field-declaration contract defines how the implementation reads it.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` are explanations, empty lines are skipped. There is no header. A cell is read byte for byte
between TABs, nothing is unescaped: `\t`, `\n` in a cell are two characters. Three fields:

| Field | Meaning |
|---|---|
| `raw` | the text as written — a log line, an error, a JSON document, a connection string; not a value of a field |
| `masked` | what the log shows: the credentials of the headers `Authorization` and `Proxy-Authorization`, the value of every pair with a secret name (both `name=value` and a JSON pair) and every address — with the mask |
| `note` | why the row exists; empty — there is no explanation |

## Run

A side masks `raw` by the log mask of a process that knows the manifests of the stand, and compares with `masked` byte for byte. The rule
of the catalog is the union of the rules of the fields `cam.source` and `rec.volumes.url` from `fields.yaml` of the vectors `secret-in`
(in the input of the single command `vectors` — `files` with the key `fields.yaml`; `cells: {raw}`; the inventory C04/C06-NEXT-167, the Architect's decision 2026-10-27)
with the common dictionary N1.1 `common_words` (the names that the manifest adds — `sig`, `psd` — are included).
Who performs it — every process of the platform that writes a log (ACC-VECTORS-CONNECT-04, the Architect's decision 2026-10-26; the principle ACC-VECTORS-CONNECT-03): the store daemon and its CLI (`01-store`),
the installer, `w2c-run.sh` and the workers script (`02-installer`), the worker (`03-worker`), the controller (`04-controller`), the resource
(`05-resource`), the cluster console (`06-console`), the process `domain` (`08-domain`), the agent (`09-agent`), the domain console
(`10-domain-console`); the console module (`07`) writes no log. The scripts of `02-installer` (`w2c-run.sh`, the workers script) write none of their
log lines past the mask: their diagnostics go through `w2cctl` — the same mask function of the role `02-installer`, there is no direct
write to the log file. The store daemon and the CLI (`01-store`) do not load manifests — their catalog is empty (the contract `log-mask`
`rule`) (C01-C02-LOG-MASK-ROLES-01, the Architect's decision 2026-10-27).

For P/01 the route of its target is this package with the fixture `fields.yaml` of `secret-in` alone: P/01 has no `secret-in` target and executes `cases.tsv` only, and `mask_in.tsv` is executed by `06-console` alone. In the vector the catalog rule comes from that fixture at every consumer, `01-store` included, although the catalog of the store daemon at work is empty (the Architect's answer on P01.86).

The value of a field `type: url` — the vectors [`../secret-in/`](../secret-in/README.md): in a free text an address ends at a space,
a quote, `\`, `<` or `>` (the address contract A2), in the value of a field — it does not.

## `mask_in.tsv`

The mask at the input — the log mask contract «Mask at the input» (`mask_in`); the whitespace — the person name contract `white_space`
(the Architect's decision 2026-10-27). UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line without `#` is
the header `case<TAB>value<TAB>expect<TAB>note`. `value` is the value of a secret field sent for a write, as a JSON string
(invisible characters — `\uXXXX`); `expect` — `{"mask": true}` (a mask: the write is refused, P/06.2 N4) or `{"mask": false}`
(a value). The mask characters are those that cover the display of the table `cases.tsv` and the vectors `secret-in` (`***`), and the whole set
of the contract.
The input of the single command `vectors` is `cells: {value}`; the native outcome is code 0 and the object `{mask}`, JSON by value.

Who performs it — the console (`06-console`: a write of a secret field recognizes a mask, P/06.2 N1.1 `mask_in`, N4); the other writers
of the log do not call `mask_in` — for them `cases.tsv` (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## What the vector does not cover

The journal, the heartbeat, the snapshot, argv and the text of a refusal without values (N1.4 `never`) — by reading against the write places of the implementation: these
outputs the table does not read (P/06.2-05).

## Vector wire

The wire of `cases.tsv`, `mask_in.tsv` is set by the `common/log-mask` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
