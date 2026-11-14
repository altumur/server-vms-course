# P/03 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/03-worker.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is `ru/03-worker.md` (for people, not in the export).

Concrete scenarios, fixtures and expected answers are not supplied in M; the judge receives them separately. The public norms and forms define the implementation obligations, including the acceptance interfaces and observation limits stated in N5. In chapter checklists, `sc. NN` names a process scenario of that chapter; an explicitly named chapter selects its acceptance. Seam ids name the SDK scenarios in the named seam table.

## Task

Implement the basic loop of the worker in the language `<LANG>`: ownership of a name, leases of units, the heartbeat, the stand-in for a stuck step,
the holding of a place and the stop — by the seven chapters of the lesson; pass the N5 acceptance of the chapters and close their readiness checklists.

- **3.1.** The subsystem supplies its work through the six calls of [chapter 3.1](03.1-worker.norms.md) N2: four working ones and
  two of the ordered stop. The signatures in a specific language and the internal division are not normed.
- **3.2.** The slot, the epoch, the lease, «nobody», the place and the schema check by the worker — [chapter 3.2](03.2-worker.norms.md).
- **3.3.** The reconciliation loop in the order of N3 of [chapter 3.3](03.3-worker.norms.md) (read after P/04).
- **3.4.** The heartbeat, the stand-in, writes under the slot, the stop by SIGTERM, the memory budget, `id` on every write —
  [chapter 3.4](03.4-worker.norms.md).
- **3.5.** Opening a secret by the recipient per the [sealing contract](../../common/contracts/sealing.md) —
  [chapter 3.5](03.5-worker.norms.md) N3.
- **3.6.** For the holder — the execution of a request with a mark before the call and an explicit unknown outcome; the writing of events and suppression —
  [chapter 3.6](03.6-worker.norms.md) (read after lesson P/05).
- **3.7.** The late layer: the write of a contribution under the slot and the cleanup on capturing a foreign slot; the check of a token at the recipient —
  [chapter 3.7](03.7-worker.norms.md) (introduced by lesson 8).

## Inputs and their priority

