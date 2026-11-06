# Acceptance V/05.1 — the job as a unit

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`05.1-detjob.norms.md`](../../spec/05.1-detjob.norms.md) N5. The stand and the vocabulary are in [the common VMS acceptance
README](../../../common/acceptance/README.md) over the common platform README (export `7a875c75`).

## Preparation

The store and the cluster console; the manifests `VMS/01-cam/cam.subsystem.yaml`, `VMS/02-rec/rec.subsystem.yaml`
(an orderer of `detjob` rows), `VMS/04-det/det.subsystem.yaml`, `VMS/05-detjob/detjob.subsystem.yaml`,
`VMS/07-auto/auto.subsystem.yaml` are installed; the console — `CONSOLE_ROOT=detjob` (the door `/jobs`), `rec` is mounted (`console2` — the prefix
`/rec`). The controller, the workers, the resource and the domain are not started. Requests — from loopback without a domain (one identity with full rights).
The scenario runs on a clean instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` | V/05.1-01, V/05.1-02 | a job with the defaults of `labels`, `alarms`, without `state` and `ended`; a recording of another camera — 409 `must_match`; `rec` does not change; the orderers' names `rec-…`, `auto-…` — 400. `mask_of` (a detector of another camera — 409 `must_match`) — by reading: there is no `det` door on the stand |
