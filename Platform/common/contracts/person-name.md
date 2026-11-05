# The person name contract: the form of the name and white-space characters

This English text is the source; the Russian translation `ru/contracts/person-name.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5), addendum (13): the form of a person's name is checked by the process `domain`, the gates
of the consoles, the token recipient, the function `may`, and the set of white-space characters is also read by the log mask and the secret mask — a contract,
not copies in chapters; layout audit A-20, the Architect's decision of 2026-10-25). The owner is chapter
[P/08.4](../../08-domain/spec/08.4-domain.norms.md) Н1.1 (`name` of a person row). Participants: the process `domain` (P/08.4 Н1.1–Н1.2:
the editing of people, the login), the checker of a person token — the gates of the cluster console and the domain console ([the domain token
contract](domain-token.md) `person`), the right function ([the right contract](may.md), `subject`), the log mask ([the log mask
contract](log-mask.md) `space`, `mask_in`).

Moved from P/08.4 Н1.1 `name` without a change of behaviour; P/08.4 and the participant contracts refer here.

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The person row `domain/users/<имя>` is the family `users`: the form `Platform/08-domain/data/users.schema.json`, the outcomes
`Platform/08-domain/data/users.outcomes.tsv` ([form](../../08-domain/data/users.schema.json),
[outcomes](../../08-domain/data/users.outcomes.tsv)).

## White space

```yaml
white_space:   white-space characters — the property White_Space of Unicode 15.0.0: U+0009–U+000D, U+0020, U+0085, U+00A0, U+1680,
               U+2000–U+200A, U+2028, U+2029, U+202F, U+205F, U+3000 (the Architect's decision of 2026-10-20 on the assembly questions
               of lesson 8, item 3); one set of the module: the person name, the log mask (`space`), the secret mask (`mask_in`)
```

## Name

```yaml
name:          a person's name — 1–64 characters without white-space ones (white_space above), control ones (U+0000–U+001F, U+007F) and
               : | ( ) " /; not exactly break-glass (the name of an emergency session is break-glass(<who>), the brackets are forbidden anyway);
               not a subject of the name index (chapter P/08.5 Н1.7)
refusal:       what a reader does with a name out of form is the reader's: the process domain — 400 bad name (P/08.4 Н1.1);
               a gate — 401 (the domain token contract person); the function may — the input is out of form, code 2 (the right contract)
```

## Vectors

There is no package of its own; a participant is the package [`may`](../vectors/may/README.md) — the package of the common contract may, executed by common; this contract is
a participant there (`subject` by this form; CM-RECORD-VECTORS-128, the Architect's decision of 2026-10-25), and the acceptance of
[chapter 8.4](../../08-domain/acceptance/4/README.md) (sc. 01, the white-space boundary U+0085 and U+FEFF).

## Correspondence to former lessons

From P/08.4 Н1.1 `name` (the norm P/08.4 — by `note` of [id-map](../id-map.tsv)); P/08.4, the domain token contract `person`, the right
contract `subject`, the log mask contract `space` and `mask_in` refer here (layout audit A-20).
