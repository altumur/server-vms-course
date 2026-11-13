# Acceptance P/09.2 — the relay mode (stand)

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand, the dictionary of directives and doors — [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (the stand of several clusters). The norm of the chapter is [`09.2-agent.norms.md`](../../spec/09.2-agent.norms.md) N5. In total 5 scenarios / 62 steps. There are no inputs.

The division: the outcome of all three scenarios is the door, the package and the relay pass. The neighbours on
the stand: the holder on the relay package and the knock ([P/08.3](../../../08-domain/spec/08.3-domain.norms.md) N3 «the holder on `POST /api/relay/<relay>`»;
P/08.3-07, P/08.3-13), the acceptance and the topology (chapter 8.3), `join` and `domain/reached` of the agent of a member behind a
relay (chapter 9.1: P/09.1-05, P/09.1-21, P/09.1-24), the silence of a member in the view (chapter 8.1).

## Stand

The preparation is as [the stand of chapter 9.1](../1/README.md#stand),
there are four clusters: `hold`, `m1`, `m2`, `relay`. The agent `relay` always opens
the relay door (`RELAY=1`, `{relay_port}`); the doors and the directives — the section «Domain stand» of the common acceptance README
(`@domain <clusters>`, `@start agent <cluster> via relay`, `@stop agent`, `@cut relay`, `@mend relay`, `@clock`).
The topology is empty until the step that writes it.

## scenarios.tsv

The format of the table is the dictionary of the «Stand» and the section «Domain stand» of the common acceptance README; the expectation is a subset of the fields. `$fp2` is the fingerprint
of the stranger whom the holder learned of from a knock that came in a relay package.

## Kit assistance seams

CALL seams provides 10 CALL steps over ordinary implementation paths. The fixture/port contract is [forms/README.md](../../forms/README.md); [stages.tsv](../../forms/stages.tsv) selects them. They assist the kit and do not replace the ordinary process scenarios or their required neighbours.
