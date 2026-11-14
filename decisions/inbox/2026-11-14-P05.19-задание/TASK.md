Implement P/05 from scratch in 05-resource, using only the pinned model-visible specification M and its required pinned dependencies. Implement the complete resource: local and cluster object operations, whole-object publication and tombstones, body copies, event writing and bucket layout, cache-independent event queries, wait hints, the resource process and HTTP door, presence observations and heartbeat, retention and space relief, mirroring and startup restoration described by M. Write your own lesson code and meaningful tests. Read the public contracts, forms, schemas, protocols and dependency versions in M as needed. Other lessons are dependencies through their published contracts in M; their implementation code is not an input and is not part of this task.

This is generation only. Nobody checks your code while you write it: there is no loop, no check command and no gate. Build it, vet it and run your own Go tests yourself; they do not establish conformance to the specification. No acceptance judge, judge feedback, stand gate or judge profile is used during generation. The finished candidate is judged separately after generation. Do not replace required product behavior with adapter answers or hard-coded examples. Concrete scenarios, fixtures and expected answers are not supplied in M. SPEC_VERSION identifies the immutable M input.

For each learning stage, implement its stated goal and norms. The nine rows of Platform/05-resource/forms/stages.tsv define the work order and dependencies; their acceptance, vector, seam, build and code:* entries are not gates executed during this generation run. Keep the full implementation and tests coherent across all nine stages. Read the complete spec/05-resource.norms.md and the imported contracts in full, following the lesson README's dependency table. Implement the resource's own HTTP door, including raw routing, role admission, the published representations and stream behavior. Use the owning lesson's contract wherever M refers to another process; console merge and operator doors, worker request execution and controller placement remain with their owners. Document the implementation choices and the local object library's contract and API as required by the norms, including the API description before its code. A whole file, a responding source and a published copy are distinct confirmation boundaries.

Use the shared Go modules servervms.local/common/json, servervms.local/common/store-client and servervms.local/common/log-mask as required by Platform/common/modules.md and the lesson's forms/code-rules.tsv. Take their exact versions from direct require directives of Platform/common/versions/go.mod and their checksums from Platform/common/versions/go.sum in this same M. Import and use these modules; a copied implementation, blank import, replace, vendor or go.work does not satisfy the requirement. Follow every requires_module and forbid_imports row of the lesson, including the prohibition of direct encoding/json imports throughout the lesson's non-test main-module packages. The functions used by P/05 are those assigned by the public contracts and consumers.tsv; P/05 is not a JCS-vector consumer. Other common contracts do not require additional shared code modules beyond the published inventory and the lesson's code rules.

Keep traceability from the published requirement ids to implementation files and tests. For every readiness checklist item assigned to a stage by stages.tsv, identify its implementation and evidence according to its published [test], [reading] and [stand] labels. Supply meaningful own tests for items marked [test]. Preserve the checklist's reading and stand obligations too: provide pointers to the implementation and state what your own tests establish and what still needs reading, OS installation, real durability checks or a multi-process stand. A test's existence and successful execution alone do not prove that it checks the requirement. Satisfy the applicable code:* rows of forms/code-rules.tsv and bind their abstract names through the profile's code field according to Platform/common/acceptance/PROFILE.md. Traceability and code checks are obligations of the candidate for the later judgement, not generation gates.

Produce a buildable complete candidate with tests exercising its behavior. Supply the lesson's acceptance.yaml, code mappings and root assembly.yaml according to the public profile and assembly contracts in M; declare the lesson's own implementation and interfaces, including the resource launch, object-put and object-spoil commands, assigned vector commands and real seam bindings. Other lesson implementations are supplied separately to the later stand, including the store, installer, worker, controller and console required by the complete process acceptance. Implement adapters by calling the real product code through the published protocols, preserving the distinction between test-side seams and product interfaces. Do not write replacement implementations of those neighboring lessons to stand in for them. Tests that only check a stub are insufficient for your implementation goal. Use the public pinned Go dependencies with the supplied offline module cache and file proxy.

---

## Environment of this run

