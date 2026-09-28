"""The event index is the platform's, one per resource: w2cplatform.eventdatabase.EventIndex, run
inside the resource job (`python3 -m cluster resource`) — the resource's tree read where it lies, nothing to
rebuild. The console holds none — MergedIndex asks and merges. Kept here under the name the platform uses."""
from w2cplatform.eventdatabase import EventIndex, MergedIndex  # noqa: F401
