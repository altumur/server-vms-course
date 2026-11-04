# Acceptance V/03.1 — the delivery as a unit by demand

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`03.1-live.norms.md`](../../../spec/03.1-live.norms.md) Н5. The stand and the vocabulary are in [the common VMS acceptance
README](../../../../common/acceptance/README.md) on top of the common platform README (export `7a875c75`).

## Preparation

The store and the cluster console; the manifests `VMS/01-cam/cam.subsystem.yaml` and `VMS/03-live/live.subsystem.yaml` are installed;
the console — `CONSOLE_ROOT=live` (the door `/streams`), `cam` is mounted (`console2` — the prefix `/cam`). The controller, the workers,
the resource and the domain are not started. Requests — from loopback without a domain (one identity with full rights). A scenario runs on a clean
instance.

The scenario `02-two-viewers` runs on the VMS domain stand ([the common VMS acceptance README](../../../../common/acceptance/README.md), «Стенд домена VMS»):
`@domain m1`, on `m1` — the same manifests, `member m1 console` — the root `live`, `member m1 console2` — `/cam`;
people and grants — the doors `holder` and the directive `@person` of the common platform README. Ann sees only the camera `$a`, Bob — only
`$b`. The stream choice at the gateway door (`?stream=`, `?width=&height=`, V/03.3 Н1.2) — [acceptance 3](../../3/README.md): there is no gateway on this stand.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` | V/03.1-01, V/03.1-02 | a delivery of a camera with the default `grace` 60; the second viewer — 409 `exists`; `cam` does not change — 400; a delivery of a camera without a row — is created; without `cam` — 400; the row has no field `stream` — 400 (the stream is at the gateway door); `grace` 5 and 3601 — 400 (the bounds 10–3600) |
| `02-two-viewers` | V/03.1-01, V/03.1-02 | the domain stand, two people with `view` each on their own camera: a delivery of a foreign camera — 403, of one's own — 201; `PUT` of one's own delivery with only `view` — 403 (editing is not viewing); an already created foreign one — also 403, not 409 (the right comes before `exists`) |
