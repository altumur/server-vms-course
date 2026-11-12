# Console module — lesson P/07

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

A micromodule: a JS library. What it norms and from where — the module design note `Platform/module-design.md` (judge-only: for people, not in the export), the table «Lessons».

The layout of the catalogue (the English source on the canonical path, the Russian text for people in `ru/`). The lesson has one chapter; it has no HTTP contract, life cycle, families,
vectors or acceptance catalogue of its own: the doors the module calls are the contract of lesson P/06, the publication of the module is chapter
6.5 and its acceptance (sc. 01):

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
| [`02-installer/spec/02.1-installer.norms.md`](../02-installer/spec/02.1-installer.norms.md) | [N1.2a Summary table of keys](../02-installer/spec/02.1-installer.norms.md#n12a-summary-table-of-keys) | platform door names used to recognize a table |
| [`02-installer/spec/02.2-installer.norms.md`](../02-installer/spec/02.2-installer.norms.md) | [N1.2 View row](../02-installer/spec/02.2-installer.norms.md#n12-view-row) | the manifest view and writes_via |
| [`03-worker/spec/03.6-worker.norms.md`](../03-worker/spec/03.6-worker.norms.md) | [holder's look (the worker, on a pass; ≤ REQUESTS_HOLD, ≤ COMMANDS_PER_LOOK)](../03-worker/spec/03.6-worker.norms.md#holders-look-the-worker-on-a-pass--requests_hold--commands_per_look) | the writer of command event fields |
| [`06-console/spec/06-console.api.openapi.yaml`](../06-console/spec/06-console.api.openapi.yaml) | the whole contract | the called HTTP doors, response types, WorkerRow and FieldView.hidden |
| [`06-console/spec/06-console.README.md`](../06-console/spec/06-console.README.md) | [Chapter 6.5: the given form of `GET /manifest` and `Where`](../06-console/spec/06-console.README.md#chapter-65-the-given-form-of-get-manifest-and-where) | checking the HTTP Where door independently of the library |
| [`06-console/spec/06.1-console.norms.md`](../06-console/spec/06.1-console.norms.md) | [N1.1a Writing only by a ticket: `writes_via`](../06-console/spec/06.1-console.norms.md#n11a-writing-only-by-a-ticket-writes_via); [Refusal: `error` and `field`](../06-console/spec/06.1-console.norms.md#refusal-error-and-field); [Versions: `revision`, index, `ETag`, `If-Match`](../06-console/spec/06.1-console.norms.md#versions-revision-index-etag-if-match); [Change feed](../06-console/spec/06.1-console.norms.md#change-feed); [repeat memory — the write doors of people](../06-console/spec/06.1-console.norms.md#repeat-memory--the-write-doors-of-people) | unit/table writes, versions, field refusals, feed and replay ownership |
| [`06-console/spec/06.3-console.norms.md`](../06-console/spec/06.3-console.norms.md) | [N1.3 The gate](../06-console/spec/06.3-console.norms.md#n13-the-gate) | session, login and the gate |
| [`06-console/spec/06.4-console.norms.md`](../06-console/spec/06.4-console.norms.md) | [N1.5 Request](../06-console/spec/06.4-console.norms.md#n15-request) | page-owned requests through console.api |
| [`06-console/spec/06.5-console.norms.md`](../06-console/spec/06.5-console.norms.md) | [N1.1 Three parts](../06-console/spec/06.5-console.norms.md#n11-three-parts); [N1.2 `display`, `servers`, `console`](../06-console/spec/06.5-console.norms.md#n12-display-servers-console); [N2 Doors](../06-console/spec/06.5-console.norms.md#n2-doors); [Static files of a subsystem](../06-console/spec/06.5-console.norms.md#static-files-of-a-subsystem); [N4 Refusals](../06-console/spec/06.5-console.norms.md#n4-refusals) | module bytes, mount options, display, observations, publication and version refusals |
| [`06-console/spec/06.7-console.norms.md`](../06-console/spec/06.7-console.norms.md) | [N1.12 `GET /api/held` at the cluster console](../06-console/spec/06.7-console.norms.md#n112-get-apiheld-at-the-cluster-console); [N1.13 `GET /api/backup` at the cluster console](../06-console/spec/06.7-console.norms.md#n113-get-apibackup-at-the-cluster-console); [N2 Doors](../06-console/spec/06.7-console.norms.md#n2-doors) | domain forwarding, held/shared and the backup door excluded from the module |
| [`06-console/spec/06.8-console.norms.md`](../06-console/spec/06.8-console.norms.md) | [N2 Doors](../06-console/spec/06.8-console.norms.md#n2-doors); [N3 Procedures](../06-console/spec/06.8-console.norms.md#n3-procedures) | folder routes, quoted store-index CAS and folder rights |
| [`06-console/acceptance/5/README.md`](../06-console/acceptance/5/README.md) | [Stand: observations](../06-console/acceptance/5/README.md#stand-observations) | scenario 01 checks packaging and ?v=1; scenario 04 checks HTTP Where (judge-only: these scenarios); P/07-R266, P/07-01 and P/07-02 name the module/publication boundary |
| [`08-domain/spec/08-domain.api.openapi.yaml`](../08-domain/spec/08-domain.api.openapi.yaml) | the whole contract | domain door forms and ServedView.unread |
| [`08-domain/spec/08.4-domain.norms.md`](../08-domain/spec/08.4-domain.norms.md) | [N1.2 Login, person token, revocation](../08-domain/spec/08.4-domain.norms.md#n12-login-person-token-revocation) | login_url and POST /api/login |
| [`08-domain/spec/08.6-domain.norms.md`](../08-domain/spec/08.6-domain.norms.md) | [N2 Doors](../08-domain/spec/08.6-domain.norms.md#n2-doors) | record revision for domain placement CAS |
| [`08-domain/spec/08.8-domain.norms.md`](../08-domain/spec/08.8-domain.norms.md) | [N1.3 The holder's view: the field `term`](../08-domain/spec/08.8-domain.norms.md#n13-the-holders-view-the-field-term); [N1.7 The planned handover](../08-domain/spec/08.8-domain.norms.md#n17-the-planned-handover) | holder term, backup pairs, backup_holders and handover |
| [`08-domain/acceptance/4/README.md`](../08-domain/acceptance/4/README.md) | [scenarios.tsv](../08-domain/acceptance/4/README.md#scenariostsv) | people-door acceptance (judge-only: scenarios of chapter 8.4); module rights follow P/07-R110 |
| [`09-agent/spec/09.1-agent.norms.md`](../09-agent/spec/09.1-agent.norms.md) | [follow (the member's agent, in every pass before the report)](../09-agent/spec/09.1-agent.norms.md#follow-the-members-agent-in-every-pass-before-the-report) | member-agent following in the public-surface description |
| [`10-domain-console/spec/10-domain-console.api.openapi.yaml`](../10-domain-console/spec/10-domain-console.api.openapi.yaml) | the whole contract | domain-console HTTP doors |
| [`10-domain-console/spec/10-domain-console.norms.md`](../10-domain-console/spec/10-domain-console.norms.md) | [N1.2 The read doors — it answers itself](../10-domain-console/spec/10-domain-console.norms.md#n12-the-read-doors--it-answers-itself); [N1.7 The holder's page](../10-domain-console/spec/10-domain-console.norms.md#n17-the-holders-page); [N1.8 The alarm list at the holder](../10-domain-console/spec/10-domain-console.norms.md#n18-the-alarm-list-at-the-holder); [N2 Doors](../10-domain-console/spec/10-domain-console.norms.md#n2-doors) | opaque domain pages and unread, holder page, alarms and shared schema |
| `Platform/module-design.md` (judge-only: human design note outside the export) | «Lessons» | P/07 within the course; the library boundary is P/07-R249 |
| `Source/tests/console`, including `module-*.test.js` and `platform-page.test.js` (judge-only: owner tests outside model input) | Subjects of N5 | Evidence for P/07-R265 and P/07-01…08; a generation line checks packaging by P/07-R266 |
