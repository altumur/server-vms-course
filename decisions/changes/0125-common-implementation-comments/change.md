# Change 0125-common-implementation-comments

change: 0125-common-implementation-comments rev 1 · lesson Platform/common · author spec103 · state review

Parent `80709fde3e3b657f987b38a3bcf05c7e183357a3`. Authority: ADR-0125 Addendum (10), `da596c154`. Add the common implementation instruction once in the existing EN/RU common README entrypoint. Implementation code has no explanatory comments. An optional short marker names the exact existing requirement anchor only at the implementation site. No marker ID, alternate numbering scheme, required comment or new judge obligation is introduced.

| Source | Before blob | After blob | After SHA256 |
|---|---|---|---|
| `Platform/common/README.md` | 59434575e83f351368a8655462481e96cf92b952 | 9322b4145c693758df6c2ffb8683a806ebef644a | b20d705504648c3a77da205bf2c211971deadff7b5ee9b26ed57a0f0cb9efcb2 |
| `Platform/common/ru/README.md` | 771f30edec2a70b75ace22ade7b98886368503f1 | a8ba98832a9df2c5b975ba550ce498c1ce5d8c40 | 0ca5257b1af9df017dbf2f142a47ae60d656b5c9b2addcb912c5e015f68f02d6 |

Both replacements append only the instruction paragraph and its heading; existing README bytes and links stay exact. No per-lesson edits, generated output, old package, pilot, implementation, profile or pin changes.

Checks: the changed EN/RU pair has zero mirror messages; exact append/inverse and protected prefix checks pass. No new links or example marker IDs need resolution. Source requirement IDs are unchanged (the README is an unanchored entrypoint); this artifact manifest records two file changes without fictitious requirement units. No accepted/applied/readiness, runtime or global GATE claim.
