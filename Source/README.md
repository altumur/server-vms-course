# Source — the course's code, one root: the platform, the VMS, the cluster, the domain

The lessons of four modules as one runnable package — 58 of them: М10_Platform 11 (the former М10A_Platform 21 and М11_Cluster 10, deleted 2026-10-14, ADR-0080), М10B_ServerVMS 28,
М12A_Domain 15, М12B_DomainVMS 4 (М13_Observability and М14_VendorVMS have a design, `module-design.md`, and no lessons
yet). On one box (М10, М10B): no scheduler, no KVS, no database: two stores on disk, a controller that is the only writer, a worker that is DriverPack and holds the camera, a recorder that is the only writer of footage, into volumes of ObjectStorage through the host's `obsd` — and three more subsystems through the same platform, which proves it knows nothing about video.

```
Source/
  w2cplatform/                 the platform (named so because Python owns `platform`)
    variables.py               Lesson 1  a config store with ModifyIndex and check-and-set, as files; one writer per prefix
    memvariables.py            Lesson 20  the same contract in memory, registered as `memory://` — the second backend, and
                               what the contract suite is FOR (CONTRACT_URL=memory:// python3 tests/run.py)
    objects.py                 Lesson 1  an object store: a directory
    epoch.py                   Lesson 1  the fencing-token issuer and the lease — generic
    contract.py                Lesson 1  Subsystem, Assignment, Heartbeat, Slot; the Controller and Worker bases; identity by claim
    events.py                  Lesson 3  the event log: buckets per unit per epoch on the resource, for any subsystem — generic
    resource.py                Lesson 3  the resource as a platform job: heartbeat, buckets over HTTP, retention by each subsystem's row, the mirror to a peer, restore
    eventdatabase.py           Lesson 10  EventIndex — a resource's own buckets, read where they lie, with a bounded cache; MergedIndex — what a console has instead: every live resource's /events, merged
    longpoll.py                М10B L25  a hint the reader pulls: Watch — the requests a resource holds until a watched line is appended (GET /events/wait);
                               LongPoll — one held request per resource; Wake — a loop's early pass, never sooner than a quarter of a second
    spec.py                    Lesson 6  the controller as data: SubsystemSpec (rows, fields, derived rows, placement by name — requires, servers, near — snapshot, the two ACLs) and SpecController, the one controller every subsystem runs
    speckeys.py                the closed key sets of a spec: every key the platform reads, at every level — any other is
                               refused at load, named where it stands (no key is accepted and passed over)
    console.py                 Lesson 7  the console as data: SpecConsole over the same spec — the page, /spec, /<rows>, /where, /metrics with the subsystem's prefix, /marks, the writes with the spec's refusals; a subsystem registers extra routes;
                               Mount — one process fronting several subsystems, the root at / and the others under their names (/live/…, /det/…)
    secrets.py                 Lesson 23  the `*_secret` rule: mask_secrets on the way out of the console, and a spec that
                               names a secret in its snapshot does not load; an address read as RFC 3986 writes one, and how a
                               subsystem's addresses carry a login besides that from its url field's `secret_in` (`param`/`login`
                               names, regexes by part, scheme and decoded text, `nested` pairs); a refusal names the field of
                               `credentials` for what it found
    catalog.py                 the specs this process loaded (or `SPEC_DIR` names): which objects are rows, how an address
                               carries a login — what the platform used to know by name (the boundary's step 4)
    host.py, __main__.py       the platform's own processes for any subsystem (the boundary's steps 5 and 6): `python3 -m w2cplatform
                               controller <sub> | resource | console` from `SPEC_DIR` (`CONSOLE_ROOT` names the spec at `/`),
                               and the loops every controller, console and resource
                               runs — `controller_loop`, `placement_pass`, `step` (said once a spell), `sweep_loop`, `run_resource`
    console.js, console.css    Lesson 16 the console module every page is built from (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md, version 1, the product's file):
                               the tree, the forms, servers, the domain, rights, the journal — from /spec and the platform's doors
    reconcile.py               Lesson 4  the reconcile helper (ADR 0033): М9 Lesson 6's loop — desired persisted, running derived,
                               backoff that doubles to a ceiling, spread by jitter — for any worker with a set of pipelines
    console.html               Lesson 16 the platform's page: the module and its mount, nothing else — `/` for a root subsystem with no page
                               of its own (`<sub>.shell.html` beside its spec); only the console's root serves a page
  vms/                         the VMS — the first subsystem
    obsd.py                    М10B L6  the client (the VMS's: the platform knows no archive engine) of ObjectStorage's daemon: frames over a unix socket, Session/Volume/Writer/Reader, SMPL samples,
                               archive time; a silence is `Unavailable` after a timeout and is not asked twice
    archive.py                 М10B L7  the course's vocabulary over obsd: streams <recording>/e<epoch> (…/backfill, e0 for a keep's copy), Span,
                               authoritative (the highest epoch owns each stretch), visible_from (retention as a ceiling), ArchiveError (wrong / away / busy),
                               Archive — one volume: open (format at quota), put, finish, seal, a fresh reader per question, spans, samples
    worker.py                  Lesson 4  camworker: holds N cameras against an assignment — one connection, one fan-out (live_url) each, events into the resource, no footage; an epoch per camera; a lease; the heartbeat with server, labels and capacity — on a box or in an allocation
    rec.subsystem.yaml         Lesson 5  the FOURTH subsystem, as a spec: recordings named by the operator (id: name — one per archive a camera is written to), retention_days, requires: resource, servers: distinct over place_by: volume — the only one placed on the archive
    recworker.py               Lesson 5  RecWorker: VmsWorker over rec/recordings/*, fed by the worker's tee from the VMS heartbeat — shared memory on the same server, RTSP from another;
                               takes a volume (declared, by hold, or its server's own) and writes into it through obsd under owner rec:<volume>; re-subscribes when the
                               camera's holder moves; serves its volume at its archive door (/timeline, /samples); backfill, backups, keeps into an incidents volume
    volumes.py                 М10B L27  the volumes an operator declares — local, network, backup, edge, incidents — and who may serve which
    card.py                    М10B L26  the camera's card WITHOUT an engine, as the product does it — and the camera's memory as ONE budget in bytes
                               (32 MiB: ring 24, the card's queue 6, two pieces of 1): CamRing (one ring, a window of 60 s, `reach()` at the bitrate it is given),
                               CardBuffer (segment files with a byte budget, oldest deleted, an open segment a stream, a range reader that hands over pieces
                               and raises), CardActuator (hold, keep by recording, a queue in bytes that drops to the next key frame, the ring taken a piece
                               at a time, a recording that goes on from where it stopped), CardRecorder (RecWorker's gate over the card; a failing card closed,
                               said and opened again; `card.prebuffer.short`)
    cam.subsystem.yaml         Lesson 6  the VMS's controller, as a spec: cameras numbered, seven operator fields, cam/retention/<cam> derived, labels-subset placement, requires: resource (for its events), the snapshot
    controller.py              Lesson 6  the VMS's words (create_camera, cameras) over the platform's SpecController, for the tests and the
                               lessons — no process: the controller of `vms` is `python3 -m w2cplatform controller cam`
    console.py                 Lesson 7  the one-box console's Mount for the tests and the lessons (the process is `python3 -m w2cplatform
                               console`, `CONSOLE_ROOT=cam`): the platform's SpecConsole over the VMS's specs and nothing of the VMS's own — no media route: /where/<id> hands out the holder's door with a token, and the page reads
                               the footage from the recorder (/timeline, /segment) and the stream from the gateway (/whep) itself; the first viewer asks for a
                               fan-out with POST /live/streams
    cam.shell.html             Lesson 12 the VMS's page, `/` when CONSOLE_ROOT=cam (beside cam.subsystem.yaml): a shell over the platform's console module —
                               the camera's video (live at the gateway's door, the timeline from the recorders' and the places' doors) and archive, the volumes,
                               the scenarios, the domain's cameras; its core (the doors, the timeline, the pieces, WHEP) the product's, checked by
                               tests/test_shell_core.py; jsdom tests tests/console/shell-*.test.js
    live.subsystem.yaml        Lesson 8  the SECOND subsystem, as a spec: live fan-outs named by camera, placed on gateways by viewer headroom, labels for where viewers are
    det.subsystem.yaml         Lesson 9  the THIRD subsystem, as a spec: one model on one camera, named by the operator, placed on GPU-labelled workers by stream headroom
    detworker.py               Lesson 9  DetWorker: runs a Model against the camera's fan-out, writes what it saw into det/<unit>/e<epoch>/ on the resource under its own epoch —
                               the kinds the row names in `alarms` as alarms (det.alarms/…), `motion` suppressed by the spec's window
    liveworker.py              Lesson 8  LiveWorker, a worker whose unit is a camera's fan-out and whose capacity is viewers: one subscription to the worker's
                               RTSP fan-out (live_url) per camera, N webrtcbin peers behind it, WHEP (POST /whep/<cam>, DELETE /whep/session/<id>), demand-created and demand-deleted units
    config.py                  the schema's Python view over the spec: row() and items()
    jobs.py                    the VMS's housekeeping: the requests turned into work and the finished work into closed rows
    __main__.py                python3 -m vms worker | recorder | gateway | detworker | detjobworker | surveyworker | autoworker — the
                               VMS's workers — and jobs. Every controller, the resource and the console are the
                               platform's (`python3 -m w2cplatform …`, the boundary's step 6): the VMS has no process of its own
                               beside its workers and these two
  gstvms/                      Track 2 — needs GStreamer
    uri.py                     Lesson 2  driverpack://file/<name> resolved and refused — pure, no GStreamer
    webrtc.py                  Lesson 8  the gateway's media path (Track 2): rtspsrc ! depay ! parse ! pay ! tee per camera, queue ! webrtcbin per viewer, WHEP without trickle
    livesrv.py                 Lesson 4  FanOut: the worker's RTSP server (GstRtspServer) re-serving each camera's loopback RTP port as rtsp://<server>:8554/<cam> — shared, TCP-interleaved
    driverpacksrc.py           Lesson 2  the element: looping, PTS rebased across the loop
    actuator.py                Lesson 4  GstActuator: driverpacksrc ! h264parse ! watchdog ! tee ! rtph264pay ! udpsink, per camera, published by FanOut; the bus drained into (dead, posted)
                               Lesson 5  GstRecActuator: shmsrc (the worker on this server) or rtspsrc ! rtph264depay (another server), then h264parse ! watchdog ! appsink —
                               each access unit a sample into the volume's writer
  deploy/                      Quadlet, on М9's box: Containerfile (localhost/vmsserver:latest, the image М11 builds FROM), obsd.service (the host's archive engine),
                               w2c-controller@.container (every subsystem's controller, one instance per spec, as `w2c`), w2c-console.container,
                               w2c-resource.container — the platform's; camworker@, recworker@ (the only writer of footage), liveworker@, detworker@,
                               detjobworker@, surveyworker@, autoworker@.container and vmsjobs.container — the VMS's; w2c-spares.sh and its units
                               (a spare for an offer); w2c.env.example + vms.env.example, check-quadlet.sh
  tests/                       the suite: no GStreamer, but the archive's tests start a real obsd (OBSD_BIN); every runner keeps the run's
                               temp dirs under a root of its own (/tmp/w2c-tests-<pid> on macOS), removed at exit (runroot.py)
    cluster/                   М11's suite, its own runner (python3 tests/cluster/run.py), the traced stand (stand.py, trace.py)
    domain/                    М12A's suite, its own runner (python3 tests/domain/run.py)
    domainvms/                 М12B's suite, its own runner (python3 tests/domainvms/run.py)
    console/                   the console module's and the pages' jsdom tests, run by tests/run.py (`npm install` there, once)
  w2cplatform/cluster/         М11: what a cluster adds on top of the above (w2cplatform/cluster/README.md) — `python3 -m
                               w2cplatform.cluster controller <sub> | console | resource | rights`; the store's daemon is
                               `python3 -m w2cplatform.configstore`
  w2cplatform/domain/, trust/  М12A: the layer above the clusters — `python3 -m w2cplatform.domain.signer_service | .console |
                               .agent`, the holder's tools `w2cplatform.domain.members | grants | breakglass`; the operator's
                               tool `python3 -m w2cplatform.w2cctl`
  deploy/cluster/, deploy/domain/   М11's units and installer (`w2c-run.sh <program>` runs every one of them), the domain's
                               platform units and its image
  traces/                      М11's stand's traces, quoted by its lessons (python3 tests/cluster/stand.py --write)
```

```bash
OBSD_BIN=<out>/build/obsd python3 tests/run.py        # obsd built from ObjectStorage: standalone-build/build.sh <out>
python3 tests/cluster/run.py; python3 tests/domain/run.py; python3 tests/domainvms/run.py   # М11's, М12A's, М12B's suites
SPEC_DIR=vms python3 -m w2cplatform controller cam     # the cameras' controller: the platform's, from cam.subsystem.yaml
SPEC_DIR=vms python3 -m w2cplatform controller rec     # the recordings' — one per spec: vms rec live det detjob survey auto
SPEC_DIR=vms python3 -m w2cplatform resource           # the box's resource: heartbeat, every spec's buckets, /events
SPEC_DIR=vms CONSOLE_ROOT=cam python3 -m w2cplatform console   # the console on :8080: the VMS at /, the others under /rec/, /live/, …
WORKER_NAME=w-1 python3 -m vms worker                  # with GStreamer: holds cameras, rtsp://<box>:8554/<cam>; without: the fake actuator
RECORDER_NAME=r-1 python3 -m vms recorder              # subscribes to the fan-out, writes into its volume through the host's obsd
LIVE_NAME=g-1 python3 -m vms gateway                   # a live gateway: WHEP for the camera's viewers
python3 -m vms worker                                  # no name: claims the first free slot — a lapsed one first
python3 -m vms jobs                                    # the VMS's housekeeping: requests into work, finished work into closed rows
```
(`PLATFORM_DIR`, by default `/data/platform`, is where every one of them finds the box's two stores.)

## Storage request parsing — М10/1 implementation choices

The storage door accepts HTTP/1.0 and HTTP/1.1. Its request line is at most 65536 bytes including CRLF;
the complete header block, including its final CRLF, is at most 65536 bytes and 99 fields. Malformed HTTP
and parsing limits return `400 badrequest` as JSON Faults, unknown methods/routes `404 badrequest`.
JSON nesting is at most 64 objects/arrays, including the root. Repeated names are refused in every object;
ignored fields' strings and numbers have no further limit beyond body size and nesting. Numbers in ignored
fields are not converted to Python integers or floats. Key and items Unicode checks follow their own
Fault kinds and command validation follows Н2.1. Byte prefixes may stop inside a UTF-8 character.

The default POST body limit remains `6 * 524288 + 65536` bytes, enough for a fully escaped row at its ceiling.
`StoreDaemon(body_limit=1048576)` sets the acceptance stand's limit; the row ceiling stays 524288 bytes.
Chunked POST bodies are bounded after decoding; their overflow Fault has no `size`. GET bodies are unread.
`tests/test_storage_request_parse.py` supplies raw socket probes that scenario TSV cannot express.

## The Go implementation — the product's

The same contract in Go is the product, `vmssubsystem` (a repository of its own): the same platform, the same
subsystem, the same decisions. **It belongs to the product, not to the course.** The course is written against
this package, and lessons no longer promise that Go has caught up: where they compare the two, they are
describing how the product does it, not a second thing kept in step lesson by lesson.

## What each lesson's deliverable became — М10's first eleven, by its first plan

The numbers are the ones the `tests/test_lessonN_*.py` names keep, not today's lesson numbers of М10A and М10B.

| Lesson | Deliverable | Test |
|---|---|---|
| 1 | a config store that survives a restart and refuses a stale CAS; one writer per prefix; the contract a second team could implement; names by claim | `test_lesson1_platform.py` — including *the platform knows nothing about its subsystems* (no import from a subsystem's package, and not the word for the camera) and *identity by claim* (two claims, a lapse inherited, a release, the scheduler's index) |
| 2 | `driverpacksrc` running for an hour with monotonic PTS; the refusal of a vendor URI | `test_lesson2_driverpacksrc.py` — the URI logic here; the element and the hour on a box with GStreamer |
| 3 | the archive is a volume: streams named by recording and epoch, readable once their block closes, a fenced epoch on the timeline, retention as a ceiling, events still buckets on the resource | `test_obsd.py` — the engine's properties against a live daemon; `test_lesson3_archive.py` — the stream grammar, `seal`, the fenced epoch across two volumes, the retention ceiling, two writers for one camera |
| 4 | М9's four failures against the worker with its tests passing unchanged; the zombie on one box | `test_lesson4_worker.py` — М9 Lesson 6's seven, then the assignment, the epoch per camera, `live_url` in the heartbeat, the restart with the controller stopped, a nameless replacement inheriting the lapsed slot, the zombie fenced at the slot, the reassignment that is not one |
| 5 | *Record* pressed; the stream `1/e1` in the server's volume; the worker moved and the recorder re-subscribed under `e2`; *Stop recording* | `test_lesson5_recorder.py` — the recording placed on the archive (`requires: resource`, `servers: distinct`) beside the camera's worker (`near: vms`, the reason saying so) and fed from its tee through shared memory, or over RTSP when placed away from it, under the recorder's epoch, the frames landing in its volume while the resource's tree stays events-only, a restart writing a second stream and overwriting nothing, the re-subscription on failover, the recording that waits while nobody holds the camera, the toggle turned off |
| 6 | one box, one controller; the controller stopped, the worker killed, the cameras held again | `test_lesson6_controller.py` — refusals, stored placement by the capacity each worker reports, adding a worker moves nothing, two controllers agree, scale-in redistributed and a crash left alone, the failure arithmetic |
| 7 | the console as its own process; a camera added, edited, recorded, played, deleted from the page; two consoles answering one retry | `test_lesson6_controller.py::test_the_console_over_http` and `…is_one_camera` — the whole surface on a real port, a retry across two consoles; `test_lesson9_det.py::test_one_console_mounts_every_subsystem_it_fronts` |
| 8 | press *Live*; fifty tabs, one subscription; a gateway killed, the next offer answered by the survivor | `test_lesson8_live.py` — the first viewer creates the fan-out and the controller places it, fifty viewers one subscription and the worker unchanged, the grace period and the gateway deleting its own unit, a dead gateway's fan-outs moved to the survivor, placement by label, two subsystems sharing the platform |
| 9 | a model added to the camera from the page, its events beside the VMS's on the resource | `test_lesson9_det.py` — a model placed on the GPU worker and writing its own buckets under its epoch, a camera that stops leaving the model waiting, the unplaceable model placed when a GPU arrives, three subsystems' events on one camera's timeline through the console's index and fenced by their own epochs |
| 10 | three subsystems' events on one timeline through the resource process and the console; the database rebuilt to the same rows; retention taking the rows with the file | `test_lesson10_events.py` |
| 11 | the box: ten units, one image, an update that records nothing rolled back | `test_deploy_units.py` — the Quadlet units against the package: entrypoints, `/data` volumes, the mounts as the ACL, the image's contents |

## The three lines the code holds

**The controller is never on the recovery path.** `test_restart_with_the_controller_stopped` deletes the controller object, starts a fresh worker under the same name, and asserts it holds its cameras again — from its assignment, with the next epoch for each; the recorder re-subscribes to the new fan-out the same way, from the heartbeat.

**The controller never decides how many workers there are.** It has no scheduler client and no `count`. `test_scale_in_releases_a_slot_and_the_controller_redistributes` shows the only thing it does about worker numbers: moving the cameras of a slot whose holder *said* it was stopping — and leaving a merely silent one alone for Nomad. The workers export `headroom`; `/metrics` serves it; whoever runs `count` reads it.

**The platform knows nothing about video.** `test_the_platform_knows_nothing_about_its_subsystems` greps `w2cplatform/` — `events.py` included — for an import from `vms/` (or any subsystem's package) and for the word *camera*, which it reads from `vms/cam.subsystem.yaml`; `test_boundary.py` holds the whole tree to every word of the product.

## Verified where

The suite runs on the author's machine against obsd built from the ObjectStorage sources. `gstvms/` — the element, the two actuators and the RTSP fan-out — is written to GStreamer's Python binding and not exercised here; the logic it calls (`vms.archive.Archive` against a live daemon, the URI resolution) is. The hour-long PTS run, `kill -9` mid-recording, and the zombie with two real worker processes are the box's.
