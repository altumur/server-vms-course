# V/09 Deploying VMS

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/09.1–V/09.4 (2026-10-23; review 2026-10-29); the plan below is the history of the translation. Sources:
the inventory [`../common/inventory.md`](../../common/inventory.md) § 1, § 2 (М10B/17 steps 5–8, 10 — what did not go into P/02.4; М10B/28
step 1 — the values of `CAPACITY`; М12A/05 steps 1, 2, 5). The platform: the export `cammeta-specs` `7a875c75`. The lesson has no subsystem
and no manifest of its own.

## What lesson V/09 is

How VMS is installed on a platform cluster. The installation mechanism — users and groups, the units of workers and parts, the shares, the
environment files, the order of `manifest put`, the upgrade server by server — belongs to the platform (P/02.3, P/02.4) and is not retold in the lesson.
The lesson sets norms for what the platform does not know: what lies in the VMS installation source, which values VMS puts into the files
that the platform only reads, what the operator does after installation, what the package is built from and by which numbers one sees that
VMS is running.

## Chapters

| Chapter | What it norms | Former steps | Platform and lessons |
|---|---|---|---|
| V/09.1 | The installation source and the order: nine manifests (`cam`, `rec`, `live`, `det`, `detjob`, `detedge`, `auto`, `assist`; `backend` — with the V/11 generation), the shells — the files `<sub>.shell.html` next to the manifest (the field `shell`: the root `cam`, `backend`); the executables `worker.exec` (`/usr/lib/<sub>/worker`) and the part `rec` (`parts.obsd.exec`); `W2C_DEPLOYMENT=vms`, `CONSOLE_ROOT=cam`; the order of `manifest put`; after installation the operator mounts the volumes of the part `obsd`, the server volume is declared by the row `rec/volumes/<имя>`; the vendor key (V/01.7) | М10B/17 steps 5, 8 (the layout, an own volume) | P/02.3 «Установочный источник»; P/02.4 Н1.1, Н1.7; V/01.1, V/01.7, V/02.2, V/02.6 |
| V/09.2 | The environment: a summary of the keys of the subsystem files `/etc/<sub>/<sub>.env` by lessons 01–07, 10, 11 (key, default, owner lesson — for reference, the norms are at the owners); the site lines of `w2c.env` that VMS reads (`LABELS`, `CONSOLE_ORIGINS`, `SERVER_NAME`); the role files `roles/<роль>.env` — `CAPACITY` by `B + n·I` and `WORKER_MEMORY_MB` from `capacity` of the manifests, a sample of values for a role | М10B/17 step 8; М10B/28 step 1 | P/02.4 Н1.2, Н1.5; P/03.4 Н1.2; the contract `env-file`; V/01.2, V/02.2–V/02.8, V/03.3, V/03.6, V/05.4, V/07.2 |
| V/09.3 | The package: one for all servers and all kinds of clusters (server, camera, domain) — the difference is by a property of the server (labels) and by the set of enabled units, not by a fork; the composition — the VMS executables and the media library from system packages, a build without downloads from the network; `obsd` with patches 01–07 is the executable file of the part; delivery by push and by pull — what is visible and what is not; the licences of the dependencies — the implementation names them and says in one sentence what each requires | М10B/17 steps 5, 7; М12A/05 steps 1, 2, 5 | P/02.4 Н1.7, Н1.10, Н1.12; V/02.2, V/03.4 |
| V/09.4 | The health check: `console.running` of each subsystem (`cam_cameras_running`, `rec_recordings_running`, `live_streams_live`, `det_units_running`, `detjob_jobs_running`, `detedge_watches_running`, `auto_scenarios_running`, `assist_models_running`, `backend_instances_running`) at `/<sub>/metrics`; «the archive is growing» — the numbers of the recorder (`rec_last_frame_age_seconds`, `rec_writer{state}`, `rec_archive_failure{kind}`, `rec_archive_away_seconds`, `rec_volume_error`) | М10B/17 step 10 | P/06.5 Н1.2, Н3 `/metrics`; V/02.4 Н1.8 |

## Decisions for the plan

