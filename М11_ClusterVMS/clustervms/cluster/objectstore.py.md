# objectstore.py — the cluster's object store: files on every server (`cluster://`), the create-only keys in the store, and the other adapters

**Role in the module.** Lesson 1, and Lesson 6's objects step. `w2cplatform.objects.ObjectStore` (see `../../../vmsserver/w2cplatform/objects.py`) is three calls — `put`, `get`, `list` — holding worker heartbeats (`vms/heartbeats/<w>`), resource heartbeats (`platform/resources/<server>/heartbeat`), the controllers' snapshot shards and pass reports, and the blobs a row names by digest. The docstring's design decision (the owner's, 3 October: the cluster without an orchestrator): every object has ONE writer and almost every one is written again within a pass, so no consensus is needed to hold it — each server keeps its own objects as files, and its resource answers for them over HTTP (`w2cplatform/resource.py`, `/v1/objects`). `ClusterObjectStore` writes here and reads everywhere. What must be created once across the cluster (`CREATE_ONLY`: a worker's mark before a device command) is a row in the replicated store through `VariablesObjectStore`; a blob is copied by the resource to the next live peers (`Resource.mirror_blobs`) and deleted by the sweep on every server that answers. No ceiling: the 64 KiB went with the Variables. `vms/` and `w2cplatform/` never know which adapter they hold; `s3+http://…` stays for a rented cluster (М12 Lesson 8). Footage never goes to any of these. Used by `__main__` (via `open_store(OBJECTS)`) and by the tests.

## `class ObjectStore(Protocol)`
The contract restated locally: `put(key, data: bytes)`, `get(key) -> bytes | None`, `list(prefix) -> list[str]`. Keys are the platform's slash-separated names, never absolute.

## `class HttpObjectStore`
Anonymous PUT/GET against any endpoint with plain HTTP object semantics (MinIO with a bucket policy, nginx with dav, a proxy in front of presigned URLs). No listing.

### `__init__(self, base_url, timeout=10.0)`
Strips a trailing slash; keeps the socket timeout.

### `put(self, key, data)`
`PUT <base>/<key>` with `Content-Type: application/octet-stream`; anything but 200/201/204 is an `IOError`.

### `get(self, key) -> bytes | None`
`GET <base>/<key>`; 404 → `None`, other HTTP errors propagate.

### `list(self, prefix)`
Raises `NotImplementedError` with the pointer: plain HTTP has no listing, use `s3+http://` for the heartbeat prefix. So this adapter cannot serve a controller (which lists heartbeats) — only a writer.

## `class FsObjectStore`
A directory: the tests, and a bench with a shared mount. Same semantics as М10's `w2cplatform.objects.FsObjectStore`.

### `__init__(self, root)`
Creates `root`.

### `put(self, key, data)`
Writes `<root>/<key>.tmp` and `os.replace`s it over `<root>/<key>` — an object appears whole or not at all (a reader never sees a half-written heartbeat).

### `get(self, key) -> bytes | None`
The file's bytes, or `None` if absent.

### `list(self, prefix) -> list[str]`
Walks the tree, skips `.tmp` leftovers, returns sorted relative keys starting with `prefix`.

## `CREATE_ONLY`, `is_create_only(key)`, `_may_hold_create_only(prefix)`
The keys created once across the cluster, as globs over segments (`*` one segment, a last `*` the rest): `*/commands/*`. A directory's `link` is create-only on one server, and two holders of a device are on two. The product's camera clock chunks (`ingest/clock/*`) join with one line. `_may_hold_create_only` tells whether a listing of a prefix must ask the store too (`vms/` yes, `vms/heartbeats/` no).

## `class ObjectsUnavailable(OSError)`
The resource on THIS server did not answer: nothing of the cluster can be read from here. An `OSError`, read by every caller as "the store did not answer" — a controller that took a silent door for an empty listing would call every other server's worker dead.

## `class ClusterObjectStore`
`cluster:///data/platform/objects?resource=http://127.0.0.1:8090`. `max_bytes = 0`.

### `__init__(self, root, resource="http://127.0.0.1:8090", vars_=None, timeout=10.0, wall=time.time, clock=time.monotonic, list_fresh=1.0)`
`local` is М10's `FsObjectStore(root)` — what the resource here serves as `scope=local`. `vars_` is the store for the create-only rows; without it they are opened from the environment on first use (`store_url`, else `PLATFORM_STORE`, else `CONFIG_URL`). `missing` is the servers the last answer named as silent; `_where` and `_heard` are what this reader last listed and read of each server (`_remembered`, below).

### `put(key, data)`, `put_durable(key, data)`
A create-only key goes to the rows; anything else to the local file, its mtime set to the writer's `wall` — the `written` a reader picks the freshest copy by.

### `put_new(key, data) -> bool`
Only for a `CREATE_ONLY` key (a `ValueError` naming `CREATE_ONLY` otherwise): `VariablesObjectStore.put_new`, a row written with `cas=0`.

### `get(key) -> bytes | None`
A create-only key from the rows. A blob from the local file when it hashes to its name (a copy that does not is logged and skipped). Anything else — and a blob not here or rotted here — `GET /v1/objects/<key>?scope=cluster` at the resource here: the freshest copy, or `None`. `X-Missing` goes into `missing`; a 404 for a key whose server is missing answers the bytes this reader last read of it (`_heard`), and a 404 otherwise forgets them.

### `list(prefix) -> list[str]`
`GET /v1/objects?prefix=&scope=cluster`, the union of every server's, plus the keys of a missing server this reader last listed (`_remembered`), plus the create-only rows when the prefix may hold any; cached for `list_fresh` seconds, with what this process wrote or deleted meanwhile in it (`_seen`).

### `_remembered(prefix, listed, missing) -> set[str]`
**A server that does not answer is not a server that never was** (found by the module's stand: the power pull with the dead server's doors down). Its objects are files on it, and with it gone its worker's last heartbeat and its resource's left every listing — and `Controller.slot_fate` could not tell which server the worker ran on ("never said which server": wait for ever), nor see the resource silent rather than unknown: the dead server's units never moved. So the reader notes the server of every key it lists (`_where`); a key an ANSWERING server no longer lists is let go; the keys of a MISSING server are returned, and `get` answers their last bytes — ageing by their own `ts`, which is how the controller sees the two silences. A reader started after the server went never heard it and says nothing of it (the operator's decommission is for that). Tests: `tests/test_cluster_objects.py::test_a_reader_that_heard_a_server_answers_with_what_it_said_last_while_it_is_missing`, `tests/test_lesson4_failover.py::test_the_power_pull`.

