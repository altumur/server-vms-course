# Vectors: the createExport repeat-body digest

This English text is the source; the Russian translation `ru/vectors/export-repeat-digest/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is V/11.20 Н1.2, the body-digest rule in [the chapter norms](../../spec/11.20-backend.norms.md); the stored field is `body` of `backend/repeats` in [V/11.4 Н1.4](../../spec/11.4-backend.norms.md). This package changes no other operation. It isolates digest calculation, not the acceptance of an HTTP request or a write. Every password in the table is synthetic test data.

## `cases.tsv`

UTF-8, LF, six fields separated by TAB; the first row is the header. A cell is read byte for byte between TABs; JSON escapes belong to JSON and are not unescaped by the table reader.

- `case` — the unique case name;
- `raw` — the JSON body text to parse;
- `canonical` — the exact JCS text after removing only `password` and `supervisor.password`, without a final LF;
- `sha256` — lowercase hex SHA-256 of the UTF-8 bytes of `canonical`;
- `relation` — `-`, `same:<case>` or `different:<case>`, an additional comparison of the two digests;
- `note` — the reason for the case.

## Required comparisons

There are 16 cases. Password-only changes and absence of the optional root password preserve the digest. Object-key order, whitespace, Unicode escape spelling and an equivalent numeric spelling preserve it too. Retained names, the supervisor login, a camera value, array order, a period bound and a comment remain part of the hash input. If both excluded paths are absent, the whole parsed body is canonicalized as is; an absent supervisor object is not introduced.

The canon is RFC 8785 in full, as in the existing [P/01 JCS package](../../../../Platform/01-store/vectors/jcs/README.md). These cases do not replace that package's general serializer conformance cases.

## Execution and limits

The backend vector driver feeds `raw` to its createExport body-digest calculation and compares both `canonical` and `sha256`, then checks `relation`. This specifies no new CLI, HTTP operation or function signature. A matching vector does not prove rights, supervision, export execution, repeat-memory races or expiry. The author checked the expected bytes and hashes as data; no backend implementation or cluster was run.
