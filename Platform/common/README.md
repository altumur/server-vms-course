# Common to all micromodules

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The layout of the catalogue (ADR-0124: the English source on the canonical path, the Russian text for people in `ru/`; common has no lecture):

```text
README.md                  this file
data/catalog.tsv           the data catalogue: rows, objects, files — the owner, the participants, the readers (ADR-0083)
data/README.md             the key by the template of the catalogue: the table of placeholders — grammar, number of components, example
data/codec.tsv             the codec of the store rows (ADR-0088)
data/common.schema.json    the common definitions of the family schemas, for reference, not a norm; its layers — data/common.layers.tsv
contracts/                 common contracts of several processes: sealing (the ring, enc:v2, AAD), the role certificate,
                           the event journal, the presence lock, observation (resource_state, LOST_AFTER), the label alphabet;
                           a request and its mark, the door token, the domain token (review analysis of stage B 3–5, V1);
                           the local token door of the agent (review analysis of stage A 8–10, decision 1); the domain envelopes
                           x25519:v1 and m1 (№ 12); the agent signature, the domain key set, the domain backup key (I02-BACKUP-HMAC), the domain founding (I02-FOUND), the placement of secret files (S-005, DF-G01), the term record, the signature
                           of a request, the report admission (№ 13); the gate and the pass door.pass (№ 14); forwarding (№ 23); the right
                           by grants may, the client peer (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) items 1, 2); the row check
                           and the url address — login and password (W03-E07); the group by host group-of (W03-GROUP-01); the environment file
                           env-file (C04-ENV-01); the password hash password-hash (GP-G06)
LAYERS.md                  the layers of V7: the standard JSON Schema 2020-12 and CEL, our own remainder (ADR-0092)
versions/                  the pinned versions of the standard libraries and the YAML parsers: README, go.mod, go.sum, requirements.txt
vectors/README.md          the index of all vectors by owner lessons (the vectors themselves are in the directory of the owner)
vectors/sealing/           the vectors of the sealing contract (common, without an owner lesson)
vectors/domain-envelopes/  the vectors of the domain envelopes contract (former inputs of the acceptance of M11/2, M11/3)
vectors/domain-token/      the vectors of the domain token contract (former inputs of the acceptance of M11/2 token-*)
vectors/{keys,agent-sig,accept,record,ask-sig,may,peer}/  the vectors of the common domain contracts: the key set, the agent signature,
                           the report admission, the term record, the request signature, the right may, the client peer (former inputs of the acceptance of M11;
                           review analysis of stage B 8–10, № 22)
contracts/gate-and-pass.api.openapi.yaml  the common body forms of the gate-and-pass contract (Denied; referenced by P/06, P/08, P/10)
acceptance/README.md       the common acceptance stand: the dictionary of directives and doors, the domain stand
acceptance/PROFILE.md      the complete generic acceptance profile v2 and assembly v1, substitutions, adapters and vector wire
acceptance/system/         end-to-end scenarios of several micromodules
acceptance/pass/           the pass of the second kind with the stand-in worker of the runner
acceptance/ops/            the stand of group operations door.pass.operations (ADR-0095)
acceptance/tls/            the TLS stand and the fourth cluster — acceptance data of lessons 8–10
ru/                        for people, not in the export — translations of the English text by the same path
```

The dictionary of normative words is the canon of the whole course; it lies outside the module (a course file).

[Production obligations](contracts/production-obligations.md): finite budgets and public sequences for ADR-0130 Addendum (10).


[Shared code modules](modules.md): contracts, acceptance inputs, consumers and pin locations.
## Implementation code

Write implementation code without explanatory comments. A short requirement marker is optional and may appear only where that rule is implemented; use the exact ID of an existing requirement anchor. Do not invent marker IDs or a separate numbering scheme. Acceptance checks and judges do not require comments.
