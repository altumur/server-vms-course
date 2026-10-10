"""What a subsystem's code used to decide inside the platform's controller, and a spec declares now (the boundary's step
6, ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md §4, «три места вместо хука»):

    placement.constraint, tie_break   a closed catalogue: a spec naming another rule does not load (`register_constraint`
                                      is gone, and nobody had gone through it)
    placement.affinity                a row of the spec's table named in the unit's field BINDS the unit to the place it
                                      is (`strict`), and that place takes nobody else; a row that says `admits: false`
                                      takes nobody (it was an admit hook)
    placement.near.prefer             of several units of the followed subsystem, the one whose row — or the row its
                                      field refs — says so (it was a near-rank hook)
    fields.<f>.ref + must_match       what a field points at must agree with the row (it was a refusal hook)
    fields.<f>.unique                 one value per cluster; `canonical` — one address in its RFC 3986 spelling
    placement.group_by.cut_at         a group is the host an address names (`host`), or the address up to a segment of
                                      its path (it was an override of `group_value`)
    fields.<f>.schemes (a url)        the schemes it is reached by, and how each writes its address, in a closed
                                      dictionary: `host: authority | path`, `fragment: keep | none`, `none: [<authority>]`
    tables: {<t>: {key, fields, …}}   a table the console serves — written, listed, deleted, journalled (it was a
                                      subsystem's routes on the console)
    requests: {schema, key, …}        `POST /requests`, a row for a worker to answer (it was a subsystem's route)
    rights: {reach, names, …}         what a change or a request reaches beyond its unit (it was a subsystem's code in
                                      the console: `moved_units`, `body_units`, `CLUSTER_ROWS`)
    door: {routes}                    what a unit's holder serves a page itself, handed out with the unit's place and a
                                      token the console signs and the holder checks (it was a subsystem's routes on the
                                      console, `extra`; `door.py`)

A test of the platform alone: two subsystems invented here, `bin` and `pick`; no subsystem's package is imported.
"""
from __future__ import annotations

import os
import tempfile

from w2cplatform import catalog
from w2cplatform.console import Heartbeat
from w2cplatform.objects import FsObjectStore
from w2cplatform.spec import Refused, SpecController, SubsystemSpec, canonical_url, url_cut, url_host
from w2cplatform.variables import FileVariables

CAP = {"capacity": {"from": "capacity", "default": 4}}
BIN = {"name": "bin",
       "unit": {"rows": "items", "id": "name",
                "fields": {"name": {"type": "string", "required": True},
                           "owner": {"type": "string"},
                           "home": {"type": "string", "ref": "bin/bays", "must_match": {"owner": "owner"}},
                           "tag": {"type": "string", "unique": True},
                           "addr": {"type": "url", "unique": "canonical"}}},
       "tables": ["bays"],
       "placement": {**CAP, "place_by": "bay", "group_by": {"field": "addr", "cut_at": "part"},
                     "affinity": {"field": "home", "table": "bays", "server_field": "server",
                                  "strict": {"kind": ["reserve", "spare"], "enabled": True}}}}
PICK = {"name": "pick", "unit": {"rows": "picks", "id": "name", "fields": {"name": {"type": "string", "required": True}}},
        "placement": {**CAP, "near": {"sub": "bin", "of": "owner", "prefer": {"home.kind": ["reserve", "spare"]}}}}


class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t


def _box():
    root = tempfile.mkdtemp(prefix="declared-")
    return FileVariables(os.path.join(root, "config")), FsObjectStore(os.path.join(root, "objects")), Clock(1_757_500_000.0)


def _worker(objects, wall, spec, worker, server, bay, status=()):
    objects.put(spec.sub.heartbeat_key(worker),
                Heartbeat(worker, wall(), list(status), {"server": server, "bay": bay, "capacity": 4, "headroom": 4}).to_bytes())


def _refused(make, words: str) -> None:
    try:
        make()
    except (ValueError, Refused) as e:
        assert words in str(e), (words, str(e))
        return
    raise AssertionError(f"taken, and should not have been: {words}")


def test_the_catalogue_is_closed_and_nothing_registers_a_rule():
    """A constraint or a tie-break the catalogue does not hold is refused at load, in words; the module has no door to
    add one (`register_constraint`, `register_admit`, `register_near_rank`, `register_refuse` are gone)."""
    import w2cplatform.spec as spec
    for gone in ("register_constraint", "register_admit", "register_near_rank", "register_refuse", "ADMIT", "NEAR_RANK", "REFUSE"):
        assert not hasattr(spec, gone), gone
    base = {"name": "probe", "unit": {"rows": "items", "id": "name", "fields": {"name": {"type": "string"}}}}
    _refused(lambda: SubsystemSpec.from_dict({**base, "placement": {**CAP, "constraint": "my-own-rule"}}), "the catalogue is closed")
    _refused(lambda: SubsystemSpec.from_dict({**base, "placement": {**CAP, "tie_break": "fewest-units"}}), "tie_break is one of")
    _refused(lambda: SubsystemSpec.from_dict({**base, "placement": {**CAP, "affinity": {"field": "name", "table": "nope"}}}),
             "placement.affinity is")
    _refused(lambda: SubsystemSpec.from_dict({**base, "unit": {**base["unit"], "fields": {"name": {"type": "string", "must_match": {"a": "name"}}}},
                                              "placement": CAP}), "has no `ref`")
    _refused(lambda: SubsystemSpec.from_dict({**base, "unit": {**base["unit"], "fields": {"name": {"type": "string", "unique": "canonical"}}},
                                              "placement": CAP}), "`unique` is true, or `canonical` for a url field")
    _refused(lambda: SubsystemSpec.from_dict({**base, "placement": {**CAP, "group_by": {"field": "name", "cut_at": "x"}}}),
             "group_by.cut_at reads a url field")


def test_an_address_has_one_spelling_by_rfc_3986_and_nothing_a_scheme_means():
    """RFC 3986 §6.2.2: the scheme and the host in lower case, a percent-encoding in upper case and an unreserved one
    decoded, the dot segments gone, an empty port gone. A default port written out, or `02` beside `2`, stay two
    spellings: that is a scheme's meaning, which the platform does not know."""
    assert canonical_url("HTTP://Host.Example:/a/./b/../c/%7euser/%2f") == "http://host.example/a/c/~user/%2F"
    assert canonical_url("http://h:80/x") != canonical_url("http://h/x")
    assert canonical_url("x://h/part/02") != canonical_url("x://h/part/2")
    assert canonical_url("not an address") == "not an address"
    assert url_cut("x://H/a/b/part/7?q=1", "part") == "x://h/a/b" == url_cut("x://h/a/b/part/8", "part")
    assert url_cut("x://h/a/b", "part") == "x://h/a/b"                    # no such segment: its own group


def test_a_group_is_the_host_an_address_names_in_one_spelling_and_a_scheme_declares_where_its_host_stands():
    """`cut_at: host`: neither the scheme, the port, a login nor the path is part of the group; the host in lower case
    without the root's dot, an IP as `ipaddress` writes it (IPv6 unbracketed and folded, no zone; IPv4-mapped as IPv4).
    A host as written: an escape is not decoded, and what is neither a name of RFC 1123 labels nor an IP — or an address
    that does not parse — is no host, refused at write (ADR 0053). `schemes` says where a scheme writes its host: the path's first segment
    (`host: path`, the authority then a name the group does not hold; an empty segment leaves it the authority), no
    fragment (`fragment: none`: `#` is a character, the host after the last `@`), authorities naming none (`none`)."""
    assert url_host("x://H.:8/a/1") == url_host("y://h/b/2") == url_host("x://u:p@h") == "h"
    assert url_host("x://[0:0::1]:9/") == url_host("x://[::1]") == "::1"
    assert url_host("x://[::FFFF:10.0.0.5]/") == url_host("x://10.0.0.5./") == "10.0.0.5"
    assert url_host("x://[fe80::1%25en0]/") == "fe80::1"
    for none in ("x://h%2Ecorp/", "x://h_1/", "x://010.0.0.5/", "x://[fe80::1%en0]/", "x://h:pw/",
                 "x:///a", "h", "", "x://a b/"):
        assert url_host(none) == "", none
    assert url_host("x://h/%zz") == "h"              # the path's broken escape is the url rule's refusal, the host still read
    assert url_host("x://a#@h/") == "a" and url_host("x://a#@h/", {"x": {"fragment": "none"}}) == "h"
    hub = {"m": {"host": "path", "none": ["local"]}}
    assert url_host("m://hub1/H.Example/a", hub) == url_host("m://hub2/h.example:21/b", hub) == "h.example"
    assert url_host("m://hub1", hub) == url_host("m://hub1/", hub) == "hub1"           # no host in the path: the authority
    assert url_host("m://local/x", hub) == url_host("m://LOCAL.", hub) == url_host("m://local", hub) == ""
    assert url_host("m://local:9/x", hub) == url_host("m://u@local/x", hub) == "x"   # `none` is the authority as written
    assert url_host("m:///h/x", hub) == "h"                                    # an empty vendor: the spec's schema to refuse
    assert url_host("m://hub/a:b%40h/x", hub) == url_host("m://hub/a:b@h:80/x", hub) == "h"   # a login set aside
    assert url_host("m://hub/a:b/c@h/x", hub) == url_host("m://hub/h:pw/x", hub) == ""   # a port no number: a login's
    assert url_host("m://hub/a:b%40h%2Ecorp/x", hub) == ""                     # a host only decoding makes is none
    # testsub2: a tally's feed by its host — a mirror's in its path, and the shelf's own copy (`local`) none
    spec = SubsystemSpec.load(os.path.join(os.path.dirname(__file__), "testdata", "testsub2.subsystem.yaml"))
    assert spec.group_of("https://Feed.Example/t1") == spec.group_of("sftp://feed.example:22/t2") == "feed.example"
    assert spec.group_of("mirror://hub/feed.example/t3#x@y") == "feed.example"
    assert spec.group_of("mirror://local/t4") == "" == spec.group_of("")
    # ADR 0053: with `cut_at: host` there is no unit without a group but the ones `none` says — a host nobody can tell is
    # refused at write, in words that do not repeat it; `local` is the lawful exception, and a value not given asks nothing
    for unreadable in ("https://feed_1.example/t5", "mirror://hub/h%2Ecorp/t6", "https://010.0.0.5/t7", "sftp:///t8"):
        _refused(lambda: spec.refuse({"feed": unreadable}), "feed names no host that can be told")
        assert unreadable not in str(spec.group_refusal(unreadable))
    assert spec.group_refusal("mirror://local/t4") is None and spec.group_refusal("") is None
    spec.refuse({"feed": "mirror://local/t4"})
    spec.refuse({"feed": "https://feed.example/t1"})


