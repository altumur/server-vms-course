# Change 0133-go-sum-raft-closure

change: 0133-go-sum-raft-closure rev 1 · lessons Platform/common · author spec103 · state review

Publication parent `17beee057930a848eff9c4fbbb36afc8c7be1630`. Task P01.45: an implementation that imports `github.com/hashicorp/raft v1.7.3` did not build with `-mod=readonly` from the pinned `go.mod` and `go.sum`. `go.sum` receives the full checksum closure, confirmed by sum.golang.org, and `go.mod` receives the `// indirect` requirements that module graph pruning requires, at the versions selected by the module graph. No existing requirement or version changes.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/versions/go.mod` | MODIFIED | 1e766c96c6af2864b3cd4d5ca8064b90252b136a | 6b0185980cbc44472a289e224b83c8552e3029ee | 3c3ef9ce63e26c50b61523e0afcfaf65648b3b8bd51b4d79af7463a7b0c93e70 |
| `Platform/common/versions/go.sum` | MODIFIED | 058d49508ef550acbbf7d62250deb0909ef47944 | 32aba23e02b6e9eeb286dff293bd4e9be18adcfb | e07c2c4008f94f4d2437bb07a180ead019cb45b48d1f0a538424975724c22ba8 |
