# Generator vectors V/12.2

This English text is the source; the Russian translation `ru/vectors/generate/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The input is the plugin directory (`plugin.json`, `langs/*.json`) and the list of installed ones; the output is the subsystem manifest and the `calls` fragment
(V/12.2 N1.2) or a refusal line (N1.3). The manifest is compared after loading by the strict loader P/02.1, not as text.

Cases:

- `security_controller` and `camera` of psim-sdk `c3d9ebb` as they are, the installation order `camera` → `security_controller` and the reverse one
  (the owner `CAM`, V/12.2 N1.2 item 3);
- synthetic manifests for every row of N4 of chapters V/12.1 and V/12.2, for `readonly`, `hidden`, `secret`, arrays, `enum_values`
  on numbers and translations: the psim samples do not have these words.

**Status:** the vectors are written after the loader key `display.tables` (ADR-0115 addendum (11), the share of Specification): without it
the strict loader will not accept the subsystem manifest.
