# The right contract: the function `may`, refusal words

This English text is the source; the Russian translation `ru/contracts/may.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (13) and addendum (14): a common algorithm of several processes is a contract, not
copies in chapters; the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 1; analysis of review of stage A 8–10). The owner is lesson
P/08, [chapter 8.4](../../08-domain/spec/08.4-domain.norms.md) (N1.4 is a pointer here): people, grants and
the right by grants. The function `may` is performed by:

| Who | Where | `grants`, `as_of`, `disabled` |
|---|---|---|
| the cluster console ([P/06.3](../../06-console/spec/06.3-console.norms.md) N1.3 `identity` step 3, `need`; chapter 6.7 — a session with grants) | [P/06.7](../../06-console/spec/06.7-console.norms.md) N1.9 `cluster`, `session` (effective lines — step 5) | the copy of `domain/grants` of this cluster and its `as_of`; `domain/disabled` of this store |
| the domain console ([lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.5) and the process `domain` (8.4) | [P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.5 `domain`; N3 «people door» step 2, «grants» step 1 | `domain/grants/domain`, `as_of` — `null`; `roles` — from the role and group rows of the holder (P/08.4 N1.3 `roles_at_holder`) |

Where the cluster console gets the input `roles` — the copy of the role table `domain/roles` and its tie with the copy of the grants: [P/06.7](../../06-console/spec/06.7-console.norms.md) N1.9 `cluster`, [the gate-and-pass contract](gate-and-pass.md) «The gate with grants» (ADR-0098 §4).

Step 5 (effective lines) is also read by the delivery of a book by grant ([P/08.5](../../08-domain/spec/08.5-domain.norms.md)
N1.3 `grant`) and by the name index (P/08.5 N1.7 `delivery`): `sub` is the subsystem of the book, only the direct group; the `role:` lines and
the role table do not take part (ADR-0097 §4, ADR-0098 §4); the console module computes a hint by the same groups and tiers
([P/07](../../07-console-module/spec/07-console-module.norms.md) N1.5 `may`), the server always checks.

Steps 1–8 are moved from M11/9 N1.4 (input, output) and N4 (the words of `may`); the step numbers are the former ones, steps 4a, 7a–7c were added by ADR-0098–ADR-0100. The
owner keeps: the grant line ([P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.3: `lines`, `line`, the ranks of `cap` — `none < view < edit < admin`, `sub`, `scope`,
`until`, `GRANT_LIFETIME`, `unreadable` — the value and the input rule are repeated below, «The function `may`»; the member's copy — [P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.4), the check at the process
`domain` and what the door answers on `deny` (P/08.4 N1.5: 403 `denied`, `detail` at `stale`), the break-glass account at the holder
(P/08.4 N1.6); the gate with grants and the break-glass entry at the cluster console — P/06.7 N1.9, N1.10, at the domain console — P/10 N1.5. The reference
«N1.6» in the moved text is M11/9 N1.6, now P/06.7 N1.10 (the break-glass session of the console); `rank` is the order of `cap` of
P/08.4 N1.3; labels — the [labels alphabet contract](labels.md).

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## Form

Inputs of the function: `grants` — the copy of `domain/grants` of a member, and `domain/grants/domain` at the domain console and the process `domain` — `Platform/09-agent/data/grants.schema.json`, `Platform/09-agent/data/grants.outcomes.tsv`; `Platform/08-domain/data/grants.schema.json`, `Platform/08-domain/data/grants.outcomes.tsv`; `disabled` — the row `domain/disabled`: `Platform/08-domain/data/disabled.schema.json`, `Platform/08-domain/data/disabled.outcomes.tsv` (layout audit, V-36, V-37; the Architect's decision of 2026-10-25); `roles` at the cluster console — the member's copy of `domain/roles`: `Platform/09-agent/data/roles.schema.json`, `Platform/09-agent/data/roles.outcomes.tsv`; at the domain console and the process `domain` — the rows `domain/roles/<name>` and `domain/groups/<name>`: `Platform/08-domain/data/roles.schema.json`, `Platform/08-domain/data/groups.schema.json` with their outcome tables.

## The function `may`

From M11/9 N1.4 «The right — the function `may`»:

```yaml
input:     {grants: <doc {lines}> | null, as_of: <count> | null, disabled: [<name>…], user, glass, cap, unit, now,
            sub?, roles?, unread?, iat?, anywhere?, as_role?}
  unit:    null — a door without a unit; "*" — the right to everything; "any" — the domain's judgement by the target cluster: at least one line of the needed rank, the scope is not
           judged («Judgement by target» below); {sub, id, labels: [<label>…], about?, chains?}
  about:   {sub, id, labels, chains?} — the about unit; "unknown" — about is needed but unknown (the unit's row is unreadable or
           the read is not confirmed); no field — the unit has no about; the value of the field about.field in the row is empty or the field is
           absent from the row — the same: no about, the unit is judged by itself (C02-ABOUT-EMPTY-01)
  chains:  [[F, parent of F, …, root folder]…] — one chain for each membership, only live ones: a link without a tombstone and the whole
           chain up to the root is live (ADR-0097 §5, ADR-0099 §2); [] — it is confirmed that there are no folders; "unknown" or no field — the membership,
           a link of a chain or its liveness was not read
           a folder as the object of a write — unit {sub: platform, id: <F>, labels: [], chains: [[F, ancestors of F]]}; unit: and labels: do not
           cover it, only tiers 3 and 4 (ADR-0097 §5); creating a root folder — unit "*"
  disabled: the row domain/disabled is read only while domain/holder of its own store names this cluster, otherwise [] : the row of a former holder is stale and is not updated; no term record or it is unreadable — the row is read, the stricter way: a former holder always has the record, it is absent only before `claim` and in a break of admission; the condition is common to all readers (C08-DISABLED-FORMER-01, C08-DISABLED-NO-RECORD-01)
  glass:   true — a session of the break-glass entry (N1.6); for it the caller reads neither grants nor disabled (step 1 decides earlier) —
           their unreadability does not stop it (C06-GLASS-UNREADABLE-01, the Architect's decision of 2026-10-28)
  until:   until of a grant line — the same finiteness check as for now and as_of (the time canon P/01.1 N0: the value is finite in
           binary64); does not fit — the input is out of form, code 2, before step 1 (glass); at the reader of the grants document —
           a grant line out of form, an outcome of the family grants (MAY-UNTIL-D8-01, the Architect's decision of 2026-10-25)
  sub:     a subsystem name (the grammar P/02.1 N1.2 name), platform or null; no field — null. The subsystem of the check, not of the unit:
           a check of the subsystem testsub2 over a unit of testsub — unit {sub: testsub, id: c1}, sub: testsub2. Who names it and how — the gate-and-pass contract
           «Subsystem of the check»; null — only the pre-check before the body and the reading «any grant» (ADR-0097 §2)
  roles:   a table {<name>: [{role, until, at}…]}, expanded by the caller down to the pointer «person → roles»; null or no field —
           the member has no table: role lines do not apply, this is a checked absence; "unreadable" — the copy of the table does not read,
           the fingerprint did not match or as_of of the table did not pass step 4 (ADR-0098 §4). One role of a person twice (directly and through
           a group) — one element: the later until (0 — later than all) (ADR-0098 §4)
    at:    from what moment the admin assignment applies: at the cluster console — admin_at of the table, at the holder — the same rule (P/08.4 N1.3b);
           for other roles 0, nobody reads their at
  unread:  which role groups the caller saw incomplete: [{role: <R>, sub?: <S>}…] — a line of this role is out of form, the subject
           did read (sub — if it read too: then only in this sub); "all" — the subject of the line did not read: incomplete are all
           role groups of the document; no field — []. The caller drops an unreadable line (lines_in) but does not lose the sign (ADR-0099 §2)
  anywhere: {<person>: <until>} — who has a grant in any cluster of the domain (P/08.4 N1.3 anywhere); only for step 6 and only at the door
           door.pass of the second kind and at the view doors of the domain; no field — {}
  as_role: a role name: a check of an action as a role, there is no person (ADR-0105 item 4; the section «Action as a role»); no field — a person
  iat:     iat of the request token; on the path of a ticket and of an operation step — iat of the ticket record, the token is the same (the gate-and-pass contract «Pass of the second kind»); null — only sessions without a token: glass, the debug identity; no field — null; needed only by step 4a:
           a token issued before at of the admin assignment does not serve step 4a (ADR-0100 §3); the comparison is by whole seconds: at carries up to
           three digits of fraction, iat of a token — any finite number
output:    {result: allow} | {result: deny, reason: disabled | stale | no_grant} | {result: unavailable}
           unavailable — the door answers 503 unavailable, not 403 (the rule «Unreadable row» of the gate-and-pass contract)
```

```
1. glass                                                                → allow
2. user ∈ disabled                                                      → deny disabled
3. grants = null and (unit ≠ null or user is not in anywhere)           → deny no_grant
4. as_of ≠ null and now − as_of > GRANT_LIFETIME                        → deny stale
4a. roles[user] has {role: admin, until: t, at}, t = 0 or now < t, and iat = null or ⌊iat⌋ ≥ ⌊at⌋ → allow
5. selection: a line is effective if until = 0 or now < until, and the line has no sub, or it equals sub of the input, or sub of the input = null.
   the direct group — effective lines with subject = user;
   role groups — one for each {role: R, until: t} of roles[user], R ≠ admin, t = 0 or now < t: effective lines with
   subject = role:R; lines of a role not in roles[user] do not apply (ADR-0097 §2, ADR-0098 §4, ADR-0099 §2)
6. unit = null and cap = view: at least one line of the direct group or of a role group whose cap ≠ none,
   or anywhere[user] = 0, or now < anywhere[user]                       → allow
6a. unit = "any": at least one line of the direct group or of a role group with rank(cap of the line) ≥ rank(cap) → allow; otherwise step 7b, then step 8
7. the direct group: a line with rank(cap of the line) ≥ rank(cap) whose scope covers unit → allow
   * — any (and "*"); unit:<s>/<i> — a unit with (sub, id) = (s, i) or its about with (s, i); labels:L — all labels L at about, if
   there is about, otherwise at the unit itself; folder:<id> — id is in a chain of chains at the unit or at about;
   null and "*" are covered by no scope except *; a folder object (unit.sub = platform) is covered neither by unit: nor by labels:;
   about "unknown" and chains "unknown" — a line that needs them does not cover, the next one is checked (not 503)
7a. a role group gives a level ≥ rank(cap) (the level of a group — below) → allow
7b. roles = "unreadable"                                                → unavailable
7c. there is an «unreadable» role group that could allow (below)        → unavailable
8.                                                                      → deny no_grant
```

**The level of a role group** for the check `(cap, unit, sub)` (ADR-0099 §2). The group takes the **first tier** where it has a line
covering the unit; the level is the greatest `cap` of the lines of this tier (`none < view`). `none` and a positive line of one tier,
including of one scope, give the positive one. A chain without a line of the group gives nothing to tier 3.

| Tier | Lines |
|---|---|
| 1 | `unit:` — the unit itself |
| 2 | `unit:` — its about unit |
| 3 | `folder:` — the nearest folders: in each chain of `unit.chains` and `about.chains` the first folder on which the group has a line from the selection of step 5 (the rank is not looked at in the choice); the tier is the lines of these folders over all chains |
| 4 | `*` |

`unit = "*"` and `unit = null` are covered only by tier 4; a folder object — by tiers 3 and 4 along its chain. No tier covers — the group
gives no level. An expired line did not get into the selection and takes no part in a tier: an expired `none` on a unit — the folder tier applies.

**An unreadable group** (ADR-0099 §2). A role group does not go down to a less precise tier if a more precise one cannot be computed. A group
is «unreadable» from tier `k`:
- `k = 1` — the role is named in `unread` (without `sub` or with `sub` of the input) or `unread = "all"`;
- `k = 2` — tier 1 is empty, `about` = `"unknown"`, the group has a `unit:` line;
- `k = 3` — tiers 1–2 are empty, the group has a `folder:` line, and `unit.chains` are unknown, or `about.chains` are unknown, or `about` = `"unknown"`.

Such a group gives no level. It could allow (step 7c) — there is a line of it from the selection of step 5 with a rank ≥ `cap` in the tiers from `k` and
below: for `k = 1` — any; for `k = 2` — `unit:`, `folder:`, `*`; for `k = 3` — `folder:`, `*`.

**Cut-off** (ADR-0099 §2): tier `k = 3` is not «unreadable» if the result does not depend on the membership. All `folder:` lines of the group
in the selection have a rank ≥ `cap`, and tier 4 gives a level ≥ `cap` — step 7a allows; all are below `cap`, and tier 4 does not allow — the group does not
allow and is not counted in step 7c. The caller then does not read the membership.

The direct group only adds up lines, it has no exceptions. `none` occurs only in role lines. The role `admin` has no lines
(step 4a) and forms no groups: exceptions of other roles do not act on it (ADR-0100 §1). Step 7b also applies when there are no matching
`role:` lines: an unreadable table could carry an `admin` assignment (ADR-0100 §1). Lists give `withheld` instead of `unavailable` (P/06.4).

The constant and the input of lines (from P/08.4 N1.3 `GRANT_LIFETIME`, `unreadable` and N5 `exit` without a change of behaviour; the owner of the
text is P/08.4; analysis of review of stage B 8–10, № 4, Claude `S-7`):

```yaml
GRANT_LIFETIME: 86400   # s — step 4: a member's copy older than as_of + GRANT_LIFETIME gives no rights
lines_in:       the function gets only lines of lines in the form of P/08.4 N1.3 (the family files — Platform/09-agent/data/grants.schema.json,
                grants.outcomes.tsv; C04-DEP-OBS-HEARTBEAT-01): an unreadable line is dropped by the caller before the
                call — a skip with diagnostics at the member's door over the copy from the holder's answer (P/08.4 N1.3 unreadable;
                the copy — P/09.1 N1.4 member_copy, holder_copy); a line out of form in the input of the function — the input is out of form, exit
                code 2, not a skip (P/08.4 N5 exit). There is no contradiction between «is skipped» (N1.3) and «2, not a skip» (N5): the skip
                is at the caller, code 2 is at the function
```

Which input is out of form (the `grants` lines are a trusted input) — [the native input form](may-input.md#may) (MAY-G01/G02); the exit codes of the command `may` are a copy of [P/08.4](../../08-domain/spec/08.4-domain.norms.md) N5 `exit` (layout audit, the Architect's decision of 2026-10-25, B-14):

```yaml
exit:      0 — computed; 2 — the input is out of form; exit codes follow the principle of the vocabulary of «Domain stand» («Exit codes of vector commands»: 2 — the form
           of a trusted input, 0 with a word — a document of another cluster; the Architect's decision on the M11 reconciliation, H14):
           the grants lines of may are a trusted input (a copy already parsed by N1.3), so a line out of form is 2, not a skip
```

## Judgement by target

The domain door judges a record of a cluster by the grant of this cluster, not by `domain/grants/domain` (ADR-0110 addendum (4) item 4, addendum (5) items 1, 5; D-1, D-2, D-8 of the analysis). Otherwise a person with a grant only on a cluster would get an empty domain.

```yaml
wide:      may(grants = domain/grants/domain, cap = view, unit = "*", sub = null) = allow — a viewer of the domain: no filter, the answer is whole;
           the group of the manager line (P/08.4 N1.3c manager) does not count here: it gives no rights in clusters
gate:      the entry of the view doors: wide, or may(grants = null, unit = null, cap = view, sub = null, anywhere = the row domain/anywhere of the holder);
           otherwise 403 by refusal; the row exists but does not read, and wide was not enough — 503 unavailable
target:    a record of cluster C: may(grants = domain/grants/C, as_of = null, disabled and roles — at the holder, as for the row domain, iat — of the token,
           sub — the subsystem of the record); no row domain/grants/C — grants = null
read:      each record is judged separately, cap = view:
  unit:    {sub, id, labels, about?, chains} — from the view (P/08.1 N1.4): labels — Unit.labels, none — [] and the input is incomplete; about — Unit.about and the unit with this id in
           the same copy: found — {sub, id, labels}, not found — "unknown"; a manifest without about has no field; chains — from domain/memberof and domain/folders (P/08.5 N1.8), does not read — "unknown"
  row:     a row of a table snapshot (P/04 N1.3b): a unit row — {sub, id: key, labels, about?} from the fields of the snapshot row, as unit above; a table in rights.unit_of —
           unit of the unit from its field (link 150 keeps the field in the list), no value — unit = "*"; otherwise unit = null, as GET of a table at the console
  allow:   the record is in the answer; deny — no record; unavailable — no record, the count withheld of the answer
  partial: deny with an incomplete input (no labels, about or chains "unknown"), and the person has in C an effective line labels:, folder: or unit: not on
           the unit itself which this input could cover: the record is hidden and counted in withheld: «I do not see» differs from «there is none»
write:     an edit of a record of cluster C: wide with cap = admin and unit = "*", or may(unit = "any", cap — need of the console door of this row: at PUT and DELETE of a unit admin, at POST and tables — by rights.routes, otherwise admin, sub — the subsystem of the record) by C;
           a bundle — each row by its own sub.
           Judgement before the search: the person has no edit line in any cluster — 403 before find; a cluster is found, the judgement did not pass — 403 without names of
           clusters; contested and executors name clusters only to a viewer of the domain. This is a rough check: scopes, about, chains, routes, unit_of, names the domain does not count, it has no lines of the member.
           The exact judgement is at the member's console on application, by the person whose edit it is; a refusal is the outcome refused
           (P/09.1 N1.5; P/08.6 N1.4). One judgement per edit, whatever entry it came through
cost:      may is computed per record, but the input changes only with the cluster and the person: with the memory of the door pass grants need not be recomputed
```

## Action as a role

The evaluator `auto` executes a rule as the role `runAsRoleId` (ADR-0105 item 4): there is no person in the request, the right of the role to the target is judged. A role is not a person, so the input is special.

```yaml
input:     as_role: R; user — "", glass — false, disabled — [], iat — null; roles is not read
steps:     steps 1, 2, 4a do not apply; steps 3, 4 — as they are; step 5: there is no direct group, one role group R with until 0; then tiers, steps 6, 7a, 7c, 8; step 7b does not apply
admin:     R = admin → deny no_grant: the built-in role has no lines, step 4a is only for a person (ADR-0100 §1)
who:       the worker in its own process, grants — the copy of domain/grants of the cluster, as_of — its own; no row or older than GRANT_LIFETIME — a refusal, as for a person: the action is not executed, a journal line
reads:     worker.reads: [domain/grants, platform/folders/, platform/memberof/] (P/02.5 N3 step 3); chains and about are assembled by the worker, as by the gate
```

## Refusal words

From M11/9 N4: the words of `may`: `disabled`, `stale`, `no_grant`. The outcome `unavailable` is not a refusal word of `may`: the door answers 503 `{error: "unavailable"}`.

## Vectors

The package [`may`](../vectors/may/README.md) contains 126 rows covering grants, roles, tiers, folder scopes, target judgement and the input form, including 24 inputs of the former M11/9 acceptance (sc. 07). There is also `covers.tsv` with 19 rows of the function `covers(scope, ref, row)` of the gate ([the gate contract](gate-and-pass.md) `scope`; C06-EVENTS-QUERY-UNKNOWN-138-10). The governing function and input-form rules determine outcomes; the detailed named case inputs and answer associations remain judge-only in the package.

