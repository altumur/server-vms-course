# Acceptance P/08.4 — people and grants (stand)

This English text is the source; the Russian translation `ru/acceptance/4/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (a stand of several clusters). The norm of the chapter is
[`08.4-domain.norms.md`](../../spec/08.4-domain.norms.md) N5. In total 33 scenarios / 498 steps.

The function `may` without a stand is the vectors `may`.

## Stand

The preparation is as the acceptance of [chapter 8.5](../5/README.md): the catalogue `testsub` and `testsub2`, the counter
`c1-<cluster>` and the shelf `sh1` on each cluster, the training writer of contributions. The doors `holder`, `member`, `signer` and the directives
`@domain`, `@person`, `@stop agent` — the section «Domain stand» of the common acceptance README.

- The person `root` with the password `w2c test root password` is created at `@install domain` (`domain first-admin`, the directive
  `@admin`): an assignment of the role `admin`, there is no direct row in `domain/grants/domain`. The runner goes as them by default:
  step 4a at the domain door and `admin` `*` in the grants row of each cluster of the stand.
- `@person -` is without a token; `root` is returned by the directive `@person root …`.
- `$ta` is the token of `ann` from the login answer; the steps with `@header Authorization: Bearer $ta` go on her behalf, the others — on behalf of
  the current person.

An equal answer time to an unknown and a wrong one, the log and the limit band by the address of the client from the domain console (not by its
TCP peer) — by reading (the norms N5).

The steps at the cluster console (`member … console`: `/session` with grants, reading and writing a unit under a token) and `holder GET /domain/grants` (a door of the domain console) are neighbours on the stand: their norms are the cluster console (a late layer of lesson P/06) and lesson P/10; the outcome of the scenarios is the rows of people and grants of the process `domain`.

## scenarios.tsv

The format is the dictionary of the «Stand» and the section «Domain stand» of the common acceptance README; the expectation is a subset of fields.

## Kit seams

CALL seams  execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.
