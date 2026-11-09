# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/8/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

The norm of the chapter is [`08.8-domain.norms.md`](../../spec/08.8-domain.norms.md) N5. The scenarios and the text below were moved from the acceptance of
M11/10 (stage B, ADR-0083 addendum (1): without
a change of behaviour); the numbers of the scenarios and the steps are the former ones. Scenarios 05 (`record`) and 07 (`ask-sig`) are removed — the same cases are in
the packages [`common/vectors/record`](../../../common/vectors/record/README.md) and
[`common/vectors/ask-sig`](../../../common/vectors/ask-sig/README.md) (the plan of the move of lesson 8, V1); scenario 06 (`follow`) is removed — the package
[`follow`](../../../09-agent/vectors/follow/README.md), 11 — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md); 01 —
[the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) sc. 15.

<!-- original-mixed-case-paragraph -->

- **Scenario 02.**
  - `@stop domain` switches the holder off, `@start domain on m1` brings up an empty signer on `m1`, `@move m1` moves
    by the installation file.
  - `@start domain` returns `hold`: its agent brings the term record 2, the process yields. Step 13 waits (`@until`) for its forgotten keys — a look at
    its own store.
- **Scenario 04.** The handover target is `m1`. `m9` is not a member.

<!-- original-mixed-case-paragraph -->

of the chapter). `stolen` is the steps of chapter 8.2 «change after theft». The cancellation of a handover — sc. 13.

<!-- original-mixed-case-paragraph -->

The scenarios of the chapter have no inputs. The inputs `record-*` and `ask-sig-*` of the acceptance of M11/10 are removed together with scenarios 05 and 07: the same
cases are the tables of the packages `record` and `ask-sig` (the input is JSON text in a row). The inputs `follow-*` are removed — the same cases are in
the package [`follow`](../../../09-agent/vectors/follow/README.md).

<!-- original-mixed-case-paragraph -->

In total 13 scenarios / 122 steps. Sc. 18 — ADR-0098 §5, there is no dry run by an implementation.
