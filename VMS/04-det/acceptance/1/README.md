# Acceptance V/04.1 — the detector as a unit

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`04.1-det.norms.md`](../../spec/04.1-det.norms.md) N5. The stand and the vocabulary are in [the common VMS acceptance
README](../../../common/acceptance/README.md) on top of the common platform README (export `7a875c75`, the VMS pin; the form `@raw` of a body is from its
vocabulary).

## Preparation

The store and the cluster console; the manifests `VMS/01-cam/cam.subsystem.yaml`, `VMS/04-det/det.subsystem.yaml` and
`VMS/07-auto/auto.subsystem.yaml` (the orderer of `det` rows) are installed; the console — `CONSOLE_ROOT=det` (the door `/units`), `cam` is mounted
(`console2` — the prefix `/cam`). The controller,
the workers and the domain are not started; the resource is started by the first step: the console reads heartbeats and bodies through the resource of its own server. Requests — from loopback without a domain (one identity with full rights). The scenarios run
sequentially on one instance; scenario 02 relies on the detector of scenario 01.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` | V/04.1-01, V/04.1-02 | the defaults `labels`, `alarms`, `until`; without `kind` — 400; `cam` does not change; the orderer's name `auto-…` — 400 |
| `02-mask` | V/04.1-01 | a mask that is not a digest — 400; the mask body — a digest in the row, `revision` grows |
| `03-stream` | V/04.1-01 | the detector's stream `stream`: a stream of its own camera — 201; a stream of another camera and the id of the camera itself — 409 `must_match`; a change to empty (the main one) and back — 200 |
| `04-mask-of` | V/04.1-01 | the door checks `mask_of` of an operator's row (without `made`): a detector of the same camera — 201; a detector of another camera — 409 `must_match`; a nonexistent id — 201 (`ref` does not require the target, the vector `ref_no_target` of the row check contract); the worker does not read such a reference — by reading |
