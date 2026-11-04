# Acceptance V/01.5 — the device archive and its door

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`01.5-cam.norms.md`](../../../spec/01.5-cam.norms.md) Н5. The stand, the directives and the door `holder` are in [the common VMS
acceptance README](../../../../common/acceptance/README.md) over the common platform README (export `7a875c75`). There are no certificate
kits. The run — after the first stage C generation that has passed
the platform acceptance (ADR-0090 addenda (8), (9)).

| Steps of `01-door` | Norm | What it observes |
|---|---|---|
| 1–3 | V/01.5-01 | a camera without a device archive — the heartbeat has no `coverage`, `playback_url`, `index_url` |
| 4 | V/01.5-02 | without a kit the holder routes (admission by role) are closed — 401 `no_role` |
| 5–7 | V/01.5-06 | the order of the checks of Н2 without a kit: a path with a trailing slash and an unknown path — 404 `no such path`, another method on a route — 405 (the path and the method come before admission) |
| 8 | V/01.5-06 | two errors at once — a path with a trailing slash and another method (`POST /devices/`): the path before the method — 404 `no such path` |

The routes `/devices`, `/recordings`, `/playback` with answers — a TLS stand with role kits.
Bytes, chunks, budgets, getting stuck, device sessions, `501 no index`, the outcomes of the class `mixed` (the handshake, 401, 403),
parsing of `from`/`to` — by reading (Н5 of the norms).
