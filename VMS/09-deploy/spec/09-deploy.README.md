# V/09 Deploying VMS — instructions for an implementation

This English text is the source; the Russian [`09-deploy.README.md`](../09-deploy.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the VMS installation does and how to check the result. The canon is the norms of the chapters `09.K-deploy.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75`.

## Inputs and their priority

- The canon: the norms of the chapters `09.K-deploy.norms.md` (Н1–Н5 of each chapter; the addresses `V/09.K Н…`).
- [The lecture](../../09-deploy.md) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/09.1 | the source: nine manifests (`backend` — with the V/11 generation), the pages next to the manifests, `worker.exec`, the part `obsd`, the vendor key; `W2C_DEPLOYMENT=vms`, `CONSOLE_ROOT=cam`; the order of `manifest put` (`requests` and the token kinds; `near` is not an edge, in one pass); after installation the volumes of the part are mounted, the server volume is declared by a row `rec/volumes` | by reading; installation on the stand |
| V/09.2 | a sample file of each subsystem with the keys of lessons 01–07, 10, 11; the site lines `SERVER_NAME`, `LABELS`, `CONSOLE_ORIGINS`; the files of the nine roles in the package that pass the memory rule (`recworker` ≥ 1951 MB with `CAPACITY=50`), `CAPACITY` by the rule and the named load limit | by reading; installation on the stand |
| V/09.3 | one package for all kinds of clusters (the difference is a property of the server, `BUILD`); the composition — the executables, the bytes of the canon, `obsd` with patches 01–07, the media library from the OS packages, the role files; delivery by push or pull; the notices and the sentence about the licence of each dependency | by reading; installation on the stand |
| V/09.4 | health is a failure (`/<sub>/unplaceable`, the owners' «Failure» phases, `workers_live`), the series `console.running` is a diagnostic; «the archive is growing» — `recordings_running`, `writer` ok, `volume_error` 0, no `archive_failure` (`last_frame_age` is a hint) | by reading; installation on the stand |

The installation is a mechanism of the platform (P/02.4): the VMS implementation gives the source and the values, not an installer of its own.

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/09.4 Н1.1 | judging health by a difference of counts | health is a failure (the «Failure» phases, `/unplaceable`, `workers_live`); the counts are diagnostics |
| V/09.2 Н1.3 | computing `CAPACITY` without the load limit | `min(память, предел)` with `unit_mb`, otherwise the limit; the package file is the `default`, the operator edits it for the server |
| V/09.1 Н1.2 | putting the installation under an OS name base other than `vms` | `W2C_DEPLOYMENT=vms`: the share directories and the `obsd` client group depend on it |

## Done when

The sample files of the subsystems and roles pass the environment file contract and the memory rule; an installation on the implementation's stand gives
the health of chapter 4; the checklist items marked «by reading» are confirmed by the implementation description. The check of the platform
installer does not substitute for it.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.
