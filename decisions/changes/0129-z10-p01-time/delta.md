# Delta 0129-z10-p01-time — current Time reader

change: 0129-z10-p01-time rev 1; lesson P/01, delta_base 725653954; base 854681a2fcd1db12ff7db8127feee977f62be6b6. State review only.

Authority: ADR-0129 (23), SOURCE-B 8f21b9c9415f489a255df1de6ce5273368366c484eba3818177ea2b4ba26dcf6 and mirror-only supplement d267c9507b34699f0853fb81951219cbedd7baf1430b8fb39bdebfda5dc03813.

ADR-0122 units end at the next req anchor or a same/older heading. Normalize LF and strip trailing spaces; the complete replacement starts at the req anchor. A FORMAT/floor bundle is immutable and separate.

## ADDED

(none)

## MODIFIED

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R008

old-sha256: 4bc26543258acf73d2d1e1dffa4d66503388ebabf4ff76ddc7b68f1adee0cbcd

new-sha256: 3b07ccb8c6dd55235fa1a2b8fcc2f47eb3f89b38585f228a792f58213677fe1a

<!-- req: P/01.1-R008 -->
- The **reader** MUST accept the same form with at most three fractional digits as the current writer: `^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$`. Excess precision has the existing field/row unreadable outcome of that field, without rounding or truncation.



### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R010

old-sha256: 2e82860d82d97e2a8bd20dfcf3c91f2ae1356b3461524372453bfad283ffe5a7

new-sha256: 94350e2ff46de09389877a5bca8d61928464a2547c0845036276a0091c1b741c

<!-- req: P/01.1-R010 -->
- A notation outside this form is a field out of form; the field rule determines the reader outcome. Its value is finite in binary64: overflow is also out of form. The reader has the writer's fraction bound. The R007 exception and own forms of R012 are not narrowed by this rule.



## REMOVED

(none)
