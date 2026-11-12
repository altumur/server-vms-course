Implement P/01 from scratch in 01-store, using only the pinned model-visible specification M. Implement the complete store, including the Raft group behavior, public interfaces, persistence, recovery and production obligations described by M. Write your own code and meaningful tests. Read the public contracts, forms, schemas, protocols and dependency versions in M as needed; do not use another implementation, generated SDK, judge or hidden case corpus.
This is generation only. The loop checks compilation, go vet and your own Go tests. Those checks do not establish conformance to the specification. No acceptance judge, judge feedback, stand gate or judge profile is used during generation. The finished candidate is judged separately after generation. Do not replace required product behavior with adapter answers or hard-coded examples. All implementation, auxiliary code and tests are your work. SPEC_VERSION identifies the immutable M input.
For each learning stage, implement its stated goal and norms. The source stage names/goals/norm references define the progression; acceptance/scenario/seam gates are not executed in this generation run. Keep the full implementation and tests coherent across all eleven stages. Use the public pinned Go dependencies with the supplied offline module cache. Produce a buildable complete candidate and tests exercising its behavior; tests that only check a stub are insufficient for your implementation goal.
The P/01 group is built in the variant keys.store_build: raft, on the library named by Platform/common/versions/README.md of M.
A run with -group-size 3 must bring up the group on the Raft library named by Platform/common/versions/README.md of M.


---

## Environment of this run

This section only says where things are in this run; the task above is unchanged.

- The specification export M is read-only at "$SPECS" (an absolute path in your shell's environment). SPEC_VERSION: be48405e645b49985d35efc42b6d61c2f304c4d8.
- Your working tree is the current directory, "$WORK" (below: work/). It is the implementation root and already holds SPEC_VERSION; the lesson module is the directory 01-store in it. Write all code there. Nothing else on the machine is visible to you.
- Commands have no network. Go 1.22.10 is on PATH; Go dependencies come only from the offline module cache (GOPROXY=off, GOSUMDB=off, GOTOOLCHAIN=local, GOWORK=off, GOFLAGS=-mod=mod are set).
- The command `check` runs the gates of the generation loop of this attempt on work/ as it is now and prints what the loop would show you after a round: the stages green in order, then the first red stage with its gate lines. The gates are built from M only: the build, `go vet` and your own Go tests in work/01-store; the code checks of the stages; the norm trace of each stage's checklist items, with mutation of the code they cover and the mode of the item; your own tests of the packages a stage changed; the profile of the implementation (assembly.yaml at the implementation root, the module's acceptance.yaml) and its commands, by PROFILE.md and the forms of M. No acceptance judge runs and no verdict is shown: this is generation only. A full check takes minutes; you decide when to run it. It never tells you a correct answer.
- If, by your reading of M, a gate demands something wrong, do not fit the code to it: write a guess to work/GUESSES.md with the place in M, what the gate wants and what you think M says, and go on.
- The budget of this run is 150 million input tokens (cached input counted) and 24 active hours. The run ends when you end it or when the budget is spent.
- The stages are the rows of "$SPECS/Platform/01-store/forms/stages.tsv". The lesson files a generator is given in full at the start are:
  Platform/01-store/README.md, Platform/01-store/spec/01-store.README.md, Platform/01-store/lifecycle.md,
  Platform/01-store/forms/stages.tsv, Platform/01-store/forms/write-checks.tsv, Platform/01-store/spec/01.1-store.norms.md,
  Platform/01-store/spec/01.2-store.norms.md, Platform/01-store/spec/01.3-store.norms.md,
  Platform/01-store/spec/production-acceptance.md, Platform/common/acceptance/PROFILE.md,
  Platform/common/acceptance/runner-targets.README.md, Platform/common/contracts/vector-adapter.protocol.json,
  Platform/common/versions/README.md, Platform/01-store/probes/README.md (all under "$SPECS").

Working notes and work rules (quoted from the generation loop's instructions and rules; work/ is "$WORK"):

> Where a norm is silent or ambiguous, do not invent: write a guess to work/GUESSES.md (number, place in the norm, question, what you chose and why) and go on.
> Guesses in GUESSES.md are entries "## N" (N is the number).
> The plan goes to work/PLAN.md (about 6000 chars): packages and files, norms → files, order of steps, before any code. Decisions and what is done go to work/NOTES.md (about 8000 chars).
> Write code early and in small steps, check it [...]. Do not fit the code to a test around the norm: if a test and the norm disagree, write a guess to GUESSES.md.
> Do not carry deferred norms: if a norm is unclear, write a guess, do not postpone it.
> Code with distributed state (consensus, groups, transfer) is reviewed on the properties of the model, not only on the words of the norm: write it so that the properties hold under races, retries and breaks, not only the listed steps.