- The specification export M is read-only at "$SPECS" (an absolute path in your shell's environment). SPEC_VERSION: bd8b2402aa927914e8191dca753ce8d51bc0b140.
- Your working tree is the current directory, "$WORK" (below: work/). It is the implementation root and already holds SPEC_VERSION; the lesson module is the directory 05-resource in it. Write the lesson code there and the assembly at the implementation root. Nothing else on the machine is visible to you.
- Commands have no network. Go 1.22.10 is on PATH; Go dependencies come only from the offline module cache and file proxy supplied for this sandbox. Preserve the supplied GOMODCACHE and GOPROXY settings; GOSUMDB=off, GOTOOLCHAIN=local, GOWORK=off and GOFLAGS=-mod=mod are set. Do not substitute local module sources for the pinned dependencies.
- There is no input-token or active-hour budget limit. Finish when the implementation, meaningful own tests and required candidate artifacts for all nine stages are ready. Report the evidence and its limits; a later judge or system stand remains separate from this generation run.
- The stages are the rows of "$SPECS/Platform/05-resource/forms/stages.tsv". Start reading from Platform/05-resource/README.md; the norms are navigated by the Index of the norms file. A reading list, all under "$SPECS":
  Platform/05-resource/README.md, Platform/05-resource/spec/05-resource.README.md,
  Platform/05-resource/spec/05-resource.norms.md, Platform/05-resource/spec/05-resource.api.openapi.yaml,
  Platform/05-resource/lifecycle.md, Platform/05-resource/forms/README.md,
  Platform/05-resource/forms/stages.tsv, Platform/05-resource/forms/code-rules.tsv,
  Platform/05-resource/forms/targets.tsv, Platform/05-resource/forms/daemon-flags.tsv,
  Platform/05-resource/forms/runtime-constants.tsv, Platform/05-resource/forms/refusals.tsv,
  Platform/05-resource/forms/door-roles.tsv, Platform/05-resource/forms/decision-order.tsv,
  Platform/05-resource/vectors/relieve/README.md,
  Platform/common/acceptance/PROFILE.md, Platform/common/acceptance/stand.md,
  Platform/common/acceptance/seams.md, Platform/common/acceptance/runner-targets.README.md,
  Platform/common/acceptance/forms/code-rules.tsv, Platform/common/contracts/vector-adapter.protocol.json,
  Platform/common/modules.md, Platform/common/versions/README.md,
  Platform/common/versions/go.mod, Platform/common/versions/go.sum,
  Platform/common/vectors/consumers.tsv, Platform/common/vectors/wire.tsv,
  Platform/common/contracts/json.md, Platform/common/contracts/jcs.md,
  Platform/common/contracts/store-client.md, Platform/common/contracts/log-mask.md,
  Platform/common/contracts/object-client.md, Platform/common/contracts/event-journal.md,
  Platform/common/contracts/events-merge.md, Platform/common/contracts/presence-lock.md,
  Platform/common/contracts/observation.md, Platform/common/contracts/tombstone.md,
  Platform/common/contracts/holds.md, Platform/common/contracts/role-certificate.md,
  Platform/common/contracts/schema.md, Platform/common/contracts/production-obligations.md.
  Follow the lesson README's dependency table and the chapter references for all other public contracts, schemas, owned data families and vector interfaces in M.

Working notes and work rules (work/ is "$WORK"):

> Where a norm is silent or ambiguous, do not invent: write a guess to work/GUESSES.md (number, place in the norm, question, what you chose and why) and go on.
> Guesses in GUESSES.md are entries "## N" (N is the number).
> The plan goes to work/PLAN.md (about 6000 chars): packages and files, norms → files, order of steps, before any code. Decisions and what is done go to work/NOTES.md (about 8000 chars).
> Write code early and in small steps, check it with your own tests. Do not fit the code to a test around the norm: if a test and the norm disagree, write a guess to GUESSES.md.
> Do not carry deferred norms: if a norm is unclear, write a guess, do not postpone it.
> Code that changes shared state is reviewed on the properties of the model, not only on the words of the norm: write it so that the properties hold under races, retries and breaks, not only the listed steps.
