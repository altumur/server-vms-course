# Acceptance V/04.4 — the detector on the stand

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`04.4-det.norms.md`](../../../spec/04.4-det.norms.md) Н5 (and of chapters 2, 3). The stand and the vocabulary are in [the common VMS
acceptance README](../../../../common/acceptance/README.md) on top of the common platform README (export `7a875c75`, the VMS pin).

## Preparation

The store, the cluster console, the controllers `cam` and `det`, the resource `srv-a`; the manifests `VMS/01-cam/cam.subsystem.yaml`,
`VMS/04-det/det.subsystem.yaml`, `VMS/07-auto/auto.subsystem.yaml` are installed; the console — `CONSOLE_ROOT=det` (the doors `/units`, `/events`),
`cam` is mounted (`console2` — the prefix `/cam`). The camera holder and the detection worker are on `srv-a` (`@start worker`); the server
labels are not set — the scenario's detectors have no labels (`labels: []`). The camera is the stand file `door.mp4`. The subsystem file of `cam` is
set by the stand through `W2C_SUB_ENV` (the common VMS acceptance README): `MEDIA_DIR` with `door.mp4`, `SHM_DIR` — a stand directory (the frame
share, V/01.2 Н1.3), therefore the detector on the holder's server goes through the share (`via: shm`). The scenario runs on a clean instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-detect` | V/04.2-02, V/04.2-03, V/04.3-01, V/04.3-02, V/04.4-01 | the teaching model `tick` — `running` through the share; its rows are alarms (`alarms: [tick]`) with `of` of the camera in `/events`: the two oldest (`keep=oldest&limit=2`, the contract `events-merge`) — `pass` 3 and 6 (the log grows, the wait holds the length); a detector of a nonexistent camera — `waiting` with a reason; an unknown kind — `unsupported` |