### `delete(key) -> bool`
A create-only row by the store; a blob by `DELETE /v1/objects/<key>?scope=cluster` — here and on every server that answers (the sweep); anything else, this server's file.

## `class VariablesObjectStore`
NARROWED on the cluster to the create-only keys (`ClusterObjectStore` routes them here); the class still holds any key, which the module's stand uses. Objects as Variables: key `vms/w-1/heartbeat` becomes the Variable `objects/vms/w-1/heartbeat` with a single item `{data: <utf-8 text>}`. The store is whatever `Variables` the caller holds, so the rights come with its door: on the cluster only the create-only rows are here, and the rights file grants them to the role that makes them (`objects/vms/commands/*` to `vmsworker`, `deploy/configstore-rights.json`).

### `__init__(self, vars_, prefix="objects")`
`vars_` is any `Variables` (the process's `ConfigstoreVariables`, `FakeVariables` in older tests); `prefix` is stripped of slashes.

### `_path(self, key) -> str`
`<prefix>/<key>`; refuses `..` and a leading slash with `ValueError`, so no key can escape the prefix the policy was written for.

### `put(self, key, data)`
`vars.put(path, {"data": data.decode()})` **without** CAS — the comment: the last heartbeat wins, as it should. Objects here are always whole replacements, never read-modify-write. `Forbidden` from the token propagates (the Lesson 1 test proves a worker token cannot write `objects/vms/w-2/heartbeat` without `objects/*`).

### `get(self, key) -> bytes | None`
Reads the Variable and re-encodes `items["data"]`; `None` if the Variable is missing or has no `data` item.

### `list(self, prefix) -> list[str]`
`vars.list("objects/" + prefix)` with the store prefix stripped back off, sorted — so `objects.list("vms/")` returns `["vms/w-1/heartbeat"]` while `vars.list("objects/")` returns `["objects/vms/w-1/heartbeat"]` (the test asserts both).

### `delete(self, key)`
Deletes the Variable; beyond the Protocol, for a bench to purge a stale heartbeat.

## Functions

### `open_store(url, vars_=None) -> ObjectStore`
The URL scheme picks the adapter, as the docstring lists:
- `cluster:///path?resource=http://host:port` — `ClusterObjectStore(path, resource|"http://127.0.0.1:8090", vars_)`.
- `s3+http://host/bucket?region=r`, `s3+https://…` — `S3ObjectStore(endpoint, bucket, region|"us-east-1")` from `s3.py`, SigV4 with credentials from `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (on a server from its environment, never from code). The `s3+` is sliced off before `urlsplit`.
- `http://`, `https://` — `HttpObjectStore` (anonymous, no listing).
- `file:///path` — `FsObjectStore`.
- anything else — treated as a bare directory path.

## Notes
- `tests/test_cluster_objects.py`: three servers, a resource door each on a real socket, one `FakeVariables` — a heartbeat written on srv-a read on srv-b; the copy written last wins; a silent peer named, a silent door here `ObjectsUnavailable`; a blob mirrored, a rotted copy refused and read elsewhere; a 1 MiB shard; the command marks as rows conflicting across servers; the sweep deleting on the peers.
- A server whose resource is down hides its objects from a reader that never heard it; a reader that did answers with what it last heard, named missing (`_remembered`). The slots' leases in the store are what decide a worker's fate, the heartbeats and the resource's silence what say where it ran.
- `tests/test_lesson1_stores.py::test_objects_are_files_on_each_server_read_across`: a heartbeat a file on srv-a, read on srv-c through srv-c's resource, no row in the store, no ceiling; `::test_a_command_mark_is_create_only_across_the_cluster`: the mark a row, `cas=""`, refused to a socket without the grant. The module's stand (`tests/conftest.py`) runs this class with the resource's own code as its door (`StandObjects`), in process.
