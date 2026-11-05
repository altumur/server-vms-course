# P/08 forms and process seams

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export (ADR-0121). Forms express the existing norms under ADR-0125 addendum (5).

## Inputs and constants

[daemon-flags.tsv](daemon-flags.tsv) declares 20 environment inputs and the existing first-admin positional name with the common header. `$NAME` stays environment; commands=domain is the process role. The complete launcher, aliases, catalogue, instance, ring, TLS and address contracts still apply. Operation-time unknown inputs keep their own outcomes. A missing signer row makes the process wait; this form does not turn waiting into a start failure. The logical first-admin invocation denotes the implementation-chosen operator command, with its required person name; it fixes no executable spelling. Its password still comes from stdin under P/08.4 Н1.9 (whole UTF-8, remove at most one final LF/CRLF), never from a new flag or environment value.

[runtime-constants.tsv](runtime-constants.tsv) declares 26 positive integer literals, with the common header `name value unit norm meaning`. Units are count, s and bytes. Count means Unicode code points where the meaning says characters. KiB/MiB are converted to exact bytes. Conditional camera formulas, the agent report period and dependent bounds stay in their owning sections; MARK_REFRESH = LOST_AFTER/2 remains a derived fractional duration, without rounding. These constants are not environment settings.

## Refusal catalogue

[refusals.tsv](refusals.tsv) preserves all 154 original Н4 rows, plus two explicit first-admin operator failures from Н1.9, as 178 projections. Four-cell source rows retain cause/outcome/diagnostic/caller exactly; the third cell of 8.1 was Body. Three-cell tables in 8.4, 8.7, 8.8 and 8.9 retain word/outcome/cause, with diagnostic/caller `-`. Word is the original normative cell: its indexed tokens are not an arbitrary choice of error or reason. A projection applies under the original condition and operation.

HTTP schemas name existing lesson components. Fields list directly declared required properties; inherited/composed and conditional requirements remain the full OpenAPI and original source cells. Native form refusals and operator exits keep their original exit rules. A per-member relay refusal or a later kept-edit outcome is not a new HTTP error. The older-road success has the direct Carry and relay RelayAnswer envelopes selected by the actual operation. Dynamic Retry-After and conditional detail/reason/field remain their complete owning norms, not invented fixed header values. The existing closed error vocabulary remains data/refusal-words.tsv.

## Versioned doors

[versioned-doors.tsv](versioned-doors.tsv) is the source of the former P/08.0 Н1.9 table: 19 operation projections of its 16 rows. Its closed header is `method path row revision etag if_match absent_revision norm`, literal TAB. A pair method/path is unique and is an existing operation of the lesson OpenAPI. Every OpenAPI operation declaring ETag or If-Match has a row. The batch row is retained even though it declares neither header. Norm is a comma-separated nonempty list of existing req anchors of this lesson.

Row has three kinds. A literal or template selects the existing version row by its family; a `<name>` placeholder is a capture of this operation's OpenAPI path. The sole exception `<part>` is the member-list shard computed by the ordinary core, not a new door parameter. `-` means no pre-existing version row at creation. `writes[]` means each individual row of a batch, never a store key. Revision is closed to doc.rev, revision or rev: the logical version field of the norm's decoded family, not an arbitrary expression language. Row resolution, missing/unreadable fields and all reference guards remain the ordinary family/core procedure.

Etag is true or false. True means the success ETag is the result index in double quotes, never the revision counter. The actual write/repeat procedure supplies this index; creation with row=- still gives the success header. False means there is no ETag header. DELETE of a member keeps the ETag of its changed member-list row; DELETE of a person/group/role/placement and POST batch do not. The table, not a generic rule by method, selects presence.

If_match is optional, ignored or base-rev. Optional validates and judges the optional header by P/08.0-R006. Ignored does not read it at the creation POSTs or POST batch. Base-rev gives If-Match priority and uses base_rev only without that header; if both are present and incompatible, the existing refusal applies (400 refused, field /base_rev); an index next to base_rev is incompatible as in the norm. These rows must include P/08.0-R006 in norm. The ordinary identity, repeat-memory, row-existence and condition order stays P/08.0-R006/R007, including a replay that does not judge the former condition anew.

Absent_revision is the closed value 0 or `-`. Zero supplies revision 0 only for a confirmed absent selected row, including the first topology/shared write and the other creating/version-counter paths declared by their rows. `-` supplies no absent-row counter: the operation's own creation or missing-row rule applies. A transport error or an unconfirmed read never becomes revision 0. For writes[] this policy is per write. Row=- and writes[] are distinct even when If-Match is ignored.

The metadata belongs to core; there is no new KIT_PARTS value. The old four English source cells were checked once, without loss, during the move; they are not a second normative source column.
