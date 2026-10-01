"""The two actuators — a worker's verb -> pipeline.

    GstActuator     the WORKER's: `driverpacksrc ! h264parse ! watchdog ! tee`, the tee's branch RTP to the
                    loopback port the RTSP fan-out (`livesrv.py`) serves as rtsp://<server>:8554/<cam>. It holds
                    the camera and records nothing.
    GstRecActuator  the RECORDER's: `rtspsrc location=<live_url> ! rtph264depay ! h264parse ! appsink` —
                    subscribed to the fan-out, every access unit a sample into the volume's writer (ObjectStorage,
                    through the host's `obsd`) under the recorder's epoch.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # actuator.py — the worker's verb → pipeline: `driverpacksrc ! h264parse ! watchdog ! tee` per camera, and
# the recorder's `… ! appsink` into the volume; the bus drained into (dead, posted)
#
# **Role in the module.** Lesson 4, Track 2 (needs `gi`). The real actuator `VmsWorker` runs its reconciler
# against when GStreamer is present (`vms/__main__.worker` tries to import it and falls back to
# `FakeActuator`). It has the same three-part surface as the fake — callable `(verb, cam) -> bool`, `pump()
# -> (dead, posted)`, `stop_all()` — so the worker does not know which it holds. It builds one
# `Gst.Pipeline` per camera from a launch string, keeps them in a dict, and turns bus messages into two
# lists the worker drains on every pass: cameras whose pipeline errored (`dead`) and element messages that
# are observations (`posted`). "The element never knows about buckets or epochs: it posts what it saw; the
# worker, which holds the epoch, turns it into a line." Importing `driverpacksrc` here registers the element.
#
# ## Module-level names
# - `log` — logger `gstvms`.
# - `DESC` — the worker's launch template: `driverpacksrc name=src ! h264parse ! watchdog
#   timeout={watchdog} ! tee name=t`, then two leaky branches: `rtph264pay ! udpsink 127.0.0.1:{port}` (the
#   loopback RTP the RTSP fan-out re-serves as rtsp://<server>:8554/<cam> — subscribers on any server) and
#   `shmsink socket-path=<SHM_DIR>/<cam>.shm` (the same bytes in shared memory — subscribers on THIS server,
#   the recorder first, read it with `shmsrc`: no RTSP hop, no fan-out process on the recording path). The worker
#   records nothing. `watchdog` posts an error if no buffer passes for `timeout`
#   ms, which is how a stalled source becomes a dead camera.
# - `REC_DESC` / `REC_SHM_DESC` — the recorder's: `rtspsrc location=<live_url> ! rtph264depay` or
#   `shmsrc socket-path=<…>.shm` (the source the recorder chose by where the worker is), then `h264parse !
#   watchdog ! appsink` — each access unit a sample into the volume's writer under the RECORDER's epoch.
#
# ## Notes
# - Verified where: the README says `gstvms/` is written to GStreamer's Python binding and not exercised in
#   the test run; the logic it calls (`resolve`, the recorder's sink into a live `obsd`) is. The zombie with two
#   real worker processes and `kill -9` mid-recording are the box's exercises.
# - Bus callbacks run on the GLib main context; since the worker runs no GLib main loop, `add_signal_watch`
#   delivery depends on the default main context being iterated — the code as written relies on it, and the
#   worker's loop only reads the lists `pump` hands back.
# ================================================================================================
from __future__ import annotations

import logging
import os

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from . import driverpacksrc  # noqa: E402,F401 — registers the element
from .observes import observes      # noqa: E402 — which bus messages are observations; no GStreamer needed to test it

log = logging.getLogger("gstvms")
Gst.init(None)

# No `uri=` and no credential in the template. A launch string is what ends up in a log line, in a crash
# dump and in `ps`, so the three things worth hiding are set as PROPERTIES after `parse_launch` — by
# construction, rather than by remembering to redact at every place that prints one.
DESC = ("driverpacksrc name=src ! h264parse ! watchdog timeout={watchdog} ! tee name=t "
        "t. ! queue leaky=downstream max-size-buffers=30 ! {live} "
        "t. ! queue leaky=downstream max-size-buffers=30 ! {shm}")
SHM = "shmsink socket-path={path} shm-size=20000000 wait-for-connection=false sync=false"      # the tee's same-server branch: any number of shmsrc readers
LIVE = "rtph264pay config-interval=1 pt=96 ! udpsink host=127.0.0.1 port={port} sync=false"   # the tee's branch: RTP to the loopback port
IDLE = "fakesink sync=false"                                                                    # the RTSP fan-out (livesrv) serves from
# The recorder's sink is not a file: every access unit leaves the pipeline through `appsink` and goes into the
# volume's writer as one sample (`RecSink`, `vms/recworker.py`) — byte-stream, one access unit per buffer, the
# parameter sets on every key frame (`config-interval=-1`), so a sequence the engine opens on a key frame can be
# played on its own.
REC_SINK = ("h264parse config-interval=-1 ! video/x-h264,stream-format=byte-stream,alignment=au ! "
            "watchdog timeout={watchdog} ! {ring}appsink name=sink emit-signals=true sync=false max-buffers=200")
# The prebuffer of a `when: offline` backup (Lesson 26): a queue that holds the last N seconds and drops the
# oldest when full — `leaky=downstream` — with its source pad blocked while the backup is on hold. Released,
# it pushes what it holds into the sink first. After the watchdog, so a held pipeline is still watched.
RING = "queue name=ring max-size-time={ring_ns} max-size-buffers=0 max-size-bytes=0 leaky=downstream ! "
REC_DESC = "rtspsrc location={source} latency=200 protocols=tcp name=src ! rtph264depay ! " + REC_SINK       # another server's worker: its fan-out
# Backfill (Lesson 16): a range out of the holder's playback door, its access units collected as samples the
# way a live recording's are. `souphttpsrc` because the door is HTTP — a browser has to seek it too — and the
# range is in the query, so nothing here knows how the vendor addresses time.
REC_RANGE_DESC = ("souphttpsrc location={source} ! qtdemux ! h264parse config-interval=-1 ! "
                  "video/x-h264,stream-format=byte-stream,alignment=au ! appsink name=sink emit-signals=true sync=false")
REC_SHM_DESC = "shmsrc socket-path={path} is-live=true do-timestamp=true name=src ! video/x-h264,stream-format=byte-stream ! " + REC_SINK   # this server's worker: its tee, directly


# State: `watchdog` (ms), `pipelines` (`{camera id:
# Gst.Pipeline}`), `dead` (ids whose bus posted an error since the last pump), `posted` (`(camera, kind,
# fields)` since the last pump).
class GstActuator:
    """The worker's: holds the camera, serves the fan-out, records nothing."""

    def __init__(self, watchdog_ms: int = 8000, rtsp_port: int = 8554, rtsp_address: str = "127.0.0.1"):
        self.watchdog = watchdog_ms
        from .livesrv import FanOut
        self.fanout = FanOut(rtsp_port, rtsp_address)
        self.rtsp_port = self.fanout.port                # what the OS gave, when `rtsp_port` was 0                  # rtsp://<server>:8554/<cam>: one shared factory per camera over its loopback port
        self.pipelines: dict[int, Gst.Pipeline] = {}
        self.dead: list[int] = []
        self.posted: list[tuple[int, str, dict]] = []   # what elements posted on the bus: (camera, kind, fields)

    # The reconciler's actuator. For `stop` or `restart` with a running pipeline: pop it, send EOS (lets the
    # last access units reach the sink), then `NULL`. `stop`
    # returns True there. For `start`/`restart`: format `DESC` with the row's `source` as the URI, the
    # watchdog, the camera id, `cam["epoch"]` (added by `VmsWorker._actuate`; 0 if absent) and the ports;
    # `Gst.parse_launch` — an exception (a refused URI from `uri.resolve`, a missing
    # plugin) is logged and returns False, which the reconciler counts as a failure with backoff. Then a
    # signal watch on the bus: `message::error` appends the camera to `dead`; `message::element` goes to
    # `_posted`. `set_state(PLAYING)` returning `FAILURE` is False. Success stores the pipeline and returns
    # True.
    def __call__(self, verb: str, cam: dict) -> bool:
        cid = cam["id"]
        if verb in ("stop", "restart") and cid in self.pipelines:
            p = self.pipelines.pop(cid)
            p.send_event(Gst.Event.new_eos())            # lets the last access units reach the sink
            p.set_state(Gst.State.NULL)
        if verb == "stop":
            self._unpublish(cid)
            return True
        try:
            p = Gst.parse_launch(self.describe(cam))
            src = p.get_by_name("src")
            src.set_property("uri", cam["source"])                    # the URI, after the parse: see DESC
            if cam.get("cred_username"):
                src.set_property("user", cam["cred_username"])
            if cam.get("cred_secret"):
                src.set_property("password", cam["cred_secret"])
        except Exception as e:                        # noqa: BLE001
            log.error("camera %s: %s", cid, e)        # the message may name the URI; it can no longer name the password
            return False
        bus = p.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", lambda b, m, c=cid: self.dead.append(c))
        bus.connect("message::element", lambda b, m, c=cid: self._posted(c, m))     # motion, person, ...: an element saw something
        self._before_play(p, cam)
        if p.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            return False
        self.pipelines[cid] = p
        self._publish(cid, cam)
        return True

    # What a subclass does to a built pipeline before it plays — the recorder blocks its ring here, so that
    # not one buffer reaches the sink of a pipeline that starts on hold.
    def _before_play(self, p, cam: dict) -> None:
        pass

    # The pipeline for this verb's row: the worker's DESC with the tee's loopback branch.
    def describe(self, cam: dict) -> str:
        live = LIVE.format(port=cam["live_port"]) if cam.get("live_port") else IDLE
        shm = SHM.format(path=cam["live_shm"][len("shm://"):]) if cam.get("live_shm") else IDLE
        return DESC.format(watchdog=self.watchdog, live=live, shm=shm)

    def _publish(self, cid: int, cam: dict) -> None:
        if self.fanout is not None and cam.get("live_port"):
            self.fanout.publish(str(cid), cam["live_port"])

    def _unpublish(self, cid: int) -> None:
        if self.fanout is not None:
            self.fanout.unpublish(str(cid))

    # Filters an element message into an observation. Messages with no structure, or posted by an element that
    # is not one of ours (`gstvms/observes.py`), are plumbing and dropped. Otherwise the structure's name is the event kind (`motion`, `person`, … — whatever an
    # analytics element posts) and its scalar fields (`int`, `float`, `str`, `bool`) are copied; appended to
    # `posted`. The worker's `pump_once` turns each into `observe(cid, kind, **fields)`, a line in the
    # camera's bucket, if it still holds the epoch.
    #
    # ONLY WHAT ONE OF OUR ELEMENTS SAID (feedback BL). The filter used to be a list of names to DROP, and a
    # list like that is wrong the day GStreamer grows a message: on the product's box `rtpbin` posted
    # `application/x-rtp-source-sdes` every few seconds, and each went into the camera's event log as an event
    # of the camera. So the question is turned round — who posted it — and `observes` answers it.
    def _posted(self, cid: int, msg) -> None:
        st = msg.get_structure()
        src = getattr(msg, "src", None)
        factory = src.get_factory() if src is not None and hasattr(src, "get_factory") else None
        if st is None or not observes(factory.get_name() if factory is not None else "", st.get_name()):
            return                                       # plumbing, not an observation
        fields = {}
        for i in range(st.n_fields()):
            name = st.nth_field_name(i)
            v = st.get_value(name)
            if isinstance(v, (int, float, str, bool)):
                fields[name] = v
        self.posted.append((cid, st.get_name(), fields))

    # Returns and clears both lists; every dead camera's pipeline is popped and set to `NULL`. The worker
    # then calls `reconciler.lost(cid)` (restart after backoff) and writes a `silent` event for it.
    def pump(self) -> tuple[list[int], list[tuple[int, str, dict]]]:
        """(dead cameras, posted observations) since the last pump. The element
        never knows about buckets or epochs: it posts what it saw; the worker,
        which holds the epoch, turns it into a line."""
        dead, self.dead = self.dead, []
        posted, self.posted = self.posted, []
        for cid in dead:
            p = self.pipelines.pop(cid, None)
            if p:
                p.set_state(Gst.State.NULL)
        return dead, posted

    # `self("stop", {"id": cid})` for every running pipeline: EOS then NULL for each. Called by
    # `VmsWorker.fence` and at the end of `VmsWorker.run` — with `vmsworker@.container`'s `StopTimeout=20`
    # giving the finalizations time.
    def stop_all(self) -> None:
        for cid in list(self.pipelines):
            self("stop", {"id": cid})


