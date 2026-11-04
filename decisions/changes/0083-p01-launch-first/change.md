# Change 0083-p01-launch-first — the stage launch right after model, the daemon frame a part of kit B (ADR-0083 addendum (95) item 3)

change: 0083-p01-launch-first rev 1 · lesson P/01 (delta_base 725653954) · author «Спецификация» · state review

**Why.** ADR-0083 addendum (95): the seventeenth stalled on `launch` (160 moves, 0 of 1); the daemon frame is a new part of kit B,
`launch` (the flags by the form, the sockets, the mark `FORMAT`, `apidoor.Handle` over the `Handler` of the model, the methods
stubs). The word of the Architect (the owner's «да»): `launch` right after `model` (depends 1), so that the daemon answers from the
start, as in the sixteenth; `store_core` and the rest after `launch`; the gate `accept:1.1:01-absent` on the frame with an empty core.

**The order.** 1 model, 2 launch (depends 1), 3 jcs, 4 store_core (depends 1, 2, 3), 5 http (4), 6 rights_eval (2 — `launch`, as
before), 7 rights (5, 6), 8 daemon_box (5), 9 durable (8), 10 group (8, 9): the stages after `launch` keep their dependencies by
name. `launch`: parts `launch` (the part `flags` is inside it), kit `-` — the model still gives an empty core that answers
`01-absent`; the stubs «not implemented» alone do not close the stage.

## Manifest

| Artifact | Operation | Base | Result |
|---|---|---|---|
| `Platform/01-store/forms/stages.tsv` | replace: the order and n, depends, the goal and parts of `launch`, the header (the part `launch`) | 9329a0ccea22ff438e35228b881515f048f3aa10 | f4e20eed0c7919a3da144629b750632a5e975622 |
| `skills/lesson-spec/scripts/check_forms.py`, `test_check_forms.py` | the part `launch`; n in order, depends — former stages | — | — |
| `decisions/adr-norms.tsv`, `decisions/changes/registry.tsv` | append the rows of the change | — | — |

## Change map

| Place | Mark |
|---|---|
| `spec/01-store.README.md` «Order of work» | agreed: it refers to the table; the advice by chapter does not name the order of stages |
| `acceptance/1/README.md` «`seams.tsv`» | agreed: names `store_core` and `durable` by name |
| the norms of P/01, acceptance | not related: unchanged |

## History

- rev 1, 2026-11-04 — «Спецификация»; applied in the branch `spec/0125-launch-early`.
