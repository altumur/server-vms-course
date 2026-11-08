# Delta 0083-p03-data-catalog515

change: 0083-p03-data-catalog515 rev 1 · state review · author spec103

Base `959af8d62e7c35ab527fde6e86979b1279ead2ba`. Existing P/03.4 Data catalogue family address corrected by the public Platform515 source request. No role, form, runtime or catalogue-row semantic change; the current concrete form remains 1. No ADDED requirement. No accepted/applied/readiness claim.

## MODIFIED P/03.4-R003

path: `Platform/03-worker/spec/03.4-worker.norms.md`

old-sha256: dbb17e0a0af86d1972d40a1549bc216d40e820b5d66715f33841f79ffbf819a5

new-sha256: bdefdc22d10647bfbc6ba49657118044ba622694889e75a979f1ed0dbfb3dad7

<!-- req: P/03.4-R003 -->

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `<sub>/heartbeats/<name>`;
- writes: `<sub>/slots/<name>` (cas), `<sub>/holds/<place>` (guard), `<sub>/<manifest:tables>/<name>` (cas);
- reads: `platform/manifest/<sub>`, `platform/doors/<host>` (the object client at a bare cluster:// — the object store client contract door; V7 item 3, the Architect's decision 2026-10-28, P3; row 11 of the list), `platform/manifest/<sub>/rev` (the mark: manifest change — P/02.3 N3), `platform/manifest/<sub>/canonical/<form>` (form 1; the worker runner takes the worker program — P/02.3 N3 «The worker program from the row»; V7 item 3, the Architect's decision 2026-10-28, P3; rows 18, 19 of the list), `<sub>/epoch/<id>`, `platform/schema`, `door/keys`, `/etc/w2c/tls/<role>/server.key`, `domain/member-list/<part>` and `domain/<sub>/<manifest:domain.books>` — by worker.reads (N1.7 door_admission, cross_cluster: the CAs of the members for checking a mixed door of another cluster; the copy of the assignment book — for the decisions of the subsystem, freshness by its field missing; ADR-0091 addendum (13) item 5, addendum (15) item 6, addendum (18) item 2), `domain/holder`, `domain/shared`, `domain/shared-docs/rev-<rev>`, `domain/view`, `domain/member-topology`, `domain/topology` (by worker.reads of the subsystem; C08-CATALOG-TOPOLOGY-READERS-01).
