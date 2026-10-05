# vms-jobs.service — the VMS's housekeeping, on every server

**Role in the module.** `w2c-run.sh vms jobs` (`python3 -m vms jobs`) as `vms`, through the console's socket (`w2c-console`, the platform's role it writes as): the turns that make a request into work and work into a closed row — `record_on_request`, `detect_on_request`, the ends of recordings and detectors with an `until`, the reaper, the answered requests cleared. They ran inside the cluster's console process (`cluster/__main__.console_turn`) until the boundary's step 7; the console is the platform's now, built from the specs alone. Every write of a turn is a CAS, so the unit runs on every server and two of them end a recording once. Its own numbers on `JOBS_PORT` (`vms_requests_expired_total`). No events archive and no key: it writes rows and reads heartbeats.

## Notes
- `tests/cluster/test_units.py`: the role's socket and group, `w2c-run.sh vms jobs`, after `configstore.service`, as `vms`.
