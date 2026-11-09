# Judge-only case data

This English text is the source; the Russian translation `ru/spec/06-console.README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [06-console.README.md](06-console.README.md). The following original passages preserve the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

6. Prepare the instances by the acceptance README. Scenarios 01–14: `testsub` is loaded, its data and claim memory are empty,
   the background writers are stopped, the caller has the needed rights; 03 and 14 — each on its own clean instance, the other
   12 — in the order of the file on one. The scenarios are linked: 04 and 11 use `c2` created by scenario 02; this
   instance must not be reset between them (review analysis of stage A 3–5, № 10). Scenarios 15–20: a fresh stand for each — the build schema
   1, the body 1 MiB, testsub/testsub2, c1 only in 15/16/18; in 20 the runner puts the order and state rows bypassing the writer. Then separate probes of the maintenance window and of the full answer; the copy
   of the body at the resource and its refusals — [the instructions of P/05](../../05-resource/spec/05-resource.README.md).

<!-- original-mixed-case-paragraph -->

   The values `a/b` and `..`, inadmissible for any unit.id, are rejected by the schema; the chosen kind of id is checked separately.
