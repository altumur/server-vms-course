# Acceptance P/08.7 — issuing tokens (stand)

This English text is the source; the Russian translation `ru/acceptance/7/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (a stand of several clusters). The norm of the chapter is
[`08.7-domain.norms.md`](../../spec/08.7-domain.norms.md) N5. The input deadline of 10 s — by reading (there is no slow-client directive). In total 7 scenarios / 55 steps.

Issuing in all scopes and refusal words without a stand is checked by the vector [`issue`](../../vectors/issue/README.md) (cases and their provenance: the canonical package README). The refusals of a kind declaration are the cases `m57_tokens_*` of the corpus of
[P/02.1](../../../02-installer/acceptance/1/README.md); the check of a token at the receiver on vectors is
[the domain token contract](../../../common/contracts/domain-token.md), the package `domain-token`.

The division: selected scenarios are chapter 8.7, their outcome is the holder's issuing and the token claims. The local
door of the agent ([the local token door contract](../../../common/contracts/local-token-door.md), [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md) N1.6) and the receiver
(`@verify`, [P/03.7](../../../03-worker/spec/03.7-worker.norms.md) N1.5) are neighbours on the stand.

## Preparation

As the stand preparation of chapter 8.3 ([the acceptance of chapter 8.3](../3/README.md)) with one
difference: the catalog of each cluster is `testsub` and `testsub2`, like the stand of chapter 8.5 (the order is the «Stand» of the common acceptance
README); on each cluster the controller of `testsub2` works too (without its snapshot shard the agent does not report — [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md)
N1.2 `ready`), the worker of `testsub2` is not needed. The kind `tally` of the manifest `testsub` is the scope `placement`,
`caller: origin`, `target_fields: [cluster, copies]`. The role `testsub2worker` of the stand is a real identity (a role socket or a kit), and
the `grant` of the kind `tally` does not name it. The door `token <cluster> <role>` and
the directive `@verify` are the dictionary of the domain: `@verify` checks a token with the function `token`
([the domain token contract](../../../common/contracts/domain-token.md) «The check») by the rows `domain/keys` and `domain/revoked`
of the named cluster and with its name in `expect`.

## scenarios.tsv

The format is the dictionary of the «Stand» and the dictionary of the domain; an expectation is a subset of fields. `$tok` is the token from the answer of the local door.

## Kit seams

3 CALL seams  execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.
