# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/rights-evaluator/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

- an exact pattern (`acc/exact`), a prefix (`acc/pre/*`: `*` only as the last character);
- literal characters: `*` not last (`acc/a*b` — only the key `acc/a*b`, not `acc/axb`), `!` not first (`acc/p/!x`);
- a final wildcard after a literal star: the role `star-prefix` has `a**` for each action; `a*`, `a*x` and `a**` are allowed, while `a` and `ax` are denied (P/01.2-R008);
- `!` — the negation of the empty key, takes nothing away; `!*` — the negation of everything (the role `none`);
- a negation wins regardless of its place in the list: `!acc/pre/secret/*` first, before the wider `acc/pre/*`, takes away
  `acc/pre/secret/k1`, while `acc/pre/secret` (without `/` — not under the prefix of the negation) stays allowed (coverage audit P/01,
  second pass, G07);