The canon is the norms of the chapters, including N0, the deadlines of N1.2 of chapters [3.2](03.2-worker.norms.md), [3.3](03.3-worker.norms.md),
[3.4](03.4-worker.norms.md) and the order of N3. The lesson has no HTTP door and no OpenAPI of its own ([chapter 3.1](03.1-worker.norms.md)
N2): the forms of the requests and answers of the store are set by [P/01.1](../../01-store/spec/01-store.api.openapi.yaml),
the doors of units — by [lesson P/06](../../06-console/spec/06-console.api.openapi.yaml) (chapter 6.1), the publication of objects — by
[lesson P/05](../../05-resource/spec/05-resource.norms.md#n2-doors). The forms of the rows and objects of the lesson are
the family schemas `../data/*.schema.json` (the sections «Data families» of chapters 3.2 and 3.4).

## Glossary

These distinctions explain the chapter terms; they add no rule to the norms.

| Word | Meaning in this lesson |
|---|---|
| worker, `<sub>worker` | The SDK implements the worker loop; the subsystem supplies the work through the calls of chapter 3.1. A worker process runs one instance of that loop. `<sub>worker` is its store role, not the unit holder id. |
| holder, `holder` | A slot holder is an instance, identified together with `gen`. A unit holder acts under its `epoch`. The request holder observes and executes requests under that unit epoch. The domain holder belongs to the domain protocol; a slot holder alone does not acquire it. |
| name, slot, `instance`, `BOX_ID`, `SERVER_NAME` | The worker name selects the slot. `instance` names one process incarnation, `BOX_ID` the box and `SERVER_NAME` the server. None substitutes for another. The state `nobody` has no owned worker name. |
| `gen`, `epoch`, `revision`, `born` | `gen` fences slot ownership. `epoch` fences a unit holder. `revision` identifies the unit row version; `born` distinguishes a new unit with a reused id. A restart caused by revision alone keeps the epoch. |
| lease, hold, `may_act`, `may_write` | The unit lease controls its actions and data; a place hold controls the place writer. `may_act` and `may_write` have the distinct windows of chapter 3.2. A place hold and a unit lease are checked jointly; neither replaces the other. |
| confirmation, freshness, `until`, `ts` | Confirmation uses the send time of the confirmed request on the worker monotonic clock. Freshness uses the reader observation of a version. `until` and `ts` are wall-clock display values; they do not measure the age of a foreign version. |
| stop, fencing, `before_stop_all`, `after_stop` | Fencing closes admission and stops work whose ownership was lost. An orderly process stop makes the ordered calls `before_stop_all` and `after_stop` of chapters 3.1 and 3.4. A crash does not publish an orderly release. |
| request, mark, order, `begun`, `fetched` | An ordinary request has a mark and requires a confirmed `begun` before the external call. The append profile `fetched` has no mark. An order creates a row of another subsystem; its outcome is distinct from executing an ordinary request. |
| door, handler, door token, domain token | The process door calls a subsystem handler after route admission. A door token authorizes the request checked by the holder. A domain token carries a kind and audience, checked by the recipient. These token checks do not replace the process-door route admission. |

## What to create

- The loop of the worker process with the ownership gates, the state «nobody», the assignments and the leases of units (3.2, 3.3).
- The capture, renewal and release of the slot, the cleanup of the predecessor's contributions and the write under the guard per chapter 3.2 N1.4 and N3.
- The issue of the epoch and the lease state per chapter 3.2 N1.5–N1.6 and N3. The procedures report a loss to the owner of the loop;
  the loop — chapter 3.3 N3 «loop()»; the stop of a unit and the reading of `platform/epoch_floor` at the lease step —
  chapter 3.2 N3 «lease_step()», steps 2 and 4.
- The heartbeat and the watchdog with a bounded stand-in for a stuck step, the holding of the place and a correct stop (3.4; watchdog —
  3.3 N1.2; the holding of the place — 3.2).
- Opening a secret by the worker (3.5), the holder's view and the writing of events (3.6), the contribution under the slot and the token check (3.7).

## Order of work

1. Implement the start and the state «nobody». The manifest and the memory budget are checked before the name is obtained ([chapter 3.4](03.4-worker.norms.md)
   N3 «start() — the budget step»). The first capture on one's own box and a repeated search are different modes; a repeated search does not
   take away a live slot. A refusal at the start does not permit writing the heartbeat under a foreign name.
2. Assemble the loop in the order of [chapter 3.3](03.3-worker.norms.md) N3. First the ownership gates, then the reconciliation of the assignment and
   of the unit, the pump, the lease step, the heartbeat, the watchdog and the wait. Every unit checks the gates before its start.
3. The lease step checks the slot first. The loss of the slot stops all units; the loss of one epoch — only its unit.
   Do not count the absence of an answer as an empty row or list. The saved last list on a non-answer does not permit
   taking the epoch again.
4. Make the repeat of a write with the same id after ambiguous (P/03.4-07). Check a conflict as a reason to re-read: one's own
   renewal with the same holder/gen does not mean the loss of the name. Do not substitute a new id for the unknown outcome of the old write;
   take into account the window of the replay memory of P/01.1.
5. Separate the availability of actions and of data. 25 seconds is the window from the sending of the last confirmed request;
   the first window at the issue of an epoch has the same reference point. An answer after the boundary and a pause before start_unit
   do not create a new window: a late issue is lost without a start, even with forever. After a refusal
   a new successful reading of the assignment is needed; all the gates and may_act are checked once more before the start.
   The acceptance of a start is reconciled with the fencing locally: cancelled attempts and late results
   do not revive after the return of the name. The fencing also sees unfinished starts; a long call
   does not block the stand-in from closing the admission. The subjects of the interventions — in the acceptance README of chapter 3.2.
   The data under silent depend on unconfirmed_max. An overslept process, a foreign epoch and a raised floor
   do not get this allowance. A control write under the slot requires live ownership regardless of the ceiling.
6. Add the stand-in: a common non-blocking lock of the slot, cas, the FOR limit, the heartbeat with stood_in.
   Check the return of the loop after FOR, the race of heartbeats, the release of the slot and the prohibition of the watchdog from the stand-in.
7. Work out the capture and the cleanup: first the new guard and `released: taking` (chapter 3.2 N3 «capture»), then the deletions under
   this guard, then `released: false`. Check a change of owner between any two actions; a foreign contribution is not
   deleted. The table of N3 sets the transitions, the pseudo-code — the order of reads and writes; there is one kind of worker: check each
   branch with a given name, without a name and through names_given. The slot order and «by name» differ per N1.4;
   also checked are non-numeric suffixes, equal numbers of different names and the next number after a long digit
   suffix. After 412 re-read the ownership: one's own renewal keeps the name, a foreign holder/gen fences off. Taking away on
   one's own box is available only to the first start; NameOnAnotherBox leaves the process nobody with the mark `refused` in the object
   `<sub>/contenders/<name>/<box>` (chapter 3.2 N1.4a), without a change of the name. A first refusal of a foreign name writes only the mark,
   without `worker.name_taken`; that alarm is written only when a previously captured name is lost (P/03.2-R233). With a torn gen the candidate is not rewritten; with a torn until and a readable gen,
   after TORN_STILL the generation is increased. Count the UTF-8 bytes of the full key together with the prefix and the separators;
   handle a definite badkey per chapter 3.2 N3 «Full keys and store refusal».
8. Check the epoch and the lease at the boundaries of the window: confirmation from the moment of the request, another number,
   an unreadable row, silence until the window expires, a missed request and reaching `unconfirmed_max`.
   The first window is also counted from the sending of the confirmed write: answers at second 24/25/30,
   a pause between the answer and start_unit, CAS-conflict with a new attempt. A late success does not permit
   a start, the number is not rolled back; the next start requires a new successful reading of the assignment.
   Check off, a finite ceiling and forever: the boundary of 25 seconds applies to actions, not to all data.
   Distinguish the monotonic time of the lease and the wall-clock seconds of the slot; a difference of deadlines does not prove a common reference point.
   The issue of an epoch uses the floor; a floor raised during work — chapter 3.2 N3 «lease_step()», step 2: the reading of
   `platform/epoch_floor` once per step; an epoch below the floor is a loss of the lease.
9. Make the holding of the place: own/foreign, strict, confirmation by one's own clock, the closing of the writer.
   The right to the data of a unit and the right to the place are checked jointly; neither replaces the other.
10. Implement SIGTERM in the order of [chapter 3.4](03.4-worker.norms.md) N3 and distinguish it from SIGKILL. Describe the choices of the implementation
    («Implementation decides» of the chapters), including TimeoutStopSec and the presence of the process at the resource.
11. Opening: pass the vectors of the contract [`open.tsv`](../../common/vectors/sealing/open.tsv) and [`ring.tsv`](../../common/vectors/sealing/ring.tsv) (judge-only: opening and ring-text vectors)
    with one's own opening function; the opening by the worker and `why` on an error — by reading [chapter 3.5](03.5-worker.norms.md) N3 «open»
    (there is no worker with secrets on the stand).
12. Write an event under the epoch per the [event journal contract](../../common/contracts/event-journal.md) (lesson P/05); suppression — [chapter 3.6](03.6-worker.norms.md) N1.2. Separate
    ordinary requests, the append profile (`requests.outcome: fetched`), elsewhere and free_ask per N3 of chapter 3.6. The append does not create a mark: fetched, the removal
    of the row and the release of asked; a repeat decides by the data. For the ordinary profile carry out the table: admission and deadline,
    a confirmed begun, a single call. Check a conflict and an unknown outcome of each read/change. The presence of
    begun does not yet prove the call of the external action. The mark is deleted only by the holder after the disappearance of the row and kept.
    The outcome refused after a call always has error, never performed; check both the pass and the form of the mark.
13. The late layer (3.7): the contribution under the slot and the cleanup on capturing a foreign slot (the training writer of contributions `testsub2` — P/08.5
    N5); the check at the recipient `wrong_kind`, `wrong_audience` (`token` of the domain token contract «The check» with `expect`).
14. Run the acceptance scenarios separately, each with a new state and new processes: in total the lesson has 49 scenarios / 503
    steps (judge-only: the process acceptance of the chapters) — chapter 3.2 (`acceptance/2/`: 01, 04, 05, 08, 09, 10, 11, 14–24, 26–34, 44), chapter 3.3 (`acceptance/3/`: 02, 06, 12, 25, 35),
    chapter 3.4 (`acceptance/4/`: 03, 13, 36, 37, 38), chapter 3.6 (`acceptance/6/`: 05, 07, 08, 09, 10, 38–43). Fill in the checklists of the chapters with evidence from N5 of the chapters.
    Compare the full HTTP answers of reads with lessons P/01 and P/06 (chapter 6.1). The heartbeat, the state of the process and the stop of the writer cannot
    be confirmed by the mere presence of an epoch row.

## Pitfalls of the language and the library

| Norm | Possible error | How to keep the behaviour |
|---|---|---|
| 3.2 N3: slot capture | the slot is declared live before the contributions are deleted | keep the two writes of the slot and the guard on the deletions; even without contributions the final write is needed |
| 3.2 N3: 412 of the slot | one's own renewal is taken for a change of owner | re-read holder/gen and released; check one's own confirmed deadline, not the until of foreign clocks; a repeat only after checking the conditions |
| 3.2 N1.4: gen | an unreadable generation is replaced with zero after TORN_STILL | an existing slot is not captured; the absence of the row and the spoiling of its gen are distinguished |
| 3.2 N1.4–N1.6: time | wall clocks are compared with monotonic ones; the lease is confirmed from the receipt of the answer | `until` — only the writer's wall-clock seconds, for display; the age of the version at the judge and one's own deadline of the confirmed request — monotonic; a delay of the answer does not widen the window |
| 3.2 N3: epoch | an unreadable value is treated as absent and replaced with zero | zero only on absence; an unreadable row — `EpochUnreadable` |
| 3.2 N1.6: silence | an overslept process gets the right to write by `unconfirmed_max` | `lost` differs from `silent`; the silence ceiling does not revive a missed window |
| 3.3: memory | the cache of the assignment is taken as a fresh permission | a non-answer forbids a new taking of the epoch |
| 3.3: emptiness | a read error turns into an empty assignment | silence and an answered empty list give different actions |
| 3.2: fencing | a conflict of one's own renewal takes away the name | re-read holder/gen/released, then the decision per chapter 3.2 N3 «renew» |
| 3.2: nobody | the former slot/assignment are used after the loss of the name | the operations of the state nobody from N3, no heartbeat |
| 3.2: catalogue | the cleanup on capture reads the rows of another manifest with its own role | the cleanup — only the rows of its own subsystem; sc. 08 on two manifests |
| 3.2: name | a wrong given name is replaced by a search without a name | a start refusal with code 2, no slot and no mark (N3 «start()» step `2a`) |
| 3.2: alarm | `worker.name_taken` is written on every capture | only on the loss of the name, once per episode |
| 3.4: concurrency | the stand-in blocks the loop or renews after the release | a non-blocking lock, the stand-in is stopped first, cas of the owner |
| 3.4: heartbeat | the system clock and ts give a false freshness | the reader judges by an observed change |
| 3.4: signals | kill is taken for a performed cleanup | the judge waits for the exit; a crash does not write released |
| 3.5 N3 «open» | the opening tries former AAD ways | the single AAD of the contract; not opened — `Sealed` with a reason |
| 3.6 N3 | a CAS timeout is taken for the absence of the mark | no confirmation of begun — no call; unknown does not permit a repeat |
| 3.7 N1.5 | the recipient does not look at `aud` | `token` with `expect.cluster` — otherwise the token is good for any member |

## Boundary checks

For the slot distinguish three times: the display of until on the writer's clock, the age of the version on the judge's clock
and the deadline of one's own confirmed request. A shift of the first clock does not change held/lapsed or the fate.
Check a new first look, one's own late answer and the window of the write after one's own renewal.

Current startup admits SERVER_NAME before the presence lock: empty or invalid is the existing startup refusal, exit 2; a valid start publishes a nonempty server. BOX_ID and instance do not replace the server. The acceptance chapter READMEs specify the checks outside TSV.

## Done when

The choices of the implementation are named and all the norms of the chapters are checked with the boundaries of the evidence.
The stand confirms only the rows it observes, the changes of generations/epochs and the commands of processes.
Separately attached are the results of reading or of stands for the heartbeat, the stand-in, the memory budget
and the actual stop of the work of a unit, silence, places, another box, opening a secret by the worker, the holder's view
and the late layer. The success of the TSV parser does not mean the success of these checks.

The optional implementation plan for the generated kit is [forms/stages.tsv](../forms/stages.tsv). The inputs and test normalization are described by [forms/README.md](../forms/README.md). The plan does not replace any norm, vector, reading witness or process acceptance, including the external dependencies named above.
