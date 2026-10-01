"""The GStreamer element and the actuators that use it. Needs PyGObject and
GStreamer (python3-gi, gst-plugins-good/bad) — Track 2. The tests skip this
package when `gi` is absent; the logic it calls (vms.archive, through a live
obsd) is tested without it.

    driverpacksrc   uri=driverpack://file/<name>: a file from MEDIA_DIR, looping, timestamps rebased
    actuator        the worker's pipelines (the tee, the fan-out, shared memory) and the recorder's: an appsink
                    whose every access unit is a sample into the volume's writer
    webrtc          the gateway's media path: one udpsrc/tee per camera, one webrtcbin per viewer, WHEP
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # __init__.py — the package docstring: the GStreamer element and the actuators that use it (Track 2)
#
# **Role in the module.** No code, only the docstring. `gstvms` is the part of the VMS that needs a media
# stack: PyGObject and GStreamer (`python3-gi`, `gst-plugins-good/bad` — the Containerfile installs exactly
# these). The docstring names the element — `driverpacksrc` (`uri=driverpack://file/<name>`: a file from
# `MEDIA_DIR`, looping, timestamps rebased) — and the actuators. The recorder's has no element of its own any
# more: an `appsink` hands each access unit to the volume's writer (`vms.recworker.RecSink`), and the engine
# behind it is `obsd`. The tests skip this package when `gi` is absent
# (`test_lesson2_driverpacksrc.py::test_the_element_runs_when_gstreamer_is_present` prints a skip), and the
# logic it calls — `vms.archive.Archive` against a live daemon, `gstvms.uri.resolve` — is tested without it.
#
# ## Module-level names
# None, and no imports: importing `gstvms` does not import `gi`. `gstvms.uri` stays importable everywhere;
# `gstvms.driverpacksrc` and `gstvms.actuator` each `import gi` at the top, which is
# why `vms/__main__.worker` wraps `from gstvms.actuator import GstActuator` in `try/except ImportError` and
# falls back to `FakeActuator`.
#
# ## Notes
# - Dependency direction: `gstvms` imports from `vms`, never the other way round at import time; the worker reaches `gstvms` only through that guarded import in `__main__`.
# ================================================================================================
