# P06 C2: resolved provenance, explicit codec/LF and real byte skeletons

Normal data follow-up to1a7 after the Architect's three findings; history is retained. The approved finite-profile schema SHA ddeb is unchanged. All13 profiles, per-case status, expected answers, counts/H, expected_bounds and maximum609947876 remain identical. Only the independent proof context and its raw metadata inputs are completed. This remains a synthetic descriptor universe, not production completeness or installer/SUT execution.

- `owned-context:metadata-proofs` now resolves to the actual independent `owned_context["metadata-proofs"]` array, one unique packet proof per descriptor.
- `owned_context.metadata` independently declares the compact-json-utf8 encoder and trailing_lf1, as well as the existing finite metadata ceilings. These are compared against each profile, not derived from expect.
- Eight actual `forms/finite-profile-skeletons/<packet>.json` byte files are pinned by path/SHA256/length in that proof array and in each descriptor. Total6089646 bytes. They contain compact UTF-8 metadata JSON with an empty map in every put items slot, two dummy zero deadlines, the full64-hex id and20-digit versions, no BOM or final LF. The final entity LF is a separate1 in the profile/context.

Each full metadata key has1024 UTF-8 bytes and6146 JSON bytes. Three control-character prefix positions identify every slot uniquely, followed by1021 NUL bytes. The alphabet excludes short-escaped control characters8/9/10/12/13, so every code point costs six JSON bytes. All write and guard keys are distinct. This realizes the existing conservative full-key bound without duplicate-key requests. Folder/family-specific shorter keys can only reduce that upper bound. These files model metadata, not real store target data.

Own byte assembly/readback checked every file's exact UTF-8 bytes, SHA and length, JSON object/array counts, unique key set, empty items, dummy deadlines and descriptor agreement. Reconstruct the same metadata JSON in the preserved object/member order using compact comma/colon UTF-8 JSON and compare the assembled bytes with read_bytes **without strip, line conversion or LF insertion**. Count H from the actual matched bytes:

`H = len(skeleton_bytes) - 2*number_of_puts + 2*(313-1)`.

Only then apply the unchanged sufficient weight bound and the separately fixed entity LF. No expected bound is an assembly input; the per-packet positive/negative expect remains judge-only. The eight recalculated H and whole bound are unchanged. The map pins each new byte file and records the context delta. Long new data files are represented in the map by byte identity, not duplicated as prose diffs.

The earlier9bf judge used numeric skeleton_entity_bytes and did not read these new bytes; its13-case pass cannot be inherited as verification of the new fields. The Architect supplies the narrow provenance/codec/LF/byte-assembly judge follow-up by this exact hash. No shared checker, decoder, marker, formula, schema, old947/220, role, native command, runtime, GATE, export or pin is changed here.
