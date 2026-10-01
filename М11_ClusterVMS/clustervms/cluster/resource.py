"""The resource job on a cluster is М10's resource process (vms.resource) run as
a `system` job on every server with meta.archive: the platform's Resource with
the VMS registered on it — serving buckets, taking mirrors from its peers,
retaining every subsystem's buckets by that subsystem's policy, and keeping
the event index over its own tree. Nothing here is new; the names say so:
platform/resources/<server>/heartbeat, platform/mirror, job "resource".

Footage is not on its tree. It is in volumes of ObjectStorage, written through
the host's `obsd` (the `obsd` system job) by the recorder that holds each one,
and read through that recorder's archive door — a resource has nothing of it
to serve, retain or evacuate.

    cluster_resource   = vms.resource.vms_resource: an EventIndex attached, the VMS's keeps for bucket retention
"""
from __future__ import annotations

from vms.resource import vms_resource as cluster_resource  # noqa: F401
from w2cplatform.resource import (PeerClient, Resource, mirror_settings, mirrored_buckets, peers_of,  # noqa: F401
                                  resources_seen, serve)
