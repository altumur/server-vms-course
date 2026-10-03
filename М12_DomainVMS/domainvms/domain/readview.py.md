# readview.py — Lesson 3: the camera list built from every cluster's worker heartbeats and its published configuration, held in memory, with an age on every row and one cause per dead server

**Role in the module.** Lesson 3, "the camera list, and where the console gets it". The docstring rules out the two easy answers: not a fan-out to N cluster consoles (waits for the slowest, breaks on the first dead one) and not status in Variables (raft is not for frequent, large data). The read model reads what each cluster's *workers* already publish beside their heartbeat — `vms/<worker>/heartbeat`, carrying the worker's status per camera, its server and its epochs (`../../../vmsserver/vms/worker.py.md`, `heartbeat_once`) — holds them in memory and serves list, search and pagination from there: no call to any worker or controller on any request; a cache that admits to being one, rebuilt by one pass over the objects on restart. Staleness is shown, never hidden: every row carries the age of its heartbeat, a worker older than `lost_after` is "stale — last known state" with its cameras still listed, and a cluster that did not answer keeps its rows from the last successful pass and is reported as unreachable — never as empty. Grouped by failure domain: the heartbeat carries the server, so when a server dies its workers go silent together and the console shows ONE cause. Used by `console.Console` (a refresher thread calls `refresh()`; the routes call `list()` and `causes()`) and the Lesson 3 tests. It reads a SECOND source for the cameras no worker reports at all: each cluster's `vms/snapshot/*`. A heartbeat is an observation (*this camera is running, at this revision, on this worker*); the snapshot is the configuration (*this camera is supposed to exist*). A camera in both appears once, from the observation; a camera only in the snapshot — nothing placed it, or the worker holding it has never reported — appears marked `configured`, and that is the whole of "set up but not working". Until this was written those cameras were not in the list at all: an operator could add one, watch it fail to be placed, and see nothing in the domain — absence, which is the most confusing shape a fault can take.

## `class Row` (dataclass)
One camera as the console lists it.
- `camera: int` — `st["id"]` from the heartbeat: the cluster-local id (see Notes).
- `ref: str` — the name the DOMAIN knows the camera by. It is also the dedup key between the two sources, because the cluster's number is the cluster's: every cluster has its own camera 7.
- `name: str`, `worker: str`, `cluster: str`, `server: str` — where it is.
- `phase: str`, `position: str` — the worker's own words (`running`/`pending`/`failed`, `converged`/`lagging`/`stalled`), passed through untouched (the API docstring insists on this).
- `revision: int`, `observed_revision: int`, `epoch: int` — from the status entry.
- `age: float` — seconds since the heartbeat this row came from.
- `worker_state: str` — `live` | `stale` | `unreachable` (the cluster did not answer on the last pass) | `configured` (in the cluster's snapshot, no worker reports it).

### `to_json(self) -> dict`
The fields plus `as_of`: `as of 3 s ago` when live, `configured — no worker reports it; the cluster's copy is 12 s old` when configured, else `<state> — last known state, 100 s old`.

## `class Cause` (dataclass)
Silence explained at the largest failure domain.
- `scope: str` — `cluster` | `server` | `worker`.
- `name: str` — the cluster, `<cluster>/<server>`, or `<cluster>/<worker>`.
- `silent_for: float` — seconds since the most recent heartbeat in the group (for a cluster: since the first failed pass).
- `workers: list[str]`, `cameras: int` — what the silence covers.
### `sentence(self) -> str` — `server silent: north/srv-1 for 100 s — 2 worker(s), 100 camera(s)`.

## `class Snapshot` (dataclass)
The last heartbeat seen from one worker, as kept in memory: `worker`, `cluster`, `ts`, `server`, `status` (the raw list of status dicts), and `doors` — the worker's published `live_url`, `playback_url` and `coverage`, and since Lesson 16 `push` (nobody can dial this one) and `polls` (a member camera, holding a poll) — `DOORS`, kept since Lesson 13 because the source book is built from them. Not to be confused with a cluster's `vms/snapshot` object.

## `_text(v) -> str`
"A field shown and searched as text": `""` for `None`, else `str(v)`. A row's `name` is read through it in both sources: `{"id": 2, "name": 42}` in one heartbeat broke `GET /api/cameras?q=` for every operator (`r.name.lower()`, the review's eighth pass). `test_foreign_data.py::test_a_name_that_is_not_a_string_stops_no_search_and_a_camera_claimed_twice_is_contested`: `q="42"` finds it.

