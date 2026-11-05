# The presence lock contract: the file, who holds it, who reads it, the count `room`

This English text is the source; the Russian translation `ru/contracts/presence-lock.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5); analysis of the review of stage A 3–5, № 9). The owner is the resource
[P/05](../../05-resource/spec/05-resource.norms.md): it reads the locks of its box, derives from them the presence of the worker
processes (P/05 N1.4 `workers`, `running`, `unknown`, `presence`) and the count `room.<sub>` of the door row (P/05 N1.4
`door_row`). The lock is held by the worker — the worker's side: chapter [P/03.2](../../03-worker/spec/03.2-worker.norms.md) N3
«start()», step 2b; the number `room.<sub>` is read by the controller ([P/04](../../04-controller/spec/04-controller.norms.md) N3
«shortage(), order(), withdraw the order, shrink() — with grows: true»); the layout of the events root — [P/02.4 N1.2](../../02-installer/spec/02.4-installer.norms.md) «The setting channel
and the layout of `PLATFORM_DIR`». Moved from М10/8 N1.4 (`presence_lock`, `room`) and М10/11 N1.4 (`presence`) without a change of
behaviour; the derivation of the presence words from the fields of the resource heartbeat — P/05 N1.4 `presence`.

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The content of the lock is the family `presence-lock`: `Platform/05-resource/data/presence-lock.schema.json`,
`Platform/05-resource/data/presence-lock.outcomes.tsv`; the elements `room.<sub>`, `live.<sub>` are written into the door row
`platform/doors/<server>` — `Platform/05-resource/data/doors.schema.json`, `Platform/05-resource/data/doors.outcomes.tsv`
(layout audit, V-45; the Architect's decision of 2026-10-25).

## Lock

```yaml
presence_lock:  <events root>/.workers/<sub>/<instance>.lock   # the components — by the name encoding of the event journal contract
             # («File names in shared trees», event-journal.md); the Architect's decision, the second pilot, N-1
             content: JSON {instance, sub, worker, server, pid} — the instance, the subsystem, the slot name, the server, the pid of the process;
             the form — the family presence-lock of P/05 (the schema ../../05-resource/data/presence-lock.schema.json, the outcomes
             presence-lock.outcomes.tsv next to it): worker — the slot name, or "" before the capture of a name and while the worker searches without a name,
             pid — an integer ≥ 1, the set of fields is closed (analysis of the review of stage B 3–5, № 23; ADR-0083 addendum (11))
             the worker: at start, before the capture of a name (chapter P/03.2 N3 «start()»): open(O_CREAT) → an exclusive blocking flock
             (it waits while the resource releases the lock of its check; without LOCK_NB) → a comparison of fstat(fd) and stat(path) (the same
             device and inode; stat refused with ENOENT — the file is deleted — a mismatch; analysis of the review of stage B 3–5, № 19); no match — close and
             repeat from the start; a match — write
             the content anew (it does not append) under the lock, worker — ""; after every capture of a name — rewrite the content
             anew under the same lock, worker — the slot name (analysis of the review of stage B 3–5, № 23); at the loss of the name (give_up_name) — rewrite
             the content anew under the same lock, worker — "" (the Architect's decision of 2026-10-20 on № 23); it holds flock for the whole life of the process; the lock is released only by
             the exit of the process (ADR-0083 addendum (10))
  modes:     by the actual readers (guess of stage C PL-G02, the Architect's decision of 2026-10-23): the path to the locks — the events
             root and .workers — 2771, the group w2c-events: to others a passage without reading (guess of stage C PL-G03, the Architect's decision of 2026-10-23); .workers/<sub> — 2775,
             the group w2c-events (the files are created by the workers of different subsystems and deleted by the resource — the group writes; the workers script
             w2c-workers without groups, P/02.4 N1.5, — listing and reading as any other); the bucket directories — 2770/2750, the event
             journal contract bucket modes; the lock file — 0644,
             the owner — the worker's user, the group w2c-events (the resource opens it for flock and reads it as the group, the workers
             script — as any other); the mode is set by the writer explicitly at creation, not by umask (the processes have umask 0007, P/02.4
             N1.1 common); an existing path to the lock (the events root, .workers, .workers/<sub>) or a lock file with other
             permissions or another group — a refusal of the worker start before the write, a log line; existing objects the worker does not
             change itself (chmod/chown is the business of the installation, P/02.4), new directories and the file it creates with the exact permissions and group
             of the norm, the creation of a directory is serialized by the flock of the parent — the same rule as the event journal's bucket modes
             (guess of stage C PL-EXT-02, the Architect's decision of 2026-10-23); the content is without fsync — the truth about presence is in the flock itself, the content is for reference; an error
             of fstat/stat (not ENOENT) or of the write after flock — a refusal of the start or of the update, the lock is held until the process exits
             the resource: «known» workers — only by the lock files, the key <sub>/<worker> from the content; on every file —
             flock without waiting: took it — a comparison of fstat(fd) and stat(path) (ENOENT at stat is a mismatch, analysis of the review of stage B 3–5, № 19); no
             match — the file is already replaced or deleted, do not touch it; a match —
             the process is dead, gone (release the lock; a file that the resource deletes — delete it while holding the lock, and only then release,
             ADR-0083 addendum (10); analysis of the review of stage B 6–7, № 35); busy and the content by the form with a non-empty
             worker — runs; busy, while the content is empty, out of form or worker = "" — a live process without a number: it enters
             room.<sub>, does not enter workers, running, live.<sub>; unknown — only a file that does not read (an error
             of open or read), not its content (analysis of the review of stage B 3–5, № 23), and a lock whose check cannot be
             completed: an error of flock other than «busy» (EWOULDBLOCK), or an error of fstat/stat other than ENOENT at stat (that is
             a mismatch), — also unknown, like an unreadable file; do not touch the file (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7); one <sub>/<worker> has several files — runs, if at least one is busy;
             a gone file the resource MAY delete, holding its flock and after a matching comparison; there is no other source of presence (pid files, kill(pid, 0))
presence:   the resource tells about the processes of its box by the heartbeat fields of P/05 N1.4 (`workers`, `running`, `unknown`; the words and their
            derivation — there too, the fate — P/04); how it learns — the presence lock above
            (<events root>/.workers/<sub>/<instance>.lock, flock; the second pilot, N-1); unreadable → unknown (a word
            of the closed list of P/04: the controller waits for it), never «left»
```

The form of the content is the family `presence-lock` of P/05: [the schema](../../05-resource/data/presence-lock.schema.json),
[the outcomes](../../05-resource/data/presence-lock.outcomes.tsv); the instance is `{key, file}`, the text of the file with `x-encoding: json` at the root
([layers V7](../LAYERS.md) § 6); the column `schema` of the catalogue row names the family, the section of families is in the norms of P/05 (analysis of the review of stage B 6–7, № 44).

The race «the worker between open and flock, the resource deletes the file»: the worker opened the file, the resource takes flock without waiting, the comparison
matched — gone, the resource deletes the file and releases the lock; the blocking flock of the worker gets the lock on the deleted file,
its stat(path) is ENOENT, this is a mismatch: the worker closes and repeats from the start, a new file. The evidence is
by reading: a test with the worker stopped between open and flock (analysis of the review of stage B 3–5, № 19).

## Count `room`

```yaml
room:      the element room.<sub> of every subsystem of the catalogue whose role file roles/<sub>worker.env (the environment file contract «Environment variables») is on
           the box is written at every door mark — how many more role processes this server will raise (ADR-0084 item 2):
           decimal min(floor(HOST_MEMORY_MB / WORKER_MEMORY_MB) − live, 98 − live with a number n ≥ 2), not less than 0;
           live — the presence lock files of <sub> (presence_lock above) with a busy flock, by the instance files, not by
           the aggregate running, with empty or out-of-form content included (analysis of the review of stage B 3–5, № 23); the number — n of the name <prefix>-<server>-<n> from the content of the lock (the slot name contract «Role process name and its number»; n 2…99 — the ordered ones; B-25);
           there is no role file — there is no element; the role file does not parse, a role lock is unknown (the file does not read, analysis of the review of stage B 3–5, № 23) or the listing of the directory of the role locks is not obtained (C05-PRESENCE-SCAN-UNKNOWN-01) — "unknown"; the controller
           does not choose a server without a number in room.<sub> and itself subtracts the reserves of its orders
           (free(s); P/04 N3 «shortage(), order(), withdraw the order, shrink() — with grows: true»);
           a limit of the scheme: room of every role is counted from the whole memory of the server, a common ceiling is not divided among the roles
           (ADR-0084 addendum (1) R12)
number:    n of the name <prefix>-<server>-<n> — the canonical decimal ASCII notation without leading zeros; the range — as for the instances
           of the worker unit of P/02.4 N1.1: 1 — the base one, 2…99 — by order; n > 99 (and a non-canonical notation) — not a slot of this
           installation: the lock as without a number — it enters live, it does not enter «live with a number» and live, a log line (the vectors
           common/vectors/presence-room; guess of stage C PL-EXT-01, the Architect's decision of 2026-10-23)
live:      next to every room.<sub> — the element live.<sub>: the numbers n ≥ 2 of the live role locks by which room.<sub> is counted,
           decimal, separated by commas, ascending, without repetitions, from the same snapshot of the locks; a lock without a number (the name is not
           <prefix>-<server>-<n>, worker = "", the content is empty or out of form — analysis of the review of stage B 3–5, № 23) enters room, not the list; an empty list — ""; room.<sub> "unknown" — there is no live.<sub>;
           the controller does not choose a server without live.<sub> (free(s), P/04 N3 «shortage(), order(), withdraw the order, shrink() — with grows: true»; ADR-0084 addendum (3) R14′; analysis of the review
           of stage A 3–5, № 3, 19)
```

## Vectors

The package [`presence-room`](../vectors/presence-room/README.md) (the count `room`); the modes of the directories and files of the locks are the rows of `modes.tsv` of the package [`journal`](../vectors/journal/README.md) (together with the event journal). (ADR-0083 addendum (32) item 2)

## Correspondence to former lessons

From М10/8 N1.4 (stage B, analysis of the review of stage A 3–5, № 9): `presence_lock` whole and `room` (at P/05 N1.4 `room` is
a reference here); from М10/11 N1.4 — `presence`. Part of the norm М10/8-10 (the lock and the count `room`; P/05-07) — by `note` of
[id-map](../id-map.tsv); the worker's side (step 2b «start()» of М10/5) — chapter P/03.2, a part of М10/5 by the id-map of lesson 3.
