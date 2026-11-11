# Change 0133-p03-common-acceptance-words

change: 0133-p03-common-acceptance-words rev 1 · lessons P/03, Platform/common · author run P03.25 (Claude) · state review

Publication parent `537e32fc3062942004e39ac812c8eaf35f269ff3`. Task P03.25, part 3в1 of the readiness audit P03.20 (`decisions/inbox/2026-11-11-P03-аудит-готовности.md`), with the Architect's answers to its questions 2 and 4 (P03.21), ADR-0133 addendum (29). The rules that the acceptance READMEs of P/03 kept only in prose get shared words of the common acceptance (EN/RU):

- the closed engine word `seams` in line 2 of `forms/targets.routing.tsv` and in «Seam adapter protocol» of the common README: the `seams.tsv` of the first directory through the seam adapter protocol, also when that directory holds a `scenarios.tsv`, which the word does not execute; `run` keeps its meaning; `seams` takes the body modes `whole` and `subset` like `run`. The files stay in place, because the gate `seams:<chapter>` names the `seams.tsv` of its chapter;
- the section «Testsub process stand» of the common README: a fresh stand per scenario (stop and wait for every process, then remove the state; a new `{data}`, ports, store, console; no bound names and replay keys), no foreign processes, one box, the stop of `@sigterm`/`@sigkill` by R017, the time of a scenario by R036 instead of a lesson budget, own directories and ports for scenarios that run at the same time;
- the request prefix `@rid $<name>` of the dictionary: the judge binds the rid `r-<sha16(Idempotency-Key)>` of the console door before it sends the step, so both branches of `@oneof` of step 05/5 of P/03.6 compare one rid (appendix Г, `6/README.md:76–77`).

The norms of the judge do not change. The probes through the seam adapter of question 4 (candidates 1–3 of appendix Д) need no new reason of R030: a missing bridge descriptor is already `MissingBinding` of R050, and a scripted clock and store depend on nothing of the environment of the run. The comparison rules repeated in four READMEs of P/03 are already in «Expectation» of the dictionary.

Left to other parts. 3в2: the rows of P/03 in `targets.tsv` and `targets.routing.tsv` (`seams` for the seams of 3.2, 3.3, 3.4 and 3.6, `run` for 3.1, 3.5 and 3.7) and the filters. 3г: the READMEs of P/03 reference «Testsub process stand» and the dictionary instead of their own boundaries, comparison and the lines «One scenario takes no longer than 3 minutes»; step 05/5 gets `@rid $rid`; the probes through the seam adapter.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/README.md` | MODIFIED | e86fddd24b847c871513297e22d1ddd2c90592b6 | 8b3bdfd469136649e37f1447f9a6b233195fcbd7 | 49b72b38109c137d732550fc36c4bc2580f7544ccb60b15ae3b8333adf81cb74 |
| `Platform/common/acceptance/forms/targets.routing.tsv` | MODIFIED | e48132f51c6848fbc7939ddaf13ae92a8006aac4 | c080382512b683913e548e334c21361920806977 | 8bffca311aaa1cfbf7629d77fd8364155b48e3383cc7453f3e62eef608d81fa6 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | 9ff929d1ce8625554b1706e87f20f4215f1a6576 | b7aa619b8b6ec0b83de191204866846b0b0d2ea0 | 9f4d77ea36751747287e44b430af635518d3c31f1b5e30e4385cf63950b12569 |
