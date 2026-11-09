# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/view/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

The expectations depend on the bytes of the catalog manifests (the review analysis of stage A 8–10, № 37): `domain.ref`, `domain.view`, `unit.rows` and
`unit.id` of the manifests `testsub` and `testsub2` from the specification data:

| Manifest | File | sha256 |
|---|---|---|
| `testsub` | [`Platform/common/data/testsub/testsub.subsystem.yaml`](../../../common/data/testsub/testsub.subsystem.yaml) | `fc3bf70585646b078a8812edd0c92cd5c7d0c2e364b689273c5fd229aed7355b` |
| `testsub2` | [`Platform/common/data/testsub/testsub2.subsystem.yaml`](../../../common/data/testsub/testsub2.subsystem.yaml) | `e4bfd9e0035dba5839018625bba20f7214176004fc2d0cb4f8d640015d915dbb` |

The bytes of `testsub2` changed on 2026-11-04 (roadmap 4.5): the token kind `vault` with `keep: true` was added to `domain.tokens`, then the comments of the header were rewritten without the names of test files; the fields on which the expectations of this table depend are not touched — a recheck by the oracle is not needed.

A change of these bytes is a reason to recheck the table by the oracle.
