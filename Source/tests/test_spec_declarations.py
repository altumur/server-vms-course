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
    placement.group_by.schemes        where a scheme writes its host, in a closed dictionary: `host: authority | path`,
                                      `fragment: keep | none`, `none: [<authority>]`
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
    for none in ("x://h%2Ecorp/", "x://h_1/", "x://010.0.0.5/", "x://[fe80::1%en0]/", "x://h:pw/", "x://h/%zz",
                 "x:///a", "h", "", "x://a b/"):
        assert url_host(none) == "", none
    assert url_host("x://a#@h/") == "a" and url_host("x://a#@h/", {"x": {"fragment": "none"}}) == "h"
    hub = {"m": {"host": "path", "none": ["local"]}}
    assert url_host("m://hub1/H.Example/a", hub) == url_host("m://hub2/h.example:21/b", hub) == "h.example"
    assert url_host("m://hub1", hub) == url_host("m://hub1/", hub) == "hub1"           # no host in the path: the authority
    assert url_host("m://local/x", hub) == url_host("m://LOCAL", hub) == url_host("m://u@local.:9/x", hub) == ""
    assert url_host("m://hub/a:b%40h/x", hub) == url_host("m://hub/a:b/c@h/x", hub) == "h"   # a login set aside
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


def test_the_schemes_of_a_group_are_a_closed_dictionary_said_beside_cut_at_host_only():
    """`group_by.schemes` loads only beside `cut_at: host`, each scheme in lower case with at least one word, each word of
    the dictionary with one of its values; anything else is refused at load, in words."""
    base = {"name": "probe", "unit": {"rows": "items", "id": "name",
                                      "fields": {"name": {"type": "string"}, "addr": {"type": "url"}}}}

    def spec(**g):
        return SubsystemSpec.from_dict({**base, "placement": {**CAP, "group_by": {"field": "addr", **g}}})

    ok = spec(cut_at="host", schemes={"m": {"host": "path", "fragment": "none", "none": ["local"]}, "y": {"host": "authority"}})
    assert ok.group_cut == "host" and ok.group_of("m://a/b/c") == "b" and spec(cut_at="host").group_of("m://a/b") == "a"
    _refused(lambda: spec(cut_at="part", schemes={"m": {"fragment": "none"}}), "only `cut_at: host` reads a host")
    _refused(lambda: spec(schemes={"m": {"fragment": "none"}}), "only `cut_at: host` reads a host")
    _refused(lambda: spec(cut_at="host", schemes={"m": {"port": "none"}}), "'port' is not a word of the dictionary")
    _refused(lambda: spec(cut_at="host", schemes={"m": {"host": "query"}}), "m.host is one of authority, path")
    _refused(lambda: spec(cut_at="host", schemes={"m": {"fragment": "drop"}}), "m.fragment is one of keep, none")
    _refused(lambda: spec(cut_at="host", schemes={"m": {}}), "a scheme says at least one of")
    _refused(lambda: spec(cut_at="host", schemes={"m": None}), "a scheme says at least one of")
    _refused(lambda: spec(cut_at="host", schemes={}), "{<scheme>: {host?, fragment?, none?}")
    _refused(lambda: spec(cut_at="host", schemes={"M": {"fragment": "none"}}), "not a scheme in lower case")
    _refused(lambda: spec(cut_at="host", schemes={"m": {"none": "local"}}), "m.none is a list of authorities")
    _refused(lambda: spec(cut_at="host", schemes={"m": {"none": ["a/b"]}}), "m.none is a list of authorities")
    _refused(lambda: spec(cut_at="host", schemes={"m": {"none": [False]}}), "m.none is a list of authorities")
    _refused(lambda: spec(cut_at="host", port=1), "placement.group_by is a field, or")
    _refused(lambda: SubsystemSpec.from_dict({**base, "placement": {**CAP, "group_by": {"field": "name", "cut_at": "host"}}}),
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
    ctl.create({"name": "c", "owner": "bob", "home": "b9"})               # not declared: binds nothing
    from w2cplatform.variables import Garbled
    real = vars_.get
    vars_.get = lambda k, *a, **kw: (_ for _ in ()).throw(Garbled(k, "torn")) if k == "bin/bays/b3" else real(k, *a, **kw)
    _refused(lambda: ctl.create({"name": "d", "owner": "ann", "home": "b3"}), "whose row does not parse")
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
                 'bin_away_seconds{worker="w-1"} 30.0', 'bin_away_seconds{worker="w-2"} 0',
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


def test_what_a_table_holds_is_kept_past_its_days_for_the_unit_and_every_unit_about_it():
    """`holds:` (it was a subsystem's function the resource called, `kept`): a row of the spec's table holds its unit's
    buckets — and those of every unit about it, read through that unit's spec's `about` — for its stretch, at most
    `longest` from its start; a row whose bounds do not read holds its unit as far as they read; a unit whose row does
    not read, or names nobody, is held by every hold that reads; another unit's buckets go by their days."""
    from w2cplatform import holds
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
    res = platform_resource(root, "s1", "http://s1", vars_, objects, wall=wall)
    res.kept = lambda progressed=None: holds.kept(vars_, [owner, about], progressed)
    res.retain()
    left = lambda sub, unit: len(bucket_names_under(root, sub, unit, 600))
    assert (left("shelf", "1"), left("label", "t1")) == (1, 1)            # the pin's hour: the unit and the unit about it
    assert (left("shelf", "2"), left("label", "t2")) == (1, 1)            # as far as it reads: up to its end
    assert left("label", "torn") == 1                                     # nobody can say whose: the sound pin holds it
    vars_.get = real
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "holds": {"table": "nope", "unit": "u", "since": "a", "until": "b"}}),
             "`holds:` is")


def test_the_resource_asks_a_subsystem_that_frees_by_a_request_row_and_reads_its_answer():
    """`requests: {free: true}` (it was a subsystem's hook the resource called, `free`): over the high mark the resource
    writes `<sub>/requests/free-<server>-<volume> {free, volume, server}` and reads what the subsystem's live workers
    on its server say they freed (`freed` in their heartbeats); back under the mark, the row is taken away. Nothing of
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
    objects.put(spec.sub.heartbeat_key("w-1"), Heartbeat("w-1", wall(), [], {"server": "s1", "bay": "", "freed": {vol: 40}}).to_bytes())
    out = res.relieve()
    assert out["freed"] == 40 and out["short"] == 8 and vars_.get(key)[0]["free"] == "8"   # what is left, asked again
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


SHED = {"name": "shed", "placement": CAP,
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
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": -1}}), "requests.valid_for is a positive number")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"stamp": ["colour"]}}), "`requests:` is")


def test_how_long_a_request_stands_is_declared_and_a_spec_that_does_not_say_it_does_not_load():
    """The architect, 2026-10-05 (ADR 0012): no number is assumed. A family that frees says `requests.ttl` — a ledger
    `per_person` reads it too; any other says `requests.valid_for`; a spec without the key it needs is refused, naming
    the path. `ttl: 0` is no limit, said so; a negative one is no time."""
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "requests": {"free": True}}), "requests.ttl is required with `free: true`")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"stamp": ["by"]}}), "requests.valid_for is required")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": 20, "per_person": 3}}),
             "requests.ttl is required with `per_person`")
    _refused(lambda: SubsystemSpec.from_dict({**BIN, "requests": {"free": True, "ttl": -1}}), "requests.ttl is a positive number (or 0")
    _refused(lambda: SubsystemSpec.from_dict({**SHED, "requests": {"valid_for": 0}}), "requests.valid_for is a positive number")
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

