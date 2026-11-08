# P/02.4 — supplementary command and poll seams for the kit

This English text is the source; the Russian translation `ru/acceptance/4/README.md` is derived from it by translation and is not edited by hand (ADR-0121).

This directory supplies [`seams.tsv`](seams.tsv) to generated stagetests (ADR-0125 addendum (4) item 7 and addendum (5)). It adds no HTTP stand or public runner target for P/02.4. Its scenarios use the exact grammar and CALL normalization of [`forms/README.md`](../../forms/README.md).

The obligations of these scenarios are P/02.3 N3 step 1 and N4, P/02.4 N1.9 `secrets` and «Walk» with P/02.4-14, and P/02.4 N1.9 poll with P/02.4-22; the scenario subjects are in [judge-only case data](README.cases.md).

Every scenario has fresh temporary roots; ring-file inputs are owned strings with no real key material. RUN calls the command function; CALL `command` observes 0 versus nonzero without prescribing an unspecified native exit code or output shape. A crash is not a refusal. The source [machine](../../forms/rollout-poll.machine.yaml) and [traces](../../forms/rollout-poll.traces.tsv) remain canonical: poll seam inputs contain only the input and timed external events, never the expected trace assertions. The adapter observes the implementation’s poll; running the course interpreter alone does not prove the implementation.

The source traces exercise the complete machine; these seven sampled poll scenarios are a smaller implementation regression. They do not prove the real rollout, get/install, store and console barriers, OS/service-manager effects, TLS, revocation, operator windows or remote-client behavior. Those retain the named checks of the norms and readiness checklist. The 947 loader cases, existing puts tables and rights acceptance remain separate. No implementation was run when preparing these seams.

## Profile interface

The [generic profile contract](../../../common/acceptance/PROFILE.md) does not make these generated CALL seams into a new public stand target. The `02-installer` vector interfaces `stand.workers-script`, `stand.platform-lists`, `stand.exec`, `stand.install-order` and `stand.env-line` each receive `{input}` with the exact native input and outcome assigned by their package rows in the [wire form](../../../common/vectors/wire.tsv) and package README. They call the implementation's own functions. `stand.ring` creates the ring at `{file}` through the existing secrets command; it is not a permission to replace an existing file. A `vectors` envelope is used only on a surface explicitly declared by that form, without inventing an alias for a native stand command. These declarations do not connect or execute the otherwise unbound seams.

## Inputs

File inputs of the seam table are judge-owned; their descriptions are in [judge-only case data](README.cases.md).

## Platform role socket groups

The structural unit check includes the role-socket group in SupplementaryGroups for resource, console, `<sub>controller`, domain, domainconsole and domainagent (P/02.5 N3 item 2). It adds to, rather than replaces, the existing store/events/secret groups. Do not grant every role group to the shared w2c user. In particular domainconsole still has no w2c-secrets.

The added seam `CALL installer-role-unit-groups <JSON>` runs the ordinary installer's unit renderer/writer with a valid catalogue containing testsub, deployment w2c and the domain units enabled, in a temporary output root. Parse the actual generated service/socket units; compare each service's effective SupplementaryGroups with the role's socket SocketGroup and SocketMode=0660. `checked` counts the six actual matched roles, `missing` lists roles without their required supplementary group, `mismatched_socket_groups` lists role socket mismatches, `domainconsole_secrets` observes membership of w2c-secrets. Return observations of the generated units, not a copy of the input or expected object. This structural seam needs no service launch, root or OS-group modification; the real system stand remains its own obligation.

## Secrets walk selection

The seams `s12-secrets-walk-unknown` and `s13-secrets-walk-kept` check the selection of P/02.4 N1.9 «Walk». The input of
`CALL secrets-walk <JSON>` is `{argv:["w2cctl","secrets","status"|"seal",<prefix>,…], rows:{<key>:<row>,…}}`, a row is an object of
string elements. The adapter prepares a fresh store of the scenario (the store of P/01 with the full-rights door, in process or as a
temporary daemon under `$data/configstore`), installs the owned manifest [`testsub`](../2/puts/testsub.subsystem.yaml) by the
ordinary `manifest put`, writes exactly the given rows by `cas ""`, sets no ring (`SECRETS_KEY` is unset) and invokes the command
function with argv against this store. It returns `{exit_code:<integer>, unknown:[…], untouched:<bool>}`: `unknown` — the keys of
the log lines «`<key>` unknown-row-form» of the call, sorted, each once; `untouched` — every given row has the same bytes and version
after the call. In `s12` (the default D) `identity/x` matches no row family: it is listed, code 1; the kept rows
`domain/testsub/ledger` and `domain/testsub/badges/b1` (testsub `domain.kept: [ledger, badges/]`) are not listed. In `s13` (the given
prefix `domain/`, only kept rows) nothing is walked: code 0. Both seams are outside a stage gate of
[`stages.tsv`](../../forms/stages.tsv): the generated kit has no adapter function for this CALL yet, and the seams are not claimed as run.
