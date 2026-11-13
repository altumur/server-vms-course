# Canonical JSON (JCS, RFC 8785)

This English text is the source; the Russian translation `ru/contracts/jcs.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

JSON text that a platform contract signs or compares by bytes uses RFC 8785 in full, without deviations.

## Canonical form

- Object keys are ordered by UTF-16 code units, not Unicode code points. The distinction applies to keys containing characters outside the Basic Multilingual Plane.
- The output has no whitespace between tokens. Strings are encoded in UTF-8; only control characters, `"` and `\` are escaped. Other characters have no `\uXXXX` or HTML escaping: `<`, `>` and `&` remain literal.
- Numbers use the shortest representation of ES6 `Number.prototype.toString`: `1.0` becomes `1`, `1e21` becomes `1e+21`, and `-0` becomes `0`. `NaN` and `Infinity` are refused.

The SHA-256 of a canonical JSON text is computed over the UTF-8 bytes of that form.

## Consumers and vectors

The common package [`jcs`](../vectors/jcs/README.md) defines the table format, command wire and roles that execute the vectors. A caller canonicalizes the JSON value named by its own contract; this contract does not extend the fields or documents signed by that caller.
