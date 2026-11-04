# The label alphabet contract

This English text is the source; the Russian [`labels.md`](../labels.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5); the Architect's decision on the analysis of the review of stage A 6–7, № 11: the label
alphabet is in `common/`). The owner is lesson [P/06](../../../06-console/spec/06.6-console.norms.md) (chapter 6.6: the label doors of a
server; moved from there; analysis of the review of stage B 6–7, № 35). Readers: the controller — the constraint `labels-subset` and the worker labels ([P/04](../../../04-controller/spec/04-controller.norms.md)
Н1.3), the console — the label field of a unit ([P/06.1](../../../06-console/spec/06.1-console.norms.md) Н1.2 `list`), the label doors
of a server and the forecasts ([P/06.6](../../../06-console/spec/06.6-console.norms.md) Н2.1), the grants by labels ([P/08.4](../../../08-domain/spec/08.4-domain.norms.md) Н1.3
`scope`). Moved from chapter 6.6 Н2.1 (formerly М10/4 Н2) without a change of behaviour. The form of the server label row is the family
`server-labels` ([P/06.6](../../../06-console/data/server-labels.schema.json)); what labels mean for placement is with the reading lessons.

Normative keywords follow [the course canon](../../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The files the contract works by (layout audit, В-33, В-34; the Architect's decision of 2026-10-25): the server label
row `platform/servers/<s>` is the family `server-labels`: `Platform/06-console/data/server-labels.schema.json`,
`Platform/06-console/data/server-labels.outcomes.tsv`; the label doors of a server (`PUT /servers/{server}/labels`, the probe `labels`,
the refusal 400) are `Platform/06-console/spec/06-console.api.openapi.yaml`.

## Label

```yaml
label:   1–64 ASCII characters: the first is a letter or a digit, then a letter, a digit, `_`, `.`, `:`, `-`;
         as a whole `[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}`; a line feed and any other character — not a label
compare: by bytes; case is distinguished   # the Architect's decision (analysis of the review of stage B 6–7, № 40): the source lessons did not name the way
                                         # of comparison
set:     a label set — without repeats, the order does not matter; a repeated label (byte equality) in the input of a write of server labels and
         in the query `labels` of the probe — a refusal 400, not a compaction (P/06.6 Н2.1, Н4; analysis of the review of stage B 6–7, № 40; the probe — (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7))
output:  a set that the platform writes or gives out (the server label row, the answers of the label doors and the forecasts, the worker labels) —
         in ascending order of UTF-8 bytes (`Vlan:a` < `gpu` < `vlan:b`, `a10` < `a9`); the order of the input is not kept; the value
         of the label field of a unit is the value of a list field (the row check contract «Unit row»), it is not reordered as a set
         (stage C guesses L01–L03, the Architect's decision of 2026-10-23)
```

## Label list

```yaml
text:    labels separated by commas (the list rule, [the row check contract](../row-check.md) `values_by_type` `list`: otherwise —
         a JSON array); "" — no label; the writer writes a JSON array compactly, without spaces (`["a","b"]`); for labels by the
         alphabet it is not needed — a label has no comma, leading `[` or empty element (stage C guesses L01–L03, the Architect's decision of 2026-10-23)
read:    a leading `[` matters only as the first character of the text: such a text is read as a JSON array (spaces between tokens
         are admissible, as at `list`), its elements are labels by the alphabet; a `[` further in the text is a label character, that is an alphabet refusal
query:   a query list is split at commas, without empty elements, except a wholly empty string (P/06.6 Н2.1)
empty:   an empty element is inadmissible in a placement label field, in an ordinary `list` it is admissible (the row check contract)
env:     LABELS of the worker environment (the environment file contract «Environment variables») — a list text, each label by the alphabet
         (otherwise a start refusal, code 2); a repeat is not a refusal: the node labels are a set, a repeat is compacted, the heartbeat writes them by output
         (ENV54-01/02, the Architect's decision of 2026-10-25)
refuse:  an element not by the alphabet — a refusal of the one who reads the input: 400 at the console doors (P/06.1 Н4, P/06.6 Н4); a repeated label in
         `PUT /servers/{server}/labels` and in the query `labels` of the probe `GET` — also 400 (P/06.6 Н4; № 40; the probe — (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7))
```

## Vectors

The package [`labels`](../../vectors/labels/README.md): a label, the write of a set, the reading of a list text, `LABELS` of the environment (`env_labels`). The label field of a unit as a list field — the packages [`values-by-type`](../../vectors/values-by-type/README.md) (`list:labels`) and [`row-check`](../../vectors/row-check/README.md) of the row check contract. (ADR-0083 addendum (32) item 2)
