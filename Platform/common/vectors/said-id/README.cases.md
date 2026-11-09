# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/said-id/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing case data as judge-only provenance.

### Original passage 1

| `case` | the name of the row; `plain-…` — the SaidID equals the rid, `hashed-…` — a hash |

### Original passage 2

The boundaries: 40 and 41 code points for ASCII, Cyrillic (2 bytes), characters outside the BMP (4 bytes, two UTF-16 units), 40 and 42 for letters with
a combining mark (points, not graphemes); «#» first and inside; a comma; the space U+0020 and NBSP; Cf, Co, Cn; a digit outside
ASCII; ASCII punctuation and symbols; the largest rid of 200 bytes.

### Original passage 3

A side implements SaidID and the reading of `fetched` by its own function (the worker — the write, the console — the reading) and checks each row: `said.tsv` — SaidID(`rid`) equals `said` byte for byte; `read.tsv` — the outcome of the reading
equals `reported`. The vectors are derived from the norm; on a divergence the norm is right, the vector is corrected by «Specification».

End of judge-only case data.
