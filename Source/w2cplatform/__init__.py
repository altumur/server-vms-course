"""The platform, on one box (the package is `w2cplatform` only because Python owns the name `platform`). Everything here would host any fleet of
stateless shards writing bulk data; nothing here knows what a unit is.

    variables.py   a small, consistent config store with ModifyIndex and check-and-set (file-backed)
    objects.py     an object store (a directory)
    epoch.py       the fencing-token issuer and the lease, generic
    contract.py    what a subsystem gives the platform: a controller and its workers
    spec.py        the controller as data: SubsystemSpec from <sub>.subsystem.yaml, SpecController
    console.py     the console as data: SpecConsole over the same spec; console.js, the module every page is
                   built from, and console.html, the platform's page — the module and its mount
    events.py, eventdatabase.py, resource.py   buckets, the event index each resource reads its own by, the resource job
    longpoll.py    a reader of the events asks a resource to hold a request until a line it watches is written

М11 replaces variables.py with `configstore://` (the same semantics replicated by raft over the servers) and
objects.py with `cluster://` (a directory on every server, read through the resources), behind the same interfaces,
and changes nothing above this line.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # __init__.py — the package docstring: what `w2cplatform` is and what each module holds
#
# **Role in the module.** The file contains no code, only the package docstring. It names the package
# (`w2cplatform` rather than `platform` because Python's standard library already owns `platform`), states
# the one design line that governs everything under it — *nothing here knows what a unit is*; anything
# here would host any fleet of stateless shards writing bulk data — and gives a one-line map of the modules:
# `variables.py` (config store with ModifyIndex and check-and-set), `objects.py` (object store), `epoch.py`
# (fencing token and lease), `contract.py` (Controller and Worker bases), `spec.py` (the controller as
# data), `console.py`, `console.js` and `console.html` (the console as data), and `events.py` / `eventdatabase.py` /
# `resource.py` (buckets, the index over them, the resource job).
#
# The docstring also fixes the boundary the next module (М11) uses: М11 replaces `variables.py` with
# `configstore://` and `objects.py` with `cluster://` *behind the same interfaces* (the `Variables` and
# `ObjectStore` Protocols) and changes nothing above that line.
#
# ## Module-level names
# None. There are no imports either, so `import w2cplatform` pulls in nothing; each module is imported
# explicitly (`from w2cplatform.spec import SpecController`).
#
# ## Notes
# - `tests/test_lesson1_platform.py::test_the_platform_knows_nothing_about_its_subsystems` greps the code of every
#   `.py` under this directory for an import of a subsystem's package, and every file except this `__init__.py` for
#   the word a subsystem's spec calls its unit, in any case. This file is exempt from that word check because its
#   docstring once named the unit; it still must not import a subsystem's package, and `tests/test_boundary.py`
#   holds it, like the whole tree, to every word of the product (ADR-0001).
# ================================================================================================
