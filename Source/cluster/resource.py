"""The resource on a cluster is the platform's resource process (`python3 -m w2cplatform
resource`, `w2cplatform.resource.platform_resource`) run by the platform's unit on every
server (`w2c-resource.service`): the platform's Resource, with what the loaded specs'
`holds:` keep (the boundary's step 6) — serving buckets, taking mirrors from its peers,
retaining every subsystem's buckets by that subsystem's policy, keeping the event
index over its own tree (the platform's events archive, `/data/platform/events`),
listing the workers registered there (`workers`, `running`), and the door to this
server's objects. Nothing here is new; the names say so:
platform/resources/<server>/heartbeat, platform/mirror, platform/doors/<server>.

Footage is not on its tree. It is in volumes of ObjectStorage, written through
the host's `obsd` (`vms-obsd.service`) by the recorder that holds each one,
and read through that recorder's archive door — a resource has nothing of it
to serve, retain or evacuate.

    cluster_resource   = w2cplatform.resource.platform_resource: an EventIndex attached, the specs' holds for retention
"""
from __future__ import annotations

from w2cplatform.resource import platform_resource as cluster_resource  # noqa: F401
from w2cplatform.resource import (PeerClient, Resource, mirror_settings, mirrored_buckets, peers_of,  # noqa: F401
                                  resources_seen, serve)
