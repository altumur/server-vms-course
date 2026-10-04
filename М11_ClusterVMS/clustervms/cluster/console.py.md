# console.py — the cluster console: М10's console, unchanged — `SpecConsole` over the VMS spec with М10's media routes

**Role in the module.** Lesson 5. The console is not rewritten for a cluster: it is `w2cplatform.console.SpecConsole` (see `../../../vmsserver/w2cplatform/console.py.md`) run from `vms.subsystem.yaml` — the page, `/spec`, `/cameras`, `/where`, `/resources`, `/unplaceable`, `/events`, `/metrics`, `/marks`, the POST/PUT/DELETE writes and the Idempotency-Key store — with М10's media routes registered (`vms.console.vms_routes`). Those were written to find footage by the recorders' heartbeats, so a cluster changes nothing about them: a camera's footage may be in two volumes on two servers, and the console asks every live recorder's archive door. It runs as its own unit on every server (`deploy/systemd/vms-console.service`) through its own socket of the store (`console`, `deploy/configstore-rights.json`): the operator's rows, never placement — a write it must not make is a 403 from the store's daemon, not a rule here. Used by `__main__.console` and by `test_the_console_over_http`.

## Functions

### `cluster_routes(ctl, rec_ctl=None)`
`vms_routes(True, None, ctl, rec_ctl)`:
- `GET /timeline/<cam>?from=&to=` — every recording of the camera (`recordings_of`), from every live recorder's door, each span tagged with its `recording`, `recorder` and `volume`, and `fenced` against the recording's epoch row in raft. A door that did not answer is listed in `unreachable`; a volume nobody serves now — its recorder silent and nobody else holding it, which is what a dead server's disk looks like — in `unavailable`, with the note "… is unavailable until a recorder holds it again — not lost". Everything answered: a plain list.
- `GET /export/<cam>?rec=&from=&to=` — the interval as a fragmented MP4, from whichever doors hold it, and an `archive.read` line in the console's journal with its sha256.

### `make_console(ctl, worst_failover=0.0, index=None, archive_root=None, rec_ctl=None) -> Mount`
The VMS at `/` with `cluster_routes` and `media=True`; when `rec_ctl` is given, the recorder at `/rec/…` (the page's Record toggle). Both answer `/events` from the same `MergedIndex` over the resources' indexes.

### `serve(ctl, host, port, worst_failover, index, archive_root, rec_ctl)`
`make_console(...).serve(host, port)`.

## Notes
- No `/segment` proxy any more: there are no files to fetch from a resource. The page plays what `/export` hands it, a piece at a time.
- `test_the_console_over_http` proves through this file: a POST with an Idempotency-Key retried is answered once, `PUT {"worker": …}` is refused with 400, `/where/1` agrees with the directory, `/metrics` carries the worst failover and live counts, a mark lands in the console's bucket on `srv-a`'s resource and is found by the index on its `cam` field, and a camera's timeline and an export come from srv-a's recorder's door.
