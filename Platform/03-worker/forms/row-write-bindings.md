# State row-write bindings

This English text is the source; ru/forms/row-write-bindings.md is its Russian translation for people, not in the export. [row-write-bindings.tsv](row-write-bindings.tsv) is the normative constructor table for P/03.6-R018, P/03.6-R128, P/03.6-R192.

## Grammar

The literal-TAB header is write,key,field,source,value,guard_key,guard_version,norm. One row binds one direct items property. write is [a-z][a-z0-9-]* and groups a constructor; (write,field) is unique. key/guard_key/guard_version must be identical in all rows of one write. field is an RFC 6901 JSON Pointer to one direct property of the row's schema. The key template selects exactly one existing catalogue family; every required property is covered, and foreign properties are forbidden. Property codecs come from that schema and codec.tsv: the constructor does not invent codecs or convert a version to binary64.

source is start | input | const. With start/input, value is a nonempty JSON Pointer beginning with / into the immutable start snapshot or this invocation's input. With const, value is one strict JSON value; for example "" is an empty JSON string. There are no expressions, conversions, fallback or re-reads. A missing pointer is an invocation error, never an implicit zero or null.

#start /pointer type and #input /pointer type declare file-wide source paths. Types are string | boolean | integer | number | object | array | dyn. These are JSON values before the items codec; integer is exact. A file has one immutable start snapshot contract; input cannot replace it. The family schema and the snapshot contract retain their field restrictions.

key and guard_key consist of literal segments and {start:/pointer} / {input:/pointer}. A placeholder occupies a whole segment and must reference a declared string. At invocation its value must be nonempty and a single segment; it is not URL-encoded. An unknown reference, missing value, wrong type or slash in a substituted segment is an error before IO. These are neither CEL nor shell templates. guard_key can instead be -.

guard_version is start:/pointer or input:/pointer to a declared exact P/01 string version, or -. No guard means both guard_key and guard_version are -; otherwise both are set. The version is copied exactly, without arithmetic or reading a current version. norm is a comma-separated list of existing req anchors of the lesson.

## The state constructor

[The four rows](row-write-bindings.tsv) choose family `<sub>/state/<name>/<unit>`. start carries the accepted unit start: sub/unit, its born (the current 32 lowercase hex life, required at the accepted start), revision, holder epoch and the exact index of the epoch row confirmed when taking it. input carries one declared state name and its value. born/revision/epoch and both guard references must come from start. value alone comes from input and is encoded as JCS by the state-family codec, after validation against `unit.state.<name>`. The name and unit also retain their manifest/key grammar.

The result is key/items/guard. Reading the former state row, its CAS version, may_write, CAS/retry, guard refusal, synchronization and confirmation remain the ordinary IO rules P/03.6-R193 and P/03.6-R194. The constructor performs none of them and reads no store. Capturing epoch_index from a newer read would break the binding even if its string is valid.

The independent seam s5-state-start-born changes the unit row after start: the result must retain the start born/revision/epoch and epoch_index while taking the new input.value. A guard version outside binary64 is copied exactly. Required negative checks include start replaced by a re-read, epoch_index replaced by a current version, a foreign key/property and a missing required property. A subsystem-value error remains an error without a write.