def test_a_url_fields_schemes_are_a_closed_dictionary_read_alike_by_its_refusal_and_its_group():
    """A url field's `schemes` is a map of the schemes it is reached by to the words of a closed dictionary — `{}` for one
    read by RFC 3986 — and the one reading of its addresses: the refusal (a scheme not in the map, a `#` of a scheme with
    a fragment) and the group (`cut_at: host`) ask the same words (ADR 0053). The list it was is refused (ADR 0003); so is
    a word not of the dictionary, a value not of the word's, and `schemes` said under `group_by`."""
    def spec(field_schemes, **g):
        return SubsystemSpec.from_dict({"name": "probe", "unit": {"rows": "items", "id": "name", "fields": {
            "name": {"type": "string"}, "addr": {"type": "url", **({"schemes": field_schemes} if field_schemes is not None else {})}}},
            "placement": {**CAP, "group_by": {"field": "addr", "cut_at": "host", **g}}})

    ok = spec({"m": {"host": "path", "fragment": "none", "none": ["local"]}, "y": {"host": "authority"}, "x": {}})
    assert ok.group_of("m://a/b/c") == "b" and ok.group_of("x://a/b") == "a" and spec(None).group_of("m://a/b") == "a"
    ok.refuse({"addr": "m://a/b/c#d"})                                 # no fragment there: `#` a character, as its group
    assert ok.group_of("m://a/b/c#d") == "b" and ok.group_of("x://a#@b/c") == "a"
    _refused(lambda: ok.refuse({"addr": "x://a/b#c"}), "may not hold '#'")          # a fragment: refused as before
    _refused(lambda: ok.refuse({"addr": "z://a/b"}), "addr is reached by m, y, x, not by 'z'")
    _refused(lambda: spec(["m", "x"]), "`schemes` is a map")
    _refused(lambda: spec({"m": {"port": "none"}}), "'port' is not a word of the dictionary")
    _refused(lambda: spec({"m": {"host": "query"}}), "m.host is one of authority, path")
    _refused(lambda: spec({"m": {"fragment": "drop"}}), "m.fragment is one of keep, none")
    _refused(lambda: spec({"m": None}), "a scheme says {host?, fragment?, none?}")
    _refused(lambda: spec({"M": {}}), "not a scheme in lower case")
    _refused(lambda: spec({"m": {"none": "local"}}), "m.none is a list of authorities")
    _refused(lambda: spec({"m": {"none": ["a/b"]}}), "m.none is a list of authorities")
    _refused(lambda: spec({"m": {"none": [False]}}), "m.none is a list of authorities")
    _refused(lambda: spec({"m": {}}, schemes={"m": {"fragment": "none"}}), "the url field's `schemes`")
    _refused(lambda: spec({"m": {}}, port=1), "placement.group_by is a field, or")
    _refused(lambda: SubsystemSpec.from_dict({"name": "probe", "unit": {"rows": "items", "id": "name", "fields": {
        "name": {"type": "string"}}}, "placement": {**CAP, "group_by": {"field": "name", "cut_at": "host"}}}),
        "group_by.cut_at reads a url field")


def test_a_row_points_only_at_what_agrees_with_it_and_a_unique_value_is_one_units():
    """`must_match`: a unit whose `home` names a bay of another owner is refused, on a create and on an edit, and a bay
    row that does not parse is no row to point at; a bay nobody declared asks nothing. `unique`: a second unit with the
    same tag, or the same address in another spelling, is refused — asked only when the value is new to the row."""
    vars_, objects, wall = _box()
    spec = SubsystemSpec.from_dict(BIN)
    ctl = SpecController(spec, vars_, objects, wall=wall)
    vars_.put("bin/bays/b1", {"owner": "ann", "kind": "plain"})
    vars_.put("bin/bays/b2", {"kind": "plain"})                            # nobody's: anybody's units point at it
    ctl.create({"name": "a", "owner": "ann", "home": "b1", "tag": "t1", "addr": "x://h/part/1"})
    _refused(lambda: ctl.create({"name": "b", "owner": "bob", "home": "b1"}), "home b1 is owner ann's")
    ctl.create({"name": "b", "owner": "bob", "home": "b2"})
    _refused(lambda: ctl.update("b", {"home": "b1"}), "home b1 is owner ann's")
    # …a refusal that depends on the rows standing: 409 with `fault: must_match` (ADR 0031's rule), either way
    from tests.conftest import Served
    from w2cplatform.console import SpecConsole, refused_status
    from w2cplatform.spec import Mismatched
    try:
        ctl.update("b", {"home": "b1"})
    except Mismatched as e:
        assert refused_status(e) == 409 and e.fault == "must_match"
    with Served(SpecConsole(ctl, wall=wall)) as call:
        st, out = call("POST", "/items", {"name": "b-door", "owner": "bob", "home": "b1"})
        assert st == 409 and out.get("fault") == "must_match" and "owner ann" in out["detail"], (st, out)
        st, out = call("POST", "/items", {"name": "t-door", "tag": "t1"})                 # `unique`: the rows too
        assert st == 409 and out.get("fault") == "unique" and "bin a" in out["detail"], (st, out)
    ctl.create({"name": "c", "owner": "bob", "home": "b9"})               # not declared: binds nothing
    from w2cplatform.variables import Garbled
    real = vars_.get
    vars_.get = lambda k, *a, **kw: (_ for _ in ()).throw(Garbled(k, "torn")) if k == "bin/bays/b3" else real(k, *a, **kw)
    _refused(lambda: ctl.create({"name": "d", "owner": "ann", "home": "b3"}), "whose row does not parse")
    from w2cplatform.console import refused_status as _st
    from w2cplatform.spec import RefGarbled
    try:                                                                 # the rows standing: 409, `garbled` (ADR 0031)
        ctl.create({"name": "d", "owner": "ann", "home": "b3"})
    except RefGarbled as e:
        assert _st(e) == 409 and e.fault == "garbled" and "mend it first" in str(e)
    vars_.get = real
    _refused(lambda: ctl.create({"name": "t", "tag": "t1"}), "bin a has that tag already")
    _refused(lambda: ctl.create({"name": "u", "addr": "X://H/part/./1"}), "bin a has that addr already")
    ctl.create({"name": "v", "addr": "x://h/part/01"})                   # another spelling to the platform
    ctl.update("a", {"tag": "t1", "owner": "ann"})                        # the same value: nothing new, nothing asked


def test_a_strict_row_binds_its_units_to_its_place_and_a_place_that_admits_nobody_takes_none():
    """`affinity`: a unit homed on a `strict` bay (kind reserve, enabled) goes to the worker whose bay it is, on the
    server the row names, and nowhere else; that bay takes no unit homed elsewhere; a bay saying `admits: false` takes
    nobody; a bay that is not strict is a preference, not a filter. And `group_by.cut_at`: units whose address differs
    only after `/part/` are one group."""
    vars_, objects, wall = _box()
    spec = SubsystemSpec.from_dict(BIN)
    ctl = SpecController(spec, vars_, objects, wall=wall)
    vars_.put("bin/bays/plain", {"kind": "plain", "server": "s1"})
    vars_.put("bin/bays/res", {"kind": "reserve", "enabled": "true", "server": "s2"})
    vars_.put("bin/bays/none", {"kind": "plain", "admits": "false"})
    for w, s, b in (("w-1", "s1", "plain"), ("w-2", "s2", "res"), ("w-3", "s3", "none")):
        _worker(objects, wall, spec, w, s, b)
    pool = ["w-1", "w-2", "w-3"]
    assert ctl.eligible({"id": "a"}, pool) == ["w-1"]                     # not homed: not on the strict bay, not on `none`
    assert ctl.eligible({"id": "b", "home": "res"}, pool) == ["w-2"]      # homed on the strict bay: there or nowhere
    assert ctl.eligible({"id": "c", "home": "plain"}, pool) == ["w-1"]    # a plain home filters nothing (`home` prefers)
    vars_.put("bin/bays/res", {"kind": "reserve", "enabled": "true", "server": "s9"})
    assert ctl.eligible({"id": "b", "home": "res"}, pool) == []           # the row's server is not the worker's
    vars_.put("bin/bays/res", {"kind": "reserve", "enabled": "false", "server": "s2"})
    assert ctl.eligible({"id": "b", "home": "res"}, pool) == ["w-1", "w-2"]   # not strict now: a preference again
    assert ctl.group_value({"addr": "x://H/n/part/1"}) == ctl.group_value({"addr": "x://h/n/part/2"}) == "x://h/n"


def test_of_several_followed_units_the_one_the_spec_prefers_is_stood_beside():
    """`near.prefer`: two bins hold units of owner `ann`; the pick follows the one whose home bay is a reserve — read
    through the bin spec's `home: {ref: bin/bays}` — and the other only when none is. Ties by their id."""
    vars_, objects, wall = _box()
    bins, picks = SubsystemSpec.from_dict(BIN), SubsystemSpec.from_dict(PICK)
    catalog.register(bins)                                                # their spec is the catalogue's
    vars_.put("bin/bays/plain", {"kind": "plain"})
    vars_.put("bin/bays/res", {"kind": "reserve", "enabled": "true"})
    vars_.put("bin/items/a1", {"name": "a1", "owner": "ann", "home": "plain"})
    vars_.put("bin/items/a2", {"name": "a2", "owner": "ann", "home": "res"})
    _worker(objects, wall, bins, "w-1", "s1", "plain", [{"id": "a1", "owner": "ann", "phase": "running"}])
    _worker(objects, wall, bins, "w-2", "s2", "res", [{"id": "a2", "owner": "ann", "phase": "running"}])
    ctl = SpecController(picks, vars_, objects, wall=wall)
    assert ctl.holder_near("ann") == ("w-2", "s2")                        # beside the reserve, not the smaller id
    vars_.put("bin/items/a2", {"name": "a2", "owner": "ann", "home": "plain"})
    assert ctl.holder_near("ann") == ("w-1", "s1")                        # none preferred: the smaller id


