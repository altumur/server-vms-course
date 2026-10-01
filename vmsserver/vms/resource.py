"""The resource process — the platform's resource job (w2cplatform.resource)
with the VMS registered on it. One per server, pinned there for as long as
the server exists; on a box it is `python3 -m vms resource`
(`deploy/resource.container`), in М11 the `resource` system job. It has
no controller: it has a policy pass on a timer, a heartbeat, its HTTP, and
the event index over its own tree.

Its tree is EVENTS: the camera's buckets under `vms/<cam>/`, a recorder's under
`rec/<name>/`, the alarms', the journal's. Footage is not here any more. It is
in volumes of ObjectStorage, written through the host's `obsd` by the recorder
that holds each one (`vms/archive.py`): a volume is a ring, formatted at its
quota, that gives up its oldest minutes by itself — there is nothing on this
tree to repair, to retain by days or to free under a watermark, and no media
door here. A camera's timeline and its frames are asked of the recorders.

What the VMS adds is the one thing the platform cannot know: which event
buckets somebody said to KEEP (`kept_buckets`, from `rec/keeps/*`).

    platform/resources/<server>/heartbeat   {server, ts, url, usage, units, mirrors} — how the console finds it
    GET <url>/events?from&to&cam&kind&subsystem&unit   the platform's: this resource's EventIndex
    GET <url>/buckets/<sub>/<unit>, /events/<path>, /mirrored/<server>; PUT /mirror/<server>/<path>
"""
from __future__ import annotations

from w2cplatform.eventdatabase import EventIndex
from w2cplatform.resource import Resource


def vms_resource(root: str, server: str, url: str, vars_, objects, wall=None, peers=None,
                 bucket_seconds: int = 600) -> Resource:
    """The platform's resource for this server, with the event index over its tree and the VMS's keeps."""
    import time
    wall = wall or time.time
    r = Resource(root, server, url, vars_, objects, bucket_seconds, wall, peers)
    r.index = EventIndex(root, server, wall, bucket_seconds)
    r.kept = kept_buckets(vars_)
    return r


# Which event buckets a keep holds (`vms/keeps.py`), for the platform's retention pass. The camera's events
# are in `vms/<cam>/`; whatever a recorder wrote about a recording is in `rec/<name>/`. Read once a pass.
def kept_buckets(vars_):
    from . import keeps

    def once():
        all_ = keeps.declared(vars_)

        def kept(sub: str, unit: str, start: float, end: float) -> bool:
            from w2cplatform.events import tree_owner
            sub = tree_owner(sub)[0]                 # a keep holds the alarms' tree as it holds the other
            if sub == "vms":
                return keeps.held(keeps.spans_of_cam(all_, str(unit)), start, end)
            if sub == "rec":
                return keeps.held(keeps.spans_of(all_, str(unit)), start, end)
            return False
        return kept
    return once