1. **A lesson with chapters and no subsystem** (like V/11): there is no door and no manifest of its own; the registry lines `V/09 no-openapi`,
   `V/09 no-acceptance` — by an inquiry with chapter V/09.1. The check is by reading and by installation on the stand (the stand is the implementation's).
2. **Normative is what the platform does not know:** the composition of the source, the values, the operator's steps after installation, the health numbers.
   The mechanism is by reference to P/02.3, P/02.4. The summary table of keys of V/09.2 is for reference: the value and the default are set by the
   owner lesson; where the owner lesson did not name the file (`PLAYBACK_HOST`, `ARCHIVE_HOST`, `BACKFILL_BUDGET`, `BACKFILL_WINDOW`), it is
   an edit of the owner lesson (the subsystem file) in the commit of V/09.2.
3. **`W2C_DEPLOYMENT=vms`.** The engine of the part `rec` listens on the socket `OBSD_SOCKET` (the default `/run/vms-rec-obsd/obsd.sock`; it is passed by
   the wrapper `parts.obsd.exec`, V/02.2 Н1.1), and the share directory is
   `/run/<dep>-rec-obsd` (P/02.4 Н1.1); the default of `OBSD_CLIENT_GROUP` is `vms-rec-obsd` (V/02.2). The VMS installation sets the OS name base
   `vms`; with another base the keys of the files will not match the share (the lesson's line: «the base is `vms`, otherwise fix the
   keys»). The norm P/02.3 cannot substitute `<dep>` into `exec` — no inquiry is needed while there is one base.
4. **The installation order is by the norm:** `near` is not an edge of the order (ADR-0091 addendum (26)), the installation is one pass (V/09.1 Н1.3);
   the former inquiry «installation order» is closed by this.
5. **The server volume is a table row, not a variable.** An own volume without a row (`ARCHIVE_VOLUME`, `ARCHIVE_QUOTA_BYTES`, `OWN_VOLUME`)
   is removed in V/02.4 (places only from `volumes`). After installation the operator mounts the volume of the part (`/data/platform/subsystems/rec/obsd/
   volumes/<n>`, the owner is the user of the part; the installer does not mount, P/02.4 Н1.1) and declares `rec/volumes/<имя>` (`kind:
   local`, `server`, `url: file:///data/platform/subsystems/rec/obsd/volumes/<n>`, `quota_bytes`) through the console door or the page
   (V/11.18); without a row the recorder writes nowhere — this is visible (`/rec/unplaceable`).
6. **The vendor key (V/01.7)** is a file of the settings directory of `cam`: `/etc/cam/vendor.pem` (0640 `root:vms-cam`, P/02.4 Н1.1 — other
   files of the subsystem directory); the package puts it, the operator does not edit it; the lesson names the path, М14 sets the signature form.
7. **The `CAPACITY` values by role** are a rule and an example, not a table of numbers: with `unit_mb` in `capacity` of the role's manifest —
   `min(⌊(WORKER_MEMORY_MB − base_mb) / unit_mb⌋, предел нагрузки)`; without `unit_mb` (`det`, `detjob`, `detedge`) — the load
   limit that the implementation names, the role file of the package is the `default` of the manifest (8, 2, 2); the example is a budget of 460 MB for `camworker`.
8. **Remove:** the Quadlet units, `Containerfile`, `vms.env` as one file and `/etc/vms` — a reference (the subsystem files and `/etc/<sub>`,
   P/02.4 Н1.1, Н1.2), the entry point verbs (`worker.exec`), `jobs`, `domainpart`, the spares (P/02.4 Н1.5 — workers on order),
   `SPOOL`, `SEGMENT_SECONDS`, the check of units by a regular expression (the units belong to the platform).

## Inquiries of the lesson

There are no inquiries; the registry lines `V/09 no-openapi`, `V/09 no-acceptance` — with chapter V/09.1.

## Differences from the witness that the lesson records

There are no containers — the units and the runner of the platform (P/02.4); the environment files are per subsystem, not `vms.env`; an own volume is a row of
`volumes`, not a variable; the OS name base is `vms` (`W2C_DEPLOYMENT`); the order of `manifest put` is the norm P/02.4 Н1.7 (the witness
had no order).

## Order of work

Chapter by chapter, a commit per chapter: V/09.1 → V/09.2 → V/09.3 → V/09.4. The lecture `09-deploy.md` and the instructions
`spec/09-deploy.README.md` — with the first chapter. `lessons.tsv` — `переведён` after the last chapter.
