# C2: complete packet bytes, proposal only

The store command is POST /v1/write, not a fictional /batch route. For deletion of one unit U the target entity is the complete UTF-8 JSON command:

```json
{"op":"batch","writes":[{"op":"put","key":"testsub/units/u","items":{"id":"u","revision":"2","born":"b","deleted":"1","note":"..."},"cas":"1"},{"op":"put","key":"platform/folders/00000000000000000000000000000000","items":{"name":"F","parent":"","members":"remaining refs"},"cas":"1"},{"op":"delete","key":"platform/memberof/testsub/units/u","cas":"1"},{"op":"put","key":"platform/memberof-gone/testsub/units/u","items":{},"cas":""}],"guards":[{"key":"testsub/idem/attempt","index":"1"},{"key":"platform/memberof/parent/units/p","index":"1"}],"id":"example"}
```

There are up to8 folder puts, complete prepared unit/tombstone fields, actual full keys, actual CAS strings, membership removal, memberof-gone when required for a member, and all rights/claim guards. Deletion does not add ancestor-chain guards that P06.8 forbids; rights guards already required by the gate are counted. A key may not occur in both writes and guards: its writes CAS already conditions that key. Count top-level op/id/deadlines if emitted and every separator, key, quote, escape and value. Internal console batches do not gain an arbitrary row-count exemption from the entity-body limit.

The pending claim is a guard in the current target packet, not an overlapping put+guard of the same key. The subsequent saved-answer write has its own complete command, e.g. `{op:put,key:<idem>,items:<actual implementation done row>,cas:<my claim version>}`. Count its actual encoded body too. If a separately authorized procedure includes a claim row in a combined packet, count that put and its CAS; do not invent it as a new public claim schema or change the ownership protocol merely to reduce the budget. One packet's limit does not apply to the sum of independent HTTP requests: every actually emitted request must fit.

## Exact size function

For the encoder I and its actual prepared command P:

`L_I(P) = len(UTF8(JSON_I(P))) + len(actual trailing entity whitespace)`.

This is byte length of the actual entity, not item weight, UTF-16/code-point count, a parse/reserialize estimate or the size of only folder members. The wire-profile used by the attached examples is compact comma/colon JSON, UTF-8 directly (`ensure_ascii=false`), no BOM, no optional trailing LF. JSON string quotes/backslashes/control bytes are escaped as required. Other encoders remain possible, but must size the exact bytes they send; an ASCII-escape or pretty encoder cannot use this profile's smaller number. An emitted final LF is a body byte and must be added. A missing LF is not implicitly added by the formula.

HTTP request line/header CRLF, Content-Length header bytes, chunk-size lines, delimiters and final zero chunk are HTTP framing, not decoded entity bytes. Content-Length must equal the whole entity, including its optional LF. For chunked transfer the body limit is the sum of decoded chunk data, including entity whitespace; framing does not create spare capacity. The examples record Content-Length wire length and chunked data+delimiter length separately from entity length.

Proposed requirement replaces the incorrect8*64KiB item-weight argument: every admitted folder-enabled state must keep **all** required deletion packets within the configured store body limit B, inclusively. `max(L_I(P_target), L_I(P_done), ...) <= B`. No new DELETE refusal is presented as satisfying the promise.

The deployment/admission decision still needs Architect approval. The following is a concrete sufficient profile option, not an active threshold:

1. Declare finite full-key, CAS/index/id/deadline lengths, row ceiling V, folder weight F, number of unit deletions n (including the console/batch case), put/guard multiplicities and the exact compact encoder above. Use the actual declared key grammar/metadata bounds; do not guess a1024-byte row key is a200-byte user id. Unbounded fields mean no finite profile proof.
2. For an items map of UTF-8 weight W with m fields, the compact JSON encoding is at most `6W + 6m + 1` bytes; every nonempty distinct key contributes at least one byte, so `m <= W+1` and `12W+7` is a conservative universal bound. The empty map is2 bytes. A folder's fixed three fields give the tighter `6F+19` bound. This includes worst JSON escaping; ordinary Unicode often costs less, which is not grounds to remove the bound.
3. Build the maximal permitted packet skeleton S with the full bounded metadata, keys, writes/guards and each put items replaced by `{}`. Let `H = len(encode(S)) - 2*N_put`. A sufficient entity limit is `H + (n_unit+n_claim)*(12V+7) + n_folder*(6F+19) + n_empty*2 + emitted_LF`, using the actual bounded multiplicities of that procedure; `n_folder <= 8*n_unit`. Compute separate target/done maxima and require B at least their maximum. This may require a substantially larger store body profile than default1MiB; that cost is explicit, not hidden by the old512KiB argument.
4. An alternative preserving a smaller B is an admission invariant over every mutation that can increase an affected deletion packet, including unit edits, folder edits/membership and agent-delivered copies. Its complete writer/read/guard scope must be approved separately: checking only a new POST or only a folder's current row would not preserve it. No new reads/roles/P09 behavior or launch refusal are adopted here. Recommend approving the sufficient finite store profile first unless the owner explicitly chooses that wider invariant.

## Measured examples, no store execution

`prepare.py` reconstructs an actual escaping example:450000 quote characters in a unit, eight folders with999 remaining59-byte refs each, membership/gone and two guards. Entity length is1380972 bytes, above1048576, while each put item weight is within1MiB. This is our explicitly described packet, not a claim to reproduce the reviewer's differently named1380980-byte packet exactly.

It also constructs complete commands of1048575/1048576/1048577 bytes by ordinary ASCII padding of a unit field while retaining8folder puts, membership/gone, claim/right guards and id. Every prepared item map fits1MiB; the corresponding client PUT is below1MiB. Exactly-limit fits, one extra byte does not. The exact-limit JSON with a trailing LF becomes1048577; ASCII escaping of the same Unicode value also increases actual body bytes. Hashes, item weights, full keys and framing lengths are in c2-byte-witnesses.json. No algorithm, refusal class, body default, SDK/native or active batch-bounds form is changed by these codec witnesses.
