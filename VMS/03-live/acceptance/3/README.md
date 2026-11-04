# Acceptance V/03.3 — the WHEP door: the stream choice by size

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`03.3-live.norms.md`](../../spec/03.3-live.norms.md) Н5. The stand and the vocabulary are in [the common VMS acceptance
README](../../../common/acceptance/README.md) on top of the common platform README (export `7a875c75`).

All steps are `@manual`: they need a worker `live` with a holder of two streams of different sizes, a live driver with sound and a WebRTC client; the stand has none of them.
Preparation: a camera and its other stream, 1920×1080 and 640×360, both `running`, the codec is `codec` of the heartbeat; the size of the main one is `resolution` of the row, of the other one — `size` of the heartbeat.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-size` | V/03.3-02 | `@manual`: a window smaller than the small stream and one between the streams — the smallest one not smaller than the window; a window larger than all — the largest one; the size is not known, a camera of another cluster — the main one; `stream` outranks the size; the stream's codec is absent from the offer — the stream is filtered out; the demand is rejected — the stream is filtered out; `width` without `height` — 400 |
| `02-sound` | V/03.4 sound | `@manual`: the codec of the branch, one `msid`, the note, sound through the receiver |
| `03-talk` | V/03.3 talk | `@manual`: `talk`, `not yet`, `busy`, `no speaker`, hang-up, `why: device` |
