"""Lesson 9: ADR-0074 C2 explicit CRUD queue, exercised on two declared test subsystems.

The former field base/via/conflict merge and carried human subject were removed by
ADR-0074's C2 amendment. Conflicts are now the member console's HTTP Outcome;
separate edits retain their own keys rather than merging values in the domain.
"""

from tests.frozen_data import frozen_testdata
import json
from types import SimpleNamespace
from w2cplatform.domain.agent import DomainAgent
from w2cplatform.domain.api import ConsoleAPI
from w2cplatform.domain.pending import AgentConsole, PendingEdits, apply_pending, _load
from w2cplatform.domain.federation import Unreachable
from tests.test_member_edits import site, console, raises


def _agent(e, url):
    return DomainAgent("north", e.vars, e.vars, now=e.wall,
                       console=AgentConsole(url, e.key, e.wall), key=e.key)


def _collect(e):
    e.pending.collect(SimpleNamespace(clusters={"north": SimpleNamespace(vars=e.vars, is_domain_holder=False)}))


def _queue(e, body, key, method="PUT"):
    return e.api.queue(method, "testsub", "counters", "unit" if method != "POST" else None,
                       body, key, "north")


def test_an_edit_for_a_member_that_is_off_is_kept_not_refused():
    with site() as e:
        reply = _queue(e, {"start": 7}, "offline")
        edit = e.pending.of("north")[reply["kept"]]
        assert reply["what"] == "start" and edit["body"] == {"start": 7}
        assert e.vars.get("testsub/counters/unit")[0] is None
        def off(_): raise Unreachable("member off")
        assert apply_pending({edit["id"]: edit}, SimpleNamespace(apply=off), e.wall()) == {}
        assert PendingEdits(e.vars, e.wall).of("north")[edit["id"]] == edit


def test_the_member_that_comes_back_takes_the_edit_from_its_own_agent():
    with site() as e, console(e) as url:
        reply = _queue(e, {"name": "unit"}, "create", "POST")
        assert _agent(e, url).sync()
        assert e.vars.get("testsub/counters/unit")[0] is not None
        _collect(e)
        assert e.pending.of("north") == {}
        outcome = _load(e.vars.get("domain/outcomes/north")[0], "outcomes")[reply["kept"]]
        assert outcome["status"] == 201 and outcome["what"] == "name"


def test_an_existing_unit_is_a_console_conflict_outcome_not_an_early_domain_refusal():
    with site() as e, console(e) as url:
        _queue(e, {"name": "unit"}, "first", "POST")
        agent = _agent(e, url); agent.sync(); _collect(e)
        reply = _queue(e, {"name": "unit"}, "another", "POST")
        assert reply["kept"] in e.pending.of("north")
        agent.sync(); _collect(e)
        assert e.pending.of("north") == {}
        assert _load(e.vars.get("domain/outcomes/north")[0], "outcomes")[reply["kept"]]["status"] == 409


def test_a_person_can_correct_a_refused_operation_with_a_new_key():
    with site() as e, console(e) as url:
        # The shape is valid, but the unit is not there on the member yet.
        bad = _queue(e, {"start": 7}, "bad", "PUT")
        agent = _agent(e, url); agent.sync(); _collect(e)
        assert _load(e.vars.get("domain/outcomes/north")[0], "outcomes")[bad["kept"]]["status"] == 404
        good = _queue(e, {"name": "unit"}, "fixed", "POST")
        agent.sync(); _collect(e)
        assert _load(e.vars.get("domain/outcomes/north")[0], "outcomes")[good["kept"]]["status"] == 201
        assert e.pending.of("north") == {}


def test_an_unknown_field_is_refused_before_the_operation_is_kept():
    with site() as e:
        raises(400, lambda: _queue(e, {"name": "unit", "unknown_field": 1}, "bad", "POST"))
        assert e.pending.of("north") == {}
        assert e.vars.get("testsub/counters/unit")[0] is None