## `class ReadView`

### `__init__(self, fed, lost_after=45.0, wall=time.time, lanes=1, backoff=0.0, backoff_max=60.0)`
`lost_after` is the same 45 s as М11's `disconnect.lost_after` and the resource's `lost_after`: a heartbeat older than this means the worker is gone. State: `snapshots: {(cluster, worker): Snapshot}`, `configured: {cluster: [snapshot rows]}` and `configured_at: {cluster: ts}` (the second source and its age) (survives across passes — that is what keeps an unreachable cluster's rows), `cluster_ok: {cluster: last good pass time}`, `cluster_down_since: {cluster: first failed pass time}`, `passes` (reported by `/healthz`), `why: {cluster: reason}` — why each member that did not answer did not (the review's eighth pass: "has not reported for 60 s" and "reports through relay east, which runs an older build; update it" are different things to do about it). Lesson 11: `lanes` members are read at once; `backoff` > 0 makes a silent member wait `backoff · 2^(failures−1)` seconds, capped at `backoff_max`, before it is asked again (`failures`, `retry_at`). The defaults are Lesson 3's pass: one lane, every member every pass.

### `_read(c)` (static) and `_try(self, c)`
One member's part of a pass: `c.heartbeats()` and `c.snapshot()`, each read ONCE — the pass used to call `snapshot()` twice (for the rows and for their age), a third of every pass at three hundred members (`test_one_pass_asks_each_member_four_things_and_no_more`). `_try` turns `Unreachable` into `None` and keeps its message in `why`; whatever the member's read still raises of what it published (`PARSE_ERRORS` — its copy's rows, a relay's bundle) is that member's too: counted in `MEMBER_OBJECTS` (`<cluster>/(read)`), `why` = `what it published does not parse: …`, `None` — the member reads as one that did not answer, its rows kept as last known, and the other members are read. A member that answered drops its `why`. `test_foreign_data.py::test_a_relay_of_an_older_build_whose_bundle_is_a_list_is_refused_by_name_and_shown`: `list()["why"]` names "relay east runs an older build" and "update it".

### `refresh(self) -> None`
The one pass, over the members whose `retry_at` has come. Read in a thread pool of `lanes` when `lanes > 1`, in turn otherwise; the results are applied in member order either way (`test_reading_in_lanes_changes_the_time_and_nothing_else`; `test_lanes_are_real_threads_not_only_arithmetic` times real sleeping stores). For a member that answered: every worker's heartbeat replaces its `Snapshot` — one whose `ts` or `status` is not numbers and a list (`PARSE_ERRORS`) is skipped, counted in `MEMBER_OBJECTS` (`<cluster>/vms/heartbeats/<worker>`), and the others are taken — the snapshot's rows and `ts` replace `configured`/`configured_at`, `cluster_ok` is stamped, and `cluster_down_since`, `failures`, `retry_at` are cleared. For one that did not: `cluster_down_since` (kept at its first value), and with `backoff` the next `retry_at`. Its rows stay as they were. Increments `passes`.

### `last_known(self, camera) -> tuple[str, dict] | None`
Lesson 9. The cluster whose last snapshot carried the camera the domain calls `camera` (its `ref`), and that row — kept when the cluster stops answering, which is the point: a kept edit is measured against what the domain last saw.

### `where(self, camera) -> Answer`
Lesson 11. "Where is camera X" from this pass's memory instead of `DomainDirectory.where`'s scan of every member — which at three hundred members is two calls per member per edit (`test_where_from_the_directory_scans_every_member_on_every_edit`: 28 550 calls for fifty edits through the directory, none from memory). Exactly as honest: found only in a member that answered, `unreachable` lists the silent ones and the never-read, two claimants raise.

