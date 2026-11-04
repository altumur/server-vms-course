# The holds contract: the manifest section `holds`, hold rows, what they hold

This English text is the source; the Russian [`holds.md`](../holds.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes is a contract, not copies in
chapters; the stage C guess R05-G06, the Architect's decision of 2026-10-23). The owner is lesson P/06, [chapter 6.4](../../../06-console/spec/06.4-console.norms.md)
Н1.5 `holds`. The rows of the hold table are written by the table door of the console ([P/06.1](../../../06-console/spec/06.1-console.norms.md) Н1.6); the holds
are read by the resource in the term pass ([P/05](../../../05-resource/spec/05-resource.norms.md) Н3 «resource pass» `retain`; the rights —
[P/02.5](../../../02-installer/spec/02.5-installer.norms.md) Н1.4, the row `resource`: «the table `holds`, the rows of manifests with
`about`»). The form of the section in the manifest and the reference checks by the loader are [P/02.1](../../../02-installer/spec/02.1-installer.norms.md)
Н1.2 `holds`, references 50–54. Decisions: [ADR-0057](../../../../decisions/0057-консоль-из-каталога-спек-хуки-консоли-уходят.md)
(the addendum of 2026-10-10 — `released`), [ADR-0091](../../../../decisions/0091-механизмы-платформы-по-запросам-vms.md) item 8 (the hold «about»).

Moved from P/06.4 Н1.5 `holds` and `about` without a change of behaviour; added are the rules of reading the window and the addressee with an incomplete
declaration and unreadable rows — in them the rule «an unknown read is not equal to absence» applies (P/05 Н1.3 `retention`
`rule`): what is not read reliably is held.

Normative keywords follow [the course canon](../../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The reasons of the term pass and the count of unreadable hold rows (`garbled_rows.<table>`, `retention_withheld`) are written by the resource into its
heartbeat — the family `resource-heartbeat`: `Platform/05-resource/data/resource-heartbeat.schema.json`,
`Platform/05-resource/data/resource-heartbeat.outcomes.tsv` (layout audit, В-30; the Architect's decision of 2026-10-25).

## Declaration

```yaml
holds:      a section of the manifest <M>: {table, unit, since, until, longest?, released?} — names: table — a table of the manifest
            (tables.<table>), unit, since, until, released — fields of this table; longest — seconds, a number > 0
  complete: the declaration is complete when table, unit, since and until are named; longest and released are optional
            (ADR-0057: longest?, released?); the loader accepts the section without them too (P/02.1 Н1.2: all keys are optional)
  partial:  the declaration is incomplete — the holds of the manifest are not read: the resource removes nothing by term in the trees of the addressee
            (below); a manifest without the section holds has no holds
addressee:  A — the subsystem of the addressee: about.sub of the manifest <M> if <M> declares about, otherwise <M> itself
            (ADR-0091 item 8); the trees of the addressee — <A>, <A>.alarms and <X>, <X>.alarms of each manifest X of the catalogue whose
            about.sub = A (including <M> itself)
```

## Hold row

The row is `<M>/<table>/<id>`; the elements are texts by `values_by_type` ([the row check contract](../row-check.md) «Unit row»;
the vectors [`values-by-type`](../../vectors/values-by-type/README.md); Б-23).

```yaml
released:   released is declared and the element of this field in the row exists and is non-empty (a text longer than zero) — the row holds nothing,
            whatever the other fields are (ADR-0057, the addendum of 2026-10-10); the type of the field does not matter: a number written as 0 is
            a non-empty text
unit:       the element of the field unit — the id of a unit of the subsystem A as it is, byte for byte; there is no element or it is empty — the addressee is not
            read
since, until: the elements of the fields since and until read by their type are finite numbers, wall seconds (the codec `Platform/common/data/codec.tsv`, the row `time`; Б-27);
            the notation is also read by the reader `time`: ^(0|[1-9][0-9]*)(\.[0-9]+)?$, the value is finite — «-1», «+5», «1e3» are out of form,
            though the type int or float would read them (the Architect's decision of 2026-10-27, as OBS154-RAW-TIME-EXACT-01);
            there is no element, it does not read by its type or by the reader `time`, the field is not of a numeric type or the number is not finite — the window is not read
window:     the window [since, end], end = until, with longest — min(until, since + longest); until ≤ since — the row holds
            nothing (an empty window)
bucket:     a bucket holds the window when its segment [start, start + 600 s] (the event journal contract `bucket` `span`)
            intersects the window, the ends included
```

A row that did not decode as a row of the table — neither `released`, nor the addressee, nor the window is read.

## What a row holds

The row is not released (`released` above):

| Read | Holds |
|---|---|
| the addressee and the window | the buckets of the unit `<A>/<id>` in the window — in the trees `<A>`, `<A>.alarms`; the buckets in the window of the units `<X>/<u>` of the trees `<X>`, `<X>.alarms` whose field `about.field` names `<id>` — including deleted ones: the value of `about.field` is also read from the tombstone of the unit row; the buckets in the window of the units `<X>` of which it is unknown whether they name `<id>` (there is no row and no tombstone, or the row does not read) — while this is unknown: «I do not know» is not «nobody's» (ADR-0091 item 8) |
| the addressee, the window — not | the same without the window: all buckets of these units |
| the addressee — not | all buckets of the trees of the addressee |

Holds — the bucket is not removed by term (`retain`); the other term rules (days, the floor of the console marks, the hour of mirror copies —
P/05 Н1.3 `retention`, Н3 `retain`) apply to the buckets that no row holds. A row whose addressee or window is not read
and which is not released is counted in `garbled_rows.<table>` of the resource heartbeat (P/05 Н1.4).

## Reading the table

The resource reads the rows `<M>/<table>/` by a store listing in every term pass. The listing is not received whole (a store
error, a cut, a rights refusal) — the holds are not read: remove nothing in the trees of the addressee in this pass, the reason in the
heartbeat (P/05 Н4, the row «retention: … holds failed to read»). An empty complete listing — there are no holds.

## Vectors

The package [`holds`](../../vectors/holds/README.md) — the function «does the row hold the bucket» (the input — the declaration, the row, the segment of the bucket;
the output — `held` | `not_held` | `unknown`): the sections «Declaration», «Hold row», «What a row holds» without the choice of the trees of the
addressee (ADR-0083 addendum (37) item 5). Reading the elements of a row by their type is the package
[`values-by-type`](../../vectors/values-by-type/README.md). The table listing, the trees of the addressee and the hold «about» are checked
by reading; the removal by term too: the stand does not wait out the term of buckets (P/06.4-08, P/05-06).

## Correspondence to former lessons

From P/06.4 Н1.5 (`holds`, `about`): the declaration, `released`, the window, `longest`, the hold «about» (the norm P/06.4-08 — by `note` of
[id-map](../../id-map.tsv)). P/06.4 Н1.5 and P/05 Н3 `retain` refer here.
