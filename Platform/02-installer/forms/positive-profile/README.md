# Positive P/02 profile: byte specimens and an open completeness obligation

This English text is the source; the Russian translation is derived from `forms/positive-profile/README.md` for people, not in the export (ADR-0121).

## Status

A sufficient full positive stand profile is **not established** by this delivery. The candidate body parameter2147483648bytes is not accepted as sufficient. The existing [finite-profile form](../finite-profile.schema.json), its13 synthetic cases/eight skeletons, codec boundaries and old installer corpus remain unchanged. The lower bound6291463 for one row is not a complete packet bound. These specimens introduce no manifest field, command, port, profile grammar or store limit.

The missing count proof cannot use writer-only caps as reader caps. In the unchanged P/06 [folder schema](../../../06-console/data/folders.schema.json) and [membership schema](../../../06-console/data/memberof.schema.json), the limits FOLDERS_MEMBERS_MAX and FOLDERS_PER_UNIT_MAX constrain the writer definitions; their base reader arrays have no such maxItems. At V524288, a readable membership with14979 distinct32hex folder ids has items weight524273bytes, so it fits the store while exceeding the writer cap. A readable folder with1001 distinct members also fits V. The deletion/reaper procedures of [P/06.8 N3](../../../06-console/spec/06.8-console.norms.md) must not silently truncate them or turn them into unreadable rows. Preexisting readable folders also cannot be assigned the writer FOLDER_ROW_MAX category without a separate proof.

Consequently, the draft roster using writer8/1000 does not bound all allowed preparation states. A complete profile still needs reader-derived multiplicities, each actually required guard/write/alternative, and the right weight category for every auxiliary row, against the full confirmed catalogue and actual procedure descriptors. The arithmetic term14979*(6*65536+19)=5890267065 already exceeds the candidate body ceiling under that draft's own category. This diagnoses a missing sufficient-bound proof; it is not a measurement of one emitted request and does not by itself prove what replacement B is sufficient. No new restriction on old rows, strings or client versions is imposed.

The existing `{body_limit}` and `{row_ceiling}` substitutions of the [common acceptance](../../../common/acceptance/README.md) remain the only stand launch bindings; `manifest-put {socket} {file}` remains the command. No common source is changed. Until the full proof and its actual execution binding are supplied, the positive profile obligation is open and unexecuted, not PASS. The old isolated ceiling cases and payloads are not changed to refusals to hide it.

## Metadata specimens

The public [P/01 N1](../../../01-store/spec/01.1-store.norms.md) `index.wire` and `Version`/`BatchGuard` in its [OpenAPI](../../../01-store/spec/01-store.api.openapi.yaml) bound the wire version to20decimal digits. Client opacity means exact equality, not an unbounded version on this wire. Keys use KEY_BYTES, id the existing64hex domain. No free metadata string is silently shortened.

The three compact UTF-8 specimens below contain the actual public put/delete/batch field spellings, distinct legal maximum-byte keys with worst JSON control-character escaping, a20digit version and64hex id. The single-write field is `guard`, the batch field is `guards`. Put items are dummy empty objects. Both deadlines are dummy0. These are byte-count specimens, not admitted target requests or expected SUT answers; there is no final LF. A real profile must count its actual LF separately.

| File | UTF-8 bytes | SHA-256 |
|---|---:|---|
| `metadata-put.json` | 12490 | `181ef7fb5178e07e729150fb16d709f9c038e6a5a2ffeb513b00f7c15a7348b7` |
| `metadata-delete.json` | 12482 | `0b187caceef01b1c6ffe94ddabad8bd04eb3824e67e3ea1b567798401b148312` |
| `metadata-batch.json` | 18712 | `649053f768d9dd9ea8487215540a7f16516a74d495bd8f31a46aca7de832e379` |

Removing only the put-items value leaves its property name/delimiters to be charged to metadata. The quoted worst key occupies6146bytes. An independently encoded put/delete metadata component with a following comma occupies6190/6193bytes; a guard component 6181. The remaining frames with empty slot arrays/guard occupy124/127/139bytes for put/delete/batch. Replacing each dummy0 deadline by the existing conservative313byte allowance gives748/751/763bytes for those frames. The extra items property/delimiters are below the remaining margin. Thus8192 per declared write component, per guard component and one frame is conservative **for this closed constructor set**. Whole specimen lengths exceed8192 because they include multiple components;8192 is not a packet bound.

This component calculation neither proves H for an unseen emitter nor establishes the full profile. Arbitrary ignored top-level fields, an extra producer string, another number formatter, omitted guards or a new request shape require their own byte accounting. The finite binary64 domain is not a bound on a caller's original decimal lexeme. A bounded emitter may use a round-trip shortest/scientific JSON representation (at most17significant digits and24bytes including sign/exponent), but no input lexeme is truncated and admission/fingerprint values are unchanged. The older313 allowance is not a new input-string limit. Every nonempty items payload remains assigned once to its independently proved V/F category, never hidden in H.