def test_a_subsystems_own_numbers_are_declared_and_the_console_prints_them_from_the_store_and_the_heartbeats():
    """`metrics:` (it was a function of the subsystem's the console called, `metrics_extra`): a count of a table's rows
    — matching, unheld, nothing while another table has a row — and a field of the heartbeats or of each status entry:
    its value, a flag, an age, a label, a count by value (or, with `equals`, one line: the running gauge, which
    `console.running` only names), a sum or max over the workers by a wildcard's keys, a histogram. A word where a number
    goes is 0, never the page's end. The places a worker holds (`placement.places`) make the platform's
    `<sub>_workers_needed` for a subsystem placed by its rows. And `/spec` carries `display`, `servers.show` and the
    gauges' names, which the platform reads none of."""
    from w2cplatform.console import SpecConsole
    from w2cplatform.metrics import text
    vars_, objects, wall = _box()
    spec = SubsystemSpec.from_dict({**BIN, "placement": {**BIN["placement"], "places": {"table": "bays", "where": {"enabled": True}}},
        "console": {"running": "units_running"}, "metrics": [
        {"name": "units_running", "from": "status.phase", "agg": "count", "equals": "running", "live": True},
        {"name": "bays_open", "count": "table bays", "where": {"enabled": True}, "unheld": True},
        {"name": "unguarded", "count": "table bays", "unless": {"table": "bays", "where": {"kind": "guard"}}},
        {"name": "jam", "from": "heartbeat.jam", "agg": "flag", "default": 0},
        {"name": "away_seconds", "from": "heartbeat.away_since", "agg": "age", "default": 0},
        {"name": "belt", "from": "heartbeat.belt.state", "agg": "label", "label": "state", "default": "ok"},
        {"name": "moves_total", "from": "heartbeat.moves.<outcome>", "agg": "sum", "type": "counter"},
        {"name": "items", "from": "status.phase", "agg": "count"},
        {"name": "depth", "from": "status.depth"},
        {"name": "wait_seconds", "from": "heartbeat.wait", "agg": "histogram", "buckets": [1, 5]}],
        "display": {"unit": "ящик", "tree": {"group_by": "owner", "nested_by": "/"}},
        "servers": {"show": [{"table": "bays", "by": "server", "title": "места"}]}})
    ctl = SpecController(spec, vars_, objects, wall=wall)
    vars_.put("bin/bays/b1", {"enabled": "true"})
    vars_.put("bin/bays/b2", {"enabled": "true"})
    vars_.put("bin/bays/b3", {"enabled": "false"})
    objects.put(spec.sub.heartbeat_key("w-1"), Heartbeat("w-1", wall(), [{"id": "a", "phase": "running", "depth": 3},
                                                                        {"id": "b", "phase": "pending", "depth": "deep"}],
                                                         {"server": "s1", "bay": "", "jam": "stuck", "away_since": wall() - 30,
                                                          "belt": {}, "moves": {"done": 2, "failed": 1},
                                                          "wait": {"buckets": [1, 2], "count": 3, "sum": 7.5}}).to_bytes())
    objects.put(spec.sub.heartbeat_key("w-2"), Heartbeat("w-2", wall(), [], {"server": "s2", "bay": "b1", "belt": {"state": "slow"},
                                                                          "moves": {"done": 5}}).to_bytes())
    lines = text(ctl).splitlines()
    for want in ("bin_units_running 1", "bin_bays_open 2", "bin_unguarded 3",
                 'bin_jam{worker="w-1"} 1', 'bin_jam{worker="w-2"} 0',
                 'bin_away_seconds{worker="w-1"} 30', 'bin_away_seconds{worker="w-2"} 0',
                 'bin_belt{worker="w-1",state="ok"} 1', 'bin_belt{worker="w-2",state="slow"} 1',
                 'bin_moves_total{outcome="done"} 7', 'bin_moves_total{outcome="failed"} 1',
                 'bin_items{worker="w-1",phase="pending"} 1', 'bin_items{worker="w-1",phase="running"} 1',
                 'bin_depth{unit="a"} 3', 'bin_depth{unit="b"} 0',
                 '# TYPE bin_wait_seconds histogram', 'bin_wait_seconds_bucket{worker="w-1",le="1"} 1',
                 'bin_wait_seconds_bucket{worker="w-1",le="+Inf"} 3', 'bin_wait_seconds_sum{worker="w-1"} 7.5'):
        assert want in lines, (want, lines)
    vars_.put("bin/bays/g", {"kind": "guard"})
    assert "bin_unguarded 0" in text(ctl).splitlines()
    got = SpecConsole(ctl, wall=wall).describe()
    assert got["display"]["unit"] == "ящик" and got["servers"] == {"show": [{"table": "bays", "by": "server", "title": "места"}]}
    assert got["running_gauge"] == "bin_units_running" and got["workers_gauge"] == "bin_workers_live"
    page = SpecConsole(ctl, wall=wall).metrics_text().splitlines()
    assert 'bin_workers_needed{labels=""} 1' in page and page.count("bin_units_running 1") == 1   # two bays free, w-1 takes one
    assert SubsystemSpec.from_dict(BIN).running_gauge == "" and SpecConsole(SpecController(SubsystemSpec.from_dict(BIN), vars_,
                                                                                        objects, wall=wall)).describe()["running_gauge"] is None
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "console": {"running": "nope"}}), "console.running names one of its metrics")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "metrics": [{"name": "x", "count": "table bays", "minus": "placeless"}]}),
             "minus is no key of a metric")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "placement": {**CAP, "places": {"table": "bays"}}}), "placement.places is")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "metrics": [{"name": "x", "count": "table nope"}]}), "count is `table")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "display": {"logic": "if"}}), "words for a page, no logic")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "servers": {"show": [{"table": "nope", "by": "server"}]}}), "`servers:` is")


def test_a_label_with_values_writes_a_word_of_the_set_and_counts_a_word_outside_it_garbled():
    """ADR-0063: `values: [...]` of an `agg: label` is the closed set of words the field says. A word of it is a series
    (the default where nothing is said, too); a word outside it is a garbled field — no series, counted once a spell in
    `FIELDS` like a word where a number goes, under a key of its own (`servers.status` reads the same leaf as a string
    and must not undo the count), and counted again only after it was a word of the set. A status entry's field too.
    The loader refuses `values` on another agg, not a list, empty, a word twice, an item that is no label word, and a
    `default` outside the set (ADR 0012)."""
    from w2cplatform.metrics import text
    from w2cplatform.rows import FIELDS
    belt = {"name": "belt", "from": "heartbeat.belt.state", "agg": "label", "label": "state", "default": "ok",
            "values": ["ok", "slow", "true"]}
    spec = SubsystemSpec.from_dict({**BIN, "servers": {"status": [{"field": "belt.state", "title": "лента"}]},
                                    "metrics": [belt, {"name": "lane", "from": "status.lane", "agg": "label",
                                                       "values": ["fast", "slow"]}]})
    vars_, objects, wall = _box()
    ctl = SpecController(spec, vars_, objects, wall=wall)
    hb = lambda w, extra, status=(): objects.put(spec.sub.heartbeat_key(w), Heartbeat(w, wall(), list(status), {
        "server": "s1", "bay": "", **extra}).to_bytes())
    hb("l-1", {"belt": {"state": "slow"}}, [{"id": "a", "lane": "fast"}, {"id": "b", "lane": "sideways"}])
    hb("l-2", {"belt": {}})                                                     # not said: the default, a word of the set
    hb("l-3", {"belt": {"state": "jammed"}})                                    # a word outside the set
    hb("l-4", {"belt": {"state": True}})                                        # `true` compared as the word it prints
    key = lambda w, f: f"{spec.sub.heartbeat_key(w)}#{f}"
    before = FIELDS.counts.get("bin", 0)
    lines = text(ctl).splitlines()
    for want in ('bin_belt{worker="l-1",state="slow"} 1', 'bin_belt{worker="l-2",state="ok"} 1',
                 'bin_belt{worker="l-4",state="true"} 1', 'bin_lane{unit="a",value="fast"} 1'):
        assert want in lines, (want, lines)
    assert not [l for l in lines if 'worker="l-3"' in l or 'unit="b"' in l], lines
    assert {key("l-3", "belt.state@belt"), key("l-1", "b.lane@lane")} <= FIELDS.bad
    assert not {key(w, "belt.state@belt") for w in ("l-1", "l-2", "l-4")} & FIELDS.bad
    assert FIELDS.counts.get("bin", 0) - before == 2
    # read again, and through `servers.status` (the same leaf, a string it shows): the same spell, not counted again —
    # `servers.status` counts only what it cannot show itself (`l-4`'s `true`, its own reading, ADR 0012), once
    from w2cplatform.console import SpecConsole
    rows = {w["worker"]: w["status"] for s in SpecConsole(ctl, wall=wall).servers()["servers"].values()
            for w in s["workers"]}
    assert rows["l-3"] == {"belt.state": "jammed"} and rows["l-4"] == {}, rows
    assert key("l-4", "belt.state") in FIELDS.bad and key("l-3", "belt.state") not in FIELDS.bad
    text(ctl)
    assert FIELDS.counts.get("bin", 0) - before == 3 and key("l-3", "belt.state@belt") in FIELDS.bad
    hb("l-3", {"belt": {"state": "ok"}})                                       # a word of the set again: the spell ends…
    assert 'bin_belt{worker="l-3",state="ok"} 1' in text(ctl).splitlines() and key("l-3", "belt.state@belt") not in FIELDS.bad
    hb("l-3", {"belt": {"state": "jammed"}})                                   # …and a new one is counted
    text(ctl)
    assert FIELDS.counts.get("bin", 0) - before == 4

    def metric(**m):
        return lambda: SubsystemSpec.from_dict({**BIN, "metrics": [{"name": "x", "from": "heartbeat.x", **m}]})
    _refused(metric(agg="label", default="stuck", values=["ok", "slow"]), "default 'stuck' is none of values (ok, slow)")
    _refused(metric(agg="flag", values=["ok"]), "`values` closes the words of `agg: label`, not of agg 'flag'")
    _refused(metric(values=["ok"]), "`values` closes the words of `agg: label`, not of agg 'value'")   # agg left out
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "metrics": [{"name": "x", "count": "table bays", "values": ["ok"]}]}),
             "`values` closes the words of `agg: label`, not of a count")                 # a row count says no words
    _refused(metric(agg="label", values=[]), "values is a list of words")
    _refused(metric(agg="label", values="ok"), "values is a list of words")
    _refused(metric(agg="label", values=["ok", "slow", "ok"]), "values says 'ok' twice")
    for bad in ("zone 1", "", "-ok", "склад", "a,b", True, 1, None, ["ok"], "x" * 65):
        _refused(metric(agg="label", values=["ok", bad]), "values is a list of words")
    assert SubsystemSpec.from_dict({**BIN, "metrics": [{"name": "x", "from": "heartbeat.x", "agg": "label",
                                                        "values": ["ok", "vlan:cctv-a", "site.b"]}]}).metrics[0]["values"] \
        == {"ok", "vlan:cctv-a", "site.b"}                                     # a label's alphabet; no default: no check


def test_a_metric_number_is_printed_by_its_value_and_not_by_how_the_heartbeat_spelled_it():
    """ADR 0055: a number on `/metrics` by its value, on both sides — a whole value whole (`61` whether the heartbeat
    wrote `61` or `61.0`, an age `10`), any other the shortest text that reads back as it, an exponent where Go's
    shortest `%g` writes one; one rule for a sample, a bucket's `le` and a word `equals` compares. The table is the
    product's `sampleText_internal_test.go`, to the letter."""
    from w2cplatform.metrics import text, value_text
    for n, want in {61: "61", 61.0: "61", -3: "-3", 0: "0", -0.0: "0", 10.0: "10", 7.5: "7.5", 0.1: "0.1", 10.25: "10.25",
                    1e21: "1e+21", 1e-7: "1e-07", 1234567.5: "1.2345675e+06", 1e6: "1000000", 1e15: "1e+15",
                    0.0001: "0.0001", float("inf"): "+Inf"}.items():
        assert value_text(n) == want, (n, value_text(n), want)
    vars_, objects, wall = _box()
    spec = SubsystemSpec.from_dict({**BIN, "metrics": [
        {"name": "depth", "from": "heartbeat.depth"},
        {"name": "level_hit", "from": "heartbeat.level", "agg": "flag", "equals": [1]},
        {"name": "moves_total", "from": "heartbeat.moves", "agg": "sum", "type": "counter"},
        {"name": "wait_seconds", "from": "heartbeat.wait", "agg": "histogram", "buckets": [0.5, 1.0, 1e6]}]})
    ctl = SpecController(spec, vars_, objects, wall=wall)
    for w, said in (("w-1", 61), ("w-2", 61.0)):
        objects.put(spec.sub.heartbeat_key(w), Heartbeat(w, wall(), [], {"server": "s1", "depth": said, "level": said / 61,
                                                                         "moves": said, "wait": {"buckets": [0, 1, 2],
                                                                                                 "count": 2, "sum": 2.0}}).to_bytes())
    lines = text(ctl).splitlines()
    for want in ('bin_depth{worker="w-1"} 61', 'bin_depth{worker="w-2"} 61',
                 'bin_level_hit{worker="w-1"} 1', 'bin_level_hit{worker="w-2"} 1', "bin_moves_total 122",
                 'bin_wait_seconds_bucket{worker="w-1",le="0.5"} 0', 'bin_wait_seconds_bucket{worker="w-1",le="1"} 1',
                 'bin_wait_seconds_bucket{worker="w-1",le="1000000"} 2', 'bin_wait_seconds_sum{worker="w-1"} 2'):
        assert want in lines, (want, lines)

