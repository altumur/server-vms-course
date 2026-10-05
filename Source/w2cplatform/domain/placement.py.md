# placement.py — Lesson 1: which CLUSTER gets a unit, by reachability; stored with a reason, by CAS

**Role in the module.** Placement at the level above М11's: the servers pick the server on resources, the cluster picks the worker on capacity, and the domain picks the CLUSTER on REACHABILITY — only it knows which clusters exist and what each can see. A unit on one network can be reached from the clusters that see that network and from nowhere else; capacity only breaks ties. Only place when you must: a dead server or a dead cluster is not a trigger. The decision is stored in the holder's store under `domain/placement/<unit>` with a reason and a time, by CAS — two placers racing is harmless: the second gets a conflict and re-reads.

## Names
- `class UnitSite(unit, network, load=1.0)` — where a unit's traffic can be seen from.
- `class ClusterPlacement(cluster, reason, at, rev)`.
- `class Refused` — no cluster can reach that network, or the only ones that can are silent: "the domain cannot place it", never "cluster X is full".
- `class ClusterPlacer(fed, vars=None, headroom=None, clock)` — `current(unit)`, `candidates(site, unreachable)`, `place(site, unreachable)` (an existing placement is returned untouched), `rebalance_across_clusters` (refused: a worker never crosses a cluster; a unit moves between clusters only when an operator asks).
