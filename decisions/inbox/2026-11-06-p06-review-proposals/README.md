# P06 related review proposals: INACTIVE

Base c81dd35d5ff850c687c94d251cdc84269e28730d. Only this inbox directory is changed by this early commit. No shared source, checker, reader, wire, consumer, schema, corpus or published byte is activated. These are concrete inputs for Architect review through coord103, not additional adopted norms or a CODE-ready source freeze.

- [C2 packet/formula and byte probes](c2-packet.md), [measured witnesses](c2-byte-witnesses.json).
- [C3 loader condition, proposed IDs and unchanged schema/view hashes](c3-loader-proposal.json). Existing947/220/rights/P03 untouched; normalized protection predicate and exact rule scope need approval.
- [C4 form/selector and comparison decision](c4-turn-proposal.json), [15 proposed operations rows](c4-turn-cases.proposed.tsv), [one proposed wire row](c4-wire-row.proposed.tsv). These are not sources of active generation. The current wire form rejects compare=turn; a new approved form is required before copying any row to active wire.
- [One-path source binding and valid/invalid fixtures](source-binding-proposal.json). Existing marker/decoder only, no shared change.
- [Localization and rootdoc text proposal](ui-related.md), no bytes behavior or P07 rewrite.

`prepare.py` deterministically reproduces the JSON/TSV proposal artifacts by reading exact c81 Git objects and measuring own serialized byte examples. It writes only this inbox directory; codec calculations/YAML inventory are not loader/native/SUT execution. No whole suite or GATE has run. All old frozen source/history/maps and Source/w2cplatform console assets remain unchanged.

Accepted LOCAL06 C1/C5/C6/C7/M1/M2 will follow in separate semantic source commits; bulk English and cell-json await the closed semantic baseline. C2/C3/C4 remain proposals until Architect gives exact decisions. A missing form is not replaced by a canned native command or a false function PASS.
