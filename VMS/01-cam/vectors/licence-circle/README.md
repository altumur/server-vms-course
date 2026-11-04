# Vectors: the licence counting circle

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson V/01 ([the norms of chapter 7](../../../spec/01.7-cam.norms.md) Н1.2, Н3 «Счёт»; ADR-0113 addendum (11) item 5). The numbers are derived from the text of the norm and are not checked by an implementation. The run — after the first stage C generation.

## Files

| File | What |
|---|---|
| `cases.tsv` | one circle per row: `case`, `input`, `expect`, `note` |

## Fields

- `input` — `units` (`null` — there is no document), `doc`, `state`, `row` — the row `domain/cam/licence-count` on input (`null` — there is no row), `head` — the `parts` of the head, `budget` — sections per pass, absent — all, `sections` — per section the `refs` of the cameras of the set, `licensed` of the previous decisions, in the simplification one member per section, `never` — the ref of a member row `never`, `unreadable` — the decision is not readable, `view_unread` — the view row is not readable, `units` — the records of the view for the summary, absent — all `running`.
- `expect` — `read` — the sections read, `decisions` — `licensed` of the sections read, `row` — the row at the end of the pass, `doc`, `state` — in the key of the section, `part` only for a circle that is not closed, `summary` — the sums of the summary of states, only at the end of the circle.
