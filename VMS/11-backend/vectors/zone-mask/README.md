# Vectors: the detector zone raster

This English text is the source; the Russian translation `ru/vectors/zone-mask/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson V/11 ([the norms of chapter 3](../../spec/11.3-backend.norms.md) N1.3 «`zone`»; ADR-0112 addendum (1) item 3). They fix `ZONE_MASK` = 256 and the point rule. The numbers are derived from the norm and are not checked by an implementation. The run — with the `backend` driver.

## `cases.tsv`

UTF-8, LF, fields separated by TAB, the first row is the header:

- `case` — the case name;
- `shape`, `points` — the fields of `DetectorZone`;
- `count` — the number of points with the value 255;
- `sha256` — hex SHA-256 of the PGM body: `P5\n256 256\n255\n` and 65,536 bytes of the raster, rows from top to bottom, within a row from left to right;
- `note` — an explanation.

The centre of the point `(x, y)` is `((x + ½) / 256, (y + ½) / 256)`. The boundaries of the shapes in the vectors do not pass through point centres: checked by exact rational arithmetic, there are zero centres on the edges, and a point on a boundary is not judged by the norm. That is why the vertices are not round numbers: the diagonals between round vertices run through the centres.
