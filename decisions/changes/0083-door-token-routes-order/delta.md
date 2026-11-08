# Delta 0083-door-token-routes-order

change: 0083-door-token-routes-order rev 1 · state review · author spec103

Two unanchored common-contract artifacts; no invented requirement IDs. Exact old/new/UTF8CP/LF and inverse records are in external Source2 map; only issuer ordering, no crypto or format change.

## MODIFIED artifact `Platform/common/contracts/door-token.md`

old-sha256: 8aeee0f3415194a5c98ad6e5418dc9b5ea7d23fb87a811a97c9c51b05e396f5d

new-sha256: fda371b689936f6851450144b72577058e5f564d3532d4bc48a6937a940475c8

On issue, `claims.routes` preserves the order of the selected routes in the manifest's `door.routes`.


## MODIFIED artifact `Platform/common/ru/contracts/door-token.md`

old-sha256: 9fb35fa32355e1224c706f6ad432ae3acaa235dc3b98edaa2c0b54eaa40df740

new-sha256: a9b9121a68eefc17f7b8ee27771f61bd0d37cd033cffac1c6e89fe67ef9b40fb

При выдаче `claims.routes` сохраняет порядок выбранных маршрутов в `door.routes` манифеста.
