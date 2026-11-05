# Delta 0125-p01-box-observations — Status row ceiling and metric presentation (P/01)

change: 0125-p01-box-observations rev 1. English source of P/01, delta_base 725653954; assembled tree base 286db071c4fd915df1eca1c929793f47f4c162d9.
Units and hashes follow ADR-0122 addendum (1) item 1: LF, trailing spaces stripped, one final LF.
The OpenAPI description is a machine artifact addressed by component/property in the manifest, without a shape change.

## ADDED

### `Platform/01-store/spec/01.3-store.norms.md` — after P/01.3-R006, before P/01.3-R007

<!-- req: P/01.3-R032 -->
**Metric presentation (C01-BOX-OBSERVATIONS-01).** `configstore_raft_state` is a gauge: the current state has value 1; other state samples, when emitted, have value 0. The label is lowercase (`leader`, `follower`, `candidate`, `shutdown`), as in sc. 17; `Status.state` keeps its separate Leader/Follower/Candidate/Shutdown/Door spelling. Emitting only the current-state sample or also zero-valued other states is an implementation choice. A box emits `state="leader"` with value 1. A door without a vote keeps its own series and emits no Raft series, as above. `# TYPE` metadata is optional; when present, `configstore_raft_elections_total` and `configstore_door_forwards_total` have type counter, the other listed series type gauge. The existing series names, label escaping and required observations remain unchanged.

## MODIFIED

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R016 — service door table, Status.max_value

old-sha256: 38dbb897ac549b55e341a810f1c49fa73ba41302e463f95a10e06664235ac01e

<!-- req: P/01.3-R016 -->
| HTTP door | Full form / rule |
|---|---|
| GET `/v1/status` | `{id, state, leader, leader_id, term, commit, applied, voters, members, tls, max_value}`; optional `base, again, role, last_snapshot, out, admission_ahead` (Н1.3 `admission`; ADR-0091 item 1). Indices are exact uint64, state — Leader/Follower/Candidate/Shutdown/Door; voters/out — an array of ids, members — a map id → `-api` address, without `-api` the member is not in `members` (the map can be `{}`; a value is never empty — `minLength: 1` of OpenAPI; C01-STATUS-MEMBERS-NOAPI, the Architect's decision of 2026-10-26); `leader` — the `-api` address of the leader (empty if the leader is unknown or was started without `-api`), `leader_id` — the id of the leader (empty if the leader is unknown) (the store pilot, А7). Door requires role=door and term/commit/applied=0. `max_value` is this instance’s effective row-weight ceiling in bytes, the value of `-max-value` (Н1.3; the row weight of chapter 1.1), separately from `-max-body`; on the acceptance stand it is 524288. This is a local observation, not a confirmation by the majority |
| POST `/v1/join` | `{id, raft, api, force?}`, success 200 `{}`; 409 `{kind: refused, error}` — an inadmissible membership; 403 — `ForbiddenFault` of chapter 1.1: it is called only by `admin.sock` and a daemon of the group over mTLS of the role `configstore` (Н1.3 `identity`); a role socket (`console.sock` and others) — 403 before parsing the membership (reconciliation of python and go М10/6–11, B1); empty `raft`, `api` — 400 before the membership (B4) |
| POST `/v1/leave` | `{id}` (an empty string — oneself), success 200 `{}`; a role socket — 403, as for join (B1); a change of another's membership — only through admin.sock (`leave [id]` of admin_ops Н1.3); for a box without raft the leaving of the last voter — 409 `{kind: refused, error}` «the last voter» (Н1.3 `box`) |
| GET `/v1/rights` | The exact form and the refusals of chapter 1.2, availability admin/role/forwarding by its Н3 |
| POST `/v1/write` | An ordinary Cmd of chapter 1.1, a batch BatchCmd of chapter 1.1 or `{op: floor, floor: integer 1 … 2^53 − 2^32, id: 1–64 lowercase hex}` on admin.sock of the leader. A replay of floor with the same id returns the saved outcome — the replay memory is the same as for a write with id (chapter 1.1 Н3 «Replay by identifier»): in the store, with its durability and the same lifetimes — a durable one survives a daemon restart, a non-durable teaching one («Implementation decides» item 2) loses at a restart both the floor and the memory, and says so in its description; another payload with this id — a refusal 400 badrequest of chapter 1.1 (not a CAS conflict); a new id with floor ≤ the current one — 409 refused (a row of chapter 1.1 Н4). Success — Written of chapter 1.1. An ordinary write of floor through put/delete is forbidden |
| GET `/metrics` | The list of text series of Н1.3; correct escaping of labels |

## REMOVED

(none)
