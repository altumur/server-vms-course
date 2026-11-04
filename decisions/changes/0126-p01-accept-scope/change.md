# Change 0126-p01-accept-scope — `accept:<chapter>:<scenarios>` runs the named scenarios without the chapter-wide probes (ADR-0126)

change: 0126-p01-accept-scope rev 1 · lesson P/01 (delta_base 725653954) · author «Спецификация» · state review

**Why.** The runner selects the exact scenarios of a gate (`--scenarios TARGET=NAME`, the series `runner/p01-scenario-selection`
002b97c, read by «Спецификация» — CLEAN): the gate `accept:1.1:01-absent` of `launch` runs on the daemon frame with an empty core,
where the chapter-wide probes of the stand (the body limit, the row ceiling, raw HTTP) cannot pass. The text of the common acceptance
README «Instance» said that the runner checks the parameters on every instance; the header of the form did not say what a named gate
runs. Now both say it: the named scenarios — with the isolation per scenario, without the chapter-wide probes; `*` and the green of a
target — the full run.

## Manifest

| Artifact | Operation | Base | Result |
|---|---|---|---|
| `Platform/01-store/forms/stages.tsv` | replace: the header (`accept:` — named scenarios without the chapter-wide probes, `*` — the full run) | 7f321a6514e2c04017ac53a1212a057ddfb6f21f | 19d60a31e397bb7d345d6bbcdc990c50b384c303 |
| `Platform/common/acceptance/README.md`, `Platform/common/ru/acceptance/README.md` | «Instance»: a run of named scenarios (ADR-0114, not on deltas) | — | — |
| `decisions/adr-norms.tsv`, `decisions/changes/registry.tsv` | append the rows of the change | — | — |

## Change map

| Place | Mark |
|---|---|
| the gates of `forms/stages.tsv` | agreed: unchanged |
| acceptance 1.1 README, the probes of Н5 | agreed: the full run keeps them |
| the runner | agreed: the series 002b97c does this |

## History

- rev 1, 2026-11-05 — «Спецификация»; applied in the branch `spec/accept-scope`.
