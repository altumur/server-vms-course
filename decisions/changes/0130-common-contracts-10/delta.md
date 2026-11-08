# Delta 0130-common-contracts-10

change: 0130-common-contracts-10 rev 1 · state review · author spec103

Base `ef7192b2dd9bccb091e2c9066f7ded0dea66d49e`. Authority: ADR-0130 Addendum (10), selected commit 597f306aae6b58f502c37c6ace8a9eadc241f2b6; public semantic package c43d2ae46741899d1c5304d9fb40e7810ae88b33b8f6817ac71f015ed8f60415. Requirement units normalized to LF, trailing whitespace removed, one final LF; headings outside code fences terminate units. Common contracts and unanchored P/02 text use exact full-file blob replacements in the artifact manifest; no fictitious req IDs. No accepted/applied state.

## ADDED P/01.1-R149

path: `Platform/01-store/spec/01.1-store.norms.md`

old-sha256: -

new-sha256: a0edf0873ebdcc21c994ba012ff4fccf551bef015cbbcafbe8eb3ac9f136ba6c

<!-- req: P/01.1-R149 -->

The [common production obligations](../../common/contracts/production-obligations.md) apply to this owner (ADR-0130 Addendum (10)). Q4/Q5/Q6: replay identity, retained state, dependency waits and monotonic deadlines; existing P/01 phase outcomes remain authoritative.

## ADDED P/03.2-R069

path: `Platform/03-worker/spec/03.2-worker.norms.md`

old-sha256: -

new-sha256: 5fc86cb6bb5f36f1ec01125b14483c700e2d77b6244b98db64edc7958d6155dc

<!-- req: P/03.2-R069 -->

The [common production obligations](../../common/contracts/production-obligations.md) apply to this owner (ADR-0130 Addendum (10)). Q3: startup presence-lock and inode-retry waiting is finite and cancellable; expiry/cancellation gives existing start refusal code `2` with a reason, before readiness, slot, contender or heartbeat.

## MODIFIED P/03.2-R038

path: `Platform/03-worker/spec/03.2-worker.norms.md`

old-sha256: 5b51913594a582145e960ebc5d3ab3b3700d79c43caf2e28440919d57a721a12

new-sha256: 318712e33a2adcf9e920c054856951a921fa30f05e6b4bea4834dadbcf8c32cc

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
   an exclusive blocking flock within the finite cancellable startup budget of the presence lock contract → compare fstat(fd) and stat(path) (ENOENT at stat — a mismatch, review of stage B 3–5, № 19); no match — close and repeat; a match — write {instance, sub,
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

## ADDED P/04-R069

path: `Platform/04-controller/spec/04-controller.norms.md`

old-sha256: -

new-sha256: 652147b512365d30e66bc3dc09286df9dc13a726b8f02eb35d8c23c431b00d65

<!-- req: P/04-R069 -->

The [common production obligations](../../common/contracts/production-obligations.md) apply to this owner (ADR-0130 Addendum (10)). MB4: a turn protects guarded store mutations only; external actions require their owner-declared independent fence. Q4 retry ownership and Q5 bounded resources also apply.

## ADDED P/05-R058

path: `Platform/05-resource/spec/05-resource.norms.md`

old-sha256: -

new-sha256: a846b113ac438d7304ab11b8840488d478a087a8d0704e512512cb91e5fb7a91

<!-- req: P/05-R058 -->

The [common production obligations](../../common/contracts/production-obligations.md) apply to this owner (ADR-0130 Addendum (10)). Q1/Q5/Q6 and MB1: distinguish pre-effect refusal from unknown publication durability; retain required tombstones, defer unsafe pruning and copy bodies only from their owner. A neighbour copy is never a source for retransmission after `404`.

## MODIFIED P/05-R012

path: `Platform/05-resource/spec/05-resource.norms.md`

old-sha256: 45ceb27baaacb1c8f20e2641dfdcb26322443bf374821b959a8d3d609005f952

new-sha256: f72ace6338098eb88b08f4928ab59f26e1f72db57ac0e3a76299478b241d78fe

<!-- req: P/05-R012 -->

```yaml
mirror:   every owner-originated local body (a received copy is not a source) — to the next copies live neighbours of the ring (N1.4 mirror), always, regardless of mirror.enabled;
          copies — from the row platform/mirror (an integer ≥ 0), no row or no field copies — 1 (log of cammeta-go, lesson 10 № 1); the row
          does not read — bodies are not copied in this pass, the reason is in the heartbeat (settings_unread: mirror; V7 item 3, the decision of the Architect of 2026-10-28, P1; line 20 of the list);
          reception: hash while reading; PEER_FAILS; the copy door exists only for the key `<sub>/blobs/sha256-<64 lowercase hex>`
          of a subsystem with a blob field; another key (uppercase hex, without `sha256-`, a subsystem without a blob field) — an ordinary object,
          its owner writes it: 405 (reconciliation of python and go M10/6–11, T11)
```