def test_what_a_table_holds_is_kept_past_its_days_for_the_unit_and_every_unit_about_it():
    """`holds:` (it was a subsystem's function the resource called, `kept`): a row of the spec's table holds its unit's
    buckets — and those of every unit about it, read through that unit's spec's `about` — for its stretch, at most
    `longest` from its start; a row whose bounds do not read holds its unit as far as they read; a unit whose row does
    not read, or names nobody, is held by every hold that reads; another unit's buckets go by their days."""
    from w2cplatform.events import EventLog, bucket_names_under
    from w2cplatform.resource import platform_resource
    vars_, objects, wall = _box()
    root = tempfile.mkdtemp(prefix="held-")
    owner = SubsystemSpec.from_dict({"name": "shelf", "unit": {"rows": "items", "id": "name",
                                                              "fields": {"name": {"type": "string"}}},
                                     "tables": ["pins"], "placement": CAP,
                                     "holds": {"table": "pins", "unit": "item", "since": "a", "until": "b", "longest": 3600}})
    about = SubsystemSpec.from_dict({"name": "label", "about": {"sub": "shelf", "field": "item"},
                                     "unit": {"rows": "tags", "id": "name", "fields": {"name": {"type": "string"},
                                                                                      "item": {"type": "string", "fixed": True}}},
                                     "placement": CAP})
    old = wall() - 40 * 86400
    for sub, unit in (("shelf", "1"), ("shelf", "2"), ("label", "t1"), ("label", "t2"), ("label", "torn")):
        EventLog(root, sub, unit, 1).append(old + 10, "seen")
        EventLog(root, sub, unit, 1).append(old + 7200, "seen")                   # past `longest` from the pin's start
        vars_.put(f"{sub}/retention/{unit}", {"days": "30"})
    vars_.put("label/tags/t1", {"name": "t1", "item": "1"})
    vars_.put("label/tags/t2", {"name": "t2", "item": "2"})
    vars_.put("shelf/pins/p", {"item": "1", "a": str(old), "b": str(old + 86400)})
    vars_.put("shelf/pins/q", {"item": "2", "a": "soon", "b": str(old + 60)})     # its start lost: from the start of time
    real = vars_.get
    vars_.get = lambda k, *a, **kw: (_ for _ in ()).throw(ValueError("torn")) if k == "label/tags/torn" else real(k, *a, **kw)
    res = platform_resource(root, "s1", "http://s1", vars_, objects, wall=wall, specs=[owner, about])
    res.retain()
    left = lambda sub, unit: len(bucket_names_under(root, sub, unit, 600))
    assert (left("shelf", "1"), left("label", "t1")) == (1, 1)            # the pin's hour: the unit and the unit about it
    assert (left("shelf", "2"), left("label", "t2")) == (1, 1)            # as far as it reads: up to its end
    assert left("label", "torn") == 1                                     # nobody can say whose: the sound pin holds it
    vars_.get = real
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "holds": {"table": "nope", "unit": "u", "since": "a", "until": "b"}}),
             "`holds:` is")


def test_a_hold_let_go_by_its_released_field_holds_nothing_and_the_field_is_the_tables():
    """`holds.released` (ADR-0057, the addendum of 2026-10-10; the review's fifteenth pass, minor 4): a row whose named
    field is not empty holds nothing — no bucket, no event; one where it is empty holds as before. The field is one of
    `tables.<table>.fields`: another name, or a table only named, is refused at load, under `holds.released`."""
    from w2cplatform import holds
    vars_, _, wall = _box()
    pins = {"key": "{item}-{a:int}", "fields": {"item": {"type": "string", "required": True}, "a": {"type": "float"},
                                               "b": {"type": "float"}, "gone": {"type": "string"}}}
    shelf = {"name": "shelf", "unit": {"rows": "items", "id": "name", "fields": {"name": {"type": "string"}}},
             "tables": {"pins": pins}, "placement": CAP}
    spec = SubsystemSpec.from_dict({**shelf, "holds": {"table": "pins", "unit": "item", "since": "a", "until": "b",
                                                       "released": "gone"}})
    assert spec.holds["released"] == "gone"
    t = wall() - 86400
    vars_.put("shelf/pins/p", {"item": "1", "a": str(t), "b": str(t + 600)})
    vars_.put("shelf/pins/q", {"item": "2", "a": str(t), "b": str(t + 600), "gone": str(t + 60)})
    held = holds.kept(vars_, [spec])
    assert held("shelf", "1", t + 10, t + 20)                             # stands: holds its stretch
    assert not held("shelf", "2", t + 10, t + 20)                         # let go: holds nothing
    vars_.put("shelf/pins/p", {"item": "1", "a": str(t), "b": str(t + 600), "gone": str(t + 90)})
    assert not holds.kept(vars_, [spec])("shelf", "1", t + 10, t + 20)    # …and nothing is held at all
    _refused(lambda: SubsystemSpec.from_dict({**shelf, "holds": {"table": "pins", "unit": "item", "since": "a",
                                                                 "until": "b", "released": "gonne"}}), "holds.released")
    _refused(lambda: SubsystemSpec.from_dict({**shelf, "tables": ["pins"], "holds": {"table": "pins", "unit": "item",
                                                                                     "since": "a", "until": "b",
                                                                                     "released": "gone"}}),
             "holds.released")
    _refused(lambda: SubsystemSpec.from_dict({**shelf, "holds": {"table": "pins", "unit": "item", "since": "a",
                                                                 "until": "b", "released": ""}}), "holds.released")

def test_the_resource_asks_a_subsystem_that_frees_by_a_request_row_and_reads_its_answer():
    """`requests: {free: true}` (it was a subsystem's hook the resource called, `free`): over the high mark the resource
    writes `<sub>/requests/free-<server>-<volume> {free, volume, server}` and reads what the subsystem's live workers
    on its server say they are still freeing (`freeing` in their heartbeats); back under the mark, the row is taken away. Nothing of
    the subsystem's runs in the resource."""
    from w2cplatform.resource import SPACE_KEY, Resource
    vars_, objects, wall = _box()
    spec = SubsystemSpec.from_dict({**BIN, "requests": {"free": True, "ttl": 0}})
    catalog.register(spec)
    full = {"used": 98}
    res = Resource(tempfile.mkdtemp(prefix="full-"), "s1", "http://s1", vars_, objects, wall=wall,
                   space_probe=lambda path: (100, 100 - full["used"]))
    [vol] = list(res.volumes)
    key = spec.sub.request_key(f"free-s1-{vol}")
    vars_.put(SPACE_KEY, {"enabled": "true", "high": "0.9", "low": "0.5"})
    out = res.relieve()
    assert out["space"] == "over" and vars_.get(key)[0]["free"] == "48" and vars_.get(key)[0]["volume"] == vol
    objects.put(spec.sub.heartbeat_key("w-1"), Heartbeat("w-1", wall(), [], {"server": "s1", "bay": "", "freeing": {vol: 40}}).to_bytes())
    out = res.relieve()
    assert out["freeing"] == 40 and out["short"] == 8 and vars_.get(key)[0]["free"] == "8"   # what is left, asked again
    full["used"] = 10
    assert res.relieve()["space"] == "ok" and vars_.get(key)[0] is None                # under the mark: nothing asked


def test_a_fields_shape_is_a_json_schema_in_the_spec_and_the_door_says_where_it_does_not_fit():
    """The owner's decision 3 of the boundary's step 6: what a field may BE is JSON Schema in the spec (`schema.py`),
    checked at the door for every writer — a json field's document, an int's number — in the schema's words, naming
    the place: it was a controller of one subsystem's own. A schema with a word the platform does not read does not
    load: a typo is not a rule that silently holds nothing."""
    from w2cplatform.schema import Invalid, check, load
    vars_, objects, wall = _box()
    spec = SubsystemSpec.from_dict({"name": "plan", "placement": CAP, "unit": {"rows": "plans", "id": "name", "fields": {
        "name": {"type": "string", "required": True},
        "steps": {"type": "json", "required": True, "schema": {
            "type": "array", "minItems": 1, "maxItems": 2,
            "items": {"type": "object", "required": ["op"], "additionalProperties": False,
                      "properties": {"op": {"enum": ["lift", "drop"]}, "n": {"type": "integer", "minimum": 1}},
                      "if": {"properties": {"op": {"const": "lift"}}}, "then": {"required": ["n"]}}}},
        "every": {"type": "int", "default": 0, "schema": {"anyOf": [{"const": 0}, {"minimum": 5, "maximum": 60}]}}}}})
    ctl = SpecController(spec, vars_, objects, wall=wall)
    ctl.create({"name": "a", "steps": [{"op": "lift", "n": 2}, {"op": "drop"}]})
    for steps, every, words in (([], 0, "steps has at least 1 entry"),
                                ([{"op": "spin"}], 0, "steps[0].op is one of 'lift', 'drop', not 'spin'"),
                                ([{"op": "lift"}], 0, "steps[0] needs 'n'"),
                                ([{"op": "drop", "x": 1}], 0, "steps[0] has no key 'x' — it takes n, op"),
                                ([{"op": "drop"}], 3, "every fits none of what it may be")):
        _refused(lambda: ctl.create({"name": "b", "steps": steps, "every": every}), words)
    _refused(lambda: ctl.update("a", {"steps": [{"op": "lift", "n": 0}]}), "steps[0].n is at least 1, not 0")
    assert check(True, {"anything": 1}) is None
    try:
        check({"type": "integer"}, True)
        raise AssertionError("true is not an integer")
    except Invalid as e:
        assert "is integer, not boolean" in str(e)
    _refused(lambda: load({"type": "array", "itmes": {}}, "x"), "itmes — not a keyword the platform reads")
    _refused(lambda: load({"type": "list"}, "x"), "type 'list' is none of")


SHED = {"name": "shed", "placement": {**CAP, "group_by": {"field": "addr", "cut_at": "part"}},   # `reach.group` asks one
        "unit": {"rows": "tools", "id": "name",
                 "fields": {"name": {"type": "string", "required": True},
                            "addr": {"type": "url"}, "tag": {"type": "string"}, "labels": {"type": "list"}}},
        "tables": {"racks": {"key": "{owner}-{slot:int}",
                             "fields": {"owner": {"type": "string", "required": True},
                                        "slot": {"type": "int", "required": True, "schema": {"minimum": 1}},
                                        "size": {"type": "int", "default": 1},
                                        "note": {"type": "string", "schema": {"maxLength": 20}}},
                             "schema": {"if": {"properties": {"size": {"minimum": 10}}}, "then": {"required": ["note"]}},
                             "stamp": ["by", "at"],
                             "journal": {"written": "rack.set", "deleted": "rack.gone"}}},
        "requests": {"schema": {"type": "object", "required": ["unit", "action"], "additionalProperties": False,
                                "properties": {"unit": {"type": "string"}, "action": {"enum": ["poke"]},
                                               "valid_until": {"type": "number"}}},
                     "valid_for": 20, "most_valid": 60, "stamp": ["by", "group"]},
        "rights": {"reach": {"group": ["addr"], "cluster": ["tag"], "requests": ["poke"]}}}


def _shed():
    d = dict(SHED)
    d["placement"] = {**CAP, "group_by": {"field": "addr", "cut_at": "part"}}
    return SubsystemSpec.from_dict(d)


