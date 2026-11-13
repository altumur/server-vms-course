# Stand data of the target P/01/production

This English text is the source; the Russian translation `ru/forms/production/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

These are the data of the stand for [the production qualification of P/01](../../../common/acceptance/spec/acceptance.norms.md#n6-production-qualification-of-p01): judge only, not an input of the implementation. They add no outcome, route or flag. The duration of the long random fault run below is a qualification procedure value.

## Bindings

[`bindings.tsv`](bindings.tsv) gives, for each entry of [`production.tsv`](../production.tsv), the activations of its D7 bindings by [the payload form](../../../common/acceptance/forms/d7-payload.schema.json). The descriptor of an entry by [`d7.schema.json`](../../../common/acceptance/forms/d7.schema.json) has the scope `P/01/production#<id>` and one provider for each capability of its rows. The stand writes its `identity`, `invoke`, `observer_ref`, `qualification_ref` and `source_pin` from the provider it builds and qualifies and from the run. An entry without a qualified provider for a capability of its rows has no descriptor for it and is `not_executed` with that capability as the reason (N6.5).

- `RUN-W03` and `prod-id-age`: `clock` in the mode `observe`, real waiting with an independent observer of the clock; the stand shifts no clock.
- `prod-clock-group`: `clock` in the mode `control` over the separate wall-clock domains of the voters `s1`, `s2`, `s3`. A stand whose members share one wall clock cannot give it, and the probe is then `not_executed` with the reason `clock`.
- `storage` names the medium `ext4`, the envelope of [the first approved budgets](../../qualification/README.md#first-approved-budgets); tmpfs is not that medium.

## Input of N6.2

[`input.json`](input.json) is the input of N6.2 by [`production-input.schema.json`](../production-input.schema.json) without `source_pin`. The stand adds `source_pin`, the Source commit of the run, before it names the file in the invocation. A field that the environment has not given yet is absent, and the entries that need it are `not_executed` with its name as the reason (N6.5); no value is invented.

- `budgets` is absent until the owner approves the thresholds.
- `manager` is absent: the stop deadline of the actual manager is known (systemd of the stand), the teardown margin is not measured yet; the stand adds the object when it has both.
- `volume` is absent: a directory of limited size on the declared filesystem is given only by a volume of the host.

## Long random fault run

[`soak.json`](soak.json), checked by [`soak.schema.json`](soak.schema.json), is the Q record `RUN-SOAK`: duration 2 h, fault inventories for `group` and `box`, observed properties, negative controls, executor and environment. Its procedure is [Long random fault run](../../qualification/stand-procedures.md#long-random-fault-run). It is separate from the inventory `production.tsv` and the run input `input.json` of N6.2; it adds no functional judge directive or input field of N6.2.

`sigkill_*` means `kill -9`; `sigstop` means SIGSTOP followed by resumption; `sigterm` means SIGTERM. `checkpoint_sigkill` uses the listed checkpoint points, and `unsynced_loss` discards data that has not reached a durability barrier under the independently observed storage fault model. A process kill alone does not establish that loss. `unique_applied_versions` distinguishes logical applications: a replay retains the first version.

`barrier_noop_power_loss` suppresses file barriers with false success before qualified loss of unsynchronised data. `directory_barrier_noop_power_loss` does the same only to parent-directory barriers after a successful rename, leaving file barriers honest. `isolated_read_stale_response` uses a two-way peer partition and a stand fixture's stale public response after a newer write has completed. The [procedure](../../qualification/stand-procedures.md#history-properties-and-controls) defines their activation, correct fixtures, history witnesses and missing-binding outcomes. They qualify the stand and checker without code mutants of a candidate; naming them without activation qualifies nothing.

The record's executor fields `scope: load_and_faults` and `stand_controls: requires_qualified_binding` limit the historical executor reference to its load and faults. The fixed revision is not evidence that it implements the new stand controls. A run must explicitly bind and independently qualify their actual executor; until then the dependent controls remain unexecuted with the missing capability under N6.5. No unqualified result from the historical executor discharges them.

Before the qualifier is ready, `court-tools` at `6fd588df`, directory `soak/`, executes the load/fault portion of this record; afterwards it is the comparison reference for that scope. Heavy runs use a virtual machine; until it is available they use CT 103 under the existing [load gate](../../../common/acceptance/spec/acceptance.norms.md#n33-declared-environment). VM-only cases remain `not_executed` with their reason until the VM exists; the long run itself remains a promotion gate. Workload, random seed, fault schedule and actual timing are recorded by the run; this record sets no additional rate, interval, repetition count or numeric budget.
