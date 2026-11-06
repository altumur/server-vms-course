# V/09 Deploying VMS

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: translated. The platform export pin is `cammeta-specs` `7a875c75`.

## What lesson V/09 is

How VMS is installed on a platform cluster. The installation mechanism — users and groups, the units of workers and parts, the shares, the
environment files, the order of `manifest put`, the upgrade server by server — belongs to the platform (P/02.3, P/02.4) and is not retold in the lesson.
The lesson sets norms for what the platform does not know: what lies in the VMS installation source, which values VMS puts into the files
that the platform only reads, what the operator does after installation, what the package is built from and by which numbers one sees that
VMS is running.

## Chapters

| Chapter | What it norms | Platform and lessons |
|---|---|---|
| V/09.1 | The installation source and the order: nine manifests (`cam`, `rec`, `live`, `det`, `detjob`, `detedge`, `auto`, `assist`; `backend` — with the V/11 generation), the shells — the files `<sub>.shell.html` next to the manifest (the field `shell`: the root `cam`, `backend`); the executables `worker.exec` (`/usr/lib/<sub>/worker`) and the part `rec` (`parts.obsd.exec`); `W2C_DEPLOYMENT=vms`, `CONSOLE_ROOT=cam`; the order of `manifest put`; after installation the operator mounts the volumes of the part `obsd`, the server volume is declared by the row `rec/volumes/<name>`; the vendor key (V/01.7) | P/02.3 Installation source; P/02.4 N1.1, N1.7; V/01.1, V/01.7, V/02.2, V/02.6 |
| V/09.2 | The environment: a summary of the keys of the subsystem files `/etc/<sub>/<sub>.env` by lessons 01–07, 10, 11 (key, default, owner lesson — for reference, the norms are at the owners); the site lines of `w2c.env` that VMS reads (`LABELS`, `CONSOLE_ORIGINS`, `SERVER_NAME`); the role files `roles/<role>.env` — `CAPACITY` by `B + n·I` and `WORKER_MEMORY_MB` from `capacity` of the manifests, a sample of values for a role | P/02.4 N1.2, N1.5; P/03.4 N1.2; the contract `env-file`; V/01.2, V/02.2–V/02.8, V/03.3, V/03.6, V/05.4, V/07.2 |
| V/09.3 | The package: one for all servers and all kinds of clusters (server, camera, domain) — the difference is by a property of the server (labels) and by the set of enabled units, not by a fork; the composition — the VMS executables and the media library from system packages, a build without downloads from the network; `obsd` with patches 01–07 is the executable file of the part; delivery by push and by pull — what is visible and what is not; the licences of the dependencies — the implementation names them and says in one sentence what each requires | P/02.4 N1.7, N1.10, N1.12; V/02.2, V/03.4 |
| V/09.4 | The health check: `console.running` of each subsystem (`cam_cameras_running`, `rec_recordings_running`, `live_streams_live`, `det_units_running`, `detjob_jobs_running`, `detedge_watches_running`, `auto_scenarios_running`, `assist_models_running`, `backend_instances_running`) at `/<sub>/metrics`; «the archive is growing» — the numbers of the recorder (`rec_last_frame_age_seconds`, `rec_writer{state}`, `rec_archive_failure{kind}`, `rec_archive_away_seconds`, `rec_volume_error`) | P/06.5 N1.2, N3 `/metrics`; V/02.4 N1.8 |