class GstRecActuator(GstActuator):
    """The recorder's: `rtspsrc` on the camera's fan-out URL — or `shmsrc` on the worker's shared-memory
    branch when the worker is on this server — then `appsink`, each access unit a sample into the volume's
    writer under the recorder's epoch. No fan-out of its own; nothing here reads a camera."""

    def __init__(self, watchdog_ms: int = 8000):
        self.watchdog = watchdog_ms
        self.fanout = None
        self.range_error = ""                            # why the last range pipeline failed, if it did (Lesson 16)
        self.pipelines, self.dead, self.posted = {}, [], []

    # `release` opens a held pipeline's ring; every other verb is the worker's.
    def __call__(self, verb: str, cam: dict) -> bool:
        if verb == "release":
            return self._release(cam["id"])
        if verb in ("stop", "restart") and cam["id"] in getattr(self, "sinks", {}):
            # The open sequence closed: what was taken is kept — and a restart (back on hold, a new source) must not
            # let the next frames continue it after a gap: a hole inside a sequence is drawn as footage. Closed AFTER
            # the pipeline is down: a key frame handed to the sink between `finish` and NULL would open a sequence
            # nobody closes (the review's first pass, blocker 4, in its obsd form).
            sink = self.sinks.pop(cam["id"])
            ok = super().__call__(verb, cam)
            sink.finish()
            return ok
        return super().__call__(verb, cam)

    # A pipeline that starts on hold: block the ring's source pad before the first buffer can pass. And on every
    # recorder pipeline: count what reaches the sink — the writer watch's "offered" (Lesson 10) — and hand each
    # access unit to the volume's writer, with the time it was CAPTURED: the pipeline's running time turned into
    # the wall clock, so a released ring lands thirty seconds back where it belongs, not now. A sample the engine
    # refused makes the sink skip to the next key frame — the engine opens a sequence on nothing else.
    def _before_play(self, p, cam: dict) -> None:
        import time as _time
        from w2cplatform.obsd import ObsdError, archive_ms, video
        sink = p.get_by_name("sink")
        if sink is not None and cam.get("sink") is not None:
            self.offered_bytes = getattr(self, "offered_bytes", {})
            self.offered_bytes.setdefault(cam["id"], 0)
            self.sinks = getattr(self, "sinks", {})
            self.sinks[cam["id"]] = writer = cam["sink"]
            skipping = {"until_key": False}

            def on_sample(appsink, cid=cam["id"]):
                smp = appsink.emit("pull-sample")
                buf = smp.get_buffer()
                data = buf.extract_dup(0, buf.get_size())
                self.offered_bytes[cid] += len(data)
                key = not buf.has_flags(Gst.BufferFlags.DELTA_UNIT)
                clock = p.get_clock()
                running = (clock.get_time() - p.get_base_time()) if clock is not None else 0
                ago = max(0, running - buf.pts) / Gst.SECOND if buf.pts != Gst.CLOCK_TIME_NONE else 0.0
                begin = _time.time() - ago
                dur = buf.duration / Gst.SECOND if buf.duration != Gst.CLOCK_TIME_NONE else 0.04
                if skipping["until_key"] and not key:
                    return Gst.FlowReturn.OK
                try:
                    writer.put(video(archive_ms(begin), archive_ms(begin + dur), data, key))
                    skipping["until_key"] = False
                except ObsdError:
                    skipping["until_key"] = True          # refused: the rest of this group is lost, the next key opens anew
                return Gst.FlowReturn.OK

            sink.connect("new-sample", on_sample)
        if cam.get("hold"):
            pad = p.get_by_name("ring").get_static_pad("src")
            self.blocks = getattr(self, "blocks", {})
            self.blocks[cam["id"]] = pad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, lambda *_: Gst.PadProbeReturn.OK)

    def offered(self, cid):
        return getattr(self, "offered_bytes", {}).get(cid)

    # Unblock — and drop what the ring pushes until its first KEYFRAME: the leaky queue dropped its oldest
    # buffers one at a time, so it may begin mid-GOP, and the engine opens a sequence only on a key frame. The
    # product measured the result on a box: recording began 28.5 s before the hold was lifted.
    def _release(self, cid) -> bool:
        p = self.pipelines.get(cid)
        probe = getattr(self, "blocks", {}).pop(cid, None)
        if p is None or probe is None:
            return False
        pad = p.get_by_name("ring").get_static_pad("src")

        def to_keyframe(pad_, info):
            if info.get_buffer().has_flags(Gst.BufferFlags.DELTA_UNIT):
                return Gst.PadProbeReturn.DROP
            return Gst.PadProbeReturn.REMOVE

        pad.add_probe(Gst.PadProbeType.BUFFER, to_keyframe)
        pad.remove_probe(probe)
        return True

    # One range from the device's own archive, run to completion: the pipeline ends by itself at EOS, and every
    # access unit came out of `appsink` as a sample, its time the range's start plus its own timestamp. The
    # recorder lands them (`RecWorker._land`), dropping any group live recording reached first. (Not run against
    # GStreamer here.)
    def record_range(self, cam, source: str, t0: float, t1: float) -> list:
        from w2cplatform.obsd import archive_ms, video
        out = []
        p = Gst.parse_launch(REC_RANGE_DESC.format(source=source))
        sink = p.get_by_name("sink")

        def on_sample(appsink):
            smp = appsink.emit("pull-sample")
            buf = smp.get_buffer()
            begin = t0 + (buf.pts / Gst.SECOND if buf.pts != Gst.CLOCK_TIME_NONE else 0.0)
            dur = buf.duration / Gst.SECOND if buf.duration != Gst.CLOCK_TIME_NONE else 0.04
            out.append(video(archive_ms(begin), archive_ms(begin + dur), buf.extract_dup(0, buf.get_size()),
                             not buf.has_flags(Gst.BufferFlags.DELTA_UNIT)))
            return Gst.FlowReturn.OK

        sink.connect("new-sample", on_sample)
        p.set_state(Gst.State.PLAYING)
        # A deadline, not for ever (feedback BE): a device that stops answering in the middle of a range would keep
        # this call — and whoever waits for it — as long as the TCP connection cared to. Generous, because a card
        # is slow: the length of the range, and a minute, and never less than five.
        deadline = max(300.0, (t1 - t0) + 60.0)
        msg = p.get_bus().timed_pop_filtered(int(deadline * Gst.SECOND), Gst.MessageType.EOS | Gst.MessageType.ERROR)
        p.set_state(Gst.State.NULL)
        self.range_error = ""
        if msg is None:
            log.error("camera %s: backfill %s-%s: the device did not finish the range in %.0f s", cam, t0, t1, deadline)
            self.range_error = f"the device did not finish the range in {deadline:.0f} s"
        if msg is not None and msg.type == Gst.MessageType.ERROR:
            log.error("camera %s: backfill %s-%s: %s", cam, t0, t1, msg.parse_error()[0])
            # Said, not only logged: a range that failed half way is not a range the source does not have,
            # and the recorder must not remember it as "nowhere" (Lesson 16).
            self.range_error = str(msg.parse_error()[0])
        return out

    # The ring is in the pipeline only for a backup that may be held.
    def describe(self, cam: dict) -> str:
        ring = cam.get("ring_seconds")
        kw = dict(watchdog=self.watchdog, ring=RING.format(ring_ns=int(float(ring) * Gst.SECOND)) if ring else "")
        if cam["source"].startswith("shm://"):                                 # the worker is on this server: read its tee's shared memory
            return REC_SHM_DESC.format(path=cam["source"][len("shm://"):], **kw)
        return REC_DESC.format(source=cam["source"], **kw)
