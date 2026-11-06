# Server VMS course

Course material: how to grow an appliance that owns its own truth into a platform — first on one server, then on a cluster, then on a domain of several clusters.

The first two course modules — M8 (a product over a cloud archive) and M9 (the same product as an appliance) — moved to the separate **edge-vms-course**. This course begins where one box becomes several.

---

## Device → Server → Cluster → Domain — then the vendor

The module names describe how the same idea becomes harder three times. The course is built around that idea: **where the truth about the system lives, and how many entities can disagree about it.**

| | The box knows | Truth lives | Who can disagree | The new hard problem |
|---|---|---|---|---|
| **M9 · EdgeVMS** | what it *is* | in the image that booted | nobody: the box is what was flashed onto it | replace the OS under a working product without destroying recordings |
| **M10 · ServerVMS** | what it *should be* | in the database on the box | desired and actual state inside one process | close the gap, and never persist the half that must be derived again |
| **M11 · Cluster** | what it should be, *recorded in cluster raft by one controller* | in each worker's heartbeat from the server running it | **two instances of the same worker** | survive a server failure without letting two writers reach the same archive |
| **M12A · Domain**, **M12B · DomainVMS** | what it should be, *and which cluster holds it* | in each cluster's raft, with a catalogue above the clusters | clusters and their catalogue | a layer that must remain useful while unavailable, and honest when an entire cluster is unreachable |
| **M14 · VendorVMS** | *outside the product's scope* | nowhere on which the product depends | customer and vendor | **keep working when the vendor is unreachable or disappears** |

**Every boundary in this table is a network you have stopped trusting, except one: administration defines it.**

A **cluster** consists of servers close enough to share a recording channel: one LAN, usually one server room. That is a physical boundary. A **domain** consists of clusters under one catalogue, one CA and one set of operators: one customer installation with one cluster or several. That is an administrative boundary. A campus can be one domain, three clusters and three sites; a cloud deployment can be one domain, one cluster and fifty sites. **Sites and clusters intentionally have a many-to-many relationship.** Rented servers in a cloud region form a cluster like any other; this lets M13 offer appliance, cloud and mixed deployments from one codebase.

The rule that makes these two modules different, and on which the explanation above depends:

> **Work moves within its own cluster, never between clusters.** Camera video lives on that cluster's disks. An entire cluster failing is therefore a larger event than a move. The domain's task (M12A) is to report what is unreachable honestly, rather than repair it.

The rule was chosen for archive locality. It also puts the fencing epoch at the right scale: every cluster has its own raft. Two independent arguments arriving at the same boundary are a useful sign that the boundary belongs there.

### Three words the course keeps separate

