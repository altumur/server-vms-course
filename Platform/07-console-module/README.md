# Console module — lesson P/07

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

A micromodule: a JS library. What it norms and from where — the module design note `Platform/module-design.md` (judge-only: human design note outside the export), the table «Lessons».

The layout of the catalogue (the English source on the canonical path, the Russian text for people in `ru/`). The lesson has one chapter; it has no HTTP contract, life cycle, families,
vectors or acceptance catalogue of its own: the doors the module calls are the contract of lesson P/06, the publication of the module is chapter
6.5; the publication check is P/07-R264:

```text
README.md                                this file
spec/07-console-module.norms.md          norms (one chapter; N2 — the library contract)
spec/07-console-module.README.md         implementation instructions
ru/                                      for people, not in the export — the lecture ru/07-console-module.md, translations of the English text by the same path
```

## What this lesson takes from common

The following common contracts and earlier/later lesson interfaces are the external inputs named by the norms, instructions and public-surface description. The table identifies existing rules; it adds no module behaviour.

| File | Sections | Used here |
|---|---|---|
| [`common/NORMATIVE-TERMS.md`](../common/NORMATIVE-TERMS.md) | the whole contract | normative words |
| [`common/contracts/may.md`](../common/contracts/may.md) | [The function `may`](../common/contracts/may.md#the-function-may) | session grants, scopes, group tiers and unknown folder input |
| [`common/contracts/forwarding.md`](../common/contracts/forwarding.md) | [Domain doors](../common/contracts/forwarding.md#domain-doors) | the closed domain door list and forwarding |
| [`common/contracts/gate-and-pass.md`](../common/contracts/gate-and-pass.md) | [The gate](../common/contracts/gate-and-pass.md#the-gate) | session and login_url |
| [`01-store/spec/01.1-store.norms.md`](../01-store/spec/01.1-store.norms.md) | [N0 Vocabulary](../01-store/spec/01.1-store.norms.md#n0-vocabulary) | the common rules of the module |
| [`02-installer/spec/02.1-installer.norms.md`](../02-installer/spec/02.1-installer.norms.md) | [N1.2a Summary table of keys](../02-installer/spec/02.1-installer.norms.md#n12a-summary-table-of-keys); [N1.2b The section `domain` — a chapter of the late layer: introduced by lesson 8 (P/08.K); the loader holds the corpus whole](../02-installer/spec/02.1-installer.norms.md#n12b-the-section-domain--a-chapter-of-the-late-layer-introduced-by-lesson-8-p08k-the-loader-holds-the-corpus-whole) | platform door names used to recognize a table |
| [`02-installer/spec/02.2-installer.norms.md`](../02-installer/spec/02.2-installer.norms.md) | [N1.2 View row](../02-installer/spec/02.2-installer.norms.md#n12-view-row) | the manifest view and writes_via |
| [`03-worker/spec/03.6-worker.norms.md`](../03-worker/spec/03.6-worker.norms.md) | [holder's look (the worker, on a pass; ≤ REQUESTS_HOLD, ≤ COMMANDS_PER_LOOK)](../03-worker/spec/03.6-worker.norms.md#holders-look-the-worker-on-a-pass--requests_hold--commands_per_look) | the writer of command event fields |
| [`06-console/spec/06-console.api.openapi.yaml`](../06-console/spec/06-console.api.openapi.yaml) | the whole contract | the called HTTP doors, response types, WorkerRow and FieldView.hidden |
| [`06-console/spec/06-console.README.md`](../06-console/spec/06-console.README.md) | [Chapter 6.5: the given form of `GET /manifest` and `Where`](../06-console/spec/06-console.README.md#chapter-65-the-given-form-of-get-manifest-and-where) | checking the HTTP Where door independently of the library |
| [`06-console/spec/06.1-console.norms.md`](../06-console/spec/06.1-console.norms.md) | [N1.1a Writing only by a ticket: `writes_via`](../06-console/spec/06.1-console.norms.md#n11a-writing-only-by-a-ticket-writes_via); [Refusal: `error` and `field`](../06-console/spec/06.1-console.norms.md#refusal-error-and-field); [Versions: `revision`, index, `ETag`, `If-Match`](../06-console/spec/06.1-console.norms.md#versions-revision-index-etag-if-match); [Change feed](../06-console/spec/06.1-console.norms.md#change-feed); [repeat memory — the write doors of people](../06-console/spec/06.1-console.norms.md#repeat-memory--the-write-doors-of-people) | unit/table writes, versions, field refusals, feed and replay ownership |
| [`06-console/spec/06.3-console.norms.md`](../06-console/spec/06.3-console.norms.md) | [N1.3 The gate](../06-console/spec/06.3-console.norms.md#n13-the-gate) | session, login and the gate |
| [`06-console/spec/06.4-console.norms.md`](../06-console/spec/06.4-console.norms.md) | [N1.5 Request](../06-console/spec/06.4-console.norms.md#n15-request) | page-owned requests through console.api |
| [`06-console/spec/06.5-console.norms.md`](../06-console/spec/06.5-console.norms.md) | [N1.1 Three parts](../06-console/spec/06.5-console.norms.md#n11-three-parts); [N1.2 `display`, `servers`, `console`](../06-console/spec/06.5-console.norms.md#n12-display-servers-console); [N2 Doors](../06-console/spec/06.5-console.norms.md#n2-doors); [Static files of a subsystem](../06-console/spec/06.5-console.norms.md#static-files-of-a-subsystem); [N4 Refusals](../06-console/spec/06.5-console.norms.md#n4-refusals) | module bytes, mount options, display, observations, publication and version refusals |
| [`06-console/spec/06.6-console.norms.md`](../06-console/spec/06.6-console.norms.md) | [N1.1 Console rows](../06-console/spec/06.6-console.norms.md#n11-console-rows); [N1.1a Schema](../06-console/spec/06.6-console.norms.md#n11a-schema); [N1.2 Drain](../06-console/spec/06.6-console.norms.md#n12-drain); [N2.1 Inputs](../06-console/spec/06.6-console.norms.md#n21-inputs) | settings, policy, schema, drain and settings-door CAS |
| [`06-console/spec/06.7-console.norms.md`](../06-console/spec/06.7-console.norms.md) | [N1.12 `GET /api/held` at the cluster console](../06-console/spec/06.7-console.norms.md#n112-get-apiheld-at-the-cluster-console); [N1.13 `GET /api/backup` at the cluster console](../06-console/spec/06.7-console.norms.md#n113-get-apibackup-at-the-cluster-console); [N2 Doors](../06-console/spec/06.7-console.norms.md#n2-doors); [N1.8 Forwarding to the signer](../06-console/spec/06.7-console.norms.md#n18-forwarding-to-the-signer); [N1.11 Domain key families, `/domain/keys`](../06-console/spec/06.7-console.norms.md#n111-domain-key-families-domainkeys) | domain forwarding, held/shared and the backup door excluded from the module |
| [`06-console/spec/06.8-console.norms.md`](../06-console/spec/06.8-console.norms.md) | [N2 Doors](../06-console/spec/06.8-console.norms.md#n2-doors); [N3 Procedures](../06-console/spec/06.8-console.norms.md#n3-procedures) | folder routes, quoted store-index CAS and folder rights |
| [`06-console/acceptance/5/README.md`](../06-console/acceptance/5/README.md) | [Stand: observations](../06-console/acceptance/5/README.md#stand-observations) | publication and HTTP Where checks under P/07-R264 and P/07-R130; P/07-R266, P/07-01 and P/07-02 name the module/publication boundary |
| [`08-domain/spec/08-domain.api.openapi.yaml`](../08-domain/spec/08-domain.api.openapi.yaml) | the whole contract | domain door forms and ServedView.unread |
| [`08-domain/spec/08.4-domain.norms.md`](../08-domain/spec/08.4-domain.norms.md) | [N1.2 Login, person token, revocation](../08-domain/spec/08.4-domain.norms.md#n12-login-person-token-revocation) | login_url and POST /api/login |
| [`08-domain/spec/08.6-domain.norms.md`](../08-domain/spec/08.6-domain.norms.md) | [N2 Doors](../08-domain/spec/08.6-domain.norms.md#n2-doors) | record revision for domain placement CAS |
| [`08-domain/spec/08.8-domain.norms.md`](../08-domain/spec/08.8-domain.norms.md) | [N1.3 The holder's view: the field `term`](../08-domain/spec/08.8-domain.norms.md#n13-the-holders-view-the-field-term); [N1.7 The planned handover](../08-domain/spec/08.8-domain.norms.md#n17-the-planned-handover); [N1.8 The emergency move](../08-domain/spec/08.8-domain.norms.md#n18-the-emergency-move) | holder term, backup pairs, backup_holders and handover |
| [`09-agent/spec/09.1-agent.norms.md`](../09-agent/spec/09.1-agent.norms.md) | [follow (the member's agent, in every pass before the report)](../09-agent/spec/09.1-agent.norms.md#follow-the-members-agent-in-every-pass-before-the-report) | member-agent following in the public-surface description |
| [`10-domain-console/spec/10-domain-console.api.openapi.yaml`](../10-domain-console/spec/10-domain-console.api.openapi.yaml) | the whole contract | domain-console HTTP doors |
| [`10-domain-console/spec/10-domain-console.norms.md`](../10-domain-console/spec/10-domain-console.norms.md) | [N1.2 The read doors — it answers itself](../10-domain-console/spec/10-domain-console.norms.md#n12-the-read-doors--it-answers-itself); [N1.7 The holder's page](../10-domain-console/spec/10-domain-console.norms.md#n17-the-holders-page); [N1.8 The alarm list at the holder](../10-domain-console/spec/10-domain-console.norms.md#n18-the-alarm-list-at-the-holder); [N2 Doors](../10-domain-console/spec/10-domain-console.norms.md#n2-doors) | opaque domain pages and unread, holder page, alarms and shared schema |
