# Acceptance V/01.3 — the source `driverpack://file`

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`01.3-cam.norms.md`](../../spec/01.3-cam.norms.md) Н5. The stand and the directives are in [the common VMS acceptance
README](../../../common/acceptance/README.md) (export `7a875c75`). The run — after the first stage C generation that has passed the platform
acceptance (ADR-0090 addenda (8), (9)).

| Steps of `01-bad-name` | Norm | What it observes |
|---|---|---|
| 1–3 | V/01.3-01, -03 | the door accepts a name of two segments (`driverpack://file` has no host — V/01.1), the holder refuses by the rule of V/01.2 Н3 (the address is not read): the phase `pending`, `device_state: refused`, `reason` «bad media name …», no stream |

A stream from a file — acceptance 2 (`running`); the pace, the loop and the monotonicity of the timestamps — by reading (an hour-long run of the implementation).