def test_a_declared_table_is_written_listed_and_deleted_by_the_console_and_each_write_is_a_line():
    """`tables: {racks: {key, fields, schema, stamp, journal}}`: `POST /racks` names the row by its key template, takes
    the fields' types and words and the row's own schema, stamps who and when; the same key again is the same row,
    and the journal says what that write changed and from what; `GET /racks` lists every row, one that does not parse
    said as one; `DELETE /racks/<name>`."""
    from w2cplatform.console import SpecConsole
    from w2cplatform.eventdatabase import EventIndex
    from w2cplatform.variables import Garbled
    from tests.conftest import Served
    vars_, objects, wall = _box()
    spec = _shed()
    assert "shed/racks/*" in spec.acl_console()
    ctl = SpecController(spec, vars_, objects, wall=wall)
    marks = tempfile.mkdtemp(prefix="marks-")
    with Served(SpecConsole(ctl, marks_root=marks, wall=wall)) as call:
        st, made = call("POST", "/racks", {"owner": "ann", "slot": 2}, headers={"X-User": "ann"})
        assert st == 201 and made["row"]["name"] == "ann-2" and (made["row"]["by"], made["row"]["at"]) == ("ann", wall())
        for bad, words in (({"slot": 2}, "needs owner"), ({"owner": "ann", "slot": 0}, "slot is at least 1"),
                           ({"owner": "ann", "slot": 3, "size": 12}, "needs 'note'"),
                           ({"owner": "ann", "slot": "two"}, "slot is int"), ({"owner": "a/b", "slot": 1}, ""),
                           ({"owner": "ann", "slot": 3, "colour": "red"}, "")):
            st, body = call("POST", "/racks", bad)
            assert st == 400 and words in body["detail"], (bad, body)
        st, again = call("POST", "/racks", {"owner": "ann", "slot": 2, "size": 12, "note": "the big one"}, headers={"X-User": "bob"})
        assert st == 201 and again["row"]["by"] == "bob" and again["row"]["size"] == 12
        vars_.put("shed/racks/zed-1", {"owner": "zed", "slot": "1"})
        real = vars_.get
        vars_.get = lambda k, *a, **kw: (_ for _ in ()).throw(Garbled(k, "torn")) if k == "shed/racks/zed-1" else real(k, *a, **kw)
        try:
            st, view = call("GET", "/racks")
        finally:
            vars_.get = real
        assert st == 200 and [r["name"] for r in view["racks"]] == ["ann-2", "zed-1"] and view["racks"][1] == {"name": "zed-1", "garbled": True}
        assert call("DELETE", "/racks/ann-2")[0] == 200 and call("DELETE", "/racks/ann-2")[0] == 404
    lines = [e for e in EventIndex(marks, "", wall=wall).query(0, wall() + 1, subsystem="audit")["events"] if e["kind"].startswith("rack.")]
    assert [(e["kind"], e["user"]) for e in lines] == [("rack.set", "ann"), ("rack.set", "bob"), ("rack.gone", "operator")]
    assert "changed" not in lines[0] and lines[1]["changed"] == "size,note" and lines[1]["was"] == {"size": 1}
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "tables": {"racks": {"key": "{x}", "fields": {}, "colour": 1}}}),
             "tables.racks is {key, fields, schema, stamp, journal}")


def test_a_table_or_rows_named_like_a_route_of_the_console_is_refused_at_load_and_the_routes_are_the_dispatchs():
    """A table named `marks` was never written over HTTP: `POST /marks` is the operator's mark, answered before a
    spec's tables are looked at (503 «no resource…» on a mount). The console's own routes are a closed set
    (`spec.CONSOLE_ROUTES`): a spec whose rows or a declared table is one of them does not load, and says which and
    why — a table only named (`tables: [metrics]`) is served by nobody and collides with nothing; and the set is the first segments the console's dispatch answers itself, every one of
    them, read from its code."""
    import re
    from w2cplatform import console, spec as spec_mod
    for route in sorted(spec_mod.CONSOLE_ROUTES):
        _refused(lambda: SubsystemSpec.from_dict({**SHED, "tables": {route: {"key": "{x}", "fields": {"x": {"type": "string"}}}}}),
                 f"tables.{route} is {route!r}, a route the console answers itself")
        _refused(lambda: SubsystemSpec.from_dict({**SHED, "unit": {**SHED["unit"], "rows": route}}),
                 f"unit.rows is {route!r}, a route the console answers itself")
    assert SubsystemSpec.from_dict({**SHED, "tables": {"notches": SHED["tables"]["racks"]}}).table_specs
    assert SubsystemSpec.from_dict({**SHED, "tables": ["metrics"]}).tables == ("metrics",)
    # the set is the dispatch's: every literal first segment `SpecConsole.dispatch`, `_declared` and `Mount` compare a
    # path with is in it, and nothing else is
    src = open(console.__file__, encoding="utf-8").read()
    start = src.index("    def _declared(")
    code = src[start:src.index("    # `/<table>[/<name>]`", start)]
    start = src.index("    def dispatch(self, h, method: str, path: str, q: dict)")
    code += src[start:src.index("    # Starts the server in a daemon thread", start)]
    start = src.index("            def _route(self, method):")
    code += src[start:src.index("            def _answered(self, method):", start)]
    said = set(re.findall(r'(?<!endswith\()"/([a-z][a-z.]*)', code))           # `"/spec"`, `"/where/"`, `"/domain/shared/"`
    said |= set(re.findall(r'segs\[1\] == "([a-z]+)"', src))                  # `place_path`: `/where/<table>/<name>`
    said |= {r.strip("/").split("/")[0] for r in (*console.Mount.MOUNT_ROUTES, *console.RESERVE_ROUTES, *console.MONITOR_ROUTES,
                                                  *console.MODULE_ROUTES)}   # `/session/break-glass`, `/platform/console.js`
    assert said == set(spec_mod.CONSOLE_ROUTES), (sorted(said - spec_mod.CONSOLE_ROUTES), sorted(spec_mod.CONSOLE_ROUTES - said))


def test_a_request_is_a_row_named_by_its_key_stamped_with_its_group_and_held_to_its_schema_and_deadline():
    """`requests:`: `POST /requests {unit: <sub>/<id>, …}` is a row of `<sub>/requests/` for whoever holds the unit, its
    body held to the spec's schema, its deadline `valid_for` from now unless it says one no further than `most_valid`;
    the `Idempotency-Key` names it, so a retry is the same row; it carries who asked and the group its rights were
    asked on. A request for no unit is 404, a bare id 400."""
    from w2cplatform.console import SpecConsole
    from tests.conftest import Served
    vars_, objects, wall = _box()
    ctl = SpecController(_shed(), vars_, objects, wall=wall)
    ctl.create({"name": "drill", "addr": "x://h/bench/part/3"})
    with Served(SpecConsole(ctl, wall=wall)) as call:
        st, body = call("POST", "/requests", {"unit": "shed/drill", "action": "poke"}, key="p-1", headers={"X-User": "ann"})
        assert st == 202 and body["queued"]["id"] == "p-1" and float(body["queued"]["valid_until"]) == wall() + 20
        row = vars_.get("shed/requests/p-1")[0]
        assert (row["unit"], row["by"], row["group"]) == ("drill", "ann", "x://h/bench")
        again = call("POST", "/requests", {"unit": "shed/drill", "action": "poke"}, key="p-1", headers={"X-User": "ann"})
        assert again[1] == body                                                                      # a retry
        assert call("POST", "/requests", {"unit": "shed/drill", "action": "poke"}, key="p-1")[0] == 422   # another's key
        for bad, code, err in (({"unit": "shed/drill", "action": "spin"}, 400, "refused"),
                               ({"unit": "shed/drill", "action": "poke", "valid_until": wall() + 61}, 400, "too far"),
                               ({"unit": "shed/none", "action": "poke"}, 404, "no such unit"),
                               ({"unit": "drill", "action": "poke"}, 400, "denied")):     # the gate asks first: whose?
            st, out = call("POST", "/requests", bad)
            assert (st, out["error"]) == (code, err), (bad, st, out)
        assert call("POST", "/requests", {"unit": "shed/drill", "action": "poke"}, key=False)[0] == 400
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": -1}}),
             "requests.valid_for is a finite number of seconds above 0")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"stamp": ["colour"]}}), "`requests:` is")


def test_how_long_a_request_stands_is_declared_and_a_spec_that_does_not_say_it_does_not_load():
    """The architect, 2026-10-05 (ADR 0012): no number is assumed. A family that frees says `requests.ttl` — a ledger
    `per_person` reads it too; any other says `requests.valid_for`; a spec without the key it needs is refused, naming
    the path. `ttl: 0` is no limit, said so; a negative one is no time."""
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "requests": {"free": True}}), "requests.ttl is required with `free: true`")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"stamp": ["by"]}}), "requests.valid_for is required")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": 20, "per_person": 3}}),
             "requests.ttl is required with `per_person`")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "requests": {"free": True, "ttl": -1}}),
             "requests.ttl is a finite number of seconds, or 0: no limit")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": 0}}),
             "requests.valid_for is a finite number of seconds above 0")
    assert SubsystemSpec.from_dict({**BIN, "requests": {"free": True, "ttl": 0}}).requests["ttl"] == 0


def test_how_far_a_deadline_may_be_is_declared_with_valid_for_and_the_door_and_the_reaper_read_that_number():
    """ADR 0012, the rule of `ttl` (the architect, 2026-10-05): `most_valid` is required wherever `valid_for` is — the
    door assumed no bound and the reaper ten minutes, two numbers nobody declared. A default deadline past it, and a
    stamp of `about` in a spec that says no `about:`, are refusals naming the path. The door refuses a deadline past
    the declared 90 s, and the reaper ends a row with no deadline 90 s after its filing (and `REAP_AFTER`), not 600."""
    from w2cplatform import requests
    from w2cplatform.console import SpecConsole
    from tests.conftest import Served
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": 20}}),
             "requests.most_valid is required with `valid_for`")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "requests": {"free": True, "ttl": 0, "valid_for": 20}}),
             "requests.most_valid is required with `valid_for`")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": 120, "most_valid": 60}}),
             "requests.valid_for (120) is past requests.most_valid (60)")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": 20, "most_valid": 60, "stamp": ["about"]}}),
             "requests.stamp names `about`, and the spec says no `about:`")
    d = dict(SHED, requests={**SHED["requests"], "most_valid": 90})
    d["placement"] = {**CAP, "group_by": {"field": "addr", "cut_at": "part"}}
    vars_, objects, wall = _box()
    ctl = SpecController(SubsystemSpec.from_dict(d), vars_, objects, wall=wall)
    ctl.create({"name": "drill", "addr": "x://h/bench/part/3"})
    with Served(SpecConsole(ctl, wall=wall)) as call:
        for ahead, code in ((89, 202), (91, 400)):
            st, out = call("POST", "/requests", {"unit": "shed/drill", "action": "poke", "valid_until": wall() + ahead})
            assert st == code and (code == 202 or out["detail"] == "a request's `valid_until` is at most 90 s away"), (ahead, out)
    start = wall.t
    vars_.put("shed/requests/bare", {"unit": "drill", "action": "poke", "at": str(start)})     # filed with no deadline
    wall.t = start + 90 + requests.REAP_AFTER - 1
    requests.clear_requests(ctl)
    assert vars_.get("shed/requests/bare")[0] is not None
    wall.t = start + 90 + requests.REAP_AFTER + 1
    requests.clear_requests(ctl)
    assert vars_.get("shed/requests/bare")[0] is None and not hasattr(requests, "MOST_VALID")


def _asks(ttl):
    from w2cplatform.console import SpecConsole
    spec = SubsystemSpec.from_dict({**BIN, "requests": {
        "free": True, "ttl": ttl, "per_person": 1, "settle": 10, "stamp": ["at"],
        "schema": {"type": "object", "required": ["unit"], "properties": {"unit": {"type": "string"}}}}})
    vars_, objects, wall = _box()
    ctl = SpecController(spec, vars_, objects, wall=wall)
    ctl.create({"name": "a"})
    return ctl, SpecConsole(ctl, wall=wall), wall


def test_the_ledger_and_the_reaper_both_end_a_request_at_the_declared_ttl_and_ttl_0_ends_none_by_age():
    """One key, read by both: a person's ledger forgets an id older than `ttl` though its row stands, and the reaper ends
    that row; `ttl: 0` — no limit — keeps both, a day or a year on (the ledger assumed a day, the reaper nothing)."""
    from w2cplatform import requests
    from tests.conftest import Served
    for ttl, later, forgets in ((100, 101, True), (0, 365 * 86400, False)):
        ctl, con, wall = _asks(ttl)
        start = wall.t
        with Served(con) as call:
            # an action and no deadline: the reaper's `most_valid` turn is for a family of deadlines, not this one
            assert call("POST", "/requests", {"unit": "bin/a", "action": "x"}, key="r1", headers={"X-User": "ann"})[0] == 202
            wall.t = start + 50
            assert call("POST", "/requests", {"unit": "bin/a"}, key="r2", headers={"X-User": "ann"})[0] == 429
            wall.t = start + later                         # r1's row stands: the ledger reads its own age of it
            assert (call("POST", "/requests", {"unit": "bin/a"}, key="r2", headers={"X-User": "ann"})[0] == 202) == forgets, (ttl, "ledger")
            requests.clear_requests(ctl)
            assert (ctl.vars.get(ctl.spec.sub.request_key("r1"))[0] is None) == forgets, (ttl, "reaper")
            assert ctl.vars.get(ctl.spec.sub.request_key("r2"))[0] or not forgets         # filed just now: not old


