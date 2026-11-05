# Delta 0126-p01-daemon-split — separate the one-box daemon doors from copies (P/01)

change: 0126-p01-daemon-split rev 1. The norms of P/01 do not change. The plan in `forms/stages.tsv` is changed by a whole-file
replacement against the expected blob (ADR-0122 addendum (1) item 4; the manifest in `change.md`). The form rows are identified by
`stage`: remove `daemon_box`, add `daemon_doors` and `daemon_copy`, and update only the order numbers and dependency references
of `durable` and `group`. The implementation README introduction and its Russian translation describe the split.

## ADDED

(none)

## MODIFIED

(none)

## REMOVED

(none)
