"""Which bus messages are observations of the camera — and nothing here needs GStreamer, so it is tested without it."""
import os

# The elements whose bus messages are observations: the ones this package registers, and whatever analytics
# element an installation adds (`EVENT_ELEMENTS`, comma-separated factory names). Everything else on the bus
# is GStreamer talking to itself.
#
# It used to be the other way round — a list of message names to DROP — and a list like that is wrong the day
# GStreamer grows a message: on the product's box `rtpbin` posted `application/x-rtp-source-sdes` every few
# seconds, and each went into the camera's event log as an event of the camera (feedback BL).
OUR_ELEMENTS = ("driverpacksrc", "archivesink")
PLUMBING = ("GstBinForwarded", "splitmuxsink-fragment-opened", "splitmuxsink-fragment-closed")


def observes(factory: str, name: str, extra: tuple = ()) -> bool:
    """Is a bus message `name`, posted by an element of `factory`, an observation of the camera?"""
    ours = OUR_ELEMENTS + tuple(extra) + tuple(f for f in os.environ.get("EVENT_ELEMENTS", "").split(",") if f)
    return factory in ours and name not in PLUMBING
