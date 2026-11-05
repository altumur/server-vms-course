# Vectors: login and password in an address (`secret_in`)

This English text is the source; the Russian translation `ru/vectors/secret-in/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is chapter [P/06.2](../../../06-console/spec/06.2-console.norms.md) of the console (Н1.1 `url_field`, `common_words`, `mask`; Н1.1а A1–A15;
Н3 «read_address»; Н4 the row «a password or a login in an address»). The participants are the loader [P/02.1](../../../02-installer/spec/02.1-installer.norms.md)
(the declarations `credentials` and `secret_in` of a field `type: url`, Н1.2а) and [P/02.4](../../../02-installer/spec/02.4-installer.norms.md)
(address parsing). The bytes are written by «Спецификация»; the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16,
ADR-0083). Moved from `Source/tests/testdata/secret_in.tsv` byte for byte (stage B, the move of lesson 6, the Architect's decision
on V8 of the plan of lesson 6); the head of the file is English, as it was: `М10/7 Н1.1а` in it is the former address of chapter P/06.2 Н1.1а.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` are explanations, empty lines are skipped. There is no header. A cell is read byte for byte
between TABs, nothing is unescaped: `\t`, `\n` in a cell are two characters. Five fields:

| Field | Meaning |
|---|---|
| `field` | by whose rule the row is read: `cam.source` or `rec.volumes.url`; a field the reader does not know is a wrong row, not a skip |
| `raw` | the address as written |
| `masked` | the display (Н1.1а A14): every password is `***` where it stands; the login — as written |
| `fault` | the refusal of the value as a value of the field (A15): empty — the credentials do not refuse it; otherwise — the field of `credentials` that the refusal names (`cred_secret`, `access_secret` — a password; `cred_username`, `access_key` — a login only) |
| `note` | why the row exists |

The declarations of the two fields are vector data, not a reference to the VMS catalog (ADR-0001): the file
[`fields.yaml`](fields.yaml) next to it (moved from the acceptance of chapter 6.2 byte for byte; stage C guess URLC-SOURCE-01, the Architect's decision 2026-10-23; the key is the name from the column `field`, the value is the declaration
of the field by the form of P/02.1 Н1.2а). The rule of the catalog for nested addresses (A8) is the union of the rules of these two fields with the common
dictionary Н1.1 `common_words`.

## Run

A side reads each row by the rule of the named field:
1. the display equals `masked`, byte for byte;
2. the refusal is empty or names the field from `fault`;
3. the text of the refusal does not contain the value of the password: Н4, a refusal does not repeat the value. The password value of a row is the substring of `raw`
   that `masked` covers with `***` (with several — each one); a password shorter than 4 bytes is not checked by this item — such
   characters the text of a refusal may carry without a leak (the reading of the commits of «cammeta-acceptance» 2026-10-20).

The package checks the display and the refusal by the credentials (`fault` — a field of `credentials` or empty), including the refusal of an address that does not
parse by RFC 3986 (a character outside the grammar of A2, a non-numeric port) — it names `credentials.secret` (A15). Outside the package are
only the refusals of a parsed address by the «Схемам» of [the address contract](../../contracts/url-credentials.md) (a scheme not from `schemes`,
no host, at `host: path` no path): the credentials do not give them, `bad_url` is the url step of the row check; such a row has
an empty `fault` (stage C guess URLC-VECTORS-02, a refinement, the Architect's decision 2026-10-23).

A log line that is not a value of a field — the vectors [`../log-mask/`](../log-mask/README.md) ([the log mask contract](../../contracts/log-mask.md)).
Who performs it — by the items of the run: the display (item 1) — the console (`06-console`, P/06.2 Н3 «read_address», Н1.4) and the controller (`04-controller`, P/04 Н1.3а — the addresses of the snapshot with the same mask); the refusal (items 2–3) — the unit door of the console (`06-console`, P/06.1, P/06.2 Н4) and the customer's library (`03-worker`, P/03.6 Н1.6 — the url step of the row check); finding a password in an address — the process `domain` (`08-domain`, P/08.9 Н1.3 «Edit» step 4: item 2 — whether `fault` is empty, its refusal word is its own). The loader (`02-installer`, P/02.1 Н1.2а) checks only the declarations of the fields and does not perform the rows (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Native outcome

By the common rule «Vectors» of [the common acceptance README](../../acceptance/README.md) (two expectation columns — an object;
C06-VECTOR-SECRETIN-WIRE-168-12, the Architect's decision 2026-10-27). The input of the single command is `cells` `field`, `raw` (the cells
as written), `files` `fields.yaml`. The outcome is code 0 and a JSON object:

- `masked` — the display as a string (item 1), byte for byte with the column `masked`;
- `fault` — the field of `credentials` that the refusal names, or `""` — the credentials do not refuse the value (item 2), equal to
  the column `fault`;
- `text` — the text of the refusal as the side gives it (at the door — the `error` of the 400 answer, at the library — the reason in the log); only at
  a non-empty `fault`, otherwise there is no key. The runner checks item 3 by this field: `text` contains no password value
  of the row (the substrings of `raw` that `masked` covers with `***`, of length from 4 bytes); the text itself is not compared with the table.

A side gives the fields of its items of «Who performs it» (above): the display — `masked`; the refusal — `fault` and `text`; the process `domain`
— `fault`, only whether it is empty or not is compared (its refusal word is its own), and `text`. A field whose row the side does not
perform the runner does not compare; there are no extra keys.

## What the vector does not cover

The refusal at the unit door (400 `fault: bad_url`, the order of refusals Н3 step 2) — scenario 04 of [the acceptance of chapter 6.2](../../../06-console/acceptance/2/README.md);
the grammar of the url itself (schemes, host) — [P/02.1 Н1.2а](../../../02-installer/spec/02.1-installer.norms.md) `schemes` and the vectors
[`group-of`](../group-of/README.md).

## Vector wire

The wire of `cases.tsv` is set by the `common/secret-in` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
