# The process instance contract: grammar and computation

This English text is the source; the Russian translation `ru/contracts/instance.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5), addendum (13): several processes write the process instance into the rows of the slot, the turn, the presence
lock and into event ids — a contract, not copies in chapters; layout audit А-06, the Architect's decision of
2026-10-25). The owner is chapter [P/03.2](../../03-worker/spec/03.2-worker.norms.md) (Н1.4 `holder`, Н3 «start()» step 2).
Participants: the worker (the slot, the contender mark, the heartbeat — P/03.2, P/03.4), the resource — the field `instance` of the presence lock
([P/05](../../05-resource/spec/05-resource.norms.md) Н1.4; [the presence lock contract](presence-lock.md)), the process `domain` —
`holder` of the row `domain/signer-turn` ([P/08.10](../../08-domain/spec/08.10-domain.norms.md) Н1.7), the writers of the event journal
(the instance in an event id — [the event journal contract](event-journal.md) «The event id and the writer instance»), the installer —
the variable `INSTANCE_ID` ([the environment file contract](env-file.md) «Environment variables»).

Moved from P/03.2 Н1.4 (`holder`: the grammar of the instance) and Н3 «start()» step 2 (the computation) without a change of behaviour;
P/03.2 and the readers refer here. The profile of the instance as a path component (forbidden characters, representability in file names)
stays in the event journal contract; what a process does on a refusal is with its lesson (the worker — P/03.2 Н3 «start()», Н4).

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The instance is a string in the fields `holder` of the slot row (`Platform/03-worker/data/slots.schema.json` (outcomes — `Platform/03-worker/data/slots.outcomes.tsv`)), `holder` of the turn row
of the process `domain` (`Platform/08-domain/data/signer-turn.schema.json` (outcomes — `Platform/08-domain/data/signer-turn.outcomes.tsv`)), `instance` of the worker heartbeat
(`Platform/03-worker/data/heartbeats.schema.json` (outcomes — `Platform/03-worker/data/heartbeats.outcomes.tsv`)), of the contender mark (`Platform/03-worker/data/contenders.schema.json` (outcomes — `Platform/03-worker/data/contenders.outcomes.tsv`)) and of the presence
lock (`Platform/05-resource/data/presence-lock.schema.json` (outcomes — `Platform/05-resource/data/presence-lock.outcomes.tsv`)); the outcomes are the `.outcomes.tsv` of the same families.

## Instance

```yaml
grammar:   instance: <box>:<pid>:<6 hex of randomness>; the box of the holder is the part up to the first «:»
forms:     two forms (INSTANCE54-02, the Architect's decision of 2026-10-25): computed — pid decimal without leading zeros, 6 hex lowercase; given by INSTANCE_ID —
           pid — ASCII digits, not all zeros, leading zeros are admissible, 6 hex — [0-9a-fA-F]{6}; anything else — a start refusal, code 2;
           the given one is used as given, byte for byte (the hex case and the zeros of pid are not normalized)
compare:   readers compare the instance by bytes (the slot, the heartbeat, the hold, the turn, the presence lock) (INSTANCE54-02, the Architect's decision of 2026-10-25)
compute:   instance = INSTANCE_ID of the environment (the environment file contract «Environment variables») if given; otherwise <box>:<pid>:<6 hex>; the box — BOX_ID |
           machine-id | hostname (the environment file contract «Environment variables»); both sources — by the instance grammar above and the instance profile
           of the event journal contract («The event id and the writer instance»), otherwise a start refusal
sources:   the order and the outcomes (INSTANCE130-SOURCES-01, the Architect's decision of 2026-10-25): INSTANCE_ID given and non-empty — the form «given» (forms above); empty — as not
           given; the box: BOX_ID non-empty — it, not by the box grammar — a start refusal, code 2 (what the operator gave is not
           substituted); empty — as not given → /etc/machine-id: the first line, trimming SP, TAB, CR, LF at both ends;
           no file, a read error, empty after trimming or not by the box grammar — the next source → the hostname
           of the system, the same trimming; empty or not by the grammar — a start refusal, code 2 «no box name»; which source was taken —
           by a line of the start journal (without the value of INSTANCE_ID)
box:       the box grammar — non-empty, without «:» and without what the instance profile of the event journal contract forbids
           (not `.`/`..`, without `/`, `\`, `|`, `"`, comma, Cc/Zl/Zp)
```

## Vectors

The package [`instance`](../vectors/instance/README.md): a given INSTANCE_ID — accepted as given or a start refusal (INSTANCE54-02, the Architect's decision of 2026-10-25);
`box.tsv` — the box resolver: INSTANCE_ID, BOX_ID, the content or an error of machine-id, hostname → the box and the source, or code 2
(INSTANCE130-SOURCES-01, the Architect's decision of 2026-10-25).
The computed form depends on the environment and the machine of the box — by reading and by acceptance scenarios of P/03.2 (two boxes — system
acceptance).

## Correspondence to former lessons

From P/03.2 Н1.4 (the comment of the field `holder`) and Н3 «start()» step 2 (the first phrase — the computation); they, P/05, P/08.10 and
P/02.4 refer here (layout audit А-06).
