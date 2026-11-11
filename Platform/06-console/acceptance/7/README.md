# Acceptance P/06.7 — the cluster console in a domain (stand)

This English text is the source; the Russian translation `ru/acceptance/7/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (a stand of several clusters). The norm of the chapter is
[`06.7-console.norms.md`](../../spec/06.7-console.norms.md) N5. In total 10 scenarios / 106 steps.

The function `resolve` without a stand is checked by the vector [`resolve`](../../vectors/resolve/README.md); `families` of the door `/domain/keys` (N1.11) — by the vector [`key-families`](../../vectors/key-families/README.md) (on the stand there is one manifest with `domain.keys`).

## Stand

**Selected scenarios.** The preparation is as in the acceptance of [chapter 8.3](../../../08-domain/acceptance/3/README.md)
(«Stand», «Preparation of each scenario»): the clusters `hold`, `m1`, `m2`, the catalogue `testsub`. The doors `holder`,
`holder@<cluster>`, `member <cluster> console`, `signer` and the directives `@domain`, `@person`, `@env`, `@start domain on`,
`@stop domain`, `@move` — the section «Domain stand» of the common acceptance README; the forwarding environment is there too (`CLUSTERS` of the consoles,
`DOMAIN_CONSOLE_URL` of the process `domain`, `SIGNER_URL` only at `hold`). The runner goes as the person `root` (chapter 8.4).

- `member hold console` is the console of the holder's cluster: `GET /domain` at it is also a forwarding (into the domain console of its own
  box by `view.url`).

**The other selected scenarios.** The preparation is as in the acceptance of [chapter 8.5](../../../08-domain/acceptance/5/README.md)
(«Preparation»): the catalogue of each cluster is `testsub` and `testsub2`; on each cluster the controllers of both work, the worker
`w-1` of the manifest `testsub`, the worker `t-1` of the manifest `testsub2` (with the training writer of contributions — [chapter 8.5](../../../08-domain/spec/08.5-domain.norms.md) N5) and
the resource of its own server `srv-<cluster>`; before the steps the store of each cluster has the counter `testsub` `c1-<cluster>` and the shelf
`testsub2` `sh1` `{zone: z1, server: srv-<cluster>}`. `console2` at `member` is the prefix `/testsub2`.

- The person `root` with the password `w2c test root password` is created at `@install domain` (`domain first-admin`, the directive
  `@admin`). The runner goes as this person by default: `admin` `*` at the domain door and in the grants row of each cluster of the stand.

An equal answer time to an unknown and to a wrong one, the journal and the limit band by the peer address (not by a header) — by reading.

`answer too large`, `answer broke off`, the recognition of `X-Operator: console` by the role and the journal `domain.forwarded` the stand does not
cause: they are checked by reading (N5 of the chapter). How the runner passes the environment and restarts the console and the agent of a cluster with
a variable (`@env`) — «Implementation decides» item 2 of the chapter.

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and the section «Domain stand»; the expectation is a subset of fields. In total 10
scenarios / 106 steps.
