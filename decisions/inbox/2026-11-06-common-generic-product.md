# Generic product wording in the root module contract

Separate source-only follow-up from `cac140972cfc4e949e2859adbe4afde10fa3c7ff`, without P/01. The second private export scan treats renamed `CONSOLE-MODULE.md` as a new file and found three inherited private implementation references at lines 9, 270 and 309. Those three references are removed in favour of the existing generic product wording; the matching human mirror follows the same edit.

No asset file, public name, code span other than the private implementation identifier, JS/CSS/HTML contract or runtime value changes. Both documents retain all physical line numbers and all other source bytes. The exact line map and file hashes are in `2026-11-06-common-generic-product-map.tsv` and `2026-11-06-common-generic-product-proof.json`. The root source/mirror comparison passes. No check exception is added.

This is not the full console module language pass. Its translation and UI localization remain with P/06–P/07. LF source handling, 31 canonical cases, the original 351 byte proofs, unit/catalogue inputs and root filenames are unchanged. coord103 repeats the private export scan and owns composition/publication; official ce8 and MiniMax40 are unchanged.