### `rows(self) -> list[Row]`
From memory: for each snapshot, `age = now − ts`, `worker_state` = `unreachable` if the cluster is down, else `stale` if `age > lost_after`, else `live`; one `Row` per status entry, `name` through `_text`, `ref` from the entry. An entry that does not convert (`PARSE_ERRORS`) is that entry's: left out, counted (`<cluster>/vms/heartbeats/<worker>#<id>`). Then the second source, for reachable clusters: each row of `configured` whose `(cluster, ref or id)` no heartbeat row has — deduped by what the DOMAIN calls the camera, since the cluster's number is the cluster's — becomes a `configured` row (`phase` `unobserved`, age of the cluster's copy). A row whose `id` is not an integer — `{"id": 1e400}` is `int(inf)`, an `OverflowError` the old list of exceptions left out, and `rows()`, `list()`, `publish()` all raised (the review's ninth pass, major) — is left out, counted (`<cluster>/vms/snapshot#<id>`); a `revision` that is not a number is counted and shown as 0. Sorted by (cluster, worker, camera). `test_foreign_data.py::test_a_camera_id_of_1e400_in_a_members_copy_freezes_no_list_and_no_view_of_the_domain`; the configured rows: `test_lesson3_readview_api_gateway.py::test_a_camera_nobody_is_running_is_in_the_list_and_says_so` and `test_a_camera_is_not_listed_twice_when_both_sources_have_it`.

```python
            for row in rows:
                try:
                    cam = int(row["id"])
                except PARSE_ERRORS as e:                  # its own list here left out `OverflowError`: `{"id": 1e400}`
                    MEMBER_OBJECTS.garbled(f"{cl}/vms/snapshot#{row.get('id')}", e)   # froze every list (the ninth review)
                    continue
                ...
```

### `list(self, q="", page=1, size=50, cluster=None) -> dict`
Filters rows by cluster and by `q` (case-insensitive substring of `name`, or exact match on the id), paginates, and returns `{total, page, size, rows: [to_json], clusters: {name: "ok"|"unreachable"}, why: {name: reason} for the members down, rpo: rpo(), complete: no cluster down}`. `test_two_hundred_cameras_from_heartbeats_nobody_called`: 200 rows from four heartbeat objects, `as of 3 s ago`, search `cam175` finds south/w-0. `test_unreachable_cluster_keeps_last_known_rows_and_says_so`: south down → its 50 rows still listed as `unreachable`, `clusters.south == "unreachable"`, `complete == False`.

### `causes(self) -> list[Cause]`
"Silence grouped by the largest failure domain that explains it." First, every down cluster is one `cluster` cause covering all its known workers and cameras. Then, among reachable clusters, the silent workers (`now − ts > lost_after`) are grouped by (cluster, server): if *every* worker known on that server is silent and there is more than one of them, that is one `server` cause (silent for `now − max(ts)`); otherwise each silent worker is its own `worker` cause. Sorted by most cameras first, then name. `test_kill_a_server_one_cause_displayed`: srv-1's two workers stop heartbeating, the others continue → exactly one cause, `server silent: north/srv-1 for 100 s`, workers `[w-0, w-1]`, 100 cameras, and the 100 rows are still listed as `stale` with `last known state`.

### `rpo(self) -> dict[str, float | None]`
How far behind each cluster's published copy is, in seconds (`DomainDirectory.ages()`), `None` for a cluster that did not answer; a reader never fails a list, so an exception there is no ages. A different silence from `causes()`: a stale snapshot means the cluster runs and the domain's picture of it does not move. `test_lesson3_readview_api_gateway.py::test_a_cluster_that_stopped_publishing_is_a_different_silence_from_a_silent_worker`.

### `publish(self, objects, crossings=None) -> dict`
What this pass saw, as ONE object (`w2cplatform.console.DOMAIN_VIEW`) in the domain holder's own object store (feedback X): `ts`, `complete`, `members` (`state`, `rpo`, and `why` for a member down), `units` (the rows, trimmed to `ref, camera, name, cluster, server, worker, phase, worker_state, as_of`), the causes' sentences, and the crossings. The holder's console serves it at `GET /domain` without asking any member anything. `test_lesson3_readview_api_gateway.py::test_the_domain_holder_console_draws_the_domain_from_one_object_and_says_when_it_is_old`.

## Notes
- `Row.camera` is the cluster-local id; the row carries the domain's `ref` too, and the two sources are deduped by it. The search does not use it: `q` matches `name` or `camera`, so two clusters each running an id 1 give two rows numbered 1, distinguishable by `cluster` and `ref`, and `q="1"` matches both.
- A server with a single known worker that goes silent is reported as a `worker` cause, not a `server` cause (the `len(group) > 1` condition): the code will not claim "server" from one witness.
- `cluster_ok` is written on every good pass but read by nothing.
- `refresh()` reads each member in `_try`: `Unreachable` and the parse errors (`PARSE_ERRORS`) make that member one that did not answer, with why (`why`, shown in `list()` and `publish`); any other exception (e.g. `NotImplementedError` from an `HttpObjectStore.list`) escapes to the console's step, which logs it once. See `deploy/console.nomad.hcl.md`. `where()` answers a ref two members claim as `contested`, not complete. A row's `name` is read as text.
