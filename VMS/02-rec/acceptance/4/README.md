# Acceptance V/02.4 — the recorder

This English text is the source; the Russian translation `ru/acceptance/4/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`02.4-rec.norms.md`](../../spec/02.4-rec.norms.md) N5. The stand and the directives are in [the common VMS acceptance
README](../../../common/acceptance/README.md) (export `7a875c75`).

## Preparation

A VMS stand with the manifests `cam` and `rec`: the console — `CONSOLE_ROOT=rec` (the door `console` — `/recordings`, `/volumes`),
`cam` is mounted (`console2` — `/cam/…`); the controllers `cam` and `rec`, the resource `srv-a`. The part `obsd` is started on `srv-a`
(the engine of V/02.2 N1.4: ObjectStorage with patches 01–07); the mount point `{data}/subsystems/rec/obsd/volumes/1` is a directory
of the part's user. The camera holder and the recorder — `@start worker` with the Stand command of the implementations `cam` and `rec`. The media —
`door.mp4` (the common VMS README). Each scenario runs on a clean instance.

| Steps of `01-record` | Norm | What it observes |
|---|---|---|
| 1–6 | V/02.4-01, -03, -08 | the recording of a camera onto a volume of its own server goes on: `running`, the source is shared memory (the holder is on the same server) |
| 7 | V/02.4-03, -08 | the recorder holds the volume `disk-a` (a place), the writer watchdog is `ok` |
| 8–9 | V/02.4-08 | a disabled recording — `pending` |

The scenario `02-audio` is `@manual`: the stand has no live driver with sound (ADR-0102 addendum (9) item 9).

| Scenario | Norm | What it observes |
|---|---|---|
| `03-backup-always` | V/02.6-10 | a recording on a `backup` volume without `when` — `waiting` with a word; `when: offline` — `standby` |
| `04-replica` | V/02.6-11 | `replica` from the archive: the phase, there are no fields of the live stream; a cycle — `waiting` at both, removed — both go on; no source; the source on a `backup`; `@manual` — a copy within 900 s, the ring, a change of the source, a label: the stand can neither wait for nor outrun the ring |
| `05-replica-device` | V/02.6-11, V/02.8-05 | `@manual`: the stand has no device archive |
| `06-edge` | V/02.6-12, V/01.6-08 | one row of an `edge` volume: the holder of each camera orders `cam-<cam>-<volume>`, `home`, `when` — the default `offline`; one removed by the operator — again; `@manual` — two cameras on the card, eviction, the budget, the guard, `when` of the volume, the end of the row, the deadline of 7200 s, the default `when` of a cluster of one, a claim to the recorder of the card, `role`: the stand has no card |
| `07-segment-lost` | V/02.3-08 | `@manual`: the loss event, the fields, collapsing: the stand cannot make the engine lose a sequence |

The scenarios `03`, `04`, `05`, `06` run on their own instances. In `04-replica` there are two volumes: the stand starts the second recorder itself, there is no order (`grows`) on the stand; the volume `bk-a` has no holder, its kind is read from the row.

Volume refusals, leaving a volume, stopping within the budget, the watchdog on getting stuck, the backup ring — by reading (N5 of the norms).