def test_what_a_change_or_a_request_reaches_is_the_specs_group_the_cluster_or_the_units_a_row_names():
    """`rights.reach`: a change of a `group` field reaches every other unit of the group it leaves and of the one it
    joins — a group nobody else is in is the cluster's (`*`); a change of a `cluster` field is the cluster's; a request
    of a `requests` action reaches every unit of its unit's group. `rights.names`: the units a row of another subsystem
    names inside a json field answer for a unit that moves; a row that cannot be read names anybody."""
    from w2cplatform.console import SpecConsole, names_in
    vars_, objects, wall = _box()
    shed = SpecController(_shed(), vars_, objects, wall=wall)
    plan_spec = SubsystemSpec.from_dict({"name": "plan", "placement": CAP, "unit": {"rows": "plans", "id": "name", "fields": {
        "name": {"type": "string", "required": True}, "steps": {"type": "json"}}},
        "rights": {"cluster_rows": True, "names": [{"field": "steps", "unit": "tool", "of": "shed"}]}})
    plan = SpecController(plan_spec, vars_, objects, wall=wall)
    for name, addr in (("a", "x://h/bench/part/1"), ("b", "x://h/bench/part/2"), ("c", "x://h/wall/part/1")):
        shed.create({"name": name, "addr": addr})
    plan.create({"name": "p", "steps": [{"tool": "c"}, {"tool": "b"}]})
    con, pcon = SpecConsole(shed, wall=wall), SpecConsole(plan, wall=wall)
    con.units = pcon.units = {"shed": con, "plan": pcon}
    a = shed.unit("a")
    assert con.reach_of_change(a, {**a, "name": "a2"}) == set()                                     # nothing that reaches
    assert con.reach_of_change(a, {**a, "addr": "x://h/bench/part/9"}) == {"shed/b"}                # its group, still
    assert con.reach_of_change(a, {**a, "addr": "x://h/wall/part/2"}) == {"shed/b", "shed/c"}       # left and joined
    assert con.reach_of_change(a, {**a, "addr": "x://h/attic/part/1"}) == {"shed/b", "*"}           # a group of nobody's
    c = shed.unit("c")
    assert con.reach_of_change(c, {**c, "addr": "x://h/bench/part/7"}) == {"shed/a", "shed/b", "shed/c"}   # p names c and b
    assert con.reach_of_change(a, {**a, "tag": "new"}) == {"*"}
    assert con.reach_of_request("/requests", {"unit": "shed/a", "action": "poke"}) == {"shed/a", "shed/b"}
    assert con.reach_of_request("/requests", {"unit": "shed/a", "action": "look"}) == set()
    assert names_in(plan_spec, {"steps": "[{\"tool\": \"c\"}]"}) == {"shed/c"}
    assert names_in(plan_spec, {"steps": "{torn"}) == {"*"} and names_in(plan_spec, {"steps": "[{}]"}) == {"*"}
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "rights": {"reach": {"group": ["nope"]}}}), "rights.reach is")
    # …and two that asked nothing (the product's `reach-names`, «Архитектор» 2026-10-06): `reach.group` with no
    # `placement.group_by` — no group to reach; a name read from a field that is not `json` — "*" hid a typo
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "placement": CAP, "rights": {"reach": {"group": ["addr"]}}}),
             "no placement.group_by")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "rights": {"names": [{"field": "tag", "unit": "tool", "sub": "s"}]}}),
             "reads names from a json field, and tag is string")


def _sealer():
    """A key ring for a test (`SECRETS_KEY`): what a console seals the door key with."""
    from tests.conftest import key_ring
    from w2cplatform.sealing import Sealer
    return Sealer.from_file(key_ring())


def test_a_door_token_opens_one_holders_door_to_one_unit_for_its_routes_until_it_ends():
    """`door.py`: the door key is in the STORE (the product's `door/signer`, `door/keys`): the console makes it the first
    time it is asked — the public half into the ring first, the seed sealed — and signs (`Signer`); the holder checks by
    the ring (`Ring`): this holder, this unit, this route, not past its time (and `SKEW`), a signature that holds; anything
    else is a 401 whose `reason` is one word a page acts on. A rotation signs with a new key and the old half stays. A
    token in a query is masked wherever a path is logged; a page's origin is answered only when it is a console's
    (`DOOR_ORIGINS`). A spec's `door:` is a list of words."""
    from w2cplatform.door import (KEYS_KEY, SIGNER_KEY, DoorRefused, Ring, Signer, cors, masked, origins, parse_routes,
                                  rotate, token_in)
    vars_, objects, wall = _box()
    assert Signer.for_console(vars_, None) is None                            # no key ring to seal one: the open mode
    sealer = _sealer()
    sign, ring = Signer(vars_, sealer), Ring(vars_)
    assert ring.keys() == {}                                                  # nothing made yet: a door that opens to all
    tok, exp = sign.issue("ann", "bin/a", "w-1", ("read",), 1000.0)
    signer, keys = vars_.get(SIGNER_KEY)[0], vars_.get(KEYS_KEY)[0]
    assert set(signer) == {"kid", "seed"} and signer["seed"].startswith("enc:") and list(keys) == [signer["kid"]]
    assert exp == 1000.0 + 120 and Ring(vars_).check(tok, unit="bin/a", holder="w-1", route="read", now=1100.0)["sub"] == "ann"
    ring = Ring(vars_)
    for kw, reason, words in (({"unit": "bin/b"}, "unit", "is for bin/a"), ({"holder": "w-2"}, "holder", "elsewhere"),
                              ({"route": "write"}, "route", "does not open 'write'"), ({"now": 1126.0}, "expired", "expired")):
        args = {"unit": "bin/a", "holder": "w-1", "route": "read", "now": 1100.0, **kw}
        try:
            ring.check(tok, **args); raise AssertionError(kw)
        except DoorRefused as e:
            assert e.status == 401 and e.reason == reason and words in e.why, (kw, e.reason, e.why)
    assert ring.check(tok, unit="bin/a", holder="w-1", route="read", now=1123.0)       # past `exp`, inside `SKEW`
    other_vars = _box()[0]
    other = Signer(other_vars, sealer).issue("ann", "bin/a", "w-1", ("read",), 1000.0)[0]
    for bad, reason in ((None, "token"), ("", "token"), ("x.y", "signature"), (tok[:-3] + "AAA", "signature"),
                        (other, "signature")):                               # none; not one; tampered; another cluster's
        try:
            ring.check(bad, unit="bin/a", holder="w-1", route="read", now=1100.0); raise AssertionError(bad)
        except DoorRefused as e:
            assert e.status == 401 and e.reason == reason, (bad, e.reason)
    old_kid = signer["kid"]
    new_kid = rotate(vars_, sealer)
    assert new_kid != old_kid and set(vars_.get(KEYS_KEY)[0]) == {old_kid, new_kid}   # the old half stays in the ring
    assert Signer(vars_, sealer).issue("ann", "bin/a", "w-1", ("read",), 1000.0)[0].split(".")[1] == new_kid
    assert ring.check(tok, unit="bin/a", holder="w-1", route="read", now=1100.0)        # a token the old key signed: still
    assert token_in({"Authorization": "Bearer abc"}, "/x") == "abc" and token_in({}, "/x?t=def&from=1") == "def"
    assert masked("/read/a?from=1&t=secret&to=2") == "/read/a?from=1&t=***&to=2"
    allowed = origins({"DOOR_ORIGINS": "https://console.example, http://10.0.0.5:8080/"})
    assert allowed == ("https://console.example", "http://10.0.0.5:8080")
    assert cors("https://evil.example", allowed) == [] and ("Access-Control-Allow-Origin", "https://console.example") in cors("https://console.example", allowed)
    assert not any(k == "Access-Control-Allow-Credentials" for k, _ in cors("https://console.example", allowed))
    assert parse_routes("x", {"routes": ["read", "play"]}) == ("read", "play") and parse_routes("x", None) == ()
    for bad in ({"routes": []}, {"routes": ["../x"]}, {"routes": ["read"], "url": "x"}, ["read"]):
        _refused(lambda: parse_routes("spec x", bad), "`door:` is")


def test_a_new_door_key_is_made_in_the_store_by_the_verb_and_the_old_half_stays():
    """`python3 -m w2cplatform.door new` (`door._new`): a new door key in this cluster's store — the seed sealed into
    `door/signer` with the cluster's key ring (`SECRETS_KEY`), its public half added to `door/keys` — so a holder reads
    it there and no unit carries a key file. Without the ring nothing is made, and it says why."""
    import contextlib
    import io
    from tests.conftest import key_ring
    from w2cplatform import host
    from w2cplatform.door import KEYS_KEY, SIGNER_KEY, _new
    env = {"PLATFORM_DIR": tempfile.mkdtemp(prefix="platform-")}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert _new(env) == 2                                         # no key ring: nothing to seal the seed with
    assert "SECRETS_KEY" in out.getvalue()
    env["SECRETS_KEY"] = key_ring()
    with contextlib.redirect_stdout(io.StringIO()):
        assert _new(env) == 0 and _new(env) == 0                      # made, and made again: a rotation
    vars_, _ = host.stores(env)
    signer, keys = vars_.get(SIGNER_KEY)[0], vars_.get(KEYS_KEY)[0]
    assert signer["seed"].startswith("enc:") and len(keys) == 2 and signer["kid"] in keys


