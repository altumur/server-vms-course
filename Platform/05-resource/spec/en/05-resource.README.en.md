# P/05 — instructions for an implementation

This English text is the source; the Russian [`05-resource.README.md`](../05-resource.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is [`../05-resource.md`](../../05-resource.md).

## Task

Give the platform objects, events and their reading; give the resource the cleanup, the mirroring and the restoration of its own buckets.

## Inputs and their priority

- The canon is the [norms](../05-resource.norms.md), the definitions of Н0 — per P/01.1; the file contracts are
  [the event journal](../../../common/contracts/event-journal.md) and [the presence lock](../../../common/contracts/presence-lock.md).
- The [HTTP contract](../05-resource.api.openapi.yaml) expresses Н2.
- The [acceptance](../../acceptance/README.md) sets the preparation and the observations.
- The [lecture](../../05-resource.md) explains the reasons and the boundaries; the [lifecycle](../../lifecycle.md) — the environment, the exit codes.

The objects use the store vocabulary of P/01.1, the roles — [P/02.4 Н1.6](../../../02-installer/spec/02.4-installer.norms.md) and
the role certificate contract. `PUT /v1/objects/<sub>/blobs/<digest>` — Н1.1 «Тела у ресурса», Н2; `restore` (`GET /mirrored/<server>`) — Н1.4 «Восстановление бакетов».
Internal functions,
libraries and the way the handlers are placed are not prescribed.

## What to create

The operations of objects and their permitted door; the write of events with buckets and classes;
the reading of the tree with a bounded cache; the resource query; the wait hint;
the resource pass retain → usage → relieve → mirror; `restore` at start.
A whole copy of a file, a source that answered and a published copy
are different boundaries of confirmation; one does not prove another.

## Order of work

1. Separate a file and a row object. Check put_new and CAS per Н1.1, the ban on giving out
   row objects through the files door, equal written and missing. Do not turn the absence of a server's answer
   into a proof of the absence of an object.
2. Write an event under the epoch. The identifier distinguishes processes, boxes and restarts;
   the fields of the platform cannot be overwritten by the fields of the subsystem. Check both classes, of, the bucket
   by t and the keeping of the whole line; check fsync by a separate piece of evidence (the suppression — chapter 3.6).
3. Build the query over the files: the parameters, the candidates, the filter, the priority of alarms,
   limit and truncated. The same query with an empty cache and after its eviction gives the same
   result with unchanged files. A torn tail gives partial, not an event line.
4. Make wait per Н1.6: four closed answers, the identity on eviction, the queue and
   the timeout. The client continues the periodic pass on the loss of the hint, on overflow
   or on a restart of the resource.
5. Perform the resource pass. An unknown reading of retention/holds gives no right to remove;
   free_ask contains no unit and matches by server/volume. The volume name is ASCII A-Z/a-z/0-9/_ of length 1–64, without a hyphen (Н1.4 `free_ask`); another volume does not publish a request and is diagnosed. The removal uses CAS of the version
   on which the form and the owner of the row were checked. The mirror is published after the check of the full body
   and the sum; a failure keeps the former copy.
   The door row carries, next to `room.<sub>`, the list `live.<sub>` — the numbers n ≥ 2 of the live locks of the same snapshot (the presence
   lock contract; ADR-0084 addendum (3) Р14′): the controller computes the free space of the server by it.
6. Pass the 35 scenarios / 292 steps of the acceptance separately. Check full answers by the owner of the form,
   even when only a code is expected in the TSV. For each checklist item name a separate
   observation; the probes outside the TSV are listed in the README of the acceptance.

## Pitfalls of the language and the library

| Norm | Possible error | Check |
|---|---|---|
| Н1.1/Н2 | prefix checked as a key; traversal got through decoding | An empty prefix is admissible; an empty key segment, a dot, two dots, a backslash and control characters are not |
| Н1.2/Н1.3 | The event fields overwrote the metadata; a PID repeated on another box | The fields of the platform are protected; id distinguishes the instances |
| Н1.3 | bool taken for integer, NaN for a number, a truncation for the incompleteness of the sources | Finite numbers, an integer limit; distinct truncated/partial |
| Н1.6/Н2 | JSONL wrapped in an array; wait returned events | Check the form, the types and the absence of extra fields |
| Н2 | After the headers a second JSON refusal is given | A break stays a break; an incomplete copy is not published |

## Done when

The whole canonical checklist is fulfilled, the choices of the implementation and the evidence for
the norms outside the TSV are named. Success, a known refusal and an unknown result of
a publication are shown separately. A check of the schema does not check the durability of files or a race;
a reading of an algorithm does not prove its execution in several processes.

## On a discrepancy

Pass to the Specification the slice, the place and a counterexample; establish whether it existed before the change.
Fix the source of the norm and its direct consumers, check the whole related class.
Do not extend the lesson with a new mechanism for the sake of a case outside the declared profile.

An additional check after run 33: GET of an object: 64 MiB/+1, without a successful truncation.

Check the id for collisions of the composite names a-e1-j/node:1:aaaaaa and a/j-e1-node:1:aaaaaa, UTF-8, different trees/epochs/parallel numbers, a restart and the outcome of the suppression; copies keep the original id. For both lists buckets/mirrored: an absent, an empty known and an unreadable directory are distinguished; an error before the headers is 500 without a body, a break does not give a full answer. Additional probes outside the TSV.
