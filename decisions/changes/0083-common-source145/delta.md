# Delta 0083-common-source145

change: 0083-common-source145 rev1 · lesson P/03-P/10/common, direct P/01 Time owner · state review

Base `7bc7e3fdfdacf20d4fd026bb2ee6bb0234acd1fb`. Faithful accepted own component Source closure; no new normative decisions, classes, fields or keys. Earlier accepted component kits and freezes remain immutable; this kit binds their current published composition. Normalization: LF, trailing spaces removed, one finalLF; req markers end at next marker or same/higher heading, immediate associated heading belongs to the unit. 118MODIFIED/0ADDED/0REMOVED.

## MODIFIED

### `Platform/03-worker/spec/03.1-worker.norms.md` P/03.1-R009

old-sha256: cf2cd83c22a3e1f8b997568233837a2ddaff3ba5cf02526825f2c97400bcb100

<!-- req: P/03.1-R009 -->

The chapter has no procedures of its own. Who makes the calls of N2 and when: `start_unit` — after the gate «take_unit_epoch» of [chapter 3.2](03.2-worker.norms.md) N3
and at a restart by revision ([chapter 3.3](03.3-worker.norms.md) N3 «loop()», step 2); `stop_unit` — the loop, the lease step, fencing and
the stop (chapters 3.2–3.4); `status` — the heartbeat ([chapter 3.4](03.4-worker.norms.md) N1.1); `reconcile_once` — the loop, step 2;
`before_stop_all`, `after_stop` — «stop by SIGTERM» of [chapter 3.4](03.4-worker.norms.md) N3, steps 2 and 5.

---

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R002

old-sha256: 1cbf2e8383d8073db95af52bfba6653f2ce2127670797fbf21970a3b9f2fdb42

<!-- req: P/03.2-R002 -->

**Time.** Time fields follow [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#time-in-a-row): `<sub>/slots/<name>` — `until`; `<sub>/holds/<place>` — `until`; `<sub>/contenders/<name>/<box>` — `since` and `at`; `platform/epoch_floor` — `generation_at` ([P/01.3](../../01-store/spec/01.3-store.norms.md)).

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R004

old-sha256: 645762d10d4560c50960f8aeaf35739266e813bce7ed922f750b0f5ddcc46c3a

<!-- req: P/03.2-R004 -->

The lease, contender and place timings used by this chapter. The terms of the loop and of the heartbeat (`HEARTBEAT_EVERY`, `POLL`, `WAKE_GAP`,
`PASS_SHARE`) and the watchdog (`watchdog`) — [chapter 3.3](03.3-worker.norms.md) N1.2; the stand-in (`stand_in`) and the memory budget
(`memory`) — [chapter 3.4](03.4-worker.norms.md) N1.2.

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R005

old-sha256: 22863efb203fdce087ee9571a779f34ec8ff53f406dfb61655ae481abf6516fb

<!-- req: P/03.2-R005 -->

Independent settings are in [runtime-constants.tsv](../forms/runtime-constants.tsv). SLOT_TERM belongs to the slot contract; HOLD_SKEW and CONTENDER_FRESH belong to observation. Equal current values from different owners are not the same setting.

```yaml
# LEASE_TTL, LEASE_MARGIN, CONTEND_EVERY are the owned runtime-constants.tsv rows.
loop:
  LEASE_EVERY: (LEASE_TTL - LEASE_MARGIN) / 3  # exact; from the START of the previous step
  again: the slot renewal got no answer or at least one lease became silent - the next step at once
contend:
  CONTENDER_FRESH: the observation contract, Freshness of a contender mark
places:
  HOLD_SKEW: the observation contract, Hold of a place
  WRITE_WINDOW: SLOT_TERM - HOLD_SKEW  # strict writer's confirmed window
  CLOSE_BY: SLOT_TERM + HOLD_SKEW     # strict writer must be closed by this moment
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R007

old-sha256: 780677b126b6a5acc4cbe05ff1abb50cddc61431b01acfa25091cead0c0d186e

<!-- req: P/03.2-R007 -->

```yaml
slot:                                     # a manifest section (P/02.1 N1.2); closed: two keys
  prefix:   <1–8 lowercase Latin letters> # default w; the slot name is <prefix>-<suffix>
  name_env: <VARIABLE_NAME>               # ^[A-Z][A-Z0-9_]*$; the environment variable from which the worker takes the preferred name when it was not given as an argument (N3 «start()», step 3); no key — the name is not taken from the environment
<sub>/slots/<name>:                        # name: <prefix>-<suffix>, suffix ^[a-z0-9]+(-[a-z0-9]+)*$: a numeric <n> — the names that
                                          # a capture without a given name invents; <server>-<n> — a name from the unit (P/02.4 N1.1: the instance
                                          # %i = <prefix>-<server>-<n> as an argument, P/02.4 N1.2; ADR-0043), <server> = SERVER_NAME (P/02.4 N1.2);
                                          # n is a decimal integer without leading zeros: 1 — the base process of the role on the server, 2…99 —
                                          # ordered by the controller (P/04 N3 «order()»; ADR-0084); a choice by number (the reduction of
                                          # P/04, the workers script of P/02.4 N1.5) compares n as an integer, not by the slot order below
  holder:    <instance> | ""              # instance — the instance contract grammar (common/contracts/instance.md; layout audit «A-06», the Architect's decision 2026-10-25)
  until:     <Time>   # writer clock + SLOT_TERM; display/divergence, not freshness
  released:  "true" | "false" | "taking"     # taking — the first write of a capture (N3 «capture» step 3; added by the Quint pilot, F2)
  gen:       <exact decimal integer 1..9007199254740991> # initial operand of an absent row is 0; +1 at capture
  server:    <nonempty holder server> # capture/renewal after SERVER_NAME admission before the presence lock
states:    held, lapsed, released, taking, torn — the slot contract «States» (moved there without change; layout audit «A-04», the Architect's decision 2026-10-25)
constants:
  SLOT_TERM, TORN_STILL: the slot contract «Terms» (common/contracts/slot.md; moved there without change; layout audit «A-04», the Architect's decision 2026-10-25)
  RENEW_EVERY: LEASE_EVERY # exact formula in N1.2
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R011

old-sha256: 3bc0f65850593a88614caae1c47076bdacb5a5bb475671b14abc1e7dd9ede3ff

<!-- req: P/03.2-R011 -->

Confirmed row absence supplies the initial generation operand 0. An existing `gen` MUST be an exact decimal integer in `1..9007199254740991`, the current capture writer range. Missing, zero, negative, above-bound or otherwise invalid gen selects the existing refusal-catalogue entry `slot_gen_unreadable`: do not rewrite the candidate, even after `TORN_STILL` or controller permission. Preserve its original bytes, without zeroing or rounding.

The maximum `9007199254740991` is readable. Before an allowed capture, check whether the next generation fits: the maximum gives `generation_exhausted` before a write. Damage to other fields with a readable gen permits the first capture after `TORN_STILL` only with exact gen+1 inside the writer range. NameOnAnotherBox and capture admission still apply. The machine input `gen_readable` is checked on the original bytes before narrowing; `gen_incrementable` is true for confirmed absence or a readable gen below the maximum. Machine int gen is an exact operand or an unused zero placeholder; a wide damaged gen never becomes zero. With no preferred name, rejecting one candidate does not prevent checking the next ones.

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R012

old-sha256: c36cdd194497e3fbd3a3b437aefeade084b7f680366e9049b2be4d8fd406c4e7

<!-- req: P/03.2-R012 -->

The local policy selector is [`contender-writer.machine.yaml`](../forms/contender-writer.machine.yaml), with its [traces](../forms/contender-writer.traces.tsv) and [effect boundary](../forms/README.md#worker-policy-machines). Capture, IO and cryptography still follow the ordinary procedures below.

The object `<sub>/contenders/<name>/<box>`: `{name, state: refused | nameless | waiting, box, hostname, server, instance, holder, holder_box, since, at}`; `refused` — NameOnAnotherBox by the capture table of N3 «capture», including an occupied unreleased lapsed row of another box; `nameless` — its own former capture is gone, the worker waits; `waiting` — it has had no capture of its own yet, and there is no candidate without NameOnAnotherBox. The priority of refused is above the other two. On a decommissioned server (N3 «start()» step 3) there is no mark: the worker is nobody without a name search and is not a contender. In a search without a given name `name` is `-` and `holder` is `""`; with a given name — the sought name and its current holder. It is rewritten every `CONTEND_EVERY`; the freshness at the reader is the [observation contract](../../common/contracts/observation.md) «Freshness of a contender mark» (`CONTENDER_FRESH`; C06-CONTENDER-FRESH-33-01, the Architect's decision 2026-10-25): a mark older than `CONTENDER_FRESH` is not counted; an unreadable mark (not in form) is, for a worker reader, as one older than `CONTENDER_FRESH` (review of stage B 3–5, № 5), for the console a fresh unreadable one is a conflict with a flag (the outcomes by reader — [`contenders.outcomes.tsv`](../data/contenders.outcomes.tsv); C03-CONTENDER-UNREADABLE-01); `since` is kept within one state.

All ten listed fields are required in the current object; name/state obey the policy and server is nonempty. since and at use the existing Time type, not arbitrary values. Within one state retain since only from a readable current object or valid local policy memory, never from an unchecked value. A state change supplies a new since. Freshness remains based on the observed version, not at or since.

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R014

old-sha256: e0bfc5ed114c515c0940c173ad38cbdcfcfcccac7480ee7c50ab29544e46051c

<!-- req: P/03.2-R014 -->

```yaml
lease:
  # Action window: LEASE_TTL - LEASE_MARGIN from the last confirmed request send.
  states:
    confirmed:    the issue of my epoch is confirmed or a read carries my number → last — the greatest send moment of the confirmed requests
    fenced:       the row has another number, the row does not read or the worker is fenced → forever for this epoch
    silent:       the store did not answer while the window was open → unconfirmed is counted from the end of the window
    lost:         the window ended without a request (overslept), or the initial issue/launch was late, or the epoch is below floor — not silent
  may_act:    not fenced and not lost and now − last < (LEASE_TTL - LEASE_MARGIN) and the own slot term of N1.4 has not expired
              # lost and the slot term — added by the Quint pilot (F3): with lost writes and live reads the old holder
              # stops acting before the move — its own term is SLOT_TERM from the renewal send; movement follows the controller contract P/04
  may_write:  may_act or (silent and unconfirmed < unconfirmed_max)      # unconfirmed_max: off = 0, forever = ∞
  unconfirmed_max: from manifest.lease (P/02.1): forever | off | <integer ≥ 1 s>; default off
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R024

old-sha256: 16352fdf07ef7fe01e49dc9416b6b87bcf7be72c95854274767d14c3a7212116

<!-- req: P/03.2-R024 -->

```
1. read the slot rows and the field names_given of the object <sub>/controller/pass (P/04 N1.2; bound to the version of the slot row);
   do not count a non-answer as an empty list or as the absence of a row → nobody
2. keep only the admissible names of the own manifest and the candidates by the table;
   the order of candidates (skip a repeated name):
   a. the name from the environment, if given, is the only candidate (ADR-0043); do not pass to b–e
   b. the names released by the controller, in the order of names of N1.4
   c. free readable rows — in the slot order of N1.4
   d. torn rows with a readable gen that stood unchanged for TORN_STILL — in the slot order
   e. only a process without a given name: a new <prefix>-<max + 1> by N1.4
3. for a candidate: re-read the row and apply the table again;
   the ground of the chosen branch must persist: the version of names_given is exact, the free row stayed free,
   the torn row did not change, the new name is still absent; otherwise the next candidate;
   for a given name check the conditions of the table anew, including holder and the first-start flag;
   write {holder: me, until: now + SLOT_TERM, released: "taking", gen: gen + 1, server} with cas of the read version; conflict → the next candidate. The slot is captured but not live: the controller and
   the agents do not read it as live, the controller does not take it for a release (N1.4 taking;
   added by the Quint pilot, F2), writing under it is not allowed (P/03.2-03); from this write on, the guard of the predecessor is invalid —
   its late contribution write gets 412
4. list the contributions of the predecessor under this name (the contribution rows of chapter 3.7 N1.2 claim) — already after step 3, so
   the list is complete; delete each by a write under the guard {key: slot, index: the version of the write of step 3}; then write
   released: "false", until: the writer's clock + SLOT_TERM with cas by that version → the slot is live; the version of this write = the guard from then on (ADR-0074 C2: no row
   of the predecessor is visible under the live slot of the new holder). No contributions — the second write is made anyway
→ slot; all candidates failed → nobody
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R026

old-sha256: fdf944f7ad20bc45db339dcd133f53191cccdc2eb1ee66991f5aa5c420f4a5f2

<!-- req: P/03.2-R026 -->

```
every RENEW_EVERY:
  read the slot; holder/gen not mine, released or the slot does not read   → lost: become nobody (N3 «nobody and getting the name back», give_up_name())
  write {…row, until: now + SLOT_TERM, server} with cas; conflict                 → re-read and check all the conditions again
  the store did not answer                                                 → still mine (the lease of the units decides)
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R032

old-sha256: e40fa65700c097e9bbd1c1c9d4a53fa796c6880b97df69b03181476c80bf638a

<!-- req: P/03.2-R032 -->

```
conditions: I am somebody (the slot is mine); the unit is in the assignment that answered last; not lost since then
read <sub>/epoch/<id>: confirmed absent → 0; existing epoch not an exact integer in 1..9007199254740991 → EpochUnreadable, preserve original bytes (not 0)
read platform/epoch_floor: floor (absent → 0; does not read → a refusal of the issue, the floor is not replaced by 0)
max(current, floor) >= 2^53 − 1 (compare exact readable integers before conversion to a machine number) → a refusal of the issue before the write: the epoch row does not change, do not launch the unit, the log
  names the unit and the epoch; do not retry a known out-of-range issue (like rev of P/02.3 N1.5 at the same bound; review of stage B 3–5, № 8)
t0 = now (monotonic, immediately before sending the write)
write {epoch: max(current, floor) + 1} with cas of the read version;
  conflict → re-read the epoch row and the floor and repeat with a new t0 for the new write (the floor — added by the Quint pilot, F1)
  outcome not confirmed → a retry with the same id by P/03.4-07, t0 — the first send (N1.6); not confirmed even then — a refusal,
                          do not hand out a new lease
  confirmed → last = t0; now − last ≥ (LEASE_TTL - LEASE_MARGIN) → lost, a refusal of the launch, not silent
before start_unit — a successful «confirm» (below) with t0 after the confirmed issue write (the order is causal: the read
  is sent after the answer of the write; equal readings of the monotonic clock within one tick are admissible; C03-POST-GRANT-SAME-TICK-01): an epoch below floor → lost,
  do not launch; another one or unreadable → fenced; the store did not answer — do not launch, silent does not allow
  the first launch (added by the Quint pilot, F1)
→ epoch; lease = a new one with last = t0, only within the remaining window
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R034

old-sha256: 4084ea38d74294468dbbe5de53f8d871fa1511adec05b66c681a99cf1b659f67

<!-- req: P/03.2-R034 -->

A delayed answer of the issue does not start a new window: a send at 0, a successful answer at 30 — the epoch may
have been written, but the start is already forbidden. The number is not rolled back and not deleted; a late answer gives
neither silent nor a right by unconfirmed_max, not even with forever. The next attempt requires a new successful
read of the assignment and passes the gates of N3 «take_unit_epoch(unit)» again. Right before start_unit the gates and may_act
are checked once more: a pause between the return of the issue and the launch does not extend the window.

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R035

old-sha256: ed47ddc9f7486d7e431db748403c7d42dba12edfc27992fc176df6ac14797acd

<!-- req: P/03.2-R035 -->

```
t0 = now (monotonic); read <sub>/epoch/<id> and platform/epoch_floor
  the floor does not read      → fenced, as a refusal of the confirmation: the floor is not replaced by 0
  my epoch is below floor      → lost (N1.6; the Races of the issue)
  carries my epoch             → the window ended without a request (t0 − last ≥ (LEASE_TTL - LEASE_MARGIN) and not silent — overslept) → lost, do not revive: N3 «lease_step()»,
                                 step 4 stops the unit (stop_unit); otherwise last = max(last, t0), also after silent:
                                 a successful read of its own epoch returns the lease to confirmed
  another one or unreadable    → fenced: stop the unit, remember the loss of the epoch (N3 «lease_step()», step 4; the epoch row does not change)
  the store did not answer     → the lease was not silent and the window is still open (t0 − last < (LEASE_TTL - LEASE_MARGIN)) → silent from the moment the window ends;
                                 already silent → stays silent (unconfirmed grows up to the ceiling); the window missed without a request → lost
may_act / may_write — by N1.6
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R036

old-sha256: af24c63991ce0a89d2bb2d7877d38df14566e0adb7a0153b5946425da6beb796

<!-- req: P/03.2-R036 -->

**Races.** A confirmation and a change of the epoch by another worker: the read sees either mine or the new one —
in the first case the window is extended by LEASE_TTL - LEASE_MARGIN from t0, in the second the worker is fenced at once. The term of the move is set by
the fate of the slot, not by this read alone (P/03.2-08). With silent, actions stop by the end of the window;
data — by unconfirmed_max: with off also by the end of the window, with a finite ceiling — when it is reached,
with forever no finite stop term for data follows from the silence. The data of different attempts are told apart by epochs.

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R038

old-sha256: 5be7b331bee4c86dcfa9de317a2616398e0ff039a21ec1a8ae0e355f986f4c89

<!-- req: P/03.2-R038 -->

```
0. the check of the store schema — N3 «schema check by the worker» (P/06.6 N3 «console start — schema check», the common block; added by M10/10): the first step, before the manifest
1. the manifest from the catalogue and the memory budget — chapter 3.4 N3 «start() — the budget step»; the procedure is for the role <sub>worker (the worker on
   the domain — chapter 3.7); a program launched by the runner compares W2C_MANIFEST_REV with rev of the read row: not equal —
   exit 0 (P/02.3 N3 «Process start» step 4; ADR-0091 addendum (4)–(6)); it compares at start only if the variable is set:
   not set (a launch not by the runner w2c-run.sh) — it does not compare and serves by the read row (C03-MANIFEST-REV-UNSET-01,
   the Architect's decision 2026-10-30, norm questions of the Gemini audit, P/03 item 4; acceptance — the system one, sc. 08 `@manual`)
2. the instance — the instance contract compute (common/contracts/instance.md; moved there without change; layout audit «A-06», the Architect's decision 2026-10-25): both
   sources — by the instance grammar and the instance profile of the event log contract («The event id and the writer instance»), otherwise a start refusal: exit code 2, a log with the instance
   and the reason; the slot is not captured, there is no lock, contender mark or heartbeat (review of stage B 3–5, № 7); likewise —
   a word of `LABELS` of the environment (the environment file contract «Environment variables») outside the [alphabet of labels](../../common/contracts/labels.md): a start refusal, code 2,
   a log with the word (the VMS request «heartbeat and a garbled row», the Architect's decision 2026-10-23)
2b. the presence lock (the presence lock contract): open(O_CREAT) <events root>/.workers/<sub>/<instance>.lock →
   an exclusive blocking flock → compare fstat(fd) and stat(path) (ENOENT at stat — a mismatch, review of stage B 3–5, № 19); no match — close and repeat; a match — write {instance, sub,
   worker, server, pid} anew under the lock (worker — ""; the form — the family presence-lock of P/05) and hold the flock until the exit of the
   process; after each capture of a name (step 5, N3 «nobody and getting the name back») — rewrite the content anew under the same
   lock, worker — the slot name (review of stage B 3–5, № 23), after a loss of the name (N3 «nobody and getting the name back»
   `give_up_name`) — the same way, worker — ""; failed → a start refusal, code 2 (the second pilot,
   «N-1»; ADR-0083 addendum (10))
2a. a given name (an argument or slot.name_env, step 3) not by the slot name grammar or not with the prefix of its own manifest (N1.4)
   → a start refusal: exit code 2, a log with the name and the reason; the slot is not captured, there is no contender mark or heartbeat
2c. a name from the unit <prefix>-<s>-<n> (N1.4, P/02.4 N1.1: <s> is non-empty, <n> is an integer without leading zeros) whose <s> ≠
   SERVER_NAME (the environment file contract «Environment variables») → a start refusal, code 2, the log «<name> names server <s>, and this server is <SERVER_NAME>»:
   the server name in the unit and in the order row of P/04 is one identity (ADR-0084)
3. the server is decommissioned (the observation contract «Server decommissioned»: the row platform/decommission/<my server> or <sub>/decommissioned/<my server>) → nobody, the log
   «server <s> is decommissioned», the name is not taken, there is no contender mark (N1.4a); the decommission row exists but does not read in its own
   form → the name is not taken until it reads, the reason goes to the log without the value (V7 item 3, the Architect's decision 2026-10-28, P1; row 6 of the list); otherwise capture(name | without a name) (N3 «capture»): the name is the argument of the worker command (the unit — the instance %i, P/02.4 N1.1; the stand —
   {name}); no argument — the variable slot.name_env, if the manifest declared it; otherwise without a name;
   the right to take a name from its own box — only this first call at start, not a later search;
   the refusal NameOnAnotherBox → nobody, the mark refused
4. remember what it found under the name (previous_*)
5. the name is obtained → writing_allowed = true, a heartbeat at once; the name is not obtained → writing_allowed = false, no heartbeat;
   start the stand-in and the loop (the stand-in renews no one while the worker is nobody)
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R047

old-sha256: 51c8fc80e27b34f1f2b68f19921f42391975365ecb9ee5eeb44bdcde16c2d788

<!-- req: P/03.2-R047 -->

```
give_up_name(): cancel the unfinished launch attempts; seeking = name; slot = nil; the assignment is forgotten; rewrite the content of the presence
                lock anew under the same lock, worker — "" (step 2b of N3 «start()»; the Architect's decision
                2026-10-20 on the review of stage B 3–5, № 23)
while nobody: renewal → no; stand-in → no; assignment → empty, do not ask the store; take_unit_epoch → NoSlot;
              heartbeat → do not write; release the slot → nothing; the place hold → waits like everyone
seek_name(): the server is decommissioned (as at start, step 3) → stay nobody, no mark;
             choose only by the admission and the table of N3 «capture»; given is set → only this name, subject to the same admission and capture table
             NameOnAnotherBox (including lapsed of an unreleased row of a foreign box) → the mark refused;
             another case of «no candidate» → after the loss of the former capture the mark nameless,
             if there has been no capture of its own yet — waiting. The mark every CONTEND_EVERY;
             worker.name_taken — only on the loss of the name (give_up_name after a capture taken away), once per episode; a successful
             capture, the first search and waiting do not write it. The priority of refused is above waiting/nameless
             given absent → any admitted free/released name or a new <prefix>-<max+1>
rejoin(): add the lease-conflict counters of units being forgotten to conflicts_carried exactly once; keep the prior carried total;
          release all epochs, forget those units, give_up_name,
          seek_name; the name is obtained → writing_allowed = true, the log «rejoined as <name>», worker.name_back (the event log contract `journal`) — only after name_taken of this episode
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R051

old-sha256: fd7fcb48ac5ba17eee277fafb053ac470e26bd69fe84c0c633b44917c6c7ecef

<!-- req: P/03.2-R051 -->

```
take_place([candidates in the order of the subsystem]):     # when — N3 «lease_step()» step 6: without a place, without waiting for the assignment
  skip torn ones; first the places whose by = my name (if the slot is mine); take at once only a place that
  «follows the name»: by = my name and the place row names my server (without server_field — the former holder from this
  box); a place of another name on my server is not taken at once;
  others — only when free (released, holder "", mine) or when it stood unchanged for LOST_AFTER + HOLD_SKEW by my clock;
  the heartbeat of the worker by of the place (the observation contract «Hold of a place» active) is read only while the hold row is effective
  by itself (holder non-empty, not released, the age of its version by my clock < LOST_AFTER + HOLD_SKEW): such a heartbeat does not read in its own
  form → do not take the place until it reads, the reason goes to the log without the value: an unreadable heartbeat is not «the heartbeat is not fresh»
  (V7 item 3, the Architect's decision 2026-10-28, P1; row 23 of the list); the row is no longer effective — the place is free by the row,
  the heartbeat is not read, and its unreadability does not hinder the taking (C03-PLACE-PULSE-LIVE-ROW-01 to C06-UNHELD-PULSE-UNREAD-01, the Architect's decision 2026-10-30,
  norm questions of the Gemini audit, P/03 item 1);
  write the form of N1.3 with cas under the guard of its own slot (review of stage B 3–5, № 4); conflict → the next one; all occupied → "" (the place is not taken)
  the secrets of the place row — chapter 3.5 N3 «open» (place): Sealed → the candidate is not taken, place_error.<place>: sealed (chapter 3.4
  N1.1); the subsystem refused — refused, the place row not in form — wrong;
  an exclusive place (affinity.exclusive, P/04 N1.3: a place row binding by strict) is taken only by a worker without places and
  without assigned units — the check before the taking; the one that took it takes no other places and accepts only the units bound to this
  place (ADR-0091 addendum (9) items 5–6, addendum (10); the Architect's decisions on the repeated review of addendum (10), 2026-10-23)
hold: a change of the row of a held place (including a secret) — the place is re-read and opened anew (chapter 3.5);
      a renewal at every lease step and in the stand-in with cas under the guard of its own slot; another holder → lost;
  its own place row is torn (N1.4 torn) → the renewal is not confirmed, the row is not rewritten — like silence (review of stage B 3–5, № 5);
  the store is silent → it is held
  within the window: a strict place (lease: strict and not own) — while confirmed < WRITE_WINDOW, close by CLOSE_BY;
  an own place and a non-strict foreign one (without lease: strict) — while < WRITE_WINDOW + unconfirmed_max (forever — without a limit):
  the window WRITE_WINDOW is only for a strict one (N1.3 own_place; the cammeta-go log, lesson 5 № 3)
  the window ended → ask once more; not «mine» → leave_place: the log «the hold on <p> has not been confirmed for N s,
  and its lease is strict | past the units' ceiling — letting go of it»; the subsystem closes the writer
let go: released: "true", until: now with cas under the guard of its own slot — only an orderly stop, before the release of
  the slot (chapter 3.4 N3 «stop by SIGTERM», step 4); 412 guard or the slot is no longer mine → do not let go: the place
  is freed by the term (LOST_AFTER + HOLD_SKEW) (review of stage B 3–5, № 4)
```

### `Platform/03-worker/spec/03.2-worker.norms.md` P/03.2-R063

old-sha256: bb568a4841c087c6c8f83bd1fc4ca0d8a252b7f8859d77686fd97bddb78785da

<!-- req: P/03.2-R063 -->

| № | Scenario | Norms |
|---|---|---|
| 01 | the start of `w-1`: a slot row of the form of N1.4 with `server`, `gen: 1`, `released: false` | N3 «start()», N1.4 |
| 04 | a second copy of `w-1` on the same box: `gen` 2, a new `holder`, the epoch of the unit raised by the new one; the first one is nobody (the mark `nameless` is an object on the resource, checked by reading) | N3 «nobody and getting the name back», N1.4a |
| 05 | SIGKILL: the slot is not released, after 20 s the slot row is the former one (`holder`, `until`); the fate of the slot after the margin and the release itself are checked by reading (P/04); a single lower bound of 90 s is not promised with a known gone; that there is no mark — by reading (the mark is an object, the TSV does not read objects) | P/04 |
| 08 | workers of two manifests of the catalogue: `w-1` (`testsub`) and `t-1` (`testsub2`) hold slots, `gen` 1 does not grow; the unit `testsub` in `rows` with `running` | N3 «start()», N3 «capture» |
| 09 | a given name not by the grammar (`W-1`) and not with `prefix` (`x-1`): a start refusal with code 2 (`@exit 2`); there are no slots `W-1`, `x-1` and `w-1` | N3 «start()» step 2a, N4 |
| 10 | a second copy of `w-1` with the resource P/05: in the log `audit/testsubworker` exactly one line `worker.name_taken` | N3 «nobody and getting the name back», the event log contract `journal` |
| 11 | a word of `LABELS` outside the alphabet of labels (`a,b@c`): a start refusal with code 2 (`@exit 2`), there is no slot `w-1`; by the alphabet (`a,b`) — `w-2` holds a slot | N3 «start()» step 2; P/02.4 N1.2 `LABELS` (the VMS request «heartbeat and a garbled row») |
| 14 | an existing slot row with an unreadable `gen` (released, `holder` empty): rewritten neither at once nor after `TORN_STILL`; no name and no heartbeat | N1.4 the paragraph «An absent row has…», N3 «capture» (the transition table), N4 |
| 15 | readable free rows: without `released` and with an empty `holder` — a capture with `gen` 8; a released one with a foreign `holder` — a capture with `gen` 4; `server` of its own server | N1.4, N3 «capture» (the transition table) |
| 16 | an occupied unreleased row of another box with a given name: NameOnAnotherBox — the row of the same version, no heartbeat, no `worker.name_taken` | N3 «capture», «nobody and getting the name back», N4 |
| 17 | a torn row (`until` not in form) with a readable `gen`: untouched before `TORN_STILL`, after it — a capture with `gen` 8 | N3 «capture» (the transition table), the slot contract «Terms» |
| 18 | epoch rows before the issue: `2^53 − 1` and not a number — after the assignment of units both of the same version (a refusal of the issue before the write; 0 not substituted) | N1.5, N3 «take_epoch(id)», N4 |
| 19 | `platform/schema` with `version` greater than SCHEMA before the start: a start refusal with code 2 (`@exit 2`), no slot | N3 «start()» step 0, «schema check by the worker»; the schema contract |
| 20 | `version` raised on the run: after the renewal the slot version no longer changes, `released` is not written, there is no heartbeat any more | N3 «schema check by the worker», «lease_step()» step 1 |
| 21 | the decommission row of its own server before the start: no slot, heartbeat or contender marks; the row removed — a new worker takes the name | N3 «start()» step 3, N1.4a |
| 22 | a start refusal with code 2: a name from the unit with a foreign server, `INSTANCE_ID` and `BOX_ID` not by the grammar, `SERVER_NAME` not by the grammar; no slots; a name of its own server is taken | N3 «start()» steps 2, 2c; N1.4 `server`; N4; the contracts of the instance and of the environment file |
| 23 | an own place (`testsub2`, the shelf names `srv-a`), the hold row is torn: it is not rewritten, the place in the heartbeat is held longer than the strict window `CLOSE_BY` | N3 «place: take, hold, let go», N1.3 `own_place`, N4 |
| 24 | the store is silent to the worker role for 10 s (longer than a lease step, shorter than the window): the slot is the same (`holder`, `gen`, `released` false); afterwards — a renewal by the same holder, the lease is confirmed, the epoch and the placement are the former ones (coverage audit P/03, C11) | N3 «renew», «lease_step()», N1.6, N4 «slot renewal: the store did not answer» |
| 26 | the epoch floor (`op: floor` of the door `admin`) before the start: the first epoch is `floor + 1` (`floor + 1`); the floor raised on the run above the epoch — the lease is `lost`, the unit is again under the epoch `max(current, floor) + 1` (`max(current, floor) + 1`), `running` in the heartbeat (coverage audit P/03, second pass) | N1.5, N1.6 `lost`, N3 «take_epoch(id)», «confirm», «lease_step()» steps 2, 4; N4 «the epoch of the unit is below the floor» |
| 27 | the floor row does not read (`@spoil row`): the epoch of an assigned unit is not issued, 0 not substituted (coverage audit P/03, second pass) | N3 «take_epoch(id)»; the outcomes of `epoch_floor` (P/01.3) |
| 28 | contender marks: an unreadable `gen` of a given name — `waiting`; the name is occupied by an unreleased row of another box — `refused` with `holder`, `holder_box`; no `worker.name_taken` (coverage audit P/03, second pass) | N1.4a, N3 «nobody and getting the name back», N4 |
| 29 | a second copy of the same box took the name: the first one has the mark `nameless`, one `worker.name_taken`; the displacing one is stopped — the first one gets the name back (`gen` 3) and writes `worker.name_back` (coverage audit P/03, second pass) | N1.4a, N3 «nobody and getting the name back» `rejoin()` (rejoin()); the event log contract `journal` |
| 30 | free forms of the slot row: `released: taking` of a foreign box and `released: false` with an empty `holder` — a capture with `gen + 1` and its own `server` (coverage audit P/03, second pass) | N1.4, N3 «capture» (the transition table); the slot contract `taking` |
| 31 | the decommission mark of the subsystem `testsub/decommissioned/srv-a`: the worker `testsub` is nobody, without a slot, heartbeat and marks; the worker `testsub2` of the same server takes the name; the mark removed — the name is taken (coverage audit P/03, second pass) | N3 «start()» step 3, N1.4a |
| 32 | the row `platform/decommission/srv-a` not in form: no name until it reads; the row removed — the same worker takes the name (coverage audit P/03, second pass) | N3 «start()» step 3; the outcomes of `decommission` |
| 33 | a capture of a released slot of a foreign holder deletes the contributions of the predecessor under this slot (`notes`, `rolls` of the books of `testsub2`) before `released: false`; the contribution of a foreign slot is intact (coverage audit P/03, second pass) | N3 «capture» step 4; chapter 3.7 N1.2 `claim` |
| 34 | a foreign place with a torn hold row is taken neither at once nor after `LOST_AFTER + HOLD_SKEW`; a free place is taken (coverage audit P/03, second pass) | N3 «place: take, hold, let go» `take_slot` (take_place); the outcomes of `holds` |
| 44 | a place of another name: the holder is killed, its heartbeat is unreadable (`@spoil object`) — while the hold row is effective, the place is not taken (the row of the same version after 30 s); the row stood `LOST_AFTER + HOLD_SKEW` — the place is free by the row, the heartbeat is not read, it is taken with `gen` 2 (C06-UNHELD-PULSE-UNREAD-01; the draft G05c of the second pass of the coverage audit) | N3 «place: take, hold, let go» `take_slot` (take_place); the outcomes of `heartbeats` (chapter 3.4 N1.1) |

### `Platform/03-worker/spec/03.3-worker.norms.md` P/03.3-R005

old-sha256: 6792a54b2a9730cfebaef7a3f8372a5b3bb35c56183a8936f48287663c5a03f7

<!-- req: P/03.3-R005 -->

Settings are [runtime-constants.tsv](../forms/runtime-constants.tsv); WAKE_GAP_MS / 1000 gives seconds without rounding.

```yaml
loop:
  # LEASE_TTL, LEASE_MARGIN, LEASE_EVERY, again — the lease timings, chapter 3.2 N1.2
  # HEARTBEAT_EVERY, PASS_SHARE, RETRY_MIN, RETRY_MAX: runtime-constants.tsv
  POLL: implementation choice for an idle pause or long polling, not a fixed period
  WAKE_GAP: WAKE_GAP_MS / 1000  # exact seconds; an event pass is no earlier than this gap
  # and no more often than PASS_SHARE pass durations for long polling
watchdog:
  notify:       from the loop, not from the stand-in; WatchdogSec of the unit is the contract of the environment file «Constants and units» («A-16»)
retry:          # the backoff of repeating a failed start of a unit (ADR-0091 item 6; M10B/02:182–264, M10B/04:576–590)
  rule:         the pause grows exponentially from RETRY_MIN to RETRY_MAX with mandatory jitter (the form of the exponent and
                the jitter — «Implementation decides» item 3); only failures of the start and of the work of a unit count — a move,
                fencing and a new name do not change the count; the count is reset on any of three: after RETRY_MAX of continuous
                stable work, by the word of the subsystem (its answer «stable»), when the unit is confirmed absent from the desired
                (the assignment) — an unconfirmed read of the assignment is not absence; a move does not count as a failure, and a unit
                that has left the worker resets the count by the third condition (C03-RETRY-RESET-01)
  stalled:      the pause has reached RETRY_MAX — status[].stalled: true in the heartbeat (chapter 3.4 N1.1) until the count is reset; the subsystem asks with the library word stalled(id) (chapter 3.1 N2)
```

### `Platform/03-worker/spec/03.3-worker.norms.md` P/03.3-R008

old-sha256: a4207d6c52ab7dfa3e2c74e1ff028ebe1c838156c2a0c784b9fde431ea8f4baa

<!-- req: P/03.3-R008 -->

```
1. if nobody or not writing_allowed: «rejoin()» (chapter 3.2 N3 «nobody and getting the name back»);
   no name obtained → only the search/the rival's mark and waiting; do not run steps 2–5
2. the reconciliation pass: read the assignment; an assigned unit without a row or with a tombstone is not started until the next
   pass (the placement row is the controller's business); for each assigned unit that is absent: open the secrets
   (chapter 3.5 N3 «open»: not opened — Sealed, do not take the epoch; reconciliation of python and go M10/6–11, S19) → «take_unit_epoch» →
   check the gate and may_act again immediately before start_unit; a refusal → do not start;
   a led unit absent from the assignment → cancel its unfinished starts, stop_unit;
   revision grew → with the gate open and may_act, accept the restart attempt: stop_unit (the subsystem learns it by the word restarting(id), chapter 3.1 N2) and start
   under the same epoch/lease through the local transition of chapter 3.2 N3 «take_unit_epoch», without a new issue and without resetting last;
   otherwise the change of revision waits, the former unit runs only while may_write allows;
   born changed (the row was deleted and created anew — a new life, the row check contract, born; ADR-0091 item 3) → stop_unit, release
   the epoch and take it anew — a new issue, new bindings of (ADR-0013), as for a deleted and created one (sc. 06); the state
   of the unit the new life writes with its own born and revision (chapter 3.6 N1.7);
   a crashed process of a unit (an answer of the subsystem) → a raise under the same epoch (chapter 3.2 N3 «take_unit_epoch(unit)», raise)
   after the retry pause of N1.2;
   the row of an own unit does not read by its type (the row check contract «Unit row») → a started unit runs with the last read row,
   `why` of the heartbeat element — «row unreadable: <reason>»; a unit never read is not started, the epoch is not taken, the heartbeat
   element is {id, phase: "unreadable", the same why, revision?} without epoch and observed_revision (revision — if the revision of the row
   reads; chapter 3.4 N1.1; the stage C guess W03-G05, the Architect's decision of 2026-10-23); each
   such read — `garbled_rows` of the heartbeat + 1 (chapter 3.4 N1.1); a read of the assignment or of rows broken off by an error —
   `pass_failures` + 1 (the VMS request «heartbeat and a garbled row», the Architect's decision of 2026-10-23);
   a lost lease is stopped by «lease_step»; each unit in its own attempt
3. the pump: events (`append`, the contract of the object store client `ops`), requests (chapter 3.6 N3 «holder's look»), commands (the marks
   `objects/<sub>/commands/<rid>`, P/06.4 N1.5 `mark`)
4. if clock − start_of_previous_lease_step ≥ LEASE_EVERY or again: «lease_step()» (chapter 3.2 N3)
5. if clock − previous_heartbeat ≥ HEARTBEAT_EVERY: the heartbeat (chapter 3.4 N1.1)
6. watchdog notify; a pause until POLL or until an event (long polling)
each step in its own attempt and under the marker guarded(step name) for the stand-in (chapter 3.4 N3 «stand_in()»)
```

### `Platform/03-worker/spec/03.3-worker.norms.md` P/03.3-R009

old-sha256: e87ff9dd78dd73f8bc0ab9d0399424008097bdca77821c0f0b485c4434d45084

<!-- req: P/03.3-R009 -->

**Races.** One loop thread, but the stand-in can lose the name/fence the worker while the epoch issue or
start_unit has not returned. A start and fencing agree through the local transition ([chapter 3.2](03.2-worker.norms.md) N3 «take_unit_epoch»); the CAS of the store
does not protect the state of the process. The stand-in writes the heartbeat, the slot, the leases and the place under the same `cas`.

---

### `Platform/03-worker/spec/03.3-worker.norms.md` P/03.3-R010

old-sha256: 5fd092f8581eafad8c51811cbb084774566828dff545b9c08b3dce613fe6e8f1

<!-- req: P/03.3-R010 -->

The chapter has no N4 rows of its own: the refusals of the loop steps belong to their procedures: the lease step, the gate «take_unit_epoch», «nobody» — [chapter
3.2](03.2-worker.norms.md) N4; the stand-in, a write under the slot, the stop — [chapter 3.4](03.4-worker.norms.md) N4.

---

### `Platform/03-worker/spec/03.4-worker.norms.md` P/03.4-R003

old-sha256: 00dfd688279b4d7c032288791222e1d886165344d078992fe8a959658b2472a6

<!-- req: P/03.4-R003 -->

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `<sub>/heartbeats/<name>`;
- writes: `<sub>/slots/<name>` (cas), `<sub>/holds/<place>` (guard), `<sub>/<manifest:tables>/<name>` (cas);
- reads: `platform/manifest/<sub>`, `platform/doors/<host>` (the object client at a bare cluster:// — the object store client contract door; V7 item 3, the Architect's decision 2026-10-28, P3; row 11 of the list), `platform/manifest/<sub>/rev` (the mark: manifest change — P/02.3 N3), `platform/manifest/<sub>/canonical/1` (the worker runner takes the worker program — P/02.3 N3 «The worker program from the row»; V7 item 3, the Architect's decision 2026-10-28, P3; rows 18, 19 of the list), `<sub>/epoch/<id>`, `platform/schema`, `door/keys`, `/etc/w2c/tls/<role>/server.key`, `domain/member-list/<part>` and `domain/<sub>/<manifest:domain.books>` — by worker.reads (N1.7 door_admission, cross_cluster: the CAs of the members for checking a mixed door of another cluster; the copy of the assignment book — for the decisions of the subsystem, freshness by its field missing; ADR-0091 addendum (13) item 5, addendum (15) item 6, addendum (18) item 2), `domain/holder`, `domain/shared`, `domain/shared-docs/rev-<rev>`, `domain/view`, `domain/member-topology`, `domain/topology` (by worker.reads of the subsystem; C08-CATALOG-TOPOLOGY-READERS-01).

### `Platform/03-worker/spec/03.4-worker.norms.md` P/03.4-R006

old-sha256: 5a3eddab0d267dbc343a0ad53e2f20a17c5dd4410b6c562239fb37c641bf6515

<!-- req: P/03.4-R006 -->

```yaml
heartbeat:
  worker:    <slot name>                 # MUST; equal to the name in the key
  ts:        <wall seconds of the writer>  # MUST; for display and for the clock divergence, not for freshness (ADR-0049)
  status:    # MUST; one element per unit that the worker runs
    - {id, phase, epoch, revision, observed_revision, why?, lease?, unconfirmed_s?, …words of the subsystem}
    - {id, phase: sealed, why, revision}                                  # the unit is sealed (chapter 3.5 N3 «open»):
                                                                          # no epoch is taken — epoch and observed_revision
                                                                          # are absent both at a unit sealed for the first time and at
                                                                          # one that has been running; revision — of the read
                                                                          # row; not a claim on the unit (P/08.1 N1.6 claim)
                                                                          # and not «running» (P/06.5) (W03-G02)
    - {id, phase: unreadable, why, revision?}                             # the row has never been read by its type (chapter
                                                                          # 3.3 N3 step 2): no epoch is taken — epoch and
                                                                          # observed_revision are absent; why
                                                                          # «row unreadable: <reason>»; revision — if the revision
                                                                          # of the row is readable; not a claim and not «running» (W03-G05)
                                                                          # lease: unconfirmed and unconfirmed_s — the seconds without
                                                                          # a confirmation of the lease (chapter 3.2 N1.6 silent), with
                                                                          # a precision of 0.1 s, — only while the lease is not confirmed;
                                                                          # observed_revision — the revision of the row
                                                                          # under which the unit is running now; why — the reason
                                                                          # of the platform when the unit is not running (sealed — chapter 3.5
                                                                          # N3 «open»), like fates.why of P/04, not error
                                                                          # (the second pilot, «N-7»)
    # the teaching handler testsub: the subsystem word is one — n, the current value of the counter (the book tallies of the manifest testsub
    # shows n); the element has no other words (the second pilot, «N-7»)
  server:    <nonempty server> # SERVER_NAME admission precedes presence lock, by the input form
                                         # (stage C guess W03-G01, the Architect's decision 2026-10-23)
  instance:  <instance>                  # MUST
  labels:    <node labels, comma-separated>
  fetched:   <SaidID(rid), comma-separated, without spaces>   # the requests whose outcome the holder has reported (chapter 3.6 N3 «holder's look»);
                                     # no field or empty — nothing is reported; the length is bounded by FETCHED_COUNT/FETCHED_BYTES (the request mark contract «fetched»)
  <capacity.from>:  <capacity>            # the field name — from manifest.placement.capacity.from (default capacity); when known
  <headroom.from>:  <headroom>                # default name headroom; the base computes capacity − Σ of the assignment weights, the subsystem MAY say its own value, the base does not overwrite it, like schema, build; the controller does not read the field (C03-HEADROOM-SAY-01); the weight of each unit — by
                                     # the pool contract weight, as at the controller (layout audit, the Architect's decision 2026-10-25, «A-12»): the field weight.field of the row read by the last reconciliation,
                                     # no field — weight.default, no placement.weight — 1; the field is not a number — the unit does not enter the sum
                                     # (the controller does not place it, P/04)
  <place_by>:  <place>                 # only when the manifest declared place_by — a heartbeat field (P/02.1 N1.2, P/04 «distinct»):
                                     # the name of the place that the worker holds (chapter 3.2 N3 «place»), "" — holds none; written by the base, not by the subsystem
  conflicts: <integer> # current units lease-conflict total + conflicts_carried of forgotten units, without double counting
  started:   <the start moment>
  previous_hb, previous_instance, previous_server:  # what the worker found under its name at start, if there was anything: previous_hb —
                                         # the number ts of the found heartbeat, previous_instance and previous_server — its instance and server
                                         # (the cammeta-go journal, lesson 9 № 6: by them the console computes failover_seconds, P/06.5 N3)
  fenced:    true                        # only while fenced and the name is still mine; after «release_name» the heartbeat is not written
  was_fenced:    true | false            # whether this instance has been fenced since launch; the series worker_fenced{worker} of P/06.5
  store_errors:  <number>                # requests to the store without an answer or with an error since launch (chapter 3.2 N4: store_errors + 1)
  pass_failures: <number>                # reconciliation passes (chapter 3.3 N3 step 2) cut short by a read error, since launch
  unconfirmed:   <number>                # units whose lease is not confirmed now (the elements of status[] with lease: unconfirmed)
  garbled_rows:  <number>                # reads of the rows of its own units not read by their type (chapter 3.3 N3 step 2), and of the rows
                                         # of requests and marks not read by their form by the holder (chapter 3.6 «holder's look»; RM-G01), since launch
  place_error:   {<place>: sealed | refused | wrong}   # the place is not taken or is lost (chapter 3.2 N3 «place: take», chapter 3.5
                                         # «open»): sealed — the secret of the place row did not open, refused — a refusal of the subsystem,
                                         # wrong — the place row is not by the form; a closed list of words; the record is removed
                                         # when the place is taken or let go; there are no more records than candidate places;
                                         # place_by — as before; a change of the row of the held place — reread and open anew
                                         # (ADR-0091 addendum (10) item 4; the Architect's decisions on the repeated review of addendum (10), 2026-10-23)
  freeing:       {<resource volume>: <bytes, an integer ≥ 0>}   # the answer of a subsystem worker with requests.free to a resource request of its own
                                         # server <sub>/requests/free-<server>-<volume> (P/05 N1.4 free_ask): while the row stands —
                                         # the bytes that it frees and that are not yet reflected in used; 0 — frees nothing;
                                         # what to free — the subsystem; no field — 0 (VMS request freeing, the Architect's decision 2026-10-23)
                                         # the base worker writes the five fields above always, at zero too; the series of P/06.5 come from them;
                                         # passes, assignment_rev are not introduced by the norm (VMS request «heartbeat and a garbled row», the Architect's decision 2026-10-23)
  schema, build, pending_writes:         # added by M10/10 (P/06.6 N1.1a heartbeat: schema, build; N1.2 pending_writes) —
                                         # the base worker writes schema := SCHEMA and build := BUILD (default dev); pending_writes := 0 when the subsystem did not supply it; no pending_writes field — the drain is not safe
  stood_in:  {step, for, as_of}          # only in a stand-in heartbeat (N3); as_of — ts of the last heartbeat of the loop that the stand-in
                                         # repeats (the age of the subsystem state), the same at the next repeats; ts of the heartbeat —
                                         # the time of this repeat (the cammeta-go journal, lesson 5 № 2)
  stand_in_renewals: <number>            # only when > 0
  # the tallies of the holder and of the orderer (ADR-0091 items 1, 6, 7; the witness names); each field — only when it holds a non-zero value:
  command_counts:  {performed, refused, expired, unknown}   # the outcomes of action calls by this instance since its start
                                         # (chapter 3.6 N3 «holder's look»); the metric — command_counts.<outcome>
  commands_in_flight: <number>           # action calls not yet returned (chapter 3.6: not more than one per group)
  commands_reanswered: <number>          # outcomes written again (a late answer after unknown — late)
  command_road:    {<by>: <histogram>} # the road: from at of the request row to its first local observation by this worker (W03-E05; the ends — the Architect's decision 2026-10-23);
                                         # by — operator or the subsystem of the filer
                                         # (the first part of the stamp by «<sub>/<unit>» of a request filed by a worker, chapter 3.6 N1.5)
  command_request: {<by>: <histogram>} # the full time: from at of the request row (the filing time) to the outcome; from filed (the instance row) the time
                                         # is not derived (stage C guess W03-E05, the Architect's decision 2026-10-23)
  command_wait:    <histogram>         # the wait at the holder: from the first local observation of the request by this worker to the outcome, by the
                                         # monotonic clock (W03-E05; the ends — the Architect's decision 2026-10-23); command_request ≈ command_road + command_wait
  filings:         {filed, again, refused}   # the filing of requests by the worker (chapter 3.6 N1.5): filed; the same filed again; not filed
  creates:         {<outcome>: <number>}  # the ordering of rows of another subsystem (chapter 3.6 N1.6), a closed list of outcomes:
                                         # created, extended, unchanged, taken, gone, expired, refused («G-7»)
  made_rows:       {<A>/<rows>: <number>} # the orderer: keys under the prefix <A>/<rows>/<C>- by the last listing (not more often
                                         # at least MADE_ROWS_MIN_INTERVAL between listings; no upper deadline; tombstones and taken rows included
histogram:   # the form of a heartbeat histogram (the witness names)
  buckets:   [<count>…]                   # one per boundary of ROAD_BUCKETS, the count of observations not greater than the boundary (cumulative)
  sum:       <sum of seconds>; count: <number of observations>
  ahead, behind: <number>                # only at command_road, command_request: the clock of the writer ahead (seconds < 0 — counted as 0)
                                         # behind: filing earlier than the listing that did not see it by strictly more than COMMAND_BEHIND_TOLERANCE
  ROAD_BUCKETS: [0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 300]
stalled:     status[].stalled: true      # a unit whose launch backoff has reached RETRY_MAX (chapter 3.3 N1.2 retry); otherwise there is no field
said_id:     # the request name in fetched — the request mark contract «fetched» `said_id` (moved there without change; layout audit «A-24», «B-02», the Architect's decision 2026-10-25)
phase:
  rule: words of the subsystem; the platform knows three — running (the counter running, the neighbourhood near), sealed (W03-G02) and unreadable
        (W03-G05) — the elements above
cadence:
  # HEARTBEAT_EVERY: runtime-constants.tsv; first before the first pass, last at stop
  fresh_for: LOST_AFTER          # the observation contract «Freshness» (the value is there; layout audit, the Architect's decision 2026-10-25, «A-01»); the reader judges by the change on its own clock
nobody: no heartbeat is written while the worker is nobody
platform_strings: [worker, server, url, instance, labels, fetched, events]   # heartbeat.strings does not name them;
                  # url — added by M10/9 (P/06.5 N3 «/where/<id>»: the url of the door); fetched — added by M10/8 (chapter 3.6 N3 «holder's look»)
```

### `Platform/03-worker/spec/03.4-worker.norms.md` P/03.4-R007

old-sha256: 50dede850003f0007de8c06697070d769b3e4d90e890fa6ca2adca6136af8a79

<!-- req: P/03.4-R007 -->

The current worker resolves SERVER_NAME by the process-input form before the presence lock. An empty or invalid value gives the existing startup refusal, exit 2: this start has no lock, capture or heartbeat. A running worker heartbeat carries its resolved nonempty server; BOX_ID and instance are different identities and do not replace it.

### `Platform/03-worker/spec/03.4-worker.norms.md` P/03.4-R010

old-sha256: ff4919a687bcbd7fb2b46f66bb5ef78d8eceea8956e7939a7376c5285e0c976e

<!-- req: P/03.4-R010 -->

```yaml
stand_in:
  STALL: (LEASE_TTL - LEASE_MARGIN) / 2 # a step is stuck strictly beyond this duration
  WAKE: <= (LEASE_TTL - LEASE_MARGIN) / 4 # upper bound, not required equality
  FOR:          the environment file contract «Constants and units» (the value is there; layout audit, decision of the Architect 2026-10-25, «A-16»)   # s; it does not stand in longer: the units go
  # BEAT_EVERY: runtime-constants.tsv, stand-in heartbeat repeat
memory:
  rule: CAPACITY × unit_mb + base_mb ≤ WORKER_MEMORY_MB, otherwise the process does not start (ADR-0070); without unit_mb, CAPACITY or WORKER_MEMORY_MB — not checked, the capacity — capacity.default: a worker on the domain has no role file, there are no values (C03-MEMORY-NO-ROLE-01)
        # one budget formula per module: CAPACITY — the capacity of the worker in weight units (the pool contract capacity),
        # unit_mb — MiB per weight unit, base_mb — MiB of the process (none — 0), WORKER_MEMORY_MB — the environment of the process
```

### `Platform/03-worker/spec/03.4-worker.norms.md` P/03.4-R014

old-sha256: c38b20b4bc5588ee09cfa3bffd7e413ffac4cd3046b212a2f775c3dd88729198

<!-- req: P/03.4-R014 -->

Door settings are [runtime-constants.tsv](../forms/runtime-constants.tsv); PACE_FLOOR uses the byte numerator per one second.

```yaml
# DOOR_* are independent owned rows in runtime-constants.tsv.
door_limits:
  PACE_FLOOR: DOOR_PACE_FLOOR_BYTES per second  # measured after DOOR_PACE_AFTER
  busy: a connection beyond DOOR_CONNECTIONS or DOOR_PER_ADDRESS - 503 {error: "busy"}, no queue; Retry-After is process_busy in forms/refusals.tsv
  slow: incomplete request line/headers at DOOR_HEAD_WITHIN, or average pace below PACE_FLOOR after DOOR_PACE_AFTER - cut the connection, no answer
  body: DOOR_BODY_BYTES; larger - 413 before reading when the header proves it
  other: a door needing different settings names them at its own lesson; no manifest setting
```

### `Platform/03-worker/spec/03.4-worker.norms.md` P/03.4-R019

old-sha256: 029c701f8650f0a49b9d557dbf5068dbcdc72cfce8b72d46d22d2ca4f17315dd

<!-- req: P/03.4-R019 -->

```
a step of the loop: STALL < age <= FOR, the worker is not nobody and writing_allowed:
  renew the slot first by a write with cas — only while the row names me and is not released (the store did not answer — still me;
  a foreign holder or released → fence everything, as in the lease step, stop the stand-in; renewed → the same schema check as in
  the lease step, step 1); then renew each lease —
  by a confirming read of the epoch row (chapter 3.2 N3 «confirm»), nothing is written;
  renew the hold of a strict place by a write with cas under the guard of its own slot (review analysis of stage B 3–5, № 4), as in the lease step (chapter 3.2 N3 «place: take, hold, let go»): a read does not
  renew the hold term;
  heartbeat: repeat the last heartbeat of the loop with a new ts, stood_in: {step, for, as_of}, stand_in_renewals —
  not more often than BEAT_EVERY and only if the loop itself has not written
the step runs longer than FOR: done; the journal is "no longer standing in for it (FOR " + decimal(FOR) + " s): its units go";
  the leases that can no longer act — stop their units one by one
age <= STALL: no stand-in actions. the stand-in never revives a fenced one and does not call watchdog
```

### `Platform/03-worker/spec/03.4-worker.norms.md` P/03.4-R021

old-sha256: b80f0fb0b1a6bd8a27f980df181f4a0c342cdb397a913061d34df4ccbfcbaefa

<!-- req: P/03.4-R021 -->

**Races.** The stand-in and the loop renew one slot row: the slot lock is non-blocking, whoever did not take it skips; `cas` insures against a write over a foreign capture. The loop has returned from a stuck step: `take_unit_epoch` is refused in it (the step outlived the stand-in) until the loop reads the assignment anew.

### `Platform/03-worker/spec/03.4-worker.norms.md` P/03.4-R025

old-sha256: 425138a4cbededd3d102be330158007b2bcd865b22f9d2682bd50071c537acc8

<!-- req: P/03.4-R025 -->

**Races.** The stop against the stand-in: the stand-in stops first, then the place is let go and the slot is given away. The place
is let go before the slot is given away: one may not write under a given-away slot (chapter 3.2 N3 «write_under_slot»), and a place not
let go before the hand-over is held up to LOST_AFTER + HOLD_SKEW (review analysis of stage B 3–5, № 4); the stop against the lease step — the step is brought to the write or interrupted before it, the hand-over is one; SIGKILL — nothing is written (sc. 05 of [the acceptance of chapter 3.2](../acceptance/2/README.md)).

### `Platform/03-worker/spec/03.5-worker.norms.md` P/03.5-R009

old-sha256: e1a0228bac84f63d398a76b9456a94a7228dbc6ca23feb8cbe159eab83ded821

<!-- req: P/03.5-R009 -->

```
before «take_unit_epoch» (chapter 3.3 N3 «loop», step 2): read the row; for each *_secret at any depth: not an envelope → as
is (a value written by the current development mode without SECRETS_KEY); an envelope → open with the key kid with the single AAD of the sealing contract of the row and the full path; do not try old ways
  no key (SECRETS_KEY not set) / a foreign kid / does not open    → Sealed: do not take the epoch, do not start the unit; the
                                                                     status element — {id, phase: "sealed", why, revision}: why "the
                                                                     password does not open: <reason>" (P/06.2 N1.4 heartbeat)
                                                                     (reconciliation of python and go M10/6–11, S19, S2); there are no
                                                                     epoch and observed_revision, revision — of the read row
                                                                     (chapter 3.4 N1.1; the stage C guess W03-G02, the Architect's decision of 2026-10-23)
the value — only to the recipient (the driver, the client); in memory, the heartbeat and logs — the envelope
the place (chapter 3.2 N3 «place: take», «hold»): on taking a place and on a change of the row of a held place — open the *_secret
of the row of the place table by the same rule and with the same AAD of the sealing contract (the key of the table row and the full path) as the unit
row; Sealed → the place is not taken (a held one — leaves the place, leave_place of chapter 3.2 N3 «hold»; released is not written, C03-PLACE-SEALED-LEAVE-01), place_error.<place>: sealed in the heartbeat (chapter 3.4 N1.1),
the cause is at the place, not at the unit; the opened value — only in memory and in the subsystem call (ADR-0091 addendum (9) items 5–6, addendum (10))
```

### `Platform/03-worker/spec/03.5-worker.norms.md` P/03.5-R010

old-sha256: 4dc9c33464984ca827d8c3d15f8651cd3ef994e89d8d3675086a8efefdfeff0c

<!-- req: P/03.5-R010 -->

Step 2 of the loop is [chapter 3.3](03.3-worker.norms.md) N3 «loop», `take_unit_epoch` — [chapter 3.2](03.2-worker.norms.md) N3; AAD — the
[sealing contract](../../common/contracts/sealing.md) «AAD path»; `why` of the `status` element of the heartbeat — [chapter 3.4](03.4-worker.norms.md)
N1.1 and [P/06.2 N1.4](../../06-console/spec/06.2-console.norms.md) `heartbeat`.

### `Platform/03-worker/spec/03.6-worker.norms.md` P/03.6-R012

old-sha256: ef5b582e83664361a4e733e8a62ed00c9e4fff09f8b71ce4b6bcdb3f246be11e

<!-- req: P/03.6-R012 -->

Holder settings are [runtime-constants.tsv](../forms/runtime-constants.tsv). PERFORM_GRACE and REQUESTS_HOLD are exact seconds via /1000, not new settings.

```yaml
# PERFORM_TIMEOUT, COMMANDS_PER_LOOK: runtime-constants.tsv
PERFORM_GRACE: PERFORM_GRACE_MS / 1000
REQUESTS_HOLD: REQUESTS_HOLD_MS / 1000
```

### `Platform/03-worker/spec/03.6-worker.norms.md` P/03.6-R015

old-sha256: 76af7623fb165952b0c4ff5076f489df88ebe9de449703d63c8cb277f5993d10

<!-- req: P/03.6-R015 -->

```yaml
order:       an event E that a unit U of the customer executes under its own epoch (the holder of U, P/03.2): the event time t_E —
             Unix seconds by the clock of the event's writer; the fields F of the row of A — without the id source field of A, without *_secret and blob
id:          <C>-<key(F)>                    # the prefix is not chosen
key:         the template worker.creates[].key — substitutions {field} joined by «-»: {field} — the value F[field] in the notation values_by_type
             (the row check contract: string, url — as is; int — decimal; float — its choice rule; bool — true | false),
             then every UTF-8 byte of this notation outside A–Z a–z 0–9 _ . ~ — %XX, hex digits in upper case (`-` → %2D,
             `%` → %25); between substitutions — the literal «-»; different values of the fields give different ids, so the id determines these
             values: a returned name is the same subject (ADR-0067); vectors creates-key
born:        a new random value at creation (the row check contract, born)
made, ORDER_HORIZON, not_after, tombstone: the row check contract «Customer row: made» — `made` (keep), `ORDER_HORIZON`,
             `not_after` of the order write, the tombstone window of the row-check contract, The customer’s row: made (moved there without a change; layout audit «A-11», the Architect's decision of 2026-10-25)
fields:      the row is created by the row check contract «Preparation of fields», as at the door: what is not passed — default or the empty form of the type; the id source field —
             with the ready id; *_secret are never written — they stay empty, the secret is set by the operator through the door («G-8», the
             Architect's clarification of 2026-10-22); blob are empty (P/06.1 N1.5)
until:       the deadline field of the addressee — placement.ends.field of the manifest of A (P/04 N1.3), if ends is declared; extension — max(the previous,
             the new); a previous = never (without a deadline) is not touched
ends_past:   a row whose deadline by the field ends in F has already passed (≠ never and ≤ now by the holder's clock) is not created
deletes:     the worker of the addressee deletes a row with made by worker.deletes (the library) — by the rule of the row check contract
             «Customer row: made» `delete` (layout audit «A-11», the Architect's decision of 2026-10-25); a row without made — as before (cas of the read version)
guard:       every write — CAS of its own row and guard {key: C/epoch/U, index: the version of the epoch row confirmed at the taking of the
             epoch} in one operation (P/01.1 guard: index — the version of the row, not the epoch number), and only while may_write
             (P/03.2 N1.6; «S-4»: after the store is restored, the guard version can coincide — the lease checks the floor)
writers:     the order row has two writers (P/06.1 N1.1): the operator — through the door, any fields except the fields of key (P/06.1 N1.3
             made_key); the customer — only rows of its own made (made.by = C); a row of its own made may be extended by any
             unit of C; a row without its own made is taken: C does not write it
check:       the common row check — the row check contract (P1–P5, R1–R3), the same as at the door; its reads are derived from the
             declaration (the rights — P/02.5 N1.4)
outcomes:    created | extended | unchanged | taken | gone | expired | refused   # the count — the heartbeat of C, P/03.4 N1.1 creates
```

### `Platform/03-worker/spec/03.6-worker.norms.md` P/03.6-R018

old-sha256: a458a31eafac5a9dfccd30e29368176784fa7af961093ec64e21704a610b142f

<!-- req: P/03.6-R018 -->

The key/items/guard constructor is [row-write-bindings.tsv](../forms/row-write-bindings.tsv), by the [form grammar](../forms/row-write-bindings.md). The start snapshot is immutable: born/revision/epoch and the guard version come from the accepted start, never a newer read. Reading the state CAS version and performing IO remain procedure R029.

```yaml
row:         constructor state in forms/row-write-bindings.tsv; the family is state.schema.json
writer:      only the holder of the unit: CAS of the read version of the state row ("" — there is none) and guard {key: <sub>/epoch/<unit>,
             index: the version of the epoch row confirmed at the taking} in one operation, while may_write (P/03.2 N1.6; «S-4»);
             born and revision — of the start, not of the re-read unit row: a cut-off holder, also by a late replay,
             will not overwrite the state of the new epoch
acts:        the row check contract «Unit state» `acts` (moved there without a change; layout audit «A-05», the Architect's decision of 2026-10-25)
cursor:      unit.state.cursor acts by born (revision is not compared: an edit of the row does not reset the cursor); monotonic —
             the meaning of the value is set by the subsystem; written not more often than STATE_EVERY; survives a move
STATE_EVERY: runtime-constants.tsv # state write cadence
unreadable:  the row check contract «Unit state» `unreadable` (layout audit «A-05», the Architect's decision of 2026-10-25)
delete:      the holder does not delete the state; the controller deletes it — after a confirmed delete of the unit row and by the cleanup
             of the orphaned (P/04 N3); it is read by the console (P/06.1 N2 «State in the answer») and by the controller (P/04 N1.3, N1.3a)
```

<!-- families:begin -->

### `Platform/03-worker/spec/03.6-worker.norms.md` P/03.6-R025

old-sha256: 20c5c99d90b6535fe9313a6b2de752ca13248473daf38136b62dd21a5d3a2526

<!-- req: P/03.6-R025 -->

Device action (ADR-0091 item 6; a new norm from M10B/04:223). Within one holder (one process epoch), not more than one unfinished call of an action per group
of the unit (`placement.group_by`, [group by host contract](../../common/contracts/group-of.md); the target of the call is the group, so the targets are placed together, ADR-0011), also after
`unknown`: while a call into the group has not returned, there is no second one into it. The memory of the call is with the process, so a new holder of a group makes its first call into it not earlier than `PERFORM_TIMEOUT` + `PERFORM_GRACE` from the taking of the epoch of its first unit, if this epoch is not the first: a call of the previous holder could still be going; the request waits, its deadline runs (C03-GROUP-TAKEOVER-WAIT-01, the Architect's decision of 2026-11-01, review of the VMS invariants). «Device not open» is the subsystem's answer «not ready»
(`refused` with a reason), not a delayed call. The fixed wait is not proof that a previous holder call has physically finished: after a holder change, calls of two holders can overlap, even after unknown. This risk is explicit; no cross-holder exclusion is promised. A subsystem SHOULD provide epoch fencing. If the action receiver accepts an epoch, it MUST reject a call carrying an epoch lower than the last it has seen. Losing an epoch prevents the old holder new admissions and guarded writes; it does not prove cancellation or completion of an already sent call. The two-holder late-return seam records overlap_possible_marked without inventing an IO or cancellation guarantee. Calls go outside the loop thread; leases are held with all targets hung
(ADR-0037). For a unit of assignment without an epoch — first take the epoch ([P/03.2](03.2-worker.norms.md) N3 «take_unit_epoch(unit)»,
M10B/04:257); the start of the unit inherits this epoch without a new issue ([P/03.3](03.3-worker.norms.md) N3 step 2).

### `Platform/03-worker/spec/03.6-worker.norms.md` P/03.6-R027

old-sha256: 27d83077a726ba6a601a894daf281ab8c2ca976cf30743922ac56908b7cf793e

<!-- req: P/03.6-R027 -->

1. If the manifest of A is not in the manifest catalogue, the outcome is `refused`.
2. If now − `t_E` > `ORDER_HORIZON`, or the field ends of A in F ≠ never and ≤ now, the outcome is `expired` (no write).
3. Let id := C + "-" + key(F) (N1.6 key); if id is not by the row check contract «Identifier and field constraints» or the key A/rows/id is not by P/01.1 N1, the outcome is `refused`.
4. Read A/rows/id:
   1. If there is no row: build the row `{id, revision: 1, born: new, made: {by: C, at: t_E, keep: t_E + ORDER_HORIZON + 120}, …}` with
      the fields by N1.6 fields; if the common row check (the row check contract, creation P1–P5) refuses, the outcome is `refused`;
      write with `cas ""`, the guard of N1.6 and `not_after` given for this t_E by the row-check contract, The customer’s row: made, not_after, the outcome is `created`.
   2. If it is a tombstone of its own made with `made.gone` and t_E admitted by the row-check contract’s tombstone condition: the row as above, the revision of the tombstone + 1, a new born;
      if the common check (creation over a tombstone: the same fixed) refuses, the outcome is `refused`;
      write with `cas` of the version of the tombstone, the guard and `not_after`, the outcome is `created`.
   3. If it is another tombstone (its own without gone, or an event not admitted by that tombstone condition), the outcome is `gone` (no write).
   4. If there is no made or made.by ≠ C (a live row or a tombstone), the outcome is `taken` (no write).
   5. If it is its own, the new values are: the field ends of A — max(the previous, from F), a previous = never is not touched; made.at — max(the previous, t_E);
      made.keep — max(the previous, made.at + ORDER_HORIZON + 120).
      1. If the values (including made.at, made.keep) do not change, the outcome is `unchanged` (no write).
      2. If the common row check (the row check contract, edit R1–R3 of the changed fields) refuses, the outcome is `refused`.
      3. Write `{…row, …new, revision + 1}` with `cas` of the read version, the guard and `not_after`, the outcome is `extended`.
   6. On `conflict` (cas), re-read from step 4; if the retry limit is exhausted, the outcome is `refused`.
   7. On `409 expired` (the admission time is later than not_after), the outcome is `expired`; do not repeat with the same write.
   8. On `412 guard`, the epoch of U is lost: no write, no order outcome; U — P/03.2 N3 «fence».
   9. On `unavailable` / `ambiguous`, repeat with the same write with the same write id (P/01.1 N4; P/03.4-07).
5. The outcome is counted in the heartbeat of C `creates.<outcome>` (P/03.4 N1.1).

### `Platform/03-worker/spec/03.6-worker.norms.md` P/03.6-R028

old-sha256: 362e871001ab5303700cb363b1a52cb8a9d3adc443d32bcaab3d2b2d74cda4f3

<!-- req: P/03.6-R028 -->

**Races.** Two units of C order one event: `cas ""` lets one through, the second re-reads and finds a row of its own
`made` — `unchanged` or `extended`. An edit by the operator between the read and the write is a conflict, re-read. A delete of the row
(the controller, the worker of the addressee, the operator) between the read and the write is a conflict; a re-read tombstone — `gone`; no row
(physically deleted) — step 4 creates it again only if the write is admitted not later than `not_after`: the physical delete of a
row with `made` is admitted not earlier than its the owner-defined `not_before` of this deleted life, which is >= `not_after` of any executable replay
(P/04 N3 step 8), and the store's admission time does not decrease — a late replay gets `expired`, however the wall clocks go. The cut-off of the epoch of U and a write in any
order: the write is made before the change of the epoch row or refused with `412 guard` (P/01.1 «Races»).

### `Platform/03-worker/spec/03.7-worker.norms.md` P/03.7-R009

old-sha256: cf0ff1bcc7574ea5d73df8294b18a1c09fd2b229c93b9e269987d7b27587df54

<!-- req: P/03.7-R009 -->

The local policy selector is [`token-cache.machine.yaml`](../forms/token-cache.machine.yaml), with its [traces](../forms/token-cache.traces.tsv) and [effect boundary](../forms/README.md#worker-policy-machines). Capture, IO and cryptography still follow the ordinary procedures below.


A worker's token is a domain token ([domain token contract](../../common/contracts/domain-token.md) «The token», owner P/08.2; review of stage B 3–5, V1) with `kind` of a kind of the manifest.
The holder's signing key is not handed to the worker, nor is the member's key: the token is requested by the worker that needs it, through the agent of its own
cluster (ADR-0074 addendum (5)). The token lives only in the worker's memory: not in a row, not in a book, not in a report, not in the log, not in a
copy. There is one exception — a kind with `keep: true` of the manifest (ADR-0110 addendum (9)): the worker also holds the token as the file `<worker state dir>/tokens/<kind>-<sha16(ref)>`, mode 0600, in an envelope of the sealing contract with the context of this path; the owner of the file is the kind, not the camera. At start it reads it, to work while the domain is silent. The term is judged by the receiver, not by the box clock: an expired file is not thrown away but is replaced after the refusal `expired`; the envelope did not open — as if there were no file. A new token replaces the file only after the first request accepted with it, until then both are in memory; while it holds a token with `current` it does not request; `unknown_key` on a token with `current` — it waits rather than requests (ADR-0110 addendum (10) items 5, 6). Such a token does not go into a row, a book, a report or the log either. The limit: theft of the box gives this token until revocation. The request is by the local door of the agent: [local token door contract](../../common/contracts/local-token-door.md) (owner
chapter 9.1; socket `<AGENT_TOKEN_DIR>/<W2C_ROLE>.sock`; review of stage A 8–10, № 1 / decision 1).

### `Platform/03-worker/spec/03.7-worker.norms.md` P/03.7-R011

old-sha256: 376c35838997f080d61678de389722fb4f43c4d1d264326615b662b08eafb7cb

<!-- req: P/03.7-R011 -->

```yaml
domain_worker:   the worker of a subsystem on the holder, role <sub>domain (the word of secrets.readers is domainworker, P/01.2 N1.1);
                 one: the slot domain/<sub>/worker (lease — chapter 3.2 N1.4); it exists for a manifest that has kept or a carried book;
                 the unit <dep>-<sub>domain.service — on every server with w2c-domain, one is active by the slot (P/02.4 N1.12);
                 the change of a dead holder: the spare captures the slot by cas on the version of the slot row that has not changed for
                 LOST_AFTER + HOLD_SKEW on the observer's monotonic clock (HOLD_SKEW — the observation contract «Hold of a place»), gen + 1 at a readable gen; only
                 for the slot of the domain worker — slots of the members of a cluster are not captured so (guess of stage C W03-E03, the Architect's decision of 2026-10-23)
carried_book:    domain.books.<book>: {} | {show} — the rows domain/<sub>/<book>/<member> at the holder are written by the domain worker;
                 the row of a former member (it is not in the member list) is deleted by the process domain in a pass, as for an assembled one
                 (P/08.5 N1.3 write; review of stage A 8–10, № 30); delivery, member_row and the door — as for an assembled one (P/08.5 N1.4; P/09.1 N1.4 member_row; the door — P/06.7 N1.1)
kept:            domain.kept: [<name>|<family>/…] — the rows domain/<sub>/<name> at the holder, written by the domain worker; they are not
                 delivered to a member; domain.tables — which of kept are tables (P/06.1 N1.6)
door_pass:       /domain/<sub>/<door.pass segment> of the domain console → to the domain worker (P/10 N1.6)
door_client:     the door of the domain worker under TLS accepts door.pass only from a client of the role domainconsole (the client —
                 P/10 N1.6); it requests the client certificate optionally and verifies a presented one in the handshake, as
                 the listener of SIGNER_URL does: does not chain to ca.pem or ca.next.pem of the cluster, its term has passed, extendedKeyUsage without
                 clientAuth — alert, no HTTP (the role certificate contract signer; ADR-0083 addendum (20), addendum (21) item 7); no
                 certificate, the role from SAN is not domainconsole, the signature of the leaf or of the CA outside the list sig, the serial in revoked —
                 403 {"error": "forbidden"}, the request is not executed; the worker does not verify people — the person's token was verified by
                 the guard of the domain console (the domain token contract: there is no row of the domain worker among the verifiers); over HTTP
                 of the stand there is no role — checked by reading, as X-W2C-Client (the forwarding contract «Client address»)
                 (the Architect's decision of 2026-10-20 on the reconciliation of 3.7); the client — the domain console — verifies the server of this door as
                 a client of its own cluster (the role certificate contract own_client, role <sub>domain; norms review of ADR-0075, Claude fd85ea8cc, «S-1»)
start:           the start of the domain worker — the steps of chapter 3.2 N3 «start()»: 0 — the schema check (N3 «schema check by the worker»: does not
                 start, code 2; after the renewal of the slot domain/<sub>/worker — fencing), 3 — the server is withdrawn (the withdrawal row
                 of its own server is unreadable — the name is not taken until it reads, the log) (V7 item 3, the Architect's decision of 2026-10-28, on a proposal; rows 4, 6 of the list)
heartbeat:       the object domain/<sub>/heartbeat in the object store of the holder (P/05 N1.1), one per subsystem — the heartbeat
                 of the domain worker in the form of chapter 3.4 N1.1 (worker, ts, server, url, instance, status …; time — N0); worker —
                 is exactly the string «domain/<sub>/worker», the full key of its slot (the grammar of the slot name of chapter 3.2 does not
                 apply to it); a heartbeat with another worker is out of form (added by the reconciliation of M11, log of cammeta-go M11-05 № 8;
                 checked by reading — the stand does not carry a domain worker); written by <sub>domain every HEARTBEAT_EVERY and
                 by the stand-in (chapter 3.4 N3); read by domain and domainconsole — the url of the door door.pass (P/10 N1.6 address), a heartbeat that
                 does not read, is out of form or is not fresh by LOST_AFTER — «not heard» (P/10 N1.6 absent); objects do not fall under the rights
                 of the store (P/01.2) (stage A, A3)
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R006

old-sha256: 2107fc2b429e6d08afd4d62c114500ec43b1245054e91e96b866a5c3f66c3d45

<!-- req: P/04-R006 -->

```yaml
<sub>/placement/<id>:                     # a decision; the writer is the controller
  worker:    <worker name> | ""           # "" — not placed; with an active intent the common decision of N1.5 applies
  reason:    <a string for a human>       # non-empty; grammar — N3 «Reason»
  at:        <wall seconds of the controller>
  rev:       <decimal integer ≥ 1>        # +1 on every write
  manifest_rev:  <revision of the manifest under which the decision was taken>   # required for the current decision; a missing value is unreadable, never stamped (P/02.3)
<sub>/workers/<name>:                      # an assignment; derived from the placement rows
  units:     <list of ids by the list rule of P/06.1 N1.2 (comma-separated, otherwise a JSON array)>   # sorted
  rev:       <decimal integer ≥ 1>        # +1 only when the list changes
<sub>/policy:                             # the writer is the console; the controller reads it
  servers:   shared | distinct            # another value or key on read — the manifest default; on write — a refusal
platform/servers/<host>:                # the writer is the console (ADR-0026)
  labels:    <comma-separated labels>     # "" — none; the row beats the node labels
platform/doors/<host>:                  # the writer is the resource of the server (ADR-0045); the form — P/05 N1.4 door_row (family doors)
  room.<sub>, live.<sub>:                 # the controller reads them — free(s) N3 «shortage()» (ADR-0084 addendum (3) R14′); the element
                                          # is absent, does not read or is unknown — the server is not an order candidate
platform/drain:                           # the writer is the console; one row per cluster
  server: <server>; at: <moment>
platform/decommission/<host>:           # the writer is the console
  by: <who>; at: <moment>; why: <words>; gone: "true"?   # gone — the confirmation «there is no server» when the resource was never heard
<sub>/decommissioned/<host>:            # the writer is the controller; removed when the request is withdrawn
  asked_at, at:  <wall seconds of the console request and of the controller mark>
  slots, units, holds:  <names of the released slots, ids of the removed units, places of the holds — by the list rule of P/06.1 N1.2; "" — none>
                 # an element: slots — a slot name P/03.2 N1.4, units — a unit id P/06.1 N1.3, holds — a place name P/03.2 N1.3;
                 # a count («0») is not an element (added by the pilot of the data family schemas, D7)
                 # names, not numbers (reconciliation of python and go 2026-10-18)
<sub>/decommission-pending/<host>:     # unfinished controller progress, never the final decommission mark
  state: prepared | cleaning | finalizing
  request_index: <version>             # exact fixed platform/decommission/<host> index
  asked_at, at: <time>                 # request at and plan acceptance time
  manifest_rev: <revision>
  remaining: [{name: <slot name>, index: <version>}, ...]  # JSON; original versions, no later substitution
  from: [<owned from prefix>, ...]     # fixed full prefixes, each ending in /
  released, skipped: [<slot name>, ...]
  current: [<slot name>, ...]          # at most BATCH_WRITES - 1, the confirmed release chunk
  cleanup_index: "" | <version>        # empty means the progress row's own index, before its first cleanup rewrite
  slot_cursor, from_cursor: <count>    # next current slot and its next from prefix
  units, holds: <lists>                # fixed final-mark metadata, same form as decommissioned
<sub>/want/<host>:                      # the writer is the controller, cas with the guard placement_turn (N1.5); ADR-0084 and addendum (1)
  want:      <decimal 1…WANT_NUM_MAX>               # the absolute target of the number of role processes on the server, the base <prefix>-<server>-1 is included
  at:        <moment of the write>        # diagnostics; the terms — by the observation of the row version (N1.4 terms)
  by:        <controller instance>        # diagnostics; the authority — cas and the guard placement_turn
  why:       <non-empty reason>           # grammar N3 «shortage(), order()…»
  retiring?: <worker name>                # chosen for shrinking (N3 «shrink»)
  # the row exists, except while pending/finally decommissioned, for an installed role on a server of a manifest with grows: true (N3 «order row»); only the decommission
  # of the server and the removal of the role delete it; shrinking writes want 1, does not delete; the controller and the console read it (series workers_wanted P/06.5 N3 «/metrics — text»)
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R008

old-sha256: b10321baedc4d5bd3fa64ff043b1cd997aa3d268b57f2743f392b707e4c03c68

<!-- req: P/04-R008 -->

```yaml
pass:
  at:                   <moment the control part ends, before snapshot publication>
  ok:                   bool;  error: <text of the last error or "">;  failures: <number>;  last_success: <moment>
                        #   ok: true — the control part reached its end, all its inputs were read and no control write was refused; otherwise false
                        #   (C04-PASS-OK-01)
  seconds:              <duration of the control part, excluding later snapshot/report publication>
  manifest_rev:             <manifest revision of the controller>;  manifest_behind: <rows of this pass whose write
                        is postponed because of a lagging manifest; a row — once per pass> (C04-MANIFEST-BEHIND-COUNT-01)
  names_given:          {<slot name>: <version of the slot row at which the name is given>}
  hung_move_after:      <seconds of the hang limit in force at this controller>
  fates:                {<name>: {fate, server, why, rev, since}}   # only occupied slots not released: holder non-empty, released
                        #   false (not true and not taking — the slot contract «States»); since — the moment the slot entered this fate on the clock of the controller
                        #   (a change of fate — a new since), not the first look at the slot (reconciliation of python and go 2026-10-18)
  diverged:             <assignments fixed by sync>
  unplaced:             <units without a worker, except those taken out of service>
  garbled:              <unit rows that do not read>
  expired_kept:         <manual rows with a passed deadline that the deadline removed but did not delete: a target with fixed fields
                        or about not by id (N3 «pass()» step 8; ADR-0091 item 1)>
  snapshot_state_garbled: <unit states not included in the snapshot shard of this cycle: the state row does not read
                        by its type (N1.3a; P/03.6 N1.7 unreadable; ADR-0091 item 3)>
  state_swept_total:    <state rows removed by the sweep of the orphaned and after the delete of the unit row (N3 step 8a)>
  snapshot_tables_refused: <tables of N1.3b that this cycle replaced with a stub: the object is larger than SNAPSHOT_TABLE_MAX>
  snapshot_rows_garbled: <unit rows not included in the snapshot shard of this cycle: a field of snapshot does not read
                        by its type (N1.3a garbled)>   # P/01.1 N0 «Stability of output»; the decision of the Architect,
                        #   reconciliation of python and go M10/6–11, T7
  reach_moves_total, slots_released_total, unplaced_deleted_total, servers_decommissioned_total,
  workers_hung, workers_hung_moved_total, workers_unsure_moved_total, name_conflicts: <numbers>
  unplaceable:          {<id>: <why>}   # units without a place in this pass and a non-empty reason; the console takes why from it
                        #   for /unplaceable and reason 404 /where/<id> of an unplaced one (N2.2)
  short:                # only with placement.grows: true; an element for each label set with waiting ones
    - {labels: [<labels>], units: <exact nonnegative integer sum of waiting unit weights>, workers: <processes needed beyond the live ones and the capacity in flight>,
       groups: <waiting groups>, ordered: <ordered by this pass>, withheld?: <words why it is not ordered>}
                        #   labels — the canonical notation: unique labels ascending, a repeat collapses (R21);
                        #   groups — always, 0 too (required in the form — review of stage B 3–5, № 13); own counters of the element MAY be added by the existing count form; standard fields keep their forms; acceptance compares the named fields;
                        #   an empty set in the words of why is any labels; a set without a computable per is the same element: workers 0,
                        #   ordered 0, withheld «no positive capacity estimate» (R20); the series <sub>_workers_withheld{labels}
                        #   (P/06.5 /metrics) — for each set of the pass report, zero too (ADR-0084 addendum (2) R23)
  wants:                {<server>: {want, live, pending, retiring?, why, state}}   # only with grows: true; live — the live
                        #   role processes of the server, pending — in flight(s) by heartbeats (N3, R13′); state: ok | raising |
                        #   raise_failed | no_base
  raise_failed:         {<server>: {since, times}}   # the server «failed to raise»: since — the moment the order was withdrawn, times — in a row
  near_waiting:         [<subsystem>…]   # only with placement.near whose near.sub is not in the manifest catalogue of this pass:
                        #   the affinity waits for its installation (N1.3 near; ADR-0091 addendum (27) item 6); otherwise there is no field
```

The current reader and writer both require expired_kept, snapshot_state_garbled and state_swept_total as nonnegative count values. Missing or invalid fields use the existing unreadable outcome. The first two belong to this cycle; state_swept_total accumulates confirmed deletions from zero in this process. The current snapshot reader and writer both require exactly one admissible unit.rows array, including an empty array; missing or multiple arrays are unreadable. Absence before the first object publication is separate.

Weight aggregates short[].units, waiting and load are exact nonnegative integers without a common.uint53 ceiling; their JSON output has integer notation and never rounds or saturates through binary64/int64. Individual weights/capacities and other count fields keep their forms. Custom short counters keep count; widening the aggregate changes no full serialized-object write limit.

A cycle ends its control part and releases the placement turn, then attempts the unit snapshots and table snapshots, and finally writes one pass report containing the snapshot counters of that same cycle. At, seconds, last_success, ok and failures describe only the control part. Snapshot errors keep their own existing outcomes/logs/counters and do not become control failures. The three snapshot counters start at zero for each cycle; the next cycle cannot reset or absorb an unfinished prior cycle. After publication attempts return their confirmed, refused, failed or unconfirmed outcomes, write the final report once, without later patching it. state_swept_total is not reset.

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R010

old-sha256: 73c05220c31cdbc829678dd13a11b0230abc0c808b176ff92fd6cbe2d6395868

<!-- req: P/04-R010 -->

| Key | Meaning | Default |
|---|---|---|
| `capacity: {from, default, unit_mb, base_mb}` | capacity — [the pool contract](../../common/contracts/pool.md) `capacity` (moved there without a change; layout audit, the Architect's decision of 2026-10-25, A-12); the reason — the field `fates.<worker>.why` of the pass report (N1.2) | `from: capacity`; `default` is required |
| `headroom: {from}` | headroom — a heartbeat field that the subsystem names; the controller does not read it (neither the choice, nor the slot fate, nor the pass report); the console shows it — the series `worker_headroom{worker,server}` and `headroom` ([P/06.5](../../06-console/spec/06.5-console.norms.md) N3 «/metrics — text») (C04-HEADROOM-UNREADABLE-01) | `from: headroom` |
| `weight: {field, default}` | the weight of a unit — an `int` field of the row ≥ 1, when the field is absent — weight.default ≥ 1; a wrong present value is not replaced with default: the unit row is unreadable (`garbled` of the pass report), the unit is neither placed nor removed, the reason is in `unplaceable`; the load = Σ of the weights (ADR-0078) | without the key — weight 1 for all |
| `constraint` | `none` \| `labels-subset`: the labels of the unit ⊆ the labels of the worker. The labels of the unit — its field `labels` of type `list` (no field — an empty set, the constraint holds); a label — by [the label alphabet](../../common/contracts/labels.md); the labels of the worker — the row `platform/servers/<host>` or the node labels | `none` |
| `tie_break` | `most-free-capacity` — the only word | the same |
| `servers` | `shared` \| `distinct`: with `distinct` only one worker can carry the units on one place — the one with the largest load, on equality the first in the slot order of P/03.2 N1.4; the others stay idle | `shared`; the row `policy` overrides |
| `place_by` | what counts as a place with `distinct` — [the pool contract](../../common/contracts/pool.md) `place`, the keeper — `keeper` (layout audit, the Architect's decision of 2026-10-25, B-07); `distinct` units are given only to the keeper of a non-empty place (ADR-0084 addendum (2) R15) | `server` |
| `places: {table, where, server_field, lease, wanted}` | the table of places and the hold row `<sub>/holds/<place>` (P/03.2 N1.3); `lease: strict` — a strict place; `wanted` — a table of the subsystem: a row with the name of a place says that the place needs a holder, the reason is known to the subsystem (N3 «shortage()»; C04-PLACE-WANTED-01) | — |
| `spread_by` | a field: two units with one value are not on one server; an absent or empty value does not take part in the spreading — a unit without a value neither constrains nor is constrained (a pair to `group_by`: empty is not a group; reconciliation of python and go M10/3–5, the Architect's decision) | — |
| `group_by: {field, cut_at}` | a group — one value of the field (for `url` — the host by `cut_at: host`); it is placed only whole on one worker (ADR-0011). What a group is, the host in one spelling, `none`, an unreadable host, «not in a group» and the refusal — [the contract of the group by host](../../common/contracts/group-of.md) (moved without a change of behaviour; stage C guess W03-GROUP-01, the Architect's decision of 2026-10-23; ADR-0053; vector [`group-of`](../../common/vectors/group-of/README.md); review of stage A, SA1-20; reconciliation of python and go 2026-10-18) | — |
| `near: {sub, by, of, prefer}` | a preference: beside the holder of a neighbour — the units of the subsystem `sub` (the manifest catalogue). My value — the field `by` of my row, without `by` — my id; the value of a neighbour — its field `of`, without `of` — its id; the neighbours — the live rows of `sub` whose value equals mine. Among several neighbours first those that matched `prefer` — AND over the fields, OR over a list of values; a field value is a scalar (equality) or a list (as `affinity.strict`; C04-NEAR-PREFER-SCALAR-01); a field of `prefer` is a path: a segment through `.` is a step along a reference field of the neighbour to the row it names (`home.kind` — the field `kind` of the row named by the field `home` of the neighbour); among equals — by the id of the neighbour (UTF-8 bytes). The worker holding the chosen neighbour is preferred; no holder — no preference (ADR-0091 item 10; vectors [`near-of`](../vectors/near-of/README.md)). The manifest `sub` is not in the catalogue — the affinity does not apply, the unit is placed without it, the controller does not need the rows of `sub`; the subsystem is in `near_waiting` of the pass report (N1.2); the affinity is switched on from the pass at which the manifest `sub` appeared in the catalogue (N3 «pass()» step 1; ADR-0091 addendum (26) item 2, addendum (27) items 5–6) | `none` |
| `home` | a preference, not a filter: a field of the row naming the home (the value — of the first member in UTF-8 order; no value — no home), or `near` — the home is at the neighbour; only one side of a pair can follow. The field is a reference `ref` to the table of places `places.table`: the home is the holder of the named place, the worker whose place (`place_by`, the pool contract `place`) is the name of this row; there is no holder among the eligible (N3 «choose») — the workers of the server from the field `places.server_field` of this row, if the field is non-empty; otherwise there is no home. An empty server field does not hinder the home when there is a holder: the home is the holder (a volume without a server). Another worker of the same server, when there is a holder, is not the home: a unit at it moves to the holder (N3 «pass()», step 7). The reason: `place_by` names where the data of the unit lie; a comparison with the server would give it to the holder of another place of this server, and step 7 would not bring it back. No row or it does not read — no home. A field without `ref` — its value is the server itself: the home is the workers whose `server` equals the value. A `ref` to another table (or the manifest has no `places`) — no home: the value is the id of a foreign row, not a server, and `places.server_field` is not named for it (C04-HOME-REF-OTHER-01). C04-HOME-PLACE-HOLDER-01, the Architect's decision of 2026-10-30, replaces the comparison with the server C04-HOME-PLACE-OR-SERVER-01 | — |
| `affinity: {field, table, server_field, strict, exclusive}` | a filter: a place from the table that admits the unit; `admits: false` takes nobody; a binding row leads the unit only to its own place. The place of the unit is the row of `table` named by its `field` (no value or no row — affinity does not apply). `strict` is a predicate that selects the binding rows: a row is binding when each field of `strict` equals the value or is in the list of values (AND over the fields, OR over a list); no `strict` or `{}` — all rows of the table bind, there are no non-binding ones (C04-AFFINITY-EMPTY-STRICT-01). A binding row leads the unit only to the holder of its place — the worker whose place (`place_by`, P/03.2 N1.3) is the name of the row; with a non-empty `server_field` of the row — also only if the server of the worker is that one (both conditions; another worker of the same server with another place does not fit; C04-AFFINITY-BOUND-HOLDER-01); a non-binding one is a preference for the server `server_field`, not a filter. `admits` is checked at the actual place of the unit (journal of cammeta-go, lesson 8 № 2). `exclusive: true` (only with `strict`, P/02.1) — the binding place is exclusive: its holder admits only the units bound to this place, the others are not placed on it (as `admits` for strangers); a worker with such a place takes no other places (P/03.2 N3 «place: take, hold, let go»); a binding row with an empty `server_field` — strictness by the holder of the place without a check of the server (ADR-0091 addendum (9) item 6, addendum (10) items 1–3; repeated review of addendum (10)) | — |
| `requires` | `none` \| `resource`: with `resource` a worker is eligible only while the resource of its server is not silent | `none` |
| `grows` | `true` — the role grows on demand: the controller counts the shortage and orders processes of the role per server with the row `<sub>/want/<host>` (N3 «shortage(), order()…»; ADR-0084) | `false` |
| `retire_when: {state?, field, in, delete_after?}` | a unit with a value of the field from `in` is not placed and is removed with the value as the reason. Without `state` the field is one of the unit row; with `state` — a field of the value of the acting state `unit.state.<state>` (the row-check contract «Unit state» acts; no acting one — not finished). `delete_after` — N s after the removal by `retire_when`, by the clock of the controller, delete the row (N3 step 8): the count starts from the first pass at which the controller saw the unit removed by `retire_when`; a pass at which it is no longer removed (an operator edit removed the value or the acting state) clears the count, a new removal counts anew (C04-RETIRE-TIMER-CLEAR-01); after a restart of the controller the count starts anew, as for `unplaced.delete_after` (ADR-0091 items 1, 3; replaces `forget_finished` of the subsystems) | — |
| `ends: {field, never}` | the deadline of a unit: the field `field` of the row (Unix seconds) ≠ `never` and not later than the clock of the controller — the unit is not placed, is removed with the reason `ends`, the row is deleted (N3 step 8); `never` — no deadline (ADR-0091 item 2) | without the key — no deadline; `never: 0` |
| `rebalance: {dead_band}` | outside this lesson: manual rebalance is not executed and dead_band is not consumed by the controller; the accepted manifest form remains P/02.1 | by the manifest form |
| `unplaced: {delete_after}` | a unit row that nobody holds for longer than N s by the clock of the controller is deleted by the controller (ADR-0067); one removed by `retire_when` too: nobody holds it. For a table with `fixed` fields (except the field that is the source of the id) or with `about` not by id, only the rows with `made` are physically deleted (the name is held by the template `key` of the customer, P/03.6 N1.6) — likewise by `retire_when.delete_after` and `ends`; the deadline does not delete the manual rows of such a table: `ends` removes them and does not place them, `delete_after` does not delete them, the counter `expired_kept` of the pass report (amendment of ADR-0067 addendum 2026-10-10, ADR-0091 item 1); the operator deletes them through a door. The worker of the subsystem MAY also delete its own unit rows by the key `worker.deletes` — a delete with `cas` without the write right (ADR-0067 addendum 2026-10-17; there is no training consumer yet — a debt in «the specification progress note (for people)») | without the key — never |

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R011

old-sha256: 873e89c81954af17506123f94ee50aa34eefb46ec509e9f4e3e9c5dfe0663094

<!-- req: P/04-R011 -->

```yaml
<sub>/snapshot/<worker> | <sub>/snapshot/unplaced:     # objects; the writer is the controller; the worker name unplaced is a refusal
  {cluster, worker: <name> | null, ts, <rows>: [{id, revision, <fields of snapshot:>, state?, worker, server}]}
          worker: the worker name of the shard; null — for the shard unplaced and for the shard of a gone worker (C04-SNAPSHOT-GONE-WORKER-01)
cluster:  the installation name — CLUSTER of the environment (the environment file contract «Environment variables»; the name of a domain member, [P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.1); not set — "local" (outside a domain)
fields:   snapshot: of the manifest (P/02.1): no key — all fields except *_secret and blob; [] — no field (id, revision, worker, server
          remain); an author field server is also excluded by default; a secret, blob or server in an explicit list — the manifest does not load; addresses — with the mask
          P/06.2 N1.1a, the same as in the console output (password → ***)
          the declared fields of a unit do not include platform_fields P/06.1 N1.2, including deleted/worker: a load refusal P/02.1;
          unit.rows not cluster/worker/ts: a collision with the envelope — the load refusal refused:form (P/02.1)
state:    with a declared unit.state — an object {<name>: <value of the acting state>} (the row-check contract «Unit state» acts, the same rule
          as at the console P/06.1 N2 «State in the answer»): the names — state.<name> of the snapshot list of the manifest; without the key snapshot —
          all states except cursor; [] — none; no acting one — no name, none at all — no state. A state row
          that does not read by its type — the unit is in the shard without this state, the counter snapshot_state_garbled of the pass
          report (N1.2) (ADR-0091 item 3)
publish:  after the control part releases turn and before this cycle's one final report (N3 «pass()»); the shards of gone workers — empty; without units — an empty unplaced
          an empty shard has one form for all: {cluster, worker: null, ts, <rows>: []} — the field <rows> is present, the list is empty
          (as the witness; C04-SNAPSHOT-GONE-WORKER-01)
garbled:  a unit row whose snapshot field does not read by its type by values_by_type P/06.1 N1.2 is not included in the shard;
          the shard is published with the other units, a log line once per series and the counter `snapshot_rows_garbled` of the pass report
          N1.2 (P/01.1 N0 «Stability of output») (reconciliation of python and go M10/6–11, T7)
ceiling:  before the write the controller judges the resource door limit L owned by P/05; max_bytes of the store is held by the store itself on put
          ([P/05](../../05-resource/spec/05-resource.norms.md) «object store» — `TooLarge`), the controller does not count it itself;
          TooLarge of the store gives the same outcome of N4 — the shard is not written, the former one is kept (C04-SNAPSHOT-CEILING-MAXBYTES-01, the decision of the Architect 2026-10-28).
          The size is the number of bytes of the full serialized object, including the envelope and the empty shards, with the actual
          notation of ts (its length is part of the size) (reconciliation of python and go M10/6–11, matched without a norm).
          Exactly L is allowed; more than L → TooLarge before put_durable, do not replace the former shard.
          Diagnostics: «N units on <shard>; snapshot is B bytes, limit is L bytes»; raising OBJECTS does not lift the door limit
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R013

old-sha256: 3cf5a48daf22868ed14a4d90723e0dad33db464b69707e722663d65773db66a8

<!-- req: P/04-R013 -->

```yaml
<sub>/snapshot-tables/<table>:  # an object; the writer is the controller; <table> — a key of domain.view_tables of the manifest (P/02.1, P/08.1 N1.4a):
                                  # a table of tables or unit.rows
  {cluster, ts, refused?, rows: [{key, revision, fields, secrets?, labels?, about?, worker?, server?, phase?, status?}]}
cluster:  as for a shard, N1.3a
ts:       the moment of the object write; rows did not change — the object is not written, ts is the former one: liveness is not ts but members[].state of the view
rows:     store rows, the order — key in UTF-8 bytes; key — the row name (P/06.1 N1.6) or the unit id, revision — the row version
          (P/06.1 N2 «Row revision»); a removed row and a tombstone are not in rows
fields:   only the fields of the list domain.view_tables of the manifest; the value — by its type by values_by_type P/06.1 N1.2; a field absent from the row — in fields
          it is absent, no default is substituted; held_by of a table of places — as P/06.1 N1.6 held_by; addresses — with the mask P/06.2 N1.1a;
          the keys *_secret inside json values are cut at any depth (P/06.2 N1.4); the list does not name the *_secret fields themselves (P/02.1)
secrets:  the names of the *_secret fields of the row with a non-empty value, ascending in UTF-8 bytes; none such — no field; no values:
          the domain needs to know whether a secret is set (ADR-0110)
labels, about: only for unit rows — the field labels and the value of the field about.field of the manifest, whether the list names them or not: the right judges by them (the right contract
          «Judgement by target»); no value — no field
worker, server: only for unit rows — from the assignment; no assignment — no fields
phase, status:  only for unit rows — phase and the fields domain.view_status of the manifest from the element status[] of the heartbeat of this unit (P/08.1 N1.4 status);
          no element — no fields
garbled:  a row whose field from the list does not read by its type is not included in rows; the counter snapshot_rows_garbled, as N1.3a garbled
ceiling:  SNAPSHOT_TABLE_MAX from forms/runtime-constants.tsv of the full serialized object; more — instead of the object a stub {cluster, ts, refused:
          "too_large", rows: []} and snapshot_tables_refused of the pass report (N1.2). A stub, not the former object: an old snapshot would look alive.
           The agent owns per-member and combined table budgets (P/09.1 N1.2 tables_budget and its linked P/08 admission bounds); this controller introduces no second member count, camera count or measured domain-wide byte ceiling.
scope:    the object exists for a manifest with domain.view_tables; domain.ref is not needed for it; the key removed from the manifest — the object
          is not removed, the agent no longer carries it (the report intake contract member_objects)
reader:   only the domain agent (P/09.1 N1.2); the cluster console reads its own tables as rows
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R014

old-sha256: 3bb5c819d6fd80cfa17fea4e595c32ad69fe8749e39844c4af95360af800cebf

<!-- req: P/04-R014 -->

```yaml
constants:
  LOST_AFTER:       the observation contract «Freshness» (the value is there; layout audit, the decision of the Architect 2026-10-25, A-01)   # heartbeat freshness («within the last LOST_AFTER»;
                          # review of stage A 6–7, № 1, № 2) and the margin after SLOT_TERM of observing an unchanged slot version
  HUNG_MOVE_AFTER:  the environment file contract «Constants and units» (the value is there; layout audit, the decision of the Architect 2026-10-25, A-17)   # s; the age of the observed slot version up to the hung/unsure/wait limit; from the environment of the controller, published in the report
  ALIVE_EVERY:      the observation contract «Resource state» (the value is there; layout audit, the decision of the Architect 2026-10-25, A-10)   # the resource rewrites at of its door
  REACH_BUDGET:     the environment file contract «Constants and units» (the value is there; A-17)   # units per pass for moves by reachability; from the environment
  WRITE_CONFLICT_LIMIT: forms/runtime-constants.tsv  # consecutive conflicts of one logical change; after the limit the existing step fails, not an extra attempt; barriers remain
  HOME_BUDGET:      forms/runtime-constants.tsv     # unit per pass for moves home
  WANT_GRACE:      forms/runtime-constants.tsv    # s; an order the server has not raised is withdrawn (N3 «withdraw on deadline»)
  RAISE_QUIET:      forms/runtime-constants.tsv   # s; a server that «failed to raise» gets no orders
  RAISE_FAILS_LOUD:      forms/runtime-constants.tsv     # failures in a row — the alarm workers.raise_failed of raised severity
  SHRINK_AFTER:     the environment file contract «Constants and units» (the value is there; A-17)   # s; without a shortage — shrinking (N3 «shrink»); only on the stand — W2C_SHRINK_AFTER=<seconds>
                          # of the environment of the controller (as W2C_WALL_OFFSET M11/3): with the variable set, the controller writes
                          # a loud journal line at start; outside the stand the variable is not set (ADR-0084)
  SHRINK_BUDGET:      forms/runtime-constants.tsv     # unit per pass for a move from the worker being shrunk (as HOME_BUDGET)
  # the terms of the order and of shrinking are starting values of the policy; the count is by the local monotonic clock of the controller from the first
  # observation of the order row version (for SHRINK_AFTER — from the first pass without a shortage), a new controller starts from 0,
  # a repeated write of the same target does not extend the term, at is diagnostics (ADR-0049; ADR-0084 addendum (1) R5);
  # WANT_GRACE — from the first pass where in flight(s) > 0 (N3), reset — when in flight(s) = 0: the order is raised, then the process
  # of the number died without a change of the row version — the count is from the pass where the number is in flight again, not from the former version (C04-WANT-GRACE-REPATH-01)
resource_state:     # the resource of a server — live | unreachable | unknown | silent: one definition for all observers
                    # (the controller, the console) by their monotonic clocks, the rules in order — the observation contract
                    # (common/contracts/observation.md «Resource state»; review of stage A 6–7, № 2);
                    # only silent excludes and moves
process_presence:   # what the resource says about the process of a worker: the output of [P/05 N1.4](../../05-resource/spec/05-resource.norms.md) `presence` by the key <sub>/<slot name> of its subsystem;
                    # only from the heartbeat of a resource in the state live: a stale heartbeat with the word runs gives no presence, and the slot
                    # is judged by resource_state (reconciliation of python and go 2026-10-18); an absent one of the fields workers, running,
                    # unknown is an empty list (a partial set: running without workers — runs, workers without running — gone;
                    # C04-PRESENCE-PARTIAL-01)
  runs | gone | unlisted | unknown   # unknown — an unconfirmed read; silent — only the resource state above
fate:               alive | wait | hung | hung_moved | unsure | unsure_moved | move | release
NAME_FATES:         [move, hung_moved, unsure_moved, release]   # + wait beyond the limit HUNG_MOVE_AFTER
MOVED_FATES:        [move, hung_moved, unsure_moved]
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R016

old-sha256: 3799a66ba9f863d7e19818b1f022fbbcae231665bcd1928b02e63d80b5d1e996

<!-- req: P/04-R016 -->

```yaml
power_pull:
  moves:    units — by two silences (the heartbeat of the worker and the word of the resource), by the tolerances of N3; (SLOT_TERM + LOST_AFTER) + a pass —
            a guide for a sound stand with heartbeats known in advance, an available store and capacity, not a general deadline; the new holder takes
            the next epoch; the same with shared and distinct; it does not move back by itself, except a declared `home` (N3 «pass()», step 7, HOME_BUDGET)
  stays:    the archive on the volume of the server — under the old epoch, unavailable until the return, not rebuilt, not lost;
            the units of a hung live worker — stay with it (one writer)
  lost:     the open bucket and the closed buckets without a confirmed mirror copy; one vote of the group.
            An RPO of a bucket length is admissible only with a confirmed mirror of all closed ones; otherwise the loss is larger
  store:    1 of 3 — an election in seconds; 2 of 3 — 503 unavailable after the effective P/01 -leader-wait, the workers live on the last assignment by the lease
            and unconfirmed_max; recovery — recover by hand (P/01.3 N3 «recover the store (no majority)»)
  restore:  P/05 N1.4 «Bucket restore»
  return:   the resource pulls the buckets; the workers take free names; a name with an expired slot — only by the word of the controller (P/03.2)
  presence: the presence lock contract (common/contracts/presence-lock.md)
fresh_controller: what is seen for the first time has just changed; it moves nothing for the first LOST_AFTER (N3 «pass()», step 0)
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R030

old-sha256: 857293b307a6e02a9b7072e14f38e4ea0b9170cd3bbce3b0aa8618fd88133824

<!-- req: P/04-R030 -->

```
0. observation: update the memory of the seen heartbeats, slots and resources on the own clock; the objects of the cluster (heartbeats of workers
   and resources, reports) are read through the resource of the own server (the objects door of P/05, `scope`; ADR-0084 addendum (2) R17); without
   a resource on the own server with `cluster://` — «unknown», not «absent» ([the object store client contract](../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27);
   seen for the first time = has just changed; get the placement turn by N3 above;
   busy → no changing pass, a retry after TURN_BUSY_RETRY; mine → first complete an active intent;
   then a fresh look: the units, the placements, the assignments and the properties of the candidates;
   before every new decision the look is refreshed, the results of the previous decision are taken into account
1. revision: read the manifest revision; a placement without its required manifest_rev is unreadable; do not stamp or repair it;
   read the manifest catalogue (platform/manifest/*) — on every pass: the manifest near.sub has appeared — the affinity (N1.3 near)
   applies from this pass; it is absent — no affinity, near_waiting (ADR-0091 addendum (27) item 5)
2. decommission of servers: resume pending or admit a stopped server by N3 decommission_server; release/cleanup in bounded chunks,
   then publish <sub>/decommissioned/<s> only at finalization. Before admission a heard server leaves the request standing.
3. slot fates (below); release → write the slot as released; names_given; alarms hung/unsure; an abandoned capture — remove the rows under it (below)
4. place: remove the deleted (reason deleted) → remove by retire_when (by the acting state with retire_when.state) →
   remove by ends (the field ≠ never and ≤ the clock of the controller; reason ends) → sync of the assignments with the placements (diverged) →
   each unplaced unit from placeable (N3 shortage; deleted, ends and retire_when excluded) — choose (below), a group whole at its first member; each in its own attempt;
   the order of the unplaced — by id in UTF-8 bytes (a group — by the id of the first member); the same order for the moves of steps 5–7
   (added by the reconciliation of M11, cammeta-python 05 № 25)
5. reachability: the units whose server no longer reaches their labels — a move within REACH_BUDGET;
   a group — whole, the first group goes even beyond the budget; nowhere — remove with a reason
6. leaving: the units of the workers that are leaving (below) — a move without a budget; a group whole, or it waits
7. home: no more than HOME_BUDGET units — home, if there is room there; the home is judged as in «choose» (N1.3 home): the holder
   of the named place is eligible — it alone is the home, a unit at another worker, including one of the same server, moves to it; there is no
   holder — the home is the server of the place, and a unit on this server is already home; no home, it has no free room or is not eligible — the unit
   stays: a preference does not become a filter (C04-HOME-PLACE-HOLDER-01)
8. unplaced for longer than delete_after: under the own turn re-read the unit and its effective placement
   by N1.5; there is an assignment, an active intent (with any target) or the read is not confirmed → do not delete. Still unplaced and the deadline is confirmed →
   delete the row with cas of its fresh version AND guard of the own version of placement_turn (the admission of step 5 above);
   conflict/412/no answer → the barrier and a new plan by the turn rule, the journal unit.unplaced_deleted only on success.
   Likewise — one removed by retire_when now, for longer than retire_when.delete_after (from the first pass that saw it removed; a pass
   at which it is no longer removed clears the count, N1.3; after a restart — anew): the condition is checked on the fresh row and, with
   retire_when.state, on its acting state, no longer removed — do not delete: an operator edit is not lost (the Architect's decision of
   2026-11-01, Quint V/05.1 V1, C04-RETIRE-TIMER-CLEAR-01) — and one removed by ends: ends deletes right after the removal (ADR-0091 items 1, 2). For a table with fixed fields or
   about not by id only a row with made is deleted; a manual row is not deleted — expired_kept + 1 (N1.3 unplaced).
   A row with made is deleted by the row-check contract «Customer row: made» `delete` (strictly after made.keep, not_before = max(0, made.keep − 60);
   layout audit A-11): 409 early — not deleted, without a barrier and a journal, on the next pass;
   keep prevents only an obviously early delete attempt; a delete arriving late is still bounded by not_before at store admission. It never authorizes deletion before keep.
   The row is deleted physically, without a tombstone (P/01.1 delete): the row first, with cas of the read version and guard of the own
   version of placement_turn; an edit or a prolongation between the read and the delete — conflict: the delete is cancelled, the state is not
   touched; only after a confirmed delete of the row — its states (step 8a); the journal unit.unplaced_deleted
   {reason: unplaced | retired | ends}
8a. state sweep (unit.state declared; ADR-0091 item 3): list <sub>/state/; for each state row read
   the unit row: it is absent, a tombstone or its born ≠ born of the state → orphaned: delete by one operation with cas of the version of the
   state and guard {key: the unit row, index: the read version — for a tombstone its version, "" — no row}; a row
   created or changed after the read cancels the sweep (412 — leave it until the next pass); the acting and
   other non-orphaned ones (born matched, revision differs) — do not touch; state_swept_total + 1 for each removed one
9. shortage and order (grows: true): order rows, capacity in flight, short, order, withdraw on deadline
9a. shrink (grows: true): the victim, retiring, a move of no more than SHRINK_BUDGET, the end or the cancel; drain — N3 below
10. finish the control part and its ok/failures/at/seconds/last_success; release the turn;
    then attempt unit snapshots and table snapshots outside turn, and write this cycle's one final <sub>/controller/pass
each step — in its own attempt: an error of a step — failures + 1, the other steps go on
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R032

old-sha256: c9e0fdc0c5d8d483c0f49a3ca1780205e908195304ceda4b30980898bb223754

<!-- req: P/04-R032 -->

**Races.** The target of placement/assignment changes only under the turn and through an intent; one cas of a unit row
does not replace the common admission. A break of the turn/store stops the whole changing pass,
not just one unit; the errors of the other independent steps are counted by the usual failures.
The next holder first repairs the unfinished decision, then accepts its own.
A missing manifest_rev is an unreadable current row, not authority to stamp it; all existing turn/intent barriers remain.

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R041

old-sha256: 4bdea472eabc4ff3293b72a8d6ecbe292eeedb7a9c9f33eab8e44a572a3b9aaa

<!-- req: P/04-R041 -->

```
write release: write the slot released (cas),
                                                                                   keep holder/until/gen/server; a torn one —
                                                                                   wholly released and nobody's, keeping a readable gen and writing until as zero Time in the existing writer notation, never now;
                                                                                   keep server only if readable by the current slot field schema; otherwise omit the field, with no empty substitute. No liveness or registry check;
                                                                                   if gen does not read — do not change the row, do not issue
                                                                                   a permission for the capture (P/03.2 N1.4)
abandoned capture: released = "taking", the version unchanged ≥ SLOT_TERM on the clock of the controller (the capturer died between the writes
                   of P/03.2 N3 «capture» steps 3 and 4) → remove the rows under the slot: the contributions <sub>/<from>/<slot> of each book of the manifest
                   with a from family (P/03.7 N1.2) by a batch with guards by <sub>/slots/<slot> with the version of this judgement, do not write the slot;
                   no row — skip; a guard refusal (412 guard, 409 conflict) — a live capture changed the version: do not repeat;
                   with a server decommission and without: an abandoned capture carries the server of the capturer, step 2 of «decommission_server» by server = s does
                   not recognise it, and an orphan under taking would keep the contribution stale forever (ADR-0113 addendum (49), (50))
names_given[name] = the version of the slot row at which the name is taken: for move, hung_moved, unsure_moved and wait ≥ HUNG_MOVE_AFTER —
                   the version at the moment of the judgement (the controller does not write the row); for release — the version AFTER the write of the release (the answer
                   of this write): the released slot is taken by it, and as a «free» one it is also a candidate (P/03.2 N3 «capture» step 2c)
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R043

old-sha256: f1fa6d7cfc982277aba2fdb06825c95a31de39e580aeea3df868e8137495e237

<!-- req: P/04-R043 -->

**Transitions of `release` (ADR-0080 addendum 12).** The branch `release` is reachable by the row «gone without assigned units»:
a live resource tells about a process with one of `runs`, `gone`, `unlisted`, `unknown` (P/05 N1.4; `silent` is a state of the resource,
not a presence), and the higher-priority rules still run first. The two closing rows are reachable when server/slot are known,
the slot version has been observed unchanged for at least SLOT_TERM + LOST_AFTER, worker freshness is not confirmed, and resource_state
is unknown: with assignments select move, without assignments enter the release procedure. This uses the existing closing-row policy, not the
unreachable-resource delay of the effective HUNG_MOVE_AFTER; unknown is not evidence of either silence or unreachability (review P/04 M1).

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R047

old-sha256: f82cad2da1d8be8f2202abdd1fd09153223b4424e0e5d9227e2c162afc9842d3

<!-- req: P/04-R047 -->

The first of: the slot is released (released = true — at once); an abandoned capture (released = taking, the version unchanged for SLOT_TERM on the clock of the controller — the capturer died between the writes; earlier — not leaving, the capture will finish; added by the Quint pilot, F2); the resource of the server is silent — only with `requires: resource` and a live worker (the pool contract): it works, but its units need a resource that is absent; it does not hold a place (`distinct`); the place does not admit; the server is draining; the server is decommissioned; an outcome from MOVED_FATES — its `why`. The units of a leaving worker — a move (step 6) by the rules of the choice; a group whole, or it stays with the alarm `units.left_on_leaving`; the placement row is not cleared until a new place is found, except for a released slot and an abandoned capture: their units that nobody can take are removed by the write `worker: ""`, the reason `slot <w> released; nothing live can take it` (`slot <w> capture did not finish; nothing live can take it`) (the worker has gone forever, a row with its name would say «placed»; acceptance P/03.4, sc. 03). A silence of the store moves nothing. Without `requires: resource` a silence of the resource does not count as leaving, and a worker silent together with the resource leaves only by fate: the units are carried by its outcome `move`, SLOT_TERM + LOST_AFTER of observation of an unchanged slot version (N3 «fate», [P/03.2-08](../../03-worker/spec/03.2-worker.norms.md); the Architect's decision of 2026-10-31, stage 2 of the plan of the group scenarios).

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R050

old-sha256: 4210430a470fb9fae2de9f6f27a7bcf3259cb59a1cc163c263312df2dac12bd2

<!-- req: P/04-R050 -->

```
order row:    on every server where the role is installed and neither pending nor finally decommissioned (the door row has room.<sub>, N1.1) — the row
              <sub>/want/<host>; none — create want 1 by a write with cas "" and guard of the own version of placement_turn
placeable = readable live unit rows, excluding deleted/tombstoned rows and every unit removed by ends or retire_when in step 4;
            a manual expired row may remain in the store, but it is outside this set. Apply this same set before grouping or weighing.
waiting = placeable ∩ (units without a placement ∪ units of the leaving ∪ out of reach); a group is one piece.
          Only these waiting units feed shortage, growth, the no-shortage timer and shrinking; retained expired rows and garbled rows
          neither cause an order nor delay shrinking (the Architect decision on ADR-0127, review P/04 C3).
live(s) = the live role processes of the server s (a live worker of N3 «choose»), including the base <prefix>-<s>-1 and the shrink victim
          (retiring): for «in flight» and «failed to raise» the victim is a live process, want includes it while it is alive; it is excluded
          from the placement pool (shrink); the number n of the name — as an integer (P/03.2 N1.4) (ADR-0084; cammeta-go M10-04 № 6)
in flight(s) = the count of the numbers 2…want(s) that have no live role process of the server s (by heartbeats, live(s)) — ordered
          and not yet raised, until the order is withdrawn on deadline; the base <prefix>-<s>-1 is not ordered and is never in flight;
          by heartbeats — for needed, the order of candidates (review of stage B 3–5, № 16), the shrink condition, the withdrawal on deadline
          and wants.<s>.pending; the candidate and the share — by the door
          (free(s) below); with consecutive numbers — max(0, want(s) − live(s)) (ADR-0084 addendum (2) R13, addendum (3) R13′)
no_base:         the base <prefix>-<s>-1 is dead — wants.<s>.state no_base, an alarm; the server is not a candidate (R6); the base is never
                 in flight, therefore it does not hold back the shrinking of the role on other servers (ADR-0084 addendum (2) R13)
free(s) = room.<sub>(s) − |{2…want(s)} ∖ live.<sub>(s)| — by the door row platform/doors/<s> of one snapshot
          (P/05 N1.4 door_row): live.<sub> — the numbers n ≥ 2 of the live presence locks by which room.<sub> was counted;
          it is counted once per pass before the loop over the sets and decreases with every share (order); no live.<sub> or it
          does not read — the server is not a candidate (ADR-0084 addendum (3) R14′)
set order:       a worker or a server that suits several label sets gives its capacity (free of the worker),
                 free(s) of the server and in flight to the sets in turn — in the UTF-8 byte order of the canonical notation of the set
                 (unique labels ascending, comma-separated, a repeat collapses — a label set is a set;
                 the empty set first; ADR-0084 addendum (2) R21); each unit of capacity, of free(s) and of in flight
                 is spent by one set once; a set takes the free, free(s) and in flight only up to its own
                 need (min): the in flight taken by a set — min(Σ in flight, processes) (R18), the remainder — to the next set
                 (ADR-0084; cammeta-go M10-04 № 7; stage A, A6)
per label set:   the capacity of a worker without a named one — placement.capacity.default (N1.3); a named 0 is not replaced with default
                 (ADR-0084 addendum (2) R19, addendum (3) R19′);
                 per = the smallest positive capacity over all suitable live workers, named or default;
                 none such → placement.capacity.default, if it is > 0;
                 no positive default either → no order for the set, withheld: "no positive capacity estimate";
                 the element of the set of the vector `order` has the same fields as a computed one: per: null, processes, in flight, needed,
                 withheld — zeros, plus why (ADR-0084 addendum (2) R20); in the pass report — an element short[] of N1.2 (workers: 0,
                 withheld — words) (review of stage B 3–5, № 15)
                 (still show the shortage of weight and of groups, workers: 0; with this withheld, zero means
                 the absence of a computable estimate, not the absence of a shortage; this is not an error of the step)
                 otherwise needed = max(0, processes − Σ in flight(s) of the suitable servers), where processes = ceil(max(0,
                 Σ of the weights of the waiting − free at the suitable live) / per) + one per group that has no room anywhere:
                 the capacity in flight is subtracted from the growth by groups too, otherwise the same growth would be ordered by every
                 pass (ADR-0084 R2; cammeta-go M10-04 № 5)
                 an exclusive place (N1.3 affinity.exclusive): the capacity of the worker holding it does not enter free for the other
                 units; waiting units bound to a place without a holder — an order for the place: the server of the place (server_field
                 of the row) is a candidate out of order, share 1; an empty server_field — no order, the place waits for a holder; a place
                 whose secret did not open — no order, withheld «<place_by> <place> is sealed»: the controller learns Sealed from
                 place_error.<place> = sealed in the heartbeats of the live workers of the role on the server of the place (P/03.4 N1.1); there are no live workers
                 there — one ordinary order (ADR-0091 addendum (9) item 6, addendum (10) items 1–3; repeated review of addendum (10))
                 a place without a holder: for a manifest with places.wanted the row of the table of places passes places.where, its hold does not act, and the row
                 <sub>/<wanted>/<place> exists and reads — an order for the place, a waiting piece of weight 1: the place may wait for neither a record nor a unit,
                 and without a holder nobody reads its archive. The server is from the row of the place, as for an exclusive place: server_field non-empty — this server is a candidate out of
                 order, share 1, on top of the general check of the candidate; not fit — no order, the place waits; Sealed — withheld, as there. server_field empty — the place is on any server: the piece goes
                 with the empty label set as an ordinary probe; a limit: a new process will take the first free place, not necessarily this one, a superfluous process lives until shrinking.
                 The row does not read — there is no reason, a journal line without the value; another empty place gives no order
                 (ADR-0084 R15; C04-PLACE-WANTED-01, the Architect's decision of 2026-11-01, analysis of the VMS invariants)
                 servers: distinct and the place from the heartbeat (place_by is a heartbeat field): free at the suitable live — only at
                 the keepers of places; a candidate for the set — a server on which in flight(s) = 0 (no probe: ordered and not raised;
                 review of stage B 3–5, № 40) and there is no live suitable process without a place; the growth of the set — no more than one probe
                 process per pass: the place of a new process is unknown before its start (R8); on a server no more than one
                 unfinished probe; no candidate or the growth is exhausted — the remainder of needed is withheld with the reason «no free
                 <place_by>» (N4); a probe on one server does not stop the growth on another (ADR-0084 addendum (5) R16‴)
candidate s:     the order row exists; the base <prefix>-<s>-1 is alive (otherwise no_base above: the server is not a candidate, R6);
                 free(s) > 0 (R14′); want(s) < WANT_NUM_MAX (otherwise the reason «<s> has no instance numbers left»,
                 the alarm workers.no_server); the labels of the server suit the set (constraint), requires: resource — the resource
                 is not silent; not draining, not decommission-pending or decommissioned; not «failed to raise» (RAISE_QUIET); servers: distinct — by the place
                 place_by: with place_by: server a server with a live worker of the role is not a candidate, with a heartbeat field the place of a new
                 process is unknown before its start — it does not restrict the choice of the server (R8)
candidate order: smaller live(s) + in flight(s) — by heartbeats (R13′; not by the door), then the server name in UTF-8 bytes (review
                 of stage B 3–5, № 16)
order:           distribute needed of the set over the candidates in order, to each — no more than min(free(s), WANT_NUM_MAX − want(s));
                 for a manifest with a non-empty door.pass.calls the ceiling of want(s) is 1, not WANT_NUM_MAX: a ticket is bound to the sheet of the server, there is one sheet per role and server
                 (the warden and hand-over contract «Pass of the second kind»); the remainder of needed — withheld, as with a lack of candidates;
                 after a share free(s) −= share (R14′); want(s) := want(s) + share — a write of the order row with cas by the read version and guard
                 of the own version of placement_turn, why — the reason «<n> more for <labels> on <s>: <waiting> waiting» (<labels> — the canonical
                 notation of the set; the empty set — any labels, R23);
                 want is the absolute target: a repeated pass and a new holder of the turn recompute needed with the capacity in
                 flight and do not repeat the growth — one acting logical order per piece of shortage (label set);
                 no candidates — the remainder of needed of the set is withheld: the number of processes in the series workers_withheld{labels} (P/06.5),
                 the words — in short.withheld of the report (N1.2), the alarm workers.no_server {server, labels, want, why} (stage A,
                 A6)
                 the competition of subsystems for the last room of a server (room of different roles) is an admissible delay;
                 the common memory ceiling of a server over all roles is a limit of the scheme (R12)
withdraw on deadline: in flight(s) > 0 for longer than WANT_GRACE (N1.4 terms) → want(s) := 1 + |live numbers ∩ {2…want(s)}|; the script
                 then renumbers: it stops a number above want, starts a missing one below; stopping a worker with
                 an assignment is a move of the units (ADR-0084 item 7; ADR-0084 addendum (4) R27);
                 the server «failed to raise» for RAISE_QUIET, raise_failed.<s>.times + 1, the alarm workers.raise_failed
                 {server, labels, want, why}; after RAISE_FAILS_LOUD in a row — of raised severity; it is removed when
                 the server raised the order; the shortage is ordered on the next candidate in the same pass; the base does not count
                 toward «failed to raise» (R6)
number above want: a live role process of the server s (the name and the number N — the slot name contract, «Role process name and its number»; not a role
                 process — the rule does not apply) with a number greater than want(s) (raised after the withdrawal of the order, a shrink victim before its stop, a remainder
                 of a door race) — not in the pool (as retiring) and gets no units; the server script stops it
                 (P/02.4 N1.5 rules 3); the controller does not raise want(s) (ADR-0084 addendum (4) R28 instead of R25)
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R054

old-sha256: b00efb1e50ef25fd2e9debe4464dbf4b2077dc9ff6e8d63b48f5262bdc80576b

<!-- req: P/04-R054 -->

```
console: request, 409 server answers, platform/decommission/<host>, door deletion and withdrawal remain P/06.6 N3.
existing valid final mark and standing request: do not rewrite the mark, its slots or remaining contributions; no new cleanup is authorized.
0. Resume a readable pending row before admitting a new plan. Its fixed request_index must still be the current request.
   Before mutation validate the progress invariants: remaining names are distinct and disjoint from released/skipped;
   released and skipped are disjoint; current is an ordered subset of released. In cleaning, slot_cursor < len(current)
   and from_cursor <= len(from); every from prefix belongs to this subsystem. The from list is frozen at acceptance from
   the declared owned books, never rebuilt from a later manifest. A malformed progress plan is a step error: keep it,
   do not infer completion, release/delete anything or replace it with a fresh plan. Schema readability alone is insufficient.
   No pending/final row: the server is heard by the ordinary observation rule -> leave the request standing, no mutation;
   otherwise completely read the request, owned slots and required metadata. An incomplete/unreadable source is not an empty list.
   Fix the original readable slots with server = s as ordered {name,index}, the owned from prefixes, asked_at, manifest_rev,
   units/holds metadata. Preflight every full key, the largest reachable serialized progress row and final mark, row weights,
   and real batch-body ceiling. Reserve the P/01 wire index width for cleanup_index; never parse an opaque version.
   An unrepresentable plan is a step error before any slot/order change, not a partial final mark.
1. Accept pending with cas "" and delete an existing want row with its read cas in one conditional batch. Guards: the own
   placement_turn version and the fixed request_index. Count both writes. State prepared has remaining candidates; no candidates
   means finalizing. The pending server is outside the placement pool and gets no new orders/automatic want-row creation.
   After acceptance continue only this frozen plan, also after a break or a later server answer; never add/adopt a new holder.
2. Prepared: read each next candidate only to confirm its original index and obtain the unchanged readable slot items.
   A different index (including absence) is obsolete: move its name to skipped, never substitute the new version for release.
   A non-answer postpones the step; it is not obsolescence. Keep holder/gen/server/until, set released = "true"; never invent gen.
   Write up to BATCH_WRITES - 1 slots with their original cas plus pending with its read cas, guarded by turn and request.
   Atomically record their names in released/current and enter cleaning; the one returned batch index is the version of ALL
   those released slots AND pending. After a lost answer, a cleaning row with empty cleanup_index carries that exact release
   index as its own row index: no slot reread is needed. With no from families, the same batch advances directly to prepared
   or finalizing with empty current/cursors. A refused release batch changes neither slots nor progress: barrier/re-read pending;
   only discard candidates proved to have changed from their planned index, never retry a release against a newer slot version.
   Persist skipped candidates under pending cas and turn/request guards; if none remain, advance directly to finalizing.
3. Cleaning: process one current slot at a time, from prefixes in their fixed order, split across bounded batches.
   Derive its authority from cleanup_index when non-empty, otherwise the current pending row index. Before ANY progress rewrite
   preserve that exact authority in cleanup_index; a later pending index must not replace it. Delete existing contribution rows
   by their read cas plus pending progress in one batch, guarded by turn, the fixed request and this slot's exact release index.
   Count all deletes AND progress/service writes, all guards, row weights and the full body. No guard key is also a written key.
   A confirmed missing contribution advances the cursor; an unknown read does not. A 409 conflict or 412 guard discards ALL
   remaining removals for this slot, with no new slot read/retry. Record cursor advancement under turn/request guards; never
   delete a new holder's contribution. Only confirmed cursor progress allows the next slot, then the next release chunk.
   On finishing a slot, advance slot_cursor and reset from_cursor. On finishing the whole current chunk, clear current,
   cleanup_index and both cursors, and set prepared if remaining is non-empty, otherwise finalizing, in a guarded progress write.
4. Every prepared/cleanup/final batch fits BATCH_WRITES, BATCH_GUARDS and the actual body ceiling. If even one indivisible
   operation plus required service writes cannot fit, record a step error and keep progress, never publish completion.
   Renew the turn by the ordinary rule; an unknown write or lost turn stops further mutation behind the existing barrier.
   A new holder re-reads pending after taking the turn and resumes its recorded phase, never restarts releases from slot names.
5. Only after remaining is empty and the current chunk's eligible removals are confirmed or conservatively discarded, enter
   finalizing. Atomically write the absent final <sub>/decommissioned/<host> mark from released/units/holds and asked_at (at = now),
   delete pending by cas, and delete a remaining want by cas if necessary, with turn/request guards. Count EVERY service write.
   The final mark is the LAST atomic step, never plan acceptance or merely the first released chunk. A failed/unknown final
   batch proves no completion: use the barrier and confirm the actual pending/final state before continuing.
6. A withdrawn/replaced request cancels its old pending row with cas and guards proving the current request state and own turn;
   it does not roll back confirmed releases/deletes, invent a final mark, or authorize an old delayed batch for a new request.
   Withdrawal removes an existing final mark as before. The resource publishes its door again; contributions return by normal
   start/capture cleanup, not by rollback. A new request requires a new admission and fresh plan.
```

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R057

old-sha256: ccf33646fe49f3d1f50ff9a324e4109b3bda7ee2e6d100a43d4ae1e39c473cd6

<!-- req: P/04-R057 -->

```
before every write of a placement row (place, move, remove): a missing manifest_rev is unreadable, never stamped;
row.manifest_rev > my revision
                                                                       → do not touch; the row — into manifest_behind
manifest_behind (N1.2): the number of rows of this pass whose write is postponed because of a lagging manifest; each row —
                        once per pass, however many write attempts touched it (C04-MANIFEST-BEHIND-COUNT-01)
```

---

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R060

old-sha256: 005bf93dc4bf1a3aed9444fb6b49a07613487ce968dcac279431a25b2cee2fb3

<!-- req: P/04-R060 -->

The current controller start check uses the common block of [P/06.6](../../06-console/spec/06.6-console.norms.md) N3 «console start — schema check». The platform/schema row, SCHEMA and its raise remain P/06.6 N1.1a, N3 «raise_schema».

### `Platform/04-controller/spec/04-controller.norms.md` P/04-R065

old-sha256: 437481e72e91bfa38e82e0478716a33d96b4ef964d1967d70fce00f63b240d55

<!-- req: P/04-R065 -->

```
t = 0      the server is off; its daemon — minus a vote; its heartbeats and its door stop changing
about 45 s the controllers with already known heartbeats: the slots expire; the resource is silent; the tolerances of N3
SLOT_TERM + LOST_AFTER with all the tolerances of N3 and free capacity → move; a new epoch. With unknown/unavailability/lack
           of room there is no common term; the archive stays on the volume. The neighbours have only confirmed mirror copies
return     the daemon restarts with the saved member.json (does not repeat join); the resource pulls the buckets (restore); the workers take free names; names with expired
           slots — by the word of the controller; nothing moves back, except a declared `home` (N3 «pass()», step 7, HOME_BUDGET)
```

### `Platform/06-console/spec/06.5-console.norms.md` P/06.5-R002

old-sha256: 017e2a08287b2ea4b8b778ce6c9417fd8513dcdc181881cfeee1e7d473b1b83e

<!-- req: P/06.5-R002 -->

**Time.** The rows of the chapter (`door/signer`, `door/keys`) have no time fields. The time that the chapter reads follows
[the canon of N0 of P/01.1](../../01-store/spec/01.1-store.norms.md#time-in-a-row): the worker heartbeat — `ts`,
`previous_hb` ([P/03.4](../../03-worker/spec/03.4-worker.norms.md) N1.1), the resource heartbeat —
[P/05](../../05-resource/spec/05-resource.norms.md) N1.4, a snapshot shard — `ts` ([P/04 N1](../../04-controller/spec/04-controller.norms.md)
«Time»); `expires` of the door token — the integer wall-clock seconds of the issue + DOOR_TOKEN_TTL, a JSON integer (review of stage B
6–7, № 10; [the door token contract](../../common/contracts/door-token.md) «Token»; review of stage B 3–5, V1).

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `door/signer`, `door/keys`;
- writes: `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append);
- reads: `platform/manifest/<sub>`, `platform/manifest/<sub>/rev`, `platform/manifest/<sub>/files/<sha256>/<n>`, `<sub>/placement/<id>`, `<sub>/controller/placement_intent`, `<sub>/controller/pass`, `platform/doors/<host>`, `<sub>/heartbeats/<name>`, `platform/resources/<server>/heartbeat`, `<sub>/slots/<name>`, `<sub>/snapshot/<worker>`, `<sub>/snapshot/unplaced`, `<sub>/holds/<place>`, `<sub>/<manifest:unit.rows>/<id>`, `<sub>/want/<host>`, `<sub>/contenders/<name>/<box>`, `<sub>/<manifest:tables>/<name>`, `<sub>/decommissioned/<host>`.

The `audit` journal of the chapter has the kinds `door.issued` and `pass.called` (the gate and pass contract `journal`); a
table row is read by the door `/where/<table>/<place>` (review of stage B 6–7, № 41).

The order rows `<sub>/want/<host>` are read by the console for the series `workers_wanted{server}` (N3 «/metrics — text»),
the contender marks — for `name_conflict` in `/servers` (N3 «/servers») (review of stage B 3–5, № 10).

The control rows (`platform/servers/<host>`, `platform/drain`, `platform/decommission/<host>`, `<sub>/policy`) are
written by the console through the doors of [chapter 6.6](06.6-console.norms.md); here they are only shown in `/servers`.
The console reads the snapshot shards for the age and the series of `/metrics` (N1.3); the writer is the controller,
[P/04 N1.3a](../../04-controller/spec/04-controller.norms.md).

### N1.1 Three parts

### `Platform/06-console/spec/06.5-console.norms.md` P/06.5-R008

old-sha256: f6301ff042e51fe8a88b599d98d92f7d1c94e10eae5ce88f558272b7f0db3f1e

<!-- req: P/06.5-R008 -->

All JSON answers of the own doors are described by OpenAPI components. Every `GET` of the console — of its own doors and of the doors of other chapters that the console serves (`/manifest` — N2 «GET /manifest»; `/<rows>` — 6.1, there is no `GET` of one unit; `/policy`, `/drain`, `/unplaceable`, `/where/<id>` — 6.6; `/events` — 6.4; `/schema` — 6.6, `/<table>` — 6.1) — also answers `HEAD`: the same code and headers, without a body; every contract that declares such a URL lists `head`. HTML, JS, CSS and metrics are strings of the corresponding media type, not JSON. A successful `/healthz` is exactly `{ok: true}`. `/mounts` — `{root, mounts: {subsystem name: ManifestView}}`. `ManifestView` — N2 «GET /manifest» (moved from M10/2 without weakening).

`Servers` — `{policy, servers: {name: ServerRow}, status?}`. `ServerRow` contains the required `resource`, `resource_heard_at`, `resource_url`, `space`, `labels`, `labels_node`, `labels_source`, `draining`, `decommission`, `decommissioned`, `decommission_refusal`, `decommission_warning`, `decommissionable`, `lost`, `requires_resource`, `placeable`, `why`, `workers`. An unknown address/place/time/cause and an absent decommission request are represented by `null` by the schema. A field whose source row is unreadable is `null` if the schema keeps it required, otherwise absent (the common rule of output; `decommissioned: null` — the decommission mark does not read; the answer of the Architect 2026-10-25, G-03). `lost` is an array `{unit, place?, worker?}`; `decommission` — `{at, by, gone?}`. Labels are arrays of words. `WorkerRow` requires `worker, load, capacity, labels, state, idle_by_policy, hung, name_conflict`; `name_conflict` is a boolean. The optional details and their types are listed closed in the schema. `status` outputs the JSON values declared by the specification, not arbitrary secret fields.

**Outputs of the console — derivation from rows and heartbeats** (the clock — the monotonic clock of the console; the first look at a version — as fresh):

| Output | Rule |
|---|---|
| `/metrics` at root | the series of all subsystems of the catalogue and the platform series `w2c_*` (N3); at `/<sub>/metrics` — the series of this subsystem only, without `w2c_*` |
| series `<sub>_<console.running>` | the manifest metric that `console.running` names, computed by its declaration (`from`, `agg`, `equals`, `live`) like any series of `metrics[]` (N3 «Manifest series `metrics[]`»; C06-CONSOLE-RUNNING-DEF-01, the decision of the Architect 2026-10-29); for a declaration without `equals` the elements `phase: sealed` and `phase: unreadable` are not counted — such a unit does not run, the element states the cause (P/03.4 N1.1; W03-G02, W03-G05); heartbeats read and none live — `0`; a non-answer when reading the heartbeats (and their listing) — `lapse` of the [observation contract](../../common/contracts/observation.md): the series from the memory of the last read versions; heartbeats never read since start — 503 for the whole `/metrics` (C06-PULSE-LAPSE-503-01, the decision of the Architect 2026-10-29) |
| `ServerRow.resource` | the resource state `resource_state` of the [observation contract](../../common/contracts/observation.md) (the observer — the console, its clock); no derivation of its own |
| `ServerRow.resource_heard_at` | the wall-clock seconds of the console (time by P/01.1 N0) at the moment it first read the current version of the resource heartbeat as readable ([observation contract](../../common/contracts/observation.md) «Observation of a version»); with an unchanged version it does not move; an unreadable version, a non-answer and a confirmed absence do not change it; the console never saw a readable heartbeat — `null`; the heartbeat field `at` of the writer is not used (C06-SERVER-DIAGNOSTICS-163-01, the decision of the Architect 2026-10-27) |
| `WorkerRow.state` | as `worker_state` of [chapter 6.1](06.1-console.norms.md) N2 («`rows` in `GET /{rows}`»): `live` at a heartbeat age ≤ 45 s (`LOST_AFTER` of the [observation contract](../../common/contracts/observation.md)), otherwise `stale` |
| `WorkerRow.capacity` | the heartbeat field `placement.capacity.from` — a finite number as in the heartbeat, a fraction without rounding; no field — `capacity.default`; the field is not a number — `null`: the worker accepts no new units ([P/04 N1.3](../../04-controller/spec/04-controller.norms.md); journal of cammeta-go, lesson 9 № 5) |
| `WorkerRow.load` | the load of the worker — `load` of the [pool contract](../../common/contracts/pool.md) (the weight of the units with reserves; the unit row absent, unreadable or the weight not a number — 0; C06-POOL-FACTS-33-01) |
| `WorkerRow.idle_by_policy` | `true` when, with `servers: distinct`, a live worker of the pool is not the keeper of its place or has no place (`""`); otherwise `false`, a non-live one included ([pool contract](../../common/contracts/pool.md) «idle_by_policy»; C06-SERVER-POLICY-33-01, answer (1)) |
| `/resources` | the servers with a read resource heartbeat; `state` — `live` or `silent` by the heartbeat, as in `resource_state` of the [observation contract](../../common/contracts/observation.md) (`/resources` does not take the door row into account); `workers`, `running`, `unknown`, `instances`, `pass_stalled` — from the resource heartbeat [P/05 N1.4](../../05-resource/spec/05-resource.norms.md) as is (keys `<sub>/<slot name>`); an unreadable heartbeat does not enter the answer, it is counted by `w2c_resource_heartbeats_garbled` |
| `WherePlace` without a door signer | the field `door` is absent altogether (not `null`) |
| worker heartbeat in `/servers` and `/metrics` | unreadable (N0 P/01.1 «Stability of output»: not a JSON object, not in the form of P/03.4 N1.1), `worker` ≠ the name in the key, or the key name not by the slot name grammar of P/03.2 N1.4 (`W-N`) — there is no heartbeat: the worker is not shown, the heartbeat is counted in `<sub>_heartbeats_garbled`, the answer is 200 (reconciliation of python and go M10/6–11, C3, C15) |
| element of `status[]` of a worker heartbeat | an element not in the form of P/03.4 N1.1 — the list is one: the row `/status` of the [heartbeat family outcomes](../../03-worker/data/heartbeats.outcomes.tsv) (the bounds — `RunningUnit` of the [contract](06-console.api.openapi.yaml); review of stage B 6–7, № 15) — the element is unreadable: `GET /{rows}` of [chapter 6.1](06.1-console.norms.md) skips it, the other elements of the same heartbeat are output; the unit «element» exists only in `GET /{rows}`: in `/servers`, `/metrics`, `/where` and for a live worker with a door (N1.8) such a heartbeat counts as unreadable (the row above); a heartbeat unreadable as a whole comes before the element: `GET /{rows}` does not output its elements either (review of stage B 6–7, № 14); the outcome by element — the row `/status` of the [heartbeat family outcomes](../../03-worker/data/heartbeats.outcomes.tsv) (a change of behaviour: review of stage A 6–7, № 13 — before, a non-integer `observed_revision` did not skip the element) |
| `ServerRow.labels`, `labels_node`, `labels_source` | `labels` — the effective labels of the server: the row `platform/servers/<s>` wins over the node labels ([chapter 6.6](06.6-console.norms.md) N2.1); `labels_node` — the node labels from the field `labels` of the heartbeats of the workers of the server; `labels_source` — `console` with a readable row, `node` without the row when there is a read heartbeat of a worker of the server, otherwise `unknown` (reconciliation of python and go M10/6–11, C16); the row `platform/servers/<s>` exists but does not read — `labels: null`, `labels_source: null`, not `node`/`unknown`, the series `<sub>_servers_labels_unread` (the answer of the Architect 2026-10-25, G-18) |
| `WorkerRow.labels` | the effective labels of its server, as `ServerRow.labels`, — not a heartbeat field (reconciliation of python and go M10/6–11, C16); the source row `platform/servers/<s>` does not read — `null`, as for `ServerRow.labels` (C06-WORKER-LABELS-129-04) |
| `ServerRow.placeable`, `why` | `true` when the server has a live worker of the pool ([pool contract](../../common/contracts/pool.md): the pool already subtracts `requires: resource` at silent, drain, decommission); labels are a property of a unit, they do not enter `placeable`; capacity does not enter; there is no such worker — `false`, `why` — «no eligible live worker» (reconciliation of python and go M10/6–11, C17; C06-SERVER-POLICY-33-01, answer (4)) |
| `ServerRow.decommissionable` | `true` when a decommission request without `gone` would be accepted now (the console side of the server decommission — [chapter 6.6](06.6-console.norms.md) N3 «decommission_server», [observation contract](../../common/contracts/observation.md): neither the resource, nor a worker, nor a slot of the server is heard for `LOST_AFTER`, the resource was heard at some time); an empty server under this condition — `true`; otherwise `false`, the cause — `decommission_refusal` (reconciliation of python and go M10/6–11, C18) |
| `WorkerRow.released`, `slot_until`, `slot_garbled` | no slot row — none of the three fields; the row is unreadable or not in the form of P/03.2 N1.4 (the state torn — [slot contract](../../common/contracts/slot.md)) — `slot_garbled: true`, `slot_until: null`, no `released`; readable — `released` and `slot_until` from it, `slot_garbled: false` (reconciliation of python and go M10/6–11, C19); `released` is `true` only at `"true"`; at `"taking"` (a capture in progress, P/03.2 N1.4) — `released: false` and `slot_taking: true`, otherwise there is no field `slot_taking` (added by the Quint pilot, F2) |
| resource heartbeat in `/resources`, `/servers`, `/metrics` | unreadable — not a JSON object; `server` ≠ the server in the key; a required field of `ResourceRow` is absent (except `state`, the console derives it) or a field is not of its type — except `schema` and `build`: for them the field outcome of [chapter 6.6](06.6-console.norms.md) N1.1a `heartbeat` (`schema` not an integer — the schema is unknown: in `ResourceRow` — `schema: null`, review of stage B 6–7, № 6; `build` not a string — `build: null`, unknown, V7 item 3, the decision of the Architect 2026-10-28, P1; row 14 of the list; `retention_garbled`, `retention_withheld` not in form — `null`, not absence), the heartbeat stays readable, as a worker heartbeat does (added by the family inventory; checked by reading — there is no scenario of `/resources` with such a heartbeat, the field outcome — sc. 12 of the acceptance of chapter 6.6); a field outside `ResourceRow` (its fields are the closed list of the heartbeat fields that the resource writes, P/05 N1.4). An unreadable heartbeat does not enter `/resources`, does not confirm life (`resource_state` of the [observation contract](../../common/contracts/observation.md)) and is counted in `w2c_resource_heartbeats_garbled`; the answer is 200 (reconciliation of python and go M10/6–11, C11) |

`/resources` is an object by server name with full `ResourceRow`: required are `server, ts, url, schema, build, usage, usage_at, space, volumes, units, mirrors, short, state, door, waits, restore, mirror`; `schema` is an integer ≥ 1 or `null` (the resource schema is unknown, [chapter 6.6](06.6-console.norms.md) N1.1a `heartbeat`; № 6); With `door.mode=mtls`, `door.cert_until` is required; with loopback it is optional. the diagnostic extensions are listed in the contract. This is an observation of resource heartbeats, not a certification of the availability of every object. `/where/<table>/<place>?unit=<id>` returns `{worker, place, server, door?}` or 404 `{unreachable}` with the same value in the header `X-Unreachable`. An unknown table — 404 before the check of `unit`, a known one without `unit` — 400.

The common refusals of the console have the form `ConsoleRefusal` (N2 «GET /manifest», moved from M10/2): `{detail, error, field?}`, the words of `error` are the closed list [`refusal-words.tsv`](../data/refusal-words.tsv), `field` — [chapter 6.1](06.1-console.norms.md) N2 «Refusal: `error` and `field`» (ADR-0094 B5); 503 includes `denied` at a loss of trust, `busy` with `Retry-After: 1` when a lane is full and `unavailable` at an unconfirmed required read and at a shell with `on…=`; 429 — `too many attempts` with `Retry-After`; `/where` not an id — 400 `badkey` (class GP-L03, the decision of the Architect 2026-10-28). Special bodies: `NoVersion` — `{error: "no such version"}`; `MountedPage` — `{detail, error: "is mounted"}`; `NotPlaced` — `{reason}`. 400/408/413 describe a read refusal, `error` — `denied` (GP-L03, the decision of the Architect 2026-10-28); the body is bounded by the bytes actually received, a short one gives 400. `/session` GET to an anonymous caller gives 200 with the state; a bad POST attempt — 401, the open mode — 400, a wrong password of the emergency login — 401, no emergency account — 403 (chapter 6.3 N4; review of stage A 8–10, № 41). DELETE removes both cookies (the procedure and the refusals of `/session` — [chapter 6.3](06.3-console.norms.md)). The lane, framing, trust/loopback, identity, Origin by cookie, grants and reading are checked in the order of N3; a refusal has no side writes of the door.

The doors of units, placement, events, tables and the schema belong to chapters 6.1, 6.6, 6.4 (and [P/05](../../05-resource/spec/05-resource.norms.md) for `/events` of the resource), 6.1, 6.6. `/domain/*` and the open `/api/*` — [chapter 6.7](06.7-console.norms.md) (the late layer: forwarding, N1.4, N1.6, N1.8; `/api/held`, `/api/backup`, `/domain/move` at the console — N1.8, N1.12, N1.13; the list of the domain doors and the forwarding by one function — [forwarding contract](../../common/contracts/forwarding.md)) and [P/08.8](../../08-domain/spec/08.8-domain.norms.md) (the move doors of the process `domain`: `/api/prepare`, `/api/take`); the successful body of a forwarding belongs to it (review № 27). They are listed as dependencies, without a fictitious schema «any object». The own routes of this chapter `/manifest`, `/servers`, `/unplaceable`, both forms of `/where` and `/metrics` are also declared explicitly with the prefix `/<sub>`; the prefixes of the delegated doors are at their owners; the common `/session`, `/mounts`, `/platform` are not mounted. An absent `v` or another string, a non-numeric one included, — 404 `NoVersion`.

The short paths of units, tables, blob fields, /policy, /manifest, /servers, /unplaceable,
/where and /metrics select CONSOLE_ROOT; the form /{sub}/… explicitly selects a loaded
subsystem, root included. In the OpenAPI of the owner the full URL can be given by a pair
of the standard servers + paths: the console origin without a trailing / or origin/{sub},
then the operation path. This is an executable description of the URL, not an explanation of x-mounting.
The common /drain, /schema, /session, /mounts, /healthz, /resources, /platform/*,
/servers/{server}/labels, /servers/{server}/decommission, /console/batch, /changes and /folders do not get such a prefix;
the first segments `console`, `changes` and `folders` are already closed by the loader from the names of subsystems, units and tables (P/02.1 N1.2a).
Events /events and marks /marks follow the forms of their owner (chapter 6.4). Requests, the person ledger and the number counter
always name the subsystem: /{sub}/requests, /{sub}/asked/{sha16} and /{sub}/next_id, CONSOLE_ROOT included; the route /{sub}/asked/…
exists only for a manifest with requests.per_person, the segment {sha16} is exactly 16 lowercase hex, otherwise 404 NoRoute (reconciliation of python and go M10/6–11, C27);
the short /requests and /asked/{sha16} are outside the profile, an unknown route — 404 by N2/N4.

The mounting area is admitted by the loader P/02.1: a subsystem name is not one of the 21 reserved words, and no subsystem name crosses unit.rows/tables of the catalogue, its own included. A catalogue that is not admitted does not start the console; there is no priority that hides one of two promised doors.

### `Platform/06-console/spec/06.5-console.norms.md` P/06.5-R016

old-sha256: d321743276008a967dbbb5c4c8a106df3ef04e1a57d0228aae2230058d9050a3

<!-- req: P/06.5-R016 -->

DOOR_TOKEN_TTL has its sole value in [runtime-constants.tsv](../forms/runtime-constants.tsv); token bytes and validation remain the common contract.

```
read intent → placement of the needed unit → intent by the read rule of the observation contract; the intent version changed → repeat;
a required read is not confirmed → 503. With an unchanged active and id in members take target/reason of intent,
otherwise worker/reason of the placement row; the absence of placement does not cancel target of an active intent.
reason is served as read, "" included — 200, without a fallback word: a non-empty reason is the duty of the writer P/04
(OpenAPI Where.reason; C06-WHERE-EMPTY-33-01).
the effective worker "" or none → 404 {reason: why of the unit from the field unplaceable of the last pass report, without it —
  «not placed: no worker holds it»} (chapter 6.6 N2.2 — the owner of the door; changed by the reconciliation of python and go 2026-10-18)
server — chapter 6.6 N2.2 (the worker heartbeat, otherwise the slot row, otherwise null); the door url (door.routes of the manifest) → door: {url, token (door1.<kid>…, by the Ed25519 key of door/signer,
TTL DOOR_TOKEN_TTL: expires = floor(now) + DOOR_TOKEN_TTL, integer seconds of the wall clock, the fraction is dropped (the decision of the Architect 2026-10-20, review of stage B 6–7); in the token user, unit, holder, routes — the door token contract), expires, routes}; token is issued by view on the unit;
routes of the token and of the answer — the routes of door.routes with the admission token whose rank (P/02.1; none — view) is allowed to the human on the unit:
may with need = rank of this route (the right contract, caps none < view < edit < admin) — yes; none at all — no field door, no journal
(ADR-0115 addendum (18) item 2, addendum (19) item 1: the plugin page is a route with rank edit, view does not get it);
every issue — the journal door.issued; directory — where the unit is seen (5 s cache), scans
```

Door token — bytes: the string `token` (`door1.<kid>.<claims>.<sig>`, the claims in JCS, an Ed25519 signature) and the row `door/keys` —
[the door token contract](../../common/contracts/door-token.md) (the chapter is the owner of the contract; moved there from this block; review of stage B 3–5, V1). Here —
the signer:

```yaml
door/signer: {kid, seed_secret} — seed_secret — 32 bytes of the Ed25519 seed in 64 lowercase hex (a secret by the suffix, the envelope
            of the ring — the sealing contract, chapter 6.2); the writer — the console at the first issue if there is no row (create-once);
            resealing at start — chapter 6.2 N3 «reseal at start» (review of stage B 6–7, № 2)
door/keys:  the console adds its own signer kid {kid: the public key of the seed} by a write with cas by the read version (no row —
            cas ""; conflict — re-read) when creating door/signer, at start (after resealing, if door/signer exists and
            reads) and at an issue if the kid is not in door/keys (review of stage B 6–7, № 3: a console that fell between the two writes
            repairs the keys by its next start); the value under its own kid differs or door/keys is unreadable — do not touch the row,
            a log line, no token is issued (no field door); another value under its own kid — also the alarm door.keys_conflict
            {kid} (class alarm, into console.alarms/<instance> by the event journal contract) at the first observation of this version
            of the row door/keys by the console (after a restart — again): the operator sees that the doors of the holders are closed (the decision of the Architect 2026-10-20, review of stage B 6–7)
```

**Races.** The double read of intent filters out a change of the accepted decision; with a stable active the target worker is taken from it, even before placement is written. The effective placement and the heartbeat are read separately. The answer names the observed holder; a move can complete before the door is used. One moment for all fields cannot be promised. No reliable door — the field `door` is absent; null in an HTTP answer is not admissible; a read error of the assignment — 503, not 404. The validity of the operation is checked again by the holder by epoch/lease. The forms `Where`, `NotPlaced`, `Door` are the exact forms of the owner (chapter 6.6 N2.2).

### `Platform/06-console/spec/06.5-console.norms.md` P/06.5-R017

old-sha256: cad86954c1681388f64a6d703a452202a31f1409c51e34995d58cdcacb70b32a

<!-- req: P/06.5-R017 -->

After the common framing/trust/identity: the table is not declared or is not a table of places — 404
with a text refusal; this is checked before the requiredness/form of unit. Then unit is required,
has the form of a unit id of the chosen subsystem (otherwise 400); view on this unit is needed.
After the grant read the hold `<sub>/holds/<place>` and the holder heartbeat by P/03.4 N1.1 and P/03.2 N1.3 (the logical name
worker = hold.by, not the instance hold.holder); the place row — for the 404 answer. A non-answer when reading the hold or the heartbeat —
`lapse` of the observation contract: the location from the memory of the last read versions with their age, the freshness and life of the
holder — by the observation contract («Hold of a place», «Freshness»); the source was never read since start — 503 `unavailable` (C06-WHERE-PLACE-LAPSE-01, the decision of the Architect 2026-10-29, refines P1 V7 item 3 for `/where`).
503 `unavailable` — also when the hold row exists but does not read, or the holder heartbeat does not read: the hold is not
known, «no hold» is not asserted ([observation contract](../../common/contracts/observation.md) «Hold of a place»; V7 item 3, the decision of the Architect 2026-10-28, P1; row 27 of the list). There is an effective hold ([observation contract](../../common/contracts/observation.md) «Hold of a place»)
— 200 `{worker, place, server}`: `server` is the field `server` of the fresh holder heartbeat, `""` → `"?"`; the place row is not
required for this answer — it is absent, it is unreadable or its `server_field` is empty or not a server name, the answer is the same.
Reliably no effective hold — 404 `{unreachable: place@<s>}` with X-Unreachable of the same value: `<s>` is the element
`server_field` of the readable place row when it follows the server grammar (`SERVER_NAME` P/02.4 N1.2), otherwise `?` (there is no row,
it is unreadable or not read, `server_field` is not declared, empty or not by the grammar) (C06-WHERE-PLACE-SERVER-33-01, the decision of the Architect 2026-10-25). A reliable door of the holder with declared
door.routes, an available signer and a confirmed addressee of unit adds door:
the same Ed25519 token for DOOR_TOKEN_TTL, user/unit/holder/routes and door.issued,
as in the procedure `/where/<id>`; `unit` of the place token is the unit of the request whose data lie in the place, not necessarily held by this
holder (the door token contract «The place token»; ADR-0091 addendum (7) item 2, addendum (8) item 9); routes — the routes of `door.routes` with
the admission `token` and a rank `rank` allowed to the human on the unit of the request — as in the procedure `/where/<id>` (ADR-0115 addendum (19) item 1). A token must not be issued to another or an unconfirmed holder: `door` is an admission, only by the reads of the hold
and the heartbeat of this procedure; an answer from memory (`lapse`) carries no field `door` and writes no journal `door.issued` (C06-WHERE-PLACE-LAPSE-01, the decision of the Architect 2026-10-29, refines P1 V7 item 3 for `/where`);
when the door cannot be confirmed, the field is absent, not null, and the location stays the answer.

**Races.** The hold/heartbeat are not a common snapshot; the answer does not extend the lease. A holder that
changed after the answer is cut off by the epoch/lease check at the door. A read error is not
declared an absence of the place, the absence of a token is not declared an absence of a hold.

### `Platform/06-console/spec/06.5-console.norms.md` P/06.5-R018

old-sha256: 5dc47dc99d13bb12778fbaf0c686eddcb4c0122264dba9eb3626f7a12096d802

<!-- req: P/06.5-R018 -->

```
per subsystem (<sub>_…; here and in all series of the module <sub> is metrics.prefix of N2 «GET /manifest»): workers_live; worker_headroom{worker,server}; headroom; worker_load{worker};
  epoch_conflicts{worker}; failover_seconds{kind=worst}, failover_seconds{kind=last,worker}; failovers_unmeasured; heartbeats_garbled;
  heartbeat_skew_seconds_max|min; workers_hung; workers_unjudged; units_unjudged; reconcile_last_pass_age_seconds;
  reconcile_last_success_age_seconds; reconcile_pass_seconds; reconcile_failures; units_unplaced; units_diverged;
  reach_moves_total; reach_unplaced_total; unplaced_deleted_total; servers_decommissioned_total; slots_released_total;
  passed_calls_total (only for a manifest with door.pass of the second kind, and at zero: the accepted callbacks of this instance, the gate and pass contract counter; ADR-0094 B1);
  decommission_requests_standing; name_conflicts; groups_waiting; servers_labels_unread; workers_needed{labels};
  units_short{labels}; workers_wanted{server}; workers_withheld{labels}; server_labels{server,labels,source};
  worker_fenced{worker}; worker_store_errors{worker}; worker_pass_failures{worker}; worker_unconfirmed{worker}; snapshot_age_seconds;
  snapshot_ahead_shards; snapshot_garbled_shards (N1.3; reconciliation of python and go M10/6–11, T6); audit_failures; garbled_rows; idempotency_store_failures; requests_ledger_garbled;
  <running> (console.running); the series of metrics: of the manifest (<sub>_<name>, gauge | counter | histogram)
  # always, and at zero (the heartbeats are read, the store answered): workers_live, headroom,
  # failovers_unmeasured, heartbeats_garbled, reconcile_last_pass_age_seconds, reconcile_last_success_age_seconds,
  # units_unplaced, decommission_requests_standing, snapshot_age_seconds, snapshot_ahead_shards, snapshot_garbled_shards
  # and the counters of the console itself
  # audit_failures, garbled_rows, idempotency_store_failures, requests_ledger_garbled; the series with labels — by their
  # objects; the series from the pass report and the shortage (reconcile_pass_seconds, reconcile_failures, units_short, workers_withheld,
  # workers_needed …) — with a read report; a shortage, a report or a heartbeat that cannot be read removes the series and does not
  # fail the answer (N0 P/01.1 «Stability of output»; reconciliation of python and go M10/6–11, C2, C8)
  # worker_headroom{worker,server} — the heartbeat field placement.headroom.from (the default headroom; P/03.4 N1.1) of a live worker as
  # is; headroom — their sum over the live workers of the subsystem (an «always» series; no live ones — 0); a field that is not a finite integer ≥ 0 — no series
  # worker_headroom of this worker, 0 into the sum, a count of the unreadable field (<sub>_console_rows_garbled{table="field"}, as for value);
  # no field — the same without the count; the controller does not read the field (P/04 N1.3) (C04-HEADROOM-UNREADABLE-01, the decision of the Architect 2026-10-29)
  # name_conflicts — the number of different names with a fresh contender mark (an unreadable one too, N3 «Contenders»), without «-» (N3 «/servers» «Contenders»;
  # C06-CONTENDER-PROJECTION-33-01): the console series comes from the marks <sub>/contenders/*, not from the field name_conflicts of the pass report
  # <sub>/controller/pass (that field is the count of the controller, the console does not take it into this series)
  # groups_waiting — without labels: the sum of short[].groups of the report <sub>/controller/pass; short absent or [] — 0; short not in
  # form (the outcome /short of the family controller-pass) — no series; no report or it is unreadable — no series (C06-GROUPS-WAITING-33-01, the decision of the Architect 2026-10-25)
  # heartbeat_skew_seconds_max|min — ts of the heartbeat minus the wall clock of the console at the read: plus — the clock of the writer is ahead
  # (reconciliation of python and go M10/6–11, C23); server_labels{server,labels,source} — source by the word labels_source of ServerRow: console | node | unknown
  # (reconciliation of python and go M10/6–11, C24)
  # reconcile_last_pass_age_seconds — how many seconds passed on the monotonic clock of the console since the last change of the object
  # <sub>/controller/pass (P/04 N1.2) that the console saw; no object or the console has not yet seen a change — −1
  # («unknown», not 0: the first look gives no age); reconcile_last_success_age_seconds — the same from the last seen
  # change of its field last_success, there was no successful pass or no change was seen — −1
  # workers_wanted{server} — want of the order row <sub>/want/<host> (P/04 N1.1), one series per readable row;
  # the row does not read — no series; it is read by the server script (P/02.4 N1.5): no series — start nothing and stop
  # nothing; workers_withheld{labels} — how many processes of the set the controller did not order because there is no suitable
  # server (the pass report, P/04 N1.2 withheld); the order series — ADR-0084
  # worker_fenced{worker} — 1 when was_fenced of the heartbeat is true, otherwise 0; worker_store_errors, worker_pass_failures,
  # worker_unconfirmed — the fields store_errors, pass_failures, unconfirmed of the heartbeat as is (P/03.4 N1.1); no field or the heartbeat
  # does not read — no series of this worker (the VMS request «heartbeat and malformed row», the decision of the Architect 2026-10-23)
  # failover_seconds{kind=last,worker} — started − previous_hb of the last heartbeat of the worker (P/03.4 N1.1: previous_hb —
  # ts of the heartbeat that the worker found under its name), if both are finite numbers and the difference is ≥ 0, otherwise −1; kind=worst —
  # one series without the label worker: the largest measured last among all workers of the subsystem that this console saw since
  # its start, none seen — −1 (C06-FAILOVER-WORST-NO-WORKER-01); failovers_unmeasured — the number of
  # instances (instance) whose heartbeat carries previous_instance and whose last cannot be measured; each instance is counted once.
  # The series are diagnostic: freshness and leases are not judged by them (journal of cammeta-go, lesson 9 № 6)
metrics[]:  the closed list of the keys of an element (the loader P/02.1 refuses others): name, type, from, agg, equals, when, default,
            live, labels, count, where, unheld, unless {table, where}, buckets, label, values; the meaning and the grammar of the values — the section
            «Manifest series metrics[]» below
of the platform, once (root); the source — the resource heartbeats of P/05 N1.4 and the request cleanup of this console:
  w2c_resources_live — the resources whose heartbeat changed within the last LOST_AFTER (≤ 45 s; the observation contract; a change of behaviour:
  review of stage A 6–7, № 1 — was «< 45 s»); w2c_resource_heartbeats_garbled — the unreadable resource heartbeats
  since the start of the console process; w2c_resource_full{server} — 1 when space.full of the heartbeat ≥ 1 (the volume is full: used = total), otherwise 0; space.full — a fraction
  of P/05 N1.4, served as is (journal of cammeta-go, lesson 9 № 8); w2c_resource_short_bytes{server} — the field
  short: how many bytes the mark asked to free and could not; w2c_resource_waits{server} — the waits of /events/wait now,
  w2c_resource_waits_held_total, _full_total, _replaced_total{server} — since the start of the resource (the field waits, P/05 N1.6
  «/events/wait»); w2c_resource_rows_garbled{server,table} — the unreadable rows of the tables read by the resource;
  w2c_resource_restore_left{server}, w2c_resource_restore_failures_total{server} — the field restore (the restore of
  events from the copies of the neighbours, P/05 N1.4 «Bucket restore»); w2c_resource_mirror_failures_total{server},
  w2c_resource_mirror_too_big_total{server} — the field mirror (P/05 N1.4 mirror, PEER_FAILS);
  w2c_requests_expired_total{sub}, w2c_requests_unknown_total{sub} — the requests that the cleanup of this console closed as
  expired and unknown since the start of the process (chapter 6.4 N3 sweep); a manifest without requests has no such series (reconciliation of python and go M10/6–11, C39);
  the feed of this instance (chapter 6.1 N3 «feed»; ADR-0094 B2), the series are always present: w2c_changes_subscribers — the door requests now; w2c_changes_tick_seconds — the duration of the last tick, no tick — 0;
  w2c_changes_tick_failures_total — the unconfirmed listings of the prefix; w2c_changes_rows_read_total — the rows read by the ticks: the cost of the feed beyond the listing;
  w2c_changes_messages_total — the messages of the history; w2c_changes_resets_total{reason} — the resets, reason: foreign (reset 1), evicted (2), rights (3), labels (4), folders (5), all five series also at zero
  # the sources are the fields of ResourceRow (N2) of a live and readable heartbeat, as is (reconciliation of python and go M10/6–11, C9, C10): waits — waits.waiting;
  # waits_held_total, _full_total, _replaced_total — waits.held, waits.full, waits.replaced; rows_garbled{table} —
  # garbled_rows.<table>; restore_left — the number of the restore neighbours with done: false; restore_failures_total — the sum of
  # restore.<neighbour>.failures; mirror_failures_total — mirror.failed; mirror_too_big_total — mirror.skipped (a bucket larger than
  # 64 MiB, P/05 N1.4 mirror); the field is absent in the heartbeat — no series of this server
exact weight aggregates worker_load and units_short — the exact nonnegative integer sums of P/04, read and emitted as decimal digits without binary64/int64 narrowing, rounding or saturation. This aggregate decimal is not RFC 8785 Number canonicalization. All other metrics, labels, counts, bucket le and equals retain the rule below.
all other values — by value, not by the notation in the heartbeat: the canonical JCS notation of a number (RFC 8785 §3.2.2.3 — ECMAScript
  Number::toString; ADR-0072): an integer with absolute value < 1e21 — in digits (61, not 61.0; age also 10; 76749071360, not
  7.674907136e+10), otherwise, and a non-integer, — the shortest ECMAScript notation (1e+21, 7.5, 1234567.5, 1e-7); -0 — 0; one rule
  for the sample, le of a bucket and the word equals (ADR-0055; the decision of the Architect 2026-10-27); the captions are escaped
```

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R011

old-sha256: bca3a3e4e4ad08b66fbe752199c6f0c83f73204f3ed0698aef6dd469eb794e81

<!-- req: P/05-R011 -->

**Bodies at the resource** (moved from M10/10 N1.5 `mirror` and N1.4, parts of
M10/10-06, -07, -08 by the move record; the decision of the Specification on question V2 of the move; the field `blob`, the digest, the bytes door of
the console, the cleanup of bodies — [chapter 6.1](../../06-console/spec/06.1-console.norms.md) N1.5):

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R012

old-sha256: b865a03d8dbe1ea4b62f5963576bd52ae97756413c6943883099987beb2fd828

<!-- req: P/05-R012 -->

```yaml
mirror:   every local body — to the next copies live neighbours of the ring (N1.4 mirror), always, regardless of mirror.enabled;
          copies — from the row platform/mirror (an integer ≥ 0), no row or no field copies — 1 (log of cammeta-go, lesson 10 № 1); the row
          does not read — bodies are not copied in this pass, the reason is in the heartbeat (settings_unread: mirror; V7 item 3, the decision of the Architect of 2026-10-28, P1; line 20 of the list);
          reception: hash while reading; PEER_FAILS; the copy door exists only for the key `<sub>/blobs/sha256-<64 lowercase hex>`
          of a subsystem with a blob field; another key (uppercase hex, without `sha256-`, a subsystem without a blob field) — an ordinary object,
          its owner writes it: 405 (reconciliation of python and go M10/6–11, T11)
```

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R014

old-sha256: 73b06aa8901bda7a5028140c3e1c19e7a5210b8ff0c36bc39ffc704326b44b4a

<!-- req: P/05-R014 -->

| What | Limit | Where | Words / code |
|---|---|---|---|
| an object at the resource door (reading, body copy, mirror piece) | `Content-Length.maximum` of the [HTTP form](05-resource.api.openapi.yaml) blob-copy operation | the resource door (N2) | `413` |
| lines in the answer of `/events` | `limit.default` and `limit.maximum` of `GET /events` in the [HTTP form](05-resource.api.openapi.yaml) | the index (N1.3) | truncation, `truncated` |
| retention term | a finite number > 0 | the resource (N1.3 `retention`) | «not known», remove nothing |
| the object store | `max_bytes` (0 — no ceiling); the store says it itself | `put` | `TooLarge` «over this store's limit» |

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R020

old-sha256: fa696515c81d35b9843bc72369ef2d5d44caba0ab145864ebe8f448f2c7c7528

<!-- req: P/05-R020 -->

```yaml
index:
  one_per_resource: over its own tree and the .mirror/<server>/ copies; the state is always live; there is no rebuild
  cache:    bounded (INDEX_CACHE_BYTES), dropped without loss of correctness; a file is reread by size/mtime/inode from the place
  query:    the query rules that the merge needs (parameters, defaults, by) — the event log merge contract «The resource query and answer»
            (moved there, EM-READ-33-01); the grammar of the parameters and the refusals — below this block
  row:      {id, subsystem, unit, of, epoch, t, kind, server, bucket, class, epoch_is, fenced, …fields}
            # server — the owner of the bucket; a line with its own field server (a line about a server: drain.*,
            # server.decommission_*, workers.no_server) keeps it — in such a row server is the server the line is about, the index
            # does not overwrite it, as class (G06-AUDIT-SERVER-01, the Specification's decision of 2026-11-05)
            # epoch_is and fenced are set by the merger — the console or the worker by the event log merge contract; at the resource the lines
            # are without them (the decision of the Architect, review of stage A; ADR-0091 addendum (27) item 7)
  epoch_is: current | fenced | earlier-run | unknown   # by current_epochs from <sub>/epoch/* and the policy of the manifest; unknown — only
            # at the worker for an epoch that it did not declare in worker.reads; the needed epoch is not read — a line without epoch_is,
            # incomplete[<sub>/epoch] (the event log merge contract «Epochs»; ADR-0091 addendum (24) item 4, addendum (27) item 2)
  cut, answer: the cut, the mirror copies, truncated, partial — the event log merge contract «The resource query and answer»; the answer
            of the merger (the console, the worker: + complete, incomplete) — in the same place, «The answer» (moved, EM-READ-33-01)
retention:
  <sub>/retention:        {days}      # the default — the event log contract «Retention of a tree»; the form of the row — P/02.4 N1.9
  <sub>/alarms_retention: {days}      # the default — the event log contract «Retention of a tree»; the form of the row — P/02.4 N1.9
  writer:   of both rows — admin by the operator command w2cctl retention (P/02.4 N1.9); the resource and the console only read them
            (P/02.5 N1.4; the store pilot, the decision of the Architect of 2026-10-18)
  rule:     per subsystem, not per unit (ADR-0076); days — a finite number > 0, anything else — «not known», remove nothing;
            the console marks live no less than the longest tree; the holds (holds) keep buckets (the holds contract);
            mirror copies — an hour longer; what is removed — the journal events.removed
```

**Retention deadline** (ADR-0127, review of P/05 C4). Use the bucket's own persisted logical `written` from the event-journal contract “Bucket write time”. First resolve term reads and holds conservatively; a hold or unknown dependency keeps the bucket. For a closed, unheld bucket with readable `written`, delete exactly when `now >= written + seconds`: normal `<sub>` uses `seconds = retention.days * 86400`; `<sub>.alarms` uses `alarms_retention.days * 86400`; `audit`/`audit.alarms` use their journal term; `console`/`console.alarms` use their term with the longest-tree floor. A mirror copy uses the corresponding tree's term plus `MIRROR_RETENTION_EXTRA`, measured from its own copy `written`. Equality deletes; a time below the deadline keeps it. Neither window start/end nor filesystem `mtime` substitutes for `written`. Restore preserves the copy's `written`; it does not restart the retention clock. All usual conservative holds and read outcomes precede this predicate.

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R022

old-sha256: 3838630b0a9b0950c39c69e85431e2f2fde2e02b603cbdc6fe2d749218d05908

<!-- req: P/05-R022 -->

A query uses finite `from`/`to`, `from ≤ to`; `limit` is an integer within the HTTP form bounds (reconciliation of python and go M10/6–11, E12–E15):
- `from`, `to` — an ASCII decimal number: an optional `-`, digits (`_` is allowed between digits), an optional dot with
  digits on at least one side, an optional exponent `e`/`E` with a sign; `1_0`, `.5`, `5.`, `1e3` are numbers,
  `1e-400` is 0; `+1`, a space (`%201`, `1%20`), non-ASCII digits (`١`), `0x10`, an overflow — 400;
- `limit` — only ASCII digits (leading zeros are allowed: `01`), otherwise 400; `since` of the hint — by N1.6;
- `unit` — UnitRef `<sub>/<id>`: a bare id, empty, `testsub/`, `/c1` — 400;
- `late` — an integer ≥ 0 in decimal notation, only together with `by=occurred`: anything else — 400 (C05-QUERY-LATE-01);
- an empty or repeated parameter — 400 (N2); an unknown non-empty parameter is not read (for `/events/wait` — 400, N1.6).

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R025

old-sha256: 3e864cb7f1e3872cebb3ba711c537a5f04fd1bb06710327867000aebe846e5f6

<!-- req: P/05-R025 -->

```yaml
resource:                                    # one process per server; without a controller
  heartbeat: the object platform/resources/<server>/heartbeat every HEARTBEAT_EVERY
    {server, ts, url, schema, build, usage, usage_at, space: {total, free, used, full}, volumes, units: {sub: [id]},
     workers, running, short, waits, mirrors: {server: n}, pass_started, pass_stalled, restore, mirror, door,
     retention_garbled?: [<sub>…], retention_withheld?: {<sub>: days_garbled | unknown | holds_unread}, …}
    # retention_garbled, retention_withheld — the reasons of the retention pass (N3 retain, N4; no reason — no fields; C05-RETENTION-PULSE-33)
    # settings_unread?: [mirror | space] — the setting rows of the pass that did not read: the step mirror (and the body copies of N1.1) or
    # relieve is not executed in this pass; in ascending order of bytes; none — no field (V7 item 3, the decision of the Architect of 2026-10-28, P1; lines 20, 21 of the list)
    # door: {addr, mode: loopback | mtls, cert_until} — in every heartbeat, written by the resource (ADR-0075 addendum (3)): addr —
    # RESOURCE_HOST:RESOURCE_PORT; mode — loopback without RESOURCE_TLS (loopback only), mtls with RESOURCE_TLS=1; cert_until —
    # the wall seconds of the end of the term of the server certificate of its own kit, with mtls; with mtls the server presents the leaf, then its authority
    # (the role certificate contract server; the client — own_client, the object client contract tls; norm review of ADR-0075, Claude fd85ea8cc, S-2); read by w2cctl tls status (P/02.4 N1.9; review of stage B 3–5, № 28)
    # waits, restore, mirror, units — in every heartbeat (reconciliation of python and go M10/6–11, E39): units — {<sub>: [<id>…]} of the units that
    # the heartbeats of the workers of this box from running name in status, ids in ascending order of bytes; none — {}; a worker heartbeat
    # is unreadable (the family heartbeats P/03.4: the whole object, for the resource also an element status[] not in form) — its units do not
    # enter units: the unreadable does not widen (C05-UNITS-PULSE-GARBLED-01, the decision of the Architect of 2026-10-30, norm questions of the Gemini audit, P/05 item 3)
  workers:   [<sub>/<slot name>…] — all the slots that the resource knows about on its box; running: [<sub>/<slot name>…] — with a
             live process (it holds the presence lock, the content in form with a non-empty worker); unknown: [<sub>/<slot name>…] —
             the presence did not read and the slot is known from current readable content (otherwise the whole-role unknown snapshot below): the lock file does not read (review of stage B 3–5, № 23) or flock/stat of the lock gave an error,
             except «busy» and ENOENT of stat (the presence lock contract; (the decision of the Architect of 2026-10-20, review of stage B 6–7));
             instances: {<sub>/<slot name>: <instance>}; the key is with the subsystem: a slot name is unique only within its own
             subsystem (P/03.2 `<sub>/slots/<name>`), two subsystems with one `slot.prefix` have the same names; pass_stalled: <seconds>, only while the pass hangs (PULSE_LIMIT)
             # one heartbeat form: the console gives it as ResourceRow P/06.5 (a derived output), the controller
             # derives the presence from it (below, P/04 «fate»)
  usage:     an integer — the bytes of the bucket files of the trees of this server and of the copies in .mirror/; usage_at — the wall seconds
             of the measurement; space — the volume of the event tree: total, free, used — bytes (statfs), full — the share used/total from 0 to 1
             (not a flag); volumes — the same per volume (log of cammeta-go, lesson 9 № 1)
  door_row:  platform/doors/<host> {url, since, at, room.<sub>…, live.<sub>…}; at — every ALIVE_EVERY (the observation contract «Resource state»; layout audit, the decision of the Architect of 2026-10-25, A-10)
  room:      the elements room.<sub> and live.<sub> — by the presence lock contract «Count room» (presence-lock.md; moved
             there, review of stage A 3–5, № 9; live.<sub> — ADR-0084 addendum (3) R14′, № 3, 19)
            do not write the door while platform/decommission/<my server> stands (the observation contract «Server decommissioned» narrower; the console deleted it)
  lost_after: LOST_AFTER                      # the observation contract «Freshness» (layout audit, the decision of the Architect of 2026-10-25, A-01); by a change on the clock of the reader
  pass:      the first — at start, right after readiness (the door row is written); then every PASS_EVERY from the end of the pass
             (C05-PASS-FIRST-AT-START-01): retain → usage → relieve → mirror; each step in its own attempt; pass_stalled on a hang
  space:     platform/space {enabled, high, low}   # shares; the typed form and defaults — P/02.4 N1.9, data/space.schema.json; enabled until switched off:
             # no row — enabled with high/low defaults of that space form; enabled: false — the resource removes its own row free-* (reconciliation of python and go M10/6–11, E45)
             # the row does not read — the step relieve is not executed: the high/low defaults of the space form are not substituted, its own row free-* is
             # neither written nor removed, the reason is in the heartbeat settings_unread: space (V7 item 3, the decision of the Architect of 2026-10-28, on the proposal; line 21 of the list)
             # the form of the row — P/02.4 N1.9 (written by admin, w2cctl space)
  free_ask:  <sub>/requests/free-<server>-<volume> {free, volume, server, at}   # its own form (ADR-0059): written and rewritten with cas only
             by the resource, not create-once, without unit/digest/family schema; for manifests with requests.free, while the volume > high;
             for requests.free volume — a non-empty name of ASCII A-Z/a-z/0-9/_, 1–64 bytes, without a hyphen (a box has one volume —
             the file system of the event tree, the name events); server — a non-empty key segment of P/01.1, hyphens are allowed.
             The split at the last hyphen is unambiguous. Another volume is out of profile: diagnose the configuration, do not create/change the request of this volume;
             free = used − total·low − Σ freeing from the heartbeats (only the freeing not yet reflected in used); with free ≤ 0 (and under the mark low) the row is removed (ADR-0059); nobody executes or marks it;
             the addressee — all the workers of the subsystem <sub> on the server <server>; <volume> — the volume of the resource, not a place of the subsystem;
             Σ freeing — the sum of freeing.<volume> (P/03.4 N1.1) over the live heartbeats of the workers <sub> on this server, no field — 0
             (vectors 05-resource/vectors/relieve; the VMS request freeing, the decision of the Architect of 2026-10-23);
             between low and high, while need > 0, its own row stands as it is — it is neither removed nor rewritten (reconciliation of python and go M10/6–11, E44)
  mirror:    platform/mirror {enabled, copies}; no row or no field enabled — enabled: false, buckets
             are not copied until enabled: true (guess of stage C R05-G05, the decision of the Architect of 2026-10-23); the row does not read —
             the step mirror is not executed, the reason is in the heartbeat settings_unread: mirror, `copies 1, enabled false` are not substituted
             (V7 item 3, the decision of the Architect of 2026-10-28, P1; line 20 of the list); bodies — N1.1 mirror;
             the neighbours — the next copies live servers by name; liveness — by the door row platform/doors/<host>, as in the merge
             contract «Live resources» (the version changed within the last LOST_AFTER on the clock of this resource, the first look — as fresh), the heartbeat
             of the neighbour does not judge here (the decision of the Architect of 2026-10-31); only closed buckets;
             the copy in .mirror/<server>/…; a copy is never a source while the owner answers; PEER_FAILS, a bucket within the resource door byte limit (OpenAPI Content-Length.maximum)
             as a whole, a copy adds MIRROR_RETENTION_EXTRA to its term; a closed bucket larger than that door limit (the mirror reception limit) is not
             copied: there is no assembly from pieces and no partial copy, it enters mirror.skipped of the heartbeat on every pass,
             the other buckets are copied (log of cammeta-go, lesson 8 № 7)
             # the form of the row platform/mirror — P/02.4 N1.9 (written by admin, w2cctl mirror)
  presence:  runs | gone | unlisted | unknown   # about the worker process of its own box — a conclusion from the heartbeat fields above:
             # the key <sub>/<name> of the worker slot of the subsystem <sub>: in running — runs; in unknown — unknown; in workers, but not in
             # running and not in unknown, — gone (the resource knew
             # the process, it is dead); not named in workers — unlisted (not registered at the resource); a heartbeat without these fields —
             # nothing about the worker (P/04 «fate»); an absent one of the three fields is an empty list, not unreadability: the order
             # unknown, running, workers, otherwise unlisted (C04-PRESENCE-PARTIAL-01).
             # The listing <events root>/.workers/<sub>/ is not obtained (an error, except ENOENT of a directory not yet created — that one
             # is empty): the heartbeat has none of the three fields — nothing about the workers (P/04 wait), the former names are not carried over, there is no partial
             # set; the rest of the heartbeat — as usual (C05-PRESENCE-SCAN-UNKNOWN-01). How the resource learns the presence — the presence lock contract
             # silent is a state of the resource itself (the observation contract), not a value of the presence
  presence_lock:  <events root>/.workers/<sub>/<instance>.lock — the presence lock contract (presence-lock.md;
             moved there, review of stage A 3–5, № 9); after flock the resource compares fstat(fd) and stat(path); if they do not
             match (ENOENT of stat too, review of stage B 3–5, № 19), it does not touch the file (ADR-0083 addendum (10)); the flock of the worker is blocking;
             the content — the family presence-lock (data/presence-lock.schema.json, presence-lock.outcomes.tsv; below):
             {instance, sub, worker, server, pid}, worker "" before the name is captured; a busy lock with empty or out-of-form
             content — a live process without a number (in room, not in workers, running, live); unknown — only an unreadable file
             (review of stage B 3–5, № 23; ADR-0083 addendum (11)) and an error of flock or stat, except «busy» and ENOENT (the decision of the Architect of 2026-10-20, review of stage B 6–7)
  requires:  placement.requires: resource — the worker is outside the pool while the resource of its server is silent (P/04)
```

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R026

old-sha256: 9a7e23c4f6d8c9244deeac06388e759a685b4a78a5277662677c81a6b7a6fd0b

<!-- req: P/05-R026 -->

**Writer and reader heartbeat forms** (ADR-0127, review of P/05 C3). The current writer and reader MUST include `door`, `waits`, `restore`, `mirror` and `units`. At initialization before any operations: `units = {}`, `restore = {}` if there are no necessary neighbours, `waits = {waiting:0, held:0, full:0, replaced:0, max:LONG_POLL_WAITERS}`, and the mirror counters `skipped`, `failed`, `peer_errors`, `lines_garbled` are zero. Existing necessary neighbours still have their actual restore entries, including incomplete ones; neutral values do not erase an error or a pending attempt. `door` always has its actual `addr` and `mode`; `mtls` additionally requires the actual server-certificate `cert_until`. The ordinary root schema requires those current fields and the mtls condition in both modes. A violation has the existing unreadable-heartbeat outcome; a reader does not synthesize successful operation or TLS state from an absent field.

**Unnamed presence uncertainty** (ADR-0127, review of P/05 C2). A current lock error without a readable slot name makes the whole role snapshot unknown, even after a successful listing and at cold start. Apply the presence-lock contract's “An unknown role snapshot”: omit `workers`, `running`, `unknown` and snapshot-derived `instances`, set the affected `room.<sub>` to `"unknown"`, omit its `live.<sub>`, keep independently complete room/live of other roles. Do not infer a slot from the filename, prior memory, or another lock; do not interpret the omission as `unlisted` or `gone`.

The content of the presence lock is the family `presence-lock` of the lesson: [schema](../data/presence-lock.schema.json),
[outcomes](../data/presence-lock.outcomes.tsv) (layers — [LAYERS](../../common/LAYERS.md)): an instance is `{key, file}`, the text of the file with `x-encoding: json` at the root
(LAYERS § 6), the column `schema` of the catalogue row names the family, the section is «Data families» below; the meaning is [the presence
lock contract](../../common/contracts/presence-lock.md) (review of stage B 3–5, № 23; ADR-0083 addendum (11); review of stage B 6–7, № 44).

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R030

old-sha256: c9d6c593398d0aa2edfb0bc16b308f4d206c6cb777457352d3023b98defcb37f

<!-- req: P/05-R030 -->

```yaml
restore:    at start the resource pulls its closed buckets from the neighbours whose heartbeats mirrors name it: GET /mirrored/<me>,
            each bucket by its sum, tmp + rename; PEER_FAILS consecutive failures — the neighbour is skipped until the end of this restore attempt; RESTORE_RETRY,
            doubling up to RESTORE_RETRY_MAX; done when the full lists are received and the copies are checked from all known necessary neighbours;
            the necessary neighbours — those whose readable heartbeats mirrors name this server; the local events are lost, and the heartbeats
            of the neighbours do not read or there is no heartbeat of a neighbour — all known server doors are necessary (platform/doors, door_row above),
            except its own: each is to answer with a full listing GET /mirrored/<me> (a full empty listing and 404 — there are no
            copies, so that neighbour is complete); 404 of GET of an already listed bucket is a missing copy, not an empty listing: the attempt stays incomplete. A restored bucket keeps the listed copy's written as its own retention stamp, not the receive time or filesystem mtime; an unknown or unreadable door leaves the restore incomplete (log of cammeta-go, lesson 11 № 4);
            a skipped/unreadable neighbour leaves the restore incomplete; 500 of a listing and a broken answer by N2, N4 do not count as an empty full list. If there were never any neighbours, there is no remote restore;
            restored of the heartbeat — only the buckets actually pulled from this neighbour; a bucket already lying on the volume does not count
            (the decision of the Architect of 2026-10-31);
            then — the reindexing of the subsystem; a copy is never a source while the owner answers (mirror above)
```


The local consecutive PEER_FAILS sequence resets after a successful peer operation and at the start of the next restore attempt or mirror pass. A skipped necessary peer leaves the current restore incomplete; the next attempt considers it again. A mirror peer is considered again next pass. These are separate procedure-local sequences; cumulative diagnostic counters are not reset by either boundary.

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R031

old-sha256: b932b493cb1c6da8ff389b58243209e37f06fbde727900f0a5e60e684b0ac032

<!-- req: P/05-R031 -->

`GET /events/wait` of the resource is a hint by ADR-0038, not a delivery of events. The profile of the lesson:
`want` — a non-empty comma-separated list `<sub>/<kind>[/<unit>]`; each part of ASCII letters,
digits, `_`, `-`, `.`, 1…64 characters, not starting with a dot. `client`, if given, — 1…128
printable ASCII characters without a space. `since` — a decimal uint64 without a sign/leading zeros,
0 by default. `timeout` — finite seconds with the bounds and default of `GET /events/wait` in the [HTTP form](05-resource.api.openapi.yaml).
Empty/repeated parameters, unknown parameters (`&foo=1`), other forms and values out of range — 400; `since` and
`timeout` — only ASCII digits (and a dot for `timeout`), non-ASCII digits — 400 (reconciliation of python and go M10/6–11, E14, E16). `since=0` —
the client has no position: the answer at once is `{changed: true, seq, touched}` if under want there are lines in the buckets of the resource of any
age; seq is an opaque monotonic number of the resource process, the client only compares it and passes it back
(reconciliation of python and go M10/6–11, E46). The hint is given by the subsystem trees of the catalogue (`<sub>`, `<sub>.alarms`); the trees `console` and `audit`
give no hint (both implementations do so, there was no norm).
This bounded profile does not require accepting any internal unit names: the periodic
pass of the client stays mandatory and works without the hint.

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R032

old-sha256: 4c1a0bde58bcf06bfda716723a107d2227cce4bc09795854f110c2622d78d395

<!-- req: P/05-R032 -->

The answer is one of the closed forms WaitAnswer: `{changed:true, seq, touched:[…]}`,
`{changed:false, seq}`, `{changed:false, seq, full:true}` or
`{changed:false, seq, replaced:true}`. In touched — the sorted unique
`<sub>/<kind>/<unit>` that match want; the events themselves are not there. seq belongs to one process
of the resource; after a restart/an unknown sequence the client makes an ordinary pass.
With full/replaced the client does not advance its cursor by seq, but returns to the ordinary pass.
By default up to LONG_POLL_WAITERS_DEFAULT waits (the deployment parameter LONG_POLL_WAITERS); a new wait when
full is answered 200/full. First replace the former wait of the same verified CN and named client: it receives 200/replaced and releases its place; only then check capacity for the new wait. Thus at a full effective LONG_POLL_WAITERS a replacement is admitted and the same number remain; a different CN cannot free that place (ADR-0127, review of P/05 M2).
A wait does not take the /events computation lane of P/06.4 N3 merge (N3 «query»); it holds its connection of the door until the answer
(changed, term, full, replaced) or until the noticed departure of the client (within WAIT_DISCONNECT_WITHIN) — the «common lane» of N2 is the connection limit
of the resource door («Implementation decides» item 10; C05-WAIT-COMMON-LANE-01).
In TLS the identity is the CN of the certificate plus client; another CN does not displace a wait (ADR-0075).
Without client the deployment uses a separate wait per client address; a repeat with a busy
address — full. The current buckets are observed every WAIT_OBSERVE_MS / 1000 seconds while there are waiting ones; a missed
hint or a write to an old bucket is made up for by the ordinary pass, not by a promise of delivery.

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R035

old-sha256: be3146883d16a72c12f700b5f0cc1f3ad6dcd75e1c93f3d2e6d30a810c15d7ff

<!-- req: P/05-R035 -->

The full contract: [OpenAPI](05-resource.api.openapi.yaml).
GET of an object is limited to the resource door byte limit (OpenAPI Content-Length.maximum) by the bytes actually read: exactly the limit is allowed,
+1 byte — 413 ResourceError before the success headers; until the size is confirmed the body is
buffered within bounds or checked against an immutable object with a reliable size.
The ceiling of the store itself can be higher and does not cancel this limit of the door. It distinguishes
the resource and the console, JSON answers, a byte stream and the absence of a body. The schemas set the required
fields and the allowed extensions; the checks of existence, rights, UTF-8 size and state
are performed separately. An outer array does not replace JSON Lines.

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R036

old-sha256: ab73122aa8b600087a507a7a87a084a8e5029ea201122334060211443c0a2c3b

<!-- req: P/05-R036 -->

| Input | Success | Application refusals |
|---|---|---|
| resource GET /v1/objects | 200 ObjectListing | 400 ResourceError; 403 ResourceError or ResourceDenied; 503 ResourceError |
| resource GET /v1/objects/{key} | 200 bytes; X-Written, X-Server, X-Missing when needed | 400/403/404/413/503 ResourceError |
| resource PUT /v1/objects/{non-blob} | none | 405 ResourceError; key/scope — 400 |
| resource GET /buckets/{sub}/{unit} | 200 JSON Lines of BucketInfo | 404/500 without a body |
| resource GET /events | 200 ResourceEvents; at the resource `HEAD` — 405 | resource 400 ResourceError (the parsing below); resource 503 ResourceError |
| resource GET /events/wait | 200 WaitAnswer, including full/replaced | 400 ResourceError; the common lane is busy — 503 ResourceError |
| resource GET /events/{path} | 200 whole bytes + X-Sum; 206 one range + Content-Range | 404/500 without a body; 416 text/plain + Content-Range |
| resource PUT /mirror/{server}/{path} | 204 without a body; the header `X-Sum` — SHA-256 of the body (64 lowercase hex), required | no `X-Sum` or it is not in form — 400, the body is not accepted; the SHA-256 of the body does not match — 422; 408/413/500 — without a body |
| resource GET /mirrored/{server} | 200 MirroredListing | 404/500 without a body |
| resource GET /mirrored/{server}/{path} | 200 bytes + X-Sum | 404/500 without a body |
| resource `PUT /v1/objects/<sub>/blobs/<digest>` | 204 without a body. Required are a length ≤the resource door byte limit (OpenAPI Content-Length.maximum), `X-Written` — a non-negative time of the source copy (absent or not a number — 400), a sha256 name with 64 lowercase hex; bytes of another digest — 422; a key not of the blob form or a subsystem without a blob field — 405, as for any object (N1.1 «Bodies at the resource» `mirror`; reconciliation of python and go M10/6–11, T10, T11). On reading the actual limit/sum are checked | 400/404/405/408/409/411/413/422/503 — `ResourceError`, 403 — it or `ResourceDenied`. The common refusals of the console do not apply here (moved from M10/10 N2) |

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R045

old-sha256: 5def1317bfe875dbe2a35dd9f86d988bdc816d00951a05b1ca308a15180efee6

<!-- req: P/05-R045 -->

**Profile limits.** A bucket file is read whole or by one Range; multiple Ranges and
conditional HTTP requests are not part of the lesson. The size of the answer is fixed before reading; the answer
does not promise a snapshot of the whole tree. After the output has started, a break of the stream does not turn into a second
HTTP status: the caller does not accept incomplete bytes as a whole copy. The mirror reception is limited by
the resource door byte limit (OpenAPI Content-Length.maximum) and by the read term declared by the deployment; exceeding the size — 413, the term — 408.
`PUT /v1/objects/<sub>/blobs/<digest>` is the body copy of a neighbour (the table above; N1.1 «Bodies at the resource»); `PUT /<rows>/<id>/<blob_field>`
belongs wholly to [P/06.1](../../06-console/spec/06.1-console.norms.md) N2 (the bytes door of the console); other
objects the resource door does not write — a refusal of the write of a non-blob, there is no partial copy of the blobs contract.

---

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R050

old-sha256: ad728e0a166583956a1df892ecb85ca111337d26c2a1a3528c771ab0f24b3093

<!-- req: P/05-R050 -->

```
1. check the parameters (N1.3)                                         → 400 (ResourceError at the resource, ConsoleRefusal at the console)
2. candidates: a window ≤ QUERY_NAMED_BUCKET_LIMIT buckets — names by time; wider — a listing of the directory; if a bound cannot be represented by a calendar name — a listing, without an overflow; the threshold only selects candidate search, never a query horizon or a result cap; both trees of the subsystem (and .alarms);
   the copies .mirror/*: the same bucket is a duplicate, it answers under the name of the owner
3. read the files from the place of the last read (a cache by size/mtime/inode); a torn line — skip it (partial);
   an unreadable line or a file not in its place — skip it and count it in lines_garbled (N1.3), the answer is not 503
4. filter: kind, subsystem, unit — the logical reference <tree>/<unit>, for a line of the tree .alarms — without the suffix (and the lines with of = unit; a parameter with the suffix .alarms — the form UnitRef allows it — is not normalized and matches no line: 200 without matches, C05-QUERY-UNIT-ALARMS-01), class, the window from ≤ t < to (or likewise by occurred: buckets up to to + late, the event log merge contract `by`)
5. epoch_is and fenced the resource does not set: they are set by the merger (the event log merge contract); the resource needs no rights to <sub>/epoch/*
6. remove the id duplicates, order and take the first limit by cut (the event log merge contract); truncated = the number of candidates after deduplication minus the number given
→ the lines of N1.3; more simultaneously computed requests than the P/06.4 N3 merge lane bound → 503 busy, Retry-After: 1 (counted are the requests /events that are being computed now;
  a held wait /events/wait does not take this lane — C05-WAIT-COMMON-LANE-01)
```

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R052

old-sha256: a20fc790eb9667b8b9a3adacdadd3c05e759a36a2d9788b379db396afd07377c

<!-- req: P/05-R052 -->

The first pass is right after readiness (the door row is written), not after PASS_EVERY: the reconciliation after a restart and the edges of
`free_ask` do not wait for PASS_EVERY; the next one is PASS_EVERY after the end of the previous one (C05-PASS-FIRST-AT-START-01, the decision of
the Specification on the recommendation of the Architect, 2026-10-30).

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R053

old-sha256: 9c71a7dcbd31f3aad91d1a7a060134a4a1aa6cf1a2841b39d4653fd45cdea08d

<!-- req: P/05-R053 -->

```
retain:  for each tree: days = <sub>/retention | the default (tree.alarms — alarms_retention | the default; audit, console —
         the default; the defaults — the event log contract «Retention of a tree», layout audit A-23, the decision of the Architect of 2026-10-25);
         days is not a number or ≤ 0 or the row did not answer → not known: remove nothing, name it in the heartbeat — a wrong days:
         <sub> in retention_garbled and retention_withheld[<sub>] = days_garbled; the row did not answer — retention_withheld[<sub>] =
         unknown; the holds are not read (the holds contract) — retention_withheld[<sub>] = holds_unread (C05-RETENTION-PULSE-33);
         each tree is kept by its own term (<sub> — retention, <sub>.alarms — alarms_retention); retention_withheld[<sub>]
         — one reason in the order: unknown → days_garbled → holds_unread; retention_garbled — a <sub> for which any term
         (retention or alarms_retention) is wrong, regardless of retention_withheld (R05-RETENTION-MIXED-51-01, the decision of the Architect of 2026-10-25);
         apply the inclusive deadline now >= written + seconds of N1.3 retention, only to closed buckets (the console marks — not earlier than the longest; holds keep — also the buckets
         of the units of other subsystems whose about names the held one, and the buckets of unknown units; what a row holds, the window,
         an incomplete declaration and unreadable rows — the holds contract common/contracts/holds.md, P/06.4 N1.5;
         the mirror copies — the tree term plus MIRROR_RETENTION_EXTRA); the journal events.removed; index.forget
usage:   measure the volumes (a probe ≤ VOLUME_PROBE_WITHIN); the heartbeat space/volumes
relieve: platform/space.enabled ∧ used/total > high → for manifests with requests.free: need = used − total·low − Σ freeing
         (Σ — over the live heartbeats of the workers of this subsystem on this server, freeing.<volume> of this volume; N1.4 free_ask);
         platform/space does not read — the step is not executed (N1.4 space); a heartbeat of a worker of this subsystem on this server does not
         read — the need of this subsystem is not computed, the step neither writes nor removes its row free-*, the reason goes to the journal (P1;
         the class of lines 21, 24 of the list V7 item 3)
         need > 0 → write free-<server>-<volume> {free: need, volume, server, at}: cas "" or cas by the version of a row of ITS OWN form
         (without unit AND with the exact server/volume of the current volume); before the write check the grammar of N1.4 `free_ask`;
         under this key a row with unit, another's server/volume or a spoiled form → do not touch it, the journal free_ask.key_taken, skip;
         need ≤ 0 (all that is needed is already being freed, ADR-0059) or below low → delete the row of its own form if there is one: delete with cas of the version
         on which the absence of unit AND the exact match of server/volume were checked (P/01.1); conflict — under the key there is already another row (an ordinary request or a new own one) → do not touch it,
         the journal free_ask.key_taken
mirror:  platform/mirror does not read → the step is not executed, settings_unread: mirror (N1.4 mirror); platform/mirror.enabled → the neighbours = the next copies live ones by name (liveness — the door row, N1.4 mirror); the closed buckets that the neighbour does not have
         (the sum) → PUT /mirror/<me>/<path> with X-Sum = SHA-256 of the bucket; PEER_FAILS consecutive failures → the neighbour is skipped until the end of this mirror pass
each step is its own attempt; a step longer than PULSE_LIMIT → pass_stalled in the heartbeat
```

### `Platform/09-agent/spec/09.1-agent.norms.md` P/09.1-R003

old-sha256: ec72f14906248f45882d0677f9aae0a61a6e44f150b1b2dd2e79763e83cf6905

<!-- req: P/09.1-R003 -->
### N1.1 The agent, the member key, `join` (M11/3 N1.1)

```yaml
agent:          the process of the role domainagent (P/01.2 N1.1) on every server of the member cluster, the holder included; one is active —
                the turn domain/agent-turn (N1.13; DOM-AGENT-TURN-01, -02, the owner's consent of 2026-10-26); the active one carries the member reports to the holder and the answer
                of the holder home; it holds no domain keys (P/08.2 N1.3)
domain/member-key: {seed_secret, pub}        # at the member; the secret is a ring envelope (sealing contract); readers — domainagent and domain (P/02.5 N1.3)
  seed_secret:  hex of 32 random bytes — the seed of the Ed25519 member key (RFC 8032)
  pub:          hex of the public key; the member key is one: the agent signs with it (N1.3) and the holder seals to it (P/08.3 N1.5);
                a point of the Ed25519 curve not of small order ([8]A ≠ the neutral element, RFC 8032 §5.1.3): another key gives no signature —
                agent-sig bad_signature, knock 401, reception 409 (added by the reconciliation of M11, M1);
                pub is the public key of the seed seed_secret (RFC 8032 §5.1.5); not it — the row has two keys: the row is unreadable by the
                outcome of the family (the agent — key_read: do not sign, sign_failures; the process domain — do not sign the ask) (C09-MEMBER-KEY-PAIR-01)
  readers:      domainagent — all signatures of the member; domain — only the signature of the ask GET /api/backup at a move (P/08.8
                N1.8 step 5, the ask signature contract ask-sig); the process domain makes no agent reports and no other member signatures; writer — the agent
  born:         by the agent at the first start, create-once; at start the agent writes to the journal the line
                «member key <fingerprint>» (the fingerprint — the domain key set contract «The key fingerprint», not serial; review
                of stage B 8–10, № 4)
join:           an operator command on the member: the domain name and the public key of the root (the domain installation P/02.4 N3 prints them together with
                the root fingerprint, the operator compares the fingerprint by eye) → domain/root {pub, domain} create-once (P/08.2 N1.1)
  same:         the same {pub, domain} is already pinned — success, nothing changes
  another:      another one is pinned — a refusal, nothing changes; changing the domain at a member is not this chapter (a debt in «work log»)
  class:        an optional input camera | server (none — server) → the row domain/join; a change — leaving and a new admission (P/08.3 N1.1a)
  batch:        an optional input: the batch name and the private key of the batch, shown by the door POST /domain/batches (P/08.3 N1.1b) → domain/join {class: camera, batch}, the seed is a ring envelope; the class of a batch is always camera
domain/join:    {class, batch?: {name, seed_secret}}    # at the member; writer — the command join, create-once next to domain/root; reader — the agent; no row — class server, no batch
  knock:        the publication carries class and, with a batch, batch {name, sig} (the report reception contract «The batch knock») until its own row
                domain/member-list/<part> confirms the admission of the current key: the row reads and its own entry is how: admitted with key equal to the pub
                of the confirmed pair domain/member-key and domain/member that signs this publication; then the fields do not go. Its own name with another key
                (the former key after the authorized replacement below) confirms nothing: the fields go. The guards come first and keep their outcomes:
                an unconfirmed, mixed or unreadable pair — no signature, no publication (key_read, N1.12); an unreadable domain/join — the fields do not go
                (its outcome below); an unreadable own row domain/member-list/<part> — its outcomes (no members_rev), it confirms no key; its own entry
                how: holder — the fields do not go, the holder's own procedure (P/08.3 N3 «the holder in the list»), not a confirmation of a new key
domain/member-list/<part>: {doc, fetched_at}        # at the member: the row domain/member-rows/<part> that passed take (N1.4 member_list_take): its own part and the requested ones; fetched_at — wall-clock seconds of receipt; writer — the agent
domain/member:  {cluster, pub}               # the name of its own member and hex of its public key, not secret: by pub the console
                                             # of the cluster checks X-Agent-Signature of its own agent (N1.3), the process domain —
                                             # by Entry.key (P/08.3 N1.1); the agent writes it create-once when the function keys
                                             # (the domain key set contract) has accepted the set (took or holding), if there is no row —
                                             # at the cluster of the holder too
```

**Authorized local member-key replacement (P09 review C4).** This is an explicit operator-authorized maintenance procedure after loss or theft, not an agent's automatic response to an unreadable key. The operator must be authorized to replace this member identity and arrange normal re-admission of the new public key at the holder. Keep the pinned root/domain and cluster name unchanged. Stop all normal local agent instances and other member-key signers, wait for their old work to finish, and keep their automatic start disabled across interruption until the pair is confirmed. The operator invokes one local maintenance execution of the existing `domainagent` role with normal process-start admission and the active `domain/agent-turn`; it performs no ordinary reports or member signatures during maintenance. Open the authorized ring-protected replacement material, derive the new pub from its Ed25519 seed and seal the seed with the member ring. This agent writes `domain/member-key {seed_secret, pub}` and `domain/member {cluster, pub}` together in one ordinary conditional store batch by the confirmed versions of both rows and the current `domain/agent-turn` guard (N1.13). The operator authorizes and controls the window; the existing agent role is the writer, not a new role. No new public command spelling or HTTP route is prescribed.

If the write is interrupted or its outcome is unknown, signing and ordinary restart remain disabled, including while the agent resolves the ordinary turn/write unknown-outcome barrier. Confirm both rows by reading them again: both contain the authorized new matching pub and the seed derives it — the replacement is complete; both are the former pair — retry the authorized conditional batch under a confirmed current turn; a mixed, absent unexpectedly, unreadable or mismatched pair — repair through that same authorized agent procedure before continuing, never generate another seed automatically. Do not repair an unreadable existing key by the create-once path or merely copy a foreign pub into the key row. After the pair is confirmed, the active agent may sign its re-admission knock with the new key; normal reports require the holder's normal admission. Until its own row `domain/member-list/<part>` confirms the new key, that knock carries the existing class and batch (N1.1 `knock`): the former entry with the old key confirms nothing. Its own console verifies the new key from the updated `domain/member.pub`. At agent startup and before the agent signs, a readable existing binding with another pub or an unconfirmed binding blocks signing and uses the existing key_read/sign_failures path until repaired. Confirmed absence during the unchanged initial create-once/admission path is distinct and keeps that path; the procedure does not require a domain set before the first knock. No secret material is logged.

`domain/member-rows/<part>` (`Entry`), the knock `knock` and the admission from the holder's side (the paragraph «Admission is
two-sided») — [P/08.3 N1.1](../../08-domain/spec/08.3-domain.norms.md); the pinning of the root and the function `keys` (`no_pin` without
`join`) — [P/08.2 N1.1](../../08-domain/spec/08.2-domain.norms.md) and the domain key set contract «The function `keys`».

### `Platform/09-agent/spec/09.1-agent.norms.md` P/09.1-R004

old-sha256: 1f9395dd45a8ab0c43e0dc0578e490274c277c27fa0564bb696ca3ebf657e1d3

<!-- req: P/09.1-R004 -->
### N1.2 The publication, contributions, report objects (M11/3 N1.2; M11/5 N1.2; M11/12 N1.4, N1.5)

```yaml
publication:    the body of POST /api/member/<member> (P/08.3 N2) — a JSON object, a closed set:
  sent_at:      a finite number — the wall-clock seconds of the agent at the moment of sending
  objects:      {<object key>: <JSON value of the object>} — what changed against base (whole at base = 0)
  base?:        an integer ≥ 0 — the rev of the generation at the holder against which the changes are; none or 0 — the body is whole
  deleted?:     [<object key>…] — the keys that are no longer there against base; only at base > 0
  key:          hex of the member key — the one in domain/member-key
  keys_rev?:    rev of the set domain/keys that the member holds (none — no set)
  stale?:       [<heartbeat key>…] — the heartbeats <sub>/heartbeats/<worker> of the copy that have not changed for longer than the threshold of the subsystem <sub>:
                heartbeat.stale_after of its manifest (P/02.1 N1.2; at rec 30 s), no key — LOST_AFTER (45 s), by the monotonic clock of the agent;
                the threshold of the subsystem applies to all readers of its stale: pulse.<sub>.stale of the view, the head of a book with stale (ADR-0113 addendum (36));
                a limit: a heartbeat under load longer than the threshold gives a false stale — the reserve writes twice, harmless;
                the agent sees a change of a heartbeat by its pass (up to 5 s), «longer than the threshold» adds a pass: at rec the death of a recorder is visible
                to the holder up to 48 s, the margin at a ring of 66 s — 16–18 s (ADR-0113 addendum (38) item 1);
                at a manifest with a book stale: true (P/02.1 N1.2b) stale also includes the key <sub>/heartbeats/<slot> of a slot whose contribution to this book
                (the row from <sub>/<row>/<slot>) exists while the heartbeat row of its worker does not: a server removed for good — the reaper or the removal took the heartbeat away,
                but the contribution lies, and without this the element would look alive (ADR-0113 addendum (37) item 2); the rule is common to all books with stale; ascending; none — empty. Out of the delta: it is not part of whole and does not create
                generations; the liveness of a worker is a fact of the cluster (P/04), the domain observes it (the Architect's decision on M11-03 № 5);
                by it the holder sets pulse.<sub>.stale of the view and the head of a book with stale (P/08.1 N1.4, P/08.5 N1.3 head; ADR-0113 addendum (33)): the clock of the agent, not of the holder
  pinned?:      the fingerprint of domain/root of the member — the domain key set contract «The key fingerprint» (none — not pinned)
  outcomes?:    {<id>: <outcome>} — the outcomes of the domain edits, N1.5 (a key ≠ the id inside the outcome — the outcome does not count, P/08.6
                N1.6 settle; the reconciliation of M11);   tls_ca?, tls_ca_certs? — the role certificate contract (reception — P/08.3 N1.6);
                sign_failures? — the form is in the report reception contract (ACC-G01), the meaning — N1.12;   members_rev? — the report reception contract «The list of members to the one lagging behind» ({term, rev} of the list that the member holds; out of the delta)
out_of_delta:   a field out of the delta — a closed list of the publication form: stale, tls_ca, tls_ca_certs, sign_failures, members_rev;
                a field that is not in the publication of P/09.1 N1.2 — the body is not of the form, 400 not_a_publication (the Architect's answer of 2026-10-25 (layout audit, question T5a)); a field out of the delta not of the form
                of its norm — the field is not taken, the holder's journal, the report is accepted, like tls_ca P/08.3 N1.6; stale — keys
                without repeats, a repeat — the field is not taken (the Architect's decision on the reconciliation of M11, A3–A6, A9)
member_objects:                               # what the agent carries and what the holder stores; the holder drops the rest silently
  <sub>/heartbeats/<worker>:  the heartbeat P/03.4 N1.1 of every manifest of the catalogue with domain.ref; the agent does not judge the form of a heartbeat:
                              a heartbeat that is JSON not of the form — it carries as is, the judgement is at the holder (P/08.1 N1.6 claim;
                              V7 item 3, the Architect's decision of 2026-10-28, on a proposal; row 25 of the list); a text that is not
                              JSON (not UTF-8, broken JSON) cannot be embedded — the agent keeps the former embedded value of this
                              object (the heartbeat time inside — freshness is judged by the holder), no former one — no object in the pass,
                              a log line; no new fields (C09-MEMBER-OBJECTS-NONJSON-01, like C09-RETAIN99); «former» is the value
                              of the object in the confirmed base (N1.2 change), not the memory of the agent of what it ever read:
                              a deletion confirmed by a trusted 200 — there is no former one (C09-PRIOR-VALUE-BASE-01)
  <sub>/snapshot/<shard>:      a snapshot shard P/04 N1.3a of every such manifest
  <sub>/snapshot-tables/<table>:  a table snapshot P/04 N1.3b of every key of domain.view_tables of a manifest of the catalogue, domain.ref is not needed
tables_budget:  the body or the whole hit BODY_LIMIT (answer 413 whole too large, N1.2 refused): the next publication carries instead of every
                table snapshot a stub {cluster, ts, refused: "whole_too_large", rows: []}, units and heartbeats go as they went: tables do not silence the member;
                once per TABLES_RETRY the agent tries again with real snapshots (ADR-0110, the sum of tables is not held by the ceiling P/04 N1.3b)
domain/servers:  {servers: {<server>: {labels}}, url?} — the servers of the cluster from the rows platform/servers/<host>, labels as in the row (P/06.6); url — PUBLIC_URL of the environment, the entry address for people; an object of the member,
                the agent carries it in the report; the view adds names from heartbeats and shards, so a server without a worker is visible to the domain (P/08.1 N1.4)
  other families:             the list and the forms — the report reception contract «The member's publication» member_objects (moved; ACC-G01);
                              what the agent takes into the report — the rows below (contributions, reports), N1.7, N1.9, N1.10 (the reconciliation of M11, X1)
ready:          the agent does not send a publication while it has not a single snapshot shard of every manifest of the catalogue with domain.ref:
                such a publication would say «no units» — a full answer that the domain would believe;
                this does not concern table snapshots: they can be absent (the ceiling P/04 N1.3b), the report is no worse for it
change:         an object has changed — its JCS differs from the confirmed base, without the field ts of a heartbeat (P/03.4 N1.1) and of a snapshot
                shard (P/04 N1.3a); only ts is not a change. The confirmed base is a copy of the state that the agent
                sent with the request accepted by the holder last (answer 200, the generation carry.rev); the agent keeps it.
                A request or an answer is lost — the base is the former one: the next pass sends a delta against the same base with a new sent_at
                (the Architect's decision on R41-04 of run 41)
fresh:          the agent remembers for every heartbeat when on its monotonic clock the whole object changed (with ts); a heartbeat that has not
                changed for longer than the threshold of its subsystem (N1.2 stale: heartbeat.stale_after of the manifest, no key — LOST_AFTER) — into stale
                (ADR-0113 addendum (36), addendum (47) item 4)
```

The contribution of a member to a book (M11/5 N1.2; the contribution rows, the writer and `claim` — [P/03.7 N1.2](../../03-worker/spec/03.7-worker.norms.md), the input form `entry` — [domain envelopes contract](../../common/contracts/domain-envelopes.md) «Contribution»,
the declaration of a book — [P/02.1 N1.2b](../../02-installer/spec/02.1-installer.norms.md), the assembly — [P/08.5 N1.3](../../08-domain/spec/08.5-domain.norms.md)):

```yaml
liveness:     a family: the row <sub>/<row>/<slot> goes into the report only while the slot <sub>/slots/<slot> is held — the holder
              is not empty, released = false (not true and not taking, the slot contract «States»), now ≤ until by the wall clock of the member; the agent reads the slot, the row, then the slot again —
              the slot changed between the reads → the row is not in this report; a single row — without the filter (it has no slot);
              the segment <slot> — by the grammar of the slot name P/03.2 N1.4, like the family key in common/data/README; a segment not by
              it — the key is not of the contribution family: the agent does not carry it, the key is not judged as <name> of reports or of another family; the outcome is the same
              as the liveness filter would give — a slot with such a name cannot be held (C09-BOOK-SEGMENT-01)
in_report:    the publication object (member_objects above) objects["<sub>/<row>[/<slot>]"] = {<item>: <input object>}
              — an object, not text (an element that is not the text of a JSON object the agent carries as a string as is: the assembly decides —
              bad_contribution, P/08.5 N1.3); a secret — the envelope x25519:v1 to book_seal of the set (the domain envelopes contract
              «Envelope x25519:v1») with AAD [member, row key, item] and the JSON Pointer of the secret in the input object; a ring value (begins
              with «enc:» — the sealing contract looks) the member opens before that, a plain value (not «enc:») is the
              value itself, it is sealed to book_seal as is (C09-CONTRIB-PLAIN-SECRET-01); it did not open — the agent carries
              the value as is (a ring envelope, not x25519:v1): the assembly decides —
              secret_unopened (P/08.5 N1.3)
seal_reuse:   the agent remembers the last envelope of every secret (row key, item, pointer), the value sealed by it and the kid
              of book_seal to which it is sealed; the same value to the same book_seal — the same envelope: an unchanged input does not
              give a new generation (change above); book_seal of the set changed — a new envelope, the contribution goes into the report
              (the Architect's decision on R41-08 of run 41)
no_seal:      there is no set with book_seal, and the input has a secret → this row does not go into the report (one journal line per change of
              the reason); the other rows and the report go
reports:      domain.reports: [<family>/…] — the objects <sub>/<family><name> of the member go into the report as is (member_objects above);
              the holder keeps them in the copy; the book does not read them
              of every manifest of the catalogue that declared domain.reports — domain.ref is not needed (it limits only
              heartbeats and snapshot shards); a key that is also named by the family of heartbeats or snapshot shards of a manifest with domain.ref
              (the element heartbeats/, snapshot/) belongs to it: the form and the judgement of that family, reports neither extends nor
              replaces them; without domain.ref the manifest has no such families — such objects go as reports (C09-REPORTS-SCOPE-01)
              <name> — one component by the grammar <name> (common/data/README «Placeholders»): domain.reports
              [extra/] names <sub>/extra/a, and <sub>/extra/a/b does not: the agent does not carry it, the holder drops it silently
              (the key is compared with the list exactly); the depth is set by the element of the declaration (extra/a/) (C09-REPORTS-NAME-01)
              reports is the last of the families of member_objects: a key that is also named by another family (book contributions,
              witnesses, domain/…) belongs to it: the form and the judgement of that family; a contribution row that has not passed liveness or no_seal
              does not free the key — the reports object does not go instead of it. The contributions domain.books.<book>.from and the witnesses
              domain.witness — also of every manifest that declared them, domain.ref is not needed (C09-REPORTS-SCOPE-02)
```

The field `members_rev` (M11/12 N1.4, the agent's side; the form and the holder's rule — [report reception contract](../../common/contracts/accept.md) «The list of members to the one lagging behind»
`publication.members_rev`, `carry.members`): the agent puts into the publication `{term, rev}` of the document `domain/member-list/<part>` that
it holds; no row — no field; out of the delta. An answer without `members` is «no change»: the agent does not touch the copy of the list (N1.4
`from_carry` does not delete anyway).

The body limit of the agent (M11/12 N1.5; the holder's ceilings `ENTRY_MAX`, `MEMBERS_MAX`, `whole` — [P/08.10 N1.5](../../08-domain/spec/08.10-domain.norms.md)):

```yaml
body:          the agent always sends a delta when base > 0; a whole larger than BODY_LIMIT the agent does not send — the reason in domain/agent
               (N1.12 too_large) and the journal no more often than once per SAY_EVERY; it sends again after a change; the answer of the holder 413
               whole too large to a whole under the limit of the agent — the same: the same whole is not repeated until the objects
               change against the one sent (added by the reconciliation of M11, N9)
SAY_EVERY:     forms/runtime-constants.tsv  # s — the journal of one reason of the agent
```

`BODY_LIMIT` is the body limit of the doors of the holder and the relay: [report reception contract](../../common/contracts/accept.md)
«Generation, mark, limits» (the value — P/08.3 N1.3). The fields `tls_ca`, `tls_ca_certs` the agent takes from the directory `W2C_TLS_DIR`
of its own cluster; the form, «no directory — no field» and the journal of the reason — [role certificate
contract](../../common/contracts/role-certificate.md) «The cluster kit, the domain roles, the center between clusters» (the holder's
side — P/08.3 N1.6). The publication, `out_of_delta`, `member_objects`, `ready` are repeated for the receiving side in the report reception
contract «The member's publication»; the owner of the text is this chapter (review of stage B 8–10, № 4).

### `Platform/09-agent/spec/09.1-agent.norms.md` P/09.1-R007

old-sha256: 547a5f0273a0b1b25aac01c4311d7e2a4c466f25d6076bb3202f3988f9c7fc61

<!-- req: P/09.1-R007 -->
### N1.4 The holder's answer and the write at home (M11/3 N1.6; M11/12 N1.2; M11/4 N1.2; M11/5 N1.4; M11/9 N1.3, N1.6)

The holder's answer `carry` and the envelope `m1` — [P/08.3 N1.5](../../08-domain/spec/08.3-domain.norms.md), [domain envelopes
contract](../../common/contracts/domain-envelopes.md) «Envelope `m1`», «Content of `sealed`» (the agent opens it).

```yaml
from_carry:     keys → domain/keys through the function keys under the condition SET_GUARD with the term record of this answer (the domain key set contract «The follow set»; a refusal — the row is the former one, the reason to the journal); a set by which its own record does not pass record — only in a batch with the record of this answer (ibid.);
                revoked → the union with its own row (the domain key set contract «Revocations» merge); a write of domain/keys by a set with thefts
                higher than that of the trusted set of the memory (below) — by this answer or by following (N3 step 4) — sets in the same batch
                domain/revoked: the set came with this answer — {jtis: ""} ∪ the revocations of this answer, by following — {jtis: ""}; otherwise
                the member would apply the post-theft revocations of the answer a period later (ADR-0110 addendum (24), replaces addendum (22); M1 of the review of norms (24)).
                thefts of the former one — from the trusted set of the memory, not from the row: an unreadable own domain/keys would otherwise clear the row
                without a theft, and a revocation lost by a move without stolen would revive at the member (addendum (25) item 1). No memory (start) and its own
                domain/keys is not readable — do not touch the revocations row until the answer of the holder, then merge it with the row of the answer (addendum (25)
                item 2, addendum (26)). Any merge of the revocations row larger than ceiling (413) — after start and without it — replace it with the row
                of the answer, journal domain.revoked.replaced: otherwise a full row of former revocations, merged before the first post-theft revocation,
                would give 413 forever (addendum (27) item 1); an overflow happens mostly after a cleanup by a theft, and then the row
                of the holder has lost nothing. A limit: at any 413 of a merge the replacement loses the own revocations of the member that the row
                of the holder does not have — after a move without stolen the row of the holder can be incomplete (the merge RV), — like domain.revoked.dropped
                of the move (P/08.8 N1.8 step 7; review of addenda (26), (27), a minor finding);
                its own row domain/keys is not readable — held = the trusted set in the memory of the agent (the last one that it
                trusted), not nil; took or holding — rewrite its own row by CAS of the read version, the journal without the
                value (P2); no memory (after start) — the set of the answer is judged keys(pinned, null, carry.keys) from the pinned root,
                took — write its own row by CAS of the read version, the journal (C09-KEYS-UNREADABLE-REWRITE-01; the outcome of the family keys); otherwise
                a member without following would stay without a set forever (ADR-0110 addendum (27) item 2, addendum (28)); revoked — by the start path above;
                the rollback limit: without memory the member may accept an older valid set — the worst case: a repeat of an old answer gives the set before the theft (the root signed it), and until the next answer or following the tokens of the thief pass at the member; the rollback does not go beyond the pinned root;
                the trusted set of the memory is the last one that the agent trusted: the outcome took or holding of an answer or its own
                row domain/keys read as readable; held of the function keys is it, and not a read row older than it
                and not its absence (the write at home failed): step 7 older holds the rollback, home catches up by home_write at the next
                trusted answer (C09-HELD-MEMORY-01);
                revoked → domain/revoked by the domain key set contract «Revocations» merge (the union by jti, only
                prune removes; review of stage A 8–10, № 3, № 13); its own row domain/revoked is not readable — the agent, the only
                writer at the member, rewrites it by CAS of the read version with the records of the answer, the reason to the journal without the value
                (V7 item 3, the Architect's decision of 2026-10-28, P2; row 44 of the list; the holder's answer does not cancel a revocation — Quint RV: only prune removes); members → member_list_take below; the set is accepted and there is no row →
                domain/member {cluster, pub} (review of stage A 8–10, № 4); the other fields of the answer (revoked, members, holder, sealed, the fields of the lessons) are applied
                only after the outcome took or holding of the function keys over keys of this answer; another outcome or no keys — the answer
                is not applied, the rows are the former ones, the journal (added by the reconciliation of M11, R2: the set is rejected — its answer is not trusted);
                the other fields — their norms; every write — only on a difference from what was read (home_write below; added by M11/12;
                freshness marks — as_of of the grants copy, domain/reached — no more often than FRESH_EVERY, as_of in the row — no more often than
                AS_OF_STORE_EVERY, fresh below), CAS by
                the read index, secret fields — ring envelopes (the sealing contract)
member_list_take: the check of the row before the write: take(keys of this answer, members, its own part, its own copy) — the term record contract «The members row»; take → domain/member-list/<part> {doc, fetched_at}; same → only fetched_at;
                a refusal or older → the copy is the former one, journal domain.member_row.refused {part, reason} without the value, the answer is applied further: a forged row does not deprive of the keys
book_want:      a book to: "*" (P/08.5 N1.4): the asks domain/book-want/<sub>/<book>/<part> are put and renewed by the reader, by them the agent holds the copies domain/<sub>/<book>/*/<part> and the head domain/<sub>/<book>/*; an ask older than BOOK_WANT_TTL — the agent removes it by the read version, a copy without an ask is removed; at the holder's cluster the asks are not executed; the publication carries book_parts as a window; carry.book_stale, a new ask or carry.book_rev of another head → GET /api/book/<member>/<sub>/<book>[/<part>] by the road of the report, up to BOOK_PARTS_PASS parts per pass; 404 with the word empty_part — the copy is removed, another refusal and 503 — the copy is held; there are no secrets
member_want:    the ask of a reader for a part — domain/member-want/<part> {at}; it is put by the client peer (the peer contract client): the console, the worker mixed, the agent; the agent keeps a fair queue in process memory across passes (N3 step 2b); initially and after restart, order the current asks by at then part name in UTF-8 bytes; take up to MEMBER_WANT_PASS asks from its head,
                GET /api/members/<member>/<part> by its own road, the answer — member_list_take, the row is written or same — the ask is removed; a refusal of the row and 503 — the ask lies and goes to the end of the queue: move it behind the other pending asks in that process queue without changing or writing its stored at; retain the order across passes so 8 persistent refusals cannot hold the whole window: a gathering «from nothing» goes on (P/08.8 N1.8a rows); 404 — the ask is removed: the part is empty, there is no copy; no domain — the copy lives on, this is a limit
holder_cluster: at the holder's cluster the agent does not write the rows that the process domain writes there (domain/keys, domain/revoked,
                domain/holder, its own domain/break-glass/<cluster>, the pointer domain/shared), while the record domain/holder of its own
                store passes record and names this cluster the holder; the condition of the agent — only by the record, domain/signer
                is not open to it; the switch point — the term record contract «The switch point `switch`» (the agent's side — N1.8)
sealed:         the envelope m1 did not open (P/08.3 N1.5, the domain envelopes contract «Envelope m1»: not_m1, not_an_envelope,
                does_not_open) — its fields are «not taken»: the member rows that they write are not touched; delete a row — only
                when the field is not in the opened envelope (the Architect's decision on finding 27 of run 41) and its name is not in held: a field
                from held means «not sent», the copy is not touched, as_of does not move, it ages by step 4 of the right contract (P/08.4 N1.3 carry)
rights:         the role domainagent (P/02.5 N1.4): writes domain/* without the holder's rows; reads its own by the declarations
```

**Opened `sealed` content.** After successful cryptographic opening, content outside the current closed composition (including an unknown field) has its fields not taken. Preserve the related copies, freshness marks and writes by the existing sealed-field rule above; do not skip unknown fields. This is rejection of the content form, not a new cryptographic opening result or rejection of the entire carry. Independent, otherwise authorized updates from the public carry fields remain permitted.

**Member-want queue lifetime (P09 review C5).** Keep retry ordering until the process ends, not only until the pass ends. Remove an entry when its request succeeds (`take` or `same`), is empty (404) or is withdrawn by its reader. Reconcile newly observed asks into the queue without resetting the order of pending retries. A completed request recreated later is a new entry; no stale cursor is reused. After restart only the persisted asks remain and their initial at/name order is rebuilt. This is bounded process memory, not a new durable row or a mutation of request `at`.

The write at home and freshness marks (M11/12 N1.2; `hot`, `durable` — [P/02.4 N1.11](../../02-installer/spec/02.4-installer.norms.md)):

```yaml
home_write: the agent writes at home a row from the holder's answer (from_carry above) only when its value differs from
           what was read; an answer without changes writes nothing (added by M11/12)
fresh:     freshness marks — as_of of the grants copy (member_copy below) and domain/reached (N1.7) — one rule: on a change
           of the content they are written at once, and with the same content they are refreshed no more often than once per FRESH_EVERY; at as_of of the grants copy
           the refresh is in the memory of the agent, to the medium (the row domain/grants) one refresh of as_of is written no more often than once per
           AS_OF_STORE_EVERY, a change of doc — at once: after a restart the copy looks older by at most an hour — stricter, not
           more dangerous; for any cluster (VMS request № 19, the Architect's decision of 2026-10-23). The value is the moment when
           the holder assembled the answer: the wall-clock seconds of receipt minus domain_age of the answer (chapter 9.2 N1.4; a direct answer — 0); it does not go
           back, so an answer from the memory of a relay does not refresh the mark (the Architect's decision on R41-12 of run 41)
FRESH_EVERY: forms/runtime-constants.tsv        # s — the refresh of a mark (at as_of of the grants copy — in memory)
AS_OF_STORE_EVERY: forms/runtime-constants.tsv  # s — one refresh of as_of of the grants copy on the medium: much rarer than FRESH_EVERY, which refreshes only memory
```

**Key changes at the member** (M11/2 N3, N4, the member side; the steps of the changes at the holder — [P/08.2 N3](../../08-domain/spec/08.2-domain.norms.md)
«planned token key change», «book acceptance key change», «change after theft»). The member takes the new set with the holder's answer
(`from_carry`). A member without a connection holds the former set — what follows from this is named by P/08.2 N3 «A member that
was offline»; its contributions sealed to the former `book_seal` are resealed to the new one by the next report after the
new set (N1.2 `seal_reuse`: `book_seal` of the set changed — a new envelope; an envelope to the former one is `missing` at the holder,
P/08.2 N4, P/08.5 N1.3).

The copies of the holder's rows at the member:

```yaml
domain/member-topology: {doc}                # at the member: item doc is JCS of the complete HTTP body {doc, via} of GET /api/topology/<member> as is; the agent takes the body when sha256 of the field topology of the answer
                                             # of the holder differs from that of the last taken body; no memory (start) — it takes the body; not taken — the copy is the former one
                                             # (P/08.3 N1.2 carry; ADR-0113 addendum (47) item 3)
                                             # (M11/4 N1.2; the topology — P/08.3 N1.2)
member_row:   domain/<sub>/<book> at the member — the elements as received, secrets — ring envelopes of the member (the sealing contract); writer —
              the agent (P/02.5 N1.4a domainagent); at the holder's cluster there is no copy: the holder does not send books to itself in sealed and reads its own
              book from the row domain/<sub>/<book>/<self> (ADR-0074, «assembled books at the holder»)   # M11/5 N1.4
member_anywhere: the agent, class server, at a new sha256 takes the body GET /api/anywhere/<member> and writes at its own cluster the exact key domain/anywhere {doc, as_of}; a camera does not write: the same rule fresh and as_of as member_copy; no field and no name in held — delete;
               before a new copy, check the complete received body against carry.anywhere.sha256 by P/08.4 N1.3 carry (G09-ANYWHERE-HASH-01). A mismatch does not write a new copy, confirm its taken-sha256 marker or apply the writes belonging to this copy; the former copy and marker stay unchanged. The owner raw-string body is hashed before any internal doc parsing; copy its doc and as_of strings exactly after successful verification. Do not change the sealed advertisement type or normalize the stored text.
               a name in held — the copy is not touched; at the holder's cluster it does not write (P/08.4 N1.3 anywhere)
member_roles:  the agent writes at its own cluster the exact key domain/roles {doc_sha256, groups, assigned, admin_at, supervision?, unreadable?, as_of} from the field roles of the opened
               sealed: as_of — as at the grants copy, the refresh — the same rule fresh, CAS by the read version, the guard domain/agent-turn; the order of the two
               writes (grants, roles) does not matter for safety: the reader checks the link by doc_sha256 (the gate and pass contract
               roles_in). The field roles is not in the opened envelope and not held — the row is deleted; held or the envelope did not open — it is not touched (sealed).
               supervision and unreadable — as in the holder's table (P/08.4 N1.3b; ADR-0119 addendum (4) item 1, addendum (6) item 2): by them the console judges supervision
               (the gate and pass contract «Supervision»); within the same ceiling of the row.
               A reader of the content of sealed skips the fields outside the list of the envelopes contract. Its own row is unreadable — it is rewritten by CAS of the
               read version, the journal without the value (ADR-0098 §4)
member_copy:   the agent writes at its own cluster the exact key domain/grants {doc, as_of} — doc as it came, as_of — the moment when
               the holder assembled the answer: the wall-clock seconds of receipt minus domain_age (chapter 9.2 N1.4; a direct answer — 0), it does not go back;
               doc changed — write at once; the same doc — refresh as_of in memory no more often than FRESH_EVERY, in the row — no more
               often than AS_OF_STORE_EVERY (fresh above); an answer
               from the memory of a relay does not move as_of; no field in the opened envelope and not held — delete the row (sealed
               above). Like domain/outcomes (N1.5): the copy of the member is an exact key, the rows of the holder are the family domain/grants/<cluster>;
               for the agent — !domain/grants/* without !domain/grants (P/02.5 N1.4)   # M11/9 N1.3
holder_copy:   at the cluster of the holder the copy domain/grants is written by its agent from the answer of its own holder, as at any member:
               one reading rule, there is no second writer (ADR-0032); until the first answer the agent has no row — no rights,
               the entrance is the break-glass one (P/08.4 N1.6; the door — the cluster console), as at a member until the first answer   # M11/9 N1.3
break_glass:   the field break_glass in sealed of the answer — at the member domain/break-glass/<member> (the secret is sealed by its ring); no field
               in the opened envelope and its name not in held — the agent deletes the row; the name in held (the holder's row is unreadable) or the envelope did not open — it does not touch it
               (sealed above; C08-GLASS-HELD-01). At the holder's cluster
               the row domain/break-glass/<holder> is its own (written by the process domain): the holder's agent does not write it and does not
               delete it, the answer to itself does not carry the field break_glass; its own row domain/break-glass/<member> is not readable — the agent,
               the only writer at the member, rewrites it by CAS of the read version with the value of the field break_glass,
               the reason to the journal without the value (V7 item 3, the decision of the Architect of 2026-10-28, P2; row 31 of the list)   # M11/9 N1.6 carry, the side of the agent (the text — P/08.4 N1.6 carry)
```

**Complete topology copy (G09-TOPOLOGY-COPY-SHAPE-01).** Item `doc` contains JCS of the entire HTTP body `{doc, via}`; the inner document stays nested. The checked `sha256` is SHA-256 of JCS of that complete body, as in P/08.3 N1.2 carry. Neither merging the inner `doc` fields with `via` nor taking only the inner `doc` replaces the body. Without a confirmed body with a matching hash, retain the former copy under the ordinary `home_write` rules; the holder reader and writer rules are not replaced.

The successful HTTP body forms consumed here are the owner references in [Forwarded owner forms](../forms/README.md#forwarded-owner-forms). This reference does not replace the copy, hash, signature or local KV decoding rules above.


The holder's side of these fields: `topology` — P/08.3 N1.2, N1.5; `sealed.books` and the mask — [P/08.5 N1.4](../../08-domain/spec/08.5-domain.norms.md);
`sealed.grants`, `GRANT_LIFETIME`, the revocation window at a member without a connection — [P/08.4 N1.3](../../08-domain/spec/08.4-domain.norms.md);
`sealed.break_glass`, `GLASS_MIN` — P/08.4 N1.6. The write of a book at the member — N3 «the write at the member».

### `Platform/09-agent/spec/09.1-agent.norms.md` P/09.1-R008

old-sha256: 8232a41d78be308173e3e3de72decb2b3d18926cbde24a581234f4ad8bb60b8d

<!-- req: P/09.1-R008 -->
### N1.5 Placement copies, applying edits and outcomes (M11/6 N1.2, N1.5)

```yaml
member:     domain/placed/<sub>/<ref> — the elements of the record as at the holder (P/08.6 N1.1); domain/placed {rev}
            the agent: carry.placement.rev > domain/placed.rev → write the changed copies (CAS by the read version),
            delete the copies that are not in records, then domain/placed {rev}; not greater — nothing (there is no rollback)
            the holder does not write copies: its readers take the record (P/08.6 N1.1 readers)
readers:    the executor at the member — by worker.reads `domain/placed/<sub>/` (P/02.5 N1.4a); it finds its record by (ref, cluster = me
            or me in copies)
```

**Exact placed.at copy (G09-PLACEMENT-AT-COPY-01).** Only for `at` of these copies, the copier transfers the holder JSON-number lexeme byte for byte from `carry.placement.records` into item `at`: without normalization, rounding or truncation, including `1e-8`, exponent notation and more than three fractional digits. Values `1.234` and `1.2340` are not rewritten into each other. A nonnumeric `at` refuses the affected copy before writing it; that revision cannot be confirmed by the `domain/placed` marker. This does not add atomicity across all copies. This narrow exception concerns the copied number, not other time writers: their three-digit bound is unchanged. The copy reader accepts the entire numeric lexeme; other field outcomes and the ordinary CAS/transfer ordering are unchanged. Checking the form does not replace checking the copier actual bytes.


The holder's answer `carry.placement` (the filter `records`, the mutex, raising the counter at start) — [P/08.6 N1.2](../../08-domain/spec/08.6-domain.norms.md);
the stored edit `edit` and `pending` of the answer — P/08.6 N1.4.

```yaml
apply:      the copy of grants, roles and anywhere of this answer is written before the edits (N1.4): a new person needs a fresh row. For every edit of the answer in order: an outcome with kept_at = at is already written — do not repeat; otherwise the secrets — P/08.6 N1.3a open, a bundle —
            P/08.6 N1.3b apply; a request to the door of units, of tables or of a batch of its own console: method, path, the body — JCS body, Idempotency-Key — key,
            X-Agent-Signature (the agent signature contract, window 60 s), X-Agent-For at by, If-Match: <base> at base (P/06.1 N3 «edit», «delete»)
outcome:    {id, status, result, error?, at, what, kept_at, made?, by?}
  made:     the id of the created unit, if the edit created it: from the answer of the door, for a bundle — the number new_id or the id of create; otherwise there is no field
  by:       by of the edit as is: a non-viewer of the domain sees its own outcomes (P/10 N1.2a)
  status:   the code of the answer of the console; the door is not called (the secret did not open, N1.5 apply) — 0
  result:   performed (2xx) | conflict (412: the unit at the member was changed after the reception — the edit is not applied, the unit is not
            overwritten) | refused (another 4xx, including 409, except «in flight» below)
  error:    detail of the answer (no detail — its error) at status ≥ 400, without the values of secrets
  at:       the wall-clock seconds of the agent;  kept_at — at of the edit
  kept_at:  the writer form P/01.1 «Time in a row» (a JSON number, a fraction of at most three digits): at of the edit, rounded to
            thousandths from the decimal notation, half away from zero (like until of chapter 8.4); at of at most three digits — as is.
            The equality «kept_at = at» (apply here, settle of the holder P/08.6) — after the same rounding of both sides, by
            the binary64 value of the rounded notations: a notation as a string or as a number and the length of the fraction do not differ
            (C09-KEPT-AT-PRECISION-01; C08-KEPT-AT-BOUND-01)
retry:      the console did not answer, status ≥ 500, 1xx or 3xx, 409 «in flight» (P/06.1), 403 with detail stale (the copy of the rights is stale, the refusal is temporary), 412 row moved of a bundle → no outcome, a repeat by the next
            pass (1xx, 3xx — added by the reconciliation of M11, A10)
same_path:  an edit with a common row (keys, P/08.6 N1.4) with a waiting one without an outcome (a repeat by retry) is not sent until that one has an outcome: otherwise
            its If-Match would meet a value not yet applied and give a false 412 (added by the reconciliation of M11, A9)
OUTCOME_HOLD: forms/runtime-constants.tsv  # s — the outcome is held after the holder stopped naming the edit: a copy older than the closure returns it, and the agent recognises the edit by the outcome (C08-OUTCOME-HOLD-01); the moment — the memory of the agent, a restart starts the period anew: stricter
OUTCOMES_KEEP: forms/runtime-constants.tsv  # outcomes in the row: above it or at the ceiling of the row the oldest by at are removed; the publication has only the outcomes of edits still named by the holder; a limit: a copy older than a week or an outcome beyond 500 — the edit is applied again
domain/outcomes:  the row of the member (the agent): the element <id> — the JSON text of the outcome; the outcome is removed OUTCOME_HOLD after the holder stopped
                  naming the edit in the answer
                  — in a trusted answer with the field pending (pending: [] — names none); an answer without the field pending
                  (the row of the holder was not read, P/08.6 N1.4 carry) — «no change»: the outcomes are not removed. At
                  holder_self the same: the row domain/pending/<me> is read (it is absent or has no edits — none is named) —
                  the outcomes of the unnamed ones are removed; the row is not readable — they are not removed; an unreadable element of an edit is named
                  (the id exists) — its outcome is not removed (C09-PENDING-ABSENT-01)
publication.outcomes:  the publication field N1.2 — {<id>: <outcome>}: the elements of the row domain/outcomes of the member, each
                  parsed into the JSON object of the outcome (not as text); there is no empty outcomes: no outcomes — no field (added by the data family schemas pilot, R1)
folders:     carry.folders (P/08.5 N1.8): at full the agent brings the copy platform/folders/<id>, platform/memberof/… to the answer as a whole; without full — a delta from its rev: it changes the named folders, null — removes, does not touch the others; all by the read versions: top down, removal in reverse; a link from platform/memberof-gone
             does not come back; then it writes rev into the object domain/folders-state; no field — it removes nothing; scope — chains at DOMAIN_FOLDERS=chains of the environment, otherwise all;
             gone — the rows platform/memberof-gone and the rows of the memberof copy whose unit was removed past the door: a confirmed read gives a tombstone or absence, the check no more often than once per GONE_CHECK_EVERY; the read is not confirmed or the snapshot is incomplete — not gone;
             the row platform/memberof-gone is removed when the link came in carry.gone_seen; own — the live folders of the cluster and their membership, while there is no copy (rev null);
             at the holder's cluster the same: the copy is separate from the domain rows
holder_self: the holder is a member: its edits are stored in domain/pending/<holder>; its agent reads them from its own store
             (without an answer) and applies them the same way; the outcomes — in its report; the row is not readable — the edits of this pass are not
             applied, an unreadable element of an edit is not applied, the others are, the reason to the journal once per pass, without the
             value, like the process domain at issuance (P/08.6 N1.4 carry; V7 item 3, the Architect's decision of 2026-10-28, on a proposal; row 41 of the list)
```

The outcomes at the holder (`settle`, the view `pending`, `outcomes`) — [P/08.6 N1.6](../../08-domain/spec/08.6-domain.norms.md).

### `Platform/09-agent/spec/09.1-agent.norms.md` P/09.1-R013

old-sha256: fdbf289e8ecfa984aa7362a19decd3375665d12fe20cdc27cc00d4fa9e22d69b

<!-- req: P/09.1-R013 -->
### N1.10 The shared document at the member and the alarm page (M11/11 N1.4, N1.7)

The document, the pointer, the signature by the issuer and the holder's side of the delivery (`carry.shared`, `holder_self`) —
[P/08.9 N1.2, N1.4](../../08-domain/spec/08.9-domain.norms.md).

```yaml
member:          the agent in order (N3 «take the document»); then the object domain/shared = the text, then the row
                 domain/shared {doc: JCS {term, rev, sha256}}; a refusal — the row domain/shared-refused {doc: JCS {term, rev,
                 reason, at}}; the former document stays; a taken document removes the row domain/shared-refused with a pair not
                 newer than its own (added by the reconciliation of M11, A4)
                 the removal did not pass (CAS failed, the store did not answer) — it is completed by every next pass independently of step 1
                 «take the document»: its own readable domain/shared with a pair not older than the pair of domain/shared-refused — the refusal is removed
                 by CAS of the read version; an unreadable domain/shared-refused — as on the take path, by the outcomes of its family
                 («differs», it is removed by CAS, P2); an unreadable own domain/shared — it is not removed (P1); the row domain/shared and
                 the object are not rolled back (C09-SHARED-REFUSED-CLEANUP-01; refined by C09-SHARED-REFUSED-CLEANUP-02)
in_report:       the rows domain/shared and domain/shared-refused are report objects (N1.2 member_objects, added by M11/11)
                 in one form: the value of the object is the parsed doc of the row, {term, rev, sha256} and {term, rev, reason, at},
                 term and rev are JSON integers (like domain/backup-taken, N1.9; the Architect's decision on the reconciliation of M11, A3);
                 at the holder's cluster the row domain/shared is the holder's pointer, and the agent carries its doc whole:
                 {term, rev, sha256, object} (added by the data family schemas pilot, D1)
```

```yaml
page:          the report object domain/alarms (N1.2 member_objects, added by M11/11):
               {from, to, events, truncated}
  events:      the rows of the index P/05 N1.3 of the class alarm of all manifests of the catalogue and of the role journals audit.alarms/<role>: GET /events?class=alarm&from=<from>&to=<to>
               &limit=ALARM_PAGE&keep=newest at its own console (P/06.4 N1.3 merge) — {id, subsystem, unit, of, t, kind, …};
               to — now, computed once per page; from = to − ALARM_WINDOW of the same page, not from to of the last one
               (after a downtime the window is not wider than ALARM_WINDOW; C09-ALARM-WINDOW-01)
  event:       a row of the page — the form of a row of the index P/05 N1.3: id — a non-empty string (required), class = alarm, kind —
               a non-empty string, unit — a string, t — a number; a row not of this form (including without id) — the page is not of the
               form: at the holder the member is unreadable (lesson P/10 N3 alarms step 1; the Architect's decision
               on the reconciliation of M11, H14, A15)
  from, to:    the window of the page by the wall clock of the member; to — the moment of assembly, from = to − ALARM_WINDOW
  truncated:   truncated of the answer of the index > 0
ALARM_WINDOW:  forms/runtime-constants.tsv  # s
ALARM_PAGE:    forms/runtime-constants.tsv  # events in one regular page
urgent:        once a second the agent reads only the front — GET /events?class=alarm&limit=1&keep=newest of its own console; t
               of the row > to of the last page — assemble the page and send the report now, outside the regular pass, but not
               more often than URGENT_GAP after the last urgent one; the cost — one read of an index row per second per member, no more
               (P/08.10 N1.9: hundreds of members)
rebuild:       the page is assembled at the start of the agent and when the front is newer than to; otherwise the report carries the former page — a quiet
               member does not create generations (N1.4 home_write)
fail:          the assembly did not pass (GET /events of the window — not 200, no answer, the body not of the answer form of P/06.4 N1.3) — not an absence
               of alarms (P1): the object domain/alarms is not written, an empty page is not assembled from a refusal, the reason to the journal without
               values; the report carries the former readable page as is; there is no readable one (no object or it is unreadable) —
               the report goes without domain/alarms: in a delta the object is neither in objects nor in deleted — at the holder the former value;
               a whole (base 0) is not held back (domain/alarms is not in the list of N3 «the agent pass» step 3) and goes without the object —
               at the holder «no page» (P/10 N3 alarms); a console refusal does not hold the report. The assembly remains due: to
               is the former one, the next pass or the urgent check assembles again. An urgent report — only with a new page;
               the read of the front did not pass — neither an assembly nor an urgent report, the regular one — at its time (C09-ALARM-REBUILD-FAIL-01)
URGENT_GAP:    forms/runtime-constants.tsv  # s
identity:      the agent goes to /events of its own console with the agent signature (N1.3; P/06.3 N1.3 identity step 2, added by M11/11)
```

Witnesses `domain.witness` ([P/02.1 N1.2b](../../02-installer/spec/02.1-installer.norms.md)): the agent carries every object
of the family `<sub>/<report>/<name>` of every manifest that declared `domain.witness` (`domain.ref` is not needed; C09-REPORTS-SCOPE-01),
as a report object (N1.2 `member_objects`), the object `<sub>/<report>` without a name is not a witness
(P/10 N1.8 `witness`, added by the reconciliation of M11, A2). The alarm list at the holder, the member states, the silence line and the function
`alarms` — lesson P/10 ([N1.8, N3 `alarms`](../../10-domain-console/spec/10-domain-console.norms.md); P/10-06).

### `Platform/09-agent/spec/09.1-agent.norms.md` P/09.1-R020

old-sha256: 6c687b6e5af795db73ee480710a8978530dc8a8ea3ab76084533aaf1913e08b4

<!-- req: P/09.1-R020 -->
### additions to the agent pass (M11/12 N3 «additions to the passes of lesson 3», the agent's lines)

```
agent, step 1:  the member key does not read → the requests of the pass are not signed: the count sign_failures, domain/agent (N1.12)
agent, step 3:  a whole larger than BODY_LIMIT → do not send, domain/agent too_large; base > 0 — always a delta
agent, step 4:  the publication carries members_rev (N1.2; the form — the report reception contract «The list of members to the one lagging behind») and sign_failures (N1.12); class and batch — N1.1 domain/join, `knock`; row — N1.2a send_row; gathered — a field of its own part row, if it is there (the report reception contract)
agent, step 5:  503 standby → the next pass, last_rev does not change; 413 whole too large → domain/agent too_large,
                last_rev = 0 (the next change — as a whole)
agent, N1.4:    a home row is written only when it differs (N1.4 home_write)
```

### `Platform/09-agent/spec/09.1-agent.norms.md` P/09.1-R027

old-sha256: b2827f47be720551fd08e42546d67d2c4221f16dea260f2dacb1acbbd5f663a9

<!-- req: P/09.1-R027 -->
## N5 Acceptance

The directory [`../acceptance/1/`](../acceptance/1/README.md): 22 scenarios / 252 steps — the domain stand, the vocabulary of directives and
doors — the [common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors), the section [«Domain stand»](../../common/acceptance/README.md#domain-stand). The scenarios are moved from the acceptances of M11/05, M11/06, M11/10, M11/11,
M11/12 (stage B); the numbers and the steps are the former ones, except two: number 04 of M11/05 is taken by a scenario of M11/06, number 06 of M11/11 —
by a scenario of M11/12; they got the next numbers after the largest number of the sources of the chapter (M11/10 sc. 12), in the order of
the lesson of M11, then of the scenario: M11/05 sc. 04 → 13, M11/11 sc. 06 → 14 (the Architect's decision on the move plans 8–10, item 14;
the rows of `corrections-1.tsv` (historical correction record)); 16–19 — the coverage audit of P/09 (audit-kimi aee4369fb); 20–25 — its second pass (Gemini,
cc36de538).

| № | Scenario | Norms |
|---|---|---|
| 01 | `quiet-member`: a quiet member — `reported.rev` stands, `received_at` gets fresher, the indexes `domain/member-list/<part>` and `domain/keys` at the member do not grow, there is no `domain/agent` | N1.4 `home_write`, `fresh`; [report reception contract](../../common/contracts/accept.md) «accept» step 6 |
| 03 | `unreadable-member-key`: the member key `m1` is spoiled — `domain/agent` with the count, the member `silent`; repaired — `ok` again; spoiled on the fly without stopping the agent — the same count and `silent`; repaired, the agent restarted — there is no row of the former run (reconciliation of M11, N1, N2) | N1.12 |
| 04 | `conflict`: the edit is stored, the member changes the unit itself — after the return the outcome 412 `conflict`, the member's value is kept | N1.5 |
| 05 | `unsigned-document`: a document of an unknown issuer, put past the edit — the member does not take it, `domain/shared-refused` `unknown_issuer`; the holder's console — values without the domain (mutation check of 2026-10-18; C09-SHARED-ACCEPT-01) | [P/08.9 N1.2](../../08-domain/spec/08.9-domain.norms.md) `signature`; N3 «take the document» |
| 06 | `fresh-and-unchanged`: a home row without changes is not rewritten (`domain/member-topology`), `as_of` of the copy of grants at most once per `FRESH_EVERY`, in the row — the former one even after 65 s: to the medium at most once per `AS_OF_STORE_EVERY` (steps 9–10, VMS request № 19; mutation check of 2026-10-18) | N1.4 |
| 07 | `outcome-refused`: an edit that the member refused with 409 (`exists`) — the outcome `refused`, 0 waiting (mutation check of 2026-10-18) | N1.5 |
| 08 | `unit-door-window`: the window of the unit door is 60 s — an agent with the clock +90 applies the edit, the member's console 401, the outcome `refused` 401, the unit is untouched (mutation check, the class of deadlines) | N1.5; [agent signature contract](../../common/contracts/agent-signature.md) `UNIT_WINDOW` |
| 11 | `revoked-not-revived`: a revocation after the last backup copy does not revive after a move — 401 (the Quint model of M11, RV) | N1.4 `from_carry` (merge `revoked`); [P/08.8](../../08-domain/spec/08.8-domain.norms.md) N1.5, N1.8 |
| 13 | `slot-liveness`: the worker is killed — its row does not go into the report by the deadline of the slot, there are no writes, the contributor is not in `missing` | N1.2 `liveness` |
| 14 | `pointer-checksum`: a pointer with a foreign sum — for the holder the object is unreadable: the holder's console 503, the document is not sent to the member (the outcomes of `shared-docs`; C09-SHARED-ACCEPT-01); the agent's refusal «does not match the pointer» — by reading: the holder does not send such a document | N3 «take the document» step 3; [P/08.9 N1.4](../../08-domain/spec/08.9-domain.norms.md) carry |
| 15 | `one-agent`: two agents — the turn `domain/agent-turn` is with one of them, it sends the reports; the local token door of the standby one carries the ask to the holder; SIGTERM — the giving up, the standby one takes it; SIGKILL — the change by `TURN_TERM` | N1.13, N3 «the agent turn» (DOM-AGENT-TURN-01, -02, the owner's consent of 2026-10-26) |
| 16 | `holder-self-edit`: an edit of a unit of the holder's cluster (`?cluster=hold`) is stored at the holder, the holder's agent applies it itself — the value at the unit `hold`, 0 waiting, the outcome `performed` 200 | N1.5 `holder_self`, `apply`, `outcome`; [P/08.6 N1.4](../../08-domain/spec/08.6-domain.norms.md) `base`, N1.6 |
| 17 | `token-wait`: the process `domain` is frozen (`@freeze`) — the local token door answers 503 `unavailable` no later than `TOKEN_WAIT`; after unfreezing — 200 | N1.6; [local token door contract](../../common/contracts/local-token-door.md) `no_queue`, `TOKEN_WAIT` |
| 18 | `break-glass-copy`: the copy of the emergency row at the member from the field `break_glass`; the holder's row is unreadable — its name is in `held`, the copy is kept; confirmed absence (no field in the opened envelope and the name not in `held`) — the copy is deleted; its own row of the holder's cluster is not touched by the agent | N1.4 `break_glass`, `sealed`, `holder_cluster`; the outcomes of the family [`domain/break-glass/<cluster>`](../../08-domain/spec/08.4-domain.norms.md) |
| 19 | `backup-refused`: the keeper's own copy of term 99 — a sent document of term 1 is refused «older than the copy kept here» with the pair of the pointer; the object `domain/backup` and the row `domain/backup-taken` are the former ones | N1.9 `member`; N3 «check the backup copy» step 3; [P/08.8 N1.5](../../08-domain/spec/08.8-domain.norms.md) `carry` |
| 20 | `join-same-and-another`: a repeated `join` of the same `{pub, domain}` — success, the row `domain/root` and the index are the former ones; another domain is pinned — a refusal, the row and the index are the former ones | N1.1 `join` `same`, `another` |
| 21 | `member-key-pair`: `pub` of the row `domain/member-key` is not from `seed_secret` (the key of another member) — the row is unreadable: the agent does not sign, `sign_failures_domain`, the local token door at once 503 `unavailable`, the member `silent`, the row is not born anew | N1.1 `pub`, `born` (C09-MEMBER-KEY-PAIR-01); N1.12 `count`, `key_unreadable` (C09-SIGN-FAILURES-COUNT-01); the outcomes of the family `domain/member-key` |
| 22 | `shared-refused-cleanup`: a taken document removes `domain/shared-refused` with a pair not newer than its own; a refusal with a pair not newer than its own `domain/shared` and an unreadable refusal are removed by the next pass without a new document; its own `domain/shared` does not roll back | N1.10 `member` (C09-SHARED-REFUSED-CLEANUP-01, -02); the outcomes of the family `domain/shared-refused` |
| 23 | `unreadable-copies-heal`: unreadable copies `domain/member-list/<part>`, `domain/member-topology`, `domain/grants`, `domain/placed` — the agent overwrites them with the value of the holder's answer | N1.4 `home_write`, `member_copy`; N1.5 `member`; the outcomes of the families (G-51, G-53, G-54, G-58) |
| 24 | `unreadable-outcomes`: an unreadable `domain/outcomes` — the edit of the answer is not executed, the row is not overwritten; the operator removed the row — the outcome `performed` | N1.5 `apply`; the outcomes of the family `domain/outcomes` (G-56) |
| 25 | `unreadable-agent-turn`: an unreadable `domain/agent-turn` — the agent is standby: there are no reports (`silent`), there is no CAS over the row, the local token door works; the row is corrected (`holder: ""`, `delete` under `domain/` is forbidden, to `admin` too) — the turn is taken, the member `ok` | N1.13 `standby`; N3 «the agent turn» step 1; the outcomes of the family `domain/agent-turn` (G-44); DOM-AGENT-TURN-02 |
| 27 | `roles-copy` (ADR-0098 §4; there is no dry run): the table of roles in the copy `domain/roles` only with the roles of this member, without the disabled ones; a disabled one with a direct row: `doc_sha256` is the fingerprint of `doc` after the filter, the right through the role acts (`/session`); an unreadable row of grants at the holder — `held`, the member's copy is intact | N1.4 `member_roles`; P/08.4 N1.3b |

**Vectors.** The agent signature (P/09.1-22) — the package [`common/vectors/agent-sig`](../../common/vectors/agent-sig/README.md)
(the owner of the contract is this chapter; the former sc. 10 of M11/03 is a duplicate, removed by the move of lesson 8); the function `peer` (P/09.1-27) —
[`common/vectors/peer`](../../common/vectors/peer/README.md) (the former sc. 06 of M11/08); the function `follow` (P/09.1-11) —
[`09-agent/vectors/follow`](../vectors/follow/README.md) (21 rows: 12 — the former sc. 06 of M11/10, 9 — the input forms and the exit
codes `exit`, the coverage audit of P/09, second pass).

The form of the command `follow` and its exit codes are from M11/10 N5 verbatim, the addresses are new (analysis of review of stage B 8–10, № 5; Claude
P-1); the steps of the function — N3 «follow», `record` — [the term record contract](../../common/contracts/record.md):

```yaml
follow:    input {keys, held: {doc} | null, answers: {<cluster>: {doc} | null}};
           output {result: follow, term, holder, url} | {result: stay, reason: holding | larger | none | two_holders,
           term?} and refused: {<cluster>: <record word>}; term of stay is the term of its own record if it passed record, otherwise
           there is no field — for any reason, and for two_holders as well: the disputed term does not stand in for term
exit:      0 — computed; 2 — the input is not by the form; the exit codes follow the principle of the common acceptance README «Domain stand» («Exit codes of vector commands»: 2 — the form of a trusted input, 0 with a word — a document of another cluster; the Architect's decision on the reconciliation of M11, H14):
           keys of follow is a trusted document of the set of P/08.2 N1.2 of the closed form (the domain key set contract «Set
           domain/keys»): a field is missing (revoked_issuing, sig, domain), issuing is not a list, keys null — 2; the signature of the set
           is checked at the write (the domain key set contract «The function keys»), the function does not check it — a spoiled sig
           is not a refusal;
           follow without held or answers, answers not an object, an extra field — 2; held is not {doc} (a string, an array) — its own record did not
           pass record: 0, stay without term or follow; answers.<to> neither {doc} nor null — 0, refused.<to>: not_a_record;
           answers: {}, held: {} — 0; a key of answers that is not a cluster name is counted as an answer
```

**Neighbours at the stand.** The agent's side is observed by the scenarios of other chapters (the outcome of a scenario belongs to the chapter of its outcome, ADR-0083 addendum
(13)): the acceptance [of chapter 8.3](../../08-domain/acceptance/3/README.md) — sc. 01, 02 (`join`, P/09.1-21; the member key, P/09.1-01;
the write at home, P/09.1-04), sc. 03 (the publication, P/09.1-02), sc. 15 step 13 (the copy of the topology, P/09.1-23), sc. 17 (`members_rev`,
P/09.1-32); [of chapter 8.4](../../08-domain/acceptance/4/README.md) — sc. 01, 02 (the copy of grants, P/09.1-28); [of chapter
8.5](../../08-domain/acceptance/5/README.md) — sc. 01 (the write of a book at the member, P/09.1-25; the same envelope — steps 11–15,
P/09.1-06); [of chapter 8.6](../../08-domain/acceptance/6/README.md) — sc. 01 steps 10–16, 19 (the copies, P/09.1-07), sc. 03 steps
11–17 (the application, P/09.1-08); [of chapter 8.7](../../08-domain/acceptance/7/README.md) — sc. 01 and sc. 02 steps 6–8, 12
(the local door, P/09.1-10); [of chapter 8.8](../../08-domain/acceptance/8/README.md) — sc. 02, 04, 09 (following and the switch
point, P/09.1-11, -31); [of chapter 8.9](../../08-domain/acceptance/9/README.md) — sc. 01 (delivery, P/09.1-12); [of chapter
8.10](../../08-domain/acceptance/10/README.md) — sc. 04 (`standby`, P/09.1-19); [of chapter 9.2](../acceptance/2/README.md) — sc.
02, 03 (`domain/reached`, a member behind a relay, P/09.1-05, -24), sc. 06 (the local token door through a relay,
P/09.1-10).

**By reading** are checked P/09.1-03, -13, -14, -17, -20, -22 (the bytes — the package `agent-sig`), -26, -33 — the causes are
at the checklist items (the former causes of the checklists of M11: the stand without TLS, the stand does not raise alarms, the stand does not lose the
holder's memory, and others). The reader's side of the manifest row (P/02.3 N3 «Process start», «Manifest change»; the agent is a consumer) —
by reading: there was no step in the acceptance of M11, the scenario — by a separate edit of the acceptance (the move plan of lesson 9, V11; analysis of review of
stage B 8–10, № 17).

### `Platform/09-agent/spec/09.2-agent.norms.md` P/09.2-R007

old-sha256: aea70646c15ce718acf191c018030257066d2a7dac08a6acccf0f9573ca7cfdc

<!-- req: P/09.2-R007 -->
## N2 Doors

HTTP contract: [09-agent.api.openapi.yaml](09-agent.api.openapi.yaml), the tag `relay`; the bodies are the schemas `Publication`, `Carry`,
`HolderAsk` of the [OpenAPI of the process `domain`](../../08-domain/spec/08-domain.api.openapi.yaml) (one form per wire). Request
parsing — P/01.1 N2.1 with the deviations of [P/06.5](../../06-console/spec/06.5-console.norms.md) N2.

The relay door and the batch `relayed` are the class `signed` of the TLS server side (N1.6): it does not request a client certificate,
the identity is the member's signature.

The six forwarded GET success forms and parameters are the existing owner references in [Forwarded owner forms](../forms/README.md#forwarded-owner-forms). `BackupPartRevision` remains a required query `rev` on GET `/api/backup-part/{member}/{part}` as at the owner; no revision or default is inferred.

| Door | Who answers | Success | Refusals |
|---|---|---|---|
| POST `/api/member/<member>` | the relay door | 200 — the holder's carry for the member (from memory) with `rev` of the relay's copy and `domain_age` | in order: 413 — `Content-Length` larger than BODY_LIMIT, before reading the body, the connection is closed (a chunked body — 400); 503 «the relay has nothing from the domain for \<member> yet» — the relay has no answer of the holder yet (before the first batch): before the signature check, without a knock, and to a stranger too; after the first batch a member that `relay_for` does not name is a stranger by N3 (the signature, the knock, 403; C09-RELAY-FIRST-ANSWER-01); 400 `not_a_publication`; 403 «\<member> does not reach the domain through this relay: the domain's topology says so, not the relay» (a stranger with a valid signature by its own key — remembered as a knock); 403 there is no key (admitted before the keys); 401 the signature, `reason` — a word of the [agent signature contract](../../common/contracts/agent-signature.md) (the key — from `keys`); the outcomes of «accept» over its own copy — 409 `same_sent_at`, 409 `rebase`, 409 `not_ready`, 413 `whole_too_large`, 503 `rev_exhausted` |
| GET `/api/carry/<member>` | the relay door | 200 — carry from memory with its own `domain_age` | global 503 before the first holder batch, as above; afterwards membership/key and signature checks as above, then 503 with the same nothing-yet text if this accepted member has no cached carry; no knock and no fabricated 200 |
| GET `/api/members/<member>/<part>`, `/api/anywhere/<member>`, `/api/topology/<member>`, `/api/backup-part/<member>/<part>`, `/api/book/<member>/<sub>/<book>[/<part>]` | the relay door | forwarding to the holder with the signature as it came, the answer as it is; `rows` of N1.4 — also the memory of rows | 503, 403, 401 — as above; 429 `busy` of the holder — as it came; the holder did not answer — 502 `did not answer` |
| POST `/api/tokens/<member>/…` | the relay door | [P/08.7](../../08-domain/spec/08.7-domain.norms.md) | P/08.7; the holder did not answer — 502 `did not answer`, as forwarding ([forwarding contract](../../common/contracts/forwarding.md) «Forwarding is one function» `answer`; the Architect's decision on the reconciliation of M11, Y8) |

The body of a refusal of the relay door is `{error: "refused", detail, reason?, send_row?}` (the schema `RelayRefusal` of the lesson contract, one closed branch per status): normative are
the status and `reason`, `detail` is required and is the words of the implementation, except two texts, 403 «… does not reach the domain through this relay …» and
503 «the relay has nothing from the domain for \<member> yet», which the norm names. `reason` is, for the outcomes of «accept», a word
of the report reception contract (`not_a_publication`, `same_sent_at`, `rebase`, `not_ready`, `whole_too_large`, `rev_exhausted`), for
401 — a word of the agent signature contract; for the early 400 of a chunked body and the early 413 of the body (both before «accept»), for 405
and for both 403 there is none. A wrong method on these paths — 405; the door
does not set the header `Retry-After` (the reference of the witnesses and the Architect's decision of 2026-10-23, items 1, 4–6).

`same_sent_at` at the relay door is by the last write of its mark of the member: the mark gets the hash of the body (`request_sha256`) at
every write — both of a generation and of `heard` (the report reception contract, steps 2 and 6); an exact repeat of the last body by the same road is
`same`, the answer is a copy (item 3).

The relay door accepts a member by the same function «accept» ([report reception contract](../../common/contracts/accept.md);
owner P/08.3) over its own memory: the relay has its own whole copy of each member and its own `rev` for its deltas. The holder
sees only what the relay raised by a batch.

The token door returns the holder's codes (a hop of the holder) as they came: they are carried by the OpenAPI of the process `domain` (the operation
`holderToken`), the OpenAPI of the lesson carries only the own codes of the relay door (analysis of review of stage A 8–10, decision 3).

---

### `Platform/06-console/spec/06.1-console.norms.md` P/06.1-R006

old-sha256: 4887422c42c13a42ae95da0e2d57ca567ed5d23e5e313dde6f371eb7b5809465

<!-- req: P/06.1-R006 -->

```yaml
id:
  numeric:                                  # unit.id: numeric
    rule:    a decimal integer ≥ 1 from the counter <sub>/next_id: n — the last issued number, the next — n + 1 (review of stage B 6–7,
             № 38); no row — recover below and the creation cas "" with n = the number being issued: without units and claims it is 1, with already
             existing units — the greatest + 1, not 1 (issuing 1 — a collision with a live unit; (the Architect's decision of 2026-10-20, review of stage B 6–7)); the first — 1; a number is never used again,
             in the path — a decimal notation without a sign, spaces and leading zeros (`01`, `+1` — 400 `badkey`);
             tombstones count; a number issued to a refused attempt is not returned
    recover: only with a full confirmed list of rows/tombstones and live claims; a loss of history or a read error does not count as emptiness and does not permit an automatic recovery. The counter does not read or there is no row → the greatest number among the rows <rows>/ (with tombstones) and the numbers in live claims + 1 — the issued
             number; the counter is rewritten whole with n = this number (the last issued, № 38); the numbers of refused attempts leave no traces and after a recovery MAY come out again —
             the only exception from «never», journal `next_id.recovered {from, to}`
  named:                                    # unit.id: <field> — [the row check contract](../../../common/contracts/row-check.md) «Identifier and field constraints»
  made_prefix:                              # ADR-0091 item 1
    rule:    a creation through the door (POST) of an id that begins with «<customer>-» of the subsystem that declared worker.creates to this
             table (the manifest catalogue, P/02.1 N3), — 400 «names starting with "<customer>-" are made by <customer>
             (worker.creates)», also over a tombstone: under this prefix live only the customer's rows; a row with such a
             name, created before the customer was declared, stays and is taken — without its own made the customer does not write it
  made_key:                                 # ADR-0091 item 1
    rule:    in a row with made the fields that the customer's key names (worker.creates[].key, P/03.6 N1.6) are immutable also
             for the door, like fixed: an edit with another value — 400 «<field> is fixed»; the other fields the operator edits through the door
# tombstone, unique, canonical_url, ref_and_must_match — [the row check contract](../../../common/contracts/row-check.md) «Identifier and field constraints»
```

The recovery profile numeric is not compatible with physical cleanup: unit.id: numeric together with placement.unplaced.delete_after is a load refusal of P/02.1. Successful numbers are represented by saved rows/tombstones; the cleanup of done claims does not cancel that. An arbitrary loss of these rows is not covered by the recover formula.

Any name that the grammar of the id and of the slot and the full key limit of P/01.1 permit is stored by any implementation: file names
(bucket directories — the event journal contract «File names in shared trees») the implementation encodes itself; there is no narrower file profile — otherwise parts of different
implementations over the same data are incompatible (reconciliation of python and go M10/3–5, U20).

**Term of a done claim.** The console MUST keep a completed saved answer of a claim with an HTTP code <500 for at least
DONE_ANSWER_KEEP from the moment it was saved. Cleanup uses a local monotonic age;
after the memory is recovered a new observer counts it as fresh and does not trust foreign wall clocks.
This does not extend done to 5xx or pending: their fate stays by N3.

DONE_ANSWER_KEEP, CLAIM_TAKEOVER_AFTER, SWEEP_LIMIT, SWEEP_GRACE and SWEEP_MARK_EVERY are defined only in [runtime-constants.tsv](../forms/runtime-constants.tsv); their formulas and conditions remain owned by these procedures.

### `Platform/06-console/spec/06.1-console.norms.md` P/06.1-R008

old-sha256: 9292fcefd47156b4fc7a8bab32baaf0cb796b10595d1b6cfb372157d19996b4d

<!-- req: P/06.1-R008 -->

A blob is declared only in unit.fields; a blob in a table is outside the profile and is rejected by the loader.
The name of a blob field is 1–64 ASCII: the first A-Z/a-z/_, the rest A-Z/a-z/0-9/_.
An empty name, a path separator, a dot, a percent, a space, a control or non-ASCII character
do not represent the blob door of this lesson: a load refusal `refused:value` with the path of the field.
Other fields are not narrowed automatically by this restriction.

A manifest with any blob field of a unit does not declare unit.fields.bytes: a load refusal
`refused:value` by P/02.1. Without blob the field bytes is permitted. This restriction keeps
the full Unit in the answer of the upload; a renaming of the counter or a new shell is not introduced.

```yaml
field:    type: blob; in the row — "sha256-<64 hex>"; bytes in the body of the row → 400 «takes a digest, not the bytes (N of them):
          PUT the bytes to /<rows>/<id>/<field> and the row gets the digest back»; in snapshot — the manifest does not load
object:   <sub>/blobs/sha256-<hex>; the name — the digest of the bytes; the reader verifies (BlobMismatch — «the object was replaced»)
write:    the object durably (fsync) → the row with the digest (revision + 1) → journal unit.changed {fields, revision, digest}
mirror:   the body copy to a neighbour and its door — P/05 N1.1 «Bodies at the resource» (stage B; the decision on V2 of the move)
delete:   the tombstone and the convergence of body copies — the tombstones contract common/contracts/tombstone.md (owner P/05; C06-BLOB-GC-33-01)
sweep:    <sub>/sweep {at, digests}  — writer the console; every SWEEP_MARK_EVERY
          # the bytes of the row: at — the wall-clock seconds of the first mark of the batch, text by values_by_type N1.2 (float);
          # digests — a list of "sha256-<hex>" by the rule list N1.2 (comma-separated); an empty batch — digests: ""
          # or no row, at then is not read; example: {at: "1760700000.5", digests: "sha256-ab…,sha256-cd…"}
  mark:   only with an empty previous batch, the digests without references from rows (≤ SWEEP_LIMIT) → write with cas; do not refresh a non-empty one; delete nothing;
          a reference — a blob field of the rows of its own subsystem; a row of another subsystem (its string field with <sub>/blobs/<digest>) does not hold the body:
          whoever needs the body longer copies it into its own blob field (C06-SWEEP-FOREIGN-REF-01, the Architect's decision of 2026-10-29, review V/04)
  wait:   SWEEP_GRACE
  sweep:  deletion only in the exceptional maintenance window of N3; an ordinary background pass only marks/waits.
          After the writers are stopped, check the references again; remove the list with cas (a conflict — delete nothing); delete the objects.
          put_blob removes the digest with cas; this cancellation is a help to the marks, not a protection against a parallel deletion
  metrics: <sub>_blobs_total, <sub>_blobs_marked — at manifests with a blob field
```

The body copy at the resource (`mirror`) — [P/05](../../05-resource/spec/05-resource.norms.md) N1.1 «Bodies at the resource» (stage B); tombstones (`delete`) — [the tombstones contract](../../common/contracts/tombstone.md) (C06-BLOB-GC-33-01).

### `Platform/06-console/spec/06.1-console.norms.md` P/06.1-R009

old-sha256: fd48f403cc43ae0020751cac85b30fd9285bd46afade2692812b412dc8b780ae

<!-- req: P/06.1-R009 -->

```yaml
tables:                                   # the manifest (form — P/02.1)
  <t>:
    key:      <a non-secret field of type string> | <a template by P/02.1 N1.4, requests.key>   # the number of substitutions is not limited to two;
                                                     # example: "{of}-{from:int}-{to:int}"; the resulting name by N2
    fields:   {<field>: {type, required, enum, default, schema, ref, must_match, bound_to, credentials, secret_in, schemes}}
              # without fixed, inherit, merge, unique (P/02.1)
    schema:   JSON Schema on the whole row
    stamp:    [by, at, made_at]                   # what the console adds at each write by POST:
              # by — the user of the write; at — the wall-clock seconds of this write; made_at — the wall-clock seconds of the first write
              # of the row, an overwrite keeps it; in the store row — text by values_by_type N1.2 (float),
              # in TableRow — by a string, at and made_at numbers; example of a row: {by: "admin", at: "1760700000.5",
              # made_at: "1760690000"} → TableRow {…, by: "admin", at: 1760700000.5, made_at: 1760690000}
    journal:  {written: <kind>, deleted: <kind>}    # default <t>.written / <t>.deleted
    service:  true                                # a service table of the worker: only by a ticket, the rule below; default false
    writes_via: [<sub>]                           # the rows of the table are written only by these subsystems, by a ticket — N1.1a; with service: true — a load refusal
    delete_after: <integer ≥ 1>                   # the term of a row, seconds; removed by the console reaper (chapter 6.4 N3 `tables`); no key — no term (ADR-0094 step 3b);
                                                  # the places table and the holds table have no such key: a load refusal (P/02.1 N1.4, rows 125, 126)
  list_form:  tables: [<t>] — only the family name for the console's rights; no doors
field_names: held_by/garbled/by/at/made_at/revision/index are not declared (computed fields, stamps and versions, regardless of stamp); name is permitted only with the type string (explicit or by default) with key: name,
             otherwise refused:value at loading. The other service names of a unit (id/worker etc.)
             are not by themselves forbidden to table fields; the values are checked by the declaration.
names:      the name grammar and the list of forbidden table names — the summary table P/02.1 N1.2a; not a value of unit.rows;
            a conflict with any subsystem name of the catalogue — a catalogue refusal by P/02.1 N3, not a permitted intersection root/mount
service:    a table with service: true (ADR-0094 addendum (15) item 3) — a service table of the worker: it is read and written only by a live ticket from the leaf of the role of this same subsystem (chapter 6.3 N1.9, the gate
            and pass contract service; without a kit — from the socket of this role), by the right of consequences, the person's may is not checked. The feed by a ticket gives the rows of such a table whose user is the person of the ticket (N2 «Change feed» «Filter»). Through the door of a person without a ticket it is closed: GET, POST, DELETE of the table and its row in a batch — 403 denied; its rows do not enter the feed `GET /changes` (N2 «Change feed»)
rows:       <sub>/<t>/<name>; writer — the console; a table from worker.writes (P/02.5 N1.4) — a worker table, without declared fields *_secret (P/02.1 N1.2a; the list form — P/03.4 N1.6 `list_secret`): it writes the row whole with cas (the worker side — P/03.4 N1.6, stage B),
            the console only reads (GET with fields), POST → 403 denied «written by its worker»; DELETE by the operator → 200 with cas by
            the read version, as for other tables (journal <t>.deleted); the worker, if the key still belongs to its units, writes
            the row anew on the next pass (P/03.4 N1.6); there is no deletion by the worker by term (the VMS request «commands and device row», the Architect's decision of 2026-10-23); PUT → 405 as an unsupported
            method; the secrets are sealed (chapter 6.2)
revision:   a platform field of each table row (ADR-0094 B4), as for a unit: 1 at creation, +1 on each write; in the row — text by values_by_type N1.2, in TableRow — an integer. It is raised by the writer of the row:
            the console (N3 «table — write a row»), the worker for a table worker.writes (P/03.4 N1.6). Sealing (chapter 6.2) does not raise it. A removed row counts anew from 1: a table has no tombstone.
            A row without a readable revision (written past the writer) is read with revision 0, the next write writes 1
held_by:    for the places table (placement.places.table) GET adds held_by: <worker> | null — the by of the acting hold
            <sub>/holds/<name> ([the observation contract](../../../common/contracts/observation.md) «Hold of a place»), otherwise null;
            the read of the hold or of the holder's heartbeat is not confirmed, the hold row or the holder's heartbeat does not read — null (not
            known), not 503 (N0 P/01.1 «Stability of output»; C06-TABLE-HELD-BY-33-01, the Architect's decision of 2026-10-25; V7 item 3, the Architect's decision of 2026-10-28, P1; row 27 of the list)
name:       TableRow.name — the element name of the row, as stored; the key `<sub>/<t>/<name>` is the address of the row; if they diverged
            (the row is written past the console), GET gives the stored name (reconciliation of python and go M10/6–11, coincided without a norm)
journal_form: <t>.written {sub, target, user, addr, fields, changed, was}, <t>.deleted {sub, target, user, addr}:
            sub — the subsystem, target — `<t>/<name>`, addr — the client address (the event journal contract `journal`); fields — the names of the fields
            of the write, changed — the names of those that changed, was — true if a row with this name existed before the write (boolean);
            unit.changed by the bytes door — {sub, target: <id>, user, addr, fields, revision, digest};
            schema.raised — {version, user, addr} (reconciliation of python and go M10/6–11, T21)
rights:     reading view, writing admin, lower — by rights.routes; rights.unit_of filters the rows and grants (chapter 6.3)
```

The console journals of this chapter (`<t>.written`, `<t>.deleted`, `unit.changed`) are the tree `audit/console` ([the event
journal contract](../../common/contracts/event-journal.md) `journal`, role console); the form of `schema.raised` is at its owner,
[chapter 6.6](06.6-console.norms.md).

The reader digest-list bound equals the existing writer SWEEP_LIMIT through the schema root reference to `$defs.writer`. An over-limit list makes the whole row unreadable, using the existing sweep outcome without truncation or rewrite. Empty batches, absent rows and the separate at rules keep their existing outcomes.

<!-- families:begin -->

### `Platform/06-console/spec/06.1-console.norms.md` P/06.1-R017

old-sha256: 3d0439c650347a2fca9b2bc0b7516262704eb0a67673a0b0c040022a6dabe839

<!-- req: P/06.1-R017 -->

The paths of tables and of blob fields of a unit choose root or /{sub} by chapter 6.5 N2.
In OpenAPI these are the standard servers + paths. /schema and /drain stay common ([chapter 6.6](06.6-console.norms.md)),
/v1/objects is the door of the resource ([P/05](../../05-resource/spec/05-resource.norms.md) N2): the console prefix is not added to it.

HTTP contract: [06-console.api.openapi.yaml](06-console.api.openapi.yaml), the paths `/{rows}/{id}/{blob_field}`, `/{table}`,
`/{table}/{name}`.

Request parsing — chapter 6.5 N2 «Console request parsing» (P/01.1 N2.1 with the deviations of the console). The deviation of the bytes door: the body is bytes (`application/octet-stream`), JSON is not parsed. Another method at a table — `405 {detail: "/<t> takes GET, POST and DELETE of one row", error: "method"}` (contract — `TableMethod`); the method is checked before the write rights. The common console refusals, `HEAD` and the read limit — chapter 6.5 and the full forms of chapter 6.5 N2 «GET /manifest».

| Door | Full success body / special refusals |
|---|---|
| PUT `/<rows>/<id>/<blob_field>` | The full `Unit` (N2 above) plus `bytes` — the number of accepted bytes; 404 `{detail, error}` for an absent unit/field; 409 for CAS; another method on this path, including GET, POST and DELETE, — 405 (reconciliation of python and go M10/6–11, T9; N2 above). `Content-Length` is mandatory, otherwise 400. The bytes door does not read `If-Match` and `Idempotency-Key` (reconciliation of python and go M10/6–11, coincided without a norm). No unit — 404 `error` «no such unit», no blob field — 404 `error` «no such blob field» (reconciliation of python and go M10/6–11, T26). Each successful new call, even with the former bytes, increases revision. Route: any PUT `/[<sub>/]<rows>/<id>/<x>` is the bytes door: the limit of 32 MiB and one of the two places (N1.4) are taken before looking up the unit and the field; no unit or blob field `<x>` — 404 after reading the body |
| GET `/<table>` | `{<table>: [TableRow…]}`; the name of the property equals the name of the table. GET of one row — `TableRow` and `ETag`; 404 `{detail, error}` when it is absent |
| POST `/<table>` | 201 `{row: TableRow}` — the same TableRow as GET of one row (for the places table — with `held_by`), and `ETag`; 400 a text or structural `FormRefusal` (N2 above); 409 `ReferenceConflict` or a text refusal; 412 `revision moved` (N2 «Versions»). This is a full replacement of fields by the manifest, not a patch; `Idempotency-Key` is optional, with it — N3 «repeat memory» |
| DELETE `/<table>/<name>` | 200 `{deleted: name}`; 404 when absent, including with `If-Match`; 412 `revision moved`; 409 — the CAS repeats are exhausted. References to the row do not hinder the deletion: `ref` does not require the target to exist, `must_match` binds only to a live target (N1.3, ADR-0057); `Idempotency-Key` — as for POST |

The door of the body copy at the resource `PUT /v1/objects/<sub>/blobs/<digest>` — [P/05](../../05-resource/spec/05-resource.norms.md) N2 (stage B).

`TableRow` contains the mandatory `name`, `revision`, `index`, the declared fields and stamp; `held_by` is added only to the places table, the value is the name of a worker or null. Secret keys with the suffix `_secret` are excluded recursively, addresses are masked by chapter 6.2. Only an already read but spoiled row — a declared field does not read by its type by values_by_type N1.2, or a present stored stamp at/made_at does not read as row Time by P/01.1 N0 — is represented as `{name, garbled: true, index}`: the index is needed to remove or replace it conditionally; a read/listing failure is 503, not an empty list and not garbled. The input of POST is its own TableInput, not the ClientFields of a unit. A field not given in POST and without `default` is absent in the row and in TableRow: the empty form of N1.2 does not apply to tables; `default` is substituted (the same — [the row check contract](../../common/contracts/row-check.md) «Preparation of fields», «Table row»). Undeclared fields of POST are rejected by the manifest; `name` is computed by key and may come from a declared field of the body of the same name. The computed `held_by`, `garbled`, `revision`, `index` and the stamps `by`, `at`, `made_at` are not set by the client; a given stamp — 400 `unknown field`, even if it is not included in the stamp of the table; `revision` and `index` — the same. A manifest declaring them as editable table fields is outside the profile of this lesson and is rejected at loading. The forms `SnapshotUnit`/`SnapshotShard` describe the snapshot object ([P/04 N1.3a](../../04-controller/spec/04-controller.norms.md)), not a new HTTP route.

JSON bodies are read with the common limit ≥1 MiB, blob with 32 MiB, the resource copy with 64 MiB (P/05). The header does not replace counting the actual bytes. Bad framing/a short body — 400, a timeout — 408, an excess — 413, chunked of the console — 400. Refusals of reading/trust/sealing give 503 with the full form `{detail, error}` by the owner. The success of publishing an object does not prove the success of the next write of the row; with an unknown outcome the client first reads the row or repeats the request with the same `Idempotency-Key` (N3 «repeat memory»); a request without a key is not repeated automatically.

### `Platform/06-console/spec/06.1-console.norms.md` P/06.1-R022

old-sha256: c7cfce058a1ab477f31763aaa125e531cffa0375ce18072fa6e824c9127e8d63

<!-- req: P/06.1-R022 -->

The repeat memory (ADR-0094 B3) is the claim row `<sub>/idem/<key>`, one mechanism for all write doors of people: steps 1, 2 and 9 of the procedure «create»,
«Claim ownership» and the term of [N1.3](#n13-identifier) «Term of a done claim». At `POST /{rows}` the key is mandatory. At `PUT` and `DELETE` of a unit, `POST` and
`DELETE` of a table and the write doors of [chapter 6.6](06.6-console.norms.md) N2.1 the header `Idempotency-Key` is optional: without it the procedure of the door is
as before and a repeat is a new write; with it — the door goes under a claim. At `POST /console/batch` — the same (N3 «batch»). The bytes door and the requests door (chapter 6.4) have no repeat memory.

```yaml
key:        (user, method, path, key)
<key>:      hex sha256(UTF-8(user) ‖ 0x00 ‖ method ‖ 0x00 ‖ UTF-8(path) ‖ 0x00 ‖ UTF-8(key)); 64 lowercase characters, one segment;
            user — the proven name of the caller (chapter 6.3 N1.3); method — in uppercase;
            path — without the subsystem prefix, the segments percent-decoded: `/testsub/counters/a%20b` and `/counters/a b` — one path
fingerprint: the caller, method, path, the body as a JSON value (step 2 of «create»); the door input in query is part of the body; no body — like `{}`;
            If-Match does not enter the fingerprint: a repeat after a lost answer carries the former condition, it is not judged (the order below); for a batch, for the same reason, the `cas` of the rows does not enter:
            it is read anew at each repeat
order:      step 1 (the form of the request and of the key, the body, the ring; If-Match — only the form) → the claim step 2 → If-Match → the door procedure →
            the target write under the guard → the answer into the claim step 9
other fingerprint: 422 `key reused` on all memory doors (ADR-0094 addendum (14))
words:      the header value — N2 (without OWS, twice — 400); a key out of form — 400 `Idempotency-Key required`; a foreign pending younger than CLAIM_TAKEOVER_AFTER — 409 `in flight`;
            503 — `store unavailable` for units, `unavailable` for tables and chapter 6.6
```

The gate and request parsing go before the claim: their refusals do not enter the memory. An answer `< 500`, including a door refusal and `412 revision moved`, is remembered and
given to a repeat as is, by code and body: having decided anew, the client takes a new key. A repeat from memory writes nothing and writes no journal.

**Target write** of a door — its former `cas` together with the guard `{key: <sub>/idem/<key>, index: my version of the claim}` (index: my version of the claim); a write door without `cas` — with the guard.
A prepared done claim is checked by weight before the write, like step 8: over the store ceiling — 413 `row too large`, the write is not performed, to step 9.
A guard refusal — «Claim ownership». The fate of one's own pending at step 9 is the same: remove it only if the target write is reliably not performed.

**Continuation.** A takeover of a claim after CLAIM_TAKEOVER_AFTER does not cancel what the former executor wrote. The one who took over first looks at the target, then goes through the door procedure:

- `POST` of a unit: step 8 of «create» keeps the intended `revision` and `born` in the claim before the target write. The live row has both values → written by this claim, step 9 with this row, before `exists` and `If-Match`. This includes a creation over a tombstone: tombstone revision 5 gives intended revision 6, not 1;
- `PUT` of a unit: step 5a of «edit» keeps the intended `revision` in the claim; the row has this `revision` and the intended `born` → written by this claim, step 9 with this row;
- a write of a table row: step 2a of «table» keeps the intended `revision`; the row has this `revision` → written by this claim, step 9 with this row. Without this the procedure anew would raise `revision` a second time and would refuse its own write with `412`;
- `DELETE` of a unit: the row is already a tombstone → step 9 with `{deleted}`; `DELETE` of a table: the row is already gone → the same;
- at POST of a unit, a claim without the complete saved intended pair `revision` and `born` does not prove a target write: run the ordinary procedure anew; a confirmed foreign live row gives the existing `409 exists`. Other doors without an intended `revision` run their procedure anew.

For POST of a unit, neither an equal foreign `revision` nor a reserved numeric id proves this claim's creation: the saved intended `revision` and `born` must both match the live target. Other door continuations keep their own confirmation rules. The target is looked at before `If-Match`: the condition judges foreign edits, not one's own write.

### `Platform/06-console/spec/06.1-console.norms.md` P/06.1-R023

old-sha256: 7e4d8a58b51bf1fce16cd02dc46105c6587b0619bc837b97701bb75a9d6341fb

<!-- req: P/06.1-R023 -->

```
1. the idempotency key: present, one segment without '/', not '..', ≤ 200 bytes                 → otherwise 400
   If-Match out of form (N2 «Versions»; at numeric the header is not read)                     → 400
   the body is a JSON object                                                                    → otherwise 400 (fault by N4); a lone surrogate
   (`\ud800` without a pair) and a number outside double (`1e400`) — 400 not_json here, before the claim
   the profile of chapter 6.2: the ring is not set and a non-empty *_secret is given at any depth → 400 sealing key required,
   without fault and without creating/changing the claim (chapter 6.2 N1.2, N4); the mask is not used as a fingerprint
   a set unreadable ring → 503 SealingUnavailable for any POST before HMAC/the claim (chapter 6.2 N3)
2. the claim <sub>/idem/<key> (<key> — «repeat memory» above): write cas "" (in the claim — the fingerprint of the request, the time, pending)
   fingerprint: the caller, the method, the path /<rows> (short and with the subsystem prefix — one path) and the body as a
   JSON value (the order of fields and the escaping of a value do not matter, as P/01.1 N3)
   exists, done, the same fingerprint                                                    → the former answer as is
   exists, done, another fingerprint                                                     → 422 key reused
   the claim is out of the claim form                                                    → 503 store unavailable, do not touch the claim
   exists, pending, stands < CLAIM_TAKEOVER_AFTER by the monotonic clock of this console from its first observation
   of the current version of the claim (after a restart the count starts anew), any fingerprint → 409 in flight
   exists, pending, stands ≥ CLAIM_TAKEOVER_AFTER, the same fingerprint                                  → take it by a write with cas; further as one's own
   exists, pending, stands ≥ CLAIM_TAKEOVER_AFTER, another fingerprint                                   → 422 key reused (do not touch the claim)
   the version of the successful write of pending = my version of the claim; after a takeover keep the number already written
3. numeric: the number is already in the claim → use it; otherwise the number n + 1 (n — the last issued, N1.3; no row — recover N1.3:
   the greatest + 1, without units and claims — 1; (the Architect's decision of 2026-10-20, review of stage B 6–7)),
   write next_id {n: number} with cas and the guard of my version of the claim
   (on a conflict of the counter repeat under the same guard; the repeat limit is exhausted → 503 store unavailable by step 9: 5xx is
   not remembered in done, one's own pending is removed — the unit is not written; journal cammeta-go, lesson 3 № 2);
   write the number into the claim with cas of my version,
   the received version of the claim becomes mine; do not create the unit before the number is saved successfully
4. refusals of form and values — [the row check contract](../../../common/contracts/row-check.md) P1–P2 (the preparation of fields — there too) → 400 by N4;
   at *_secret an envelope value enc: and a mask value — 400 (added by M10/7: chapter 6.2 N3 «create/edit», step 2; N4)
5. named: the id begins with «<customer>-» of the declared customer of this table → 400 (N1.3 made_prefix; ADR-0091 item 1);
   the id — [the row check contract](../../../common/contracts/row-check.md) P3 → 400; the row exists and is not a tombstone → 409 exists — except the continuation of a claim (Races): its revision AND born equal the intent saved by this claim
   (no answer in the claim) → step 9 with this row before exists and If-Match; revision 1 is not a special substitute for that intent. A tombstone with other fixed → 400 (P3)
5a. named, If-Match present: no row, or the value is not equal to revision or to the tombstone index (N2 «Versions») → 412 revision moved {revision of the tombstone | 0} without row, to step 9;
   equal — a creation over this tombstone; step 8 writes with cas of this same read, so the condition holds against a race too
6. the mandatory ones — [the row check contract](../../../common/contracts/row-check.md) P4                     → otherwise 400 «needs a <field>»
7. references — [the row check contract](../../../common/contracts/row-check.md) P5                             → 409 conflict with fault
8. prepare the row {id, revision: 1 | tombstone + 1, born: a new random value (N1.2), fields} and the full row of the done claim with the successful answer in the form of the implementation (item 3 of the choice);
   check the weight of both against the store ceiling → otherwise 413 row too large, do not write the unit, to step 9;
   before the target write, save the intended revision and born in pending with cas of my claim version; the confirmed new version becomes mine.
   A retry or takeover preserves and reuses these same intended values, not a fresh born or a newly computed revision. A refused or unconfirmed planning save does not authorize the target write: follow the existing step 9 and claim-ownership rules, keeping pending on an unknown outcome until its owned intent is confirmed.
   write the row with cas "" | cas of the tombstone
   and guard: {key: <sub>/idem/<key>, index: my version of the claim}
   toolarge: reliably nothing is written → 413 row too large, to step 9;
   conflict: re-read the target; its revision AND born match the complete saved intent → step 9 with 201 and that row;
             otherwise a confirmed live row → 409 exists, whether numeric or named; a reserved number alone is not proof
9. remember an answer < 500, including a form refusal 400, in the claim with cas of my version; the write succeeded → return the answer (201: {row, worker: null})
   if the write of the result is not confirmed (including toolarge of the claim itself) → 503 store unavailable;
   do not remember 5xx as done; remove one's own pending with cas only if the unit row is reliably not written;
   if the row is written or the outcome of its write is unknown — keep pending for the continuation
```

**Claim ownership.** The version of the claim row is the condition of each change: the writes/removals of the claim itself
go with `cas` of my version, the reserve of the counter and the creation of the unit — with the guard of this version together with `cas`
of the target row. Checking the claim by a separate read before an unconditional write is not enough.
After a successful change of the claim the executor remembers the new version; a takeover always changes it.
After `412 guard` or a `cas` conflict of the claim the former executor stops the changes and re-reads
the claim, without assigning its new version to itself: the same fingerprint and `done` → the saved answer whole;
the same fingerprint and `pending` → `409 in flight`; another fingerprint → `422 key reused`;
no claim or the store did not answer → `503 store unavailable`, the client repeats with the same key.
It does not save this refusal and does not remove a foreign claim. After an unknown outcome of a write it also
does not continue with the old assumption of success: until it is clarified pending is kept, the client gets 503.

A weight field absent after materialization (for example, an ungiven inherit) does not substitute a refusal of
the value: for computing the weight of such a row placement.weight.default is used. A present
0, a negative or a non-numeric value are not replaced by this default. The empty form of int equals 0,
so a manifest with a weight field without a suitable default may require an explicit positive value
at POST; the materialization rules of N1.2 stay common.

**Races.** Two consoles with one key: the claim with `cas ""` lets one pass; the second sees `pending` and answers `409 in flight`, later — the former answer. Two consoles with different keys and one name: the write of the row with `cas ""` lets one pass; the second gets `409 exists`. A console died after the reserve of the number: the claim after CLAIM_TAKEOVER_AFTER goes to another console, and that one continues from step 4 — the checks of the form, the mandatory fields and the references are repeated — and writes at step 8 with the number from the claim (numeric): use the saved number, but a live row at it is a successful continuation only if this claim's complete saved intended revision and born both match. Without that proof the confirmed live row gives 409 exists; no row proceeds through ordinary step 8 under the same guard. Named POST uses the same proof: revision 1 alone is not sufficient. A console died between the reserve of the number (cas of the counter) and the write of the number into the claim: a claim without a number — reserve anew from step 3, the former number is burnt (two rows, two operations — there is no atomicity between them). A number written into the claim before the death is not burnt; the number of a refused attempt is burnt (steps 5–7 returned a refusal).

The former console A can revive after the takeover by console B. If A reserved 1 but did not save
it in the claim, its late `cas` of the claim is refused; A does not reach the write of unit 1. B reserves 2
and creates only it. If number 1 is already saved, B keeps it at the takeover: the late write of A
under the old guard is refused, and B continues with number 1. If A wrote the unit before the takeover,
B finds this same row and saves the answer; the late `cas` of the answer of A does not replace the result of B.
The same protection acts on a refusal and a removal of pending: A does not delete the claim of B. A lost answer about the creation
does not give the right to remove pending — the saved number is needed for the continuation. These outcomes rely on the atomic
`cas`/`guard` of P/01.1, not on the assumption that the former executor died.

Exceeding the ceiling of a service write before step 8 also gives 413 row too large. If pending is not yet
created, there is nowhere to save the answer; if the claim is one's own — the refusal completes through step 9. The reserved
number is not returned. A refusal to save the result at step 9 — 503: if the unit is already written or
the outcome is unknown, pending stays for recovery; a foreign claim is not changed.

### `Platform/06-console/spec/06.1-console.norms.md` P/06.1-R028

old-sha256: 765c9f8aeec80d9f76296a2fb35ba23f2aca4a43f424b8d9bc320223ccd5747b

<!-- req: P/06.1-R028 -->

| Phase | Conditions and action | On failure |
|---|---|---|
| mark | Every SWEEP_MARK_EVERY a full successful pass; if the current batch of digests is non-empty — do not rewrite at/the version and do not add new ones. If there is no list/it is empty — CAS of a new batch ≤SWEEP_LIMIT without references with at of the first mark | An unknown pass — mark/delete nothing |
| grace | Wait 300 s of observation of an unchanged version of the list by the local monotonic clock. The first look/a new version start from 0; put_blob can remove a mark | Repeat the read later |
| deletion admission | One operator closes the new writes of units/tables with blob, blob PUT, import/restore and incoming mirror copies; waits for the started operations. One sweeper | An unknown outcome of a writer or an unconfirmed quiet — no deletion |
| sweep | In this same window re-read all references and the list and compute the `peers` of the tombstones ([the tombstones contract](../../common/contracts/tombstone.md) «Neighbours»: the listing of doors or of the output is not confirmed — no deletion). doomed = the marked ones without references; remove the list by CAS; only then get_at and delete_at of each doomed one older than the mark — the boundary «older than the mark» only by a readable `at`. `at` absent or does not read with a non-empty batch — delete nothing from it in the window: remove the batch by CAS by the read version, the output line «`<sub>`: batch dropped: mark time unknown (`<n>`)», `<n>` — the number of digests; a dropped batch is not a failure: the window code is by the whole window (N2 «Sweep window command»); the next mark writes a new batch with `at` (C06-BLOB-CUTOFF-33-01, the Architect's decision and answer of 2026-10-25) | A read error/a conflict — skip the deletion, do not count the absence as proven |
| completion | Retain the `written` of each exact body version admitted to `delete_at`; before deletion compute its tombstone stamp `max(now, removed_written + 0.001)` in seconds, with exact millisecond arithmetic (the tombstones contract). Durably write those tombstones to the deleted ones (the form and `peers` — the same contract); on a partial failure keep the ban on writers until the tombstones are restored/the outcomes are determined | Do not open copying that could resurrect the deleted |
| exit | After the completion of the window return the writers/copying | The next sweep begins a new pass |

mark/grace/sweep of one sweeper do not overlap; in the exceptional window the other sweepers, including mark, are stopped.

at is the diagnostic time of the first mark of the batch, not a sliding term. A decrease of the list does not add a new digest and starts a new conservative window of observing the version; a new observer always waits 300 s. The passes in T0+60…540 do not update a non-empty unchanged batch, so by T0+600 the grace is already waited out. New candidates get only into the next batch after the former one is emptied.

In the ordinary mode only mark/grace are executed, once a minute. Deletion is not an automatic action of a live installation. `delete_at` and the CAS of the list prevent part of the conflicts, but by themselves do not protect from a new reference after the check: only the window without writers ensures that. The results of a pass obtained before the stop are not used for sweep.

### `Platform/06-console/spec/06.3-console.norms.md` P/06.3-R006

old-sha256: 254dfc5d5c3b1292e5d3673954a86374ecac16835a4d2f79444796b55fc4d206

<!-- req: P/06.3-R006 -->

In the current GET /session response for via=ticket, until equals the ticket exp and grants are the rows of its person under the gate-and-pass contract. This reads the ticket; it is not a new POST /session admission.

A worker with `door.pass` of the second kind calls the console back by the ticket of the request ([gate and pass contract](../../common/contracts/gate-and-pass.md) «Pass of the second kind»; ADR-0094 B1, ADR-0091 addendum (30)).
This is a separate path of identity: neither a cookie nor a token, so the gate judges it by its own order `ticket`, and with a kit it goes to a separate listener of the console with a required role leaf (the role certificate contract «The callback leaf»; ADR-0094 addendum (16)), without a kit — to the socket of the role ([P/02.5](../../02-installer/spec/02.5-installer.norms.md) N1.5). The doors of the list are the same as at the main listener: only the identity is different. The manifest names the doors in `calls`; the check is the intersection with the closed list below. The loader rejects
`calls` outside the list ([P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.4), a door outside `calls` on a request is 401 (`ticket` step 4). Thus a captured worker does only what a translator inside the console could do, and only for people whose requests go through it now.

| The `calls` entry | Doors | Right |
|---|---|---|
| `<s>/<rows>`, `<s>/<t>` | the rows of units and of a declared table of the subsystem `<s>`: `/<s>/<rows>`, `/<s>/<rows>/<id>`, the bytes door, tombstones `?deleted=1&about=`, `/<s>/<t>`, `/<s>/<t>/<name>` | `need` of the door; for its own table `service: true` — the rule `service` of the contract |
| `<s>/policy` | the common setting `/<s>/policy` | `need` of the door |
| `GET <s>/where` | both forms of `/where` of the subsystem `<s>`, only `GET` and `HEAD` (ADR-0112 addendum (1) item 1) | `need` of the door, `view` on the unit |
| `<s>/<door.pass segment>` | the door `door.pass` of the first kind of the subsystem `<s>`: the segment is the first segment of `door.pass` of the manifest, `/live/accounts`; the person of the ticket is judged; the console puts the token of the external request into the passed `Authorization: Bearer`, it is not shown to the addressee of the ticket ([gate and pass contract](../../common/contracts/gate-and-pass.md) `first_kind`; ADR-0112 addendum (3) item 1); the password of the account goes once, it gets neither into the journal nor into the row. The limit: the entry opens the whole segment, all methods and subpaths; a new door under the segment is reachable by ticket without an edit of the list (ADR-0112 addendum (3) item 4) | `need` of the door |
| `servers/labels` | `PUT`, `DELETE /servers/{server}/labels` | `need` of the door |
| `<s>/requests` | the submission `POST /<s>/requests` ([chapter 6.4](06.4-console.norms.md)) of any subsystem; a write only, the door does not read the rows of requests (ADR-0105 item 4) | `need` of the door, as for a person: `edit` on the unit of the body, `rights.reach`, `names`; the person of the ticket is judged |
| `marks` | only `POST /marks` ([chapter 6.4](06.4-console.norms.md) N2), `occurred` too; `user` of the row is the person of the ticket, the row carries `via`; a mark has no delete and no edit (ADR-0112 addendum (13) item 8) | `need` of the door, `edit` on the unit of the body; the person of the ticket is judged |
| `<s>/next_id` | `GET /<s>/next_id` | `need` of the door |
| `<s>/<route>` | a route of `door.routes` of the subsystem `<s>`: `/<s>/<route>/<id>[/…]` — «Door route» below | `view` on the unit `<id>` |
| `console/batch` | `POST /console/batch` (ADR-0094 B9, addendum (9) item 2) | `need` of the door; each row of `writes` is an entry of the list, below |
| `changes` | `GET /changes` (ADR-0094 B2) | `need` of the door, the filter is that of the person of the ticket |
| `folders` | the folder doors `/folders`, `/folders/<id>`; the prefix `GET ` — read only ([chapter 6.8](06.8-console.norms.md) N2) | the folder rights of chapter 6.8 N3 |
| `<s>/operations` | the operation doors `/<s>/operations…` of its own subsystem only, with `door.pass.operations` (relation 133 of P/02.1) ([chapter 6.9](06.9-console.norms.md) N2) | the rule of the door: with `service: true` — the ticket and the author |
| `domain/roles/lines` | `PUT /domain/roles/<name>/lines` ([P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.3a; ADR-0111 item 16) | of the person, at the process `domain` |
| `domain/edits`, `domain/member-rows/<part>`, `domain/placement`; the prefix `GET ` — read only | the kept edit `POST /domain/edits`, the list and the admission of members, the placements ([P/08.6](../../08-domain/spec/08.6-domain.norms.md), [P/08.3](../../08-domain/spec/08.3-domain.norms.md); ADR-0110 step 8) | of the person, at the process `domain` |
| `domain/folders`, `domain/memberof`; the prefix `GET ` — read only | the doors of folders and of membership of the domain ([P/08.5](../../08-domain/spec/08.5-domain.norms.md) N1.8; ADR-0110) | of the person, at the process `domain` |
| `GET domain`, `GET domain/users`, `GET domain/groups`, `GET domain/roles`, `GET domain/grants`, `GET domain/<s>/<rows>`, `GET domain/<s>/tables/<table>`, `domain/batch` | the doors of the domain — «Domain doors» below (ADR-0094 addendum (11), ADR-0098 §6; the view, units and tables — ADR-0110) | of the person, at the process `domain` |
| `domain/verify` | `POST /domain/verify` — a check of the credentials of a second person without an entry ([chapter 6.7](06.7-console.norms.md) N1.15; ADR-0119); a write only; the cluster console forwards with the token of the person of the ticket and `X-W2C-Ticket` (the forwarding contract «Ticket on forwarding»); for a person without a ticket the door is closed | the person of the ticket is the author; `need` is judged by the console (N1.15) |
| `GET domain/<s>/books/<book>` | the book door of this member `GET /domain/<s>/books/<book>` ([chapter 6.7](06.7-console.norms.md) N1.1), read only, the whole path, not a beginning: `…/books/<book>/x` is not this door, 401 of step 4; the cluster console answers itself, there is no forwarding; a book without `show` — 404 of the door (ADR-0103 item 5; C06-CALLS-BOOK-01) | `need` of the door, `view` |
| `GET domain/<s>/books/<book>/*` | a section of a book `to: "*"` at the holder `GET /domain/<s>/books/<book>/*/<part>` ([P/08.5](../../08-domain/spec/08.5-domain.norms.md) N2), read only; the cluster console forwards with the person's token (ADR-0113 addendum (26) item 2) | of the person, at the process `domain` |
| `GET domain/relays` | the door `GET /domain/relays/<relay>` of the domain console ([P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.2a), read only; the cluster console forwards with the person's token | `view` of the domain, at the domain console |
| `GET domain/<s>/kept/<name>` | the row door `GET /domain/<s>/kept/<name>` of the domain console ([P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.2a), read only, the whole path; `<name>` is an element of `domain.kept_read` of the subsystem `<s>`; the cluster console forwards with the person's token, the ticket goes no further than it | `view` of the domain, at the domain console |
| `GET <s>/heartbeats` | the heartbeat door `GET /<s>/heartbeats` ([chapter 6.7](06.7-console.norms.md) N1.6 `pulse`), read only, at `<s>` with `heartbeat.door`: only the named fields (ADR-0112 addendum (12) item 3) | `need` of the door |
| `GET domain/shared/<s>` | the value of the shared settings `GET /domain/shared/<s>[?unit=]` ([chapter 6.7](06.7-console.norms.md) N1.14), read only, the whole path; the cluster console answers itself, there is no forwarding (ADR-0112 addendum (12) item 1) | `need` of the door, `view` |
| `domain/shared` | the document of the shared settings of the domain `GET`, `PUT /domain/shared` ([P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.2f, [P/08.9](../../08-domain/spec/08.9-domain.norms.md) N1.9); the cluster console forwards with the person's token (ADR-0112 addendum (12) item 1) | `GET` — `view` of the domain, at the domain console; `PUT` — of the person, at the process `domain` |
| `GET domain/topology` | the door `GET /domain/topology` ([P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.2c), read only; the cluster console forwards with the person's token (ADR-0112 addendum (12) item 1) | `view` of the domain, at the domain console |
| `GET domain/at/<s>/<name>`, `GET domain/at/events` | a read at another member `GET /domain/at/<cluster>/<s>/<name>[/<id>]`, `GET /domain/at/<cluster>/events`, the heartbeat `GET /domain/at/<cluster>/<s>/heartbeats`, a door route `GET /domain/at/<cluster>/<s>/<route>/<id>[/…]`: `<name>` is a route of `door.routes` without `role` ([chapter 6.7](06.7-console.norms.md) N1.6): the console forwards with the person's token, the ticket goes no further than it (ADR-0111 item 15) | of the target console, by its gate |
| `GET manifest/<s>/source` | the full form of the manifest `GET /manifest/<s>/source` ([chapter 6.5](06.5-console.norms.md) N2), read only; it is read by `backend` of VMS for the description of a view (ADR-0116 addendum (6)) | `need` of the door |
| `GET manifest`, `GET servers`, `GET events`, `GET session`, `GET schema` | only reading of these doors; `GET /session` — «who am I» and its grants, `via: ticket` | `need` of the door |

The prefix `GET ` at an entry `<s>/…` leaves only `GET` and `HEAD`. The path is compared without the mount prefix: with `CONSOLE_ROOT=<s>` the entry `<s>/<rows>` also covers `/<rows>`. `<s>/<rows>` at a subsystem that is not in the catalogue is not judged: there are no doors, the request is 404.

**Batch rows.** The ticket does not widen the list through the batch door: each row of `writes` is an entry without the prefix `GET`, a guard of `guards` is an entry with the prefix or without it, the guard `<s>/opbusy/<root>` is the entry `<s>/operations`; the counter `<s>/next_id` is covered by the entry `<s>/<rows>`, because it goes in the batch when a row is created; the rows `platform/folders/<id>` and `platform/memberof/…` — by the entry `folders`; the result and the counters of an operation — by the ticket of the step (chapter 6.9 N2 «Step batch»). A row outside the list is 401 of the whole batch, nothing is written.

**Door route.** The manifest `<s>` declares the door of the unit holder, `door.routes`. A request `<method> /<s>/<route>/<id>[/…]` the console passes to the live holder of the unit `<s>/<id>`: the holder and the address are as for `GET /where/<id>` ([chapter 6.5](06.5-console.norms.md) N3), the right is `view` on the unit, the journal entry is `door.issued`. The worker receives the path `/<route>/<id>[/…]`, the query, the body ≤ 1 MiB, `Content-Type` and `Authorization: Bearer <door token>` for this person; the answer is the status, `Content-Type` and the body ≤ 4 MiB, as they came. The limit is `PASS_WAIT`. No holder — 503 `{detail: "no worker of <s> with a door is heard", error: denied}`. The door `/where` itself is not in the list: the address and the token stay at the console, and the ticket dies together with the request (ADR-0094 addendum (12) item 7). A stream ticket goes to this route by any method: only so does a stream route call the model, and there is no write in this call.

**Domain doors** (ADR-0098 §6, ADR-0094 addendum (11), addendum (12) items 9, 10). An entry of `calls` opens exactly its own door. The ticket goes no further than the cluster console: the console forwards the request to the domain console by the [forwarding contract](../../common/contracts/forwarding.md) with the original token of the external request, which it keeps only in memory, next to the ticket; the worker does not see it. The kind of the session is `person`. `GET domain`, `GET domain/<s>/<rows>`, `GET domain/<s>/tables/<table>`, `GET domain/<s>/kept/<name>`, `GET domain/relays`, `GET domain/topology` and `GET` of the entry `domain/shared` the domain console answers itself, the right is [P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.2a. The process `domain` judges the right of the person as for the page ([P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.5), `by` is the name of the person, the journal carries `via: <sub>/<instance>`. The cluster console sets on this forwarding the header `X-W2C-Via-Worker: <sub>/<instance>` ([forwarding contract](../../common/contracts/forwarding.md)).

**Not included:** the writes of `/session`, `/session/break-glass`, the grants of the cluster and people by other doors, keys, `/drain`, the write of `/schema`, `/mounts`, the families `<s>/idem/*`, `<s>/asked/*`, the other `platform/*` and `domain/*`. The reason: doors beyond the translation of rows would give a captured worker consequences that outlive the request (ADR-0094 B1); the consequence of writing rights is accepted by the owner with the alarm `domain.rights_via_backend` (ADR-0094 addendum (12) item 10); the accounts of the first kind and the server labels outlive the request: accepted by ADR-0112 addendum (1) item 1; the mark `marks` is only a journal: accepted by ADR-0112 addendum (13) item 8.

---

### `Platform/06-console/spec/06.4-console.norms.md` P/06.4-R012

old-sha256: 90ce0b32f04cdf81a5038bd71f9b915c7b4328c7fcc074da77118578d05d888c

<!-- req: P/06.4-R012 -->

Two more jobs of the reaper with their own periods: [chapter 6.8](06.8-console.norms.md) N3 «folder reaper», [chapter 6.9](06.9-console.norms.md) N3 «operations reaper». Neither depends on the maintenance window.

- **clear:** an ordinary request: a confirmed mark with an outcome for the same `unit`/digest;
  fetched is a hint to re-read the mark, the absence/displacement of rid from the heartbeat does not cancel a confirmed outcome;
  rid in fetched is the name rid or SaidID(rid) among the comma-separated names (P/03.4 N1.1 `said_id`);
  the ADR-0054 append: a confirmed fetched of the holder, do not read/create a mark;
  wait for the age ≥ settle by the rule of the request and its mark contract («States…»; V1), confirm the current row and the ground;
  delete by cas; remove rid from the person's accounting (rids − rid, cas); unknown → leave it.
- **gone:** before the deadline branch, every SWEEP_EVERY: a request (an ordinary one and an append, except resource rows) whose addressee unit is absent —
  a confirmed read: there is no row `<sub>/<rows>/<unit>` or it is a tombstone — the mark gone create-once
  `{unit, digest, outcome: gone, ended_by: reaper, ended_at}` (the request and its mark contract no_begun; at an append — its
  only mark), then delete the row by cas after the age ≥ settle and remove rid from the person's accounting by cas —
  the reservation per_person is released; an unknown read — leave it (ADR-0091 addendum (11) item 4: otherwise an append to a deleted unit would
  never close); at an append settle runs from the first confirmed read of the mark gone (the request contract «States…»;
  the vectors reap; C06-GONE-FETCHED-33-01).
- **expired:** after gone, every SWEEP_EVERY: an append (except resource rows; a body with an action from elsewhere is also an append) without a confirmed
  fetched and without a mark, the unit confirmedly exists, ttl is declared and not 0, the age of the row by the ttl rule (the request contract,
  the manifest section) ≥ ttl + REAP_AFTER — the mark expired create-once `{unit, digest, outcome: expired, ended_by: reaper,
  ended_at}` (no_begun; the second mark of an append after gone, a row has one of the two): no one serves such a request, a live
  holder closes it earlier. Further as gone: settle runs from the first confirmed read of the mark, the row is removed by
  cas, rid leaves the person's accounting by cas — the reservation per_person is released; a conflict of the mark → re-read; an unknown
  read — leave it. A new request with the same rid after the mark is accepted, and the former mark closes it through settle, not through ttl (the repeat window is shortened; the mark is not removed, the request contract «States…»). A late fetched does not change the mark and does not shift the start of settle: the outcome is one, the first confirmed one
  (the request contract «States…»; VMS request «request term», the Architect's decision of 2026-10-29; the vectors reap).
- **sweep:** the marks branch is only the ordinary profile; an append, elsewhere and resource rows get no marks of this procedure.
  An ordinary row with valid_until + REAP_AFTER < now or older than ttl (without a deadline):
  - no mark → the mark expired create-once `{ended_by: reaper, unit, digest from the row}` (the request and its mark contract `no_begun`; V1);
  - the mark begun without an outcome → `{outcome: unknown, ended_by: reaper, error: "begun and never answered"}` by the index;

  delete the row by cas only after a confirmed mark with an outcome and the age ≥ settle;
  a conflict of the mark → re-read; an unknown read/write → leave the row;
  remove rid from the person's accounting by cas; resource requests (the family of the key `requests/free-<server>-<volume>`, P/05 N1.4; review of stage B 6–7, № 37) without an owner — by ttl.
  An append without fetched is not closed by a mark and not removed by age alone; its handler finishes it. The exceptions are
  the branches gone and expired above (age ≥ ttl + REAP_AFTER).
- **tables:** every SWEEP_EVERY: for each table of the manifest with delete_after (P/02.1 N1.2a; ADR-0094 step 3b; the tables holds.table and placement.places.table declare no term) — list `<sub>/<t>/` (P/01.1 N3
  «list»: key → version). The age of a row is the local monotonic age of the first observation of this version by the console:
  the store does not give the admission time of a write (P/01.1 N3 «Admission time»), the version is opaque, and the writer's clocks do not judge the term —
  the stamp at is not read here. A new version starts the age anew. A restart of the console does too: an unknown age is not
  considered expired, the term only grows longer. Age ≥ delete_after — delete the row by cas of the observed version; the body
  of the row is not read, so an unreadable row is removed the same way. conflict → a new version, the age anew; the listing
  or the deletion is not confirmed → leave it. There is no tombstone; the journal `<t>.deleted` is written only by the door (it has the user and addr
  of the request, P/06.1 N1.6). The reaper does not touch the rows of tables without delete_after.
- **asked:** an age ttl/settle alone does not permit removing a non-empty accounting. In the background remove a single rid by CAS
  only after a confirmed mark with an outcome of an ordinary request, or a confirmation of fetched of an append
  by the exception rule, or its confirmed reaper's mark (gone, expired); a repeated CAS re-reads the whole list,
  not losing new rid. An empty accounting row may be deleted by CAS after ttl/settle.
  A reservation without a proven outcome, including the absence of the row, is not released automatically: a late
  filing can still create the row. The administrative DELETE asked is called by the operator only in a window where all filings of this person are stopped
  and finished and their remaining requests are closed. Unconfirmed quiet — the operator
  does not call DELETE; this is an allowance of the served profile, an automatic detection of the window is not promised.

**Races.** Marks against holders (two holders, the reaper against the one who began, a repeat of filing with the same rid) — the [request and its mark contract](../../common/contracts/request-mark.md)
«Races of marks» (moved there; review of stage B 3–5, V1).

---

### `Platform/06-console/spec/06.6-console.norms.md` P/06.6-R007

old-sha256: 39967363d73a9bfaad88e84433eed7b23d3b17563791776de4f369a8833d135a

<!-- req: P/06.6-R007 -->

PUT /policy takes closed PolicyInput with servers only (shared or distinct); revision is not an input field. Policy with revision remains the response form.

The parsing of a request is [chapter 6.5](06.5-console.norms.md) N2 «Console request parsing» (P/01.1 N2.1 with the deviations of the console);
the controller doors have no deviations of their own (a repeat of `server` at `POST /drain` — 400 by the common rule).

`/policy`, `/unplaceable` and `/where/{id}` belong to the chosen subsystem; at the root one they are
without a prefix, at a mounted one — with `/<sub>`. `/drain` and `/servers/{server}/…` are located
at the console root and cover all its manifests (ADR-0026). A subsystem prefix does not create copies
of the cluster rows. The rights — the role `console` of [P/02.5 N1.4](../../02-installer/spec/02.5-installer.norms.md); the order of the gate — [chapter 6.3](06.3-console.norms.md) N1.3 `identity` and `need`. The standard servers of these three path items
give both full URLs; the common /drain and /servers/{server}/… do not inherit the prefix.
The name sub explicitly chooses a loaded manifest, including CONSOLE_ROOT (chapter 6.5 N2).

| Operation | Input | Success |
|---|---|---|
| GET /policy | no body | 200 Policy: `{servers: shared \| distinct, revision}`, the effective value; `revision` 0 — no row |
| PUT /policy | a required object with only `servers` | 200 Policy after the write; journal policy.changed |
| GET /drain | no body | 200 DrainState, a snapshot of the state by N1.2, with `revision` of the row `platform/drain` |
| POST /drain | a required non-empty query `server`, no body; no `server`, it is empty, repeated or not by the server name grammar — 400 `{detail, error}` by N4 | 200 `{draining: server}`; a repeat of the same server is idempotent, another one during an active drain — 409; the write `{server, at, revision}` — by `cas` of the read version of the row (no row — `cas ""`), conflict → re-read and decide anew, the retry limit exhausted — 503 (N3 «drain — start»; the Architect's decision of 2026-10-20, review of stage B 6–7) |
| DELETE /drain | no body | 200 `{draining: ""}`, also if already removed; the end of the drain is one word: the write `{server: "", at, revision}` by `cas` of the read version (conflict — re-read), do not delete the row; no row or `server: ""` in it — write nothing (the Architect's decision of 2026-10-20, review of stage B 6–7) |
| GET /servers/{server}/labels | an optional query `labels`: comma-separated labels, an empty string — an empty set; an empty element (`a,,b`) — 400; a repeated label (`a,a`) — 400 (the Architect's decision of 2026-10-20, review of stage B 6–7) | 200 `{would_move: [<sub>/<id>…], revision}` — only the units of subsystems with `constraint: labels-subset`; with the query — a probe of this set without a write, without the query — a probe of the current effective labels; `revision` — of the label row, with the query and without it, 0 — no row |
| PUT /servers/{server}/labels | a required object with only `labels`: an array of labels without repeats (a repeat — 400; review of stage B 6–7, № 40) | 200 `{will_move: [<sub>/<id>…]}` after the write of the row; this is a forecast of the next pass, not a confirmation of a move; no journal |
| DELETE /servers/{server}/labels | no body | 200 `{}` after the removal of the row; the node labels apply again; no journal |
| POST /servers/{server}/decommission | an optional body; its absence equals `{}`; only `why` (a string) and `gone` (a boolean) are allowed | 202 `{}` or `{warning: <non-empty string>}` on a confirmed decommission of a never-heard resource; the journal server.decommission_requested — only at the write of the row: a repeat while the row stands — 202 without a rewrite and without a journal (N3 «decommission_server») |
| DELETE /servers/{server}/decommission | no body | 200 `{}` after the withdrawal of the request; the mark is removed by the next pass of the controller; the journal server.decommission_withdrawn, only if the request row existed (N3 «decommission_server») |
| GET /unplaceable | no body | 200 an array of Unplaceable |
| GET /where/{id} | id by chapter 6.1, the kind is set by the manifest; an empty id (`/where/`) is not a route, 404 | 200 Where; not placed — 404 `{reason: <non-empty string>}` |

**Replay memory** (ADR-0094 B3). `PUT /policy`, `POST` and `DELETE /drain`, `PUT` and `DELETE /servers/{server}/labels`, `POST` and `DELETE /servers/{server}/decommission`,
`PUT /schema` read the optional `Idempotency-Key` by the rule of [chapter 6.1](06.1-console.norms.md) N3 «replay memory»: the key is `(user, method, path, key)` (user, method, path, key), the order is
«parsing of the request → claim → pass of the door → write under the claim guard → answer into the claim», an answer `< 500` is remembered, the term is as at `POST`. Another body or another query input
under the same key (`server` at `POST /drain`, `version` at `PUT /schema`) — 422 `key reused`; a foreign pending one younger than 30 s — 409 `in flight`; a key out of form — 400 `Idempotency-Key required`.
The claim of `PUT /policy` is `<sub>/idem/<key>` of the chosen subsystem; at the cluster doors `/drain`, `/servers/{server}/…`, `/schema` it is `<CONSOLE_ROOT>/idem/<key>`
([chapter 6.5](06.5-console.norms.md) N1.1): they have no family of their own, the path in the key distinguishes the doors. Without the header the doors are as before.
The doors that write `revision` hold the intended `revision` in the claim before the write, as chapter 6.1 N3 «edit» step 5a. The one who took over a claim looks at the target before `If-Match`: the row has this `revision` → written by this claim, the answer by step 9;
`DELETE` of the labels: no row → the same. Otherwise the pass anew would raise `revision` a second time and refuse its own write with `412`. The decommission of a server does not write `revision`; its taken-over claim passes the door anew: it converges.

**Row version** (ADR-0094 B4). The snapshots of settings — `<sub>/policy`, `platform/servers/<host>`, `platform/drain`, `platform/schema` — carry `revision`: 1 at the creation of the row, +1 for every write. A write goes with `cas` of the read version (no row — `cas ""`):
without it two writes would raise `revision` to the same number. A conflict — re-read and check the condition again, the retry limit exhausted — 503 `unavailable`. A pass without a write (`POST /drain` of the same server, `DELETE /drain` without a drain, `DELETE` of the labels without a row)
does not move `revision`. Removed labels count anew. A row without a readable `revision` reads as 0, the next write writes 1.

`If-Match`, `ETag`, the index and `412 revision moved` are [chapter 6.1](06.1-console.norms.md) N2 «Versions», with the same words:

- `ETag` is carried by `GET /policy`, `GET /drain`, `GET /schema`, `GET /servers/{server}/labels` and the success answers of `PUT /policy`, `POST` and `DELETE /drain`, `PUT` of the labels, `PUT /schema`, if the row exists. No row — no `ETag`; `DELETE` of the labels removes the row — no `ETag`.
- `If-Match` is read by `PUT /policy`, `POST` and `DELETE /drain`, `PUT` and `DELETE` of the labels, `PUT /schema`. The decommission of a server does not read it: it is a request, not a snapshot of a setting, and `PUT` does not edit its fields.
- The order: the parsing and the form of `If-Match` → the claim → the read of the row → the condition → the pass of the door → the write. The condition stands before the checks of the door: the client judges the row that it saw.
- No row and `If-Match` present — 412 with `revision: 0`, without `row`: the condition names a version that does not exist. To create a row, the client sends a request without `If-Match`.
- `row` of the refusal 412: `{servers, revision}` at the policy, `{labels, revision}` at the labels, `{server, at, revision}` at the drain, `{version, revision}` at the schema.

In all rows of the table the JSON objects are closed: there are no unlisted fields. A success `{}` contains a JSON object,
not an empty HTTP body. A label is by [the label alphabet](../../common/contracts/labels.md) (1–64 ASCII characters: the first a letter/digit,
then a letter/digit, `_`, `.`, `:`, `-`). A query list is parsed by commas, without empty elements,
except a wholly empty string; a server in path/query is a server name: a host name of RFC 1123 — labels separated by «.», a label of 1–63
characters `[A-Za-z0-9-]`, not starting and not ending with «-», in total not more than 253 bytes (`..`, `.`, a space, `/` are not a name);
otherwise — 400 before the existence check (reconciliation of python and go 2026-10-18). Into `will_move` and
`would_move` go only the references available to the caller by `view`; the list can be empty.
The label forecast `would_move` / `will_move` is the set of units that **leave** the server s, not that come to it (review
of stage B 6–7, № 33): a unit of a subsystem with `constraint: labels-subset` whose worker of the effective placement
([the observation contract](../../common/contracts/observation.md) «Reading the decision: intent → placement → intent») is fresh by the same
contract and whose heartbeat names `server: s`, while the labels of the unit (its field `labels`, [P/04 N1.3](../../04-controller/spec/04-controller.norms.md)
`constraint`) are not a subset of the checked set: the query `labels` or the body of `PUT`; at `GET` without the query — the current
effective labels of the server (the row `platform/servers/<s>`, otherwise the node labels — P/04 N1.3). Unplaced units, units
of other servers and units which the set would suit on this server do not enter the forecast. The references `<sub>/<id>` are without
repeats, in ascending order of the UTF-8 bytes of the reference string. The forecast is a read output: a non-answer when reading heartbeats and placements (and their listing) is
`lapse` of the observation contract, the forecast by the memory of the last read versions (C06-PULSE-LAPSE-503-01); a source not read even
once since the start — 503 `unavailable`, at `PUT` — before the write of the row: there is no write without an answer. The write of the label row by `PUT` does not depend
on the heartbeats and is not an admission by observations (C06-PULSE-LAPSE-503-02, the Architect's decision of 2026-10-29).
The subsystem name in the reference `<sub>/<id>`, in the keys of the drain maps and in the field `subsystem` follows P/02.1 N1.2,
including the whole closed list of reserved names; the grammar of the id itself is [chapter 6.1](06.1-console.norms.md) N1.3.
The existence of a server is determined by all subsystems and resources of the console: a server is known if there is at least
one piece of evidence — the heartbeat of the resource of this server, the row `platform/doors/<host>`, the field `server` of a worker heartbeat
or of a slot of any subsystem, and for the label operations also the row `platform/servers/<host>`. For all three
label operations and both decommission methods an unknown server — 404. A wrong form of the body/labels — 400 before this check.

### `Platform/06-console/spec/06.6-console.norms.md` P/06.6-R008

old-sha256: 1f0fc4e3a63d57a7b42ee35ddfee7618f873b62965c8fc87ca8732a6cd27a0d0

<!-- req: P/06.6-R008 -->

- **Unplaceable:** `{id, labels, workers_live, why?}`. `id` is a string; `labels` is an array of labels;
  `workers_live` is an integer ≥ 0; `why`, if present, is a non-empty reason from the field `unplaceable` of the last
  pass report ([P/04 N1.2](../../04-controller/spec/04-controller.norms.md)): the controller decides, the console reads. These are the units without a place,
  including at an empty pool, and the units for which the constraints give no candidate.
- **Where:** `{worker, server, reason, directory, scans, door?}` by [chapter 6.5](06.5-console.norms.md) N3 «`/where/<id>`». `worker` is a non-empty
  assignment name by the slot grammar of P/03.2 N1.4; `server` — from the worker heartbeat, otherwise from the field `server` of its slot row,
  otherwise null (reconciliation of python and go 2026-10-18); `reason` is a
  non-empty reason of the decision; `directory` is the name from the last scan of assignments or null;
  `scans` is the number of completed scans ≥ 0 since the start of the console. The directory cache can lag behind the decision;
  the frequency of the assignment scan is «Implementation decides» item 1. For an unplaced unit, 404 `{reason}` takes the reason
  from the field `unplaceable` of the pass report, and without it — `not placed: no worker holds it`.
  The optional `door` contains `url`, `token` (non-empty strings), `expires` (a number of wall seconds)
  and `routes` (an array of non-empty strings); the conditions of issue (`view` on the unit, the journal `door.issued`) and the term (TTL DOOR_TOKEN_TTL) are chapter 6.5 N3 «`/where/<id>`», not a right that follows from the schema.
- **DrainState:** `{draining, safe, would_strand, subsystems}`. `draining` is a name or `""`;
  `safe` is a boolean; `would_strand` is a map subsystem → array of ids.
  The value `subsystems[sub]`: `{draining, subsystem, workers, units, pending_writes, would_strand, safe, pending_unsaid?}`.
  `draining` is the same name or `""`, `subsystem` equals the key of the map; `workers`, `units`,
  `pending_writes` are integer counters ≥ 0; `would_strand` is an array of ids; `pending_unsaid`, if present,
  is an array of worker names by P/03.2 N1.4 without a readable counter. `safe` is computed by N1.2, not by the emptiness of
  `would_strand` — without modelling the placement: all units of the workers of this server and all unplaced units
  of the subsystem. The units of a worker are the union of its assignment (`<sub>/workers/<name>`) and `status[].id` of its heartbeat: an empty
  `status` with assigned units does not make the server empty (reconciliation of python and go 2026-10-18); conversely, an empty assignment with a nonempty status does not make it empty. An id occurring in both is counted once per worker; `units` is the sum of these worker union sizes. Without an active drain the server set is empty, the counters are 0, `safe: true`;
  the probe of the unplaced units can still give a non-empty `would_strand`.
  The keys of the two maps coincide and correspond to the visible subsystems; the common `safe` is determined by all
  subsystems, not only by the visible ones, so that hidden units do not allow switching the server off.

If the needed read/write of the store is not confirmed, the operation returns 503 `{detail, error: unavailable}`;
the read outputs (`GET /drain`, `GET /schema`, `GET /unplaceable` — `workers_live`) on a non-answer in the read of observations (heartbeats, door rows, holds, labels, their listing) are
`lapse` of the observation contract, the answer by the memory of the last read version with its age; 503 — only if the source was not
read even once since the start and the answer would assert emptiness or zero; writes and admissions (`PUT /schema` step 3, `POST /drain`, `POST /servers/{server}/decommission` — C06-PULSE-LAPSE-503-02) —
only by the reads of their own pass: a non-answer — 503, no write; required reads that are not observations (the row `platform/schema`,
the rows of units and tables) — 503 (C06-PULSE-LAPSE-503-01, the Architect's decision of 2026-10-29);
on an unknown outcome of a write the client first re-reads the state or repeats the request with the same `Idempotency-Key`. `busy` and `denied` have separate reasons of chapters 6.3
and 6.5 (N4). The codes and bodies of the common refusals are described at each operation of the lesson contract. The operational 404 differs from
`NoRoute`: at a server — `{detail, error}`, at an unplaced unit — `{reason}`.
The decommission refusal 409 contains `{detail, error: "server answers", server, may_confirm_gone}`;
`may_confirm_gone: true` is allowed only for a never-heard resource and in the absence of fresh
evidence of a worker/slot/resource. With a live server `gone: true` does not bypass the refusal: any fresh evidence —
409 with `may_confirm_gone: false`, and `gone: true` does not change it. The freshness of evidence is «heard within the last LOST_AFTER»
of [the observation contract](../../common/contracts/observation.md) (N3 «decommission_server»).

### `Platform/06-console/spec/06.8-console.norms.md` P/06.8-R006

old-sha256: 62ca3669ed658b6e5b9a481f511d57fbd4224577371fe4e0072ef142bd5386e1

<!-- req: P/06.8-R006 -->

The constants `FOLDER_NAME_MAX`, `FOLDERS_DEPTH_MAX`, `FOLDERS_PER_UNIT_MAX`, `FOLDERS_MEMBERS_MAX`, `FOLDER_ROW_MAX`, `FOLDERS_REAP_EVERY`, `FOLDERS_TRIES` are declared by [forms/runtime-constants.tsv](../forms/runtime-constants.tsv); the meaning and the dependent bounds remain this section.

`FOLDER_ROW_MAX` is a row-weight bound, not a serialized request-body bound. Every actually mandatory deletion request (target, done and other claim/auxiliary requests, separately) fits the store's actual entity-body ceiling B inclusively: compact JSON, UTF-8, required escaping, every metadata field and delimiter, plus the actual final LF. HTTP framing is excluded. All full keys, CAS/index/id/deadline strings/numbers, membership/gone rows, complete prepared unit/claim rows and guards are counted; auxiliary internal rows have no exemption from this ceiling. A FOLDERS_PER_UNIT_MAX*FOLDER_ROW_MAX items sum does not prove this obligation.

The profile covers states of the current writers, with these same reader limits; arbitrary states of older writers are outside its domain (ADR-0129 addendum (12)). This does not establish the full catalogue/descriptor proof or a sufficient B, and does not claim execution of recovery.

The accepted sufficient finite profile is checked **statically at installation and process start**, by [P02.3 N3](../../02-installer/spec/02.3-installer.norms.md#internal-finite-deletion-profile-adr-0127-p06-c2). The internal typed form is [`finite-profile.schema.json`](../../02-installer/forms/finite-profile.schema.json). B is actual Status.max_body, V is actual Status.max_value, F is FOLDER_ROW_MAX; no default is substituted. H bounds all encoded metadata after removing put items; each put is assigned once to a proved unit/tombstone, claim, three-field folder or empty-map category. Full finite metadata/multiplicity proofs give, for each packet:

`H + (n_unit+n_claim)*(12*V+7) + n_folder*(6*F+19) + 2*n_empty + LF <= B`.

The 12V+7 bound counts worst string escaping and every field, 6F+19 uses the folder's three fields; H includes deletes, all guards and framing inside the JSON entity. The FOLDERS_PER_UNIT_MAX*n_unit folder expansion is not a bound for arbitrary member-list replacements or mixed batches: their permitted consequences need their own complete packet/multiplicity/category proof. Every other nonempty auxiliary family is counted by an explicit proved weight category. Unbounded/missing metadata, a missing packet/proof, or any bound>B refuses the profile before any installation write, `refused:form`; exactly B is admitted. This is not per-mutation admission, a new DELETE refusal or a dynamic bypass. A conservative profile can require a much larger B than the store default declared by its -max-body form row; item weights alone cannot make deletion available. Existing caller batch refusals remain refusals of the whole batch, not a substitute for the static deletion obligation.

[`deletion-body-witnesses.json`](../forms/deletion-body-witnesses.json) records codec entities 1048575/1048576/1048577, an extra LF and the same payload's ASCII-escaped encoding. The padded boundaries explicitly use V=1048576, not the default 524288. Our escaping packet is 1380972 bytes, not the reviewer's 1380980; its 450000-quote unit fits the default row ceiling. These are byte witnesses, not store execution or successful installation of a finite profile. The separate P02 profile witnesses exercise the sufficient bound and reject incomplete proofs; actual full production descriptors remain an implementation duty.

The reader and writer of `platform/folders` and `platform/memberof` use the same limits declared in each family's `$defs.writer`: the family schema applies that definition through root `allOf`. Check the complete decoded list before a procedure uses it. A list beyond its limit makes the whole row unreadable and follows the existing family outcome; no prefix is accepted and no list is shortened. This applies to the reads of R013, R014, R016 and R018. No separate rule for an older state applies (ADR-0129 addendum (12), Z-10).

<!-- families:begin -->

### `Platform/06-console/spec/06.8-console.norms.md` P/06.8-R013

old-sha256: 007dbfe1edecfcc79057a63738b33e565eed59a096ff8d55bda354e1dd2bdf3e

<!-- req: P/06.8-R013 -->

```
1. form: body, fields, members → 400 bad folder, field; parent in the body → 400 bad folder, field /parent; If-Match and key → as in chapter 6.1
2. a key is present: the claim
3. chain(id): none, tombstone → 404 no such folder; unknown → 503 unavailable
4. rights over the folder → 403
5. If-Match is present and ≠ the index of the row → 412 folder moved
6. name and members coincide with the row → 200 with the current row: there is no write, the index does not change (the version promise)
7. member list: a repeated reference → 400 bad member, field /members/<i> of the second occurrence; members > FOLDERS_MEMBERS_MAX → 400 too many members, field /members
   for each added U (in the order of the body):
     U not by the reference form; the subsystem outside the catalogue; <rows> ≠ unit.rows; no display.tree.folders; the membership key not by P/01.1 → 400 bad member, field /members/<i>
     read the row of U: none or deleted → 400 bad member, field /members/<i>; the read is not confirmed → 503 unavailable
     read memberof(U): unreadable or not confirmed → 503 unavailable; already FOLDERS_PER_UNIT_MAX folders → 400 too many folders, field /members/<i>
   for each removed U: read memberof(U) the same way
8. rights to the added and the removed U — «folder rights» → 403; a removed U needs no read of its row if the may input does without it (the may contract)
9. batch: writes: the folder row cas the index of step 3; memberof of each added — put, the new folder at the end of the list, cas (no row — "");
                  memberof of each removed — put without F, and if F was the only one — delete, cas; the done claim with cas of its own version, if a key is present
          guards: the rows of the ancestors of F by the indexes of step 3; the row of each added U by the index of step 7
10. succeeded → journal folder.written {id, name?, added, removed, user, addr} → 200 with the new row
    412 guard on an ancestor → 412 parent moved, without a field; nothing is written
    412 guard on a unit, 409 conflict on memberof → from step 7 anew, at most FOLDERS_TRIES times, then 503 store unavailable; the unit is gone — step 7 answers 400
    409 conflict on the folder row: If-Match is present → 412 folder moved; absent → from step 3, at most FOLDERS_TRIES times
    413 → 413 row too large (the row weight > FOLDER_ROW_MAX or the store ceiling) | batch too large
    unavailable, ambiguous, no answer → 503 store unavailable
```

The row weight `FOLDER_ROW_MAX` is checked before the batch on the prepared row: `413 row too large`. Liveness is checked only for the added members. A dangling member that remains in the member list
gives no refusal: it comes into the body by a read, and a `400` on it would break a `PUT` of the name until the reaper removed the member.

The stored folder in step 3 and every membership in step 7 are read with the complete family check, including the `$defs.writer` limits. An over-limit row is unreadable before the difference or the no-change comparison is used; step 7 keeps its existing unreadable outcome. Removing elements is not a way to admit an over-limit stored row.

**A new member goes to the end of the folder's list** for the writes of the batch door; in `PUT` the body sets the order.

### `Platform/06-console/spec/06.8-console.norms.md` P/06.8-R014

old-sha256: df6f934c50d179200d73ec397a959e3ebc48eace0b3aaed65c11b245875d8529

<!-- req: P/06.8-R014 -->

```
1. If-Match and key — the form; a key is present: the claim
2. chain(id): none, tombstone → 404 no such folder; unknown → 503 unavailable
3. rights over the folder; role rows on the subtree → 403 («folder rights»)
4. If-Match is present and ≠ the index of the row → 412 folder moved
5. for each member read memberof: not confirmed → 503 unavailable, unreadable → rewrite by the rule below
6. batch: writes: the folder tombstone cas of step 2; memberof of each member: put without F, or delete if F is the only one, cas; no row or F not in it — the member is skipped; the done claim
          guards: the rows of the ancestors by the indexes of step 2
7. succeeded → journal folder.deleted {id, user, addr} → 200 {deleted}; conflicts and 412 — as «edit folder» step 10
```

The devices remain: a folder does not own units. The batch does not touch subfolders: from this index they are unreachable, the reaper removes their rows and membership. An unreadable membership row is removed in the batch by `delete` with `cas`: the deletion
of the folder does not lose the unit, and such a row has already broken the link invariant. A membership beyond FOLDERS_PER_UNIT_MAX is this same unreadable row: delete it with cas of its read version, rather than decoding a prefix or writing a shortened list.

### `Platform/06-console/spec/06.8-console.norms.md` P/06.8-R016

old-sha256: 7e5bd25b9421301d686550189bdc9cf978a6b508d2ac7639babc8ebfe194f59a

<!-- req: P/06.8-R016 -->

An insertion into step 2 «delete» of chapter 6.1 and into `delete` of the procedure «batch» of chapter 6.1. It concerns the subsystems with `display.tree.folders: true`; for the others the writes are as before.

```
a. read memberof(U):
     no row           → into the batch: the guard {memberof(U), ""}: a folder to which U was added after the read refuses the guard
     the read is not confirmed → 503 store unavailable, the row is unchanged
     unreadable       → into the batch: delete memberof(U) cas of the read version; do not touch the folders, the reaper removes the member
     reads            → for each folder of the list read its row:
                          no row or a tombstone → does not enter the batch; a subfolder under a deleted branch is not considered live, but its member is removed by the same batch if the row is live
                          the row is live → put members without U, cas of its index
                        into the batch: delete memberof(U) cas of its index
b. write — the batch: the unit row with cas (and the claim guard, if a key is present), the rows of step a
c. 412 guard, 409 conflict on the rows of step a → from step 1 «delete» anew, at most FOLDERS_TRIES times, then 503 store unavailable, the row is unchanged
d. journal: unit.deleted of chapter 6.1 and folder.written {id, removed: [U], user, addr} for each folder
```

The complete family check precedes the branches of step a. Membership beyond FOLDERS_PER_UNIT_MAX follows its existing unreadable branch: delete it with cas of the read version and prepare no folder writes from its contents. A folder beyond FOLDERS_MEMBERS_MAX is likewise unreadable and uses the existing whole-row family outcome, not the live-row branch. No new refusal is introduced.

This procedure neither reads nor guards the chain of ancestors: removing a member from a folder under an ancestor being deleted bothers no one, and chain guards would give a unit that lies in someone else's folder
a false refusal. The version of the folder changes together with the member list, because the folder row is written by the same batch. A deletion of a unit past the door (the controller by `ends` and `delete_after`, the worker by `worker.deletes`, P/06.1 N1)
does not do this procedure: the member dangles until the reaper. There is no second writer of the family: the controller does not write rows `platform/*`.

### `Platform/06-console/spec/06.8-console.norms.md` P/06.8-R017

old-sha256: 35f4616aa4efd868f54d47a9e0aa6bad30562fd8f58102d273879ba683154858

<!-- req: P/06.8-R017 -->

An insertion between steps 6 and 7 of the procedure «batch» of chapter 6.1. Refusals — the words of N4, the same order: the rows in the order of `writes`.

```
1. folder row: the form of fields — only members → 400 bad batch, field /writes/<n>/fields; repeat, number of members, weight — as «edit folder» step 7, field /writes/<n>/fields/members/<i>
2. the folder row read: none → 404 no such folder, tombstone → 409 folder gone, field /writes/<n>/key
3. the difference of the member list: the added U and the removed U relative to the row read
4. there are added ones: the chain of ancestors: none, tombstone → 404 no such parent, 409 parent gone, field /writes/<n>/key; unknown → 503 store unavailable;
   a guard for each row of the chain is in guards → otherwise 400 no chain, field /writes/<n>/key; the store checks the index
5. only removals: step 4 does not run
6. for each U — one row memberof(U) in writes, and its folders equals the one read without non-live folders (the chain of each; «unknown» → 503 store unavailable), minus all folders of the batch where U is removed, plus all folders of the batch where U is added → otherwise 400 no membership, field /writes/<n>/key
   the caller does not see a non-live folder (`?member=`), therefore it is absent in the result: the reaper removes the link of its row
   this way one batch moves U and sets its folders whole (the folderIds step)
   a memberof row without its folder row → 400 no membership, field of this row; folders in total > FOLDERS_PER_UNIT_MAX → 400 too many folders
7. added U: subsystem, table, declaration, membership key — as «edit folder» step 7
   U is created by this batch → it fits; otherwise it is live and its row is in writes or guards → otherwise 400 no chain, field /writes/<n>/fields/members/<i>
8. rights — «folder rights» by the difference; a memberof row has no check of its own: the folder row judges it
```

The caller reads and places the chain and the guard: the console only checks that the guards are there, because the indexes were read by the caller, not by the console. The row of a unit created by the batch passes the right of creation with the input `chains` from this same batch.

`delete` of a unit in the batch door puts the rows of «unit deletion by the door» into the same batch itself. These rows are not counted in the caller's `BATCH_WRITES` and do not enter the caller's incoming body; they fully count in the serialized entity of the emitted store request and its static profile bound (N1.3). If the caller has named the folder row of the unit himself, the coinciding rows are not duplicated:
the explicit body must agree with the mandatory deletion effects; the console adds only missing consistent rows. At the existing reconciliation after the gate and CAS comparison, determine these effects from the rows already read by the procedure. An explicit folder body that still contains a deleted U, or an explicit memberof put that restores its membership, is `400 no membership`, with `field: /writes/<n>/key` of that conflicting explicit row, before any target data write. Do not rewrite the caller's body silently. The existing response memory remains in effect.

An explicit folder without U and an explicit memberof delete are consistent; a missing memberof delete is supplied by the ordinary deletion procedure. Reuse each consistent explicit key once and add only missing automatic consequences. Keep the current full row-weight/batch-size accounting, CAS and guards; rights exemptions apply only to automatically added consequences, while explicit rows keep their ordinary rights checks. The reconciliation does not list all folders or replace the existing unknown/unreadable-memberof procedure.

### `Platform/06-console/spec/06.8-console.norms.md` P/06.8-R018

old-sha256: 86f73015824c4cb980bef01ed9b57a4e03ae608fffdb409a5bf4a20b2edd4a05

<!-- req: P/06.8-R018 -->

A new job of the console reaper ([chapter 6.4](06.4-console.norms.md) N3): every `FOLDERS_REAP_EVERY`, outside the maintenance window. It runs on every console: `cas` does not let two passes write the same thing twice.

```
1. list platform/folders/; not confirmed → the pass is over
2. an unreachable row (no tombstone, the chain «none» or «tombstone»): batch: a tombstone of the row cas of its index; memberof of each member — as «delete folder» step 6
3. a live folder, a member U, a confirmed read: the row of U is absent or is a tombstone:
     batch: the folder row without U cas of its index; memberof(U) without this folder or delete, cas
4. memberof(U) is unreadable at a member of a live folder: rewrite it by the member lists of all listed folders with cas of the read version
5. the chain «unknown», the row unreadable, the read of U not confirmed → leave until the next pass
6. journal: folder.reaped {id, removed} for each changed folder; conflict → the next pass
```

The same complete reader check applies before steps 2–4. An over-limit folder is unreadable, so step 5 and the existing folder outcome apply; an over-limit membership uses the existing unreadable membership handling of steps 2–4. Step 4 still reconstructs from the full member lists, with the existing writer-form check: it neither truncates the reconstruction nor permits an out-of-form write. There is no special transition for an older state.

Step 2 need not remove bottom-up: the tombstone of the parent already makes the descendants unreachable in any order. Step 3 is the only write that removes a member without a person's will: the `index` of the folder changes
on the next pass after a deletion past the door. Until the pass a read gives out the member as is.

**Races.**
- An edit of the member list against the deletion of a unit, the unit deleted first: the unit guard in the batch of the edit refuses, step 7 sees the tombstone, `400 bad member`.
- An edit of the member list against the deletion of a unit, the edit first: the deletion batch carries `cas` or a guard of the absence of the membership row. The new membership refuses the batch, the procedure re-reads the row and removes the unit from the new folder too.
- Two edits of different folders with one unit: both write one membership row, `cas` lets one through, the second goes from step 7.
- A folder write against the deletion of an ancestor: the chain guard, `412 parent moved`, nothing is written. The ancestor deleted before the read — `404`.
- Creating a subfolder against the deletion of the parent: the parent's guard. The folder does not appear under a deleted branch.
- The reaper against an edit: `cas`, the loser waits for the next pass.
- The index of the chain also changes from a rename of an ancestor: a `PUT` of the ancestor's name gives a parallel write `412 parent moved`. This is a false refusal on a rare edit; the caller re-reads and repeats with a new key.
- Two instances of `POST` with one key: the claim of chapter 6.1, the second gets `409 in flight` or the saved answer.

---

### `Platform/06-console/spec/06.9-console.norms.md` P/06.9-R012

old-sha256: 49c5cdd013246e053de862e920235642c4316adf0be695583cec27fbf4f2e8e2

<!-- req: P/06.9-R012 -->

1. If the manifest has not declared operations, return `404 no operations`.
2. Form: if the body is not a JSON object, return `400 not_json`; if the fields, id, items, root or memory are not in form, return `400 bad operation`, field.
3. Right (N2): at a table without service — `edit` on the table, at service — a live ticket from the leaf of the subsystem's role. If the session is not a person with a token (no jti), return `403 denied`: the steps go by the person's right, and without a token there is nothing to bind.
4. If items exceed the limit, return `400 too many steps`, field `/items`.
5. List the unfinished operations. If there are ≥ OPS_ACTIVE_MAX of them, or the author has ≥ OPS_PER_PERSON_MAX, return `400 too many operations`, field `/items`; if the read is not confirmed, return `503 unavailable`.
   The limit is judged by the read, not by the batch: two simultaneous acceptances can exceed it by one.
6. Write the step rows `cas ""` in order; the secret is sealed by chapter 6.2 with the key of this row.
   On conflict: if the operation record exists, return `409 exists` and do not touch the step rows; if there is no record (the tail of a break), return `503 store unavailable`; the bodies without a record will be removed by the reaper.
7. The acceptance batch, the order of writes:
   - memory, if any, with its cas (the check of the table row is its door, the right is the rule of the table);
   - the record `{by, jti, kid, iat, exp, created_at, state: running, paused: false, expired: false, cancel: false, total}` `cas ""`;
   - the counters at zero `cas ""`;
   - `<sub>/opbusy/<root>` `{operation: id}` `cas ""` for every distinct root.
8. When it is done: the journal `operation.accepted {id, by, total}`, return 202.
   - On 409 conflict on the record, return `409 exists`; remove the step rows by cas.
   - On 409 conflict on memory, return `412 row moved` {key, index}, field `/memory/cas`; remove the step rows: another executor of the same key has already accepted, the caller reads the memory.
   - On 409 conflict on opbusy, read the row; return `409 root busy` {operation, root}, field `/items/<i>/root`; remove the step rows.
   - If removing the step rows failed, or on a break, the reaper will remove them: the refusal does not depend on it.
   - On unavailable, ambiguous or no answer, return `503 store unavailable`; do not remove the step rows: the batch may have landed.

The reconciliation of `expectedVersions` is made by the subsystem before the call of the door: it is its knowledge. Between the reconciliation and the acceptance batch there is a window: if the target changed in it — 202 all the same, and the step then gets `fail` by a version mismatch. This is a limitation; it is written in the lecture.

The memory row goes in the batch by the same technique as a row of the memory table in the step batch: a lost 202 on a repeat finds the memory and gives the same operation; the steps are not executed twice.

### `Platform/06-console/spec/06.9-console.norms.md` P/06.9-R017

old-sha256: 1fc6323ae722ada061c90afcbe7542bde32eef29326290299e03ece1e627eb48

<!-- req: P/06.9-R017 -->

1. The form of the path; the manifest; the row of the record: absent, unreadable → 404, 503 (the outcome of the family).
2. Right (N2).
3. If state: done, return `409 operation done`.
4. Pause: `paused: true`; resume: `paused: false`; cancel: `cancel: true`; a request of the author is also a rebinding. If the value is already such and there is no rebinding, return 200 without a write.
5. Write the record with cas; on conflict, retry from step 1 at most OPS_CONTROL_RETRIES times after the original pass; after these retries return `503 store unavailable`.

The current step plays out: the flag is read before the next step. `cancel` also cancels waiting on pause. A human pause is not removed by rebinding: `expired` is removed, `paused` remains — the operation waits.

### `Platform/06-console/spec/06.9-console.norms.md` P/06.9-R019

old-sha256: bf772365f4de78b9a16b23f863e7ca752d03d11aa56ecd2dd93867292f9dc595

<!-- req: P/06.9-R019 -->

1. Form; manifest; the row of the record; right — as at pause. If the session is not a person with a token (no jti), return `403 denied`: the record carries jti, kid, iat, exp of the one who retries.
2. If the operation is not done, return `409 operation running`.
3. Take the steps of the former operation with the outcome fail, in order; if there are none, return `409 nothing to retry`.
4. A new operation: the author is the one who retries; retry_of: id; the step rows are copies of body and root; open the value of the secret and seal it anew: the AAD contains the key of the row. If it did not open, the former envelope goes into the row as is, and step 5 of the procedure gives the outcome fail not_run.
   expected of a copy := expected_version(i) in the former operation (N1.4), that is, the version at the moment of its execution.
5. Further — «accept» from step 4: occupancy, limits, memory.

A changed step expectedVersion is reconciled by that step and is not a retry-admission `412`. The separate memory-row CAS of the acceptance batch still gives the existing `412 row moved` with key/index and field `/memory/cas`; no acceptance effects land, and step rows are cleaned up by the acceptance procedure. A matching memory CAS permits 202; an unknown acceptance outcome retains the existing pending/cleanup rules. If the root has changed, the step is again `fail` by a version mismatch, and the person builds a new plan. Inside the new operation the chain of N1.4 acts as usual: a successful step over the root gives the version to the next one.

### `Platform/08-domain/spec/08.4-domain.norms.md` P/08.4-R006

old-sha256: eed79a9dac3be1a411d4c303cc3cf3812dfba5a326265be1565aaf8293460e65

<!-- req: P/08.4-R006 -->

```yaml
domain/grants/<cluster>:  {doc: <JCS text {lines}>, revision}   # at the holder; <cluster> — a member name by the grammar of chapter 8.3
                                                       # (it need not be a member: grants are prepared before admission) or domain;
                                                       # in the path of the door — byte for byte, %-encoding is not decoded:
                                                       # m%31 — not a name, 400 bad name (added by the M11 reconciliation, P13)
  lines:       [line…] by (subject, cap, sub, scope) in UTF-8 bytes, no sub — the empty string, then until by number, without repeats by
               (subject, cap, sub, scope, until); until is compared by value: 0 and 0.0 are one line, a repeat (added by the M11 reconciliation, P7, P9)
  line:        {subject, cap, sub?, scope, until, by}
    subject:   a person's name (N1.1) | a subject of a name index (chapter 8.5 N1.7) | role:<role name> (N1.3a, up to 69 characters; the character : the grammar
               of a person's name does not let through, so a role name does not collide with a person)
    cap:       none | view | edit | admin      # none < view < edit < admin; none gives no permission, it occurs only on a role line
               # (ADR-0099 §1); on a line of a person or of an index key — out of form, 400 bad line
    sub:       a manifest name (the grammar P/02.1 N1.2 name) or platform; no field — the line applies in all subsystems and in
               platform; the presence of the manifest is not checked: grants are prepared before admission (ADR-0097 §1)
    scope:     * | unit:<sub>/<id> | labels:<label>[,<label>…] | folder:<id>   # labels — the labels alphabet Platform/common/contracts/labels.md, without repeats;
               # <sub> — a manifest name (P/02.1), <id> — by the identifier grammar P/06.1 N1.3; folder:<id> — the id of a folder P/06.8 N1.1
               # (32 lowercase hex digits); otherwise the line is out of form (at the door — 400 bad line; added by the M11 reconciliation, P10);
               # labels: on a role line — out of form (ADR-0099 §1, A2)
    until:     0 — no term; otherwise wall-clock seconds — the line applies while now < until; at the input more than three digits
               of fraction — rounding to thousandths from the decimal notation, half away from zero (as chapter 8.1 N1.4 round): the line
               is stored and compared rounded (the Architect's decision on the M11 reconciliation, P8); a positive until that
               would round to 0 this way is written 0.001 — the meaning «expired» is the same, 0 is only «no term» (the input of PUT and
               rewriting; the Architect's decision of 2026-10-29, C08-UNTIL-REWRITE-01)
               rewriting a row whole (an edit of another subject, removal of lines at deletion, reconciliation), the process domain is
               the writer: until of the remaining lines — in the writer's form of P/01.1 «Time in a row» (a JSON number, a fraction no longer than
               three digits) by the same rounding; a notation that only the reader accepted (a string, a longer fraction) is not
               carried over as is; the match by (subject, cap, scope, until) and by — after rounding (C08-UNTIL-REWRITE-01)
    by:        the name proven by the gate at writing; a line that matched a former one by (subject, cap, scope, until) keeps, at
               a write of the row whole, its by, a new one — the name of the writer; the match — by sub too
  rewrite:     rewriting the document inside the process (a person deletion, removal of role lines, reconciliation), the process carries a line of lines out of form
               over byte for byte rather than losing it; a whole write of an administrator (PUT) replaces the document with the sent one (ADR-0098 §2)
  writer:      the process domain — by the door of N2 of the domain console (chapter 8.0 N1.8; CAS by the read version) and by removing the lines of a person
               at deletion
  revision:    next to doc, not inside: chapter 8.0 N1.9 «Versions», +1 on every write of the row; the agent carries only doc, the form of the copy is the former one
domain/grants/domain: the grants of the domain door (the domain console and the process domain); no agent carries them. No fields sub, no scope folder:,
               no role lines — 400 bad line; the one exception is the manager line {subject: role:<R>, cap: admin, scope: *, until},
               R ≠ admin (N1.3c «manager»; ADR-0097 §1, ADR-0098 §2, ADR-0100 §3)
last_admin:    a proven administrator (ADR-0100 §2) is a person whose: row domain/users reads; disabled = false; expires = 0;
               name is not in domain/disabled; there is no mark domain/deleting/<name>; there is an unlimited (until = 0) admin assignment — directly or
               through a readable group — or a direct line {cap: admin, scope: *, until: 0} in domain/grants/domain. An unreadable
               domain/roles/admin — there are no administrators by the role. Only unlimited ones: an administrator with a term of the account or
               of the assignment does not count, otherwise the domain would lock itself on expiry
               the check of the door — after every edit that can remove a proven administrator: a person (disabled, expires,
               DELETE), a group (members, DELETE), the role admin (assigned), domain/grants/domain; not a single one — 409 last admin, nothing
               written; the batch door judges the final state of the batch; an unreadable person row (N1.1 unreadable) «exists» for
               the reconciliation of grants but does not count as an admin: one cannot log in under it (N1.2 check — 503) (C08-LAST-ADMIN-UNREADABLE-01)
               guards of the proof: a write that passed the check carries in the batch P/01.1 (op: batch, guards) the guards of the rows that prove
               at least one remaining administrator: his domain/users; domain/disabled; the absence of domain/deleting/<name>
               (index ""); domain/roles/admin and the row of the group through which the assignment goes, or domain/grants/domain for a direct
               line; the row being written does not go as a guard (its condition is cas). A conflict of a guard or of cas — the whole check from the start on
               a fresh read, at most GUARD_RETRIES; exhausted — 503 {error: "unavailable"}
               without an administrator: there can be no proven ones left after a restore (P/08.8 N1.8) or an anomaly; the domain works, the journal
               domain.no_admin once per pass; the way back is the command grant-admin (N1.9)
GUARD_RETRIES: forms/runtime-constants.tsv
carry:         the holder's answer to the agent (chapter 8.3 N1.5) carries in sealed the fields grants and roles (the form — the domain envelopes contract
               «Content of sealed»; analysis of review of stage A 8–10, № 12): grants — the row domain/grants/<member> without the lines whose subject is in domain/disabled
               (ADR-0051); roles — the table of this member, N1.3b. No row: the role admin has effective assignments — grants {doc: {lines: []}},
               otherwise no field. anywhere goes separately from grants, to a member without its own row too. The row does not read, the assembly did not converge or the table is over the limit — not «none»: in sealed instead of the fields goes held: ["grants", "roles"],
               «not sent, do not touch the copies»; the copy ages by step 4 of the right contract. The absence of a field without held still means «no row». For anywhere, confirmed absence omits the field and its held name; an unreadable summary uses held: ["anywhere"]. A failed or over-limit assembly leaves the former stored row untouched; if it remains readable, carry advertises its former digest and as_of, without freshening them. If the former summary cannot be read, carry marks anywhere held. roles always goes together with grants and only with it
# member_copy, holder_copy — the copy of domain/grants {doc, as_of} at a member and at the holder's cluster: written by the agent from the answer of its
# holder — P/09.1 N1.4 member_copy, holder_copy; at the holder's cluster until the first answer
# to the agent there is no row — no rights, the entry is break-glass (N1.6)
anywhere:      the row domain/anywhere {doc: {<person>: <until>}, as_of}: who has an effective line cap ≠ none in any domain/grants/<member>, direct or through
               a role and a group; until — the largest, 0 is the largest; the disabled do not enter; written by the holder's pass on a change and no less often than FRESH_EVERY: as_of of the summary lives as as_of of the grants copy; the copy at a member — the agent from the field
               anywhere of sealed; at the holder's cluster the row is written by the process domain, the agent does not touch it; an unreadable row domain/grants/<member> or a role only
               narrows the summary. It serves as the entry (D-8), it gives no right to write (the right contract step 6). A copy older than as_of + GRANT_LIFETIME — as no field
carry:         in the answer only {as_of, sha256} of the summary; the body — GET /api/anywhere/<member> on a change; a camera does not hold the row: the entry by anywhere does not apply at it, a foreign person does not enter through a camera: a limit (ADR-0113)
               sha256 — lowercase hex SHA-256(UTF-8(JCS({doc, as_of}))) of the complete JSON value of the 200 body of GET /api/anywhere/<member>; as_of is included. The digest is not of doc alone or of the raw HTTP bytes (G09-ANYWHERE-HASH-01). The HTTP body is the raw-string form `HolderAnywhereBody` of the owner OpenAPI: hash before parsing the internal doc or converting its body time. The sealed advertisement keeps its existing type and meaning.
ANYWHERE_MAX:  forms/runtime-constants.tsv    # bytes of JCS doc, its own row: the summary does not touch the grants copy; larger — the row stays the former one, the journal domain.anywhere.too_large once per pass
GRANT_LIFETIME: forms/runtime-constants.tsv      # s — a member's copy older than as_of + GRANT_LIFETIME gives no rights
unreadable:    a row that does not read gives no rights; a line of lines that is out of form is skipped at a direct group and counted
               as diagnostics, the others apply; the parse of such a line is in two stages: the subject read as role:R — the group R is incomplete (if
               sub read too — only in this sub), the subject did not read — all role groups of the document are incomplete; the sign reaches may
               (the input unread of the right contract; ADR-0099 §2)
```

The labels alphabet — the [labels alphabet contract](../../common/contracts/labels.md); the identifier grammar —
[P/06.1](../../06-console/spec/06.1-console.norms.md) N1.3; the manifest name — [P/02.1](../../02-installer/spec/02.1-installer.norms.md);
envelopes — the [domain envelopes contract](../../common/contracts/domain-envelopes.md) «Content of `sealed`».

The revocation window at a member without connection is two limits, separately (the Architect's decision on R41-13 of run 41):
- **an already issued token** of a disabled person or a revoked one — `TOKEN_LIFETIME + TOKEN_SKEW` = 960 s from issue;
- **a grant** removed at the holder, at a member without connection — `GRANT_LIFETIME` (a day) from `as_of` of the copy: a person who was not
  disabled logs in again and with a new token uses the former copy while it is not stale.

The numbers are declared in advance (M12A/04 step 5).

### `Platform/08-domain/spec/08.4-domain.norms.md` P/08.4-R017

old-sha256: 48eb6deb89794dec2b4f4dfa0c9415b55cdb9790c061968c58af46c92cfd8b9b

<!-- req: P/08.4-R017 -->

```
1. the body is larger than 1 MiB                                    → 413 too large
2. the token (token of the domain token contract, expect {kind: person, cluster: null}) and may by domain/grants/domain → 401 / 403 {error: denied}; nothing to check with — 503 unavailable (N1.5)
2a. the headers and the repeat memory (chapter 8.0 N1.9; a body that is not a JSON object — 400 bad body here) → 400 / 409 / 422 / the former answer
3. the body is not in the form of the door                          → 400 bad body
4. the name is not by N1.1 (POST)                                   → 400 bad name
5. the password is shorter than PASSWORD_MIN (GLASS_MIN at break-glass) → 400 bad password
5a. POST: the mark domain/deleting/<name> stands                     → 409 exists (the mark — before the name checks;
    added by the M11 reconciliation, P3)
5b. a manager (N1.3c): PUT, DELETE — the status of the target target → 403 admin only / 503 unavailable
6. the name checks (chapter 8.5 N1.7)                               → 409 name taken / 503 names unknown
7. POST: the person exists or the mark domain/deleting/<name> stands — 409 exists; PUT, DELETE: none — 404 no such person; the person row
   exists but does not read — PUT: 503 unavailable, not 404 (the edit needs the read content; the unknown is not «none»);
   DELETE deletes an unreadable row too — the way to remove a spoiled one (sc. 13 of the acceptance 8.4; C08-PUT-USER-UNREADABLE-01, -02)
7a. POST: there is a line with subject = <name> in domain/grants/* (a grant of a former subject without a name that the reconciliation has not removed yet) or the name stands in
    members of a group or in assigned of a role (ADR-0098 §5) — 409 exists: the name is free only after the removal; a grants, group or role row does not
    read — 503 unavailable (P1) (C08-GRANTS-ORPHAN-01)
7b. PUT, DELETE of a person, PUT break-glass: If-Match is not equal to the version of the row (chapter 8.0 N1.9; break-glass without a row — revision 0) → 412 revision moved
8. last_admin (N1.3); expires ≠ 0 at the last unlimited one — too   → 409 last admin
8a. ROLES_TABLE_MAX (N1.3b)                                          → 409 roles table too large
9. write the row (CAS by the read version, revision + 1, the guards of N1.3 last_admin and N1.3c target); disabled or expires — then domain/disabled; DELETE: write the mark
   domain/deleting/<name> → delete the person row → remove the lines subject = <name> in all domain/grants/* (CAS) and the name from members of all groups and assigned of all roles (CAS) →
   write done: true into the mark, its term is removed by the reconciliation; a group or role row does not read — 503, the mark stays, the reconciliation finishes it; the answer — after the write of done (log of cammeta-go, M11-09 № 1; the Architect's decision; C08-DELETED-NAME-HOLD-01); a CAS conflict of a grants
   row — reread it and repeat at most three times (as step 6 «grants»); exhausted — 503 {error: "unavailable",
   detail: "the grants kept changing; the deletion is finished by the next pass"}, the mark stays, the grants rows
   are finished by the reconciliation below (analysis of review of stage A 8–10, № 38)
```

With a key, the target write of step 9 (chapter 8.0 N1.9 `write`) is the person row or the row of the break-glass account; for `DELETE` — the write of `done: true` into the mark: the answer names `grants_changed`, and this write is the last one. `domain/disabled` goes after the batch, as without a key: the divergence is finished by the reconciliation below.

A break of step 9 is reconciled at start and at each holder pass. Rebuild `domain/disabled` by the readable person rows as before. For each person deletion mark, remove the matching grant lines and the references in group members and role assignments by their read versions; an unreadable input, an unknown read/write or an unfinished CAS retry leaves the mark for the next pass, without claiming completion. The person row is never deleted by reconciliation. A still readable person row (including scenario 09) keeps that person without the removed grants: after cleanup remove the directly written or interrupted mark; a repeated `DELETE` finishes deleting the person.

If the person is confirmed absent and cleanup is complete, a readable `at` retains the mark until `at + TOKEN_LIFETIME + TOKEN_SKEW`, whether `done` was already true or completion is recorded now. At equality the hold is over. A missing or unreadable `at` is a mark without a timed hold, not a synthesized current time: after cleanup use the existing removal path of scenarios 09/10. Unknown or unreadable person state cannot prove either branch: retain the mark and retry the existing reconciliation. A key outside the person/role grammar keeps the existing dropped-mark path and log. The pass does not wait for the name indexes to clean a deletion mark; the separate orphan-subject reconciliation still waits for its own full inputs.

A role mark `domain/deleting/role:<name>` uses its separate existing recovery branch (N3 roles): delete the role row if it remained, remove the grant lines with `subject = role:<name>`, then delete the mark. The role row is not preserved by the person-row exception above. Use the current read-version CAS and retry rules. If required cleanup inputs do not read, existence or version is unconfirmed, a write outcome is unknown or cleanup remains unfinished, retain the role mark for retry; this does not add a payload-read precondition to the existing role-row deletion. While its mark or a corresponding grant line stands, creation of that role name remains 409 `exists`. There is no person-token hold for a role mark, and its writer items are exactly `{}`: no `at` or `done`.

A subject without a name (C08-GRANTS-ORPHAN-01; the Architect's decision of 2026-10-29 on the request of VMS, analysis of V/03, question 2). By the same pass, after the name indexes of the pass (chapter 8.5 N3
«assembly of a book»), the process `domain` removes the grant lines in all `domain/grants/*` whose `subject` is not a person of the domain (there is no row
`domain/users/<subject>`) and not a key of any name index — only when all indexes are known (chapter 8.5 N1.7; a catalogue without
books with `domain.names` — all are known and empty) and the list of people is read: the indexes of this pass are not built (a failure of a part of the pass, chapter 8.1 «Races»; the window after a taken term, chapter 8.5 N1.3), an index is not known, the list of people or an index row is not
read (the store did not answer) — the reconciliation of this pass does not look for subjects without a name (P1, C08-PASS-PART-02). The person row exists but
is unreadable — the person exists: his grants are not removed. A grants row does not read — it is skipped, the reason goes into the journal. The removal is
CAS of the grants row by the read version; a conflict — reread and repeat at most three times, the rest — by the next
pass; the journal without values. While a line of such a subject stands, the name is taken for `POST /domain/users` (step 7a of the people door):
a new person with this name does not get the grants of the former subject. Subjects that the norms remove themselves (the mark `domain/deleting/`) — as before.

New kinds (ADR-0098 §5). By the same pass the process removes the grant lines `role:R` if there is no row `domain/roles/R`; the elements of `members` and
`assigned` with a person who does not exist, and of `assigned` with a group that does not exist. The rule of the pass is the former one: the lists of people, groups and roles
are read whole and successfully — otherwise this pass looks for nothing (P1); a row exists but is unreadable — «exists», nothing is removed; CAS,
three repeats, the rest — by the next pass; the journal without values. **While a restore or a move of the domain is not finished, the reconciliation of the new
kinds removes nothing**: an empty list after an incomplete restore is not a ground.

**Expiry** (ADR-0098 §3, ADR-0100 §2). At every pass the process writes into `domain/disabled` the names with an expired `expires`, except the case: after that
not a single proven administrator would remain (N1.3) or the proof is unknown (unreadable rows). Then the person stays
enabled, the journal `domain.user.expiry_kept {name}` once per pass. A proven administrator is unlimited, so in the normal state
the rule does not fire: it is a protection against an anomaly.

**Reconciliation of the `admin` role** (ADR-0100 §1). The pass writes `domain/roles/admin` only at a confirmed absence of the row and a non-empty `domain/users` (before `first-admin` it does not write the row); it does not
touch an unreadable row, the journal once per pass. Creating it, it assigns the role once (`until: 0`) to each person with an effective unlimited direct line;
it leaves the line to him. No proven administrators — the journal `domain.no_admin` once per pass.

### `Platform/08-domain/spec/08.5-domain.norms.md` P/08.5-R004

old-sha256: 542f7aca68eb7a600cf658e342cea39806b88a7911dacfe9607c87d1a62bc133

<!-- req: P/08.5-R004 -->

```yaml
carry:        the answer of the holder (P/08.3 N1.5) carries the books in sealed (the envelope m1) in the field books — the form: the domain
              envelopes contract «Content of sealed» (analysis of review of stage A 8–10, № 12)
mask:         the value of a book secret gets neither into a door (the book door of the cluster console, the OpenAPI of lesson 6), nor into the log, nor into the view
              (P/06.2 N1.4)
```

A book `to: "*"` goes not into `sealed` and does not reach a member without a request (ADR-0113 addendum (11) item 1). A reader declares `domain/<sub>/<book>/` in `worker.reads` and puts the request `domain/book-want/<sub>/<book>/<part>`; the agent holds copies of these parts under the same key `domain/<sub>/<book>/*/<part>`, the copy is grown by the rules of the member, not by the domain. The publication names `book_parts` — the versions of what it holds, and `null` for a request without a copy, `carry.book_stale` — what is stale or has appeared: the comparison is as for `members_rev`, a version for the whole book would raise all readers on every change. A wide member carries a window of `BOOK_PARTS_SHOWN` parts by round, only they are judged: the cost is constant, the lag of a wide member is minutes; after a takeover all parts are stale, 4096 with `BOOK_PARTS_PASS` per pass — about 43 min: a limit. A request lives by a term: the reader renews `at` once per `BOOK_WANT_EVERY` s while the part is needed, the agent considers it removed at `now − at > BOOK_WANT_TTL` s and removes the row itself: readers share the row of the part, so it is not for any of them to remove it. The agent takes it by the door `GET /api/book/<member>/<sub>/<book>[/<part>]` ([chapter 8.3](08.3-domain.norms.md) N2), without a part — the head; there are no secrets in them. Its owner HTTP forms `HolderBookHeadBody` and `HolderBookPartBody` carry raw KV strings under items, without decoding or normalizing their internal JSON; the family key and content rules stay unchanged. A reader puts a request on any cluster; the agent of the holder's cluster does not execute it: the keys are the same, the holder's row is read. A change of the term requires nothing from the reader: the rows of the former holder become copies, are judged through `book_parts`, rows without a request are removed by the agent. A reader puts requests at its start too: agent clocks that jumped forward remove requests at once, this is a limit.

The book row at a member (`member_row`: the elements as received, the secrets are envelopes of the member's ring; the writer is the agent; the cluster
of the holder has no copy: the holder does not send books to itself in `sealed` and reads its own book from the row
`domain/<sub>/<book>/<self>`, ADR-0074) — [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) (N1.4
`member_row`). The envelope `m1` — the [domain envelopes contract](../../common/contracts/domain-envelopes.md) «Envelope `m1`».

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R008

old-sha256: 623e34fc5adcc9f051d834436788f8329880346b648b6c389b49071786f36bc4

<!-- req: P/01.1-R008 -->
- The **reader** MUST accept the same form with at most three fractional digits as the current writer: `^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$`. Excess precision has the existing field/row unreadable outcome of that field, without rounding or truncation.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R010

old-sha256: a53f646524ceedf4faaa075eb0f310989cb3803507128ad4fd9ff9b0157cc31d

<!-- req: P/01.1-R010 -->
- A notation outside this form is a field out of form; the field rule determines the reader outcome. Its value is finite in binary64: overflow is also out of form. The reader has the writer's fraction bound. The R007 exception and own forms of R012 are not narrowed by this rule.

### `Platform/08-domain/spec/08.2-domain.norms.md` P/08.2-R004

old-sha256: 29597060dd09e00cc31fc801ca372e8d60d141efa2cedf3a1e607c800ae82213

<!-- req: P/08.2-R004 -->

The form of the row and of the set document (`row`, `doc`, `writer_forms`) and the rule «only forward» (`only_forward`) — the [domain key set
contract](../../common/contracts/keys.md) «The set `domain/keys`» (the owner is this chapter; review analysis of stage A 8–10,
№ 13 / decision 2). Here — the `rev` of the writer:

```yaml
rev:               an ordinary and a planned change (token key, book_seal) — max(rev of the set that the signer holds
                   + 1, whole wall-clock seconds of the signer); rev + 1 greater than the wall-clock seconds — the change waits until
                   the clock catches up with it: rev does not overtake the wall clock of the signer
  emergency:       an emergency change — after theft (N3) and a move without the former holder (chapter 8.8 N1.8) — max(the greatest
                   known rev + 1, floor(now) + TOKEN_SKEW + 1); known — the sets of the answers of neighbours and its own domain/keys,
                   checked by the root, including one not confirmed by its own term record (chapter 8.8 N1.8 step 5; C08-MOVE-UNCONFIRMED-KEYS-02)
  clocks:          premise: the wall clocks of the holders of the domain differ by at most TOKEN_SKEW; under it the emergency set is newer than any set that the former holder issued
                   (ADR-0074 addendum 7)
```

The set is what a member trusts without a connection: the token keys of the holder, the revocations and the book acceptance key. Without the set the member has no
domain (the gate [P/06.3](../../06-console/spec/06.3-console.norms.md) N1.3, N1.8).

The field of the view `domain/view.trust` (the set that the holder trusts: `rev`, the fingerprints of `root` and `book_seal` by N1.1) —
[chapter 8.1](08.1-domain.norms.md) N1.2a (P/08.1-11; moved there from this subsection, review analysis of stage A 8–10, № 21).

**Representability of an emergency revision.** Compute the candidate exactly before any publication. Its upper bound is the existing `common.pos53` bound of the [keys family](../data/keys.schema.json); neither operand may wrap, round or saturate. If the candidate is outside that form, no set, signing key, seed, term or member entry is written. The signer operation uses its existing nonzero refusal exit; the move uses its existing failed-restoration response, without publishing a partial change. Equality and `only_forward` checks, signatures and the term guard are unchanged.

### `Platform/08-domain/spec/08.2-domain.norms.md` P/08.2-R021

old-sha256: 88ffa228b0603fe47428aaf7d94e0569ea037211839d3fd01dfdd58dd9ebff57

<!-- req: P/08.2-R021 -->

```
1. the operator takes out the recovery file; the move of the holder — chapter 8.8 (POST /domain/move {stolen: true}); before chapter 8.8
   the change after theft is a signer operation over its own set on the same holder (steps 2–3 and 5, the rows of step 2 and the set of step 3 in one batch; the call — «Implementation
   decides» item 2), chapter 8.8 calls the same steps from the move
2. a new token key, issuing key and book acceptance seed — the rows domain/signer and domain/book-seal of the new holder; they are written by the batch of step 4, before it they live in the memory of the operation (Quint M13 N13, C08-SIGNER-BATCH-01)
3. the set: keys = {new} without until (there are no former token keys); current = new; issuing = [new serial];
   stolen_issuing = former revoked_issuing ∪ former issuing: nobody knows the moment of theft, a key that left by a move before the discovery would serve the thief as a source (ADR-0113 addendum (17)); thefts = former + 1 (none — 0; the theft mark for SET_GUARD, the domain key set contract «The follow set»; C08-GUARD-THEFTS-01);
   revoked_issuing = former revoked_issuing ∪ former issuing; revoked_members = former ∪ {the member key of the stolen
   holder — the Entry.key of the holder in domain/member-rows/<part> (chapter 8.3 N1.1), without it — the last one in its revoked_keys (a repeat, step 3a); without that too —
   a refusal, nothing changes (added by the reconciliation of M11, I4)}; book_seal = new; rev — emergency (N1.2 emergency): max(the greatest rev of the set at the reachable members + 1,
   floor(now) + TOKEN_SKEW + 1) → domain/keys
   # before chapter 8.8 (the same holder) the known rev is the rev of the set of the holder: the members hold its sets; the formula is the same
3a. the Entry of the stolen holder in domain/member-rows/<part>: key goes to the end of its revoked_keys, there is no field key any more (chapter 8.3 N1.1, limit 4 — chapter 8.10 N1.5);
   the key is stolen together with the machine, so the entry does not hold it, a copy with holder_member_key does not return it (chapter 8.8 N1.2), and a returned machine
   makes a new key and is admitted anew (chapter 8.3 N3 step 1). An Entry already without key — a repeat: the step is skipped; in a move the Entry is written by chapter 8.8 N1.2 (C08-STOLEN-KEY-ENTRY-01)
3b. domain/revoked := {jtis: ""} in the same batch of step 4: all revocations are written before the change, and their tokens are signed by the former keys and no longer pass
   the signature step (keys = {new}); otherwise a full row would hold the 409 of revocation for years (ADR-0110 addendum (21)); members clear their row with the same batch
   with which they write a set with thefts above the former (the domain key set contract «Revocations» merge; ADR-0110 addendum (22), (24))
4. the term record — chapter 8.8 N1.1 (the signature of the new issuing key), in one batch with the set of step 3, the row of step 3b and the rows of step 2 (chapter 8.8 N1.8 step 8; C08-KEYS-CLAIM-BATCH-01, C08-SIGNER-BATCH-01); the common document is re-signed — chapter 8.9 N1.2 after_move
5. members take the set with the answer of the new holder (chapter 8.3; the agent — chapter 9.1)
```

A break between steps 2 and 4: the operation answers with a refusal (code ≠ 0), its repeat starts from step 2 — new keys and a new seed, `rev` again by N1.2 `emergency`;
the repeat does not spoil the unions of step 3: nobody accepted the keys of the previous attempt, and before the batch of step 4 neither they nor the set are written (C08-BOOK-SEAL-BREAK-01, C08-KEYS-CLAIM-BATCH-01, C08-SIGNER-BATCH-01).

**A member that was offline.** While it holds the former set, it accepts the tokens of the stolen key (N1.7) and
seals contributions to the former `book_seal`. Having returned, it takes the new set: its `rev` is greater than any former one under the
premise N1.2 `clocks` — the former holder did not issue a `rev` greater than its wall-clock seconds, and the emergency one is not less than the
floor(now) + TOKEN_SKEW + 1. If the clocks of the holders diverged more, there is no guarantee: this is a limit, not a norm. From this moment
the tokens of the former keys are `unknown_key`, the term records of the former issuing key are a refusal (chapter 8.8), and its contributions sealed
to the former `book_seal` are missing until the first report after the new set (chapter 8.5).

**Races.** The set is written by one process (`domain` of the holder); at a member — by one active agent (the queue `domain/agent-turn`,
[P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.13). Two sets with one `rev` from different
signers are impossible without the root; «holding» at an equal `rev` does not let a repeat overwrite the set. A change in the middle of assembling a
book: the holder opens with the seed that it read at the start of the assembly; a contribution to another `book_seal` is missing, not a refusal of the whole book.

---

### `Platform/08-domain/spec/08.0-domain.norms.md` P/08.0-R006

old-sha256: 1d626e5df9cf053bc5bb11bd4c03e0cb76bdc424e097b2c0f211d40be9c60e5f

<!-- req: P/08.0-R006 -->

- **`revision`** — the edit counter, as P/06.1 N2 «Versions». The field `revision` of the rows `domain/users/<name>`, `domain/grants/<cluster>`, `domain/break-glass/<cluster>`, `domain/groups/<name>`, `domain/roles/<name>` and `domain/folders/<id>`: 1 at creation, +1 for every write of the `domain` process,
  whoever caused it: a door, the removal of rows when a person is deleted, the reconciliation of the pass, `first-admin`. An existing row without the field or with an unreadable field is unreadable by its current family; it is not revision 0 and a write does not normalize it to 1. Confirmed absence and creation at revision 1, explicit corruption deletion and restoration from a current readable copy keep their existing rules.
  The copy at a member does not carry the field: the agent gets the `doc` of the grant and the fields `break_glass`, as before.
- **`ETag`** — the index of the row in double quotes (P/06.1 N2 «Versions»). It is carried by the answers of success per the table and by the read doors of the domain console ([P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.2).
  The listings `GET /domain/users`, `GET /domain/groups`, `GET /domain/roles`, `GET /domain/break-glass`, `GET /domain/placement`, `GET /domain/grants` do not carry the header: they have many rows, the index and `revision` stand at each row. Apart from the explicit folder and membership success bodies of P/08.5 N1.8, write success bodies do not carry the index: it becomes known only after the batch (below).
- **`If-Match`** is optional; the form of the value — the two forms of P/06.1 N2 «Versions»: `<revision>` as a number or the index in quotes. Another value — 400 `If-Match is a unit revision` before the row is read. The doors `POST /domain/users`, `/domain/groups`, `/domain/roles` and `/domain/folders` do not read it: there is no row yet, the condition has nothing to judge. The door `POST /domain/batch` does not read it: the condition of a row is its `cas`.
  Zero is not a form: the condition names a row that exists, so the first write of the topology and of the shared document is carried by `base_rev: 0` (below).
- **The condition** is judged at the first read of the door's row: after the memory and the body form, before the content of the edit. After a `cas` conflict — again, by the re-read row. A door that needs the row (`PUT`, `DELETE` of a person, a group, a role, `DELETE` of a placement, `DELETE` of a member)
  answers its own 404 before the condition; a door that creates the row — 412 with `revision: 0`. The row exists but its `revision` does not read: use the current whole-row unreadable outcome of its family before judging the condition. Neither a numeric condition nor a matching store index turns it into a readable row. An explicit corruption-deletion path still follows its own stated procedure.
- **`412 revision moved`** — the condition is not met, nothing is written: `{detail, error: "revision moved", field: "/revision", revision, row?}`, the form of P/06.1 N2 «Versions». The doors of the table require a right above `view`, so `row` is present if there is a row and it reads. `row` carries no secrets:

| Row | `row` |
|---|---|
| `domain/member-rows/<part>` | `{rev, term?, members}` |
| `domain/topology` | the document `doc` |
| `domain/users/<name>` | an element of `GET /domain/users`; there is no `pwhash_secret` in it |
| `domain/grants/<cluster>` | `{lines, revision, index}` |
| `domain/break-glass/<cluster>` | `{set_at, revision, index}` |
| `domain/groups/<name>` | an element of `GET /domain/groups` |
| `domain/roles/<name>` | an element of `GET /domain/roles` |
| `domain/placement/<sub>/<ref>` | `Placement` with `index` |
| `domain/shared` | the pointer `{term, rev, sha256, object}` |
| `domain/folders/<id>` | the live `DomainFolderView` of P/08.5 N1.8; no internal counts |

**Membership is index-only (P08 review C3).** `domain/memberof/<member>/<sub>/<rows>/<id>` contains only `folders`; it has no revision counter. Its `optional-index` condition accepts an absent If-Match or a double-quoted store index, including `""` for confirmed absence. A bare number or another spelling is 400 `If-Match is a store index`, before reading the row. Judge it after repeat memory and the body form, and again after a CAS conflict. Unknown reading is 503 unavailable, never index `""`. On a mismatch return 412 `{error: "revision moved", field: "/index", index, row?}` without a revision counter; `row` is the current `{folders,index}` when readable and present. The ordinary right check and response ceiling still apply. Successful GET and PUT return `{folders,index}` without ETag; an empty PUT deletes the row and returns `{folders: [], index: ""}`. A lost-answer replay returns the saved response before rejudging its old condition.

**`base_rev`** of `PUT /domain/topology` and `PUT /domain/shared` is the former input (the Architect's decision of 2026-10-29 on the plan of the domain share, V3). `If-Match` is the main one. The door reads `base_rev` only if there is no header, and then the refusal is the former one: 409 of the revision.
Both are present: `<revision>` equals `base_rev` — the door judges `If-Match`; not equal, or an index stands next to `base_rev` — 400 `refused`, `field: /base_rev`: a counter and an index cannot be compared without the row, and the door does not guess an edit with two different conditions.
Neither is present — the former 400: at these doors an omitted field stays as it was, so an edit without a condition is not written.

### `Platform/08-domain/spec/08.3-domain.norms.md` P/08.3-R008

old-sha256: c683c03edbae510863d53f9c84dfbac5e2f78e25e5f73dae59f7767ac4fd49f5

<!-- req: P/08.3-R008 -->

`ROAD_QUIET` and the order of roads for the agent and the relay are also the [report reception contract](../../common/contracts/accept.md) «Generation, mark, limits» (analysis of review of stage B 8–10, № 4: lesson 9 reads the contract, this chapter owns the text).

```yaml
road:          directly (no via) or through a relay R (via = R); the road of a publication is named by the holder, not by the member
one_road:      the road sets the order: the last accepted on this road is newer, even if sent_at goes back (report reception contract)
two_roads:     between the roads of one member — by the member's sent_at (one clock on both): a body of the other road with sent_at below the
               mark is not accepted (ignored) while the member is heard — heard_ago < ROAD_QUIET (report reception contract, step 2a); an equal
               sent_at — one body: the same bytes — heard (a repeat by the other road), others — 409 same_sent_at (ibid., step 2)
ROAD_QUIET:    forms/runtime-constants.tsv         # s, the holder's monotonic clock: three passes of the agent (REPORT_EVERY (forms/runtime-constants.tsv)); longer — the former road is silent;
                           # for class camera — road_quiet = max(15, 3 × mark.every) (P/08.3 N1.1a)
base:          each road has its own: the answer gives the rev of the mark only to the road of the mark, to the other — 0 (it sends the whole)
signature:     the mark of a direct report carries the agent signature; through a relay the member's signature is not carried over — the holder
               trusts the relay's signature and the topology (ADR-0074; carrying over the member's signature is a debt, the answer to the note of M11 item 4)
bytes:         the delta of a generation through a relay — the entry relayed[<member>] of the batch as received (JCS of this value)
```

### `Platform/08-domain/spec/08.6-domain.norms.md` P/08.6-R013

old-sha256: c32cd7bd6141f19850d66cbc8bf2f149ef250dd727dfcfdfe53790db981adf38

<!-- req: P/08.6-R013 -->

```
1. Idempotency-Key is absent                                                   → 400
1a. <sub> from the catalogue, <rows> — unit.rows of its manifest or a key of domain.edit_tables   → 404
1b. fields, secrets, values — N1.3                                              → 400
2. PUT, DELETE: find (N1.3 find, refusals); POST: cluster is a member            → 404 / 503
2a. PUT, DELETE without ?cluster=, ref in units at two executors and more (an early repeat, ADR-0091 addendum (15) item 4, addendum (17)
   item 1): for each executor — the id by N1.4 (the id depends on the member) and the row domain/pending/<member>; a record of this id
   is at exactly one — repeat (202 / 422) at it; at two and more — 409 executors (?cluster= is needed); at none —
   409 executors                                                                → 202 / 422 / 409
   with ?cluster= — the steps below at the named member, as before
3. id = N1.4; read domain/pending/<member>: the same id — repeat (202 / 422)
3a. secrets of N1.3a → envelopes m1; no key of the member — 503 {error: "unavailable"}, nothing is written: further on the row with envelopes is measured
4. 50 waiting                                                                   → 409 kept_full
   the row with this edit is greater than the ceiling (N1.4 row_full)           → 413 too large / 409 kept_full
   a DELETE of the same path is waiting                                        → 409 unit is being deleted
   base: the member's copy; a PUT of the same path is waiting — base of the last by seq + 1
5. seq of the row + 1; edit {id, seq, what, method, path, body, key, at, base?, by?, iat?, asked} → write the edit and seq by one CAS (a conflict — reread from step 3, up to 10 times,
   then 409 «the pending edits kept changing; ask again»)
6. 202
```

### `Platform/08-domain/spec/08.8-domain.norms.md` P/08.8-R010

old-sha256: 8c51f72c7d3428c003e124d945057cf51a8abc04f7063d1bffb0b7ac85d19dac

<!-- req: P/08.8-R010 -->

```yaml
door:        POST /domain/move {recovery, stolen?, copy?, why?} at the cluster console of the target → the process domain by the same path
             (forwarding to the signer of the cluster console — the OpenAPI of lesson 6 POST /domain/move); deadline 90 s; w2cctl domain move <door> <file> [stolen] [copy=<term>.<rev>] [why=<words>] (why without copy — a move
             «from nothing», N1.8 step 6); without a token in the environment the command signs the request by the root of the file, with a token it sends no signature headers;
             the identity — by the console mode (P/06.3 N1.3 identity) and the admin grant of the target cluster (the OpenAPI of lesson 6 POST /domain/move; the gate-and-pass contract need); on the day
             of the loss of the domain it is given by the copy of grants (the lifetime — GRANT_LIFETIME, chapter 8.4 N1.3), the break-glass entry (chapter 8.4 N1.6) or the signature by the root: the recovery file is everything (chapter 8.2 N1.1 limit), therefore
             only at this door and only from the loopback does the signature by the root replace the token, the other doors and the gate stay as before (C08-MOVE-BY-FILE-01)
  by_file:  the headers X-W2C-Time and X-W2C-Signature, the message move|<cluster>|<time>|<sha256 of the body> of the ask signature contract, the key — root_key of the file; the console judges (chapter 6.7 N1.8 step 3); the file stays in the body recovery: steps 4 and 7 need the root;
            by of the journal and of the alarm — "recovery file": a person's name carries no space
  recovery:  the text of the recovery file of chapter 8.2 N1.1 {domain, root_key, root_pub}
  copy:      {term, rev} — restore exactly this backup copy; without why — 400; why — a string with at least one
             non-blank character, otherwise as absent (400; added by the reconciliation of M11, H18)
order:       0. the process door accepts a move only on the connection of the console of its own cluster, by the same sign as `by` below; on a stand without a kit — only from the loopback; otherwise 403 {error: "refused"} before reading the body, the journal record below, not an alarm: `SIGNER_URL` is visible over the network, and the file must not bypass the loopback, the trace and the alarm (C08-MOVE-BY-FILE-01)
             1. the body is not in form — 400 {error: "refused", detail: "a move is {recovery: <the recovery file, as its text>,
                stolen?: true | false, copy?: {term, rev} with why: <words>} — a planned handover is the holder's (POST
                /domain/handover)"}
             2. a move is under way already — 503 «a move is under way here already: seconds, not minutes»
             3. this cluster holds the domain — 409 «<c> holds the domain at term N: there is nothing to move here»; the exception is one, a split: there is why, and step 5 heard a record of its own term with another holder that passed record: the move goes on, the new term is above both, the other holder yields; it did not hear one — the same 409 (P/09.1 N4 `domain.term_split`; C08-SAME-TERM-TIE-01)
             4. the file does not read or root_pub is not from root_key, or not the root of the set of this cluster — 403 «the recovery file is
                not this domain's»
             4a. a move by signature — there is at least one header by_file: the signature or the window do not match root_pub of the file — 403 «the recovery file did not sign this move»; the row domain/move-ask {at, sha256}: the signature time is numerically not larger than at — 403 «this signature was used: sign the move again»;
                 write {at: the time, sha256: of the body} by CAS on the read version before step 5: a CAS conflict — the same 403, the signature serves once; an unknown outcome — 503 unavailable, step 5 does not go, a new signature will pass; a refusal of the guard — as at any write (chapter 8.10 guard); sha256 — a trace for analysis, it is not judged; for an attacker this is not a barrier: he has the body with the root, he will sign again, the trace holds an accidental double launch;
                 the row is unreadable or at is further than now + MEMBER_WINDOW — spoiled: the move does not refuse, rewrite it by CAS, the journal without the value (C08-MOVE-BY-FILE-01); the trace is written — the alarm domain.move_by_file {at, by} at once, before step 5
             5. the neighbours — the consoles of CLUSTERS except its own (its own store is read directly; the reconciliation of M11, H17): GET /api/held of each; the backup copy — GET /api/backup with the signature of a member of this cluster
                (the ask signature contract; the key — domain/member-key, P/09.1 N1.1 readers); the neighbours — in turn, each request waits FORWARD_WAIT (5 s, the forwarding contract), not longer than the rest of the deadline
                90 s; did not answer or the deadline ran out — skipped (C08-MOVE-PEER-WAIT-01); a neighbour's 503 on GET /api/held
                (its rows of the term or of the backup copy do not read) — likewise «did not answer», skipped; its own row domain/backup-taken
                that does not read is not a source, as its own unreadable domain/backup (V7 item 3, the Architect's decision of 2026-10-28, on a proposal; row 17 of the list);
                its own domain/holder that does not read is not_a_record (the outcomes of domain/holder, domain): the move does not
                refuse and does not answer 503 — step 3 does not fire on it, it gives no term and no record for steps 6 and 8;
                claim of step 8 rewrites it by CAS on the read version (the writer — the process domain, P2), the reason goes to the journal;
                the rule «either of the two is unreadable — claim is not written» of N1.1 is about term 1 at start, not about a move (C08-MOVE-OWN-HOLDER-UNREADABLE-01)
                answered without a backup copy — ignored;
                keys of the /api/held answers — by the function keys (the domain key set contract) from the pinned root into the move set (as
                «The follow set» of the key set contract); the records and backup copies of steps 6 and 8 are checked by it (added by the Quint model of M11, RB)
                its own domain/keys that is not confirmed by its own domain/holder that passed record by this set — a case that the batch of step 8 does not close:
                its own term record is spoiled, unreadable or absent: the move set does not begin with such a row — the move
                set begins with null (the pinned root), the sets of the neighbours' answers — by the function keys; no neighbour
                gave a set — it serves (a member does not lose its only set); its rev, checked by the root, enters
                «largest known rev» of the emergency rev (chapter 8.2 N1.2 emergency), confirmed or not: a retry will not
                sign another composition with the same rev (C08-MOVE-UNCONFIRMED-KEYS-02); the new keys (step 7) overwrite it by the batch of step 8 (P2,
                the writer — the process domain); a member that only follows does not write such a set (the key set contract
                «The follow set»; the Architect's decision of 2026-10-29, C08-MOVE-UNCONFIRMED-KEYS-01)
             6. not one term record and not one backup copy (neither at the neighbours nor its own) — 409 {error: "refused",
                detail: "nothing to restore from: no neighbour and not this cluster keeps a record of the holder or a
                backup — a new domain is installed, not moved"}; otherwise
                the choice of the backup copy: copy — exactly it at any neighbour (and its own), otherwise 409 «nothing was restored: no neighbour gave
                the copy named, term T rev R (…)»; without copy — the largest (term, rev) of the checked ones, and when there is none (neither
                a neighbour nor its own store gave a backup copy) — without it, only with an explicit why («from nothing»): state is not
                restored, the member list — the copy of domain/member-list/<part> of this cluster, it is the holder, the answer 200 with
                restored_from: null; a cluster moved «from nothing» has no rows of rights, therefore until the first write of such a row the answer to a member carries held with the names grants, roles, break_glass, and not «no row»: otherwise all members would delete their copies (C08-MOVE-NOTHING-HELD-01); the sign — the row domain/from-nothing {term, partial?}: it is written by the batch of step 8 of this move, partial — N1.8a; it is in state, therefore the backup copy carries it further, a term from a copy does not remove the sign, and a copy without it removes it: such a copy had rows of rights; it is decided for each row of each member (the Architect's decision of 2026-11-01, ADR-0103 addendum (2), C08-MOVE-NOTHING-HELD-02); without why — always 409 {error: "refused"}: with its own term record ≥ 1 and a neighbour that
                did not answer — detail "nothing was restored: <n> did not answer" (added by the Quint model of M11, ER); otherwise (no own
                record or all answered) — detail "nothing to restore from: no backup copy anywhere — say why to move
                from nothing" (review of stage A 8–10, № 34); a neighbour
                announced in /api/held a newer backup copy and did not give it (401, 403, 503) — or gave 200, but the copy did not pass
                the check by the move set (except revoked_issuer — its own 409 below; added by the Quint model of M11, RB) — 409
                «nothing was restored: the newest copy this move
                could read is …, and <n> keeps term T rev R and did not give it (<why>) — restoring it would roll the
                domain back. Make the newer copy readable here, or name the copy to restore (copy: {term, rev}) and say
                why»; a backup copy (its own or a neighbour's) whose record is revoked_issuer, named by copy or newer than the chosen one,
                — 409 {error: "refused", detail: «nothing was restored: the copy term T rev R is signed by a revoked
                issuer (<kid>) — restoring it would undo the revocation»}, nothing changes (added by the reconciliation of M11, H16)
                the new term of step 8 larger than 2^53−1 without stolen — 409 {error: "refused", detail: "nothing was moved: term T is the last the form holds; if a thief signed it, move with stolen"}, nothing changes (Quint M12 N4; C08-MOVE-TERM-LIMIT-01)
                before step 7 and its first write (including stranded collection), compute the emergency revision of chapter 8.2 N1.2; if it is not representable by the keys form, 409 {error: "refused", detail: "nothing was restored: emergency revision is not representable"}, nothing is written
             7. the exception of step 3 with a copy: before the first write of this step — the gathering of stranded (N1.6) of its own state against the chosen copy: base — it, term and holder — of the new record, secrets — by its own domain/signer.backup_key_secret; the copy will replace the holder's state, and its edits newer than the copy would otherwise vanish silently: the snapshot is written only by the yielding side; the gathering failed — journal domain.stranded.lost {term}, the move goes on (Quint M12 N6; C08-SPLIT-STRANDED-01)
                restore state: secrets — by the backup copy key from the file, then by the ring of this cluster; a secret that did not
                open (another's kid, AAD, not an envelope — N1.5 kid) — its item is Sealed: it is not restored, the move
                goes on, the answer names it in sealed (added by the reconciliation of M11, H15); the keys — from the file:
                stolen — the steps of chapter 8.2 «change after theft» (a new token key, issuing key, book acceptance key, set);
                without stolen — a new token key and issuing key, a set with the emergency rev (chapter 8.2 N1.2 emergency) with them in keys/issuing, the former token
                keys: the former current — until now + OLD_KEYS and keep_until now + KEEP_OLD (except stolen), the others — their own until and keep_until, an expired until is removed only together with keep_until (the key set contract, ADR-0110 addendum (12) item 1), live keep_until more than 8 — the oldest is removed, journal domain.keys.keep_dropped, as at a planned change (C08-MOVE-UNTIL-01); the former issuer — into revoked_issuing;
                the base of the set — the largest checked set of step 5, the revocations of the neighbours that did not answer do not enter it, a limit: a move onto a member that did not hear a move with stolen also removes revoked_members with thefts of that set, a report by a stolen key is accepted again, for the kinds keep — until KEEP_OLD, 10 years; the way out — one more move with stolen (Quint M12 N10; ADR-0110 addendum (13) item 6); `book_seal` of the base whose seed the state of the copy does not give, or a state without a seed — a new seed and `book_seal`, as at a change of the book acceptance key: the contributions to the former one are missing (C08-MOVE-SEAL-BASE-01)
                «restore» — the state = the copy: the families of state of N1.5 become exactly the state of the copy — its own rows of these families
                that are not in the copy are deleted, a row of the copy is written whole (the extra own items go), except domain/revoked: it is the union of the copy and its own row by the rules `repeat`, `prune` of the set contract: its own is newer than the copy by BACKUP_EVERY, and a revocation does not revive, its own is unreadable — the copy (C08-MOVE-REVOKED-MERGE-01); a union heavier than the row ceiling (chapter 8.2 N1.6a limit, ceiling P/01.1 — 413 toolarge, the move would be refused) — beyond the ceiling the words with the smallest exp are removed, their tokens expire first, journal domain.revoked.dropped {jti, exp}: the restore is more important, the limit — a removed revocation does not act until its exp; at a member the same at any replacement of a row by the row of an answer on a 413 of the merge (P/09.1 N1.4 from_carry, journal domain.revoked.replaced; ADR-0110 addendum (26), (27)); new revocations — 409 too many revocations while the row is full (ADR-0110 addendum (19) item 2, addendum (20) item 1); a move with stolen does not unite the row but clears it — the change after theft (chapter 8.2 N3 step 3b; ADR-0110 addendum (21)), its own
                unreadable rows of these families are deleted or rewritten (the writer — the process domain, P2); a Sealed item
                is not written, and its own former value of this item is removed; without a copy («from nothing») state is not
                touched; the objects of the copy — only a write (step 8); what is outside state (the report generations, the indices, the assembled
                books, domain/signer, domain/keys, domain/stranded) — is not touched; the same at take (N1.7) (the decision
                of the Architect of 2026-10-29, C08-RESTORE-EXACT-01); at the exception of step 3 this step does not write the row domain/book-seal, does not delete it and does not remove its item: the seed of the copy lives in the operation's memory, it is written by the batch of step 8 (the Architect's decision of 2026-11-01, Quint M14 N16, C08-SEAL-COPY-BATCH-01); the pointer domain/shared — likewise: it is written by the batch of step 8 (C08-SHARED-SPLIT-BATCH-01)
                backup_key_rev of the new domain/signer — that of the document of the chosen copy; without a copy («from nothing») — that of its own readable
                domain/signer with keys (not forgotten), otherwise 1 — the installation value: no norm raises it
                (the domain backup key contract; C08-MOVE-BACKUP-KEY-REV-01)
                stolen: the member key of the former holder for revoked_members (chapter 8.2 «change after theft» step 3, I4) — key of the
                Entry {how: "holder"} of the list that the move restores: domain/member-rows/<part> of the state of the chosen copy, without a copy
                — domain/member-list/<part> of this cluster; an Entry without key — the last one in its revoked_keys: a theft on the same holder, there is no new key yet (chapter 8.2 step 3; C08-STOLEN-KEY-ENTRY-01); holder_member_key of the copy does not replace it (it is for former, N1.2, and at
                stolen there is no key in former); there is not even that — 409 {error: "refused", detail: "nothing was moved: the list names no key of the
                former holder <h>, and a stolen move must revoke it"}; the check — before the first write of the move: nothing
                changes (C08-MOVE-STOLEN-KEY-01)
             8. the new term = 1 + max(term of the records and backup copies from the answers of the neighbours and its own); larger than 2^53−1 at stolen — the same calculation without the records and copies of the issuers that the move revokes, and if none is left — term 2 (term 1 with `restored_from` is not let through by `record`; C08-MOVE-TERM-NONE-01): the record of the limit term was signed by the thief, and step 5 still trusts its issuer (Quint M12 N4; C08-MOVE-TERM-LIMIT-01); claim with restored_from; the former one —
                N1.2; the shared document — from the first backup copy whose sum matched (chapter 8.9); none matched — the move goes on, the shared document
                is not written and not re-signed, the reason goes to the journal without the value: it does not replace its own former pointer and rows (C08-MOVE-SHARED-NONE-01); the objects of the copy (N1.5 objects)
                (the order of the writes: state, the member list, domain/relay-members/*, relays of the row domain/topology from Entry.via of the rows, the index domain/folder-units from the rows domain/memberof, exp of the rows domain/issued not below now + the lifetime of the kind (chapter 8.2 N1.6a): the copy does not carry them, and a relay's batch without them would call everyone strangers; the shared document, the objects — then `domain/signer`, the new seed `domain/book-seal` when step 7 made it, and at the exception of step 3 without a new seed — the seed of the copy, at a move «from nothing» domain/from-nothing, at the exception of step 3 the pointer domain/shared of the shared document — its object lies earlier, nobody's until the pointer names it (chapter 8.9 write), — the row domain/keys of step 7 and claim in one batch op: batch (P/01.1 N3 «write batch»; each row has its own cas, the guards — as at any write, chapter 8.10 guard), then the Entry
                of the holder, N1.1; a break before the batch leaves the former set, the former term record, the former signer's keys and, at the holder of the exception of step 3, the former seed and the former pointer of the shared document, see «Races»: the signer, the seed and the issuer of the holder's document are always in its set, before the batch the new keys and the new seed live in the operation's memory, at the exception of step 3 the seed of the copy is there too; any other target does not hold the domain, the seed of the copy written by step 7 serves nobody before the batch; the Architect's decision of 2026-10-31, Quint M12 N7, C08-KEYS-CLAIM-BATCH-01; C08-TAKE-ORDER-01; the Architect's decision of 2026-11-01, Quint M13 N13, C08-SIGNER-BATCH-01; Quint M14 N16, C08-SEAL-COPY-BATCH-01; the Architect's decision of 2026-11-01, ADR-0103 addendum (2), C08-SHARED-SPLIT-BATCH-01)
                are written: objects — by value, raw — back as bytes (the decoded base64): an object unreadable in the copy
                is unreadable after it too — the outcome of its reader is as before, there is no substitution by absence (C08-BACKUP-JSON-99, the Architect's decision of 2026-10-26)
answer:      200 {term, holder, restored_from: {term, rev} | null, ignored: [<member>…], unanswered?: [<member>…], sentence, sealed?: [{key, item, why}…]}; unanswered — the neighbours of step 5 without an answer: a copy newer than the chosen one could have been at them (C08-MOVE-UNANSWERED-01)
limits:      stolen declares a theft, there is nothing to tell it apart by: an operator's error on a cut-off member takes the honest chain of handovers back (term 4 → 3), the key of the honest holder is revoked (Quint M12 N9); the term after a theft can be smaller than the former one also at the limit of step 8: the holder yields to it too (N1.6 yields), the copy and the document of a revoked issuer do not serve the keeper and the member as a boundary (P/09.1 N3), and a copy of such an issuer newer than the chosen one holds moves at the 409 of step 6 until the keeper has taken a new one (C08-STOLEN-TERM-BACK-01); a copy chosen without copy is the largest checked one: at stolen this may be the thief's copy, therefore the one who knows the time of the theft names copy, if a copy from before the theft is left at someone: a keeper holds one, otherwise only «from nothing» remains (C08-STOLEN-COPY-LIMIT-01); people, grants and disablings newer than the copy roll back, there is protection only for the revocations of jti: the window is the age of the copy restored_from, with live keepers about BACKUP_EVERY (C08-RIGHTS-NEWER-LIMIT-01); `Entry.ca` and the rows kept of the worker that came after the copy of the handover was taken are lost (C08-OUTCOME-HOLD-01); no console of the target or it is in `shut` — there is no move onto this cluster, the way out is another member with a live console; without a kit outside a stand step 0 lets the process through from the loopback past the console, the trace and the alarm; a proxy that leaves no headers is indistinguishable from the loopback (C08-MOVE-BY-FILE-01)
             # sealed — the Sealed items of step 7 by (key, item); none — no field (added by the reconciliation of M11, H15)
no_admin:    after the application of state (step 7) there may be no proven administrators (P/08.4 N1.3): the move does not stop, the domain works,
             journal domain.no_admin once per pass, the path — the command grant-admin (P/08.4 N1.9; ADR-0100 §2). The reconciliation of new kinds (P/08.4 N3) removes nothing until
             the restore or the move is complete: the unknown is not empty (ADR-0098 §5)
journal:     domain.moved {term, restored_from, stolen, copy, why, by} — at copy, stolen or a move by root signature. The signature is not checked, the door is visible over the network: a refusal of step 0 at the process and of step 1a at the console — only the journal domain.move_refused {step, why} and access.denied {why} without values, not more often than once per SAY_EVERY (600 s, P/09.1) per source address and not more than 100 lines per SAY_EVERY per door, with a count of attempts: otherwise a scanner drowns the real alarm.
             The alarm to the administrators — only after a correct signature: the console right after its step 3, before forwarding, console.move_by_file {at} into `audit.alarms/console`, and a second row {outcome} by the answer, including 404, 502, standby and the refusals of steps 1–3; the process after step 4a domain.move_by_file {at, by} into `audit.alarms/domain` and {outcome} at a refusal of steps 4, 4a and a failure of 5–8; they arrive as any row of class alarm (chapter 8.4). A failure of the alarm write does not stop the move: on the day of the loss of the domain the store is unhealthy anyway; the trace — the process journal and the words «the alarm was not written» in sentence of the answer
  by:        the name from the header X-W2C-User: set by the cluster console at forwarding to the signer (P/06.7 N1.8) — the name proven by
             the gate, at the break-glass entry — the session's name; the process trusts it only on the connection of the console of its own
             cluster: the client certificate of the role console, the check in the handshake — as at X-W2C-Client (the forwarding contract
             «Client address»: its own ca.pem, ca.next.pem, EKU clientAuth, sig, revocation); on the other connections and on a stand without
             TLS — it is not read; an X-W2C-User that came from outside the console always removes (the Architect's decision of 2026-10-29, C08-MOVED-BY-01)
             no header on the connection of step 0 — by: null: the move does not
             refuse (the identity and admin were already checked by the console, step 3 P/06.7 N1.8), the name is not invented — neither "", nor own,
             nor the name of the cluster (C08-MOVED-BY-ABSENT-01)
```

The process's client to the consoles of the neighbours (step 5) and to the console of the handover target (N1.7 steps 4, 5) over `https://` accepts the server
by the function `peer` — the [`peer` contract](../../common/contracts/peer.md) (the process `domain` is a participant). The door `GET /api/backup`
of the cluster console that checks the signature of step 5 — the OpenAPI of lesson 6
`GET /api/backup`, the [ask signature contract](../../common/contracts/ask-sig.md).

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R004

old-sha256: 4da44d89ff026b8c6721f590e8f202ed741cceeb2dbfd43f8069bfde1407af7e

<!-- req: P/10-R004 -->
### N1.2 The read doors — it answers itself

The parsing of a request is [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Request parsing and the order of checks»
(P/01.1 N2.1 with the deviations of the console; the layout audit B-09); there are no deviations of its own. The identity and the grants are N1.5 (`view` for reading by `domain/grants/domain`; the view doors — «Judgement by target» of [the right contract](../../common/contracts/may.md)). Each
door is a row of the list of domain doors of [the forwarding contract](../../common/contracts/forwarding.md) «Domain doors»; a row with `GET`
also covers `HEAD` of the same path — the same code and headers without a body (ibid.; P/06.5 N2).

**The row version at the read doors** ([P/08.0](../../08-domain/spec/08.0-domain.norms.md) N1.9 «Versions»; ADR-0094 B4). The doors of one row — `GET /domain/members/<member>`, `GET /domain/topology`, `GET /domain/placement/<sub>/<ref>`, `GET /domain/shared` — serve an `ETag`: the index of this row (for the shared document — of the pointer) in double quotes, from the same read as the value. There is no row — the answer is without `ETag`: the condition has nothing to judge about.
`GET /domain/placement` carries `index` in each record, `GET /domain/grants` — the field `versions`: the index and `revision` stand by the row, because the answer has many rows. The values are fit for `If-Match` of the edit doors that the console passes on to the process (N1.3).

**N1.2a The view (M11/1 N2, N4).** The doors are at the domain console; the cluster console forwards them without rewriting:

| Door | Success | Refusals |
|---|---|---|
| GET `/domain[?cursor=]` | the answer is the head of `domain/view` and the non-empty parts in a row up to DOMAIN_PAGE_MEMBERS members, the fields `members`, `units`, `contested`, `reports`, `pending`, `outcomes` — a merge of the rows, `cursor` — the next page, `unread` — the unread parts; a small domain — one page (P/08.1 N1.4b); for a non-viewer of the domain (the right contract `wide`) — only `as_of`, `holder`, `complete`, `members` (`servers` and `url` — only for the clusters where it has a row), `units` by record, `outcomes` — the outcomes where `by` is itself, `contested` — the refs whose cluster it sees, `age`, `url`, `withheld: <count>`; otherwise 200 — the object `domain/view` ([P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.4) as is plus `age` — seconds since `as_of` by the wall clock of the console, `max(0, now − as_of)` (a clock gone back — 0; C10-AGE-NONNEG-01), one digit after the point; the field `url` of the view that does not read (not a string) is `null` in the answer (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 53 of the list) | 404 `{error: "no domain here", detail}` — there is no object; the object exists but does not read — 503 `{error: "unavailable"}`, not 404 (V7 item 3, the Architect's decision of 2026-10-28, P1; line 54 of the list); 401/403 — N1.5 |
| GET `/domain/<sub>/<rows>[?cluster=<member>][&cursor=]`, `/domain/<sub>/<rows>?part=<part>` | 200 — `[Unit]` of the subsystem from the rows of the view, page by page by the header `X-Cursor`, with `cluster` — this member’s entire row in its one part, one page: `cursor` is not read, including an invalid opaque cursor, and there is no `X-Cursor`; with `part` — the units of one row `domain/view-rows/<part>`, one read and one page, `cursor` is not read, there is no `X-Cursor`, no row — `[]` (the part — P/08.3 N1.1; ADR-0113 addendum (22)); for a non-viewer of the domain — only the records it sees, `X-Withheld: <count>`, if some are hidden because of the unread (`unavailable`) | in order: 400 — `cluster` or `part` twice or empty ([P/06.5](../../06-console/spec/06.5-console.norms.md) N2), `part` not by the grammar of a part, `cluster` and `part` together; 404 — there is no such manifest; 404 `{error: "not in the directory"}` — the manifest has no `domain.ref`; 404 — `rows` is not its own; 404 `{error: "no domain here"}` — there is no view, 503 `{error: "unavailable"}` — the view does not read (V7 item 3, the Architect's decision of 2026-10-28, P1; line 54 of the list); 404 `{error: "no such member"}` — the member is not in the list; other parameters are not read |
| GET `/domain/<sub>/kept/<name>` | 200 `{items, index}` of the row `domain/<sub>/<name>`, `<name>` — an element of `domain.kept_read` of the manifest; the mask of [P/06.2](../../06-console/spec/06.2-console.norms.md) N1.4: an element with the name `*_secret` and a field `*_secret` at any depth of the value parsed as JSON, an envelope `enc:` — `"***"`, a value that is not JSON — as is; the domain console answers itself; the right is `view` of the domain (`wide`), judged first: a non-viewer does not tell «not declared» from «not allowed» | 401, 403 — before everything; 404 `{error: "no such path"}` — `<name>` is not declared or there is no row; 503 `{error: "unavailable"}` — does not read |
| GET `/domain/relays/<relay>` | 200 `{relay, rev, members}` of the row `domain/relay-members/<relay>` (P/08.3 N1.2): `members` — names in ascending order, up to RELAY_MEMBERS_MAX ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.2, [owner form](../../08-domain/forms/runtime-constants.tsv)), the member keys do not go; there is no row — `rev` 0, `members: []`; the domain console answers itself; the right is `view` of the domain (`wide`), judged first | 401, 403 — before everything; 404 `{error: "no such member"}` — there is no such member; 503 `{error: "unavailable"}` — the row does not read or exceeds its owner limit; never truncate |
| GET `/domain/<sub>/tables/<table>?cluster=<member>` | 200 — `{cluster, ts, rows}`, the object P/08.1 N1.4a of this member as is, for a non-viewer of the domain — only the visible rows and `X-Withheld`; `ETag` — sha256 of the served body, separate for each answer, `If-None-Match` — 304: reading the list of members is cheap; one member per request: the object is bounded by P/04 N1.3b, there is no list of all (ADR-0110) | in order: 400 — `cluster` is absent, twice or empty; 404 — there is no such manifest; 404 — `<table>` is not a key of `domain.view_tables`; 404 `{error: "no domain here"}` — there is no view, 503 `{error: "unavailable"}` — the view does not read; 404 `{error: "no such member"}` — the member is not in the list; 404 `{error: "not reported yet"}` — there is no object; 503 `{error: "unavailable"}` — the object does not read; other parameters are not read |
| GET `/domain/shadow` | 200 — the shadow report (P/08.1 N1.6) of the last pass | 404 `{error: "no domain here"}` — there is no report; the report exists but does not read — 503 `{error: "unavailable"}` (V7 item 3, the Architect's decision of 2026-10-28, P1; line 54 of the list) |
| GET `/domain/folders`, `/domain/folders/<id>/units[?cursor=&limit=]`, `/domain/memberof/<member>/<sub>/<rows>/<id>` | Own domain-console read doors by [P/08.5 N1.8](../../08-domain/spec/08.5-domain.norms.md): forms, pagination, visibility and check budget remain with that owner | N1.5 before reads; bad cursor — 400 `{error: "refused"}`, no folder — 404 `{error: "no such path"}`; unreadable source — 503 `{error: "unavailable"}` |

**Pagination of `GET /domain` (G10-PAGE-CURSOR-01).** The limit is hard: at most DOMAIN_PAGE_MEMBERS elements of `members` per page. A part is the writer's storage/work unit, not an indivisible HTTP page; a readable part with more than DOMAIN_PAGE_MEMBERS members is split at a member boundary. Visit the non-empty parts in ascending order of their four-digit names (0000…4095), and the members inside each part by name in UTF-8 byte order. Select up to the remaining page budget, then continue inside this part on the next request if needed. Each returned page's `members` is itself ordered by name; its last displayed element need not identify the last visited part.

The request without cursor starts the traversal. The returned cursor is an opaque string carrying sufficient continuation state, such as the current part and last visited member. Its encoding is the implementation's; clients return the issued token unchanged as the query value. The cursor continues after the selected members, including within a part, and is omitted at the end. On unchanged readable data, following all pages returns every member exactly once, without a skip or a repeat. The API promises ordinary reads, not a new snapshot spanning concurrent changes.

The page projects the six per-member fields: `members` contains the selected members; `units` keeps Unit records whose cluster is selected; `reports`, `pending` and `outcomes` keep selected member keys. Preserve the view's required empty subsystem keys. A contested ref is a complete conflict fact: keep a ref that has a selected claimant, with its entire original claimant list, never truncate that list at the page boundary. Names used as this context are not additional MemberState elements of the page. A conflict can therefore appear on more than one page, while the members themselves do not repeat. The head's global fields stay global. Existing visibility filtering and the unread/incomplete rules still apply; pagination alone does not change the holder's round completeness.

The existing reader field `unread` is optional `Part[]`; its named type binding is `ServedView.unread` in the [P/08 owner OpenAPI](../../08-domain/spec/08-domain.api.openapi.yaml), with items referring to the existing Part parameter's Schema Object. It is not a stored-head or writer field. During one ordinary pagination sequence in the same context, omit the collected field only if every page omitted it. If any page supplied it, retain the field, possibly as `[]`, and collect each literal Part string once in first-observation order, including order within a page. Later absence or `[]` does not erase earlier observations. Do not parse, trim, pad, sort or normalize part strings; this collector does not add `uniqueItems` or other bounds to an individual response.

This reader observation does not rewrite the first head's global fields or the six projections, full contested context, empty subsystem keys, opaque cursor or visibility filtering. Absence due to visibility does not prove completeness. Valid `200` responses with `complete: false` or `unread`, including on a later page, remain normal incomplete observations, not automatic transport errors or `domain: null`. An actual HTTP/network/body-read failure of continuation keeps the existing null/error path; no inter-page snapshot or client completeness flag is added.

Examples on fixed data: one part with 1001 members gives pages of 1000 and 1; consecutive parts with 999 and 2 give pages of 1000 and 1, continuing inside the second part. A conflict between members on opposite sides of that boundary keeps both claimant names wherever that conflict is included. No part-size bound is added to P/08.1 N1.4b.

**N1.2b Members (M11/3 N2).**

| Door | Who answers | Success | Refusals |
|---|---|---|---|
| GET `/domain/members/<member>` | the domain console (`domainconsole`) | 200 `{part, rev, term, entry}` of the row of the part of this name and `ETag`: the version for `If-Match` of the edit doors | 404 not a member; 503 does not read |
| POST, GET `/domain/batches`, DELETE `/domain/batches/<name>` | the domain console → the process `domain` ([chapter 8.0](../../08-domain/spec/08.0-domain.norms.md)) | the request, response bodies and status codes of [the P/08 owner OpenAPI](../../08-domain/spec/08-domain.api.openapi.yaml) and [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N1.1b, served as received; the POST token is shown once, GET omits it | 400 not by the form; 404 there is no batch; 409 such a batch exists; N1.9 — the right `admin` of the domain |
| GET `/domain/members[?cursor=]` | the domain console (`domainconsole`) | 200 `{members, parts, knocking, count, cursor?}`: the non-empty parts in a row, up to DOMAIN_PAGE_MEMBERS members, a small domain — one page; `parts` — `{<part>: {rev, term, index}}`; `index` is the exact nonempty string Row.index of the store row read, never a JSON number or a binary64 conversion ([P/01.1](../../01-store/spec/01.1-store.norms.md) N1 Version); `members` — a merge of the doc of the rows read by the door; `count` — `domain/member-count`, absent — no field; `knocking` — on the first page `view.knocking`, on each — `domain/knocks/<part>` of the parts of the page (the memory knock exists only in the view, [chapter 8.1](../../08-domain/spec/08.1-domain.norms.md) N1.7), the field is absent in a readable view — `[]` (the field is optional, nobody is knocking; like a view without `shared`, C10-MEMBERS-KNOCKING-ABSENT-01); `member_list` of the view is not substituted (C10-MEMBERS-SOURCE-01) | 404 `no domain here` (there is no view; there is no row `domain/member-rows/<part>` with a readable view — the list exists from the first start of the holder, [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N3 «the holder in the list», C10-MEMBERS-SOURCE-01); the row `domain/member-rows/<part>` or the view exists but does not read — 503 `{error: "unavailable"}` (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 36 of the list); 401/403 — N1.5 |

The grant `admin` for editing the list and `view` for reading are N1.5; the console passes the edits of the list on to the process (N1.3; their norms are
[chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N2).

**N1.2c Topology (M11/4 N2).**

| Door | Who answers | Success | Refusals |
|---|---|---|---|
| GET `/domain/topology` | the domain console | 200 doc ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.2) — from the row `domain/topology`, not from the view: right after a PUT — the new `rev` (reconciliation of M11, T1) | 404 `no domain here` — the view is not built (N4); there is no row `domain/topology` — not a refusal: 200 `{rev: 0, star: [], via: {}}` (P/08.3 N1.2: rev 0 — «never written», no row — the same; C10-TOPOLOGY-ABSENT-01); the row `domain/topology` exists but does not read — 503 `{error: "unavailable"}` (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 50 of the list); 401/403 — N1.5 |

**N1.2d Placements (M11/6 N2).** The doors are the domain console's; the member console forwards them (the forwarding contract «Domain doors»):

| Door | Success | Refusals |
|---|---|---|
| GET `/domain/placement` | 200 `{rev, records: {"<sub>/<ref>": Placement with index}}`; there is no row `domain/placement` — `rev` 0 (there is no counter yet, [P/08.6](../../08-domain/spec/08.6-domain.norms.md) N1.2 `absent`), `records` — as always (C10-PLACEMENT-ABSENT-01) | the row `domain/placement` (the counter `rev`) exists but does not read — 503 `{error: "unavailable"}` (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 43 of the list); 401/403 — N1.5 |
| GET `/domain/placement/<sub>/<ref>` | 200 Placement | 404 there is no record; the record exists but does not read — 503 `{error: "unavailable"}`, not 404 (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 42 of the list); 404 there is no manifest or it is without `domain.ref` |

The form `Placement` and the counter are [chapter 8.6](../../08-domain/spec/08.6-domain.norms.md) N1.1; the console passes the edits of placements
on to the process (N1.3).

**N1.2e Grants (M11/9 N2).**

| Door | Who | Right | Success | Refusals |
|---|---|---|---|---|
| GET `/domain/grants` | the domain console | view; to a non-viewer of the domain — only the clusters where it has `admin` on `*` (the right contract `target`, ADR-0110 D-1), none — 403 | 200 `{grants: {<cluster>: [line…]}, versions: {<cluster>: {revision, index}}}` | 401/403 |

The grant line `line` is [chapter 8.4](../../08-domain/spec/08.4-domain.norms.md) N1.3; the console passes the edit `PUT /domain/grants/<cluster>`
on to the process (N1.3).

**N1.2f The shared document (M11/11 N1.6 `door`).**

```yaml
door:          GET /domain/shared at the domain console (view) → 200 {doc, delivery, declared}; there is no view (domain/view) — 404
               {error: "no domain here"}, like the other read doors without a view (N1.2a); the view exists but does not read — 503
               {error: "unavailable"} (P1; line 54 of the list; C10-SHARED-NOVIEW-01); the pointer domain/shared or its document
               exists but does not read (not by the form, not with the sha256 of the pointer) — 503 {error: "unavailable"}, not doc: null (the outcomes
               of the families shared, shared-docs)
  doc:         the document as signed (an object) | null
  delivery:    view.shared — an x-opaque field: the console does not judge the form of the delivery (the form is the writer's, the process domain, P/08.9
               N1.6), it serves a non-empty object as is, by value (C10-SHARED-OPAQUE-COPY-01); no field or {} — 200,
               delivery = before (P/08.9 N1.6) by the view: term 0, rev 0, holding [], behind {}, refused {}, silent — the members
               of the view not ok, sentence «rev 0 on 0 of T members» (T — the members of the view) with the tails of before; null in term and rev is not
               written (C10-SHARED-EMPTY-DELIVERY-01)
  declared:    {<sub>: [{name, type, schema?}]} — the elements domain.shared of the manifests of the catalogue, by name; schema — at the document
               (CONSOLE-MODULE.md §10a, added by M11/11; the late layer P/07 N1.6)
```

The document and the pointer are [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) N1.2; `view.shared` is chapter 8.9 N1.6; the declaration
`domain.shared` is [P/02.1 N1.2b](../../02-installer/spec/02.1-installer.norms.md). The console passes the edit `PUT /domain/shared` on
to the process (N1.3; the execution — chapter 8.9 N1.3).
