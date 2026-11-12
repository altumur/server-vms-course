# P/07 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/07-console-module.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

This file is for the agent (or person) who writes or checks the console module from the lesson. The explanation of «why» is
`ru/07-console-module.md` (for people, not in the export).

## Task

The console module is a common module: the published files of [P/06.5 N1.1](../../06-console/spec/06.5-console.norms.md) `module`; they
are served byte for byte, not written. The lesson norms what the module calls (N1.4) and what it gives the shell (N1.5); an implementation
of the console does not write it, the owner of the specification keeps its bytes by the norms, the generator checks the completeness of the contract
by rewriting (P/06.5 N1.1 `module`: a check of the completeness of the contract, not a way to implement). The norms of the lesson are
P/07-01…08.

For a generation line, the completion criterion is packaging of the published bytes unchanged plus scenario 01 (judge-only: checks P/07-R264) of acceptance 6.5 (`?v=1`). The line does not rewrite JavaScript and has no separate executable module profile. The three module tests and readiness items P/07-07 and P/07-08 are an explicit debt of the owner of the published common module bytes, neither PASS nor FAIL of the line.

## Inputs and their priority

The canon is the [norms](07-console-module.norms.md). The doors the module calls are the [contract of lesson
P/06](../../06-console/spec/06-console.api.openapi.yaml); the publication of the module and the version `?v=1` are observed by sc. 01 (judge-only: checks P/07-R264) of [the acceptance of chapter
6.5](../../06-console/acceptance/5/README.md); the lecture (`ru/07-console-module.md`, for people, not in the export) explains the reasons; the description of the surface is
[`CONSOLE-MODULE.md`](../CONSOLE-MODULE.md) (not a norm; where it differs from N1.5, the lesson is right). On a
contradiction, record the place and a counterexample and pass it to the Specification; the instructions introduce no new refusal. The internal types,
functions and structure of the module remain the choice of its owner.

## Glossary

| Term | Meaning here | Requirements |
|---|---|---|
| `module` | The one published PlatformConsole browser library; generation lines package its bytes. | P/07-R057 |
| `shell / page` | The browser page that mounts the library and owns its additions; `pc` is the returned page object. | P/07-R058, P/07-R252 |
| `module call / page call` | A request made by the library itself / a shell request through console.api; the never list constrains the former. | P/07-R031 |
| `catalogue / opts.subsystems` | Root plus mounted profiles / the selection of unit subsystems; the selection does not empty the observation catalogue. | P/07-R034…P/07-R038, P/07-R012 |
| `worker identity` | The exact (sub, worker) from confirmed request context, represented as worker:&lt;sub&gt;/&lt;w&gt;. | P/07-R040 |
| `unknown / empty / last-known` | An unconfirmed observation / a confirmed empty value / previous data; only the second is a fresh empty fact. | P/07-R043, P/07-R170 |
| `logical action / replay` | A new console.api call / another attempt of the same action with the same key and original serialized body. | P/07-R082, P/07-R083 |
| `revision / store index` | api.opts.ifMatch carries an integer row revision; folder writes use the separately declared quoted store-index If-Match. | P/07-R072, P/07-R152 |
| `may` | A UI decision using the session grants and common right contract; the server independently checks every request. | P/07-R110, P/07-R119 |
| `ready / refresh` | The promise after mount and manifest reading / the declared observation event. | P/07-R065, P/07-R167 |
| `pending / outcomes` | A per-member integer count or null / separate outcome arrays; one does not replace the other. | P/07-R194, P/07-R195 |
| `unread / complete` | Reader fields with the meanings of the domain owner; they are not a new client completeness flag. | P/07-R240, P/07-R246 |
| `caption / protocol value` | UI words from localization.tsv or owning manifest display / contract data such as identifiers and timestamps. | P/07-R178, P/07-R188 |
| `holder mode` | The existing sections: [domain] page; its reads differ from the cluster page. | P/07-R229 |
| `byte-owner debt` | An open obligation of the owner of the common module, kept separate from packaging evidence of a generation line. | P/07-R268 |

## What to create

The following behaviour is the responsibility of the owner of the common module bytes; a generation line packages the published files.

