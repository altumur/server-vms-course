# runtime.py — the units' environment turned into a `Federation` of `Cluster`s over the config store and the object store

**Role in the module.** Wiring, not behaviour. The processes that need the whole federation (`console.main`, a subsystem's domain worker) call `federation_from_env()` to build the same `Federation` the tests build with `conftest.make_domain`, over the real adapters: `variables.open_vars` for each cluster's store (`configstore://` — the process's role socket) and `open_objects` for its objects. `CLUSTERS` is written in `/etc/w2c/w2c.env` (`deploy/domain/systemd/domain.env.example`); the units name the role sockets.

## Functions

### `open_objects(url)`
A directory on this box (`file://` or a bare path) by the platform's `FsObjectStore`; any other scheme (`cluster://`, `http(s)://`, `s3+…`) by `w2cplatform.cluster.objectstore.open_store`, imported only then.

### `federation_from_env(var="CLUSTERS") -> Federation`
Parses `CLUSTERS=<name>,<name>=<store url>|<object store url>,<name>=report,…`:
- a **bare name** is this server's own cluster: its store by `PLATFORM_STORE` (the unit's role socket — the console's `domain`, a subsystem's domain worker its own `<sub>domain`) and its objects by the platform's `OBJECTS`. One line in `w2c.env` serves every domain process, each through its own socket.
- `<name>=<store>|<objects>` splits once on `=` and once on `|` (a URL may itself contain `=`).
- `report` (or `report@<relay>`) is a member the domain never opens a connection to, read from its reports (`uplink.member_copy`); from the first pass on, the domain's member list (`domain/members.py`) says who reports.

Every store is opened behind `declared.guarded`: a write that would give one name to two name spaces a spec holds apart (`domain.names`) is refused `declared.NameTaken`, whoever writes it — the domain's console and a subsystem's domain worker alike, without a line of the worker's (ADR-0031).

The holder is `DOMAIN_HOLDER` if set, otherwise the first entry. Empty entries are dropped; an empty list is `SystemExit` — a misconfigured unit dies at start rather than serving an empty domain. `reaches` is not set here; only the read side is wired. The units' own lines run through it in `tests/domain/test_lesson3_readview_api_gateway.py::test_the_domains_units_name_stores_that_open`.