def test_where_hands_out_the_holders_door_with_a_token_and_only_the_placed_live_holder_has_one():
    """`GET /where/<id>` for a spec that declares `door: {routes}`: the door the unit's holder announces (`url` in its
    heartbeat, the product's word) — the worker it is PLACED on, live, saying it holds the unit — and a token for those
    routes, this unit, this holder, signed by the door key the console made in the store (none without a key ring to
    seal one: the door's open mode); a line `door.issued` names who got it. Nobody holding the unit so: `door: null`. A
    spec with no `door:` says nothing of one."""
    import json
    import urllib.request
    from w2cplatform.console import SpecConsole
    from w2cplatform.door import Ring
    from w2cplatform.eventdatabase import EventIndex
    vars_, objects, wall = _box()
    spec = SubsystemSpec.from_dict({**BIN, "door": {"routes": ["read"]}})
    ctl = SpecController(spec, vars_, objects, wall=wall)
    ctl.create({"name": "a"})
    ctl.sealer = _sealer()                                                     # the console's key ring (`SECRETS_KEY`)
    marks = tempfile.mkdtemp(prefix="marks-")
    con = SpecConsole(ctl, marks_root=marks, wall=wall)
    srv = con.serve("127.0.0.1", 0)
    def where():
        import urllib.error
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/where/a", headers={"X-User": "ann"})
        try:
            return json.loads(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as e:                                  # 404: placed nowhere — and said so
            return json.loads(e.read())
    try:
        assert where()["door"] is None                                         # nobody holds it
        objects.put(spec.sub.heartbeat_key("w-1"), Heartbeat("w-1", wall(), [{"id": "a"}], {
            "server": "s1", "bay": "", "capacity": 4, "headroom": 4, "url": "http://w-1:9"}).to_bytes())
        objects.put(spec.sub.heartbeat_key("w-2"), Heartbeat("w-2", wall(), [{"id": "a"}], {
            "server": "s2", "bay": "", "capacity": 4, "headroom": 0, "url": "http://w-2:9"}).to_bytes())
        SpecController(spec, vars_, objects, wall=wall).ensure_placed()
        placed = ctl.placement("a").worker
        d = where()["door"]
        assert d["url"] == f"http://{placed}:9" and d["routes"] == ["read"] and d["expires"] == wall() + 120
        assert Ring(vars_).check(d["token"], unit="bin/a", holder=placed, route="read", now=wall())["sub"] == "ann"
        lines = [e for e in EventIndex(marks, "", wall=wall).query(0, wall() + 1, subsystem="audit")["events"] if e["kind"] == "door.issued"]
        assert [(e["user"], e["target"], e["holder"], e["routes"]) for e in lines] == [("ann", "a", placed, "read")]
        objects.put(spec.sub.heartbeat_key(placed), Heartbeat(placed, wall(), [], {"server": "s1", "url": "x"}).to_bytes())
        assert where()["door"] is None                                         # its holder no longer says it holds it
    finally:
        srv.shutdown()
    plain = SpecConsole(SpecController(SubsystemSpec.from_dict(BIN), vars_, objects, wall=wall), wall=wall)
    srv = plain.serve("127.0.0.1", 0)
    try:
        import urllib.error
        try:
            got = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/where/a").read())
        except urllib.error.HTTPError as e:
            got = json.loads(e.read())
        assert "door" not in got
        assert "door" not in plain.describe() and con.describe()["door"] == {"routes": ["read"]}
    finally:
        srv.shutdown()


def test_the_console_is_the_platforms_built_from_a_directory_of_specs_and_the_deployment_says_what_is_at_the_root():
    """`python3 -m w2cplatform console` (the boundary's step 6: the console was a subsystem's verb, with its own routes and
    its own list of what it fronts): every spec of `SPEC_DIR`, the one `CONSOLE_ROOT` names at `/` and every other
    under its name, one token with each spec's console grant, one journal. A root that names no spec is refused, in
    words: what is at `/` is the deployment's to say."""
    import json
    from w2cplatform import host
    d = tempfile.mkdtemp(prefix="specs-")
    for spec in (BIN, PICK):                                          # JSON is YAML: the specs as the image carries them
        with open(os.path.join(d, f"{spec['name']}.subsystem.yaml"), "w") as f:
            json.dump(spec, f)
    env = {"SPEC_DIR": d, "PLATFORM_DIR": tempfile.mkdtemp(prefix="platform-"), "CONSOLE_ROOT": "bin"}
    m, ctls = host.build_console(env)
    assert m.root.spec.name == "bin" and set(m.mounts) == {"pick"} and set(ctls) == {"bin", "pick"}
    assert m.mounts["pick"].journal is m.root.journal
    ctls["bin"].create({"name": "a"})                                 # the console's token writes the operator's rows
    from w2cplatform.variables import Forbidden
    try:
        ctls["bin"].vars.put("bin/placement/a", {"worker": "w-1"})
        raise AssertionError("the console's token wrote a placement")
    except Forbidden:                                                 # …and never placement
        pass
    _refused(lambda: host.build_console({**env, "CONSOLE_ROOT": "nope"}), "CONSOLE_ROOT='nope' names no spec")
    assert "console" in host.USAGE



def test_servers_status_puts_the_heartbeat_fields_it_names_on_each_workers_row_as_the_heartbeat_wrote_them():
    """`servers.status: [{field, title}]`, beside `servers.show`: fields of the subsystem's heartbeats a page shows on a
    server's row under its title. `GET /servers` puts each worker's value in its row, `status: {<field>: <value>}`, as
    the heartbeat carries it — a string of `heartbeat.strings` a string, a number a number, `2` not `2.0` —, and the
    declarations once beside `policy`, as `/spec` carries them beside `show`; the page sums them per server, the platform
    adds nothing up. A field the heartbeat does not carry is absent, not null; a word where a number stands is counted
    and absent. The loader takes `{field, title}` and maybe `of` (ADR-0064): another form, another key, an empty title, a
    field said twice, the platform's own field — refused (ADR 0012)."""
    import json
    import urllib.request
    from w2cplatform.console import SpecConsole
    from w2cplatform.rows import FIELDS
    declared = [{"field": "jam", "title": "застряло"}, {"field": "stuck", "title": "застрявших"}]
    d = {**BIN, "heartbeat": {"strings": ["jam"]}, "servers": {"status": declared}}
    spec = SubsystemSpec.from_dict(d)
    assert spec.servers_status == declared and spec.servers_show == []
    vars_, objects, wall = _box()
    ctl = SpecController(spec, vars_, objects, wall=wall)
    for w, server, extra in (("w-1", "s1", {"jam": "yes", "stuck": 2}), ("w-2", "s1", {"jam": "no", "stuck": 0.5}),
                             ("w-3", "s2", {}), ("w-4", "s2", {"stuck": "many"})):
        objects.put(spec.sub.heartbeat_key(w), Heartbeat(w, wall(), [], {"server": server, "bay": "", "capacity": 4,
                                                                         "headroom": 4, **extra}).to_bytes())
    srv = SpecConsole(ctl, wall=wall).serve("127.0.0.1", 0)
    def get(path):
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}{path}", headers={"X-User": "ann"})
        return json.loads(urllib.request.urlopen(req).read())
    try:
        out = get("/servers")
        rows = {w["worker"]: w for s in out["servers"].values() for w in s["workers"]}
        assert rows["w-1"]["status"] == {"jam": "yes", "stuck": 2} and type(rows["w-1"]["status"]["stuck"]) is int
        assert rows["w-2"]["status"] == {"jam": "no", "stuck": 0.5}
        assert rows["w-3"]["status"] == {}                                        # nothing said: absent, not null
        assert rows["w-4"]["status"] == {}                                        # a word where a number stands
        assert f"{spec.sub.heartbeat_key('w-4')}#stuck" in FIELDS.bad              # …counted, as `number` counts it
        assert out["status"] == declared                                          # the titles, once
        assert get("/spec")["servers"] == {"status": declared}
    finally:
        srv.shutdown()
    plain = SpecConsole(SpecController(SubsystemSpec.from_dict(BIN), vars_, objects, wall=wall), wall=wall)
    out = plain.servers()
    assert "status" not in out and not any("status" in w for s in out["servers"].values() for w in s["workers"])
    assert "servers" not in plain.describe()
    with_show = SubsystemSpec.from_dict({**d, "servers": {"show": [{"table": "bays", "by": "server"}], "status": declared}})
    assert with_show.servers_show and with_show.servers_status == declared

    def status(*entries, strings=("jam",)):
        return lambda: SubsystemSpec.from_dict({**BIN, "heartbeat": {"strings": list(strings)},
                                                "servers": {"status": list(entries)}})
    _refused(lambda: SubsystemSpec.from_dict({**d, "servers": {"status": {"field": "jam", "title": "x"}}}),
             "servers.status is [{field")                                       # not a list
    _refused(status("jam"), "servers.status is [{field")                          # an entry that is a word
    _refused(status({"field": "jam"}), "servers.status is [{field")               # no title
    _refused(status({"title": "x"}), "servers.status is [{field")                 # no field
    _refused(status({"field": "Jam it", "title": "x"}), "servers.status is [{field")   # no field's name
    _refused(status({"field": 5, "title": "x"}), "servers.status is [{field")
    _refused(status({"field": "jam", "title": 5}), "servers.status is [{field")
    _refused(status({"field": "jam", "title": "x", "sum": True}), "servers.status is [{field")   # an unknown key
    _refused(lambda: SubsystemSpec.from_dict({**d, "servers": {"status": declared, "totals": []}}), "`servers:` is")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "servers": {}}), "`servers:` is")
    _refused(status({"field": "jam", "title": ""}), "servers.status is [{field")       # an empty title
    _refused(status({"field": "jam", "title": "  "}), "servers.status is [{field")
    _refused(status({"field": "jam", "title": "x"}, {"field": "jam", "title": "y"}), "names 'jam' twice")
    _refused(status({"field": "server", "title": "x"}), "the platform's own field")


def test_a_servers_status_field_is_a_path_into_the_heartbeats_maps():
    """A field of `servers.status` may be a path into the heartbeat's maps by its dots (`writer.state`; «Архитектор»
    2026-10-06, the product's window 12: the reading of `metrics[].from` without its `heartbeat.`): its leaf is a string
    or a number, either one (no `heartbeat.strings` names a path), or a map or a list put whole (ADR-0064), said under
    the path as the spec writes it; a leaf that is `true` or null is counted as a garbled field and left out; a path the
    heartbeat does not carry — a key not there, a word where a map should be — is absent, not counted. The loader takes
    dotted names, plain keys only (no `<k>`: a cell is one value), and refuses an empty segment, other characters, and
    a path into the platform's own field (ADR 0012)."""
    from w2cplatform.console import SpecConsole
    from w2cplatform.rows import FIELDS
    declared = [{"field": "belt.state", "title": "лента"}, {"field": "belt.lag_s", "title": "отстаёт"},
                {"field": "belt.motor.amps", "title": "ток"}]
    spec = SubsystemSpec.from_dict({**BIN, "servers": {"status": declared}})
    assert spec.servers_status == declared
    vars_, objects, wall = _box()
    for w, extra in (("w-1", {"belt": {"state": "stalled", "lag_s": 3.5, "motor": {"amps": 2}}}),
                     ("w-2", {"belt": "jammed"}),                               # no map where the path goes
                     ("w-3", {"belt": {"state": ["x"], "lag_s": {"s": 1}, "motor": {"amps": True}}}),
                     ("w-4", {}),
                     ("w-5", {"belt": {"state": "", "lag_s": "slow", "motor": {}}}),
                     ("w-6", {"belt": {"state": None}})):
        objects.put(spec.sub.heartbeat_key(w), Heartbeat(w, wall(), [], {"server": "s1", "bay": "", "capacity": 4,
                                                                         "headroom": 4, **extra}).to_bytes())
    out = SpecConsole(SpecController(spec, vars_, objects, wall=wall), wall=wall).servers()
    rows = {w["worker"]: w["status"] for s in out["servers"].values() for w in s["workers"]}
    assert rows["w-1"] == {"belt.state": "stalled", "belt.lag_s": 3.5, "belt.motor.amps": 2}
    assert type(rows["w-1"]["belt.motor.amps"]) is int                         # as written: `2`, not `2.0`
    assert rows["w-2"] == {} and rows["w-4"] == {}                             # not carried: absent…
    key = spec.sub.heartbeat_key
    assert not {f"{key(w)}#{f}" for w in ("w-2", "w-4") for f in ("belt.state", "belt.lag_s", "belt.motor.amps")} \
        & FIELDS.bad                                                           # …and not counted
    # a list and a map at the leaf go whole, not counted (ADR-0064); a bool is absent and counted
    assert rows["w-3"] == {"belt.state": ["x"], "belt.lag_s": {"s": 1}}, rows
    assert not {f"{key('w-3')}#belt.state", f"{key('w-3')}#belt.lag_s"} & FIELDS.bad
    assert f"{key('w-3')}#belt.motor.amps" in FIELDS.bad
    assert rows["w-6"] == {} and f"{key('w-6')}#belt.state" in FIELDS.bad      # null is said, and is neither
    # a string leaf, empty too, is said as it is — any leaf: no `heartbeat.strings` names a path, a map's leaf says
    # what it is (the product's `statusOf`); an empty map on the way says nothing and is not counted
    assert rows["w-5"] == {"belt.state": "", "belt.lag_s": "slow"}, rows
    assert not {f"{key('w-5')}#belt.lag_s", f"{key('w-5')}#belt.motor.amps"} & FIELDS.bad
    assert out["status"] == declared

    def status(field):
        return lambda: SubsystemSpec.from_dict({**BIN, "servers": {"status": [{"field": field, "title": "x"}]}})
    for bad in ("belt.", ".belt", "belt..state", "belt.State", "belt.<lane>", "belt state", "belt.9"):
        _refused(status(bad), "servers.status is [{field")
    _refused(status("server.name"), "the platform's own field")                # a path into the platform's own
    _refused(status("labels.zone"), "the platform's own field")


