# Course test subsystems

This English text is the source; the Russian translation `ru/data/testsub/README.md` (for people, not in the export) is derived from it and is not edited by hand (ADR-0121; ADR-0124).

The course owns the canonical manifests [`testsub.subsystem.yaml`](testsub.subsystem.yaml) and [`testsub2.subsystem.yaml`](testsub2.subsystem.yaml) here (ADR-0083 addendum (115)). The first is the named-counter subsystem; the second exercises the declared platform keys. Their initial bytes are exact copies from the accepted joint.

The files left in `Source/tests/testdata/` are immutable witnesses. Comments imported with the manifests describe their provenance; references to a product copy create no current synchronization requirement. The course changes these canonical manifests independently and does not run product `sync-course.sh`.

The installer stand's console files remain the existing acceptance assets of P/06.5; this directory does not duplicate those bytes. Readers and generators use these two explicit canonical paths; they do not fall back to Source witnesses.
