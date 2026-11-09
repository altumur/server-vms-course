# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/alarm-history/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing case data as judge-only provenance.

### Original passage 1

The comparison is JSON by value. 16 rows: 8 `same` (including `t_src` 990 and 990.0, absent and `null`), 1 `page`, 7 `write` (creation with
`cut_before` 0, without a repeat by `same_line`, removal by the week and the movement of `cut_before`, nothing removed, equal `t` at
the boundary `HISTORY_LINES` 2000; AH-SAME52-01, AH-CUT52-01).

End of judge-only case data.