def test_a_servers_status_map_or_list_goes_on_the_row_whole_and_of_names_a_table_of_the_spec():
    """ADR-0064: a `servers.status` field — a top one or a path's leaf — may be a map or a list, put on the worker's row
    of `/servers` whole, as the heartbeat carries it: the platform reads nothing in it and counts none of it garbled (a
    field once garbled and now a map is a field read). `of: <a table of this spec>` says whose rows its keys are; the
    page reads it beside `title`, on `/spec` and once on `/servers`. An `of` that names no table of the spec is refused
    at load (ADR 0012). What stays as it was (ADR 0057): `true` and null counted, a top field's word where a number
    stands counted, a key not there absent."""
    import json
    import urllib.request
    from w2cplatform.console import SpecConsole
    from w2cplatform.rows import FIELDS
    declared = [{"field": "keeps", "title": "сохранения", "of": "bays"}, {"field": "lost", "title": "потеряно", "of": "bays"},
                {"field": "writer.queue", "title": "очередь"}, {"field": "piles", "title": "кучи"}]
    spec = SubsystemSpec.from_dict({**BIN, "servers": {"status": declared}})
    assert spec.servers_status == declared
    vars_, objects, wall = _box()
    ctl = SpecController(spec, vars_, objects, wall=wall)
    key = spec.sub.heartbeat_key

    def beat(w, extra):
        objects.put(key(w), Heartbeat(w, wall(), [], {"server": "s1", "bay": "", "capacity": 4, "headroom": 4,
                                                      **extra}).to_bytes())
    beat("w-1", {"keeps": {"k1": {"copied": 3, "missing": 0}, "k2": {}}, "lost": ["k1"], "writer": {"queue": [1, 2]},
                 "piles": 2})
    beat("w-2", {"keeps": True, "lost": None, "writer": {"queue": "long"}, "piles": "many"})
    beat("w-3", {"keeps": None, "writer": "stuck"})
    srv = SpecConsole(ctl, wall=wall).serve("127.0.0.1", 0)

    def get(path):
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}{path}", headers={"X-User": "ann"})
        return json.loads(urllib.request.urlopen(req).read())
    try:
        out = get("/servers")
        rows = {w["worker"]: w["status"] for s in out["servers"].values() for w in s["workers"]}
        assert rows["w-1"] == {"keeps": {"k1": {"copied": 3, "missing": 0}, "k2": {}}, "lost": ["k1"],
                               "writer.queue": [1, 2], "piles": 2}, rows
        assert not {f"{key('w-1')}#{f}" for f in ("keeps", "lost", "writer.queue", "piles")} & FIELDS.bad
        # `true`, null and a top field's word stay garbled; a path's word leaf is said
        assert rows["w-2"] == {"writer.queue": "long"}, rows
        assert {f"{key('w-2')}#keeps", f"{key('w-2')}#lost", f"{key('w-2')}#piles"} <= FIELDS.bad
        assert rows["w-3"] == {} and f"{key('w-3')}#keeps" in FIELDS.bad      # `lost` not carried, `writer` no map
        assert f"{key('w-3')}#lost" not in FIELDS.bad and f"{key('w-3')}#writer.queue" not in FIELDS.bad
        beat("w-3", {"keeps": {}})                                            # …and now it says a map: read, not garbled
        rows = {w["worker"]: w["status"] for s in get("/servers")["servers"].values() for w in s["workers"]}
        assert rows["w-3"] == {"keeps": {}} and f"{key('w-3')}#keeps" not in FIELDS.bad
        # `of` where the page reads `title`: the declarations once on `/servers`, and `/spec`
        assert out["status"] == declared and get("/spec")["servers"] == {"status": declared}
    finally:
        srv.shutdown()

    def status(*entries):
        return lambda: SubsystemSpec.from_dict({**BIN, "servers": {"status": list(entries)}})
    _refused(status({"field": "keeps", "title": "x", "of": "keeps"}), "declares no such table")   # BIN has `bays` only
    _refused(status({"field": "keeps", "title": "x", "of": 5}), "declares no such table")
    _refused(status({"field": "keeps", "title": "x", "of": ["bays"]}), "declares no such table")
    _refused(status({"field": "keeps", "of": "bays"}), "servers.status is [{field")       # `of` is no title
    _refused(status({"field": "keeps", "title": "x", "of": "bays", "by": "id"}), "servers.status is [{field")


def test_who_holds_a_row_is_said_by_the_table_of_places_and_not_by_the_affinity_table():
    """ADR 0056: `held_by` in `GET /<table>` belongs to `placement.places.table` — a hold is of a place only
    (`<sub>/holds/<row>`). The `affinity` table, when it is another table, says no holder: in testsub2 the two are one
    table, so a condition on the wrong one never showed."""
    from tests.conftest import Served
    from w2cplatform.console import SpecConsole
    vars_, objects, wall = _box()
    t = {"key": "{name}", "fields": {"name": {"type": "string", "required": True}, "kind": {"type": "string"},
                                     "server": {"type": "string"}}}
    spec = SubsystemSpec.from_dict({**BIN, "tables": {"bays": t, "shelves": t},
                                    "placement": {**BIN["placement"], "places": {"table": "shelves"}}})
    assert spec.affinity["table"] == "bays" and spec.places["table"] == "shelves"
    ctl = SpecController(spec, vars_, objects, wall=wall)
    vars_.put("bin/bays/b1", {"name": "b1", "kind": "plain"})
    vars_.put("bin/shelves/b1", {"name": "b1", "kind": "plain"})
    vars_.put("bin/holds/b1", {"holder": "i-1", "until": wall() + 30, "released": "false", "gen": 1, "by": "w-1"})
    with Served(SpecConsole(ctl, wall=wall)) as call:
        st, out = call("GET", "/shelves")
        assert st == 200 and [(r["name"], r["held_by"]) for r in out["shelves"]] == [("b1", "i-1")], (st, out)
        st, out = call("GET", "/shelves/b1")
        assert st == 200 and out["held_by"] == "i-1", (st, out)
        st, out = call("GET", "/bays")
        assert st == 200 and [r["name"] for r in out["bays"]] == ["b1"] and "held_by" not in out["bays"][0], (st, out)


def test_a_spec_whose_neighbour_the_catalogue_lacks_is_refused_where_the_catalogue_is_whole():
    """ADR 0056: `near.of` and `near.prefer` read the neighbour by its spec, from the process's catalogue. One it does not
    hold is refused, naming it — not one file's load (a directory loads in name order, and `aisle` comes before the
    `crate` it follows), but where the catalogue is whole: the end of `load_dir`, and a controller's start. It was a
    pass's: `_preferred` read nothing and preferred nothing, in silence. A bare `near` reads only their heartbeats."""
    import json
    vars_, objects, wall = _box()
    crate = {"name": "crate", "unit": {"rows": "items", "id": "name", "fields": {"name": {"type": "string", "required": True},
                                                                              "owner": {"type": "string"}}},
             "placement": CAP}
    unit = {"rows": "picks", "id": "name", "fields": {"name": {"type": "string", "required": True}}}
    of = {"name": "aisle", "unit": unit, "placement": {**CAP, "near": {"sub": "crate", "of": "owner"}}}
    prefer = {"name": "aisle", "unit": unit, "placement": {**CAP, "near": {"sub": "crate", "of": "owner",
                                                                           "prefer": {"owner": ["ann"]}}}}
    bare = {"name": "aisle", "unit": unit, "placement": {**CAP, "near": "crate"}}
    _refused(lambda: SpecController(SubsystemSpec.from_dict(of), vars_, objects, wall=wall),
             "aisle: near.of reads the spec of 'crate', and this process loaded none")
    _refused(lambda: SpecController(SubsystemSpec.from_dict(prefer), vars_, objects, wall=wall),
             "aisle: near.prefer reads the spec of 'crate'")
    SpecController(SubsystemSpec.from_dict(bare), vars_, objects, wall=wall)           # their heartbeats only: no spec read
    d = tempfile.mkdtemp(prefix="specs-")
    with open(os.path.join(d, "aisle.subsystem.yaml"), "w") as f:
        json.dump(prefer, f)
    _refused(lambda: catalog.load_dir(d), "near.prefer reads the spec of 'crate'")
    with open(os.path.join(d, "crate.subsystem.yaml"), "w") as f:
        json.dump(crate, f)
    assert [s.name for s in catalog.load_dir(d)] == ["aisle", "crate"]                 # the follower first, and taken
    SpecController(SubsystemSpec.from_dict(of), vars_, objects, wall=wall)


def test_a_place_that_stops_admitting_gives_up_the_units_of_its_live_worker():
    """ADR 0056, its addition (the product's `Unfit` hook): a live worker whose place is a row of the `affinity` table
    saying `admits: false` is leaving — its units go, "<w>'s <place_by> <place> admits no unit". "No new ones, the old
    ones stay" kept them where the administrator closed the place, for ever. A row that does not read and a table that
    does not list give nothing up; a dead worker is not this rule's (its slot's fate is)."""
    from w2cplatform.variables import Garbled
    vars_, objects, wall = _box()
    spec = SubsystemSpec.from_dict(BIN)
    ctl = SpecController(spec, vars_, objects, wall=wall)
    vars_.put("bin/bays/b1", {"kind": "plain", "server": "s1"})
    vars_.put("bin/bays/b2", {"kind": "plain", "server": "s2"})
    _worker(objects, wall, spec, "w-1", "s1", "b1")
    _worker(objects, wall, spec, "w-2", "s2", "b2")
    ctl.create({"name": "a"})
    ctl.move("a", "w-1", "put there")
    live = sorted(ctl.workers_seen())
    assert ctl.leaving(live) == {}
    vars_.put("bin/bays/b1", {"kind": "plain", "server": "s1", "admits": "false"})
    assert ctl.leaving(live) == {"w-1": "w-1's bay b1 admits no unit"}
    real_get, real_list = vars_.get, vars_.list
    vars_.get = lambda k, *a, **kw: (_ for _ in ()).throw(Garbled(k, "torn")) if k == "bin/bays/b1" else real_get(k, *a, **kw)
    assert ctl.leaving(live) == {}                                         # a row nobody can read moves nothing
    vars_.get = real_get
    vars_.list = lambda p, *a, **kw: (_ for _ in ()).throw(OSError("store away")) if p == "bin/bays/" else real_list(p, *a, **kw)
    assert ctl.leaving(live) == {}                                         # …nor a table that does not list
    vars_.list = real_list
    wall.t += 100                                                          # w-1 falls silent; w-2 speaks on
    _worker(objects, wall, spec, "w-2", "s2", "b2")
    assert sorted(ctl.workers_seen()) == ["w-2"]
    assert "admits no unit" not in str(ctl.leaving(sorted(ctl.workers_seen())))
    wall.t -= 100                                                          # w-1 alive again: its units go, beside a place that admits
    _worker(objects, wall, spec, "w-1", "s1", "b1")
    _worker(objects, wall, spec, "w-2", "s2", "b2")
    assert ctl.redistribute(sorted(ctl.workers_seen())) == [("a", "w-1", "w-2")]
    assert ctl.placement("a").worker == "w-2" and ctl.placement("a").reason.startswith("w-1's bay b1 admits no unit")

