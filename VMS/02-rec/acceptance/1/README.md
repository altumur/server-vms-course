# Acceptance V/02.1 — the recording as a unit

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`02.1-rec.norms.md`](../../../spec/02.1-rec.norms.md) Н5. The stand and the vocabulary are in [the common VMS acceptance
README](../../../../common/acceptance/README.md) over the common platform README (export `7a875c75`).

## Preparation

The store and the cluster console; the manifests `VMS/01-cam/cam.subsystem.yaml`, `VMS/02-rec/rec.subsystem.yaml` and `VMS/07-auto/auto.subsystem.yaml` are installed;
the console — `CONSOLE_ROOT=rec` (the doors `/recordings`, `/volumes`, `/keeps`), `cam` is mounted (`console2` — `/cam/…`). The controller, the workers, the resource and the
domain are not started. Requests — from loopback without a domain (one identity with full rights). The scenarios run sequentially on one
instance with empty `rec/` and `cam/` data after the installation; scenarios 02, 03 rely on the volume `disk-a` of scenario 01.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` | V/02.1-01 | a `local` volume and a recording with defaults; without `cam` — 400; `retention_days` 0 — 400 |
| `02-fixed` | V/02.1-01 | `cam` does not change — 400 «cam is fixed»; the names `auto-…`, `cam-…` belong to the orderers `auto`, `cam` |
| `03-home` | V/02.1-02 | a home on the card — accepted by the door (a recording of a camera of a foreign server is not written by the recorder of the card, V/02.6 Н1.7 — by reading); no volume — accepted (there is no home, P/04 Н1.3) |
| `04-volumes` | V/02.1-03 | the table schema by kind: `network` with `server`, `incidents` without `admits: false`, `when` on a non-`edge`, `edge` without `server`, with the field `cam`, `when` outside the list — 400; `when` on an `edge`, without it there is no field |
| `05-stream` | V/02.1-01 | the recording stream `stream`: a stream of its own camera — accepted; a stream of another camera and the id of the camera itself — 409 `must_match`; a change to empty (the main one) — accepted |
| `06-audio` | V/02.1-01 | the recording microphone `audio`: the default 0 — the first `mic` of the camera, it is editable, less than 0 — 400 |
| `07-replica` | V/02.1-08 | the door does not judge `replica_from` and `when` on a `backup`: a cycle and `always` on a backup volume are accepted, the truth is at the recorder (acceptance 4) |
