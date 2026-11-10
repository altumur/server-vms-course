# Change 0133-p01-store-directory-by-stand

change: 0133-p01-store-directory-by-stand rev 1 · lessons Platform/common · author spec103 · state review

Publication parent `caf0244dd7a03dd85d3a3099a9cbea7c4315dcac`. The decision of the Architect on finding C1 of P01.89.4: the stand creates the empty store directory `{data}/configstore` with mode 0700 before the first start in all three stands, as the installer of P/02.4 does; the daemon does not create an absent `-dir`. No requirement unit changes; no numeric value.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/README.md` | MODIFIED | f5d7abb550997952db57b272a1c923d80e3373f0 | f0ad500fb8af4ee0b488223b61ffeb2baf61f02b | 017e54f32e5746b111b922b809e521df6e6e4e2a3b39161d4e4a912f1bd9ea58 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | 7b43a4771691ee8a065065393331776e138c56d6 | e88bd5fc0a4cf9f3212e51df14d1f6059e09944e | 7eaa5cfbe8a51807d100a73ffe85b9e07f36eba06cee1c1291931ac2e7efca3a |
