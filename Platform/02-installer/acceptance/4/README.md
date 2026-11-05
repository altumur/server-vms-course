# P/02.4 — supplementary command and poll seams for the kit

This English text is the source; the Russian translation `ru/acceptance/4/README.md` is derived from it by translation and is not edited by hand (ADR-0121).

This directory supplies [`seams.tsv`](seams.tsv) to generated stagetests (ADR-0125 addendum (4) item 7 and addendum (5)). It adds no HTTP stand or public runner target for P/02.4. Its 19 steps in 11 scenarios use the exact grammar and CALL normalization of [`forms/README.md`](../../forms/README.md).

| Scenarios | Subject | Norm |
|---|---|---|
| `s1-put-invalid-source` | an invalid candidate is refused by manifest put with code 2 and the source name; the source file stays intact | P/02.3 Н3 step 1, Н4 |
| `s2-new-existing`, `s3-rotate-invalid` | a refused creation or ring check leaves the existing file byte-for-byte intact | P/02.4 Н1.9 secrets; P/02.4-14 |
| `s4-new-exclusive` | concurrent O_EXCL creation at one path succeeds once | P/02.4 Н1.9 secrets new |
| `s5-poll-healthy`–`s11-poll-read-equality` | the pure poll: catch-up under writes, a break, last at a follower, membership, two voters, equality at tick/read deadline | P/02.4 Н1.9 poll; P/02.4-22 |

Every scenario has fresh temporary roots; ring-file inputs are owned strings with no real key material. RUN calls the command function; CALL `command` observes 0 versus nonzero without prescribing an unspecified native exit code or output shape. A crash is not a refusal. The source [machine](../../forms/rollout-poll.machine.yaml) and [traces](../../forms/rollout-poll.traces.tsv) remain canonical: poll seam inputs contain only the input and timed external events, never the expected trace assertions. The adapter observes the implementation’s poll; running the course interpreter alone does not prove the implementation.

The source traces exercise the complete machine; these seven sampled poll scenarios are a smaller implementation regression. They do not prove the real rollout, get/install, store and console barriers, OS/service-manager effects, TLS, revocation, operator windows or remote-client behavior. Those retain the named checks of the norms and readiness checklist. The 946 loader cases, existing puts tables and rights acceptance remain separate. No implementation was run when preparing these seams.

## Inputs

[`inputs/seam-bad.subsystem.yaml`](inputs/seam-bad.subsystem.yaml) is the owned fixture of `s1-put-invalid-source`: a YAML document with only `name`, missing the mandatory manifest structure. The scenario copies it with `@file`, calls the normal `manifest put`, and checks the refusal and unchanged source bytes. It is deliberately outside the accepted manifest corpus. The remaining file inputs are literal owned strings in the seam table.

## Platform role socket groups

The structural unit check includes the role-socket group in SupplementaryGroups for resource, console, `<sub>controller`, domain, domainconsole and domainagent (P/02.5 Н3 item 2). It adds to, rather than replaces, the existing store/events/secret groups. Do not grant every role group to the shared w2c user. In particular domainconsole still has no w2c-secrets.

The added seam `CALL installer-role-unit-groups <JSON>` runs the ordinary installer's unit renderer/writer with a valid catalogue containing testsub, deployment w2c and the domain units enabled, in a temporary output root. Parse the actual generated service/socket units; compare each service's effective SupplementaryGroups with the role's socket SocketGroup and SocketMode=0660. `checked` counts the six actual matched roles, `missing` lists roles without their required supplementary group, `mismatched_socket_groups` lists role socket mismatches, `domainconsole_secrets` observes membership of w2c-secrets. Return observations of the generated units, not a copy of the input or expected object. This structural seam needs no service launch, root or OS-group modification; the real system stand remains its own obligation.
