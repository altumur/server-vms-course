# Acceptance P/08.3 — admission of reports

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md), the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand)
(the dictionary of directives and doors of the stand of several clusters). The norm of the chapter is
[`08.3-domain.norms.md`](../../spec/08.3-domain.norms.md) N5. In total 21 scenarios / 218 steps.

The commands `agent-sig`, `seal-member`, `seal-member-round`, `accept` are the vectors of the common contracts [`agent-sig`](../../../common/vectors/agent-sig/README.md), [`domain-envelopes`](../../../common/vectors/domain-envelopes/README.md) and [`accept`](../../../common/vectors/accept/README.md) (judge-only: the test vectors of these contracts; they check P/08.3-R009, P/08.3-R016, P/08.3-R078, P/08.3-R161, P/08.3-R166, P/08.3-R167, P/08.3-R169, P/08.3-R170, P/08.3-R171, P/08.3-R180, P/08.3-R182, P/08.3-R183, P/08.3-R191, P/08.3-R202, P/08.3-R203, P/08.3-R206, P/08.3-R208, P/08.3-R233 and P/08.3-R218).

## Stand

**Preparation of each scenario**. The runner brings up on
one machine three clusters — `hold`, `m1`, `m2`: each has its own empty store, its own `{data}`, its own role sockets and
ports of the console and the resource, its own ring (P/06.2 N1.2), the manifest catalogue — only `testsub`; the console, the controller and the worker `w-1`
of `testsub`, the resource of its own server (`srv-hold`, `srv-m1`, `srv-m2`). There are no units. There is no domain: it is set up by the steps of the scenario
(`@install domain`, `@start domain`, `@start agent`) or by the directive `@domain`. The domain name is `acme`; the recovery file of the
installation is `{recovery}` in the instance directory.

- `store` at `member <cluster>` is the store door of the cluster through `admin.sock` (the preparation and the observation of the domain rows).
- `resource` without a prefix is the resource door of `hold`: through it the holder's objects `domain/members/<member>/…` are read.
- Do not speed up the clocks: LOST_AFTER 45 s, REPORT_EVERY 5 s, MARK_REFRESH 22.5 s; the `@until` terms are taken with a margin.

**Stands with a relay:** there are four clusters — `hold`, `m1`, `m2`, `relay`. The agent `relay` always
opens the relay door (`RELAY=1`, `{relay_port}`); the directives `@domain <clusters>`, `@start agent <cluster> via
relay`, `@stop agent`. The topology is empty until the step that writes it.

The doors of the stand do not speak TLS: the agent only publishes the fingerprints and the certificates of the centres (N1.6 `tls_ca`, `tls_ca_certs`). How the runner passes the environment and restarts the console and the agent of the cluster with the variable
(`@env`) — the dictionary of the «Domain stand» of [the common acceptance README](../../../common/acceptance/README.md), `@env` and
«Forwarding environment».

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and the section «Domain stand». `$fp1`, `$fp2` are fingerprints that the runner
binds from `knocking` and substitutes into the admission: so the stand repeats what a person does, comparing the fingerprint with the log of
the agent; `$kr` is the `rev` of the set from `trust` of the view; `$k` is the private key of the batch from the answer of `POST /domain/batches`, the runner gives it to the command `join` by the directive `@join`. In total 21 scenarios / 218 steps.

The stand does not cause the loss of the holder's memory (409 `rebase`): it is checked by the vectors `accept` and by reading the contract of the admission of a report.

## Evidence outside the TSV

Checked by reading (the norm of the chapter, N5): the CAS of the admission of a member, a failure between the writes of a generation, of `delta` and of the mark, `sign_failures`
in the mark and the view, non-matching certificates `tls_ca_certs`, the union of the handshake at the role door (lesson P/10 N1.4). The knock and the checks
of the holder on a relay packet — [the acceptance of chapter 9.2](../../../09-agent/acceptance/2/README.md).

## Kit seams

[CALL seams](seams.tsv) (judge-only: the seams of chapter 8.3; they check P/08.3-R009, P/08.3-R188, P/08.3-R195, P/08.3-R280, P/08.3-R281, P/08.3-R282, P/08.3-R283 and P/08.3-R286) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.
