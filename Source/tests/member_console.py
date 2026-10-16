"""A fixture's signed member-console request, through the real generic CRUD gate.

Full HTTP framing is covered by test_member_edits. This adapter keeps large
multi-device fixtures in process; it uses the same signature, bounded body,
SpecConsole and persistent idempotency store, with no domain mutation callback.
"""
import io
import json
from types import SimpleNamespace
from w2cplatform.console import SpecConsole
from w2cplatform.domain.federation import Unreachable
from w2cplatform.spec import SpecController
from w2cplatform.trust.memberkey import MemberKey, sign_request


class SignedConsole:
    def __init__(self, spec, vars_, objects, wall, sealer=None):
        self.wall = wall
        self.key = MemberKey.load_or_make(vars_, sealer)
        ctl = SpecController(spec, vars_, objects, wall=wall)
        ctl.sealer = sealer
        self.console = SpecConsole(ctl, wall=wall)

    def apply(self, entry):
        raw = json.dumps(entry["body"], ensure_ascii=False, sort_keys=True).encode()
        replies = []
        h = SimpleNamespace(path=entry["path"], rfile=io.BytesIO(raw),
                            headers={"Content-Length": str(len(raw)), "Content-Type": "application/json",
                                     "Idempotency-Key": entry["key"],
                                     "X-Agent-Signature": sign_request(self.key, entry["method"], entry["path"], raw, self.wall())},
                            _send=lambda status, body: replies.append((status, body)))
        local = entry["path"][len("/" + self.console.spec.name):]
        self.console.agent_edit(h, entry["method"], local)
        if not replies:
            raise Unreachable("the fixture member console did not answer")
        return replies[-1]


def device_console(device, sealer=None):
    """A pinned-device fixture supplies its stores and published view to the generic console."""
    from pathlib import Path
    from w2cplatform import catalog
    spec = catalog.spec("cam")
    if spec is None:
        from w2cplatform.spec import SubsystemSpec
        spec = SubsystemSpec.load(str(Path(__file__).parents[1] / "vms" / "cam.subsystem.yaml"))
    signed = SignedConsole(spec, device.flash, device.ram, device.wall, sealer)
    class DeviceConsole:
        def apply(self, entry):
            response = signed.apply(entry)
            if response[0] < 400:
                device.publish()
            return response
    return DeviceConsole()


def admit_fixtures(vars_, names):
    """Explicit test admission; production admission remains the holder's job."""
    items, index = vars_.get("domain/members")
    doc = json.loads(items["doc"]) if items else {"rev": 0, "members": {}}
    missing = set(names) - set(doc["members"])
    if not missing:
        return
    doc["members"].update({name: {} for name in missing})
    doc["rev"] += 1
    vars_.put("domain/members", {"doc": json.dumps(doc, sort_keys=True)}, cas=index)
