# Sealing vectors

This English text is the source; the Russian translation `ru/vectors/sealing/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The [sealing contract](../../contracts/sealing.md) defines the AAD path, the `enc:v2` envelope, opening, resealing and the ring file. Every process that seals or opens uses its own function, without a stand. The installer calls these functions through `w2cctl secrets`; the other consumers are the worker, the console and domain processes.

## Inputs and native results

| Function | Input | Native result |
|---|---|---|
| AAD | row key; path segments as a JSON array, a string for a key and a number for an index | JSON Pointer and AAD bytes in hex |
| Envelope | key, kid, nonce, row key, path, value | `enc:v2` envelope; opening it in the same place returns the value |
| Open | key, envelope, row key, path | value or `sealed`; an empty `key_hex` denotes no ring key with the envelope's kid |
| Reseal | ring, row key, row whose elements are text, json fields | `row`: `changed` \| `same` \| `skip`; observations by secret path |
| Ring | ring-file text as a JSON string | `current <kid>; keys <kid>, …` in file order or `unreadable`; rotation also reports `; rotate <kid>` or `; rotate refused` |

Keys and nonce arrive as bytes in `key_hex` and `nonce_b64url`; the implementation takes these input bytes and does not derive them anew. In operation a nonce is 12 random bytes. Values in `plaintext`, `expect` (except `sealed`) and `file` are JSON strings, with JSON escaping.

For reseal, the native labels `@same` and `@untouched` are observations: the adapter compares the actual before/after bytes produced by its regular reseal code. A `{kid, plaintext}` observation opens the actual new envelope with that key and the original AAD. It is not a copy of the expected marker or input plaintext. A random nonce means new envelope bytes are not compared. The expectation columns are judge-side data and never enter the call.

## Who performs

The installer (`02-installer`), worker (`03-worker`), console (`06-console`), process `domain` (`08-domain`) and agent (`09-agent`) execute AAD, opening and ring reading. The installer, console, process `domain` (the book at its holder) and agent (the member key and book rows) also seal; the worker only opens (P/03.5). The console reseals at start and the installer through `w2cctl secrets seal`. Only the installer rotates, through `w2cctl secrets rotate`. A role executes a function when its norm calls it; the ring holders are P/06.2 N1.2 `holders`, the installer is P/02.4 N1.9.

## Checks outside the function

Invalid UTF-8 of the ring file and symbolic links cannot be represented by a JSON string; they are checked by reading the file. The contract governs a discrepancy; «Specification» corrects the vector.

## Vector wire

The public `table` selectors dispatch `aad.tsv` to AAD, `envelope.tsv` to Envelope, `open.tsv` to Open, `reseal.tsv` to Reseal and `ring.tsv` to Ring (judge-only: `aad.tsv`, `envelope.tsv`, `open.tsv`, `reseal.tsv`, `ring.tsv`).

The `common/sealing` rows of [the single form](../wire.tsv) (judge-only: `wire.tsv`) bind the tables, headers, selected inputs, fixtures, native outcome and comparison. The public [wire grammar](../wire.md) defines the command frame. Algorithm meaning and consumer obligations remain here.

Concrete tables, fixed bytes, branches and expected answers are in [case data and coverage](README.cases.md) (judge-only: `README.cases.md`).
