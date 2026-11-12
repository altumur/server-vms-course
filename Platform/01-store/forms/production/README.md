# Stand data of the target P/01/production

This English text is the source; the Russian translation `ru/forms/production/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

These are the data of the stand for [the production qualification of P/01](../../../common/acceptance/spec/acceptance.norms.md#n6-production-qualification-of-p01): judge only, not an input of the implementation. They add no outcome, number, route or flag.

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
