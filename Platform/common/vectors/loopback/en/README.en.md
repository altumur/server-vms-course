# Vectors: the loopback threshold of a client of its own cluster

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the role certificate contract](../../../contracts/role-certificate.md) «The client of a door of its own cluster» `loopback`
(ADR-0075 addendum 2026-10-26 (3) item 1, (4) item 1, (5) item 1). The participants are the clients of the door of their own cluster (`own_client` of the contract):
the agent to its console, the workers script, the cluster console at transition 2 and in the forwarding to the signer, the client of the resource door.
The threshold decides whether to substitute `SERVER_NAME` into the `host` of the function [`peer`](../../peer/README.md) before step 1; the function `peer` itself and
its package do not change from this. The bytes are written by «Спецификация»; the rows are by the text of the contract.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — `{url}`: an absolute URL with a scheme and a host (v6 — in brackets, the zone — `%25<зона>`). **Output** — a JSON string
`"loopback"` (a loopback literal: v4 of four decimal parts 0–255 without leading zeros with the first `127`; v6 with the value `::1`
in any notation without a zone), `"ip"` (another IP literal by step 1 of `peer`, including v6 with a zone, `::ffff:127.0.0.1`,
`0.0.0.0`, `::`) or `"name"` (otherwise: `localhost`, `127.1`, a notation with leading zeros); or `@exit 2` — an input not of the form (not
an object, no `url`, `url` not a string or not a URL with a scheme and a non-empty host). Code 2 is the outcome of the function on an input not of the form;
at a client such a URL is the `bad_url` of the contract: from the environment — a refusal of start, code 2; from a store row — as if there were no field
(the review of the norms of ADR-0075 Kimi 80ee2b775, Н6).

31 rows: a v4 loopback (including the boundary and the scheme `http`), leading zeros, three parts, a part outside 0–255, a hexadecimal
notation — a name; an IP outside the loopback, `0.0.0.0`; v6 `::1` in three notations — a loopback; with a zone, `::ffff:127.0.0.1`, `::`, another v6 — `ip`;
names (`localhost` in two cases, a server name); a dot at the end — a name; `[::0.0.0.1]` (a v4 tail, the value `::1`) — a loopback;
`[::127.0.0.1]` — `ip`; `userinfo@` before the host does not interfere; not a URL, an empty host, an input not an object, without `url`, `url` not a string — `@exit 2`. The notation of the host is taken as
written, without normalisation by a URL parser (the contract `loopback`).

## Run

Without a stand: a side gives `url` to its threshold function (the one that decides the substitution of `host` of a client of its own cluster) and
compares the word with `expect`; DNS is not asked. Who performs is every client of the door of its own cluster: the agent
(`09-agent`), the workers script (`02-installer`), the cluster console (`06-console`), the domain console (`10-domain-console`:
`SIGNER_URL`, the worker door at the domain), the worker and the gateway to its console (`03-worker`), the clients of the resource door (the processes
that read the objects of the cluster by `RESOURCE_URL`: `03-worker`, `04-controller`, `06-console`, `08-domain`, `09-agent`; and the
resource `05-resource` itself — a client of the doors of the neighbours by the url of their door row: the bodies, buckets and tombstones of the neighbours; the Architect's
decision of 2026-10-27) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function).
