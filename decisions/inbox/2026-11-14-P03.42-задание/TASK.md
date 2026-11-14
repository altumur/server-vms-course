Implement P/03 from scratch in 03-worker, using only the pinned model-visible specification M and its required pinned dependencies. Implement the complete worker SDK across all seven chapters: the subsystem library calls, slot ownership and cleanup, epochs and leases, reconciliation, heartbeat and bounded stand-in, orderly stop, secret opening, requests and events, and the domain-worker layer. Write your own lesson code and meaningful tests. Read the public contracts, forms, schemas, protocols and dependency versions in M as needed. Other lessons are dependencies through their published contracts in M; their implementation code is not an input and is not part of this task.

This is generation only. Nobody checks your code while you write it: there is no loop, no check command and no gate. Build it, vet it and run your own Go tests yourself; they do not establish conformance to the specification. No acceptance judge, judge feedback, stand gate or judge profile is used during generation. The finished candidate is judged separately after generation. Do not replace required product behavior with adapter answers or hard-coded examples. Concrete scenarios, fixtures and expected answers are not supplied in M. SPEC_VERSION identifies the immutable M input.

For each learning stage, implement its stated goal and norms. The nine rows of Platform/03-worker/forms/stages.tsv define the work order and dependencies; their acceptance, vector, seam, build and code:* entries are not gates executed during this generation run. Keep the full implementation and tests coherent across all nine stages, including domain_worker. Read every chapter's norms in full and follow the dependencies listed in the lesson README. Implement the SDK and the test worker required by the public profile contract. The SDK has no new binary or HTTP API of its own; implement the subsystem process-door behavior required by the chapter norms and use the owning lesson's contract wherever M refers to another process. The later process and domain stands need neighboring implementations supplied separately; their absence during generation does not remove the SDK's obligations.

Use the shared Go modules servervms.local/common/json, servervms.local/common/store-client, servervms.local/common/log-mask and servervms.local/common/row-check as required by Platform/common/modules.md and the lesson's forms/code-rules.tsv. Take their exact versions from direct require directives of Platform/common/versions/go.mod and their checksums from Platform/common/versions/go.sum in this same M. Import and use these modules; a copied implementation, blank import, replace, vendor or go.work does not satisfy the requirement. Follow every lesson requires_module row, including the pinned JSON Schema validator, and the forbid_imports row, including the prohibition of direct encoding/json imports throughout the lesson's non-test main-module packages. The functions used by P/03 are those assigned by the public contracts and consumers.tsv; other common contracts do not require additional shared code modules beyond the published inventory and code rules.

Keep traceability from the published requirement ids to implementation files and tests. For every readiness checklist item assigned to a stage by stages.tsv, identify its implementation and evidence according to its published [test], [reading] and [stand] labels. Supply meaningful own tests for items marked [test]. Preserve the checklist's reading and stand obligations too: provide pointers to the implementation and state what your own tests establish and what still needs reading, OS installation or a multi-process stand. A test's existence and successful execution alone do not prove that it checks the requirement. Satisfy the applicable code:* rows of forms/code-rules.tsv and bind their abstract names through the profile's code field according to Platform/common/acceptance/PROFILE.md. Traceability and code checks are obligations of the candidate for the later judgement, not generation gates.

Produce a buildable complete candidate with tests exercising its behavior. Supply the lesson's acceptance.yaml, code mappings and root assembly.yaml according to the public profile and assembly contracts in M; declare the lesson's own implementation and interfaces, including its test worker and assigned vector commands. Other lesson implementations are supplied separately to the later stand. Implement test wrappers and seam bindings by calling the real SDK through the published protocols, preserving the distinction between the test-side seam bridge and product interfaces. Do not write a store, installer, resource, controller, console or domain-service substitute to stand in for a neighboring lesson. Tests that only check a stub are insufficient for your implementation goal. Use the public pinned Go dependencies with the supplied offline module cache and file proxy.

---

## Environment of this run

