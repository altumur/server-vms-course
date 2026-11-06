# Acceptance V/06.1 — the watch as a unit

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`06.1-detedge.norms.md`](../../spec/06.1-detedge.norms.md) N5. The stand and the vocabulary are in [the common VMS acceptance
README](../../../common/acceptance/README.md) over the common platform README (export `7a875c75`, the VMS pin).

## Preparation

The store and the cluster console; the manifests `VMS/01-cam/cam.subsystem.yaml`, `VMS/02-rec/rec.subsystem.yaml`,
`VMS/06-detedge/detedge.subsystem.yaml` are installed; the console — `CONSOLE_ROOT=detedge` (the door `/watches`), `rec` is mounted (`console2` —
the prefix `/rec`). The controller, the workers, the resource and the domain are not started. Requests — from loopback without a domain. The scenario runs on a clean
instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` | V/06.1-01, V/06.1-02 | a watch with the defaults of `alarms`, `start`, `keep`, `pre`/`post`/`join`; `start` and `keep` not from the list — 400; `cam` does not change; `rec` of another camera — 409 `must_match` |
