# Acceptance V/01.4 — commands and questions to the device

This English text is the source; the Russian translation `ru/acceptance/4/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`01.4-cam.norms.md`](../../spec/01.4-cam.norms.md) Н5. The stand and the vocabulary are as in [acceptance 2](../2/README.md)
(the common platform acceptance README, export `7a875c75`).
The run — after the first stage C generation that has passed the platform acceptance (ADR-0090 addenda (8), (9)).

| Scenario | Norm | What it observes |
|---|---|---|
| `01-no-device` steps 1–4, 6 | V/01.4-01, -02 | a command to a file camera (there is no device): the request is submitted with a live holder within the timeout of 30 s — the submission is `202 queued` or `200 answered` (whichever comes first; P/06.4 Н3 «подать просьбу» step 5); the holder executes the request — the label `refused` «`camera has no device`» and the camera's event `command.failed` (V/01.4 Н1.5) |
| `01-no-device` steps 5, 6 | V/01.4-02 | two errors at once — a camera without a device and `output` without `port`: by the order of Н3, «камера без устройства» comes before the arguments — the label `refused` «`camera has no device`», not «output needs a port»; there are two `command.failed` events |
| `01-no-device` step 7 | V/01.4-01 | an argument longer than 32 characters — 400 at the door (the schema of the section `requests:`) |

| `02-owner` | V/01.4-05, -08 | `@manual`: the block owner, the index, `videos`, `can` as lists, removal of a setting by the current row, a repeat of the list |
| `03-norm` | V/01.4-08 | `@manual`: `value` from `norm`, a disabled input, an `unlicensed` owner |
| `04-sound` | V/01.2, V/01.4 sound | `@manual`: the sound points, 404, a talk: `talk`, `busy`, release of busyness: `Drivers/Virtual` under the current DriverPack is usable only after `ipintd` (ADR-0102 addendum (9) items 8, 9) |
| `04-units` | V/01.4-09 | `@manual`: the tree of units, `units_down`, the event and the action `unit` |
| `05-builtin` | V/01.4-11 | `@manual`: the built-in detector, refusals, work without a stream: the stub driver has no analytics |
| `05-ptz` | V/01.4-12 | `@manual`: the lease, a stop out of turn, a stop on taking the epoch, the limit of 105 s: the stub driver has no telemetry |
| `06-rule-state` | V/01.4-13, V/01.1-15 | the rule words on a file camera: no row before a word, `arm`, `disarm` without a new `revision`, `disable` with `pending`, `reason` «rule: off», a refusal of other requests, an edit of the camera does not remove the word, a deadline in the past enables, the operator does not write the row; `@manual` — the expiry of the deadline, a new holder, a corrupted row |

`performed` with an answer, questions to a slow device, the device row, a match of `identity`, `can`, the device's children — by reading: a
device double with outputs and presets is needed, the stand has none (V/01.4 Н5). The `@manual` steps wait for a model of the stub driver with several videos
and blocks with a channel, with `-1`, without the field: `Drivers/Virtual` has none.
