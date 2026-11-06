# Acceptance V/01.2 — the camera holder

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`01.2-cam.norms.md`](../../spec/01.2-cam.norms.md) N5. The dictionary of directives, doors and expectations is in the common
[platform acceptance README](../../../../Platform/common/acceptance/README.md#dictionary-of-directives-and-doors) (export `7a875c75`);
the format of `scenarios.tsv` is the same. The run — after the first stage C generation that has passed the platform acceptance (ADR-0090 addenda (8),
(9)); until then the scenarios are norm text.

## Preparation

The stand per the section Stand of the common README: the store, the cluster console (`CONSOLE_ROOT=cam`, the door `console` — `/cameras`),
the controller `cam`, the server resource `srv-a`; the manifests `VMS/01-cam/cam.subsystem.yaml` and `VMS/02-rec/rec.subsystem.yaml` are installed (`console2` — `/rec/…`: a recording row is a consumer of the stream, there is no recorder). The implementation
of the subsystem `cam`: its holder is started by the directive `@start worker cam <name> on srv-a` with the Stand command of the implementation
(the section Implementation decides of the lesson's instructions). The subsystem file `/etc/cam/cam.env` is set by the stand (the common VMS acceptance
README, «Subsystem file on the stand»; the path is in `W2C_SUB_ENV`): `MEDIA_DIR={data}/subsystems/cam/media` is the stand directory with
`door.mp4` (H.264, ≥ 10 s; the source `driverpack://file/door.mp4`, chapter 3), `SHM_DIR` is the stand's frame share directory
(`{shm}`, «Frame share on the stand»); `RTSP_PORT` is not set — RTSP on loopback, the port is chosen by the OS. One scenario
`01-hold` on one instance: it creates the camera `$c1`, edits it step by step and creates the row `$c2`. A repeated and a parallel run — their own instances.

## Scenarios

| Scenario | Norm | What it observes |
|---|---|---|
| `01-hold` steps 1–3 | V/01.2-13 | an enabled camera `always` without a consumer — `idle`, no addresses |
| `01-hold` steps 4–5 | V/01.2-01, -03, -04, -13 | a recording row is a consumer: `running`, `live_url` on loopback, `live_shm` in the stand's share directory (`shm://{shm}/…`) |
| `01-hold` steps 6–9 | V/01.2-01, -04 | a disabled one — `pending`, no addresses; enabled again — `running` |
| `01-hold` steps 10–11 | V/01.2-01, -04 | `live: on-demand` with a recording row — the consumer holds the stream: `running` (ADR-0103 addendum (7) item 3, (8) item 2) |
| `01-hold` steps 12–13 | V/01.2-01, -04 | the row `type: ipsrv` — the phase `held`, without delivery addresses (`live` is not read) |
| `01-hold` steps 14–17 | V/01.2-10 | `resolution` did not match `size` while `running` — `warning`, the stream goes on; the field removed — no warning |
| `01-hold` steps 18–19 | V/01.2-13 | the consumer removed — after `IDLE_AFTER` and the list of rows, `idle`, no addresses, `size` remained |
| `01-hold` steps 20–21 | V/01.2-01, -04 | `live: on-demand` without a consumer — `held`, no delivery addresses |
| `02-settings` | V/01.2-10 | `@manual`, a live driver: passing `resolution`, `fps`, a refusal of one setting in the address and in the field |
| `04-events` | V/01.2-11 | `@manual`: a text source, `text`, `word`, a busy port, `lost` |

The rest of the chapter — by reading (N5 of the norms): one connection for the subscribers and the loss of frames by a slow branch, 8 s of silence and
`silent`, `busy` of a second spelling, the password outside the command line, the budget. Delivery from the subscriber's side is observed by the acceptances
V/02 (the recorder) and V/03 (the gateway).
