# Acceptance V/10.2 — the model door

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`10.2-assist.norms.md`](../../spec/10.2-assist.norms.md) Н5 (and the model process, the heartbeat — [`10.1-assist.norms.md`](../../spec/10.1-assist.norms.md)
Н1.3, Н1.4). The stand and the vocabulary are [the common VMS acceptance README](../../../common/acceptance/README.md) over the common
platform README (export `7a875c75`).

## Preparation

A VMS stand with the manifest `assist`: the console — `CONSOLE_ROOT=assist` (the door `console` — `/models`, `/where/<name>`), the controller
`assist`, the resource of the server `srv-a`. The model holder is started by the directive `@start worker assist m-srv-a-1 on srv-a
labels=assist-a` with the implementation's «Стенд» command (the section «Решает реализация» of the lesson's instructions): the server has the label `assist-a`.

**The model stub.** The stand writes the subsystem file of `assist` per scenario (the common VMS acceptance README, «Файл подсистемы на стенде»)
before the holder starts: `MODEL_COMMAND={model_stub} {spec}/VMS/10-assist/vectors/model-stub/<сценарий>.tsv` —
the answers file by the scenario name. `{model_stub}` is the runner program `model-stub` by the protocol of V/10.2 Н5, `{spec}` is the root
of the specification; the files — [`vectors/model-stub/`](../../vectors/model-stub/README.md). Transitional states are held by barriers
of the answers file, not by the speed of the stand: `loading` — `load hang` (`01-loading`); `queued` of the second step — after the observed
`running` of the first one, which is held by `hang` (`03-limits`). There are no weights and no model server on the stand.

The scenario `04-owner` is on the VMS domain stand (the common VMS acceptance README, «Стенд домена VMS»): `@domain m1`, on `m1` — the same
stand; `member m1 console` — the root `assist`; people and grants — the doors `holder` and the directive `@person`. Ann and Bob both have
`view` on the model row of `m1`.

Each scenario — on a clean instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-loading` | V/10.1-03, V/10.1-04, V/10.2-03 | the model does not load (`load hang`): the phase `loading`, a step — 503 `loading` with `retry_after`, the phase stays `loading` |
| `02-step` | V/10.1-03, V/10.1-04, V/10.2-01, V/10.2-03, V/10.2-04, V/10.2-06, V/10.2-08 | `running`; without a token — 403; empty `messages` and `content: null` — 400 `bad step`; a step 202 → a long poll → `done` with a message, `usage`, `seconds`; a repeated read of a finished one — the same outcome; a step on which the stub «thinks forever» — an observed `running`, a cancellation 200 `cancelled`, then 404; a model answer 500 — `failed` `model failed`; a step with the history «a request → the model's message as it is (`content: null`, `reasoning_content`, `tool_calls`) → the tool result» and `turn` — 202 and `done`; a foreign instance in the step id — 410 `gone`; `enabled: false` — `stopped` `disabled`, a step — 503 `model unavailable`; a broken `wait` at a foreign instance — 400 `bad step` before 410 (two errors at once); the segment `step` with `%3A` is decoded: an own id with `%3A` — 404 `no such step`, not 410: the segment is decoded |
| `03-limits` | V/10.2-03, V/10.2-04, V/10.1-03, V/10.1-04 | the first step is observed `running`; the second — in the queue (`ahead: 0`); the third — 429 `too many steps`; a cancellation removes the second; the first, which the owner does not ask about, after `ABANDON` — `cancelled` `abandoned`, the counts `steps.cancelled` (cancellation) and `steps.abandoned` in the heartbeat; a step longer than 30 s with `/health` 503 during the step (`busy`) does not restart the model (`running`) |
| `04-owner` | V/10.2-02 | Ann submits a step; Bob with the same grant on the model reads it and hangs it up by id — 404 `no such step`; Ann (after waiting for her `/session`) reads her step with a new token — `done` with the answer; a step finished and not delivered lives `KEEP_UNREAD` 120 s, the scenario fits into two waits for `/session` of 30 s each |

By reading (Н5 of the norms): `Connection: close`, `STEP_MAX`, `QUEUE_MAX`, `KEEP_UNREAD` (timeouts longer than the scenario), `context exceeded`, a restart of the model
process, `model did not load`, `model keeps failing`, 410 after a change of holder, the division of the cache (a shared prefix; data — the same `user` and `turn`), the log `assist.step`
without texts, shutting down the model process before giving up the slot, socket 0700.