def test_edits_made_while_it_is_off_keep_independent_operations():
    with site() as e:
        a = _queue(e, {"start": 7}, "a"); b = _queue(e, {"start": 14}, "b")
        assert a["kept"] != b["kept"]
        assert len(e.pending.of("north")) == 2
        assert e.pending.of("north")[a["kept"]]["body"] == {"start": 7}
        assert e.pending.of("north")[b["kept"]]["body"] == {"start": 14}


def test_authentication_is_checked_before_an_operation_is_kept():
    with site() as e:
        e.api.verifier = lambda token: token
        raises(401, lambda: _queue(e, {"start": 7}, "anonymous"))
        assert e.pending.of("north") == {}
        assert e.api.queue("PUT", "testsub", "counters", "unit", {"start": 7}, "person", "north", "anna")["kept"]
        edit = next(iter(e.pending.of("north").values()))
        assert "subject" not in edit  # The member console authenticates its own agent.


def test_carrying_it_home_twice_applies_it_once():
    with site() as e, console(e) as url:
        _queue(e, {"name": "unit"}, "once", "POST")
        agent = _agent(e, url); agent.sync()
        row = e.vars.get("testsub/counters/unit")
        e.wall.t += 1
        agent.sync()
        assert e.vars.get("testsub/counters/unit") == row
        _collect(e)
        assert e.pending.of("north") == {}


def test_without_a_place_to_keep_edits_the_api_says_503():
    with site() as e:
        api = ConsoleAPI(None)
        raises(503, lambda: api.queue("PUT", "testsub", "counters", "unit", {"start": 7}, "no-queue", "north"))


def test_a_report_about_an_earlier_key_does_not_clear_a_newer_edit():
    with site() as e:
        old = _queue(e, {"start": 7}, "old")
        entries = e.pending.of("north")
        outcome = apply_pending(entries, SimpleNamespace(apply=lambda _: (200, {"revision": 2})), e.wall())
        new = _queue(e, {"start": 14}, "new")
        e.pending.reconcile("north", outcome)
        assert old["kept"] not in e.pending.of("north")
        assert new["kept"] in e.pending.of("north")


LOGINS = ["http://10.0.0.5/videostream.cgi?usr=admin&pwd=Hunter2",
          "rtsp://10.0.0.9/user=admin_password=Hunter2_channel=1_stream=0.sdp",
          "rtsp://10.0.0.9/live;user=admin;pwd=Hunter2", "rtsp://admin:Hunter2@10.0.0.5/s",
          "rtsp://admin:Hunter2?x@10.0.0.5/s", "http://10.0.0.5/user/admin/password/Hunter2/snap.jpg",
          "https://s3.example.com/b/o?X-Amz-Signature=Hunter2"]


def test_an_address_with_a_password_is_refused_before_it_is_kept_carried_or_reported():
    from pathlib import Path
    from unittest.mock import patch
    import yaml
    from w2cplatform import catalog
    from w2cplatform.spec import SubsystemSpec
    raw = yaml.safe_load((frozen_testdata() / 'testsub.subsystem.yaml').read_text())
    raw["unit"]["fields"]["endpoint"] = {"type": "url", "secret_in": [
        {"param": ["signature"]},
        {"regex": r"(?i)(?:^|[/_&;])(?:user|usr|username)=(?P<login>[^_&;/#]*)_(?P<name>password|passwd|pwd|pass)=(?P<secret>[^&;/#]*?)(?:_[^_=&;/#]+=|[&;/#]|$)", "in": "path"},
        {"regex": r"(?i)(?:^|/)(?P<name>password|passwd|pwd|psw)/(?P<secret>[^/]+)", "in": "path"}]}
    credential_spec = SubsystemSpec.from_dict(raw)
    with site() as e, patch.object(catalog, "_loaded", {"testsub": credential_spec}), patch.object(catalog, "_derived", {}):
        for index, address in enumerate(LOGINS):
            for body in ({"name": address}, {"name": "unit", "nested": {"address": address}},
                         {"name": "unit", "nested": [address]}):
                raises(400, lambda: _queue(e, body, str(index), "POST"))
        assert e.pending.of("north") == {}
        assert not any("Hunter2" in json.dumps(e.vars.get(path)[0]) for path in e.vars.list(""))
