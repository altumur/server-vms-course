"""Start the course's Python store door (old implementation) for the clean-room runner: one role socket at --socket."""
import argparse, os, signal, sys, threading
p = argparse.ArgumentParser()
p.add_argument("--source", required=True); p.add_argument("--data", required=True)
p.add_argument("--socket", required=True); p.add_argument("--body-limit", type=int, required=True)
a = p.parse_args()
sys.path.insert(0, a.source)
from w2cplatform.configstore import LocalBackend, StoreDaemon
from w2cplatform.storemachine import Rights
rights = Rights.parse({"roles": {"acceptance": {"read": ["acc/*"], "write": ["acc/*"], "delete": ["acc/*"]}}})
sockets = a.data + "/sockets"
service = StoreDaemon(LocalBackend(), node_id="old", sockets=sockets, rights=rights, body_limit=a.body_limit)
os.symlink(os.path.join(sockets, "acceptance.sock"), a.socket)
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set()); signal.signal(signal.SIGINT, lambda *_: stop.set())
try:
    stop.wait()
finally:
    service.stop()
