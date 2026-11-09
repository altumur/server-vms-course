# Change 0133-batch-p05-seams-split

change: 0133-batch-p05-seams-split rev 1 · lessons P/01, P/05 · author spec103 · state review

Authoring parent `3e73f363142ed0aacc1d9a32a0f6ae48c0122e6c`. Task P01.10.5.15, by the Root card `TWO-SECTION-CLASSIFICATION-AND-FAITHFUL-SPLIT-CARD.json` and the namesake clarification `BATCH-NAMESAKE-CLASSIFICATION-CLARIFICATION.json`. Two mixed sections are split in both languages into a public generic part and the existing same-directory judge-only companion `README.cases.md`.

`Platform/01-store/acceptance/1/README.md`, section Batch. The scenario range is removed from the heading (the heading is now `Batch`; the ADR reference that shared the same parenthesis is removed with it, ADR-0094 B9 stays at N1 of P/01.1). The named scenario lines with their step-to-condition, result and ordering associations go byte for byte into the next `### Original passage N` / `### Исходный отрывок N`, as do the original forms of the two changed lines. The public text keeps the reference to N1/N3, the whole-JSON comparison and the `key` of a batch `conflict`; the general definition of the weight of `@big` (the field name plus the value) stays public verbatim; the `console` exemption from the row-count limit, restart and the group, and the admission of the body stay as duties, without scenario numbers. The P/01.1 N1 and N3 norms are not touched.

`Platform/05-resource/forms/README.md`, section ADR-0127 P/05 review witnesses, s38-s62. In the five port bullets the selected values, fixtures and expected-state links go into the judge-only passage; every bullet keeps its port, the actual intervention and observation duty, the ordinary implementation paths and the limits. The per-bullet range identifiers go with the original lines; the range name of the section sentence and the closing witness paragraph stay unchanged. One public value is replaced by the name of the existing constant `MIRROR_RETENTION_EXTRA` from `forms/runtime-constants.tsv`; no constant is added.

No number, field, code, behavior, form, route, requirement ID, `.tsv` or contract is changed. The J passages are byte-exact copies of the lines they replace; the generic wording in the public documents is a reduction of those lines, not a new rule. Open questions and line-level ranges and kinds are in the external `MAP.json` of the session directory; this record is not model input.

Checked: `en_mirror.compare` returned no messages for each of the four README and README.cases pairs, before and after; a script confirmed that every removed or changed line of a README is in its J file byte for byte and that the added J lines come only from the prior README; `git diff --cached --check`. The full `check_spec`, the filter, export, and any native, model or runner run were not executed, and the presence of each generic duty at its owner norm was checked by sample, not line by line.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/acceptance/1/README.cases.md` | MODIFIED | 20133ebd8987e569d7bb3384fa32a484ae818c12 | f56c6d5ef9776c93ddd9822f610c99f30d396cf1 | 02e82ae5ccbe675e0a1fb5ff734a55e4e316e3959307dd80f77fa2faf6819424 |
| `Platform/01-store/acceptance/1/README.md` | MODIFIED | f3446334be89d1b0208bfc43cec80282c392bbe8 | 2814bf255f4dad61ff292c921b1fbafa6e8e3f57 | b7e3364c221063fb61efda93381ff0c7a12aac96cfb66e8dcad36896bfa6a707 |
| `Platform/01-store/ru/acceptance/1/README.cases.md` | MODIFIED | f78a98eebaaf3a52462837925425c2713703fcbc | 252880c751fc72c98357546ad2e64cf041ec6fcf | efa70dfd9112099786bf0c9274850b91c0bb5619c8aca22187df5a22e50466b5 |
| `Platform/01-store/ru/acceptance/1/README.md` | MODIFIED | 0b8c8e6d3bd147033ccb705b9443ac8eaa651453 | 69e11ea45a3bd9ed5cd9d80c46622c9aa48b2647 | aca37ec40baf5b8c4ce0043dfdc5b2870957f193427a6c96e6e594ea12532ad7 |
| `Platform/05-resource/forms/README.cases.md` | MODIFIED | 220ab61df471227f4c0380b88d653769119ecdc3 | c5893a4ef0e092450bafe0cfbb717726a64a6187 | 441347d38de6b02eb205c4aef8a1e10158d882961ca17b530867ea7ed3497d74 |
| `Platform/05-resource/forms/README.md` | MODIFIED | bf7cd9c32173d769c476163b5bab8e9db5abbb1a | b12a42e58a6e5b279542c33848a6a0e999db5c95 | 5057575b9c302f9649526496affe11ca1e4b3f7bcf88602833be950700064c8f |
| `Platform/05-resource/ru/forms/README.cases.md` | MODIFIED | 64860cbe41b6691c8f880104aff473efab70e445 | 4a4a3518bfd0999cce9f4933263e1006228f5925 | fb7f42e97689056f1ce90141acd25d685adf9d2d4fb5438e83cc0ead60dd9330 |
| `Platform/05-resource/ru/forms/README.md` | MODIFIED | e5899400f559b1cdfb72fe4a9ad92a226bfb9169 | 162bd988a3657eb8acb8f2effc2d6688b021c1fb | 5ceb73817d59fc4baadc88201ceee87800a8b5b49c5047143efa7a6dbe43fa06 |

This change record is Source/judge provenance outside model input.