- The specification export M is read-only at "$SPECS" (an absolute path in your shell's environment). SPEC_VERSION: c6d4ba22e4734c9f752cd579e035f032f91e4bac.
- Your working tree is the current directory, "$WORK" (below: work/). It is the implementation root and already holds SPEC_VERSION; the lesson module is the directory 03-worker in it. Write the lesson code there and the assembly at the implementation root. Nothing else on the machine is visible to you.
- Commands have no network. Go 1.22.10 is on PATH; Go dependencies come only from the offline module cache and file proxy supplied for this sandbox. Preserve the supplied GOMODCACHE and GOPROXY settings; GOSUMDB=off, GOTOOLCHAIN=local, GOWORK=off and GOFLAGS=-mod=mod are set. Do not substitute local module sources for the pinned dependencies.
- There is no input-token or active-hour budget. Finish when the implementation of all nine stages and your own verification are ready. The later judge and stand checks remain separate.
- The stages are the rows of "$SPECS/Platform/03-worker/forms/stages.tsv". Start reading from Platform/03-worker/README.md; the norms are navigated by the Index of each norms file. A reading list, all under "$SPECS":
  Platform/03-worker/README.md, Platform/03-worker/spec/03-worker.README.md, Platform/03-worker/lifecycle.md,
  Platform/03-worker/spec/03.1-worker.norms.md, Platform/03-worker/spec/03.2-worker.norms.md,
  Platform/03-worker/spec/03.3-worker.norms.md, Platform/03-worker/spec/03.4-worker.norms.md,
  Platform/03-worker/spec/03.5-worker.norms.md, Platform/03-worker/spec/03.6-worker.norms.md,
  Platform/03-worker/spec/03.7-worker.norms.md, Platform/03-worker/forms/README.md,
  Platform/03-worker/forms/stages.tsv, Platform/03-worker/forms/code-rules.tsv, Platform/03-worker/forms/targets.tsv,
  Platform/03-worker/forms/daemon-flags.tsv, Platform/03-worker/forms/refusals.tsv,
  Platform/03-worker/forms/runtime-constants.tsv, Platform/03-worker/forms/slot-capture.tsv,
  Platform/03-worker/forms/contender-writer.machine.yaml, Platform/03-worker/forms/token-cache.machine.yaml,
  Platform/03-worker/forms/row-write-bindings.md, Platform/03-worker/forms/row-write-bindings.tsv,
  Platform/common/acceptance/PROFILE.md, Platform/common/acceptance/stand.md,
  Platform/common/acceptance/seams.md, Platform/common/acceptance/runner-targets.README.md,
  Platform/common/acceptance/forms/code-rules.tsv, Platform/common/contracts/vector-adapter.protocol.json,
  Platform/common/modules.md, Platform/common/versions/README.md,
  Platform/common/versions/go.mod, Platform/common/versions/go.sum,
  Platform/common/vectors/consumers.tsv, Platform/common/vectors/wire.tsv,
  Platform/common/contracts/json.md, Platform/common/contracts/jcs.md,
  Platform/common/contracts/store-client.md, Platform/common/contracts/log-mask.md,
  Platform/common/contracts/row-check.md, Platform/common/contracts/production-obligations.md.
  Follow the lesson README's dependency table and the chapter references for the other public contracts, schemas and vector interfaces in M.

Working notes and work rules (work/ is "$WORK"):

> Where a norm is silent or ambiguous, do not invent: write a guess to work/GUESSES.md (number, place in the norm, question, what you chose and why) and go on.
> Guesses in GUESSES.md are entries "## N" (N is the number).
> The plan goes to work/PLAN.md (about 6000 chars): packages and files, norms → files, order of steps, before any code. Decisions and what is done go to work/NOTES.md (about 8000 chars).
> Write code early and in small steps, check it with your own tests. Do not fit the code to a test around the norm: if a test and the norm disagree, write a guess to GUESSES.md.
> Do not carry deferred norms: if a norm is unclear, write a guess, do not postpone it.
> Code that changes shared state is reviewed on the properties of the model, not only on the words of the norm: write it so that the properties hold under races, retries and breaks, not only the listed steps.
