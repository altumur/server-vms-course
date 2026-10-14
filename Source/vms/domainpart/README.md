# The domain — М12, split along the boundary (М12A the platform's domain, М12B the VMS on it)

The smallest layer that can sit above a set of clusters, be switched off, and be the top of the product — as code. The domain is the PLATFORM's (the owner's decision of 4 October): it knows the subsystems by the `domain:` section of their specs and by nothing else (the boundary's «no hooks», `ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md` §1.1). What the video product does above its clusters is this package's: a worker that writes its books at the holder, and code its own processes run.

```
Source/
  w2cplatform/trust/       tokens (a key SET, kinds of token, `DeclaredIssuer`), signer (root, issuing, LDevID lifetimes),
                           enroll (pledge, registrar, voucher), documents (a signed document)
  w2cplatform/domain/      М12A — the platform's domain
    declared.py            what the loaded specs declare: the directory, reported objects, books, kept rows, tables, tokens
    federation.py          L1   N clusters, one directory of directories; every answer says what it could not reach
    placement.py           L1   which CLUSTER gets a unit, by reachability, stored with a reason, by CAS
    shadow.py              L2   the divergence report and the exit criterion
    readview.py            L3   the list of units from heartbeats and snapshots; one cause per dead server; the shared view
    api.py, console.py     L3   the write façade; the domain's door (`/domain/<sub>/<rows>`, `/domain/<sub>/<table>`, …)
    identity.py, grants.py, access.py, agent.py   L4   users, cluster-local grants, a cluster console's check, the agent
    entitlement.py         L5   the licence cached, graceful; work never stops
    pending.py             L9   an edit kept for a cluster that is off
    scale.py               L11  the Meter: calls and link time per member
    shared.py              L12  shared settings: one signed object behind a pointer
    alarms.py              L14  one list of alarms; silence as an alarm; a witness a spec declares; a week of history
    term.py                L15  the holder's term, the backup beyond it, moving; the root off the holder
    uplink.py, members.py, topology.py, relay.py   L10, L6, L17   reports up, the list of members, who reaches whom, the relay
    signer_service.py, tokendoor.py, runtime.py, steps.py   the processes: the signer's doors, the wiring, a pass's steps
  vms/domainpart/          М12B — the VMS on the domain
    keys.py                the VMS's rows of the domain: `domain/cam/…`, by the names `cam.subsystem.yaml` declares
    ../recording_sources.py L13  assigned source observations, backfill and reserve decisions
    ingest.py              L16  a camera nobody can reach: ingest, stream tokens, the long poll, the pusher, asks
    scenario.py            L12, L16  scenarios between cameras
    chain.py               L17  the relay's forwarder and the upstream book (the relay's platform half is `w2cplatform/domain/relay.py`)
    books.py, worker.py    the books' pass, run by `python3 -m vms.domainpart` at the holder, with its own slot, heartbeat and door
    device.py, gateway.py, cloud.py   a camera as a member; the live tee; Lesson 8's arithmetic
  tests/domain/            the platform's domain (on М11's real clusters and on testsub: `tests/test_domain_platform.py`)
  tests/domainvms/         the VMS on the domain
```

```bash
python3 tests/domain/run.py ; python3 tests/domainvms/run.py      # from Source/
python3 -m w2cplatform.domain.console    # CLUSTERS=north,south=report  (a bare name: this server's own, by PLATFORM_STORE and OBJECTS)
python3 -m w2cplatform.domain.signer_service ; python3 -m w2cplatform.domain.agent ; python3 -m vms domainpart
# on a server: deploy/domain/systemd — w2c-run.sh signer | domainconsole | domainagent | vms domainpart
```

## What the VMS declares (`cam.subsystem.yaml`, `domain:`)

C2 is declared by `cam.domain.books.sources` and `rec.domain.books.primaries`, collected from guarded worker rows. Ordinary workers own the facts and consume their carried books. Assignment is `domain/placement/rec/<ref>` with the member copy `domain/placed/rec/<ref>`; the platform's typed route serves it. Tokens of `stream` are obtained through the agent's role door and remain in memory. RTSP accounts are stored by the live gateway in its cluster and published through `live.domain.books.stream-accounts`; its doors are `/live/accounts`, passed by the cluster's console. This process still owns asks until C6 of ADR-0074; none of it publishes C2 observations or account contributions.

## What the product page shows (for «Консоль»)

The platform's domain page draws members, units and causes from `domain/view`. What is the VMS's to show — domain cameras with their `ref` and name, recording assignments (`GET /domain/placement`), scenarios between cameras and the catalogue of what one camera may ask another (`GET /catalog` on the VMS domain worker's door, `DOMAINPART_PORT`), the streams' numbers (`GET /metrics` there) — is the product page's, not a platform `domain/page.html`.

The domain card's «Ключи» tab: the families are the spec's now — `/spec` → `domain.keys` (`[{id, keys, prefix}]`) and
`display.keys` (`{<id>: {title, about, absent}}`), merged by id; the product page's `KEY_FAMILIES` constant gives way to
them. No rows for issued keys on either side: a book's entry carries its token sealed (`token_secret`), the domain's
signer's — the ask token with `by`, `acts` and `up` (ADR-0010, its addition of 2026-10-08; the product's receivers' book,
lifts and key lists went in b5ae5b7); asks carried up wait in the relay's memory; scenarios are the platform's
`domain/shared`.
