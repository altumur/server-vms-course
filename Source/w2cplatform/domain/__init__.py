"""The domain — the platform's layer above a set of clusters: the smallest
that can sit above them, be switched off, and be the top of the product.

Built on М11's `cluster` (imported, not copied) and through it on М10's
code — all of it one root, `Source/`. Exactly three things a cluster cannot know — lookup across
clusters, which cluster gets a unit, whether an answer is complete — plus
the discipline of a layer that may be down: a signer that is the top of
its own trust, identity that never reaches a worker, grants that expire
per cluster, a server that joins with nobody typing a secret, and a read
model that says how old it is.
"""
