# Acceptance V/02.5 — the archive door

This English text is the source; the Russian translation `ru/acceptance/5/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`02.5-rec.norms.md`](../../spec/02.5-rec.norms.md) N5. The stand is as in [acceptance 4](../4/README.md); the recorder's archive
door is on loopback without a kit (`archive <worker>` of [the common VMS acceptance README](../../../common/acceptance/README.md)).

| Steps of `01-door` | Norm | What it observes |
|---|---|---|
| 1–6 | V/02.5-07 | the recorder holds a volume and announces the door address on loopback (`url` — `http://127.0.0.1:…`) |
| 7 | V/02.5-10 | without a kit the process route (`/spans`, admittance `role`) is closed — 401 `no_role` |
| 8 | V/02.5-04 | another path — 404 `no such path` |
| 9–10 | V/02.5-10 | the parsing of N2: a path with a trailing slash is not a route (404 `no such path`); another method on a route — 405 `method not allowed` (path → method before admittance) |
| 11 | V/02.5-05, -10 | the page route (admittance `token`) is open on loopback, without a token — 403 `forbidden` |
| 12 | V/02.5-10 | two errors at once — a path with a trailing slash and another method (`POST /spans/door/`): the path before the method — 404 |
| `02-audio` | V/02.5-04, -06 | `@manual`: the second track of a piece; the stand has no live driver with sound (ADR-0102 addendum (9) item 9) |

The process routes (`/spans`, `/samples`) — a TLS stand with role kits; the page routes with a token, the fMP4 piece, the ceiling,
fenced-off epochs, the log — by reading (N5 of the norms).
