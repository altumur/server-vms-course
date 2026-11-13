# P/02.4 — supplementary command and poll seams for the kit

This English text is the source; the Russian translation `ru/acceptance/4/README.md` is derived from it by translation and is not edited by hand.

This directory supplies [`seams.tsv`](seams.tsv) (judge-only: the seam table) to generated stagetests. It adds no HTTP stand. The engine word `run` executes the table through the seam adapter protocol of the common acceptance README; its scenarios use the exact grammar and CALL normalization of [`forms/README.md`](../../forms/README.md).

The obligations of these scenarios are P/02.3 N3 «Manifest change» step 1 and N4, P/02.4 N1.9 «Command options» (P/02.4-R271), P/02.4 N1.9 `secrets` and «Walk» (P/02.4-R371, P/02.4-R383, P/02.4-R386, P/02.4-R388, P/02.4-R394, P/02.4-R400, P/02.4-R401), P/02.4 N1.9 `manifest get` (P/02.4-R286, P/02.4-R287, P/02.4-R292), and P/02.4 N1.9 poll (P/02.4-R305, P/02.4-R307, P/02.4-R319, P/02.4-R321, P/02.4-R324, P/02.4-R330, P/02.4-R332); the scenario subjects are in the judge's case data.

Every scenario has fresh temporary roots; ring-file inputs are owned strings with no real key material. RUN calls the command function; CALL `command` observes 0 versus nonzero without prescribing an unspecified native exit code or output shape. A crash is not a refusal. The source [machine](../../forms/rollout-poll.machine.yaml) and [traces](../../forms/rollout-poll.traces.tsv) (judge-only: the source traces of the poll machine) remain canonical: poll seam inputs contain only the input and timed external events, never the expected trace assertions. The adapter observes the implementation’s poll; running the course interpreter alone does not prove the implementation.

The source traces exercise the complete machine; these seven sampled poll scenarios are a smaller implementation regression. They do not prove the real rollout, install, store and console barriers, OS/service-manager effects, TLS, revocation, operator windows or remote-client behavior. Those retain the named checks of the norms and readiness checklist. The 951 loader cases, existing puts tables and rights acceptance remain separate. No implementation was run when preparing these seams.

## Profile interface

The [generic profile contract](../../../common/acceptance/PROFILE.md) does not make these generated CALL seams into a new public stand target. The `02-installer` vector interfaces `stand.workers-script`, `stand.platform-lists`, `stand.exec`, `stand.install-order` and `stand.env-line` each receive `{input}` with the exact native input and outcome assigned by their package rows in the [wire form](../../../common/vectors/wire.tsv) and package README. They call the implementation's own functions. `stand.ring` creates the ring at `{file}` through the existing secrets command; it is not a permission to replace an existing file. A `vectors` envelope is used only on a surface explicitly declared by that form, without inventing an alias for a native stand command. These declarations do not connect or execute the otherwise unbound seams.

## Inputs

File inputs of the seam table are judge-owned; their descriptions are in the judge's case data.

## Platform role socket groups

The structural unit check includes the role-socket group in SupplementaryGroups for resource, console, `<sub>controller`, domain, domainconsole and domainagent (P/02.5 N3 item 2). It adds to, rather than replaces, the existing store/events/secret groups. Do not grant every role group to the shared w2c user. In particular domainconsole still has no w2c-secrets.

The seam `CALL installer-role-unit-groups <JSON>` uses the [CALL normalization](../../forms/README.md#call-normalization).

## Secrets walk selection

The seams `s12-secrets-walk-unknown` and `s13-secrets-walk-kept` check the selection of P/02.4 N1.9 «Walk». The input of
`CALL secrets-walk <JSON>` is `{argv:["w2cctl","secrets","status"|"seal",<prefix>,…], rows:{<key>:<row>,…}}`, a row is an object of
string elements. The adapter uses [store and installed manifest preparation](../../../common/acceptance/seams.md#store-and-installed-manifest-preparation), installs the owned manifest [`testsub`](../2/puts/testsub.subsystem.yaml) (judge-only: the manifest fixture of chapter 2.2) by the
ordinary `manifest put`, writes exactly the given rows by `cas ""`, sets no ring (`SECRETS_KEY` is unset) and invokes the command
function with argv against this store. It returns `{exit_code:<integer>, unknown:[…], untouched:<bool>}`: `unknown` — the keys of
the log lines «`<key>` unknown-row-form» of the call, sorted, each once; `untouched` — every given row has the same bytes and version
after the call. By P/02.4 N1.9 «Walk» a row that matches no row family is listed, code 1; a kept row of a manifest (`domain.kept`) is not listed and does not affect the code. The seam `s15-secrets-walk-unreadable` uses the same input for a walked row out of the form of its family (`domain/book-seal` without `seed_secret`, the reader `admin` of its outcomes): by P/02.4-R396 the row is unreadable, not unknown — it is not listed in `unknown`, it stays untouched, code 1. The three seams are selected by stage 8 of [`stages.tsv`](../../forms/stages.tsv) and contribute their walk-selection observations to P/02.4-14. The unavailable walk (P/02.4-R402), deep resealing and envelopes that do not open remain checked by reading.

## Manifest get

The command seams use the shared fresh P/01 store of the [scenario layout](../../forms/README.md#scenario-store). Their explicit `RUN w2cctl manifest put` calls install only the input files written by earlier `@file` steps, outside `$manifest`; the `get` calls read the same store and write `$manifest`. No implicit manifest is added. The operator hash is the SHA-256 of the exact input YAML bytes supplied to `put`, fixed before `get`; it is not copied from the row returned to `get`.

Stage 8 selects the refusal and replacement seams. They check code 2 and intact former YAML, shell and static files on a wrong operator hash or a missing row (P/02.4-R286, R292); successful replacement of YAML, shell and two static files and a repeat with the same hash; quarantine of a former shell over an existing `.old`, including a repeat (R287); and preservation of a static file removed from the new manifest and of an unrelated file (R292). Case inputs and associations are in the judge's case data.

These observations cover only those branches. An unreadable row or part, a write error, removal of temporary files, atomic rename order, interruption between replacements and whether an already equal file was touched remain checked by reading. The real rollout and the obligations of P/02.4-25 remain their own checks.