| | Meaning | Who decides |
|---|---|---|
| ~~**Node**~~ | *retired on 12 September 2026*. The M9 recorder is a process with its own database and disk, distinct from the box. M10 needs no fifth server term: platform stores, a **resource** on its disks, and the **workers** placed there by the scheduler. M9 lessons 5–9 retain the word as history | — |
| **Server** | a box with CPUs and disks: a cluster-store replica, a **resource** (the platform's work on those disks), the **workers** held there by the server's service units, and spares started for a shortage | deployment: service units and the spare-worker script |
| **Site** | where the cameras are physically located; the only one of these terms named by the operator | the customer's building |

**A worker is not a server.** M9 builds one box and never needs that distinction. It starts to matter in M11: a unit is assigned to a *worker name* in the cluster store, not to a process or server. A restarted process reads the same assignment. When a server dies, the controller rewrites its workers' assignment rows, and only those rows. The *resource* and subsystem places stay with their server.

**M8** precedes this progression: it builds the product without local truth because Kinesis holds both configuration and archive. Everything that follows comes from the box having to hold its own truth.

**EdgeVMS has no desired state.** Flash an image and its containers start; actual state is the only state. M9 makes that safely replaceable, hence four lessons on atomic updates, rollback and signatures, and none on cameras.

**The recorder introduces desire.** A row saying a camera should record is not a recording camera. Someone must close the gap: five lessons build that reconciliation loop by hand, at a scale where both ends fit in one terminal. Its rule runs throughout the course: *desired state persists; actual state is derived*. Persist the latter and you have built a cache that lies.

**Cluster introduces a second box without introducing an orchestrator** (ADR 0021). A cluster would need an orchestrator's store rather than its scheduler: the platform controller assigns units to workers, workers claim names by CAS, and `systemd` holds the same processes on every server. The platform owns the store: a `configstore` daemon per server, three daemons in one raft group. The module's turning point is elsewhere: **a unit has an owner**, two instances of one worker can claim it, and a paused process is indistinguishable from a dead one. M11 is therefore the course's one module where a mistake corrupts customer video rather than stops a service. An orchestrator remains a delivery form for sites that already have one ([Orchestrator as a delivery form](./_notes-ru/orchestrator-as-a-delivery-form.md)).

**The domain (M12A) is what remains once a cluster works independently, and less remains than expected.** A cluster moves work, restores from its own object store and answers *where is camera 7* from one strongly consistent raft without asking a higher layer. Only the domain can address the questions that become uncertain with a second cluster: which cluster holds a camera, which should receive a new one, and **whether an answer is complete**. There is no raft across clusters, only partial aggregation with bounded lag. The domain is a *catalogue of catalogues* that cannot be consistent; being honest about this is the module's subject. What VMS adds to that domain is a separate module, M12B.

**Every layer may be unavailable to the layer below it.** The lower layer caches what it needs to continue. Workers keep recording while the cluster catalogue is down; clusters keep recording and remain editable while the domain is unreachable; **the domain keeps working when the vendor disappears**. At that point the rule becomes a property promised to the customer.

**The domain is the top of the product.** One customer has one domain, spanning its whole estate: three server rooms, or a cloud cluster serving fifty shops. Earlier drafts put a root CA, federated identity, vault and appliance inventory above it. Each proved to be either something the domain does for itself or something the *vendor* does across customers. M14 is therefore not a fifth scope; it is the far side of a boundary. There is no vendor root above the customer's trust domain because a vendor able to sign your CA can impersonate you.

The rule has a sharp edge: **anything a layer caches from above may keep recording forever and must not delete anything.** Destructive operations expire; recording does not. Retention policy belongs to the cluster and cannot become stale through an upper layer, whereas licensing and placement arrive from above and can become stale.

**M13 adds no scope either, for the opposite reason.** Observability shows the four scopes already present and operates at domain level. Its remote observer is another domain service; *a silent cluster is unreachable, not broken* applies M12's honesty about incomplete answers to metrics. It comes **before** the vendor because the vendor demo — *the vendor disappears for thirty days* — requires instrumentation already in place, and its canary stops according to an alert rule. It gets no VMS name because it builds no new scope needing one.

---

## The progression

A shipped VMS reaches seven layers deep. Each layer has a module, and each module ends with something working.

| Module | Layer it builds | State |
|---|---|---|
| [**M10** — Platform](./Platform) | What knows nothing about video: store vocabulary, subsystem manifest and strict loader, units and slots, controller and placement, a worker under a slot, rights, secrets, events and resource, console, schema and drain, platform on a box and cluster (`configstore` on raft, identical `systemd` units per server). Specification lessons under ADR-0080: five normative sections and acceptance | **Moved** to [`Platform/`](./Platform) in stage B, ADR-0083; the M10 lessons and directory were removed at the end of stage B |
| [**M10B** — ServerVMS](./%D0%9C10B_ServerVMS) | Seven subsystems (`vms`, `rec`, `live`, `det`, `detjob`, `survey`, `auto`): `driverpacksrc`, ObjectStorage archive, camera-holding worker, recorder, detectors, live-video gateway and scenarios | **Written** · 28 lessons |
| [**M12A** — Domain](./%D0%9C12A_Domain) | 4 · Several clusters, one catalogue of catalogues<br>5 · Domain as its own root: enrollment, lifetimes, identity and secrets<br>7 · Its own update server and clusters it rents for itself — a platform service, `Source/w2cplatform/domain/` | **Written** · 15 lessons |
| [**M12B** — DomainVMS](./%D0%9C12B_DomainVMS) | What VMS adds to the domain: source and primary books, cross-cluster streams, unreachable cameras and a relay chain — `Source/vms/domainpart/` | **In progress** · 4 lessons |
| [**M13** — Observability](./%D0%9C13_Observability) | 6 · Prometheus and logs: collecting M9–M12 signals at the domain holder | **Designed** · 4 lessons |
| [**M14** — VendorVMS](./%D0%9C14_VendorVMS) | *Not a layer.* MASA, licensing, publishing, hosting, and what a vendor must never be able to do | **Designed** · 5 lessons |

**[GLOSSARY.md](./GLOSSARY.md)** defines every course term precisely: worker versus server, desired versus actual state, epoch and fencing, and the abbreviations that would otherwise go unexplained.

**[COURSE-PLAN.md](./COURSE-PLAN.md)** gives the full argument: module order, contents, and two structural cautions — license concentration (Nomad, Consul and Vault under one vendor's BUSL; the product depends on none and the cluster runs without an orchestrator, ADR 0021), and where secrets live without a product secret manager.

**[ARCHITECTURE.md](./ARCHITECTURE.md)** describes the current system: five terms, what runs where, three stores, trust and failure matrices; then the fourteen steps that led there, with each motivating question and what it removed. Read it before the modules for a view of the destination.

**[`_notes-ru/`](./_notes-ru/README.md) contains notes about the project, not its documentation.** Readers of the code describe the whole system in their own words: one setting's path, a scenario down to each HTTP request, a Kubernetes comparison. Useful on a second pass after the lessons. Where they disagree with code, the code is authoritative.

---

## M10 and M10B — ServerVMS

The recorder rebuilt in M11's form — **workers, resources and one controller** — and first prototyped on one box without a scheduler, KVS or database. On the GStreamer side, `driverpacksrc` plays files whose names stand in for RTSP addresses; the archive uses the product's ObjectStorage engine through the `obsd` socket with an epoch in the stream name. Then come the VMS controller — platform `SpecController` assembled from `vms.subsystem.yaml` (`w2c-controller@vms`), the sole placement writer — and `vmsworker`, DriverPack as a worker. The result is a **subsystem contract**: manifest, worker, configuration prefix and heartbeat. Detectors and the gateway implement the same contract; the platform knows it without knowing cameras. A tested boundary splits the module: M10 is the video-independent platform (eleven specification lessons under ADR-0080 since 2026-10-14; former M10A and M11_Cluster removed), and M10B contains its seven subsystems.

- [Platform, formerly M10 and M11](./Platform/README.md) · [design note](./Platform/module-design.md)
- [M10B — subsystems](./%D0%9C10B_ServerVMS/README.md) · [design note](./%D0%9C10B_ServerVMS/module-design.md)
- [`Source/`](./Source/README.md) contains the module code: two CAS platform stores, epoch allocation and leases, `driverpacksrc`, ObjectStorage client, `vmsworker`, `vmscontroller`, console, systemd units, identity by claim, resource events, video in volumes, resource as platform work, and the `testsub`/`testsub2` subsystems used to test the platform
- The Go version of that contract is the `vmssubsystem` product in a separate repository. The course neither maintains nor follows it: lessons follow `Source/`, while Go evolves in the product

Four root documents address the product rather than the lesson reader:
[Product feedback](./%D0%9E%D0%91%D0%A0%D0%90%D0%A2%D0%9D%D0%90%D0%AF-%D0%A1%D0%92%D0%AF%D0%97%D0%AC-%D0%98%D0%97-%D0%9F%D0%A0%D0%9E%D0%94%D0%A3%D0%9A%D0%A2%D0%90.md) records what turning course code into a product revealed and what is fixed here; [Product automation](./%D0%90%D0%92%D0%A2%D0%9E%D0%9C%D0%90%D0%A2%D0%98%D0%97%D0%90%D0%A6%D0%98%D0%AF-%D0%92-%D0%9F%D0%A0%D0%9E%D0%94%D0%A3%D0%9A%D0%A2%D0%95.md) specifies moving the seventh subsystem to Go, existing and missing parts, order and exclusions; [Product events](./%D0%A1%D0%9E%D0%91%D0%AB%D0%A2%D0%98%D0%AF-%D0%92-%D0%9F%D0%A0%D0%9E%D0%94%D0%A3%D0%9A%D0%A2%D0%95.md) covers traffic classes, limit direction, writer-side suppression, durability by class and operator requirements; [Alarm state](./%D0%A1%D0%9E%D0%A1%D0%A2%D0%9E%D0%AF%D0%9D%D0%98%D0%95-%D0%A2%D0%A0%D0%95%D0%92%D0%9E%D0%93%D0%98.md) records the accepted acknowledgement decision and why implementation awaits the operator screen.

## Cluster — P/01.3, P/02.4 and P/04

The cluster no longer has a separate module. A replicated store is a second deployment of the same Platform norms: daemon and raft group in [P/01](./Platform/01-store/spec/01.3-store.norms.md), chapter 1.3; per-server service units in [P/02](./Platform/02-installer/spec/02.4-installer.norms.md), chapter 2.4; server failure in [P/04](./Platform/04-controller/spec/04-controller.norms.md). This was M10/11, Platform on a box and cluster; former M11_Cluster was removed on 2026-10-14. The same **controller, workers, resources and console** run across servers and survive any one server's failure. Code lives in `Source/w2cplatform/cluster/` and knows subsystems only through manifests. A platform `configstore` daemon runs per server; three daemons form one raft group. Objects are files in the writer server's directory. `systemd` holds identical processes per server (`w2c-*` platform units, subsystem worker units). **There is no orchestrator** (ADR 0021): the controller places units and workers claim names by CAS.

A unit is assigned to a worker name in the cluster store, not to a process or server. A restarted process reads the same assignment; after server death the controller gives its units to live workers by rewriting assignment rows only. Resource and subsystem places stay with their disks: unavailable while the server is down, not lost. Configuration never left the store, so edits made during the failure are already present. A host script, not the controller, starts spare workers for the controller's reported shortage.

The decisive fact is easy to miss: **two writers into one video stream cannot be merged.** No upper layer can reconcile them after the fact. This is the one module where a mistake corrupts customer video instead of stopping service. Fencing belongs at the data, not the coordinator: a CAS slot and an epoch in the stream name fence a returning old instance twice, at the slot and each epoch, preserving the archive. A zombie cannot be prevented from writing; its writes can be made harmless.

**This alone is a complete product:** one cluster on its own raft, asking no higher layer for permission. A customer with one building needs no more. [VMS on the cluster](./%D0%9C10B_ServerVMS/28-vms-on-the-cluster.md), M10B, adds camera budgets, volumes, the recorder door and a volume timeline.

- [P/02 chapter 2.4](./Platform/02-installer/spec/02.4-installer.norms.md), [P/01 chapter 1.3](./Platform/01-store/spec/01.3-store.norms.md), [P/04](./Platform/04-controller/spec/04-controller.norms.md): service units, users, directories, raft group and the pull-the-power drill (formerly M10/11)
- [Platform design note](./Platform/module-design.md): the micromodule split
- [`Source/w2cplatform/cluster/`](./Source/w2cplatform/cluster/README.md): cluster stores, catalogue, manifest-derived rights, platform process entry point; tests in `Source/tests/cluster/`, deployment in `Source/deploy/cluster/`, stand traces in `Source/traces/`
- [Orchestrator as a delivery form](./_notes-ru/orchestrator-as-a-delivery-form.md) and [Thin seam versus provider](./_notes-ru/thin-seam-vs-provider.md): decisions moved from the former module to notes

## M12A — Platform domain

Fifteen lessons start from an unusual premise: **M11 already works.** The cluster controller owns configuration in its raft, a worker survives its server by claiming a slot, and nothing asks a higher layer. This module must therefore justify that layer. A cluster cannot know three things: where a unit is among clusters, which should receive a new one, and whether an answer is complete. This is a **catalogue of catalogues**, not a configuration store.

**The domain is a platform service, not VMS** (ADR 0024). Holder and term, move, trust, people and rights, emergency access, edits carried home by a member, and their secrets live in `Source/w2cplatform/domain/` and `Source/w2cplatform/trust/`, without a subsystem import. A domain knows a subsystem only by its manifest's `domain:` section (ADR 0010, ADR 0031). Examples use course subsystem `testsub`; VMS cameras are explicitly labelled examples.

It is the course's first layer **allowed to be unavailable**, more extensively than first expected. Units continue working; an operator can edit one through its own cluster console; **work still moves after a server dies**, because M11 put both move dependencies inside the cluster. Choosing a cluster for a new unit, cross-cluster lookup, certificate issuance and token issuance stop.

The campus makes this a module rather than a chapter: **three server rooms, three clusters, one customer, one catalogue.** Each cluster owns its store; nothing replicates between them. If a whole cluster goes dark, the domain owes honesty rather than recovery: its units are on that cluster's network. **Rebalancing elsewhere would create workers unable to reach the dead network and hide the real failure.**

It turns out not to be a database: the domain reads the controller snapshot and worker heartbeats each cluster publishes as objects, querying by `ref`, a name declared by the manifest and assigned by the domain, never by a local cluster identifier. Six revisions of the decision note moved in one direction; the seventh removed the product's final database.

The cluster writes its own rows, so it must be reachable and protected. Lesson 4 gives every cluster↔domain stream **mTLS from the domain's own root**. A certificate names a server, never a worker. The intentionally self-signed root belongs to the customer, with nothing above it. Grants arrive in each cluster's own store via the domain agent and carry expiration, rather than being queried. Workers never see a person, token or grant.

**Then the domain looks after itself.** An appliance enrolls (lesson 6) and receives a certificate from the domain's own signer. Root lifetimes and rotation drills follow in lesson 7 because no higher layer will reissue anything. The domain deploys a cluster in the customer's cloud account (lesson 8), proving that a worker cannot tell where it runs. Its own update server and license cache (lesson 5) let it survive a disappeared vendor: M14's subject.

**The second part covers hundreds of small, often powered-off members** (lessons 10–15). A box is a one-member cluster; edits for an offline member wait to be carried home; shared settings are a signed document behind a pointer; alarms merge from reports; the holder runs on a box for a term and moves using a recovery file. The final lesson seals everything the domain keeps and carries: domain secrets with the platform ring, backups with a key absent from backup holders, and each member's own data for transport through the domain door encrypted with that member's key. One process — the signer — holds domain keys; the domain console holds none (ADR 0032).

- [Remaining M12 VMS material](./%D0%9C12A_Domain/README.md); the platform domain is [P/08–P/10](./Platform/README.md)
- [Where the databases live](./where-the-database-lives.md): six revisions arriving at one database, a seventh removing it when cluster configuration acquired an owner, and the storage rule protecting customer video
- [`Source/w2cplatform/domain/`](./Source/w2cplatform/domain/) and [`trust/`](./Source/w2cplatform/trust/): code over M11's `w2cplatform/cluster/`, with real controller and workers in each test. Tests: `Source/tests/domain/`, `Source/tests/test_domain_platform.py`, `Source/tests/test_domain_secrets.py`. Units `w2c-domain`, `w2c-domain-console`, `w2c-domainagent`: `Source/deploy/domain/systemd/`. Subjects include incomplete catalogue answers, reachability placement, ref-keyed shadow mode, heartbeat read models and console, signer lifetimes and root rotation, people never reaching workers, cluster-local grants, voucher/approval enrollment, licenses and grace periods, term and holder move, and sealed secrets

## M12B — DomainVMS

Four lessons cover **what VMS adds to the platform domain**. M12A already built holder, trust, move and secrets. VMS contributes the `domain:` sections of `vms` and `rec` manifests and a holder worker (`python3 -m vms.domainpart`, unit `vms-domainpart`). It writes VMS books under `domain/vms/…` and requests manifest-declared `stream`/`ask` tokens from the signer. The first lesson covers the whole subsystem contribution. The next three ask how a recorder reads another cluster's camera through agent-carried source books and keeps recording with the domain off; how a camera unreachable by both domain and recorder pushes its stream to the recording cluster receiver through primary books; and how streams and desired state traverse a site–relay–centre chain where every level calls only upward.

- [Lesson index](./%D0%9C12B_DomainVMS/README.md): start here
- [`Source/vms/domainpart/`](./Source/vms/domainpart/): module code, tests in `Source/tests/domainvms/`

## M13 — Observability

**It collects observability rather than introduces it.** Earlier modules already emit signals defined where their refusals were introduced: M9's health-check ladder and spool age, M9's `camera_silent_seconds`, M11's move duration, M12's replica lag. Six signals cover VMS; the module starts with inventory rather than installation.

The hard part is one sentence: **in a data centre, no news is bad news; on an appliance, no news is *no news*.** A silent site may be broken, have a failed uplink, or have lost building power: four problems for four people with the same signal. Monitoring unable to distinguish *broken* from *unreachable* either wakes someone on every router restart or misses a real outage; in practice it does both.

This meets a familiar rule: **monitoring must not share the monitored system's failure domain**. Prometheus pulls metrics, but pulling over a distrusted channel is unreliable. The solution is two observers with different jobs: a local one that sees everything and dies with the site, and a remote one whose sole job is to distinguish silence from health. **Details stay local; summaries are domain-wide**, the fourth occurrence of the rule that predicted a fourth data type.

The module also records the course's second licensing concern, sharper than Nomad's: **Grafana, Loki, Tempo and Mimir use AGPLv3**, whose §6 applies on distribution whether or not code changed. Prometheus, VictoriaMetrics, Thanos, Cortex, OTel Collector and Grafana Alloy use Apache 2.0. The course's position is to teach Prometheus and **ship no dashboard**; operators should not need two consoles.

- [Design note](./%D0%9C13_Observability/module-design.md): observer paradox, meaning of silence, alert design and AGPL

---

## M14 — VendorVMS

Five lessons form a different module. The domain is already the product's top, so this builds no product scope. Above the domain is a **vendor**, a separate organization beyond a boundary the product crosses in only one direction.

The thesis is a property enterprise security buyers request by name: **the product must work when the vendor is unreachable or disappears**. The demo works backward from it: the domain is a year old, and on a date chosen by the student the vendor disappears completely. Nothing already working stops for thirty days. What *cannot* happen is enumerated, not implied. On day thirty-one the license grace period ends and degrades exactly as M12 specifies.

M9–M12 asked what the product must do; this module asks **what a vendor may do, and what it must never be able to do**: vouch for hardware but never enroll a box into a domain on its own; issue a license but never stop recording by withholding it; publish a package but never push it onto an appliance; rent a cluster but never hold a customer's root. The latter boundaries are capabilities earlier drafts would have allowed.

What belongs to the vendor: **MASA** and its ten-year operating commitment; **licensing** — a database, one signing key and a document verified offline by the domain, bound to domain identity rather than hardware and checked on admission rather than against a recording camera; package signing, publishing and customer rollout with a self-stopping canary; customer-controlled support inventory; and hosting as a business option described rather than adopted. **OpenBao finally has a proper scope here**: dynamic credentials for a vendor holding many customers' secrets, after machine identities removed its earlier proposed duties.

- [Design note](./%D0%9C14_VendorVMS/module-design.md): one-way boundary, MASA, licensing, publishing, rollout and hosting

## How the lessons are written

Two conventions shape every lesson and account for the material's length.

**Every step produces an observable result.** A process to signal, a container to inspect, pipeline output to play, a page to view — rather than code accepted on trust. If a dependency cannot be installed, the lesson demonstrates its logic another way instead of asserting it.

**Every lesson replaces a previous stub.** `camera_sim.py` becomes a real pipeline; `filesink` becomes `kvssink`; fake clients become boto3; fixtures become real fragments. Nothing stands more than one layer away from something already checked.

Decisions include their costs. Missing acceptance criteria, surrendered capabilities and licenses needing legal review are stated explicitly.