- Calls of the module only from the closed list of N1.4, in the order `order`; the doors of the holders — only to the shell through `where()`.
- The contract with the shell, N1.5: `version`, `objects`, `api`, `may`, `events`, `where`, `words`, `adds`, `cards`, `commands`.
- The domain section — the late layer N1.6 (lessons 8, 10; the doors — lesson P/10 and chapter 6.7).

## Order of work

1. Connect the closed may. Tell apart a replay of one request and a new action; allow an automatic replay only by
   the memory of the owner. For an unknown PUT/table — a read first (N1.5). The three states of the session by which `may` judges —
   [chapter 6.3](../../06-console/spec/06.3-console.norms.md) N1.3 `session`.
2. Check the module/shell separately: the jsdom test of the owner of the specification `Source/tests/console` (judge-only: owner test sources; existing examples for P/07-R059…P/07-R060 and P/07-R129 only; N5 records required and open subjects separately) by the subjects of N5.
   An implementation neither reads nor runs the jsdom tests of N5. Existing Source fixtures read the frozen witness unless a test explicitly loads the canonical module; the owner separately verifies the current canonical bytes under P/07-R258. The proof of an implementation is the bytes of the module as they are and the load of `?v=1` (sc. 01 (judge-only: checks P/07-R264) of the acceptance
   of chapter 6.5).
3. The library for the shell turns the absent field `door` of the HTTP answer `Where` into `null` (N1.5 `where`). Check
   this level separately from HTTP: a `Where` without a trustworthy door has no field `door` — the check of the door is in
   [the instructions of P/06](../../06-console/spec/06-console.README.md), chapter 6.5.

## Traps of the language and the library

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| N1.5 | A key cache by method/path/body merges two clicks | A key per logical action; a new call is independent. |

The published module keeps a key per action and replays by itself only the `POST` of units, and `may` without grants gives `true` only
with `open: true` («Implementation decides» item 1 of the norms is closed); the evidence is the jsdom tests by the table of N5.

## Boundary checks

Compare the proposed changes of the module against N1.5/N1.6 and the current canonical module, not a historical witness. Keep the full original URL and CAS/replay behaviour; retain integer input on a local refusal and preserve typed list elements. Before worker changes, obtain the exact public-context disposition; before cursor code, fix the six-projection assembly and incomplete-read plan. Check current pending 0/1/null separately from outcomes; J-P07-01 stays a separate test scope. Disabled sections cannot be entered by mouse or keyboard. Publication checks still compare the same three files byte for byte at the existing routes and version. Existing unrelated debts remain open.

The module calls nothing outside N1.4 `reads`/`writes`; the paths of `never` (`/{sub}/requests`, `/api/backup`, `/resources`, tables outside
`servers.show`, the doors of the holders) do not appear among the requests intercepted by the jsdom test, neither on mounting nor on
polling. The parts of the list that the domain introduces are checked in the mode `domain` of the late layer (N1.6).

## Done when

The owner of the common module records concrete evidence for every id (`P/07-01…08`): a jsdom test by the subjects of N5 or a reading with a reason. P/07-07 and P/07-08 remain this owner's open debt until `module-unplaceable-all` (judge-only: required cases for P/07-R016…P/07-R017, P/07-R305; open debt, no evidence of closure), `module-subsystems-none` (judge-only: required cases for P/07-R015; open debt, no evidence of closure) and `module-writes-via` (judge-only: required cases for P/07-R106…P/07-R109, P/07-R316; open debt, no evidence of closure) pass on the published module. A generation line records the debt explicitly; its completion evidence is the packaging check from Task, not a separate implementation of these JavaScript branches.
The compatibility of the common console module is a separate comparison of bytes (sc. 01 (judge-only: checks P/07-R264) of the acceptance of chapter 6.5) and a reading by the norms N1.4, N1.5.

On a discrepancy — compare the norm, the answer form and the scenario. Record the exact input and outcome; do not carry a difference of an implementation
silently into the canon. The decision is reflected in the norm, the contract, the instructions and the affected acceptance; the origin of the error and
the check of the related class — in the log of the Specification.
