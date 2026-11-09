# Runner target and stand contract table

`runner-targets.tsv` documents the existing target-to-command contract. It has
224 registered Platform-owned targets, including 14 in the existing P01 target
selection. Every target is `REGISTERED_UNPLANNED`; registration alone does not
supply a profile, applicable execution, qualified provider or PASS. P07 is a
library dependency, not an invented runtime target.

The Reader coordinate is `c9e9c66b8401230b051f6d9a68c939e38a85b997`.
Published normative Source is `246d1536ff09d14a3941b437c462686de71f6bd9`;
unchanged anchors retain their explicit
`244355d161139bd6fe65fd68c7e5134598c21ba3` coordinate. Source identity is not a
profile export-Git identity. These documents select no export or profile pin.

## Reading the table

The header is the first physical LF line. Each following line describes one
registered target. Cells are TAB-separated; the four scalar columns are
`target_id`, `owner`, `driver`, and `registration_status`. Other cells are compact
JSON documentation values. This table defines no new native frame, decoder,
profile field or source-cell transport.

Required `stand_commands` retain their command owner. `stand_addresses` remain
separate: `token-door` is an address, not a shell command. `vectors`, `adapters`,
`keys`, and `artifact_modules` identify different dependency categories; a native
vector or inproc target can lawfully require no stand command.

`requires_any` retains the existing alternative order. Conditional requirements
state actual code-defined activation boundaries without a case inventory.
Conditional dependency sets describe an existing replacement branch rather than
requiring every full-target dependency in that branch. An optional declaration
or an unavailable required binding does not establish successful coverage.

Normative anchors give full pin, repository-relative path, carrier SHA256,
physical LF range and heading. Role labels describe reviewed normative
references, not permission to introduce a new interface. README paragraphs
under acceptance or vectors can define normative command contracts; the directory
name alone does not establish that role. Reader code anchors identify the actual
consumer or dispatcher. No implementation executable spelling is prescribed.

The table contains no test input inventory, case-content hashes, expected
results or private sequence selectors. Normative input forms and required
command responsibilities remain with their Source owners.

## Canonical owners

Public `Platform/common/acceptance/PROFILE.md` owns the profile, command
ownership, substitutions, adapters, vector wire and artifact contract. The
canonical shared `Platform/common/acceptance/README.md` owns the published seam
and D7 protocol. This explainer does not duplicate or replace those norms.
Publishing those protocols does not implement the missing Reader c9 generic
seam receiver or qualify a provider. Companion provenance, compatibility and
handoff records are not additional normative target contracts.
