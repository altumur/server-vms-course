"""The controller as data. A subsystem gives the platform a spec — one YAML
file — and the platform runs the controller from it:

    name          the prefix: <name>/*
    unit          the rows: where they live (<name>/<rows>/<id>), how an id is made (numeric | <field>),
                  the operator's fields with types and defaults, and derived rows (a second row the
                  platform keeps beside the unit — testsub2's <name>/retention/<id> that the resource reads)
    placement     capacity and headroom as heartbeat fields; a constraint and a tie-break BY NAME from
                  the catalogue below — never an expression; `requires: resource` when a worker must
                  run where a resource answers (not placed on, moved off, while it is silent); the
                  rebalance dead band
    snapshot      the fields that leave the cluster, as one object for the layer above

The catalogue is deliberately short and CLOSED. `labels-subset`: a unit's
`labels` must be a subset of what the worker's server reports.
`most-free-capacity`: the worker with the most capacity − load wins. Nothing
registers another: a spec naming a rule that is not here does not load. What
a subsystem needs beyond them it DECLARES — `affinity` (a row of its table
binds a unit to a place, or takes none), `near.prefer`, a field's `ref`,
`must_match` and `unique`, a url field's `schemes`, `group_by.cut_at` — and the
platform reads the declaration; no code of a subsystem's is called here (the boundary's step 6).

What is NOT in a spec: anything about what a unit does. That is the worker,
and the worker is the subsystem.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # spec.py — the controller as data: SubsystemSpec from `<sub>.subsystem.yaml`, and SpecController, the one
# controller every subsystem runs
#
# **Role in the module.** Lesson 6. A subsystem gives the platform one YAML file and the platform runs its
# controller from it. The spec says: `name` (the prefix `<name>/*`); `unit` (where rows live —
# `<name>/<rows>/<id>` — how an id is made — `numeric` or a field name — the operator's fields with types
# and defaults, and derived rows kept beside the unit, such as testsub2's `testsub2/retention/<id>` that the
# resource reads); `placement` (which heartbeat fields carry capacity and headroom, a constraint and a
# tie-break chosen *by name* from a short catalogue — never an expression — `requires: resource` when the
# worker's server must have a resource that answers, and the rebalance dead band);
# `snapshot` (the fields that leave the cluster); `console` (the name of the running gauge). What is not in
# a spec: anything about what a unit does — that is the worker, and the worker is the subsystem.
# `SpecController` extends `contract.Controller` and adds units, placement, redistribution, rebalance, the
# read model and the snapshot. A subsystem's own controller module is this class with its spec and its own names for
# the methods, and its config module exposes `row()`/`items()`; `console.py` runs over the same spec. The platform's
# tests run testsub and testsub2 through it from their own YAML (`tests/testdata/`), and the lessons run the rest.
#
# ## Module-level names
# - `PLATFORM_FIELDS = ("worker", "placement", "epoch", "revision", "observed_revision", "phase", "id")` —
#   never the operator's. `SubsystemSpec.refuse` rejects any of them in a create/update body: placement is
#   decided and stored by the controller with a reason; revision, epoch and phase are not the operator's.
# - `SpecController.POLICY_DEFAULTS` / `POLICY_CHOICES` — the administrator's knobs, one row `<name>/policy`
#   written by the console (`acl_console` includes it) and read by the controller on every pass: `servers`
#   is `shared` (default: every worker carries units, two on one server included — a box is that) or
#   `distinct` (one worker per server carries units, `idle_by_policy` names the rest). Under either, a server
#   whose worker and resource are both silent is gone (`gone_servers`) and its units move: there is no scheduler
#   to bring the worker back on a neighbour — the units go to the workers that are there, and a shortage is
#   offered to a spare (`offer_spares`).
# - `CONSTRAINTS` — the catalogue, closed: `"none"` (always eligible) and `"labels-subset"` (`_labels_subset`).
#   `requires: resource` is not a constraint on the unit but on the worker's server: `resource_state` reads
#   `platform/resources/<server>/heartbeat` — `live`, `silent`, or `unknown` (never seen) — and `_pool`
#   drops workers whose resource is silent; `redistribute` moves their units off with the reason
#   `resource on <server> silent`. A server's units put a worker where disks are declared; this is
#   whether the resource there still answers. `unknown` passes: silent is a fact, unknown is not one.
#   Extended by nobody: a spec naming another rule does not load (`TIE_BREAKS` likewise).
#
# ## Notes
# - Every write is `Controller.write` (CAS loop) or a create-only `put(cas=0)`; nothing is cached between passes,
#   so the process can be killed anywhere. Within one pass each key is read once (`contract.one_pass`). One
#   exception, on purpose: the servers' labels last read (`server_labels`) are kept, so a store that does not answer
#   moves nothing — a process that never read them knows no server's labels, and moves nothing either.
# - What a server reaches (feedback DQ, ADR-0026): `platform/servers/<server> {labels}`, the platform's row — one a
#   server, written from the console's root — over the labels its workers report (`labels_of`, `node_labels_of`);
#   `ensure_reach` moves a placed unit its server no longer reaches, or unplaces it with the reason, `REACH_BUDGET` a pass.
# - The order inside `place` — placement row, then assignment — is what makes two instances agree: the row
#   is the lock.
# - `capacity_of`/`labels_of`/`server_of` call `workers_seen(max_age=1e12)` each time: outside a pass one
#   object-store listing per call, inside one (`pass_once`, the snapshot) the heartbeats read once for the pass.
# ================================================================================================
from __future__ import annotations

import ipaddress
import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field

from urllib.parse import urlsplit

from .doors import numeric, unnamable
from .secrets import NOT_AN_ADDRESS, SecretRules, address_fault, hide_in_url, is_secret_field, opaque_fault
from .blobs import digest as blob_digest, is_digest, verify
from .contract import (ASSIGNMENTS, ASSIGNMENTS_GARBLED, CONTROLLER_PASS, DECOMMISSION, DRAIN_KEY, MOVED_FATES, SCHEMA_KEY,
                       SERVERS_PREFIX, OFFER_GRACE, SLOTS, SLOT_LOST_AFTER, SLOTS_GARBLED, UNPLACED, Controller, Subsystem, is_live,
                       label_set, one_pass, read_slot, server_key, slot_number, stored)
from .events import OWN_OF_TREES, Suppress
from .limits import TooLarge
from .objects import ObjectStore
from .canonical import GARBLED, MUST_MATCH, UNIQUE, BadUrl, canonical_json, number_text, parse_json
from .rows import PARSE_ERRORS, Table, finite
from .variables import Conflict, Garbled, Variables

PLATFORM_FIELDS = ("worker", "placement", "epoch", "revision", "observed_revision", "phase", "id")   # never the operator's
# The most a single `json` field may be. Not the row's ceiling (Lesson 19) — this one keeps ONE field
# from eating it, because a field that can hold a document will be given one.
JSON_CEILING = 4000
# THE PLATFORM'S OWN NAMES (ADR 0029, More Information; the strict loader, ADR 0012): a spec's name is the prefix of
# its keys, its trees and its space on the domain, so a subsystem named as one of the platform's own would write there.
# The console's marks and the journal are the trees whose lines say their own `of` (`events.refuse_own_of`);
# `platform/` is the platform's keys (its resources, its servers), `domain/` the domain's space. Refused at load.
RESERVED_NAMES = frozenset((*OWN_OF_TREES, "platform", "domain"))


# A write the spec does not allow: a platform field, an unknown field, a missing required field, an id for a
# numeric-id subsystem, a duplicate id. The console turns it into HTTP 400.
log = logging.getLogger(__name__)


class Moved(Exception):
    """A move the controller decided on a row that has changed since: somebody else moved the unit first."""


class Refused(Exception):
    pass


class AddressRefused(Refused):
    """A url field's value refused by address — a login in it, no host or one nobody can tell (ADR 0053), a port that is
    no number, a scheme the field is not reached by, a `#`: 400 with `fault: bad_url` at every door (`canonical.BadUrl`,
    the closed dictionary `canonical.FAULTS`), the reason in `detail`."""
    fault = BadUrl.fault


class Mismatched(Refused):
    """A write `must_match` refuses, either way (a unit pointing at a row it disagrees with; a row rewritten so that the
    units pointing at it would disagree): a refusal that depends on the rows standing — 409 with `fault: must_match`
    (ADR 0031's rule), the unit or row it disagrees with in `detail`."""
    status = 409
    fault = MUST_MATCH


class NotUnique(Refused):
    """A value a `unique` field holds that another unit holds already (in the canonical spelling where it says so): a
    refusal that depends on the rows standing — 409 with `fault: unique` (ADR 0031's rule), the other unit in `detail`."""
    status = 409
    fault = UNIQUE


class RefGarbled(Refused):
    """A write whose `ref` names a row that does not parse: right by the spec, stopped by a row standing — 409 with
    `fault: garbled` (ADR 0031's rule), the row's name and «mend it first» in `detail`."""
    status = 409
    fault = GARBLED


class Exists(Refused):
    """A create under an id a unit already has: 409 `{error: "exists"}` at every console, not a 400 (the product's)."""


# WHAT A SECRET LOOKS LIKE ON A PAGE, AND WHAT IT IS GIVEN FOR (the thirteenth round; the product's rule, one YAML key in
# both). A reply shows a secret as `***` (`secrets.mask_secrets`); a page or a client of its own shows `•••`, `●●●` or
# `＊＊＊`. Sent back, any of them is a password nobody typed: refused at the door (`is_mask`) — three or more of one of
# those characters and nothing else. And a secret is the key to an ADDRESS (`bound_to`: testsub2's `feed_secret` to its
# `feed`, a shelf's to its own `feed`): the address changed on an edit and no new secret came — the old
# one would go to whatever host the new address names; refused, in words (`unbound_secret`).
MASK_CHARS = "*•●＊"


def is_mask(v) -> bool:
    """`v` is a secret's mask as a page shows it — `***`, `•••`, `●●●`, `＊＊＊` or more of one of them."""
    s = v.strip() if isinstance(v, str) else ""
    return len(s) >= 3 and len(set(s)) == 1 and s[0] in MASK_CHARS


def unbound_secret(secret: str, bound: tuple, before: dict, after: dict) -> str | None:
    """Why an edit that sent no new `secret` may not keep the stored one — a field it is `bound` to changed — or None.
    Nothing stored: nothing to carry, nothing refused. The words never repeat an address."""
    moved = [b for b in bound if str(before.get(b) or "") != str(after.get(b) or "")]
    if moved and before.get(secret):
        return (f"{secret} was given for the {' and '.join(moved)} this row had; that changed and no new {secret} came. "
                f"A secret is not carried to another address — send the one for the new address")
    return None


# The counter of numeric ids, `<name>/next_id`, through the one reader of rows (`SpecController._next_id`).
NEXT_IDS = Table("next_id", "the next id is one past the largest one there is, and the row is written whole")
# A unit stored under a name `create` refuses today (`doors.unnamable`, `unit`; the review's ninth pass): served as it
# stands — but a name with `,` is in no assignment (`contract.Assignment.to_items`), so nobody runs it.
UNIT_NAMES = Table("unit_name", "it is served as it stands, a name with a comma is assigned to nobody; create it again "
                                "under a name without the character", "unit's name")
# A server's labels from the console (`platform/servers/<server>`, feedback DQ, ADR-0026): one that does not parse — a word that is not
# a label, no `labels` at all, a key the listing shows and a read does not find — keeps what was last read of that
# server; never read, the server reaches no label until it is (the review's tenth pass) — and nothing moves off it
# (`SpecController.server_labels`).
SERVER_LABELS = Table("server_labels", "the server keeps the labels last read of it — if none were read, it takes no unit "
                      "that needs a label — and nothing moves off it", "server's labels")
# A unit whose filters raise while `/unplaceable` or `/drain` judges it (`_unplaceable`, `_would_strand`; the review's tenth
# pass, the walks the other steps had guarded already): a field that reads and does not compare, a filter of the spec's
# (`affinity`, `home`, `near`) that trips on it. Nobody can say a worker would take it, and nothing will: it is listed as
# one nothing can serve, and the other units are judged as before.
# What a spec's `requests:` says (`SubsystemSpec._page_words`).
REQUEST_KEYS = ("free", "schema", "valid_for", "most_valid", "per_person", "settle", "ttl", "key", "stamp", "journal",
                "elsewhere")
# …its numbers: name -> (a whole number?, may it be 0?, what it is) — every one finite (the fourteenth review, minor 5).
REQUEST_NUMBERS = {
    "valid_for": (False, False, "a finite number of seconds above 0"),
    "most_valid": (False, False, "a finite number of seconds above 0"),
    "per_person": (True, False, "a whole number above 0 — how many of one person's may stand"),
    "settle": (False, True, "a finite number of seconds, 0 or more"),
    "ttl": (False, True, "a finite number of seconds, or 0: no limit"),
}
# What a spec's `display:` says: words for a page (`SubsystemSpec._page_words`, `_card_words`) — closed by sections (the
# architect, 5 Oct): what a section holds is free words, and the one thing checked is that a word for a field names one.
DISPLAY_KEYS = ("unit", "units", "units_count", "section", "general", "fields", "field_help", "options", "form", "events",
                "kinds", "actions", "keys", "tree")
# …a section's words, one string each: what a unit and its many are called, the many after a number, the section's title, the first tab
DISPLAY_WORDS = ("unit", "units", "units_count", "section", "general")
# …and the tree's: by what it groups, its columns, whether children hang under a unit — and the words a page says of a
# group, its path's separator among them (the product's words: a group's title and hint, the row of no group…).
TREE_KEYS = ("group_by", "columns", "children")
TREE_WORDS = ("nested_by", "group_title", "group_hint", "filter", "no_group", "contents_title", "group_word",
              "no_group_suffix", "pick_note", "new_root", "new_sub", "add_here", "new_group_note",
              # the words of a unit's groups box the module reads too (`groupsBox`, «Архитектор» 2026-10-06): the set is
              # the module's dictionary, the copy the course takes
              "remove", "not_in", "add_to", "no_others", "new_group")
# THE CONSOLE'S OWN ROUTES: the first segment of every path `SpecConsole.dispatch` and `Mount` answer themselves, before a
# spec's rows and tables are looked at. A spec whose rows or a declared table is named so is a family no request reaches
# — a table `marks` was never written over HTTP: `POST /marks` is the operator's mark. Refused at load; a closed set, held
# to the dispatch by `test_spec_declarations.py`.
CONSOLE_ROUTES = frozenset({"session", "healthz", "index.html", "spec", "where", "resources", "servers", "domain",
                            "policy", "unplaceable", "events", "metrics", "marks", "requests", "asked", "mounts", "drain", "schema",
                            "platform",    # `/platform/console.js`: the console module every page is built from
                            "api"})        # `/api/held`, `/api/backup`, `/api/prepare`, `/api/take`: the processes' doors
UNIT_JUDGED = Table("unit_judged", "it is listed as a unit nothing can serve — `/unplaceable`, `/drain` — until it is "
                    "mended; the other units are judged", "unit's row")
# What a label may be: a unit's own alphabet (`vlan:cctv-a`, `site.b`), and nothing that is a separator in the row
# (a comma) or in a path. The product's rule (`labelWord`). ONE alphabet (the review's tenth pass, major): a unit's
# `labels` (any subsystem's under `labels-subset`, at creation and for a label new to a row), a server's row, the
# node's `LABELS` (`runtime.labels` says the words outside it). A unit stored before with `склад` or `zone 1` is
# read as it stands and is not moved for a label no server's row can say (`UNIT_LABELS`).
LABEL_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:\-]{0,63}")
UNIT_LABELS = Table("unit_label", "the unit stays where it is: no server's row can say it reaches that label — write the "
                    "label again in letters, digits and _ . : -", "unit's label")
# A server's name: what a host's name may be (letters, digits, `.`, `-`, `_`; 253 at most) — `*`, `srv%2Fa`, a newline,
# three hundred characters were rows nobody's server would ever read (the review's tenth pass, minor).
SERVER_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,252}")
REACH_BUDGET = 10                 # moves `ensure_reach` makes in one pass: a server's labels edited moves its units over a few


# THE BUDGET IS A SETTING (the review's twelfth pass, major 7; the owner's decision of 4 Oct). A group bigger than the
# budget never moved, and the log said "raise it, or move them by hand" — with nothing to raise and no door to move by.
# Now `REACH_BUDGET` in the controller's environment raises it; a group left for it is an alarm (`units.over_budget`),
# not a log line only. No manual-move door: the owner's word. A value that is no positive whole number: the default,
# said once.
def reach_budget(env) -> int:
    raw = env.get("REACH_BUDGET")
    if raw in (None, ""):
        return REACH_BUDGET
    try:
        n = int(str(raw).strip())
        if n <= 0:
            raise ValueError("not positive")
        return n
    except ValueError as e:
        log.error("REACH_BUDGET=%r is not a positive whole number (%s): %d moves a pass, the default", raw, e, REACH_BUDGET)
        return REACH_BUDGET


def parse_labels(text) -> frozenset:
    """A row's `labels` — comma-joined label words — as a set; `ValueError` for a word that is not a label."""
    out = frozenset(l.strip() for l in str(text).split(",") if l.strip())
    bad = [l for l in out if not LABEL_WORD.fullmatch(l)]
    if bad:
        raise ValueError(f"{bad[0]!r} is not a label")
    return out


def server_name(server: str) -> str:
    """A server's name as a row's key: not a path, no character a list or a log would split on — a host's name."""
    server = str(server or "")
    if not SERVER_WORD.fullmatch(server) or server in (".", "..") or unnamable(server, unit=True):
        shown = server if len(server) <= 80 else server[:80] + "…"
        raise Refused(f"{shown!r} is not a server's name: letters, digits and . - _ (up to 253)")
    return server


def label_refusal(labels, old=()) -> str | None:
    """Why a unit's `labels` may not stand — a label new to the row outside `LABEL_WORD` — or None. One stored before is
    left as it is (`old`): refusing it would make every other edit of that unit's row a 400."""
    bad = [l for l in (labels or []) if str(l) not in set(map(str, old or ())) and not LABEL_WORD.fullmatch(str(l))]
    return (f"a label is letters, digits and _ . : - (up to 64), starting with a letter or a digit, not {bad[0]!r}"
            if bad else None)


# A stored placement decision: `unit` (int for numeric ids, str otherwise), `worker`, `reason` (a sentence
# naming the free capacity, the labels reached and the server), `at` (wall time), `rev`. Lives at
# `<name>/placement/<id>`.
@dataclass
class Placement:
    unit: object                  # the unit's id: an int for numeric ids, a str otherwise
    worker: str
    reason: str
    at: float
    rev: int


# One operator field from the spec: `name`, `type` (`string | int | float | bool | list | url | blob`),
# `default`, `required`. A `blob` holds a DIGEST (`sha256-<hex>`); the bytes live in the object store under
# `<name>/blobs/<digest>` and the platform never looks inside them — see `blobs.py`.
#
# `inherit` instead of `default` (М12 Lesson 12, feedback AT): the field may be left NOT SET, and a value
# somebody above sets — a domain's shared default — is then the value. A `default` cannot do that: it is
# written into the row when the row is created and supplied again when the row is read, so "set" and "not set"
# are the same row, and an inherited value never applies. An inheriting field has no default at all: a new row
# does not carry it, a read gives `None`, and the value in `inherit` is only the LAST link of the chain, taken
# at the moment of use by whoever resolves it (`SharedView.effective` in М12; the resource's own fallback for
# retention). `merge` says what a set value does to an inherited one: `override` (the default) replaces it,
# `union` adds to it — a list of alarm kinds the site declares, plus the unit's own.
@dataclass
class Field:
    name: str
    type: str = "string"          # string | int | float | bool | list | url | blob | json
    default: object = None
    required: bool = False
    inherit: object = None        # the fallback of an inheriting field; see `inherits`
    inherits: bool = False
    merge: str = "override"       # override | union — for an inheriting field
    bound_to: tuple = ()          # a `*_secret` field: the fields it is the key to (`unbound_secret`)
    # `fixed: true` — set when the unit is created and never changed after, by anybody, deleted or not (a tombstone
    # keeps it: the name comes back for the same value only). The field a unit is ABOUT another by (`about.field`)
    # is the case that needs it: the gate asks about the unit the row names NOW, and a row that could be pointed
    # elsewhere would take its history with it (the review's fourth pass, when the rule was written into this
    # controller under one subsystem's field name; the boundary's step 2 made it the spec's word).
    fixed: bool = False
    # `enum: [a, b]` — the values the field may hold (the product's `FieldSpec.Enum`): anything else is refused on create
    # and update (400, the values named), and `/spec` carries the list for the page's form. A scalar field's, checked at
    # load with its default among them.
    enum: tuple = ()
    # A `url` field's own words (the boundary's step 4, the keys agreed with the product): `schemes` — what it may be
    # reached by, and how each writes its address (`{<scheme>: {host?, fragment?, none?}}`, `{}` by RFC 3986; ADR 0053;
    # none said: any, each by RFC 3986); `credentials` — `{login: <field>, secret: <a *_secret field>}`, where a login and a
    # password go instead, named by every refusal; `rules` — its `secret_in` read (`secrets.SecretRules`): how its
    # addresses carry a login besides what RFC 3986 says. None for a field that is no url.
    schemes: dict = field(default_factory=dict)
    credentials: dict = field(default_factory=dict)
    rules: object = None
    # WHAT A FIELD POINTS AT, AND WHAT IS ONE PER CLUSTER (the boundary's step 6: what a subsystem's refusal of a row said
    # in code, said here). `ref: <sub>/<rows>` — the value names the row `<sub>/<rows>/<value>` (a table of a spec, or
    # its units); `must_match: {<their field>: <my field>}` — when that row holds a value in `<their field>`, this row's
    # `<my field>` is the same, and a row there that does not parse is no row to point at: refused. A row that is not
    # there asks nothing — what is not declared yet binds nothing. `unique: true` — no other unit holds the same value;
    # `unique: canonical` (a url) — nor the same address in its one spelling (`canonical_url`). Both asked when the
    # value is new to the row: a create, or an edit that changes it — rows that were doubles before stay editable.
    ref: str = ""
    must_match: dict = field(default_factory=dict)
    unique: str = ""
    # `schema: {…}` — what the field's value may BE, as JSON Schema (`schema.py`; the boundary's step 6, the owner's
    # decision 3): checked at the door on the value as it parses — a `json` field's document, an `int`'s number — for
    # every writer, in the schema's words. What a value may MEAN beyond its shape is the subsystem's worker's to say.
    schema: object = None

    # Why a url field may not store `value` as typed, None when it may: a login or a credential anywhere in it, by the
    # platform's one rule (`secrets.address_fault`) and THIS field's `secret_in`; the words name the field its
    # `credentials` gives what was found — a password the secret's, a login with no password the login's — and never
    # the value. An `@` where no address reads one — a value with no `://`, or before its first — first, in the same
    # words (`secrets.opaque_fault`; ADR-0053, addendum of 2026-10-06): `KEY:pw@store.example/…` was taken as opaque
    # and shown whole, and a local path's `@` is written `%40`.
    def refusal(self, value) -> str | None:
        got = opaque_fault(str(value)) or address_fault(str(value), self.rules)
        if not got:
            return None
        why, kinds = got
        login, secret = self.credentials.get("login"), self.credentials.get("secret")
        if "secret" in kinds and secret:
            instead = (f"Put the login in {login} and the password or token in {secret}" if "login" in kinds and login
                       else f"Put the password or token in {secret}")
        elif "secret" not in kinds and login:
            instead = f"Put the login in {login}"
        else:
            instead = "A login and a password go in fields of their own"
        return (f"{self.name} may not be stored as typed: {why}. {instead} — an address is shown on every page and in "
                f"what leaves the cluster; a secret has a field of its own, sealed")

    # Convert an item string or JSON value to the typed value; `None` gives the default. Bools accept a real
    # bool or the string `"true"`; lists accept a list or a comma-separated string.
    def parse(self, v):
        if self.inherits and (v is None or v == ""):
            return None                                  # not set: the value is whatever is inherited
        if v is None:
            return self.default_value()
        if self.type == "int":
            return int(v)
        if self.type == "float":
            return float(v)
        if self.type == "bool":
            return v if isinstance(v, bool) else str(v).lower() == "true"
        if self.type == "list":
            return list(v) if isinstance(v, (list, tuple)) else [x for x in str(v).split(",") if x]
        # A small structured value, stored as compact JSON and handed back parsed. The fifth subsystem
        # needed it and none of the four before it did, which is the bar: a scenario's triggers are a
        # LIST OF SHAPES, and flattening that into fields would either cap it at one trigger or invent
        # `when_1_sub`, `when_2_sub` — a schema pretending not to be one.
        #
        # What the platform checks is exactly what it can: valid JSON, and small. What the shapes MEAN is
        # the subsystem's, checked in its own controller before the row is written, the way a subsystem
        # checks a row of its own table. A generic loader that tried to validate a trigger would be a generic loader
        # that knows what a trigger is.
        if self.type == "json":
            return parse_json(v) if isinstance(v, (str, bytes)) else v
        return str(v)

    # A value as a body or a caller gives it (`parse` reads a stored item): a `json` field takes it AS IT IS — a string is
    # a document that is a string, never JSON text read again (the architect with «Паритет», 2026-10-06, (б): reading a
    # text box is the page's work before it sends; the double reading reached a 500 on `"\"s\""`); the rest as `parse`.
    def take(self, v):
        if self.type == "json" and v is not None and not self.inherits:
            return v
        return self.parse(v)

    # The declared default, else the type's zero (`0`, `0.0`, `False`, `[]`, `""`).
    def default_value(self):
        if self.inherits:
            return None
        if self.default is not None:
            return self.default
        return {"int": 0, "float": 0.0, "bool": False, "list": [], "json": None}.get(self.type, "")

    # The Variables form: bools as `"true"/"false"`, lists comma-joined, else `str`. A `json` field is its value's canonical
    # text (`canonical.py`: sorted keys, `5` for `5.0` — the product's `CanonicalJSON`, the architect 2026-10-05); a string
    # is a document that is a string (`"s"` is written `"\"s\""`), as `take` holds it.
    def to_item(self, v) -> str:
        if self.type == "bool":
            return "true" if v else "false"
        if self.type == "list":
            return ",".join(v)
        if self.type == "json":
            return canonical_json(v)
        return str(v)


# The fields of a unit's row — or of a table's (`tables.py`) — as written: types, defaults, `required`, `inherit`, `fixed`,
# `bound_to`, a url's words, `ref`/`must_match`/`unique`, `schema`; each checked at load, `where` naming whose they are.
# …and a field's `type` is one of these, nothing else (ADR-0012; the fifteenth review, minor 16): `type: text` was read as
# a string, the word a promise nobody keeps.
FIELD_TYPES = ("string", "int", "float", "bool", "list", "json", "blob", "url")


def read_fields(where: str, raw: dict) -> dict:
    for n, f in raw.items():
        if isinstance(f, dict) and f.get("type", "string") not in FIELD_TYPES:
            raise ValueError(f"{where}: field {n}: `type` is one of {', '.join(FIELD_TYPES)}, not {f['type']!r}")
    fields = {n: Field(n, f.get("type", "string"), f.get("default"), bool(f.get("required", False)),
                       f.get("inherit"), "inherit" in f, f.get("merge", "override"), _bound_to(n, f.get("bound_to")),
                       f.get("fixed", False) is True)
              for n, f in raw.items()}
    for n, f in raw.items():
        if "fixed" in f and not isinstance(f["fixed"], bool):
            raise ValueError(f"field {n}: `fixed` is true or false, not {f['fixed']!r}")
    for n, f in raw.items():
        if "enum" in f:
            vals = f["enum"]
            if fields[n].type in ("list", "json", "blob") or not isinstance(vals, list) or not vals \
                    or not all(isinstance(x, (str, int, float, bool)) for x in vals):
                raise ValueError(f"field {n}: `enum` is a list of the values a {fields[n].type} field may hold, not "
                                 f"{vals!r}")
            fields[n].enum = tuple(fields[n].parse(x) if fields[n].type != "string" else str(x) for x in vals)
        _url_words(fields, n, f, where)
        _ref_words(fields, n, f)
        if "schema" in f:
            from . import schema as _schema
            fields[n].schema = _schema.load(f["schema"], f"{where}: field {n}: schema")
    for f in fields.values():
        if f.bound_to and not is_secret_field(f.name):
            raise ValueError(f"field {f.name}: `bound_to` is a secret's — the address it is the key to; "
                             f"{f.name} is no `*_secret`")
        stray = [b for b in f.bound_to if b not in fields or b == f.name or is_secret_field(b)]
        if stray:
            raise ValueError(f"field {f.name}: `bound_to` names no field of this unit that is an address: {stray}")
        if f.inherits and f.default is not None:
            raise ValueError(f"field {f.name}: `default` and `inherit` — a field is either filled in when the row "
                             f"is created or left for somebody above to set, not both")
        if f.merge not in ("override", "union"):
            raise ValueError(f"field {f.name}: merge is override or union, not {f.merge!r}")
        if f.default is not None:
            f.default = f.parse(f.default) if f.type != "string" else str(f.default)
            if f.enum and f.default not in f.enum:
                raise ValueError(f"field {f.name}: its default {f.default!r} is none of its `enum` {list(f.enum)}")
        if f.inherits and f.inherit is not None:
            f.inherit = Field(f.name, f.type).parse(f.inherit) if f.type != "string" else str(f.inherit)
    return fields


def _table_names(d: dict) -> tuple:
    from .tables import parse
    return parse(d.get("name"), d.get("tables"), lambda t, raw: read_fields(f"spec {d.get('name')}: tables.{t}", raw))[0]


# `bound_to:` as written — a name or a list of names — as a tuple of names; anything else refused at load.
def _bound_to(name: str, v) -> tuple:
    if v is None:
        return ()
    names = [v] if isinstance(v, str) else v
    if not isinstance(names, (list, tuple)) or not names or not all(isinstance(x, str) and x for x in names):
        raise ValueError(f"field {name}: `bound_to` is a field name or a list of them, not {v!r}")
    return tuple(names)


# A second row the platform keeps beside the unit: `row` (a path template under the prefix with `{id}`, e.g.
# `retention/{id}`), `items` (`{item name: field name}` — which unit field feeds each item), `on_delete`
# (what the row becomes when the unit is deleted; `None` leaves it alone). testsub2's derived row makes
# `keep_days` visible to the resource as `testsub2/retention/<id> {days}` and sets `{days: 0}` on
# delete so the buckets go at the next pass.
@dataclass
class Derived:
    row: str                      # under the subsystem's prefix, with {id}
    items: dict                   # item -> field
    on_delete: dict | None = None # what the row becomes when the unit is deleted (None: left alone)


# `events.suppress` parsed into `{kind: Suppress}`. `by` left out means every field of the line, which is
# the reading that cannot lose an observation — see `Suppressor` in `events.py`. Read leniently HERE and
# refused in `from_dict`: parsing says what was written, the checks say whether it may be used, and keeping
# the two apart is what lets a refusal name the number it objects to.
def suppress_rules(events: dict) -> dict[str, Suppress]:
    out: dict[str, Suppress] = {}
    for kind, rule in (events.get("suppress") or {}).items():
        rule = rule or {}
        by = rule.get("by")
        out[str(kind)] = Suppress(str(kind), float(rule.get("window", 0) or 0),
                                  tuple(str(b) for b in by) if by is not None else None)
    return out


# `fields.<name>` of `type: url` — `schemes`, `credentials`, `secret_in` (the boundary's step 4) — read into the field;
# on a field of any other type they are refused, and so is a `credentials` naming no field of the row, a login that is a
# secret or a secret that is not one.
def _url_words(fields: dict, name: str, f: dict, where: str) -> None:
    fld = fields[name]
    said = [k for k in ("schemes", "credentials", "secret_in") if k in f]
    if fld.type != "url":
        if said:
            raise ValueError(f"field {name}: {', '.join(said)} belong to a url field, and {name} is {fld.type}")
        return
    schemes = f.get("schemes", {})
    why = schemes_fault(schemes)
    if why:
        raise ValueError(f"field {name}: `schemes` {why}")
    cred = f.get("credentials") or {}
    if not isinstance(cred, dict) or set(cred) - {"login", "secret"}:
        raise ValueError(f"field {name}: `credentials` is {{login: <field>, secret: <a *_secret field>}}, not {cred!r}")
    login, secret = cred.get("login"), cred.get("secret")
    if login is not None and (login not in fields or is_secret_field(login) or fields[login].type != "string"):
        raise ValueError(f"field {name}: credentials.login names no string field of the row that is no secret: {login!r}")
    if secret is not None and (secret not in fields or not is_secret_field(secret)):
        raise ValueError(f"field {name}: credentials.secret names no `*_secret` field of the row: {secret!r}")
    fld.schemes = {k: dict(v) for k, v in schemes.items()}
    fld.credentials = {k: v for k, v in (("login", login), ("secret", secret)) if v}
    # …and with none of its own, the loaded specs' together (`catalog.secret_rules`, read when it is asked): a url field
    # that says nothing of how its addresses carry a login is asked every way any subsystem here says one is carried
    fld.rules = SecretRules.parse(f["secret_in"], f"{where}: field {name}") if "secret_in" in f else None


# `fields.<name>.ref`, `must_match`, `unique` — read into the field, refused at load when they say nothing that can be
# asked: a `ref` that is no `<sub>/<rows>`, a `must_match` without a `ref` or naming no field of this row, a `unique`
# that is neither `true` nor `canonical` (and `canonical` only of a url).
def _ref_words(fields: dict, name: str, f: dict) -> None:
    from .doors import safe_segment
    fld = fields[name]
    ref = f.get("ref")
    if ref is not None:
        parts = ref.split("/") if isinstance(ref, str) else []
        if len(parts) != 2 or not all(safe_segment(p) for p in parts):
            raise ValueError(f"field {name}: `ref` is <sub>/<rows> — the family of rows its value names — not {ref!r}")
        fld.ref = ref
    mm = f.get("must_match")
    if mm is not None:
        if not fld.ref:
            raise ValueError(f"field {name}: `must_match` compares the row `ref` names, and {name} has no `ref`")
        if not isinstance(mm, dict) or not mm or not all(isinstance(k, str) and k and isinstance(v, str) and v in fields
                                                         for k, v in mm.items()):
            raise ValueError(f"field {name}: `must_match` is {{<their field>: <a field of this row>}}, not {mm!r}")
        fld.must_match = dict(mm)
    u = f.get("unique")
    if u is not None and u is not False:
        if u is True:
            fld.unique = "true"
        elif u == "canonical" and fld.type == "url":
            fld.unique = "canonical"
        else:
            raise ValueError(f"field {name}: `unique` is true, or `canonical` for a url field, not {u!r}")


# `placement.capacity: {from, default}` — `(from, default)`. The default is REQUIRED (the product's decision): the
# number a worker that has said nothing yet is counted at is the subsystem's to say — fifty of one kind of unit is a
# small worker and of another an impossible one — and a spec without it does not load.
def _capacity(name, cap) -> tuple[str, int]:
    if not isinstance(cap, dict) or set(cap) - {"from", "default"} or "default" not in cap:
        raise ValueError(f"spec {name}: placement.capacity is {{from: <heartbeat field>, default: <units a worker that "
                         f"said nothing is counted at>}} — the default is the subsystem's to say, not {cap!r}")
    d = cap["default"]
    if isinstance(d, bool) or not isinstance(d, int) or d < 0:
        raise ValueError(f"spec {name}: placement.capacity.default is a whole number of units, not {d!r}")
    return str(cap.get("from", "capacity") or "capacity"), d


# `placement.unplaced: {delete_after: <whole seconds, 1 or more>}` — how long a unit nobody holds stands before its
# controller deletes it (ADR-0067; the form «Платформа»'s). Without the key nothing is deleted; `0`, a fraction, a
# word, `true`, or another key under `unplaced` does not load (ADR-0012). `60.0` is sixty: YAML's number, whole.
def _unplaced(name, v) -> int:
    d = v.get("delete_after") if isinstance(v, dict) and set(v) == {"delete_after"} else None
    whole = not isinstance(d, bool) and (isinstance(d, int) or (isinstance(d, float) and d.is_integer() and abs(d) <= 1 << 31))
    if not whole or d < 1:
        raise ValueError(f"spec {name}: placement.unplaced is {{delete_after: <whole seconds, 1 or more>}} — how long a "
                         f"unit nobody holds is kept before the controller deletes it — not {v!r}")
    return int(d)


# `slot: {prefix, name_env}` — `(prefix, name_env)`; left out, `w` and `WORKER_NAME`.
def _slot(name, slot) -> tuple[str, str]:
    if slot is None:
        return "w", "WORKER_NAME"
    if not isinstance(slot, dict) or set(slot) - {"prefix", "name_env"}:
        raise ValueError(f"spec {name}: `slot:` is {{prefix: <letters>, name_env: <VARIABLE>}}, not {slot!r}")
    prefix, env = str(slot.get("prefix", "w")), str(slot.get("name_env", "WORKER_NAME"))
    if not re.fullmatch(r"[a-z]{1,8}", prefix):
        raise ValueError(f"spec {name}: slot.prefix names a slot `<prefix>-<n>` — a few small letters, not {prefix!r}")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", env):
        raise ValueError(f"spec {name}: slot.name_env is an environment variable's name, not {env!r}")
    return prefix, env


# `objects: {rows: […], door: […]}` — the patterns, each a key under the subsystem's name: names separated by `/`, a
# segment `*`. `rows`: the objects that are rows of the store, never files; `door`: the files of its that a resource's
# door gives the other servers (`resource.door_readable`; the product's key) — any other file of its is read on the server
# that wrote it alone. The platform's own families (`resource.PLATFORM_DOOR`: heartbeats, contenders, used, snapshot,
# controller, blobs) are not a spec's to name, nor every family at once.
PLATFORM_FAMILIES = ("heartbeats", "contenders", "used", "snapshot", "controller", "blobs")
PLATFORM_ROWS = ("heartbeats", "contenders", "snapshot", "controller", "blobs", "commands")   # the product's, as it is


def _object_patterns(name, objects, family: str) -> tuple:
    if objects is None:
        return ()
    if not isinstance(objects, dict) or not objects or set(objects) - {"rows", "door"} \
            or not all(isinstance(v, list) for v in objects.values()):
        raise ValueError(f"spec {name}: `objects:` is {{rows: [<key pattern>, …], door: [<key pattern>, …]}}, not "
                         f"{objects!r}")
    out = []
    for p in objects.get(family) or []:
        segs = str(p).split("/")
        if not p or any(not x or x == ".." or ("*" in x and x != "*") for x in segs):
            raise ValueError(f"spec {name}: objects.{family} takes key patterns under the subsystem's name — names "
                             f"separated by '/', a whole segment '*' — not {p!r}")
        if family == "rows" and segs[0] == "commands":
            raise ValueError(f"spec {name}: objects.rows: {p!r} is the platform's family — a request's marks are rows for "
                             f"every spec with `requests:` (`catalog.rows_of`), and a spec does not name them")
        # …nor any other family of the platform's own, nor every one (the fifteenth review, minor 16: `heartbeats/*` loaded
        # as rows of the store the platform keeps as files; the product refused it, `objectPatternFault`, by this list).
        # `used` is not in it: the door gives a resource's `used/*` out unasked, and a subsystem keeps its own `used/*` as rows.
        if family == "rows" and segs[0] in ("*", *PLATFORM_ROWS):
            raise ValueError(f"spec {name}: objects.rows: {p!r} names a family of the platform's own "
                             f"({', '.join(PLATFORM_ROWS)}) or every one — the platform keeps those itself")
        if family == "door" and segs[0] in ("*", *PLATFORM_FAMILIES):
            raise ValueError(f"spec {name}: objects.door: {p!r} names a family of the platform's own "
                             f"({', '.join(PLATFORM_FAMILIES)}) or every one — a door gives those out unasked")
        out.append(str(p))
    return tuple(out)


def _object_rows(name, objects) -> tuple:
    return _object_patterns(name, objects, "rows")


# `heartbeat: {strings: [<field>]}` — the fields of this subsystem's heartbeats that are strings by contract and that
# something decides by (the product's key: the field it places by, say — the place a worker is counted in). A heartbeat
# in which one of them is not a string is garbled — skipped and counted, as one that does not parse
# (`contract.parse_heartbeat`): a reader that keyed or compared by it raised, or took `5` for a place. The platform's
# own (`worker`, `server`, `url`, `instance`, `labels`, `fetched` — the requests a holder took, which the platform's
# clearing reads, `requests.py` — and `events`, where a worker's journal goes, the product's base says it for every
# subsystem) are not a spec's to say: a spec that declared one would collide with the platform's word unseen
# («Архитектор» 2026-10-07, ADR-0019; the product's `PlatformHeartbeatStrings`, 47efbf2).
PLATFORM_HEARTBEAT_STRINGS = ("worker", "server", "url", "instance", "labels", "fetched", "events")


def _heartbeat_strings(name, hb) -> tuple:
    if hb is None:
        return ()
    got = hb.get("strings") if isinstance(hb, dict) and set(hb) == {"strings"} else None
    if not isinstance(got, list) or not got:
        raise ValueError(f"spec {name}: `heartbeat:` is {{strings: [<a field of its heartbeats>, …]}}, not {hb!r}")
    word = re.compile(r"[a-z][a-z0-9_]*")
    for i, f in enumerate(got):
        if not isinstance(f, str) or not word.fullmatch(f) or f in PLATFORM_HEARTBEAT_STRINGS or f in got[:i]:
            raise ValueError(f"spec {name}: heartbeat.strings: {f!r} is no field of its own heartbeats (the "
                             f"platform's are {', '.join(PLATFORM_HEARTBEAT_STRINGS)}), or is said twice")
    return tuple(got)


# `lease: {unconfirmed_max: forever | off | <seconds>}` — how long past a lease's end a holder of this subsystem may go
# on WRITING DATA while the store is silent (`Lease.may_write`; the architect, 5 Oct: a weakening of the single writer
# is off until the spec turns it on). `forever` — for as long as the silence lasts: what its units write carries the
# epoch in its name, and a second writer is a duplicate, not damage; `<seconds>` — up to that long; `off` (the default)
# — not at all: a lease not confirmed in time stops the unit — where the work is actions, done twice if done by two.
# Typed (ADR-0012; «Архитектор», 2026-10-06, after the fourteenth review): `forever`, `off`, or a WHOLE number of seconds
# above 0 — one thing, one spelling. Not `0` (zero seconds is `off`), not `"90"` (a word lifted the ceiling unseen in
# the product), not `1e308` or `90.5`, not `false`/`no`/`OFF` — a spec is YAML 1.2 (`specyaml.py`), where `off` is the
# word itself and no boolean — and not an empty `lease:`: a key said says something.
LEASE_WORDS = {"forever": None, "off": 0.0}


def _lease(name, lease, said: bool = False) -> float | None:
    if lease is None and not said:
        return 0.0
    got = lease.get("unconfirmed_max") if isinstance(lease, dict) and set(lease) == {"unconfirmed_max"} else None
    if isinstance(got, str) and got in LEASE_WORDS:
        return LEASE_WORDS[got]
    if isinstance(got, int) and not isinstance(got, bool) and got > 0:
        return float(got)
    raise ValueError(f"spec {name}: lease.unconfirmed_max is forever, off or a whole number of seconds above 0 — "
                     f"`lease:` is {{unconfirmed_max: forever | off | <seconds>}}, not {lease!r}")


# `secrets: {readers: {<row or prefix>: [<role>]}, reads: [<row or prefix>]}` — the product's key, the course checks it:
# which roles read a secret row of this subsystem's (its console's door seed, `door/signer`), and the rows of somebody
# else's its worker reads. The course's rights are the grants the specs make (`w2cplatform/cluster/rights.py`), so the
# declaration is a promise held to them: the rights file is not generated while any role reads a declared row and is
# not named, or is named and does not read it (`cluster.rights.check_secrets`). A role is one of `SECRET_ROLES`:
# `controller`, `worker` and `domainpart` (its worker on the domain, the role `<sub>domain`) are the subsystem's own;
# `domainconsole` is the domain's console, its own identity on the holder's store (ADR-0032). The list is a shared table
# of parity, as the platform's heartbeat strings are (`tests/testdata/platform_lists.tsv`; ADR-0019, its addition of
# 2026-10-10): one set on both sides, the product's `known.go`.
SECRET_ROLES = ("console", "controller", "worker", "domainpart", "domain", "domainagent", "resource", "domainconsole")
_SECRET_ROW = re.compile(r"[a-z0-9_][a-z0-9_.\-]*(/[a-z0-9_.\-]+)*/?")


def _secrets(name, sec) -> tuple[dict, tuple]:
    if sec is None:
        return {}, ()
    readers, reads = (sec.get("readers", {}), sec.get("reads", [])) if isinstance(sec, dict) else (None, None)
    if not isinstance(sec, dict) or not sec or set(sec) - {"readers", "reads"} or not isinstance(readers, dict) \
            or not isinstance(reads, list):
        raise ValueError(f"spec {name}: `secrets:` is {{readers: {{<row or prefix>: [<role>]}}, reads: [<row or "
                         f"prefix>]}}, not {sec!r}")
    for row in [*readers, *reads]:
        if not isinstance(row, str) or not _SECRET_ROW.fullmatch(row) or ".." in row:
            raise ValueError(f"spec {name}: secrets names {row!r}, which is no key of the store nor a prefix of keys "
                             f"(`door/signer`, `domain/<sub>/accounts/`)")
    for row, roles in readers.items():
        if not isinstance(roles, list) or not roles or not all(r in SECRET_ROLES for r in roles):
            raise ValueError(f"spec {name}: secrets.readers.{row} is a list of roles — {', '.join(SECRET_ROLES)} — "
                             f"not {roles!r}")
    return {k: tuple(v) for k, v in readers.items()}, tuple(reads)


# `worker: {writes: [<table>], reads: [<key>], requests: [<sub>]}` — what this subsystem's WORKER may touch beyond its
# epochs, its slot and its place (`Subsystem.acl_worker`): rows of its own tables it writes (what it found a thing to
# be — a discovery, not a decision), keys of the store outside its subsystem it reads, and the subsystems whose
# request rows it files. What the role of every process is comes from the specs (§3 row 8 of the boundary note): the
# box's tokens (`SubsystemSpec.acl_worker_role`) and the cluster's rights file (`w2cplatform/cluster/rights.py`) alike.
def _worker(name, worker) -> tuple[tuple, tuple, tuple]:
    if worker is None:
        return (), (), ()
    if not isinstance(worker, dict) or set(worker) - {"writes", "reads", "requests"} \
            or any(not isinstance(worker.get(k, []), list) for k in worker):
        raise ValueError(f"spec {name}: `worker:` is {{writes: [<table>], reads: [<key>], requests: [<sub>]}}, "
                         f"not {worker!r}")
    word = re.compile(r"[a-z][a-z0-9_]*")
    for k in ("writes", "requests"):
        bad = [x for x in worker.get(k) or [] if not word.fullmatch(str(x))]
        if bad:
            raise ValueError(f"spec {name}: worker.{k} takes names, not {bad}")
    # …and the subsystems it files to are others (ADR-0012, ADR-0054; the fifteenth review, minor 10): a worker performs its
    # own units' work and files to the rest. The other two faults — a name of no subsystem, one that takes no request —
    # need the catalogue whole, and are asked where it is (`catalog.requests_known`, as `near_known`).
    if name in [str(x) for x in worker.get("requests") or []]:
        raise ValueError(f"spec {name}: worker.requests names {name!r}, which is the spec itself — a worker performs its "
                         f"own units' work, it files to others")
    bad = [x for x in worker.get("reads") or [] if not re.fullmatch(r"[a-z][a-z0-9_]*(/[a-z0-9_*.-]+)+", str(x))]
    if bad:
        raise ValueError(f"spec {name}: worker.reads takes keys of the store (`<family>/<name>`), not {bad}")
    return tuple(map(str, worker.get("writes") or ())), tuple(map(str, worker.get("reads") or ())), \
        tuple(map(str, worker.get("requests") or ()))


# The parsed YAML. Fields: `name`; `rows` (`"units"`; testsub says `counters`); `id` (`"numeric"` or a field
# name); `fields`; `derived`; `capacity_from` / `capacity_default` (heartbeat key for a worker's capacity,
# and the number for a worker that said nothing); `headroom_from`; `constraint`; `tie_break` (only
# `most-free-capacity` exists); `dead_band`; `snapshot` (field names); `running_gauge` (`console.running`: the name
# of one of its own `metrics`, the gauge of units running; empty when the spec says none).
_DOMAIN_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_DOMAIN_KEYS = ("ref", "view", "reports", "witness", "books", "kept", "tables", "tokens", "keys", "shared", "names",
                "edit")
_RESERVED_CLAIMS = ("iss", "sub", "iat", "exp", "jti", "kind")
# A book's name and a shown field's: the product's `domainNameRe`, the one rule of `domain.books` on both sides.
_BOOK_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _q(s: str) -> str:
    """A name quoted as the product's `%q` quotes it — so a refusal reads the same on both sides."""
    import json
    return json.dumps(s, ensure_ascii=False)


def _v(x) -> str:
    """A value as the product's `%v` writes it, near enough to read the same: nothing is `<nil>`, a list `[a b]`."""
    if x is None:
        return "<nil>"
    if isinstance(x, list):
        return "[" + " ".join(_v(i) for i in x) + "]"
    if isinstance(x, dict):
        return "map[" + " ".join(f"{k}:{_v(i)}" for k, i in sorted(x.items(), key=lambda kv: str(kv[0]))) + "]"
    if isinstance(x, bool):
        return "true" if x else "false"
    return str(x)
# What a family's names may be held apart from (`domain.names.<family>.exclusive_with`): the domain's people — the
# grants' other subjects. A closed set, as every word of the section (ADR-0031).
EXCLUSIVE_WITH = ("domain/users",)


# THE SUBSYSTEM ON THE DOMAIN, DECLARED (the boundary's «no hooks», DOMAIN-PLATFORM.md: the domain is the platform's,
# and what a subsystem brings to it is a declaration the platform reads, never code it calls). Every name below is a
# row family under the subsystem's own prefix of the domain, `domain/<sub>/…` (`SubsystemSpec.domain_prefix`).
#
#   ref       the field of a unit's row that names it in the domain: the units of this subsystem are in the domain's
#             directory, found across clusters by it. A field of the snapshot — the directory reads nothing else
#   view      the fields of a unit the holder's shared view shows beside the platform's own (cluster, server, worker,
#             phase, age): fields of the snapshot too, for the same reason
#   reports   objects of this subsystem a member reports to the domain beside its heartbeats and snapshot, which every
#             subsystem's member reports (`<sub>/<name>`, a prefix when it ends in `/`)
#   witness   `{report, member_field}`: an object family `<sub>/<report>/*` — `{ts, cluster, units: {<name>: seconds
#             since}}` — saying when a member's unit was last heard of by another process than its agent: the domain's
#             word "alive, not reporting". `member_field` is the field of the unit, `fixed: true` in `fields:`, that
#             carries the member's name: the witness names what it heard of by it, and the domain matches a silent
#             member by its own name — no word of the subsystem's, no name of one turned into another (ADR-0010)
#   books     rows the subsystem writes at the holder for each member, `domain/<sub>/<book>/<member>`, which that
#             member's agent carries home as `domain/<sub>/<book>` without reading them; a `*_secret` field in a book
#             (at the top of the row, or of a JSON object that is one of its values) travels sealed. A list of names,
#             or a map `{<book>: {} | {show: [<field>…]}}`: `show` names the fields of the book's entries (each item a
#             JSON object) a page is given at `GET /domain/<sub>/books/<book>` — of this cluster's own copy, never
#             another member's, an item to whoever may view the unit whose `domain.ref` is its key (`console.py`,
#             `SpecConsole.book_route`); a book without it is carried and not shown (ADR-0010, the addition of
#             2026-10-06; the product's `domainBooks`, word for word)
#   kept      rows the subsystem keeps at the holder for the domain as a whole, `domain/<sub>/<name>`, which leave the
#             holder in its backup with what the domain decided; a name ending in `/` is a FAMILY of rows,
#             `domain/<sub>/<name>/<row>` — one row per thing, kept, backed up and denied to the agent alike
#   names     `{<kept family>/: {exclusive_with: domain/users, grant: <grant>}}` — the family's rows are SUBJECTS of the
#             grants, beside the domain's people: a row's name may not be a person's, nor a person's a row's — the
#             platform refuses the write of either side that would make them meet; and a grant to such a subject is no
#             wider than `grant` (one of the platform's, `access.RANK`) — a write of grants above it is refused
#             (`domain.declared.refusal`, asked of every write of the holder's store as the platform opens it)
#   tables    the kept rows the domain's door serves read-only at `/domain/<sub>/<table>`
#   tokens    the kinds of token the books carry: `{<kind>: {lifetime: <seconds>, claims: [<name>, ...]}}`; the domain's
#             signer issues them, of those claims only, when the subsystem's worker asks (`trust.tokens.DeclaredIssuer`).
#             A token carries no rights: what its subject may do is the grants'
#   edit      the fields of a unit the domain's door lets into an edit of a member's row: any other is refused there by
#             the spec, before the member is asked. Not said: the member's console decides
#   keys      the subsystem's key families, for a page that lists the domain's keys (the domain card's «Ключи»):
#             `[{id, keys: [<exact key>], prefix: "domain/<sub>/…/"}]` — the composition only, every key under the
#             subsystem's own prefix; the words are `display.keys: {<id>: {title, about, absent}}`, merged by id on the
#             page. The platform's own families (members, reaches, topology, pending, outcomes, view) the page names
#             itself; a key in no family is «other». The platform acts on none of it: it passes it through `/spec`
#   shared    the unit's fields whose domain-wide value the domain holds (the shared document, `domain/shared.py`):
#             a field that `inherit`s — the domain's value is the middle link of its chain (the unit's, the
#             domain's, the spec's), `merge: union` adding to the unit's own — or the field the page groups units by
#             (`display.tree.group_by`) — the domain's value is the groups it offers, never a unit's value. The
#             platform resolves them and serves them at one door, `GET /domain/shared/<sub>`. An entry may also be a
#             DOCUMENT the domain holds whole, no unit's field: `{name, type: json, schema}` — its value is checked by
#             its schema where it is signed (ADR-0010, ADR-0032: the signer's `shared` is one operation over whatever
#             the specs declare, by their schemas, and knows no field by its meaning)
@dataclass
class DomainSection:
    ref: str = ""
    view: tuple = ()
    reports: tuple = ()
    witness: str = ""             # `witness.report`: the object family `<sub>/<report>/*`
    member_field: str = ""        # `witness.member_field`: the unit's fixed field that carries the member's name
    books: tuple = ()             # the names: a list's in its order, a map's sorted
    show: dict = field(default_factory=dict)        # {<book>: (<field>…)} — the books shown, each its fields (`_books`)
    kept: tuple = ()
    tables: tuple = ()
    tokens: dict = field(default_factory=dict)
    keys: tuple = ()
    shared: tuple = ()
    documents: dict = field(default_factory=dict)   # {<name>: Field} — the `shared` entries that are documents (json)
    names: dict = field(default_factory=dict)       # {<kept family>/: {exclusive_with, grant?}}
    edit: tuple = ()

    def family_of(self, key: str) -> str | None:
        """The id of the first declared family `key` falls into — an exact key, or under a prefix — or None."""
        for f in self.keys:
            if key in f["keys"] or (f["prefix"] and key.startswith(f["prefix"])):
                return f["id"]
        return None

    @classmethod
    def read(cls, spec: "SubsystemSpec", d) -> "DomainSection | None":
        if d is None:
            return None
        where = f"spec {spec.name}: domain"
        if not isinstance(d, dict) or set(d) - set(_DOMAIN_KEYS):
            raise ValueError(f"{where} takes {', '.join(_DOMAIN_KEYS)} — not {d!r}")

        def names(key: str, tail: bool = False) -> tuple:
            v = d.get(key) or []
            if not isinstance(v, list):
                raise ValueError(f"{where}.{key} is a list of names")
            for n in v:
                body = n[:-1] if tail and isinstance(n, str) and n.endswith("/") else n
                if not isinstance(body, str) or not _DOMAIN_NAME.match(body):
                    raise ValueError(f"{where}.{key}: {n!r} is not a name (lower case, digits, - and _)")
            if len(set(v)) != len(v):
                raise ValueError(f"{where}.{key} names one thing twice")
            return tuple(v)
        sec = cls(ref=str(d.get("ref") or ""), view=names("view"), reports=names("reports", tail=True),
                  kept=names("kept", tail=True), tables=names("tables"))
        sec.books, sec.show = cls._books(d.get("books"), where)
        sec.witness, sec.member_field = cls._witness(spec, d.get("witness"), where)
        for f in ([sec.ref] if sec.ref else []) + list(sec.view):
            if f not in spec.snapshot and f != "id":
                raise ValueError(f"{where}: {f!r} is not in the snapshot — the domain reads a unit from the snapshot "
                                 f"and nothing else")
        both = set(sec.books) & {k.rstrip("/") for k in sec.kept}
        if both:
            raise ValueError(f"{where}: {sorted(both)} both a book and a kept row — one writer's rows, one shape")
        stray = [t for t in sec.tables if t not in sec.kept]       # a family is no table: the door serves one row
        if stray:
            raise ValueError(f"{where}.tables names rows that are not kept: {stray}")
        sec.names = cls._names(spec, d.get("names"), sec.kept, where)
        tokens = d.get("tokens") or {}
        if not isinstance(tokens, dict):
            raise ValueError(f"{where}.tokens is {{<kind>: {{lifetime, claims}}}}")
        for kind, t in tokens.items():
            if not isinstance(kind, str) or not _DOMAIN_NAME.match(kind) or kind == "person":
                raise ValueError(f"{where}.tokens: {kind!r} is not a kind a subsystem may declare ('person' is the "
                                 f"platform's)")
            if not isinstance(t, dict) or set(t) - {"lifetime", "claims"}:
                raise ValueError(f"{where}.tokens.{kind} is {{lifetime: <seconds>, claims: [<name>, ...]}} — a token "
                                 f"carries no rights")
            life = t.get("lifetime")
            if isinstance(life, bool) or not isinstance(life, (int, float)) or not math.isfinite(life) or life <= 0:
                raise ValueError(f"{where}.tokens.{kind}.lifetime is a positive number of seconds, not {life!r}")
            claims = t.get("claims") or []
            if not isinstance(claims, list) or not all(isinstance(c, str) and c and c not in _RESERVED_CLAIMS
                                                       for c in claims):
                raise ValueError(f"{where}.tokens.{kind}.claims is a list of claim names, none of {_RESERVED_CLAIMS}")
            sec.tokens[kind] = {"lifetime": float(life), "claims": tuple(claims)}
        sec.keys = cls._families(spec, d.get("keys"), where)
        sec.shared, sec.documents = cls._shared(d.get("shared"), where)
        sec.edit = names("edit")
        for f in sec.edit:
            if f not in spec.fields:
                raise ValueError(f"{where}.edit: {f!r} is not a field of the unit")
            if is_secret_field(f):
                raise ValueError(f"{where}.edit: {f!r} is a secret — a password is set in the unit's own cluster, never "
                                 f"through the domain, which keeps, backs up and relays its edits")
        grouped = ((spec.display or {}).get("tree") or {}).get("group_by") if isinstance(spec.display, dict) else None
        for f in sec.shared:
            if f in sec.documents:
                if f in spec.fields:
                    raise ValueError(f"{where}.shared: {f!r} is a field of the unit — a document the domain holds "
                                     f"whole is no unit's: name it otherwise, or share the field by its name")
                continue
            fld = spec.fields.get(f)
            if fld is None:
                raise ValueError(f"{where}.shared: {f!r} is not a field of the unit")
            if f.endswith("_secret"):
                raise ValueError(f"{where}.shared: {f!r} is a secret — the shared document is signed, not sealed")
            if not fld.inherits and f != grouped:
                raise ValueError(f"{where}.shared: {f!r} neither inherits nor is the field the page groups by "
                                 f"(display.tree.group_by) — a domain value it would have nowhere to go")
        return sec

    @staticmethod
    def _books(v, where: str) -> tuple[tuple, dict]:
        """`domain.books`: a list of names — carried, none shown — or a map, each book `{}` or `{show: [<field>…]}`.
        `(names, {<book>: (<field>…)})`. Nothing is guessed: a book with no value, an empty `show`, a secret named or a
        key beside `show` is refused, with its path — the product's `domainBooks`, its words, so a spec of either side
        loads, or is refused, alike on both (ADR-0012)."""
        where += ".books"
        out: list = []
        show: dict = {}

        def name(n) -> None:
            n = n if isinstance(n, str) else ""
            if not _BOOK_NAME.match(n):
                raise ValueError(f"{where}: {_q(n)} is not a name (lower case, digits, - and _)")
            if n in out:
                raise ValueError(f"{where} names {_q(n)} twice")
            out.append(n)
        if v is None:
            return (), show
        if isinstance(v, list):
            for x in v:
                name(x)
            return tuple(out), show
        if isinstance(v, dict):
            for b in sorted(v, key=str):
                name(b)
                at = f"{where}.{b}"
                book = v[b]
                if not isinstance(book, dict):
                    raise ValueError(f"{at} takes {{}} (carried, not shown) or {{show: [<field>…]}} — not {_v(book)}")
                for k in book:
                    if k != "show":
                        raise ValueError(f"{at}.{k}: unknown key")
                if "show" not in book:
                    continue
                raw = book["show"]
                if not isinstance(raw, list) or not raw:
                    raise ValueError(f"{at}.show names the fields of the book's entries a page is given, at least one — "
                                     f"not {_v(raw)} (a book not shown says no show)")
                fields: list = []
                for x in raw:
                    f = x if isinstance(x, str) else ""
                    if not _BOOK_NAME.match(f):
                        raise ValueError(f"{at}.show: {_q(f)} is not a field's name (lower case, digits, - and _)")
                    if is_secret_field(f):
                        raise ValueError(f"{at}.show: {_q(f)} is a secret, and a secret is never shown")
                    if f in fields:
                        raise ValueError(f"{at}.show names {_q(f)} twice")
                    fields.append(f)
                show[b] = tuple(fields)
            return tuple(out), show
        raise ValueError(f"{where} is a list of names or a map {{<book>: {{}} | {{show: [<field>…]}}}}, not {_v(v)}")

    @staticmethod
    def _witness(spec: "SubsystemSpec", raw, where: str) -> tuple[str, str]:
        """`witness: {report, member_field}` — `(report, member_field)`, or `("", "")` when the spec says none. The
        field is the unit's, declared `fixed: true`: a name that could be changed would move what was heard of to
        another member. A field that is not declared so, and the spec does not load (ADR-0010)."""
        if raw is None:
            return "", ""
        shape = "{report: <the object family>, member_field: <the unit's fixed field that carries the member's name>}"
        if not isinstance(raw, dict) or set(raw) != {"report", "member_field"}:
            raise ValueError(f"{where}.witness is {shape}, not {raw!r}")
        report, member = raw["report"], raw["member_field"]
        if not isinstance(report, str) or not _DOMAIN_NAME.match(report):
            raise ValueError(f"{where}.witness.report: {report!r} is not a name")
        f = spec.fields.get(member) if isinstance(member, str) else None
        if f is None or not f.fixed:
            raise ValueError(f"{where}.witness.member_field: {member!r} is not a field of the unit declared "
                             f"`fixed: true` — the witness names a member by it, and a name that changes names another")
        return report, member

    @staticmethod
    def _shared(raw, where: str) -> tuple[tuple, dict]:
        """`shared: [<field>, {name, type: json, schema}, …]` — the names in order, and the documents among them as
        fields of type json with their schemas (checked as schemas here, `schema.load`)."""
        from . import schema as _schema
        v = raw or []
        if not isinstance(v, list):
            raise ValueError(f"{where}.shared is a list of the unit's fields and of {{name, type: json, schema}}")
        out, docs = [], {}
        for n in v:
            if isinstance(n, dict):
                if set(n) != {"name", "type", "schema"} or n.get("type") != "json":
                    raise ValueError(f"{where}.shared: {n!r} is not {{name, type: json, schema}} — a document the "
                                     f"domain holds is JSON, and what it may be is its schema")
                name = n["name"]
                if not isinstance(name, str) or not _DOMAIN_NAME.match(name) or name.endswith("_secret"):
                    raise ValueError(f"{where}.shared: {name!r} is not a name, or is a secret — the shared document is "
                                     f"signed, not sealed")
                docs[name] = Field(name, "json", schema=_schema.load(n["schema"], f"{where}.shared.{name}: schema"))
                out.append(name)
            elif isinstance(n, str) and _DOMAIN_NAME.match(n):
                out.append(n)
            else:
                raise ValueError(f"{where}.shared: {n!r} is not a name (lower case, digits, - and _)")
        if len(set(out)) != len(out):
            raise ValueError(f"{where}.shared names one thing twice")
        return tuple(out), docs

    @staticmethod
    def _names(spec: "SubsystemSpec", raw, kept: tuple, where: str) -> dict:
        """`names: {<kept family>/: {exclusive_with: domain/users, grant: <grant>}}` — a family this spec keeps whose
        rows are subjects of the grants beside the domain's people (a subsystem's accounts): held apart from them, and
        granted no wider than `grant`."""
        from .access import RANK
        if raw is None:
            return {}
        shape = f"{{<kept family>/: {{exclusive_with: {'|'.join(EXCLUSIVE_WITH)}, grant: {'|'.join(RANK)}}}}}"
        if not isinstance(raw, dict):
            raise ValueError(f"{where}.names is {shape}")
        out = {}
        for name, rule in raw.items():
            if not isinstance(name, str) or not name.endswith("/") or name not in kept:
                raise ValueError(f"{where}.names: {name!r} is not a family this spec keeps (`domain.kept` with a "
                                 f"trailing `/`: {[k for k in kept if k.endswith('/')]})")
            if not isinstance(rule, dict) or "exclusive_with" not in rule or set(rule) - {"exclusive_with", "grant"}:
                raise ValueError(f"{where}.names.{name} is {shape}, not {rule!r}")
            if rule["exclusive_with"] not in EXCLUSIVE_WITH:
                raise ValueError(f"{where}.names.{name}.exclusive_with is one of {list(EXCLUSIVE_WITH)}, not "
                                 f"{rule['exclusive_with']!r}")
            if "grant" in rule and rule["grant"] not in RANK:
                raise ValueError(f"{where}.names.{name}.grant is one of the platform's grants ({', '.join(RANK)}), "
                                 f"not {rule['grant']!r}")
            out[name] = dict(rule)
        return out

    @staticmethod
    def _families(spec: "SubsystemSpec", raw, where: str) -> tuple:
        own = spec.domain_prefix
        shape = f"{{id, keys: [<key>], prefix: '{own}…/'}} — the family's keys; its words are display.keys.<id>"
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise ValueError(f"{where}.keys is a list of {shape}")
        out, seen = [], set()
        for f in raw:
            if not isinstance(f, dict) or set(f) - {"id", "keys", "prefix"} or not isinstance(f.get("id"), str) \
                    or not _DOMAIN_NAME.match(f["id"]):
                raise ValueError(f"{where}.keys: {f!r} is not {shape}")
            if f["id"] in seen:
                raise ValueError(f"{where}.keys names the family {f['id']!r} twice")
            seen.add(f["id"])
            exact, prefix = f.get("keys") or [], f.get("prefix") or ""
            if not isinstance(exact, list) or not all(isinstance(k, str) and k.startswith(own) and len(k) > len(own)
                                                      and not k.endswith("/") for k in exact):
                raise ValueError(f"{where}.keys.{f['id']}.keys are keys under {own!r}, not {exact!r} — the platform's "
                                 f"own families are the page's")
            if prefix and (not isinstance(prefix, str) or not prefix.startswith(own) or not prefix.endswith("/")
                           or len(prefix) <= len(own)):
                raise ValueError(f"{where}.keys.{f['id']}.prefix is a prefix under {own!r} ending in '/', not {prefix!r}")
            if not exact and not prefix:
                raise ValueError(f"{where}.keys.{f['id']} names no key: give keys, a prefix, or both")
            out.append({"id": f["id"], "keys": tuple(exact), "prefix": prefix})
        return tuple(out)


@dataclass
class SubsystemSpec:
    name: str
    rows: str = "units"
    id: str = "numeric"           # numeric, or the field whose value is the id
    fields: dict[str, Field] = field(default_factory=dict)
    derived: list[Derived] = field(default_factory=list)
    capacity_from: str = "capacity"
    capacity_default: int = 50    # `placement.capacity.default`: a worker that has said nothing yet (the spec must say it)
    unplaced_delete_after: int = 0   # `placement.unplaced.delete_after`: a unit nobody holds that long goes (0: never; ADR-0067)
    headroom_from: str = "headroom"
    constraint: str = "none"
    requires: str = "none"        # "resource": a worker is eligible only while its server's resource is not silent
    servers: str = "shared"       # the default of the `servers` policy knob: shared | distinct (the console may change it)
    tie_break: str = "most-free-capacity"
    near: str = "none"            # a subsystem whose worker holding the same unit id this one prefers to be beside (an affinity, never a filter)
    # WHICH unit of that subsystem. `id` — the same unit id, which is what `near: <sub>` means, and all a pair
    # of subsystems needs while their units are named alike. A subsystem whose units are named for something
    # else has to say so: a unit called `7-a` is not one the other subsystem ever reports, and `near: <sub>` on
    # it would match nothing — an affinity that reads as followed and is not. So `near: {sub: <sub>, by:
    # <field>}` — follow the worker holding the unit my `<field>` names.
    near_by: str = "id"
    # `near: {sub: <sub>, of: <field>}` — WHAT OF THEIRS the value is matched against. `by` says which value of
    # MINE to look for (my id, or a field of my row); `of` says where in THEIR status to look for it (their
    # unit id by default, or a field they report). The two are independent, and the second arrived when their
    # units stopped being named by what they are about: "the worker running a unit whose `<field>` is 7"
    # holds whether the operator called that unit `7`, `7-b` or `lobby`, while "the worker running unit `7`"
    # was only ever true by coincidence — and silently false when the coincidence ended.
    #
    #   near: {sub: B, of: f}           my id (7)        vs their `f`     — whoever runs a unit about me
    #   near: {sub: B, by: f, of: f}    my field `f`     vs their `f`     — likewise, for a pair about one thing
    #   near: {sub: B, by: g}           my field `g`     vs their id      — I name their unit
    #
    # The field is read from the heartbeat STATUS (`status_extra` puts it there), not from the other
    # subsystem's rows, which this controller has no business reading. Several of their units may answer —
    # two copies kept of one unit — and then the affinity takes the smallest of their ids, so two passes
    # over the same heartbeats reach the same server. Being beside one of them is the point; the other
    # reads the same fan-out over the network.
    near_of: str = ""
    # `home: <field>` — the server named in that field of the unit's own row is where it prefers to run;
    # `home: near` — wherever the subsystem this one follows is. A PREFERENCE and not a label: a label is a
    # filter, and a unit whose home is down would become unplaceable — the one thing it must not be,
    # because the home being down is exactly when the work has to continue somewhere else. It is topology,
    # not taste: the home of a unit that writes is the disk it writes to. Coming home is then not a procedure but
    # a consequence, bounded by `ensure_home`.
    home: str = ""
    # `spread_by: <field>` — units sharing a value of that field go on DIFFERENT servers. Unlike `near` this
    # is a FILTER, not a preference: the whole point of a second copy is that it is not where the first one
    # is, and a second copy on the same server is not a second copy. Unplaceable while no other server
    # qualifies, and that is the honest answer — `/unplaceable` says so rather than quietly co-locating.
    spread_by: str = ""
    # `group_by: <name>` — the mirror image, and the one a subsystem needed first: units sharing a value go on
    # the SAME worker. Also a FILTER, for a reason that is not about preference at all — a box at the far end
    # is ONE connection. Sixteen channels of one box are sixteen units, and placing them on four workers
    # opens four sessions to a box that licenses two; the subsystem then fails in the box's words
    # ("too many sessions"), which is the hardest kind of failure to trace back to a placement decision.
    #
    # What the value is: the field of this name, or — `group_by: {field: <a url field>, cut_at: host}` — the HOST that
    # address names, in its one spelling (`url_host`): `x://H:8/a/17` and `y://h./b/18` are one group, whatever the
    # scheme, the port or the path; and how a scheme writes its host when it does not follow RFC 3986 the spec declares
    # (`schemes`, the closed dictionary `GROUP_SCHEME_WORDS`; «Архитектор», 2026-10-06). Or — `cut_at: <segment>` — the
    # address in its one spelling up to that segment of its path (`url_cut`). It was a subsystem's code overriding
    # `group_value`, which parsed the address in its own words (the boundary's step 6); the platform reads the address by
    # RFC 3986 and the declaration, and nothing else.
    #
    # Where it hurts, and it does: the worker holding the group is not chosen for its room. A group that
    # outgrows its worker becomes unplaceable rather than spilling over, because spilling over is the
    # thing being prevented. The operator raises that worker's capacity or moves the group — `/unplaceable`
    # names the group, so the answer is on the screen rather than in a session count on the far end.
    group_by: str = ""
    group_cut: str = ""           # `group_by.cut_at`: `host`, or the segment the url field's spelling is cut before
    # `near: {…, prefer: {<their field>[.<field of the row it refs>]: <value or values>}}` — when `near` finds SEVERAL
    # units of the followed subsystem (two of theirs about one of mine), the one to stand beside: the one whose row says
    # so — read through their field's `ref` when the key has a dot (`home.kind`: the `kind` of the row their `home`
    # names). Those first, the rest after; ties by their id, so two passes agree. It was a subsystem's ranking code.
    # Their spec is the process's catalogue's: with `near.of` or `near.prefer`, a neighbour it does not hold is refused
    # where the catalogue is whole (`catalog.near_known`, ADR 0056).
    near_prefer: dict = field(default_factory=dict)
    # `placement.affinity: {field, table, server_field, strict}` — a row of this subsystem's `table` (one of `tables:`),
    # named in the unit's `field`, may BIND: when the row matches `strict` (every key of it, the row's value one of the
    # values; no `strict` — every row binds), the unit goes only to the place that row is — the worker whose place
    # (`place_by`) is the row's name, on the server the row's `server_field` names when it names one — and that place
    # takes no unit homed elsewhere. A place whose row says `admits: false` takes no unit at all, and the live worker on
    # it gives up the units it has (`admitting_none`, in `leaving`; ADR 0056). A FILTER, beside the
    # labels and `spread_by`, so it beats `home` and `near` the way they do; what a place IS, the rows say. It was a
    # subsystem's admit code (the boundary's step 6).
    affinity: dict = field(default_factory=dict)
    # `place_by: <field>` — WHAT the policy and the home are counted in: the heartbeat field that names the
    # place a worker occupies. `server` by default, and for everything whose unit of storage is a server
    # that is the truth. A writer's is not: a box with three disks runs three of its workers, one per disk,
    # and `servers: distinct` has to mean one per DISK — two workers on one disk are no second place to
    # write, while two on one server with different disks are exactly that.
    #
    # Only the policy and `home` follow this field. Reachability (`requires: resource`), draining and
    # `spread_by` stay on the server, because those are about a machine: a volume has no address, cannot be
    # drained on its own, and two copies on two disks of one server survive nothing the operator was buying
    # insurance against.
    place_by: str = "server"
    # `offers: true` — this subsystem's controller offers a slot to a SPARE for every worker it is short of
    # (`SpecController.offer_spares`), named `<slot.prefix>-<n>` like the slots its workers make, and its console
    # publishes `<name>_workers_needed` and the rest. False (the default): no offers.
    offers: bool = False
    # `places: {table, where, server_field}` — for a subsystem placed by something other than the server (`place_by`): the
    # rows of one of its tables a worker would hold, one each (`<name>/holds/<row>`). Its console publishes
    # `<name>_workers_needed` from them: the rows that say `where` and no live hold names, less the live workers that
    # hold no place (they would take one) — what a host's spares script starts processes for; a place nobody CAN take
    # does not become takeable by starting processes, and one spare running proves the shortage is not of processes.
    # The number was one subsystem's metric with an operator of its own (`minus: placeless`); now it is the platform's
    # for any `place_by`. `server_field`: the field of the row naming the server the place is on — a row that names
    # none is a place ANY box may write (a share), and a hold of it under a worker's name is taken back at once only on
    # the holder's own box (`Worker.hold_follows_name`); one that names a server is a disk there, taken back at once only
    # on that server. No `server_field`: where a place is is not known, and a hold never follows the name — it waits.
    # The table is also what `/where/<table>/<place>` asks a place's holder by (`SpecConsole.where_place`). `lease:
    # strict` — a place ANY box may write (no server named) is let go when its hold has gone unconfirmed past its
    # end, whatever `lease.unconfirmed_max` lets the units write: two writers in one place is damage, not a duplicate
    # (the architect, 5 Oct: it is about the place, not the unit). Said or not, `places["lease"]` is `strict` or "".
    places: dict = field(default_factory=dict)
    # `lease: {unconfirmed_max}` (`_lease`): the ceiling a holder's data writes past an unconfirmed lease, in seconds;
    # None — for as long as the silence lasts; 0 — none (`Worker.unconfirmed_max`, `Lease.may_write`)
    unconfirmed_max: float | None = 0.0
    # `retire_when: {field: state, in: [done, failed]}` — a unit whose row says one of those values is
    # FINISHED, and finished work is not placed. The first subsystem to need it was one of jobs, whose unit
    # ends; everything before it ran until an operator said stop.
    #
    # Not `enabled`. That field is read by workers, never here: a disabled unit keeps its assignment and
    # its line in the console's list, and a unit that has to STAY VISIBLE while doing nothing is a
    # different thing from one that is over. Saying which field and which values, per subsystem, is the
    # difference between the two — and it is the row that says it, not a heartbeat: un-placing a finished
    # unit makes its worker drop it, which makes the heartbeat stop mentioning it, which would erase the
    # only evidence it was ever finished. It would then be placed again, and start over, for ever.
    retire_field: str = ""
    retire_values: tuple = ()
    dead_band: float = 0.10
    snapshot: list[str] = field(default_factory=list)
    # `tables:` — row families this subsystem's CONSOLE owns besides its units, by name, from either form below. Not
    # units: nothing is placed on them, they have no epoch and no worker; they are the administrator's lists, like
    # `policy` but plural and named. Each gains the console's token `<name>/<table>/*`; a name may not be one of the
    # platform's own families (`servers`, `policy`, `slots`, … — refused at load).
    tables: tuple[str, ...] = ()
    # `tables: {<name>: {key, fields, schema, stamp, journal}}` — the tables whose rows the console SERVES (`tables.py`;
    # the boundary's step 6: they were a subsystem's routes on the platform's console). A table named in the list form
    # is a family the console's token may write, and nothing serves it.
    table_specs: dict = field(default_factory=dict)
    # `rights:` beyond `unit_of` (the boundary's step 6, §4 `rights: {routes, unit_of}`; it was a subsystem's code in
    # the console — `EDIT_ROUTES`, `VIEW_POSTS`, `CLUSTER_ROWS`, `moved_units`, `body_units` set by a subsystem's wiring):
    #   routes: {view: [<family>], edit: [<family>]}   a write to one of this subsystem's families (its rows, a table)
    #                                                 that needs less than `admin`: asking to watch, a keep set
    #   cluster_rows: true                            a write to one of its units is the whole cluster's business
    #   reach: {group: [<field>], cluster: [<field>], requests: [<action>]}
    #                                                 what a change reaches beyond the unit: every unit of the group a
    #                                                 change of these fields leaves and joins (`placement.group_by` — a
    #                                                 group no other unit is in yet is the cluster's); the cluster, for
    #                                                 these; every unit of its unit's group, for a request of these
    #   names: [{field, unit, sub | of}]              the units a row names inside a json field (`then[].unit` of the
    #                                                 subsystem `sub` says) — what moving one of them to another group
    #                                                 answers for
    route_caps: dict = field(default_factory=dict)
    cluster_rows: bool = False
    reach: dict = field(default_factory=dict)
    names: tuple = ()
    # `requests: {schema, valid_for, most_valid, per_person, settle, ttl, key, stamp, journal, free}` — the console's
    # `POST /requests` of this subsystem (`SpecConsole._request_route`; the boundary's step 6: it was a subsystem's
    # route, `extra`): the body's shape, how long a request is worth doing (`valid_until`), how many one person may
    # have unanswered, how it is named (a template of its fields, or the `Idempotency-Key`), what the console stamps
    # on it (`by`, `at`, its unit's `group`, the field its unit is `about`), the journal's line; `elsewhere` — the
    # actions of this family another process turns into work (not the unit's holder): the reaper leaves them to it
    # (`requests.clear_requests`). The holder performs the rest (`Worker.requests`), and `most_valid` bounds its wait.
    requests: dict = field(default_factory=dict)
    running_gauge: str = ""                  # `console: {running: <a metric of its own>}`: the gauge the page reads
    # `events: {older_epochs: fenced | earlier-run}` — what it MEANS that a unit's events were written
    # under an epoch that is not the current one.
    #
    # `fenced` (the default, and right for everything that runs until stopped): a writer that lost the
    # race and kept writing. The page strikes those events through, because they are a zombie's.
    #
    # `earlier-run`: the same mechanism, the opposite meaning. A unit whose work ENDS takes a new epoch
    # every time the operator runs it again, so an older epoch is a finished earlier result — a run to
    # compare against, not a loser to strike through. Marking it `fenced` would tell an operator that the
    # search they ran last week was never valid.
    older_epochs: str = "fenced"
    # `events: {suppress: {<kind>: {window: <seconds>, by: [<field>, …]}}}` — which of this subsystem's
    # event kinds collapse when they repeat, and what counts as a repeat.
    #
    # A storm is normal, not a fault, and the only place a repeat costs nothing to recognise is the writer
    # (`Suppressor`, `events.py`). The subsystem declares it because the timescale belongs to the event:
    # a door contact bounces in milliseconds, a motion sensor re-reports for as long as the scene moves,
    # a link flaps for as long as the cable is bad. The platform holds none of those numbers.
    #
    # `by` defaults to every field of the line, which is the reading that cannot lose an observation: two
    # lines collapse only when they are identical. A subsystem narrows it when a field drifts for a reason
    # that is not a new observation.
    suppress: dict[str, "Suppress"] = field(default_factory=dict)
    # `about: {sub: <another subsystem>, field: <a field of the row>}` — every unit of this subsystem is ABOUT one unit
    # of another: the one whose id its row holds in that field (a tally is about its counter). What the platform
    # reads it for, and nothing else: an event of such a unit is also its about-unit's (the line's `of`, the index's
    # second column), a grant on the about-unit takes it in, and the labels a `labels:` grant is matched against are
    # the about-unit's — a unit's own labels say where it may run, not whose it is. Empty: about nothing but itself.
    # The field is `fixed`: what a unit is about does not change.
    about_sub: str = ""
    about_field: str = ""
    # `rights: {unit_of: {<table>: <field>}}` — a row of that table (one of `tables:`) belongs to the unit its field
    # names: a unit of the subsystem `about` names, or of this one without `about`; a value written `<sub>/<id>` is
    # taken as it is. Whoever writes the row needs on that unit what the route needs — on both, when a write moves
    # the row from one to another.
    unit_of: dict = field(default_factory=dict)
    # `objects: {rows: [commands/*]}` — the objects of this subsystem (`<name>/…`, glob by segment, a last `*` the rest)
    # that are rows of the store and not files: what must be created once across every server (a worker's mark before
    # it acts) or read where the place it names is gone. The cluster's object store asks the loaded specs for them
    # (`catalog.object_rows`; it was a constant of the platform's, naming one subsystem's family).
    object_rows: tuple = ()
    # `objects: {door: [...]}` — its files a resource's door gives the other servers (`catalog.door_objects`)
    object_door: tuple = ()
    # `heartbeat: {strings: [...]}` (`_heartbeat_strings`): read where a heartbeat is (`catalog.heartbeat_strings`)
    heartbeat_strings: tuple = ()
    # `secrets: {readers, reads}` (`_secrets`): held to the rights the specs make (`cluster.rights.check_secrets`)
    secret_readers: dict = field(default_factory=dict)
    secret_reads: tuple = ()
    # `slot: {prefix: w, name_env: WORKER_NAME}` — what a slot this subsystem's worker has to MAKE is called
    # (`<prefix>-<n>`), and the environment variable naming the slot it is started under beside `WORKER_NAME`
    # (`runtime.slot`). It was each worker's class saying it.
    slot_prefix: str = "w"
    slot_name_env: str = "WORKER_NAME"
    # `worker: {writes, reads, requests}` (`_worker`)
    worker_writes: tuple = ()
    worker_reads: tuple = ()
    worker_requests: tuple = ()
    # `metrics: [...]` — the subsystem's own numbers on `/metrics`, declared (`metrics.py`; the boundary's step 6 — it
    # was a function of the subsystem's the console called, `metrics_extra`).
    metrics: list = field(default_factory=list)
    # `display: {unit, units, units_count, section, general, fields, field_help, options, form, events, kinds, actions,
    # keys, tree}` (`DISPLAY_KEYS`, `TREE_KEYS`, `TREE_WORDS`) — what a page calls things; a dictionary the platform hands
    # to `/spec` and reads none of (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §6–§8), checked only that a word for a field names one.
    display: dict = field(default_factory=dict)
    # `servers: {show: [{table, by, title, columns}]}` — rows of this subsystem's tables a page shows under the server
    # their `by` field names (a disk under its server). Handed to `/spec`; it was a field the console's `/servers` read
    # out of one subsystem's heartbeat until the boundary's step 6.
    servers_show: list = field(default_factory=list)
    # `servers: {status: [{field, title, of?}]}` (`_servers_status`) — heartbeat fields a page shows on a server's row,
    # titled, and the table whose rows a map's keys are (`of`, ADR-0064)
    servers_status: list = field(default_factory=list)
    # `holds: {table, unit, since, until, longest}` — rows of a table that hold a unit's buckets on every resource past
    # their days (`holds.py`; it was a subsystem's function the resource called, `kept`).
    holds: dict = field(default_factory=dict)
    # `requests: {free: true}` — this subsystem's workers answer the resource's request to free bytes on a volume of
    # their server: `<sub>/requests/free-<server>-<volume> {free, volume, server, at}`, the answer in their heartbeat's
    # `freeing: {<volume>: bytes}` — deleted and not yet visible on the volume, taken off what is asked (`Resource.relieve`;
    # it was the subsystem's hook the resource called, `free`).
    requests_free: bool = False
    # `door: {routes: [<route>]}` — what a unit's holder opens to a page itself, the bytes going holder → browser and
    # never through the console (the boundary's step 6, the owner's decision 1): `/where/<id>` hands out the door —
    # the holder's `url`, a token for these routes (`door.py`). It was the console's `extra`, a subsystem's routes.
    door_routes: tuple = ()
    # `domain: {...}` — what this subsystem gives the domain above its clusters and takes from it (`DomainSection`; the
    # boundary's «no hooks»: it was code the domain called and named — the books, the rows a member carries, the fields
    # of the shared view, the kinds of token). None: the subsystem is not on the domain at all.
    domain: "DomainSection | None" = None

    @property
    def domain_prefix(self) -> str:
        """Where this subsystem's rows of the domain lie, in the holder's store and in a member's: `domain/<name>/`.
        Given by the platform, never written by the subsystem."""
        return f"domain/{self.name}/"

    # Builds the spec from the YAML dict, tolerating absent sections. Field defaults are parsed to their
    # type once here (strings kept as strings so `"u{id}"` survives). `snapshot` defaults to every field.
    @classmethod
    def from_dict(cls, d: dict) -> "SubsystemSpec":
        if not isinstance(d, dict):                     # a list, a word, an empty file: a refusal, never an AttributeError
            raise ValueError(f"a spec is a mapping of keys, not {type(d).__name__}")
        if d.get("name") in RESERVED_NAMES:
            raise ValueError(f"spec {d['name']}: `{d['name']}` is a name of the platform's own (one of "
                             f"{', '.join(sorted(RESERVED_NAMES))}), not a subsystem's")
        unit, pl = d.get("unit", {}), d.get("placement", {})
        fields = read_fields(f"spec {d.get('name')}", unit.get("fields") or {})
        derived = [Derived(x["row"], dict(x.get("items", {})), x.get("on_delete")) for x in unit.get("derived", [])]
        # `snapshot:` LEFT OUT means "every field that may go" — a convenience, not a decision.
        # `snapshot: []` means "no field of the row leaves the cluster", which is a decision. The two were
        # one thing here for as long as this read `list(d.get("snapshot", [])) or [every field]`: an empty
        # list is falsy, so a spec declaring "publish nothing" published everything, and its author would
        # have learned that from М12 rather than from the file they wrote.
        #
        # An empty list is not an empty object. `id`, `revision`, `worker` and `server` are structural and
        # go either way, because "which unit is where" is the snapshot's other job and the layer above is
        # built on it. What `[]` buys is that nothing an OPERATOR typed leaves the cluster.
        #
        # `snapshot:` with nothing after it is neither, so it is refused rather than guessed: the author
        # meant one of the two and the file does not say which.
        if "snapshot" in d and d["snapshot"] is None:
            raise ValueError(f"spec {d['name']}: `snapshot:` with nothing after it says neither — write "
                             f"`snapshot: []` for no fields, or leave the key out for every field")
        declared = d.get("snapshot")
        cap = pl.get("capacity")
        slot = _slot(d.get("name"), d.get("slot"))
        worker = _worker(d.get("name"), d.get("worker"))
        spec = cls(name=d["name"], rows=unit.get("rows", "units"), id=str(unit.get("id", "numeric")), fields=fields,
                   derived=derived,
                   headroom_from=(pl.get("headroom", {}) or {}).get("from", "headroom"),
                   constraint=pl.get("constraint", "none"), requires=str(pl.get("requires", "none")), servers=str(pl.get("servers", "shared")), tie_break=pl.get("tie_break", "most-free-capacity"),
                   near=str((pl.get("near") or {}).get("sub", "none") if isinstance(pl.get("near"), dict) else pl.get("near", "none")),
                   near_by=str((pl.get("near") or {}).get("by", "id") if isinstance(pl.get("near"), dict) else "id"),
                   near_of=str((pl.get("near") or {}).get("of", "") if isinstance(pl.get("near"), dict) else ""),
                   spread_by=str(pl.get("spread_by", "") or ""),
                   group_by=str((pl.get("group_by") or {}).get("field", "") if isinstance(pl.get("group_by"), dict)
                                else pl.get("group_by", "") or ""),
                   group_cut=str((pl.get("group_by") or {}).get("cut_at", "") or "") if isinstance(pl.get("group_by"), dict) else "",
                   place_by=str(pl.get("place_by", "server") or "server"),
                   offers=pl.get("offers", False),
                   home=str(pl.get("home", "") or ""),
                   retire_field=str((pl.get("retire_when") or {}).get("field", "") or ""),
                   retire_values=tuple(str(v) for v in ((pl.get("retire_when") or {}).get("in") or [])),
                   dead_band=float((pl.get("rebalance", {}) or {}).get("dead_band", 0.10)),
                   snapshot=(list(declared) if declared is not None else
                             [n for n, f in fields.items() if not is_secret_field(n) and f.type != "blob"]),
                   tables=_table_names(d),
                   running_gauge=str((d.get("console", {}) or {}).get("running", "") or ""),
                   older_epochs=str((d.get("events", {}) or {}).get("older_epochs", "fenced")),
                   suppress=suppress_rules(d.get("events", {}) or {}),
                   object_rows=_object_rows(d.get("name"), d.get("objects")),
                   object_door=_object_patterns(d.get("name"), d.get("objects"), "door"),
                   heartbeat_strings=_heartbeat_strings(d.get("name"), d.get("heartbeat")),
                   secret_readers=_secrets(d.get("name"), d.get("secrets"))[0],
                   secret_reads=_secrets(d.get("name"), d.get("secrets"))[1],
                   unconfirmed_max=_lease(d.get("name"), d.get("lease"), "lease" in d),
                   slot_prefix=slot[0], slot_name_env=slot[1],
                   worker_writes=worker[0], worker_reads=worker[1], worker_requests=worker[2])
        spec._about_and_rights(d)
        spec._placement_words(pl)
        spec._page_words(d)
        spec._fields_named()
        spec.domain =DomainSection.read(spec, d.get("domain"))
        words = set((spec.display.get("keys") or {}) if isinstance(spec.display, dict) else {})
        stray = words - {f["id"] for f in (spec.domain.keys if spec.domain else ())}
        if stray:
            raise ValueError(f"spec {spec.name}: display.keys gives words to {sorted(stray)}, which domain.keys does not "
                             f"declare — words for a family nobody composed")
        if not isinstance(spec.offers, bool):
            raise ValueError(f"spec {spec.name}: placement.offers is true or false — the slots offered are named by "
                             f"`slot.prefix` — not {spec.offers!r}")
        # A secret in the snapshot is a secret leaving the cluster: `<name>/snapshot/*` is what М12's directory
        # reads. Refused at LOAD time, not watched for at review time — and only when it is named, because
        # the default ("every field") is a convenience and not a decision.
        # A table's name becomes a key family and an ACL prefix, so it is a name and not a path, and it may
        # not be the unit rows under another spelling — two writers on one family with different rules.
        for t in spec.tables:
            if not t or "/" in t or t in (spec.rows, "policy", "slots", "holds", "epoch", "idem", "requests", "asked", "servers", "decommissioned"):
                raise ValueError(f"spec {spec.name}: `tables:` takes a fresh row family name, not {t!r}")
        leaks = [n for n in spec.snapshot if is_secret_field(n)]
        if leaks:
            raise ValueError(f"spec {spec.name}: a secret may not be in the snapshot: {leaks} — "
                             f"the snapshot is what leaves the cluster")
        # A blob is the one field that is certainly too big for the snapshot, and the snapshot is one
        # object per worker with a ceiling over it. Refused at LOAD time for the same reason a secret is:
        # by the time someone notices the snapshot stopped publishing, М12 has been stale for a while.
        heavy = [n for n, f in fields.items() if f.type == "blob" and n in spec.snapshot]
        if heavy:
            raise ValueError(f"spec {spec.name}: a blob may not be in the snapshot: {heavy} — the snapshot "
                             f"is one object per worker under a ceiling, and a blob is what does not fit "
                             f"in a row in the first place")
        unknown_snap = [n for n in spec.snapshot if n not in fields]
        if unknown_snap:
            raise ValueError(f"spec {spec.name}: snapshot names no field: {unknown_snap}")
        if spec.older_epochs not in ("fenced", "earlier-run"):
            raise ValueError(f"spec {spec.name}: events.older_epochs is fenced or earlier-run, "
                             f"not {spec.older_epochs!r} — the page draws one of the two")
        # Suppression drops observations, so its declaration is refused at LOAD time rather than read
        # leniently. A window of zero is the shape a typo takes (`window: 0`, a missing key, a string
        # that did not parse), and reading it as "no suppression" would leave a subsystem believing it
        # had some. The fields naming what repeats are names, never a path or the reserved words the
        # summary line itself carries.
        for r in spec.suppress.values():
            if r.window <= 0:
                raise ValueError(f"spec {spec.name}: events.suppress.{r.kind}.window is seconds and must be "
                                 f"positive, not {r.window!r} — a kind with no window is a kind not listed here")
            if r.by is not None and not r.by:
                raise ValueError(f"spec {spec.name}: events.suppress.{r.kind}.by is empty — every line of "
                                 f"{r.kind} would then be the same thing. Leave `by` out for every field, "
                                 f"or name the fields that decide sameness")
            for b in r.by or ():
                if not b or "/" in b or b in ("repeats", "since", "until"):
                    raise ValueError(f"spec {spec.name}: events.suppress.{r.kind}.by names {b!r} — a field "
                                     f"name, and not one the summary line writes itself")
        if spec.retire_field and spec.retire_field not in fields:
            raise ValueError(f"spec {spec.name}: retire_when names no field: {spec.retire_field!r}")
        if bool(spec.retire_field) != bool(spec.retire_values):
            raise ValueError(f"spec {spec.name}: retire_when needs both a field and a non-empty `in` — "
                             f"a predicate that matches nothing retires nothing, silently")
        if spec.near_by != "id" and spec.near_by not in fields:
            raise ValueError(f"spec {spec.name}: near.by names no field: {spec.near_by!r}")
        if spec.near_by != "id" and spec.near == "none":
            raise ValueError(f"spec {spec.name}: near.by needs a near to follow")
        if spec.group_by and spec.group_by == spec.spread_by:
            raise ValueError(f"spec {spec.name}: `group_by` and `spread_by` name the same field "
                             f"({spec.group_by!r}): together they say units must be on one worker and on "
                             f"different servers")
        if spec.near_of and spec.near == "none":
            raise ValueError(f"spec {spec.name}: near.of needs a near to follow")
        # `of` names a field of the OTHER subsystem's status, which this loader cannot see — nothing to
        # check here. A name that matches nothing behaves like an affinity that finds no holder: units are
        # placed by the filters alone, `_pick` says so in its reason, and nobody is refused.
        if spec.home == "near" and spec.near == "none":
            raise ValueError(f"spec {spec.name}: home: near needs a near to follow")
        if spec.home and spec.home != "near" and spec.home not in fields:
            raise ValueError(f"spec {spec.name}: home names no field: {spec.home!r}")
        # …and what names a unit, a field of its row or a number the console counts (ADR-0012; the fifteenth review, minor
        # 16): `id: nosuch` loaded, and every create answered "a unit needs a nosuch" — no unit was ever made.
        if spec.id != "numeric" and spec.id not in fields:
            raise ValueError(f"spec {spec.name}: unit.id is `numeric` or a field of the row "
                             f"({', '.join(fields) or 'none'}), not {spec.id!r}")
        # …the capacity of a worker that said nothing: the spec's to say (`_capacity`).
        spec.capacity_from, spec.capacity_default = _capacity(spec.name, cap)
        # …how long a unit nobody holds stands before its controller deletes it (`_unplaced`; ADR-0067)
        if "unplaced" in pl:
            spec.unplaced_delete_after = _unplaced(spec.name, pl["unplaced"])
        # …a key nobody above read: refused, named where it stands (`speckeys.py`).
        from .speckeys import refuse_unknown
        refuse_unknown(spec.name, d)
        # …and, the last thing asked, the key beside rows the console derives: it writes and cleans those, and the
        # controller writes no row but its own (ADR-0067, the refinement of window 17)
        if spec.unplaced_delete_after and spec.derived:
            raise ValueError(f"spec {spec.name}: placement.unplaced.delete_after with unit.derived — the controller "
                             f"deletes a unit and cannot clean its derived rows, which are the console's")
        # …and only where a name holds nothing to keep (ADR-0067, the addendum of 2026-10-10; the fifteenth review, minor 1):
        # the console deletes a unit by a tombstone that keeps its `fixed` fields, and a create under the name with another
        # `about` is refused; the controller deletes the row outright, and never writes one, so it can leave no tombstone.
        # A unit with no fixed field but its id and about nothing but its id (`live/streams/<cam>`: name and subject one)
        # may be deleted so; any other would have its name reused with another meaning — its buckets, marks and grants
        # read as the new unit's history.
        if spec.unplaced_delete_after and (
                any(f.fixed and n != spec.id for n, f in spec.fields.items())
                or (spec.about_sub and spec.about_field != spec.id)):
            raise ValueError(f"spec {spec.name}: placement.unplaced.delete_after with fixed fields or about — a deleted "
                             f"name would be reused with another meaning; say no delete_after")
        return spec

    # `about:` and `rights:` as written, checked at load: `about` names another subsystem by a name and a field of this
    # row, which is `fixed` (said in the file, not assumed); `rights.unit_of` names this spec's own tables and a field
    # each. Anything else is refused here, before a console reads a row by it.
    def _about_and_rights(self, d: dict) -> None:
        about = d.get("about")
        if about is not None:
            from .doors import safe_segment
            sub, fld = (about.get("sub"), about.get("field")) if isinstance(about, dict) else (None, None)
            if not isinstance(sub, str) or not isinstance(fld, str) or not safe_segment(sub) or unnamable(sub) \
                    or sub == self.name or set(about) - {"sub", "field"}:
                raise ValueError(f"spec {self.name}: `about:` is {{sub: <another subsystem>, field: <a field of the "
                                 f"row>}}, not {about!r}")
            if fld not in self.fields:
                raise ValueError(f"spec {self.name}: about.field names no field: {fld!r}")
            if not self.fields[fld].fixed:
                raise ValueError(f"spec {self.name}: about.field {fld!r} is what a unit is about, and that does not "
                                 f"change — say `fixed: true` on it")
            self.about_sub, self.about_field = sub, fld
        rights = d.get("rights")
        if rights is None:
            return
        if not isinstance(rights, dict) or set(rights) - {"unit_of", "routes", "cluster_rows", "reach", "names"}:
            raise ValueError(f"spec {self.name}: `rights:` takes unit_of, routes, cluster_rows, reach, names — not {rights!r}")
        self._rights_words(rights)
        unit_of = rights.get("unit_of") or {}
        if not isinstance(unit_of, dict):
            raise ValueError(f"spec {self.name}: rights.unit_of is {{<table>: <field>}}, not {unit_of!r}")
        for table, fld in unit_of.items():
            if table not in self.tables:
                raise ValueError(f"spec {self.name}: rights.unit_of names {table!r}, which is not one of its tables")
            if not isinstance(fld, str) or not fld:
                raise ValueError(f"spec {self.name}: rights.unit_of.{table} names no field")
        self.unit_of = {str(t): str(f) for t, f in unit_of.items()}

    # `rights.routes`, `cluster_rows`, `reach`, `names` — read and checked at load (see the fields above).
    def _rights_words(self, rights: dict) -> None:
        routes = rights.get("routes") or {}
        families = (self.rows, *self.tables)
        if not isinstance(routes, dict) or set(routes) - {"view", "edit"} or \
                not all(isinstance(v, list) and all(x in families for x in v) for v in routes.values()):
            raise ValueError(f"spec {self.name}: rights.routes is {{view: [<family>], edit: [<family>]}} of its rows and "
                             f"tables ({', '.join(families)}), not {routes!r}")
        self.route_caps = {cap: tuple(str(x) for x in v) for cap, v in routes.items()}
        if not isinstance(rights.get("cluster_rows", False), bool):
            raise ValueError(f"spec {self.name}: rights.cluster_rows is true or false")
        self.cluster_rows = rights.get("cluster_rows", False)
        reach = rights.get("reach") or {}
        if not isinstance(reach, dict) or set(reach) - {"group", "cluster", "requests"} or \
                not all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in reach.values()) or \
                not set(reach.get("group", [])) | set(reach.get("cluster", [])) <= set(self.fields):
            raise ValueError(f"spec {self.name}: rights.reach is {{group: [<field>], cluster: [<field>], requests: "
                             f"[<action>]}}, not {reach!r}")
        self.reach = {k: tuple(v) for k, v in reach.items()}
        # a change of a `reach.group` field reaches the unit's GROUP: with no `placement.group_by` there is none to reach,
        # and the declaration would ask nothing (ADR 0012; the product's `reach-names`)
        if self.reach.get("group") and not self.group_by:
            raise ValueError(f"spec {self.name}: rights.reach.group names fields whose change reaches the unit's group, "
                             f"and the spec says no placement.group_by — there is no group to reach")
        names = rights.get("names") or []
        if not isinstance(names, list) or not all(
                isinstance(e, dict) and not set(e) - {"field", "unit", "sub", "of"} and e.get("field") in self.fields
                and isinstance(e.get("unit"), str) and (isinstance(e.get("sub"), str) != isinstance(e.get("of"), str))
                for e in names):
            raise ValueError(f"spec {self.name}: rights.names is [{{field: <a json field>, unit: <key>, sub: <key> | of: "
                             f"<subsystem>}}], not {names!r}")
        # …and a name is read from a `json` field: any other answered "*" for a text it could not read, hiding a typo
        wrong = [e["field"] for e in names if self.fields[e["field"]].type != "json"]
        if wrong:
            raise ValueError(f"spec {self.name}: rights.names reads names from a json field, and {wrong[0]} is "
                             f"{self.fields[wrong[0]].type}")
        self.names = tuple(dict(e) for e in names)

    # What a console and a page read and do not act on, checked at load (the boundary's step 6): `metrics` (`metrics.py`),
    # `display` — a dictionary of words, its tree's columns naming fields of the row or the unit's status — and
    # `servers.show`, each entry a table of this spec and a field of its rows; `servers.status`, fields of its heartbeats.
    STATUS_COLUMNS = ("phase", "worker", "server", "revision", "observed_revision")

    def _page_words(self, d: dict) -> None:
        from . import holds, metrics
        self.metrics = metrics.parse(self.name, d.get("metrics"), self.tables)
        # The running gauge is declared once, as a metric (`{name, from: status.phase, agg: count, equals: running}`);
        # `console.running` only names it (the architect's edge 3: it was declared twice, and the console counted it).
        if self.running_gauge and self.running_gauge not in {m["name"] for m in self.metrics}:
            raise ValueError(f"spec {self.name}: console.running names one of its metrics, and {self.running_gauge!r} "
                             f"is none — declare it under `metrics:`")
        self.holds = holds.parse(self.name, d.get("holds"), tables=self.tables)
        from .door import parse_routes
        self.door_routes = parse_routes(f"spec {self.name}", d.get("door"))
        req = d.get("requests")
        if req is not None:
            known = set(REQUEST_KEYS)
            if not isinstance(req, dict) or set(req) - known or not isinstance(req.get("free", False), bool) \
                    or set(req.get("stamp") or []) - {"by", "at", "group", "about"} \
                    or not isinstance(req.get("elsewhere", []), list):
                raise ValueError(f"spec {self.name}: `requests:` is {{{', '.join(sorted(known))}}}, not {req!r}")
            from . import schema as _schema
            self.requests_free = req.get("free", False)
            self.requests = {k: v for k, v in req.items() if k != "free"}
            if "schema" in req:
                self.requests["schema"] = _schema.load(req["schema"], f"spec {self.name}: requests.schema")
            # Every number of the family, FINITE (ADR-0012; the fourteenth review, minor 5): `ttl: .nan` loaded — `< 0` is
            # false for NaN — and then the filter dropped every row, `per_person` limited nothing and the reaper ended
            # nothing by age; `per_person: 2.5` let a person stand three. A count is a whole number; seconds are finite.
            for k, (whole, zero, what) in REQUEST_NUMBERS.items():
                v = req.get(k)
                if k in req and (isinstance(v, bool) or not isinstance(v, int if whole else (int, float))
                                 or not math.isfinite(v) or v < 0 or (v == 0 and not zero)):
                    raise ValueError(f"spec {self.name}: requests.{k} is {what}, not {v!r}")
            # HOW LONG A REQUEST STANDS IS DECLARED, NEVER ASSUMED (the architect, 2026-10-05, ADR 0012): ending a row by
            # age is destructive, and a ledger's assumed day silently lifts a person's quota. A family that frees (or
            # counts per person) says `ttl` — `0` for no limit, said so; any other says `valid_for`, its rows' deadline.
            if (self.requests_free or "per_person" in req) and "ttl" not in req:
                raise ValueError(f"spec {self.name}: requests.ttl is required with "
                                 f"`{'free: true' if self.requests_free else 'per_person'}` — the seconds a request may "
                                 f"stand unanswered, or 0 for no limit")
            if not self.requests_free and "valid_for" not in req:
                raise ValueError(f"spec {self.name}: requests.valid_for is required without `free: true` — the seconds "
                                 f"a request is worth doing")
            # …and how far a deadline may be, with it (ADR 0012, the same rule): the door assumed no bound and the reaper
            # ten minutes — two numbers nobody declared, and not the same one. A default deadline past it is a family
            # whose every request is refused.
            if "valid_for" in req and "most_valid" not in req:
                raise ValueError(f"spec {self.name}: requests.most_valid is required with `valid_for` — the farthest a "
                                 f"request's `valid_until` may be, in seconds")
            if "valid_for" in req and req["valid_for"] > req["most_valid"]:
                raise ValueError(f"spec {self.name}: requests.valid_for ({req['valid_for']}) is past requests.most_valid "
                                 f"({req['most_valid']}): a request given no deadline would be refused for its own")
            # A stamp of what the unit is about names the field `about:` declares; without one it stamped nothing,
            # silently (the cross-check of «Паритет», 2026-10-05).
            if "about" in (req.get("stamp") or []) and not self.about_field:
                raise ValueError(f"spec {self.name}: requests.stamp names `about`, and the spec says no `about:` — "
                                 f"declare {{sub, field}}, or stamp without it")
            # …and of the group, the group the placement groups by (ADR-0012; the fourteenth review, minor 26): without
            # `placement.group_by` the stamp stamped nothing, and the holder's "performed in the group it was filed for"
            # held for no request.
            if "group" in (req.get("stamp") or []) and not self.group_by:
                raise ValueError(f"spec {self.name}: requests.stamp names `group`, and placement says no `group_by` — "
                                 f"declare it, or stamp without it")
            if "key" in req:
                self._request_key(req)
        from .tables import parse as _tables
        self.table_specs = _tables(self.name, d.get("tables"), lambda t, raw: read_fields(f"spec {self.name}: tables.{t}", raw))[1]
        # …a table the console SERVES (declared, `{key, fields}`) and the rows: a table only named (`tables: [x]`) is a
        # family the console's token may write and nobody serves — no route of its own to collide
        for where, n in [("unit.rows", self.rows)] + [(f"tables.{t}", t) for t in self.table_specs]:
            if str(n) in CONSOLE_ROUTES:
                raise ValueError(f"spec {self.name}: {where} is {n!r}, a route the console answers itself "
                                 f"(`/{n}`) — no request would reach that family; name it otherwise "
                                 f"(the console's routes: {', '.join(sorted(CONSOLE_ROUTES))})")
        # `holds.released` names a field of the held table's rows (ADR-0057, the addendum of 2026-10-10): a name that is
        # not one is a hold nobody can let go — every row would hold for ever, as if the word were not there.
        rel = (self.holds or {}).get("released")
        if rel:
            t = self.table_specs.get(self.holds["table"])
            if t is None or rel not in t.fields:
                raise ValueError(f"spec {self.name}: holds.released is {rel!r}, which is no field of "
                                 f"tables.{self.holds['table']}.fields — declare it there, or let go of nothing")
        # WHAT A WORKER WRITES HAS A DECLARED FORM (ADR 0012; «Архитектор» with «Паритет», 2026-10-06): `worker.writes`
        # names its units' rows or one of its DECLARED tables (`{key, fields}`), whose field rules the write goes through
        # (`tables.write_row`). Any other family under `<sub>/` — a table only named, or none — is rows of no declared
        # form that nobody serves, and its token would write them: refused at load, the family named.
        stray = [w for w in self.worker_writes if w != self.rows and w not in self.table_specs]
        if stray:
            raise ValueError(f"spec {self.name}: worker.writes names {', '.join(stray)} — neither its units' rows "
                             f"({self.rows}) nor one of its declared tables ({', '.join(self.table_specs) or 'none'}); "
                             f"declare it under `tables:` with its key and fields, or write nothing there")
        disp = d.get("display")
        if disp is not None:
            if not isinstance(disp, dict):
                raise ValueError(f"spec {self.name}: `display:` is {{{', '.join(DISPLAY_KEYS)}}} — words for a page, no "
                                 f"logic — not {disp!r}")
            stray = [k for k in disp if k not in DISPLAY_KEYS]
            if stray:
                raise ValueError(f"spec {self.name}: `display.{stray[0]}` is no section of `display:` "
                                 f"({', '.join(DISPLAY_KEYS)}) — words for a page, no logic, closed by sections")
            self._card_words(disp)
            for fid, w in (disp.get("keys") or {}).items():
                if not isinstance(w, dict) or set(w) - {"title", "about", "absent"} or not isinstance(w.get("title"), str) \
                        or not all(isinstance(v, str) for v in w.values()):
                    raise ValueError(f"spec {self.name}: display.keys.{fid} is {{title, about, absent}} — words, not {w!r}")
            tree = disp.get("tree") or {}
            # `children: false` — the page draws no child units under a unit in the tree (the product's word; the page's
            # behaviour, passed through `/spec` untouched); the rest are words
            if not isinstance(tree, dict) or set(tree) - {*TREE_KEYS, *TREE_WORDS} \
                    or (tree.get("group_by") and tree["group_by"] not in self.fields) \
                    or not isinstance(tree.get("children", True), bool) \
                    or not all(isinstance(tree[w], str) for w in TREE_WORDS if w in tree):
                raise ValueError(f"spec {self.name}: display.tree is {{group_by: <a field>, columns, children: true|false, "
                                 f"{', '.join(TREE_WORDS)}: <words>}}, not {tree!r}")
            for c in tree.get("columns") or []:
                if not isinstance(c, dict) or (c.get("field") not in self.fields and c.get("field") not in self.STATUS_COLUMNS):
                    raise ValueError(f"spec {self.name}: display.tree.columns names a field of the row or of the unit's "
                                     f"status ({', '.join(self.STATUS_COLUMNS)}), not {c!r}")
            self.display = disp
        servers = d.get("servers")
        if servers is not None:
            ok = isinstance(servers, dict) and servers and not set(servers) - {"show", "status"}
            show = servers.get("show", []) if ok else None
            if not isinstance(show, list) or not all(isinstance(e, dict) and e.get("table") in self.tables
                                                      and isinstance(e.get("by"), str) and e["by"]
                                                      and not set(e) - {"table", "by", "title", "columns"} for e in show):
                raise ValueError(f"spec {self.name}: `servers:` is {{show: [{{table: <one of its tables>, by: <its rows' "
                                 f"field naming the server>, title, columns}}], status: [{{field, title, of?}}]}}, "
                                 f"not {servers!r}")
            self.servers_show = show
            self.servers_status = self._servers_status(servers.get("status", []))

    # EVERY KEY THAT NAMES A FIELD NAMES ONE (ADR-0012, ADR-0056; the fifteenth review, major 1): a field of the unit's row,
    # or of the rows of the table the key declares — its `fields:` and what the console stamps on it (`stamp:`). It was
    # checked of `display.tree.columns` and of nine keys not: `holds: {unit: itm}` loaded and the resource held nothing,
    # `rights.unit_of: {pins: itemm}` made every row nobody's (any viewer saw it), `derived.items: {days: keep_dayz}`
    # wrote no row (365 days where the operator said 7), `affinity.strict: {kinnd: …}` bound nothing, a metric's `where`
    # counted 0 for ever. Refused at load, the key's path named; the neighbour's fields of `near.prefer` are asked where
    # the catalogue is whole (`catalog.near_known`). A table only named declares no fields, and its names are not asked.
    def row_fields(self, table: str | None) -> tuple:
        if table is None:
            return tuple(self.fields)
        t = self.table_specs.get(table)
        return (*t.fields, *(w for w in t.stamp if w not in t.fields)) if t is not None else ()

    def _names_field(self, path: str, name, table: str | None = None, of: str = "") -> None:
        if table is not None and table not in self.table_specs:
            return                       # a table only named (`tables: {shelves: }`) declares no fields: nothing to hold to
        known = self.row_fields(table)
        if not isinstance(name, str) or name not in known:
            whose = "the unit's row" if table is None else f"the rows of {table}"
            raise ValueError(f"spec {self.name}: {path} names a field of {whose} ({', '.join(known) or 'none'}), "
                             f"not {name!r}{of}")

    def _fields_named(self) -> None:
        for d in self.derived:
            for item, fld in d.items.items():
                self._names_field(f"unit.derived.items.{item}", fld)
        for table, fld in self.unit_of.items():
            self._names_field(f"rights.unit_of.{table}", fld, table)
        for e in self.servers_show:
            self._names_field("servers.show.by", e["by"], e["table"])
            cols = e.get("columns", [])
            if not isinstance(cols, list):
                raise ValueError(f"spec {self.name}: servers.show.columns is a list of fields of the rows of "
                                 f"{e['table']}, not {cols!r}")
            for c in cols:
                self._names_field("servers.show.columns", c, e["table"])
        if self.places:
            if self.places["server_field"]:
                self._names_field("placement.places.server_field", self.places["server_field"], self.places["table"])
            for k in self.places["where"]:
                self._names_field("placement.places.where", k, self.places["table"])
        if self.affinity:
            if self.affinity["server_field"]:
                self._names_field("placement.affinity.server_field", self.affinity["server_field"], self.affinity["table"])
            for k in self.affinity["strict"]:
                self._names_field("placement.affinity.strict", k, self.affinity["table"])
        if self.holds:
            for k in ("unit", "since", "until"):
                self._names_field(f"holds.{k}", self.holds[k], self.holds["table"])
        for m in self.metrics:
            if "count" not in m:
                continue
            for k in m["where"]:
                self._names_field("metrics.where", k, m["count"], f" — metric {m['name']}")
            if m["unless"]:
                for k in m["unless"]["where"]:
                    self._names_field("metrics.unless.where", k, m["unless"]["table"], f" — metric {m['name']}")

    # `servers.status: [{field, title, of?}]` — fields of this subsystem's heartbeats a page shows on its servers' rows,
    # each under its title (a belt that jammed, say): `/servers` puts each worker's value of them in its row as the
    # heartbeat carries it, and the page sums them per server; the platform reads none of them. A field is a string
    # listed in `heartbeat.strings` or a number: the numbers of a heartbeat are declared nowhere (a heartbeat carries what
    # its worker says), so a field not listed there is read as a number — and a word where a number stands is counted
    # and left out (`SpecConsole._status_of`). A field may be a PATH into the heartbeat's maps by its dots
    # (`writer.state`; ADR 0057, «Архитектор» 2026-10-06, the product's window 12: `metrics[].from` read without its
    # `heartbeat.`, plain keys — no `<k>`: a wildcard says many values, and a row's cell is one): its leaf is a string or
    # a number, either one, since `heartbeat.strings` names top fields only. A field — a top one or a path's leaf — may
    # also be a MAP or a LIST, put in the row whole, as the heartbeat carries it (ADR-0064): the platform reads nothing
    # in it. `of: <a table of this spec>` says whose rows the keys of such a value are (a count per
    # row of that table, say): the page matches them to the table's rows, and the loader only checks that the table is
    # declared (ADR 0012).
    # The platform's own fields are the row's already, not a spec's to name — nor a path into one; a field said twice is
    # a second column of one value. Each entry is `{field, title}` and maybe `of`, the title a non-empty word.
    def _servers_status(self, got) -> list:
        word = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*")
        if not isinstance(got, list):
            raise ValueError(f"spec {self.name}: servers.status is [{{field: <a field of its heartbeats>, title: <words>, "
                             f"of?: <one of its tables>}}], not {got!r}")
        out: list = []
        for e in got:
            if not isinstance(e, dict) or not {"field", "title"} <= set(e) <= {"field", "title", "of"} \
                    or not isinstance(e["field"], str) or not word.fullmatch(e["field"]) \
                    or not isinstance(e["title"], str) or not e["title"].strip():
                raise ValueError(f"spec {self.name}: servers.status is [{{field: <a field of its heartbeats>, title: "
                                 f"<words>, of?: <one of its tables>}}], not {e!r}")
            if "of" in e and (not isinstance(e["of"], str) or e["of"] not in self.tables):
                raise ValueError(f"spec {self.name}: servers.status: {e['field']!r} is of {e['of']!r}, and this spec "
                                 f"declares no such table ({', '.join(sorted(self.tables)) or 'none'}; ADR-0064)")
            if e["field"].split(".")[0] in PLATFORM_HEARTBEAT_STRINGS:
                raise ValueError(f"spec {self.name}: servers.status: {e['field']!r} is the platform's own field of a "
                                 f"heartbeat ({', '.join(PLATFORM_HEARTBEAT_STRINGS)}) or a path into one, already "
                                 f"in the row")
            if e["field"] in (x["field"] for x in out):
                raise ValueError(f"spec {self.name}: servers.status names {e['field']!r} twice")
            out.append({"field": e["field"], "title": e["title"], **({"of": e["of"]} if "of" in e else {})})
        return out

    # A UNIT'S CARD, IN WORDS (the product's; the page module draws the card from them, the platform reads none): `general`
    # — what the card's first tab is called; `fields` — a field's label (`id` and the unit's status words too);
    # `field_help` — a field's hint; `options` — the word for each value of a field with an `enum`; `form` — the card's
    # blocks in order, `{title, state?, placement?, fields, status?, note?}`: `state` puts the unit's state in the block,
    # `placement` where it runs, `status` what its worker says of it, read only (`[{field, since?, title?}]`: a field of
    # the unit's STATUS, not of its row: what it is doing, and since when); `events: false` — the card has no journal
    # tab of the module's (the page shows the unit's events itself). Each word for a field names one, checked here: a
    # word for a field that is not there is a word for nothing. A status field is named by `form[].status` and nowhere
    # else, so its words in `options` are free — its values are the worker's to say, no `enum` of the spec holds them.
    def _card_words(self, disp: dict) -> None:
        form = disp.get("form") or []
        if not isinstance(form, list) or not all(
                isinstance(b, dict) and isinstance(b.get("status", []), list) and all(
                    isinstance(x, dict) and not set(x) - {"field", "since", "title"} and isinstance(x.get("field"), str)
                    and x["field"] and all(isinstance(x.get(k, ""), str) for k in ("since", "title"))
                    for x in b.get("status", [])) for b in form):
            raise ValueError(f"spec {self.name}: display.form[].status is [{{field: <a field of the unit's status>, "
                             f"since?: <its field saying since when>, title?: <words>}}], not {form!r}")
        row = set(self.fields) | {"id", *self.STATUS_COLUMNS}
        status = {x["field"] for b in form for x in b.get("status", [])} - set(self.fields)
        named = row | status
        for w in DISPLAY_WORDS:
            if not isinstance(disp.get(w, ""), str):
                raise ValueError(f"spec {self.name}: display.{w} is a word, not {disp[w]!r}")
        if not isinstance(disp.get("events", True), bool):
            raise ValueError(f"spec {self.name}: display.events is true or false — whether the card has the module's "
                             f"journal tab — not {disp['events']!r}")
        for k in ("kinds", "actions"):
            got = disp.get(k) or {}
            if not isinstance(got, dict) or not all(isinstance(v, str) for v in got.values()):
                raise ValueError(f"spec {self.name}: display.{k} is {{<a name>: <its words>}}, not {got!r}")
        for k in ("fields", "field_help"):
            got = disp.get(k) or {}
            if not isinstance(got, dict) or not all(f in named and isinstance(v, str) for f, v in got.items()):
                stray = sorted(str(f) for f in got if f not in named) if isinstance(got, dict) else []
                raise ValueError(f"spec {self.name}: display.{k} is {{<a field of the row or of form[].status>: <words>}}"
                                 f"{f' — {stray} names no field' if stray else ''}, not {got!r}")
        options = disp.get("options") or {}
        for k, words in (options.items() if isinstance(options, dict) else [(None, None)]):
            f, free = self.fields.get(k), k in status
            if not isinstance(words, dict) or not (free or (f is not None and f.enum)) or not all(
                    isinstance(w, str) and (free or str(v) in map(str, f.enum)) for v, w in words.items()):
                raise ValueError(f"spec {self.name}: display.options is {{<a field with an enum>: {{<one of its values>: "
                                 f"<its word>}}, <a field of form[].status>: {{<a value>: <its word>}}}}, not {options!r}")
        if not all(
                not set(b) - {"title", "state", "placement", "fields", "status", "note"}
                and isinstance(b.get("title"), str) and isinstance(b.get("note", ""), str)
                and isinstance(b.get("state", False), bool) and isinstance(b.get("placement", False), bool)
                and isinstance(b.get("fields"), list) and all(x in row for x in b["fields"]) for b in form):
            raise ValueError(f"spec {self.name}: display.form is [{{title, state?, placement?, fields: [<a field of the "
                             f"row>], status?, note?}}], not {form!r}")

    # `requests.key` — the name a request is filed under, from its body (`"{unit}-{from:int}-{to:int}"`): every brace
    # closed, and — where the family declares its body (`requests.schema`) — every name in it `unit` or a property of
    # that schema (ADR-0012; the fourteenth review, minor 26). A name the schema does not declare was a family whose
    # every request the door answered 400 «bad id»; a brace left open was a name of the request that said the brace. A
    # family without a schema declares no body, and its names are the door's to fill in or refuse.
    def _request_key(self, req: dict) -> None:
        from .tables import KEY_TEMPLATE
        key = req["key"]
        schema = req.get("schema") if isinstance(req.get("schema"), dict) else None
        props = schema.get("properties") if schema is not None and isinstance(schema.get("properties"), dict) else {}
        if not isinstance(key, str) or not key or "{" in KEY_TEMPLATE.sub("", key) or "}" in KEY_TEMPLATE.sub("", key):
            raise ValueError(f"spec {self.name}: requests.key is a name with {{<field>}} or {{<field>:int}} in it, every "
                             f"brace closed — not {key!r}")
        stray = [m.group(1) for m in KEY_TEMPLATE.finditer(key)
                 if schema is not None and m.group(1) != "unit" and m.group(1) not in props]
        if stray:
            raise ValueError(f"spec {self.name}: requests.key names {', '.join(stray)}, which requests.schema does not "
                             f"declare (its properties: {', '.join(props) or 'none'}) — no request would fill it in")

    # The placement's words that are a vocabulary or a declaration, checked at load (the boundary's step 6): the
    # constraint and the tie-break are names from the closed catalogue; `group_by` is a field, or `{field, cut_at}` over
    # a url field, with `schemes` beside `cut_at: host` only and in the words of `GROUP_SCHEME_WORDS`; `spread_by` a field; `near.prefer` one key `<their field>[.<field>]` and a value or a list of them; `affinity` names a
    # field of the row and a table of this spec, and `strict` is `{<field of the table's row>: <value or values>}`.
    def _placement_words(self, pl: dict) -> None:
        if self.constraint not in CONSTRAINTS:
            raise ValueError(f"spec {self.name}: placement.constraint is one of {', '.join(CONSTRAINTS)}, not "
                             f"{self.constraint!r} — the catalogue is closed; declare what else a unit needs")
        if self.tie_break not in TIE_BREAKS:
            raise ValueError(f"spec {self.name}: placement.tie_break is one of {', '.join(TIE_BREAKS)}, not {self.tie_break!r}")
        # …and the two words read by equality further on: a typo was `none` or `shared` without a word said
        if self.requires not in REQUIRES:
            raise ValueError(f"spec {self.name}: placement.requires is one of {', '.join(REQUIRES)}, not {self.requires!r}")
        if self.servers not in SERVERS:
            raise ValueError(f"spec {self.name}: placement.servers is one of {', '.join(SERVERS)}, not {self.servers!r}")
        g = pl.get("group_by")
        if isinstance(g, dict):
            if set(g) - {"field", "cut_at"} or self.group_by not in self.fields:
                raise ValueError(f"spec {self.name}: placement.group_by is a field, or {{field: <a field>, cut_at: "
                                 f"host | <a segment of its path>}}, not {g!r} — how a scheme writes its host is the "
                                 f"url field's `schemes`")
            if self.group_cut and (self.fields[self.group_by].type != "url" or "/" in self.group_cut):
                raise ValueError(f"spec {self.name}: group_by.cut_at reads a url field — its host (`host`) or its path "
                                 f"up to a segment — {self.group_by} is {self.fields[self.group_by].type}, the segment "
                                 f"{self.group_cut!r}")
        # …and in its string form the same: a FIELD (ADR-0012; the fourteenth review, major 5). `group_by: sourcee` loaded,
        # every unit's group was empty, and sixteen units of one group went to four workers, the group's one holder
        # split four ways. `spread_by` alike (major 11): a name of no field, or no name at all (`spread_by: 5`), put every
        # unit's taken servers at none, and the filter it promised was gone without a word.
        elif "group_by" in pl and (not isinstance(g, str) or g not in self.fields):
            raise ValueError(f"spec {self.name}: placement.group_by is a field of the row ({', '.join(self.fields)}), or "
                             f"{{field: <a field>, cut_at: …}} — not {g!r}")
        if "spread_by" in pl and (not isinstance(pl["spread_by"], str) or pl["spread_by"] not in self.fields):
            raise ValueError(f"spec {self.name}: placement.spread_by is a field of the row ({', '.join(self.fields)}) — "
                             f"not {pl['spread_by']!r}")
        near = pl.get("near")
        prefer = near.get("prefer") if isinstance(near, dict) else None
        if prefer is not None:
            if not isinstance(prefer, dict) or not prefer or not self.near_of:
                raise ValueError(f"spec {self.name}: near.prefer is {{<their field>[.<field>]: <values>, …}}, and only "
                                 f"where `of` can find several of theirs — not {prefer!r}")
            for k, v in prefer.items():
                vals = v if isinstance(v, list) else [v]
                if not isinstance(k, str) or not re.fullmatch(r"[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)?", k) or not vals \
                        or not all(isinstance(x, (str, int, float, bool)) for x in vals):
                    raise ValueError(f"spec {self.name}: near.prefer is {{<their field>[.<field>]: <values>, …}}, not "
                                     f"{prefer!r}")
                self.near_prefer[k] = tuple(str(x).lower() if isinstance(x, bool) else str(x) for x in vals)
        places = pl.get("places")
        if places is not None:
            from .metrics import where_of
            if not isinstance(places, dict) or set(places) - {"table", "where", "server_field", "lease"} \
                    or places.get("lease", "strict") != "strict" \
                    or places.get("table") not in self.tables or self.place_by == "server" \
                    or not isinstance(places.get("server_field", ""), str):
                raise ValueError(f"spec {self.name}: placement.places is {{table: <one of its tables>, where?, "
                                 f"server_field?, lease?: strict}}, for a subsystem placed by something other than the "
                                 f"server (`place_by`) — not {places!r}")
            self.places = {"table": str(places["table"]), "where": where_of(self.name, places.get("where"), "places"),
                           "server_field": str(places.get("server_field") or ""),
                           "lease": str(places.get("lease") or "")}
        aff = pl.get("affinity")
        if aff is not None:
            if not isinstance(aff, dict) or set(aff) - {"field", "table", "server_field", "strict"} \
                    or aff.get("field") not in self.fields or aff.get("table") not in self.tables:
                raise ValueError(f"spec {self.name}: placement.affinity is {{field: <a field of the row>, table: <one of "
                                 f"its tables>, server_field?, strict?}}, not {aff!r}")
            strict = aff.get("strict") or {}
            if not isinstance(strict, dict) or not all(isinstance(k, str) and k for k in strict):
                raise ValueError(f"spec {self.name}: affinity.strict is {{<field of the table's row>: <values>}}, not {strict!r}")
            self.affinity = {"field": str(aff["field"]), "table": str(aff["table"]),
                             "server_field": str(aff.get("server_field") or ""),
                             "strict": {str(k): tuple(str(x).lower() if isinstance(x, bool) else str(x)
                                                      for x in (v if isinstance(v, list) else [v]))
                                        for k, v in strict.items()}}

    # -- what a unit is called outside its routes, and what it is about ----------------------------------
    # `<name>/<id>` (`doors.unit_ref`): the one way a unit is named to the gate, the index and a grant.
    # The group a value of the `group_by` field is in: the value itself; or its host (`cut_at: host` — `url_host`, by the
    # field's `schemes`); or its spelling up to the segment (`cut_at: <segment>` — `url_cut`). "" — no value, or no host
    # — is no group: a unit with it groups with nothing. The controller's `group_value` and the worker's `request_group`
    # both ask here, so the group a request was stamped with is the one its holder performs it in.
    def group_of(self, value) -> str:
        v = str(value or "")
        if not v or not self.group_cut:
            return v
        return url_host(v, self.fields[self.group_by].schemes) if self.group_cut == "host" else url_cut(v, self.group_cut)

    # …and why a value of the `group_by` field may not be stored, None when it may (ADR 0053): with `cut_at: host`
    # declared there is no unit without a group but the ones `schemes.<s>.none` says — a host nobody can tell
    # (`h%2Ecorp`, decoded by one reader and not by the next; `010.0.0.5`, octal to another) is a place nobody can say
    # whose it is, and a "no group" there would let one unit's rights reach another's host. Refused at write, 400, in
    # words that never repeat the value (`refuse`).
    def group_refusal(self, value) -> str | None:
        if self.group_cut != "host" or not value or host_of_url(str(value), self.fields[self.group_by].schemes) is not None:
            return None
        return (f"{self.group_by} names no host that can be told: its host is neither a host name (letters, digits, "
                f"'-' and '.', no escapes) nor an IP address in its usual form, or it does not parse — units are "
                f"grouped by the host they are on, and one nobody can tell is refused")

    def ref(self, uid) -> str:
        from .doors import unit_ref
        return unit_ref(self.name, uid)

    # A value a row holds as a unit of `sub`, as a reference — a value already written as one of `sub`'s stays.
    @staticmethod
    def _ref_in(sub: str, v) -> str:
        from .doors import parse_ref, unit_ref
        v = "" if v is None else str(v)
        if not v:
            return ""
        got = parse_ref(v)
        return v if got is not None and got[0] == sub else unit_ref(sub, v)

    # The unit a row of this subsystem is about — `<about.sub>/<value of about.field>` — "" when the spec says no
    # `about` or the row holds nothing in the field.
    def of_row(self, row: dict | None) -> str:
        if not self.about_sub or not row or row.get(self.about_field) in (None, ""):
            return ""
        return self._ref_in(self.about_sub, row.get(self.about_field))

    # Whose a row of one of this subsystem's tables is (`rights.unit_of`): `(ref, True)`, `("", True)` when the table
    # says whose and the row names nobody, `("", False)` when the spec does not say it of the table.
    def table_unit(self, table: str, row: dict | None) -> tuple[str, bool]:
        fld = self.unit_of.get(table)
        if fld is None:
            return "", False
        v = (row or {}).get(fld)
        if v in (None, ""):
            return "", True
        from .doors import parse_ref
        if parse_ref(str(v)) is not None:
            return str(v), True
        return self._ref_in(self.about_sub or self.name, v), True

    # The first `fixed` field `fields` would change in the row `was` (stored items or a row), None for none —
    # compared as the field parses them, so 7 and "7" are one value.
    def fixed_changed(self, was: dict | None, fields: dict) -> str | None:
        for n, f in self.fields.items():
            if not f.fixed or n not in fields or not was or was.get(n) in (None, ""):
                continue
            try:
                same = str(f.take(fields[n])) == str(f.take(was[n]))
            except PARSE_ERRORS:
                same = False
            if not same:
                return n
        return None

    # The file read by the spec's YAML (`specyaml.load`: YAML 1.2 core, a subset — no duplicate key, no anchor, alias or
    # tag; ADR-0012, the fourteenth review's major 9), then `from_dict`. PyYAML is imported lazily so the rest of the
    # platform has no dependency on it. Every refusal is a ValueError naming the file — a section of the wrong shape
    # that tripped a reader (`placement: [x]`) as well, never an AttributeError out of a load (minor 25).
    @classmethod
    def load(cls, path: str) -> "SubsystemSpec":
        from . import catalog, specyaml
        d = specyaml.load(path)
        try:
            spec = cls.from_dict(d)
        except ValueError as e:
            raise ValueError(f"{path}: {e}") from None
        except (AttributeError, TypeError, KeyError, IndexError, RecursionError) as e:
            raise ValueError(f"{path}: not a spec — a section of another shape than its key takes "
                             f"({type(e).__name__}: {e})") from None
        catalog.register(spec, path)            # a spec this process loaded is one it knows (`catalog.py`)
        return spec

    # `Subsystem(name)` — the key layout from `contract.py`.
    @property
    def sub(self) -> Subsystem:
        return Subsystem(self.name)

    # -- who writes what: two tokens, one prefix each ------------------------------------
    # The operator's rows: `<name>/<rows>/*`, `<name>/next_id`, `<name>/idem/*` (a retried POST answered the
    # same by any instance), `<name>/policy` (the administrator's knobs) and the first segment of every
    # derived row (`<name>/retention/*`). Never placement. This is the console process's token.
    def acl_console(self) -> list[str]:
        """The operator's rows: what a console (one per server, any of them) may write — never placement."""
        out = [f"{self.name}/{self.rows}/*", f"{self.name}/next_id", f"{self.name}/idem/*",   # idem: a retried POST answered the same by ANY instance
               f"{self.name}/policy",                                                         # the administrator's knobs: servers distinct | shared
               f"{self.name}/sweep",                                                          # what the blob sweep marked, and when
               f"{self.name}/requests/*",                                                     # bounded work an operator asked a worker for, outside its ordinary pass
               *([f"{self.name}/asked/*"] if "per_person" in (self.requests or {}) else []),   # each person's open requests (ADR 0060)
               SERVERS_PREFIX + "*",                                                          # what a server reaches, as the administrator says it: one row a server, every subsystem's (ADR-0026)
               DRAIN_KEY,                                                                     # "this machine is about to stop": the operator's, and the same row for every subsystem
               DECOMMISSION + "*",                                                            # "this machine is gone for good": the operator's, every subsystem reads it
               SCHEMA_KEY]                                                                    # `PUT /schema`: the operator raises the layout once every machine is new
        for d in self.derived:
            out.append(f"{self.name}/{d.row.split('/')[0]}/*")
        out += [f"{self.name}/{t}/*" for t in self.tables]              # the administrator's lists: `testsub2/shelves/*`
        return out

    # What a worker of this subsystem may write: its epochs, its slot and its place, the rows of its own tables its spec
    # says it writes (`worker.writes`), and the request rows of the subsystems it files to (`worker.requests`).
    def acl_worker_role(self) -> list[str]:
        from .contract import requests_acl
        return (self.sub.acl_worker() + [self.sub.config(t, "*") for t in self.worker_writes]
                + requests_acl(*self.worker_requests))

    # Placement: `<name>/workers/*`, `<name>/placement/*`, `<name>/slots/*` — never a unit's row. The
    # controller process's token (count = 1). Together the two ACLs split the old `<name>/*` so that the
    # console cannot place and the controller cannot edit; `test_the_console_over_http` proves
    # `con.place(1)` raises `Forbidden`.
    # With `placement.unplaced.delete_after` it may DELETE a unit's row (`delete:`, the product's `p.DeleteOnly`; ADR-0067)
    # — and still never write one.
    def acl_controller(self) -> list[str]:
        """Placement: what the controller (count = 1) may write — never a unit's row."""
        from .rights import DELETE_ONLY
        return [f"{self.name}/workers/*", f"{self.name}/placement/*", f"{self.name}/slots/*",
                f"{self.name}/decommissioned/*",                       # its mark that a server's decommission was carried out
                *([f"{DELETE_ONLY}{self.sub.config(self.rows, '*')}"] if self.unplaced_delete_after > 0 else [])]

    # Whether ids are numbers; convert a string id accordingly.
    @property
    def numeric(self) -> bool:
        return self.id == "numeric"

    def parse_id(self, v):
        return int(v) if self.numeric else str(v)

    # -- rows <-> items --------------------------------------------------------------
    # Variables items to a typed row: `id`, every spec field (default if absent), `revision` (default 1).
    def row(self, items: dict) -> dict:
        r = {"id": self.parse_id(items["id"])}
        for n, f in self.fields.items():
            r[n] = f.parse(items.get(n)) if n in items else f.default_value()
        r["revision"] = int(items.get("revision", 1))
        return r

    # The inverse, all strings.
    def items(self, row: dict) -> dict:
        out = {"id": str(row["id"]), "revision": str(row.get("revision", 1))}
        for n, f in self.fields.items():
            v = row.get(n, f.default_value())
            if v is None and (f.inherits or f.type == "json"):
                # not set is ABSENT — never a stored "None"; and a json field's `null` is no field, its default given
                # (none declared: absent — never the text `null`; the architect, 2026-10-06), as a table row's is
                continue
            out[n] = f.to_item(v)
        return out

    # Raise `Refused` for any `PLATFORM_FIELDS` key or any key not in the spec. Called first by `create` and
    # `update`.
    def refuse(self, fields: dict) -> None:
        bad = [k for k in fields if k in PLATFORM_FIELDS]
        if bad:
            raise Refused(f"a client may not set {bad}: placement is decided and stored by the controller with a "
                          f"reason; revision, epoch and phase are not the operator's")
        unknown = [k for k in fields if k not in self.fields]
        if unknown:
            raise Refused(f"unknown field(s) {unknown}")
        # A secret arrives in the clear and is sealed HERE, on its way into the store. A value that already looks
        # sealed is a copy from another row — unit 7's ciphertext under unit 8, for the holder to open for
        # whoever reads 8 — or a typo that would stop the holder's pass (the review's second pass, blocker 3 and a
        # major): refused at the door. Nothing a client types is `enc:v1:…`.
        from .sealing import is_sealed, is_secret_field
        pasted = [k for k, v in fields.items() if is_secret_field(k) and is_sealed(v)]
        if pasted:
            raise Refused(f"{pasted}: a secret is given in the clear and sealed by this console; a sealed value is not taken")
        # …nor its MASK (the review's thirteenth round; the product's guard): every reply shows a secret as `***`
        # (`secrets.mask_secrets`), and a page that sent back what it was shown stored `***` as the unit's password
        # — the unit stopped, and nothing said why. What the mask stands for is not known here: refused, in words —
        # `***` and the masks other pages draw (`is_mask`).
        masked = [k for k, v in fields.items() if is_secret_field(k) and is_mask(v)]
        if masked:
            raise Refused(f"{masked}: a secret was sent as its mask; leave the field out to keep it")
        # A `url` field may not carry a userinfo. `x://root:hunter2@10.0.0.5/…` is how a password
        # reaches a row that is in the SNAPSHOT — out of the cluster, into М12's directory, and onto the
        # screen of every console, past a mask that only looks at `*_secret`. The credential fields are
        # where it goes instead, and saying so is better than moving it quietly: an operator who pasted a
        # URL from a browser learns that this system keeps the two apart.
        # A `blob` field holds the digest of the bytes, never the bytes. Without this, the obvious thing
        # for a client to do — paste the lump into the row — is also the thing that puts a row over the
        # store's ceiling, and the refusal it gets says "too big" rather than what to do instead.
        for name, f in self.fields.items():
            if f.type == "blob" and fields.get(name) and not is_digest(fields[name]):
                raise Refused(f"{name} takes a digest, not the bytes ({len(str(fields[name]))} of them): "
                              f"PUT the bytes to /{self.rows}/<id>/{name} and the row gets the digest back")
        # A VALUE OF A LIST HOLDS NO `,` (the review's ninth answer, left open; the tenth round). A list is stored as one
        # string joined by `,` (`Field.to_item`), and every reader — this one, М11's, М12's, another build's — splits it
        # there: `["zone 1,2"]` read back as two labels, a unit nobody's server reaches, an alarm kind nobody raises.
        # Refused where it is written; the store's form stays what every reader already reads (the rows written before
        # are already split, and read as they are). A string value is the joined form itself, and is taken as it is.
        for name, f in self.fields.items():
            v = fields.get(name)
            if f.type == "list" and isinstance(v, (list, tuple)):
                bad = [x for x in v if "," in str(x)]
                if bad:
                    raise Refused(f"{name}: a value of a list may not hold ',' — the list is kept joined by commas and "
                                  f"{bad[0]!r} would read back as {len(str(bad[0]).split(','))} values")
        for name, f in self.fields.items():
            # A `json` field that is not JSON is a 400 to whoever typed it, not a 500 from the store on
            # the next read. The ceiling is the row's own (Lesson 19's limit) — this one keeps a single
            # field from eating it: a scenario is a handful of triggers, not a document.
            if f.type == "json" and fields.get(name) is not None:
                raw = fields[name]
                try:                                     # the text measured is the text stored (`Field.to_item`)
                    doc = raw                            # the value as given: a string is a document (`Field.take`)
                    text = canonical_json(doc)
                except PARSE_ERRORS as e:                # nested past JSON's depth too: 400, not 500 (the tenth round)
                    r = Refused(f"{name} is not JSON: {e}")
                    r.fault = getattr(e, "fault", "not_json")
                    raise r from None
                size = len(text.encode())                # the BYTES of the text stored, as the product counts
                if size > JSON_CEILING:                  # (`ж` is two: characters let 4008 bytes through, «Паритет»)
                    r = Refused(f"{name} is {size} bytes of JSON; the ceiling is {JSON_CEILING}")
                    r.fault = "too_long"
                    raise r
                if f.schema is not None:
                    self._schema_refusal(name, f, doc)
            elif f.schema is not None and name in fields and fields[name] is not None:
                try:
                    value = f.parse(fields[name])
                except PARSE_ERRORS:
                    raise Refused(f"{name} is {f.type}, not {str(fields[name])[:60]!r}") from None
                self._schema_refusal(name, f, value)
            if f.enum and fields.get(name) is not None:
                try:
                    value = f.take(fields[name]) if f.type != "string" else str(fields[name])
                except PARSE_ERRORS:
                    value = None
                if value not in f.enum:
                    raise Refused(f"{name} is one of {', '.join(map(str, f.enum))}, not {str(fields[name])[:60]!r}")
            if f.type == "url" and fields.get(name):
                # The address as RFC 3986 reads it BY THIS FIELD'S SCHEME (`schemes`, `rfc_spelling`): a scheme with no
                # fragment (`fragment: none`) has its `#` read as a character here as in its group (`url_host`) — one
                # reading of one address, whichever rule asks.
                written = str(fields[name])
                rfc = rfc_spelling(written, f.schemes)
                # …and a url `urlsplit` cannot read, or whose port is no port, is a 400 with the words (the product
                # team's sibling of the tenth pass): `x://[10.0.0.5/x` raised `ValueError` out of here — a 500 — and
                # `…:8²/…` was taken, to stand in every reader of the row.
                try:
                    u = urlsplit(rfc)
                    u.port
                except ValueError:                       # its words quote the port it could not read: a password
                    raise AddressRefused(f"{name} is not an address: {NOT_AN_ADDRESS}") from None   # (the twelfth review, major 16)
                # …nor a '%' that escapes nothing (`…/ch/%zz`): RFC 3986 has no such address, and one reader would take
                # it as it stands, another refuse or mend it. The url rule's refusal alone: the host it names is still its
                # group (`url_host`; ADR 0053, «Архитектор» 2026-10-06)
                if _BROKEN_ESCAPE.search(rfc):
                    raise AddressRefused(f"{name} is not an address: a '%' in it is not followed by two hex digits")
                # …A LOGIN NOR A CREDENTIAL ANYWHERE IN IT — the platform's one rule (`secrets.address_refusal`), the one a
                # volume's url and the domain's door ask. This was a copy of it, and the copy fell behind (the thirteenth
                # review, blocker 6): it read the `@` of the netloc and the path only, and `…/relay?src=x%3A%2F%2Fadmin
                # %3A…%40host` — how a relay is told what to fetch — was 201, the password in the row, the
                # page and the snapshot. What the copy had learnt before, a review at a time: a login in the path of a
                # scheme that names its host there (the tenth round), a credential pair (the eleventh review, blocker 4).
                # The words name the parameter, never its value.
                # By THIS field's rules (`secret_in`, the boundary's step 4): how its addresses carry a login is its
                # spec's to say; the words name the fields its spec gives a login and a password (`Field.refusal`).
                why = f.refusal(fields[name])
                if why:
                    raise AddressRefused(why)
                # …and reached by what the spec says it is reached by (the keys of `schemes`); said in words, the scheme
                # is no secret.
                scheme = u.scheme.lower()
                if f.schemes and scheme not in f.schemes:
                    raise AddressRefused(f"{name} is reached by {', '.join(f.schemes)}, not by "
                                  f"{repr(scheme) if scheme else 'an address with no scheme'}")
                # …and no login where the scheme writes its host in the path (`host: path`): `x://vendor/admin:
                # …%40host/ch/1` — the url rule's, at any url field, whatever its `secret_in` (ADR 0053; the group is
                # still read: `host`, refused)
                if path_login(written, f.schemes):
                    raise AddressRefused(f"{name} holds a login where its scheme writes the host (in the path): the "
                                         f"login and the password are the spec's own fields, not the address")
                # …AND NO `#`. `urlsplit` reads it as the start of a fragment: `x://acme/box7#@box50/ch/1` is
                # box `box7` to every right asked of it, while a driver that does not stop at `#` dials `box50` —
                # rights asked of one box, another box opened. Nothing a unit is reached at holds one.
                if "#" in rfc:
                    raise AddressRefused(f"{name} may not hold '#': an address with a fragment names one place to the rights "
                                  f"and maybe another to the driver")
            # …AND THE HOST OF ITS GROUP CAN BE TOLD (`cut_at: host`, ADR 0053): asked of any type the field is, by
            # `group_refusal` — no unit without a group but those the spec's `none` says
            if name == self.group_by and fields.get(name):
                why = self.group_refusal(fields[name])
                if why:
                    raise AddressRefused(why)

    # A value against its field's schema: `Refused` in the schema's words, where it failed (`schema.check`).
    @staticmethod
    def _schema_refusal(name: str, f, value) -> None:
        from .schema import Invalid, check
        try:
            check(f.schema, value, name)
        except Invalid as e:
            raise Refused(str(e)) from None
        except RecursionError:
            raise Refused(f"{name} is nested past what is read") from None

    # A fresh row: each required field must be present and truthy (`"a testsub unit needs a name"`), others
    # get their default; a string value containing `{id}` has it substituted (a spec's `name: "u{id}"`);
    # `revision` is 1.
    def new_row(self, uid, fields: dict) -> dict:
        r = {"id": uid}
        for n, f in self.fields.items():
            if f.required and not fields.get(n):
                raise Refused(f"a {self.name} unit needs a {n}")
            v = fields.get(n)
            r[n] = f.take(v) if v is not None else f.default_value()
            if isinstance(r[n], str) and "{id}" in r[n] and f.type != "json":
                r[n] = r[n].replace("{id}", str(uid))
        r["revision"] = 1
        return r


# -- the catalogue --------------------------------------------------------------------
# The unit's `labels` must be a subset of what the worker's server reports.
def _labels_subset(row: dict, worker_labels: set[str]) -> bool:
    return set(row.get("labels") or []) <= worker_labels


# CLOSED (the boundary's step 6, §4). A spec names one of these or does not load. There was a door for more —
# `register_constraint`, code under a name — and nobody went through it; the three doors beside it (an admit, a near
# rank, a refusal of a row) were each one subsystem's code run inside this controller. What a subsystem needs beyond
# the catalogue it DECLARES, and the controller reads the declaration: `affinity`, `near.prefer`, a field's `ref`,
# `must_match` and `unique`, a url field's `schemes`, `group_by.cut_at`.
CONSTRAINTS = {"none": lambda row, labels: True, "labels-subset": _labels_subset}
TIE_BREAKS = ("most-free-capacity",)
REQUIRES = ("none", "resource")       # `resource`: a worker is eligible only while its server's resource answers
SERVERS = ("shared", "distinct")      # `distinct`: one worker per place (`place_by`) carries units


# A URL IN ITS ONE SPELLING (RFC 3986 §6.2.2, the syntax-based normalisation; the owner's decision on the boundary's
# step 6): what `unique: canonical` compares and `group_by.cut_at: <segment>` groups by. The scheme and the host in lower case;
# a percent-encoding in upper case, and one that encodes an unreserved character decoded; the dot segments of the path
# removed; an empty port gone. Nothing a SCHEME means (§6.2.3): a default port written out, or two segments a
# subsystem reads as one number, are two spellings here — one spelling is the rule, and a twin that only the subsystem
# can recognise is its worker's to find and say in its heartbeat. A value that is not an address is itself.
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _pct(s: str) -> str:
    def one(m):
        c = chr(int(m.group(1), 16))
        return c if c in _UNRESERVED else "%" + m.group(1).upper()
    return re.sub(r"%([0-9A-Fa-f]{2})", one, s)


def _without_dots(path: str) -> str:
    """RFC 3986 §5.2.4, remove_dot_segments."""
    out: list[str] = []
    while path:
        if path.startswith("../"):
            path = path[3:]
        elif path.startswith("./"):
            path = path[2:]
        elif path.startswith("/./"):
            path = "/" + path[3:]
        elif path == "/.":
            path = "/"
        elif path.startswith("/../"):
            path = "/" + path[4:]
            if out:
                out.pop()
        elif path == "/..":
            path = "/"
            if out:
                out.pop()
        elif path in (".", ".."):
            path = ""
        else:
            i = path.find("/", 1)
            seg, path = (path, "") if i < 0 else (path[:i], path[i:])
            out.append(seg)
    return "".join(out)


def canonical_url(v) -> str:
    s = "" if v is None else str(v).strip()
    try:
        u = urlsplit(s)
    except ValueError:
        return s
    if not u.scheme or not u.netloc:
        return s
    user, at, hostport = u.netloc.rpartition("@")
    if hostport.endswith(":"):
        hostport = hostport[:-1]                         # an empty port is no port
    netloc = (_pct(user) + at if at else "") + _pct(hostport).lower()
    return f"{u.scheme.lower()}://{netloc}{_without_dots(_pct(u.path))}" + (f"?{_pct(u.query)}" if u.query else "") \
        + (f"#{_pct(u.fragment)}" if u.fragment else "")


# …and that spelling up to a segment of its path (`group_by: {field, cut_at}`): the address with the path cut before the
# first segment that is `segment`, and no query — what the units that differ only after it have in common. One with no
# such segment is its whole spelling: a group of its own.
def url_cut(v, segment: str) -> str:
    c = canonical_url(hide_in_url(str(v)) if v is not None else v)
    try:
        u = urlsplit(c)
    except ValueError:
        return c
    segs = u.path.split("/")
    if not u.scheme or segment not in segs[1:]:
        return hide_in_url(c)
    # as an address may be said (`hide_in_url`): a group is a key in rows and replies, and a login a row stored before
    # the refusals carried is not repeated in it
    return hide_in_url(f"{u.scheme}://{u.netloc}" + "/".join(segs[:segs.index(segment, 1)]))


# THE HOST AN ADDRESS NAMES, IN ITS ONE SPELLING (`group_by: {field, cut_at: host}`; «Архитектор», 2026-10-06): what the
# units whose addresses name one host have in common, whatever else differs. Neither the scheme nor the port is part of
# it — `x://h/1` and `y://h:8/2` are one host, and a port nobody here knows the default of cannot be told from no port
# — and neither is a login. One spelling: lower case and no trailing dot (the root's); an IP address as `ipaddress`
# writes it — an IPv6 one unbracketed, its zero runs folded (RFC 5952), its zone dropped, an IPv4-mapped one as the IPv4
# address it is. The host is judged AS WRITTEN: a percent-escape in it is not decoded (`h%2Ecorp` is decoded by one
# reader and not by the next), and a host that is neither a name of RFC 1123 labels nor an IP literal is a host nobody
# can tell, as is an address that does not parse (a control character, a broken escape, a port that is not a number, a
# login in characters a login is not written in) or names no authority. Such a value is REFUSED at write (ADR 0053,
# `SubsystemSpec.group_refusal`): with the grouping declared there is no unit without a group but the ones the spec's
# `none` says; a row stored before is in no group ("", with nobody). A name does not resolve: `h.corp` and the address it
# resolves to are two hosts, for an asked network is no rule.
#
# A readable host is grouped even where the value is refused for another reason (`secret_in`): refusing a login is the
# field's, grouping is this — a row written before a rule refused its address still has the host it names.
#
# HOW A SCHEME WRITES ITS ADDRESS when it does not follow RFC 3986 the spec DECLARES, per scheme, on the url field
# (`fields.<f>.schemes: {<scheme>: {…}}`, the keys the schemes the field is reached by, `{}` one read by RFC 3986), in a
# closed dictionary — nothing of any scheme is known here. The field's refusal and its group read the address by the
# same words («Архитектор», ADR 0053: two parses of one address with two sets of options are two truths):
#   host: authority | path   where the host stands: the authority (RFC 3986, the default), or the first segment of the
#                            path, written as an authority is — `[login[:password]@]host[:port]` — the authority being
#                            then a name the group does not hold (`x://a/h/1` and `x://b/h/2` are one host, `h`). A path
#                            whose first segment is empty (`x://a`, `x://a/`) leaves the host in the authority. In that
#                            segment a login is set aside wherever its `@` stands — escaped (`%40`), or past a password
#                            holding a `/` — for a row written before the refusal of its login (`secret_in`); the host is
#                            the one WRITTEN in the path, never one only decoding makes.
#   fragment: keep | none    `none`: the scheme has no fragment, `#` is a character like another (`x://a#@h/` is on `h`,
#                            the host after the LAST `@`, as RFC 3986 cuts a login).
#   none: [<authority>, …]   authorities that name no host, in the host's one spelling: `x://local/…` groups with
#                            nobody — the only addresses without a group (ADR 0053).
GROUP_SCHEME_WORDS = {"host": ("authority", "path"), "fragment": ("keep", "none")}
_SCHEME_NAME = re.compile(r"[a-z][a-z0-9+.\-]*")
_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?")
_BROKEN_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_LOGIN_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._:~!$&'()*+,;=%@#")
_REG_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!$&'()*+,;=%")


def schemes_fault(schemes) -> str:
    """Why a url field's `schemes` is not a map of schemes to words of the closed dictionary — "" when it is. The list
    it was (`[https, ftp]`) is refused: one form (ADR 0003)."""
    if not isinstance(schemes, dict):
        return (f"is a map {{<scheme>: {{host?, fragment?, none?}}, …}} — `{{}}` for a scheme read by RFC 3986 — not "
                f"{schemes!r}")
    for name, opts in schemes.items():
        if not isinstance(name, str) or not _SCHEME_NAME.fullmatch(name):
            return f"{name!r} is not a scheme in lower case (RFC 3986: a letter, then letters, digits, `+`, `-`, `.`)"
        if not isinstance(opts, dict):
            return f"{name}: a scheme says {{host?, fragment?, none?}} — `{{}}` for RFC 3986 — not {opts!r}"
        for k, v in opts.items():
            if k in GROUP_SCHEME_WORDS:
                if v not in GROUP_SCHEME_WORDS[k]:
                    return f"{name}.{k} is one of {', '.join(GROUP_SCHEME_WORDS[k])}, not {v!r}"
            elif k == "none":
                if not isinstance(v, list) or not v or not all(
                        isinstance(a, str) and a and not set(a) & set("/?#@ ") for a in v):
                    return f"{name}.none is a list of authorities (no `/`, `?`, `#`, `@`), not {v!r}"
            else:
                return (f"{name}: {k!r} is not a word of the dictionary — host ({' | '.join(GROUP_SCHEME_WORDS['host'])}), "
                        f"fragment ({' | '.join(GROUP_SCHEME_WORDS['fragment'])}), none: [<authority>]")
    return ""


def rfc_spelling(v: str, schemes: dict | None = None) -> str:
    """`v` as RFC 3986 reads it by its scheme's words: a scheme with no fragment (`fragment: none`) has its `#` escaped,
    a character of the address like another; any other address is itself."""
    scheme, sep, _ = v.partition("://")
    opts = ((schemes or {}).get(scheme.lower()) or {}) if sep else {}
    return v.replace("#", "%23") if opts.get("fragment") == "none" else v


def _digits(p: str) -> bool:
    return p.isascii() and p.isdigit()


def _unescaped(s: str) -> str:
    """`s` percent-decoded until nothing more decodes (`%2540` is `%40` once and `@` twice); a stray `%` stays."""
    for _ in range(8):
        d = re.sub(r"%([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), s)
        if d == s:
            break
        s = d
    return s


def _split_port(a: str) -> tuple[str, str | None] | None:
    """An authority's host and port as written (`None` for no port) — after the `]` of an IPv6 literal, else after its
    last `:`; `None` when something other than a port follows the `]`."""
    if a.startswith("["):
        rb = a.find("]")
        if rb < 0:
            return a, None
        after = a[rb + 1:]
        if not after:
            return a, None
        return (a[:rb + 1], after[1:]) if after.startswith(":") else None
    c = a.rfind(":")
    return (a, None) if c < 0 else (a[:c], a[c + 1:])


def host_spelling(h: str) -> str:
    """A host as written, in its one spelling — "" when it is neither an IP literal (an IPv6 address in brackets, a zone
    after `%25` of unreserved characters, RFC 6874; an IPv4 address in dotted decimal, four parts, no leading zeros) nor a
    host name of RFC 1123 labels (letters, digits, `-`; 1 to 63 of them, not starting or ending with `-`; at most 253 in
    all; one trailing dot). A name whose last label is all digits must be the IPv4 address it looks like: `010.0.0.5`,
    `10.1` and `0x0a.0.0.1` are addresses to a reader that takes them for other addresses (RFC 1123 2.1)."""
    if not h.isascii():
        return ""
    if h.startswith("["):
        if not h.endswith("]"):
            return ""
        addr, zoned, zone = h[1:-1].partition("%")
        if zoned and not (zone.startswith("25") and zone[2:] and all(c in _UNRESERVED for c in zone[2:])):
            return ""
        try:
            a = ipaddress.IPv6Address(addr)
        except ValueError:
            return ""
        return str(a.ipv4_mapped or a)
    name = h[:-1] if h.endswith(".") else h
    if not 0 < len(name) <= 253 or not all(_HOST_LABEL.fullmatch(lb) for lb in name.split(".")):
        return ""
    if _digits(name.rsplit(".", 1)[-1]):
        try:
            return str(ipaddress.IPv4Address(name))
        except ValueError:
            return ""
    return name.lower()


def _authority_host(a: str, *, host: bool = True) -> str | None:
    """The host of an authority in its one spelling ("" when it is no host), or — `host=False` — whether the authority
    parses at all ("ok" or ""): a login in a login's characters and escapes, a port of digits, a name in a name's."""
    login, at, hostport = a.rpartition("@")
    if at and (not set(login) <= _LOGIN_CHARS or _BROKEN_ESCAPE.search(login)):
        return ""
    split = _split_port(hostport)
    if split is None or (split[1] and not _digits(split[1])) or not split[0]:
        return ""
    if host:
        return host_spelling(split[0])
    h = split[0]
    ok = h.startswith("[") or (set(h) <= _REG_NAME_CHARS and not _BROKEN_ESCAPE.search(h))
    return "ok" if ok else ""


def _path_login(path: str) -> bool:
    """A login written in the first segment of `path` (`host: path`): an `@` in it, escaped or not, or a password where
    the port goes (`10.0.0.5:hunter2`, or past a password holding a `/`)."""
    seg = path[1:].split("/", 1)[0]
    rest, plain = path[1 + len(seg):], _unescaped(seg)
    port = (_split_port(plain) or (plain, None))[1]
    return "@" in plain or (port is not None and (port != "" and not _digits(port) or "@" in _unescaped(rest)))


def path_login(v, schemes: dict | None = None) -> bool:
    """Whether the address `v`, of a scheme whose host stands in its path (`host: path`), writes a login there — the
    url rule's refusal at any url field (ADR 0053; the product's c13c25f), whatever the field's `secret_in` says."""
    s = "" if v is None else str(v)
    scheme, sep, rest = s.partition("://")
    opts = (schemes or {}).get(scheme.lower()) or {}
    if not sep or opts.get("host", "authority") != "path":
        return False
    cut = min([i for i in (rest.find("/"), rest.find("?")) if i >= 0], default=len(rest))
    path = rest[cut:].partition("?")[0]
    return bool(path[1:].split("/", 1)[0]) and _path_login(path)


# An `@` in a path segment, written or escaped once or more (`%40`, `%2540`): where a login in it ends.
_PATH_AT = re.compile(r"@|%(?:25)*40", re.IGNORECASE)


def _host_in_path(path: str) -> str:
    """The host written in the first segment of `path` (`host: path`), in its one spelling, or "". The segment is read
    up to its `/` and no further; a login in it (an `@`, written or escaped) ends at its last `@`, the host after it is
    read all the same — refusing the login is the url rule's (`path_login`), the group is the host's. A port after the
    host that is no number makes it unreadable (`10.0.0.5:hunter2`; `admin:pa/ss@h`, whose «host» is `admin:pa`): the
    host is then a login's, and a group by it would put strangers' rows together (ADR 0053, «Архитектор» 2026-10-06)."""
    seg = path[1:].split("/", 1)[0]
    ats = list(_PATH_AT.finditer(seg))
    hp = seg[ats[-1].end():] if ats else seg
    split = _split_port(hp)
    if split is None or not split[0] or (split[1] and not _digits(split[1])):
        return ""
    return host_spelling(split[0])


def url_host(v, schemes: dict | None = None) -> str:
    """The host the address `v` names, in its one spelling, by the spec's `schemes` — "" when it names none."""
    return host_of_url(v, schemes) or ""


def host_of_url(v, schemes: dict | None = None) -> str | None:
    """`url_host`, saying why there is none: "" when the spec says the address names none (its authority is one of the
    scheme's `none`, compared AS WRITTEN — port and login and all — in the host's one spelling: lowercased, no trailing
    dot; `file:1` is not `file`), and None when no host can be told — it is no address with an authority, its scheme is
    not among `schemes` (when they are said), it does not parse, or its host is neither a name nor an IP. With
    `cut_at: host` declared, None is a value the field refuses (`SubsystemSpec.group_refusal`; ADR 0053): `none` says
    the only addresses without a group. What the url rule refuses elsewhere in the address — a broken escape in the
    path, a fragment, a login — hides no host: refusing is the rule's, the group is the host's.

    A scheme whose host stands in its path (`host: path`) may have an empty authority (`x:///10.0.0.5/y`, legal by RFC
    3986): that its vendor is never empty is the subsystem's to say in the field's `schema`, not the platform's."""
    s = "" if v is None else str(v)
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in s):
        return None
    scheme, sep, rest = s.partition("://")
    if not sep or not _SCHEME_NAME.fullmatch(scheme.lower()):
        return None
    if schemes and scheme.lower() not in schemes:
        return None                                      # a scheme the field is not reached by: no host is read for it
    opts = schemes.get(scheme.lower()) or {} if schemes else {}
    if opts.get("fragment", "keep") == "keep":
        rest = rest.partition("#")[0]
    cut = min([i for i in (rest.find("/"), rest.find("?")) if i >= 0], default=len(rest))
    authority, path = rest[:cut], rest[cut:].partition("?")[0]
    if opts.get("none") and _authority_spelling(authority) in {_authority_spelling(a) for a in opts["none"]}:
        return ""
    if opts.get("host", "authority") == "path" and path[1:].split("/", 1)[0]:
        host = _host_in_path(path) if not authority or _authority_host(authority, host=False) else ""
    elif not authority:
        return None
    else:
        host = _authority_host(authority)
    return host or None


def _authority_spelling(a: str) -> str:
    """An authority as written, in the host's one spelling where it is a host alone (`FILE.` is `file`), else lowercased
    as it stands (`file:1`, `u@file`): what a scheme's `none` is compared in."""
    return host_spelling(a) or a.lower()


# THE ROWS THIS PROCESS WROTE, FOR A READER IN THE SAME PROCESS THAT REMEMBERS BETWEEN ITS TURNS (the eleventh review: the
# tenth's `REREAD`, not fixed). The console's request loop reads its rows whole every `jobs.Remembered.REREAD` seconds
# and, between, only the rows it remembers ending; an `until` given through the console's DOOR was written by another
# controller of the same process, which the loop's memory never heard of — a unit given `until = now + 1` there
# ended 23 s later. Every `create` and `update` notes its unit here (`wrote`); a reader takes what was written since it
# last looked (`take_written`) and reads those rows at its next turn. One reader per process takes them — the console
# runs one request loop — and a reader in ANOTHER process is told nothing: the store has no change feed to tell it by.
_WRITTEN: dict[str, set[str]] = {}
_WRITTEN_LOCK = threading.Lock()


def wrote(spec_name: str, uid) -> None:
    with _WRITTEN_LOCK:
        _WRITTEN.setdefault(spec_name, set()).add(str(uid))


def take_written(spec_name: str) -> set[str]:
    """The units of `spec_name` this process wrote since the last call — and forgotten here."""
    with _WRITTEN_LOCK:
        return _WRITTEN.pop(spec_name, set())


# ONE LOOK AT THE FOLLOWED SUBSYSTEM (the scaling pass): `SpecController.near_index`. Its live workers' `running` entries,
# by the value `near` matches — their unit id, or the field `near.of` names — in the order the heartbeats were read:
# `[(their unit id, worker, server)]`. And what ranking them has read (`memo`, `ranks`), for as long as the look lives.
class NearIndex:
    def __init__(self, by: dict[str, list[tuple[str, str, str]]]):
        self.by, self.memo, self.ranks = by, {}, {}


# Sort key: numeric ids before others, numbers by value.
GARBLED_ROW = object()     # what `SpecController.parsed_unit` says of a row that does not parse: there, and unreadable


#
# By `doors.numeric`, never `isdigit` + `int` (the review's ninth pass): `"7²".isdigit()` is true and `int` raises — a
# name the API took, and every list of its subsystem (`units`, `/where`, a drain's order) went unanswered with it.
def _unit_key(u: str):
    n = numeric(u)
    return (0, n) if n is not None else (1, str(u))


# The `rev` a placement row gets when it is written again. One that does not parse counts from nothing: the row is
# being rewritten whole, and a word in `rev` must not stop the write that mends it.
# The sweep's list — `<sub>/sweep {at, digests}` — as `(digests, at)`; one that does not parse is NO list (the sixth
# pass, the follow-up). `put_blob` reads it on every upload, to take its digest off it: a row with half a list in it
# raised there, and no blob of the subsystem could be stored. Nothing is deleted on the word of a list nobody can
# read: the sweep reads it as empty and marks afresh — a new list, a new grace.
def _sweep_list(items) -> tuple[list, float]:
    try:
        marked = parse_json((items or {}).get("digests", "[]"))
        at = float((items or {}).get("at", 0))
    except PARSE_ERRORS:                              # `[` ten thousand deep too (`RecursionError`, the ninth review's sweep)
        return [], 0.0
    return (marked, at) if isinstance(marked, list) else ([], 0.0)


def _next_rev(it) -> int:
    try:
        return int((it or {}).get("rev", 0)) + 1
    except PARSE_ERRORS:                              # `rev: 1e999` (a hand edit): `int(inf)` (the tenth round's sweep)
        return 1


# What of `pieces` (a unit alone, or a group whole) does not fit `room` (each worker's free places) — used by the
# count of spares (`offer_spares`).
def _pack(pieces: list[int], room: list[int]) -> list[int]:
    """The pieces that do not fit: each — the largest first — onto the worker with the least room that takes it whole."""
    room, left = sorted(room), []
    for n in sorted(pieces, reverse=True):
        i = next((k for k, r in enumerate(room) if r >= n), None)
        if i is None:
            left.append(n)
            continue
        room[i] -= n
        room.sort()
    return left


def _bins(pieces: list[int], per: int) -> list[int]:
    """The workers of `per` places it takes to carry every piece whole: their room left, one per worker."""
    bins: list[int] = []
    for n in sorted(pieces, reverse=True):
        i = next((k for k, r in enumerate(bins) if r >= n), None)
        if i is None:
            bins.append(per - n)
        else:
            bins[i] -= n
    return bins


class SpecController(Controller):
    """The only writer of <name>/*, from a spec. Holds nothing; two instances
    are harmless; never on the recovery path. Every subsystem is a spec — the
    same code."""

    # `capacity` is only the number for a worker whose heartbeat says nothing (the spec's `capacity.default` when not given).
    # `cluster` is the name the snapshot carries (`$CLUSTER`, else `room-a` — М11's default, its env example's and
    # М12's; it was `cluster-a` here, the thirteenth review's «Вопросы» 4); one box is a cluster of
    # one.
    def __init__(self, spec: SubsystemSpec, vars_: Variables, objects: ObjectStore, capacity: int | None = None,
                 wall=time.time, cluster: str | None = None):
        from . import catalog
        catalog.near_known(spec)                         # its neighbour's spec, loaded by now — or no controller (ADR 0056)
        catalog.requests_known(spec)                     # …and the families its worker files to (ADR-0012, ADR-0054)
        super().__init__(spec.sub, vars_, objects, wall)
        self.spec = spec
        self.capacity = capacity if capacity is not None else spec.capacity_default   # the FALLBACK for a worker whose heartbeat says nothing
        self.cluster = cluster or os.environ.get("CLUSTER", "room-a")                  # the name the snapshot carries; one box is a cluster of one
        self.rows_garbled = 0                                                            # rows the last `units()` could not parse (the review's second pass, M7)
        self._garbled_rows: set[str] = set()
        # What `failover_seconds` saw, by this process's clock: per worker the instance, its `ts` and when that last moved;
        # the gaps it saw between two instances; the largest it measured; and how many it could not measure.
        self._hb_moved: dict[str, tuple] = {}
        self._failover_seen: dict[str, float] = {}
        self.failover_worst, self.failovers_unmeasured = 0.0, 0
        self._pass_failing: set[str] = set()             # the steps of `pass_once` whose last run raised: said once each
        self._server_rows_last: dict | None = None       # the servers' labels last read from the console's rows (`server_labels`)
        self._server_rows_unread: set[str] = set()       # …and the servers whose row is there and did not read on that read
        self.last_reach_moves = 0                        # what the last `ensure_reach` moved or unplaced (the pass report)
        self.last_reach_waiting = 0                      # …and the units of groups it left whole where they are (the eleventh)
        self._reach_said: set = set()                    # …those groups, said in the log once a spell
        self._reach_budget_said: set = set()             # …those left for the budget, said in the journal once a spell
        self.reach_budget = reach_budget(os.environ)     # moves `ensure_reach` makes in one pass (`REACH_BUDGET`)
        self.last_leaving_waiting = 0                    # units `redistribute` could not move off a leaving worker
        self._leaving_said: set = set()                  # …the groups of them, said in the log once a spell
        # The key that seals `*_secret` fields on the way into the store (`sealing.py`) — the console's process
        # has it (`SECRETS_KEY`); a process without it writes secrets in the clear, and says so once.
        from .sealing import Sealer
        self.sealer = Sealer.from_env()

    # The row as it goes into the store: `*_secret` values sealed, when this process holds the key.
    def _sealed(self, items: dict, uid) -> dict:
        from .sealing import seal_items
        return seal_items(self.sealer, items, self.row_key(uid))

    # `<name>/<rows>/<id>` — the key of a unit's row: what a subsystem reads a row by (exported for that, the boundary's
    # step 5: a subsystem's console called the private name).
    def row_key(self, uid) -> str:
        return self.sub.config(self.spec.rows, str(uid))

    # -- what the workers say --------------------------------------------------------
    # The worker's own number from its latest heartbeat (`extra[capacity_from]`, any age), else the
    # fallback. `test_capacity_is_the_workers_word_not_the_controllers`: workers saying 2 and 6 are placed
    # by 2 and 6; an unknown worker gets 50.
    #
    # A NUMBER THAT IS A WORD (the sixth pass, the follow-up). A heartbeat that does not parse is skipped where it
    # is read (`parse_heartbeat`); one that parses and carries a word where a number is read here raised here — and
    # `capacity_of` is asked of every candidate while ANY unit is placed, so one worker's field stopped every
    # placement. Such a field is read as "it has not said" (`_number`): the fallback, no headroom, no failover time.
    def capacity_of(self, worker: str) -> int:
        hb = self._said(worker)
        said = self._number(worker, hb, self.spec.capacity_from, int) if hb else None
        return self.capacity if said is None else said

    # What a worker last said, any age — the four questions above and `place_of` ask it per candidate and per unit placed.
    # Inside a pass it is one dict built once (`_per_pass`; the scaling pass), not a walk of every heartbeat per question.
    def _said(self, worker: str):
        return self._per_pass(self.sub.heartbeats_prefix(), lambda: self.workers_seen(max_age=1e12), "any_age").get(worker)

    # Through `rows.number` (the review's ninth pass, the sibling of `failover_seconds`): its own `(ValueError, TypeError)`
    # let `int(inf)` — `headroom: Infinity`, which JSON reads — raise `OverflowError` out of `headroom()`, and every
    # placement with it; and `inf` passed as a number.
    def _number(self, worker: str, hb, field: str, kind=float):
        """A numeric field of a worker's heartbeat, or None if it is absent or not a finite number (counted once)."""
        from .rows import number
        if field not in hb.extra:
            return None
        return number(f"{self.sub.heartbeat_key(worker)}#{field}", hb.extra[field], kind, None)

    # What this worker's server reaches, as placement reads it: the administrator's row for the server when there is
    # one (`server_labels`, feedback DQ), the worker's own word otherwise (`node_labels_of`) — and, while what the server
    # reaches is not known (`server_labels_of` says `unknown`), what its row last said, or nothing: a unit that needs a
    # label is not placed there, one that needs none is.
    def labels_of(self, worker: str) -> set[str]:
        labels, said_by = self.server_labels_of(self.server_of(worker))
        return self.node_labels_of(worker) if said_by == "node" else set(labels or ())

    # The `labels` string of its heartbeat, split on commas — the node's `LABELS` (the platform's
    # `w2c.env`, or a unit's), read by the worker when it starts: the first value of a new box and the fallback of every other.
    def node_labels_of(self, worker: str) -> set[str]:
        hb = self._said(worker)
        return set(l for l in str(hb.extra.get("labels", "")).split(",") if l) if hb else set()

    # -- what a server reaches, from the console (feedback DQ) ----------------------------------------------------
    # A unit's labels say which network segments its address answers on; a server's say which ones the machine is
    # plugged into. The server's half came from the node alone: `LABELS` in the server's environment (`w2c.env`, or a
    # unit's), read by a worker when it starts. Changing it was a file on the machine and a restart, for a fact the operator
    # learns in the console, beside the units that carry the same labels — and a label decided only the NEXT
    # placement: a unit stayed on a server that no longer reached its VLAN, served by nobody, and nothing said so.
    #
    # So a server may have a row, `platform/servers/<server> {labels: "a,b"}` — the platform's, ONE a server for every
    # subsystem (ADR-0026, its addition; §3 row 4 of the boundary note): a machine carries every subsystem, and what it
    # reaches decides where the units of each may go. It was `<sub>/servers/<server>`, one per subsystem, and the same
    # machine could reach `vlan:a` for one subsystem and nothing for another. Written by the console at its root
    # (`PUT`/`DELETE /servers/<server>/labels`, `Mount.labels_route`, admin on the whole cluster). Where it exists it IS
    # the server's labels — empty too, which says "this machine reaches nothing"; where it does not, the node's answer.
    # Placement reads the rows once a pass (`_per_pass`), and `ensure_reach` moves what a server no longer reaches.
    #
    # A STORE THAT DOES NOT ANSWER MOVES NOTHING. The rows last read are kept (`_server_rows_last`): a hiccup must not
    # turn every server back to its node's labels for one pass and move the units the administrator placed by his.
    # A process that has never read them says None — and knows NO server's labels (`server_labels_of`: `unknown`), not
    # its node's: a unit with a label is placed nowhere, a unit without one is placed, and `ensure_reach` moves nothing.
    # Placing by the node's `LABELS` there was placing by a guess — the very word the row was written to correct
    # («Архитектор», ADR-0026's addition; the product's 59808df). The node answers only for a server whose rows WERE read
    # and that has none.
    #
    # …AND A ROW THAT DID NOT READ IS NOT KNOWN, NOT "NO ROW" (the review's tenth pass, major; a run). A row that did not
    # parse kept what was last read of that server, else its NODE's: after a restart of the controller there was no
    # last read, the node's `LABELS` was the stale `vlan:b` the row had been written to correct, and `ensure_reach`
    # took 12 units of 12 off the server in two passes, "srv-a no longer reaches vlan:a". And a listing that left
    # the row out for one pass was "no row": the node's labels again, 5 units of 5 moved, and they did not come back.
    # Now each server's row is read BY ITS KEY — the listed ones, the servers this subsystem's workers run on, and the
    # ones read before — so a listing that misses a row costs nothing; and a server whose row is there and did not read
    # (garbled, no `labels`, a read that failed, a listed key the read does not find) is UNREAD this pass
    # (`_server_rows_unread`): it keeps the labels last read of it, and with none it reaches no label (`labels_of`) —
    # nothing that needs one is placed there — and `ensure_reach` moves nothing off it. One such row is that server's
    # alone: the others are read.
    def server_labels(self) -> dict[str, frozenset] | None:
        """`{server: labels}` from the console's rows — None while this process has never read them."""
        prefix = SERVERS_PREFIX

        def read():
            last = self._server_rows_last or {}
            try:
                listed = {k[len(prefix):] for k in self.vars.list(prefix)}
            except Exception as e:                     # noqa: BLE001 — a store that does not answer: the rows last read
                self._failed("server_labels", f"the servers' labels could not be read ({e}); the last read are kept")
                return self._server_rows_last
            rows, unread = {}, set()
            for server in sorted(listed | self._worker_servers() | set(last)):
                key = prefix + server
                try:
                    it, _ = self.vars.get(key)
                except Exception as e:                 # noqa: BLE001 — that server's row, not every server's
                    SERVER_LABELS.garbled(key, f"it could not be read: {e}")
                    it = ()
                if it is None and server not in listed:
                    continue                           # no row: the node's labels answer
                if it is None:
                    SERVER_LABELS.garbled(key, "the listing names it and a read finds nothing")
                # a row with no `labels` is garbled, not "reaches nothing" — that is `labels: ""`
                got = SERVER_LABELS.read(key, lambda: parse_labels(it["labels"])) if isinstance(it, dict) else None
                if got is not None:
                    rows[server] = got
                    continue
                unread.add(server)
                if server in last:
                    rows[server] = last[server]
            self._works("server_labels")
            self._server_rows_last, self._server_rows_unread = rows, unread
            return rows
        return self._per_pass(prefix, read, "server_labels", rows=True)

    # The servers this subsystem's workers say they run on, whatever their age — each one's row is read by its key.
    def _worker_servers(self) -> set[str]:
        seen = self._per_pass(self.sub.heartbeats_prefix(), lambda: self.workers_seen(max_age=1e12), "any_age")
        return {s for hb in seen.values() if isinstance(s := hb.extra.get("server"), str) and SERVER_WORD.fullmatch(s)}

    # Whether a server's row is there and did not read on the last read (`server_labels`): what it reaches is not known.
    def labels_unread(self, server: str) -> bool:
        self.server_labels()
        return server in self._server_rows_unread

    # What a server reaches as placement reads it, and from where (the product's `ServerLabelsOf`): `console` — its row,
    # read whole; `unknown` — its row is there and did not read on the last read, or this process has never read the
    # rows, with what its row last said if anything (None: nothing); `node` — the rows were read and it has none: its
    # workers' heartbeats answer (`node_labels_of`), and the labels here are None.
    def server_labels_of(self, server: str) -> tuple[frozenset | None, str]:
        rows = self.server_labels()
        if rows is None:
            return None, "unknown"
        if server in self._server_rows_unread:
            return rows.get(server), "unknown"
        if server in rows:
            return rows[server], "console"
        return None, "node"

    # Where a server's labels come from now: `console`, `unknown` or `node` (`server_labels_of`).
    def labels_source(self, server: str) -> str:
        return self.server_labels_of(server)[1]

    # How many servers' rows did not read on the last read — -1 while this process has never read them (the product's
    # `ServersLabelsUnread`): a console that counts is told from one that knows nothing.
    def labels_unread_count(self) -> int:
        return -1 if self.server_labels() is None else len(self._server_rows_unread)

    # The servers anybody has announced: this subsystem's workers (any age), the resources, the rows there are. A label
    # row is written only for one of these (the review's tenth pass, minor: a typo was 200 and a row nobody reads) — of
    # ANY subsystem the console serves (`Mount.servers_known` unites these): the row is the server's, not a subsystem's.
    def servers_known(self) -> set[str]:
        from .resource import resources_seen
        out = set(self._worker_servers()) | set(self.server_labels() or {}) | set(self._server_rows_unread)
        try:
            out |= {s for s in resources_seen(self.objects) if isinstance(s, str)}
        except Exception:                              # noqa: BLE001 — the resources not listed: the workers' word
            pass
        return out

    # The console's two writes. The row is written whole — a set of labels, not an edit of one — and the controller
    # reads it on its next pass. Refused: a server that is no name, a label that is not one (`LABEL_WORD`).
    #
    # …and only strings (the review's tenth pass, minor: `[null]`, `[true]`, `[1]` were the labels `None`, `True`, `1`),
    # and only for a server somebody has announced (`known`, else `servers_known`): a typo wrote a row no server reads,
    # and said 200. The console's root asks it with every subsystem's servers (`Mount.labels_route`).
    def set_server_labels(self, server: str, labels, known: set[str] | None = None) -> list[str]:
        server = server_name(server)
        if not isinstance(labels, (list, tuple)) or not all(isinstance(l, str) for l in labels):
            raise Refused('the labels are {"labels": ["vlan:cctv-a", …]}, each a string; [] for none')
        if server not in (self.servers_known() if known is None else known):
            raise Refused(f"no server {server} is known here: no worker and no resource of it has reported, and it has "
                          f"no row — check the name")
        out = sorted({str(l).strip() for l in labels})
        bad = [l for l in out if not LABEL_WORD.fullmatch(l)]
        if bad:
            raise Refused(f"a label is letters, digits and _ . : - (up to 64), not {bad[0]!r}")
        self.vars.put(server_key(server), {"labels": ",".join(out)})
        return out

    def clear_server_labels(self, server: str) -> bool:
        """The row goes; the node's labels answer again. False when there was none."""
        key = server_key(server_name(server))
        if self.vars.get(key)[0] is None:
            return False
        self.vars.delete(key)
        return True

    # What would move if `server` reached `labels` (None: its node's) — asked by the page before it writes, with the
    # same constraint the pass asks: the units placed on that server's workers that would no longer pass it. This
    # subsystem's ids; the console's root names them `<sub>/<id>` across every spec (`Mount.would_move`).
    def would_move(self, server: str, labels) -> list:
        rule = CONSTRAINTS[self.spec.constraint]
        out = []
        with one_pass(self):
            for row in self.units():
                pl = self.placement(row["id"])
                if pl is None or self.server_of(pl.worker) != server or self.retired(row):
                    continue
                has = self.node_labels_of(pl.worker) if labels is None else set(labels)
                if not rule(row, has):
                    out.append(row["id"])
        return out

    # The heartbeat's `server`, `"?"` if unknown. Goes into placement reasons and the snapshot.
    def server_of(self, worker: str) -> str:
        hb = self._said(worker)
        return hb.extra.get("server", "?") if hb else "?"

    # The place this worker occupies, in the units the spec counts in: its server, or its volume when the
    # subsystem says `place_by: volume`. `"?"` when the worker has not said — and an unknown place never
    # matches a home, so a unit with a home waits rather than landing somewhere at random.
    def place_of(self, worker: str) -> str:
        if self.spec.place_by == "server":
            return self.server_of(worker)
        hb = self._said(worker)
        if hb is None:
            return "?"
        # Three cases, and the difference between the last two is the point.
        #
        # The field NAMES a place — the ordinary one: that is where this worker is.
        #
        # The field is ABSENT: one volume named after the server. That is the truth for every box with one
        # disk, it is what a worker written before the field existed means, and where it is NOT the truth
        # it errs the safe way — three workers on three disks that nobody told apart read as three on
        # one place, and `distinct` idles two of them rather than letting two think they own the same disk.
        #
        # The field is PRESENT AND EMPTY: the worker says it is on NO place — a spare, running and holding
        # nothing, waiting for a place to become free. Reading that as its server would be the worst
        # answer available: the spare would share a place with the worker that actually owns the disk,
        # and `distinct` would idle one of the two at random.
        if self.spec.place_by in hb.extra:
            return str(hb.extra[self.spec.place_by])
        return str(hb.extra.get("server", "?"))

    # Sum of `extra[headroom_from]` over workers seen in the last 45 s — `<name>_headroom` on `/metrics`, what the
    # service manager's operator watches beside the spares the controller offers (`offer_spares`). Stale until the
    # workers heartbeat again after a placement.
    def headroom(self) -> int:
        return sum(self._number(w, hb, self.spec.headroom_from, int) or 0 for w, hb in self.workers_seen().items())

    # -- units ------------------------------------------------------------------------
    # For numeric ids, bump `<name>/next_id {n}` by CAS and return it; otherwise `Refused` (the unit is
    # named by its field).
    #
    # A COUNTER THAT DOES NOT PARSE (the review's seventh pass, a minor): `n: "seven"` raised here, and not one unit of
    # the subsystem could be created until somebody mended the row by hand. It is counted once (`NEXT_IDS`, through the
    # one reader of rows) and the next number is one past the LARGEST id under `<name>/<rows>/` — the deleted rows
    # included, which stay as marks, so a number once given is not given again — and the CAS writes the row whole.
    def _next_id(self):
        if self.spec.numeric:
            key = self.sub.config("next_id")

            def bump(it):
                n = NEXT_IDS.read(key, lambda: int(finite(it.get("n", 0) or 0)))
                return {"n": (self._largest_id() if n is None else n) + 1}
            new = self.write(key, bump)
            return int(new["n"])
        raise Refused(f"a {self.spec.name} unit is named by its {self.spec.id}")

    def _largest_id(self) -> int:
        prefix = self.sub.config(self.spec.rows, "")
        ids = [k[len(prefix):] for k in self.vars.list(prefix)]
        return max([n for i in ids if (n := numeric(i)) is not None] + [0])     # `doors.numeric`: not `isdigit` + `int`

    # Keep every derived row in step: on create/update write `{item: to_item(row[field])}` only if it
    # differs; on delete write `on_delete` if set and the row exists.
    def _derived(self, row: dict | None, uid, deleted: bool = False) -> None:
        for d in self.spec.derived:
            path = self.sub.config(*d.row.replace("{id}", str(uid)).split("/"))
            if deleted:
                if d.on_delete is not None:
                    # Written whether or not the row was there. "If the row exists" was the rule, and it stopped
                    # being right the day a field could be left to INHERIT (М12 Lesson 12): such a unit has no
                    # derived row at all, so deleting it wrote nothing, and what the row governs lived on by the
                    # subsystem's default — a deleted unit's events, for a year (found with feedback BO).
                    self.write(path, lambda it, v=d.on_delete: {k: str(x) for k, x in v.items()})
                continue
            # A field left to inherit gives no item: the derived row then says nothing, and its reader goes on
            # down its own chain — the resource's retention falls back to the subsystem's, then to a year.
            want = {k: self.spec.fields[f].to_item(row[f]) for k, f in d.items.items() if row.get(f) is not None}
            self.write(path, lambda it, want=want: None if it == want else want)

    # `refuse`, choose the id (numeric: `_next_id`; else the field's value, which must be present and not
    # already exist), build the row with `new_row`, write it with `cas=0` (create-only), write derived rows,
    # return the row. Placement is not done here — the controller's pass does it; the console reports
    # `worker: None`.
    #
    # `uid` and `reserve` are the console's (`IdempotencyKeys`): the id is RESERVED in the request's claim before the
    # row is written (`reserve(uid)`), so a retry that takes over a stale claim creates under the same id — or finds
    # the unit created and answers with it. "The reply was lost" and "the write was never made" look the same from
    # outside; the reserved id tells them apart (the review's second pass; the product's `CreateAs`, feedback CS).
    def create(self, fields: dict, uid=None, reserve=None) -> dict:
        self.spec.refuse(fields)
        self._refuse_labels(fields, ())
        if uid is not None:
            old = self.unit(uid)
            if old is not None:
                return old                                              # created by the attempt whose reply was lost: the row is the answer
        if self.spec.numeric:
            uid = self._next_id() if uid is None else self.spec.parse_id(uid)
        else:
            uid = str(fields.get(self.spec.id) or "")
            if not uid:
                raise Refused(f"a {self.spec.name} unit needs a {self.spec.id}")
            # A named unit's id comes VERBATIM from the operator's body, and from here it becomes three
            # things: the key `<sub>/<rows>/<id>`, the prefix an ACL is matched against, and a directory on
            # a resource's disk (`events.unit_dir`). So it is a name, not a path: no separators, and not a
            # relative one. `variables.safe_path` refuses the same shapes one layer down — this one is a
            # 400 to the person who typed it rather than a 500 from the store.
            if "/" in uid or uid in (".", ".."):
                raise Refused(f"a {self.spec.name} {self.spec.id} is a name, not a path: {uid!r}")
            # …and a name that goes into other text whole (the review's eighth pass, part 4, and its question about `|`,
            # `"` and the newline): a label value on `/metrics` (escaped there too, for the names already stored —
            # `console.label`), a `|`-joined field of a heartbeat (`closed`, `hits`), a log line. Refused here, the rule
            # the domain keeps for a user's name (`domain/grants.py`, `name_refused`): no `"`, no `|`, no control
            # character or line or paragraph separator (Unicode Cc, Zl, Zp).
            # …and a unit's name is in lists and sorted as a number (the ninth pass, sibling B of the product team): no
            # `,` — an assignment is its units joined by one — and no digit but ASCII 0–9 (`doors.unnamable`, `unit`).
            bad = unnamable(uid, unit=True)
            if bad:
                raise Refused(f"a {self.spec.name} {self.spec.id} may not hold {', '.join(repr(c) for c in bad)}: {uid!r}")
        if reserve is not None:
            reserve(uid)                                                # into the claim, before the row exists
        self.refuse_refs(uid, None, self.spec.new_row(uid, fields))  # what its fields point at, what is one per cluster
        if not self.spec.numeric:
            old, idx = self.vars.get(self.row_key(uid))
            if old and old.get("deleted") != "true":
                raise Exists(f"{self.spec.name} unit {uid} exists")
            # A NAME STAYS ITS UNIT'S (the review's fifth pass, major). A unit's name is also the name of what it left
            # behind — what its workers wrote under it — and readers find that by the name. Deleted as one unit's and
            # created again about another, the name handed the first one's history to whoever may view the second.
            # The tombstone keeps every field, the `fixed` ones with them: the name comes back with the same values,
            # and with others it is refused — whatever was written under it is still there, and nothing here can know
            # when the last of it is gone, so "reuse once it is empty" is not a rule this controller could keep.
            moved = self.spec.fixed_changed(old, fields) if old else None
            if moved:
                raise Refused(f"the name {uid} was {moved} {old[moved]}'s, and what was written under it still is: "
                              f"create {moved} {fields[moved]}'s under another name")
            if old:                                                 # a named unit deleted earlier comes back under its name:
                r = self.spec.new_row(uid, fields)                  # a fresh row, one revision on from the old one, by CAS on it
                r["revision"] = int(old.get("revision", 0)) + 1
                self.vars.put(self.row_key(uid), self._sealed(self.spec.items(r), uid), cas=idx)
                wrote(self.spec.name, uid)                          # for this process's readers that remember (`take_written`)
                self._derived(r, uid)
                return r
        r = self.spec.new_row(uid, fields)
        self.vars.put(self.row_key(uid), self._sealed(self.spec.items(r), uid), cas=0)
        wrote(self.spec.name, uid)
        self._derived(r, uid)
        return r

    # WHAT A ROW MAY POINT AT, AND WHAT IS ONE PER CLUSTER (the boundary's step 6; the review's sixth pass, two majors of
    # one class, where it was a subsystem's code called here): a field's `ref` + `must_match`, and its `unique`. Called
    # by `create` and `update` with the row as it was (None for a create) and as it will be, before anything is stored —
    # every writer of rows comes through here, a request turned into a row as much as an operator's edit. The gate asks
    # who may; this says what may be. Each asked only when the field's value is new to the row.
    def refuse_refs(self, uid, old: dict | None, new: dict) -> None:
        def changed(n: str) -> bool:
            return old is None or str(old.get(n) or "") != str(new.get(n) or "")
        for n, f in self.spec.fields.items():
            v = str(new.get(n) or "")
            if f.must_match and v and (changed(n) or any(changed(m) for m in f.must_match.values())):
                sub, rows = f.ref.split("/")
                try:
                    items, _ = self.vars.get(f"{sub}/{rows}/{v}")
                    if items is not None and not isinstance(items, dict):
                        raise TypeError(type(items).__name__)
                except (Garbled, *PARSE_ERRORS):
                    raise RefGarbled(f"{n} names {f.ref}/{v}, whose row does not parse: mend it first — nothing points "
                                  f"at a row nobody can read") from None
                if items and items.get("deleted") != "true":
                    for theirs, mine in f.must_match.items():
                        want = str(items.get(theirs) or "")
                        if want and str(new.get(mine) or "") != want:
                            raise Mismatched(f"{n} {v} is {theirs} {want}'s: only that {theirs}'s rows point at it, and "
                                          f"{uid} is {mine} {new.get(mine)}'s")
        unique = [(n, f) for n, f in self.spec.fields.items() if f.unique and str(new.get(n) or "") and changed(n)]
        if not unique:
            return
        same = {n: (canonical_url if f.unique == "canonical" else str)(new[n]) for n, f in unique}
        for row in self.units():
            if str(row["id"]) == str(uid):
                continue
            for n, f in unique:
                if row.get(n) and (canonical_url if f.unique == "canonical" else str)(row[n]) == same[n]:
                    raise NotUnique(f"{self.spec.name} {row['id']} has that {n} already: one {n} is one unit — change "
                                  f"that one, or delete it first")

    # The labels a unit is placed by, in the one alphabet (`LABEL_WORD`; the review's tenth pass): a unit with `склад`
    # was placed by the node's word and taken off its server as soon as an administrator gave that server a row, which
    # cannot hold the word.
    def _refuse_labels(self, fields: dict, old) -> None:
        if self.spec.constraint != "labels-subset" or "labels" not in fields or "labels" not in self.spec.fields:
            return
        why = label_refusal(self.spec.fields["labels"].parse(fields["labels"]), old)
        if why:
            raise Refused(why)

    # `refuse`, then read-modify-write the row: `KeyError` if missing or marked deleted; parse each field
    # into the row; bump `revision` (the trigger from М9 Lesson 5, now in the controller — the worker
    # restarts what it runs on a new revision); write. Derived rows are refreshed only if one of their
    # source fields changed.
    #
    # A `fixed` FIELD IS SET AT CREATION (the review's fourth pass, major). A unit that is ABOUT another (`about`) is
    # judged by the gate on the unit its row names NOW; a PUT that changed the field passed on the old unit and moved
    # the row — and its history, its alarms, the scenarios on it — to the new one. Rights on both would make the move
    # legal for somebody who holds both, and it would still be one unit's history going on as another's; so a fixed
    # field does not change. The same value is no change — a page sends the whole form.
    def update(self, uid, fields: dict) -> dict:
        self.spec.refuse(fields)
        # A secret sent EMPTY or null on an edit keeps the stored one (the thirteenth round; the product's rule): a page
        # whose field was typed in and cleared sends `""`, and that wiped the unit's password. Left out, it is kept —
        # unless the address it is the key to changed (`bound_to`), and then the edit is refused below.
        fields = {k: v for k, v in fields.items() if not (is_secret_field(k) and (v is None or v == ""))}
        def mutate(it):
            if not it or it.get("deleted") == "true":
                raise KeyError(uid)
            r = self.spec.row(it)
            moved = self.spec.fixed_changed(r, fields)
            if moved:
                raise Refused(f"`{moved}` is fixed when the unit is created: {uid} is {moved} {r[moved]}'s — create one "
                              f"for {fields[moved]} under another name (this one stays {r[moved]}'s, deleted or not)")
            was = dict(r)
            for k, v in fields.items():
                r[k] = self.spec.fields[k].take(v)
            for k, f in self.spec.fields.items():
                why = unbound_secret(k, f.bound_to, was, r) if f.bound_to and k not in fields else None
                if why:
                    raise Refused(why)
            if "labels" in fields and self.spec.constraint == "labels-subset":
                why = label_refusal(r.get("labels"), was.get("labels") or ())
                if why:
                    raise Refused(why)
            self.refuse_refs(uid, was, r)            # what its fields point at, old and new; what is one per cluster
            r["revision"] += 1                       # the trigger from М9 Lesson 5, in the controller
            return self._sealed(self.spec.items(r), uid)
        r = self.spec.row(self.write(self.row_key(uid), mutate))
        wrote(self.spec.name, uid)                       # for this process's readers that remember (`take_written`)
        if any(f in fields for d in self.spec.derived for f in d.items.values()):
            self._derived(r, uid)
        return r

    # The operator's half: the row is marked `deleted: "true"` (not removed) and derived rows get their
    # `on_delete`. Its placement is the controller's half, taken back on the next pass by `unplace_deleted`
    # — the console writes as `console` (`acl_console`, its rights in the store), which cannot touch an
    # assignment, and does not need to.
    def delete(self, uid) -> None:
        """The operator's half: the row is marked. Its placement is the controller's
        half, taken back on the next pass (`unplace_deleted`) — the console's writer
        (`acl_console`) cannot touch an assignment, and does not need to."""
        self.write(self.row_key(uid), lambda it: {**it, "deleted": "true"} if it else None)
        self._derived(None, uid, deleted=True)

    # The controller's half of a delete: for every `placement/<id>` row with a worker whose unit no longer
    # exists, remove the unit from that worker's assignment and rewrite the placement as `{worker: "",
    # reason: "deleted", at, rev+1}`. Runs first in `ensure_placed` and `redistribute`. The console test:
    # after `DELETE /<rows>/1` the placement still says `w-1` until `unplace_deleted()` returns `[1]`.
    def unplace_deleted(self) -> list:
        """The controller's half of a delete: every placement whose unit is gone
        loses its assignment and its row says so. Runs first in every pass."""
        gone = []
        for p in self.vars.list(self.sub.config("placement") + "/"):
            uid = self._placed_id(p)
            it = self._placement_items(p)
            if uid is None or not it or not it.get("worker") or self.parsed_unit(uid) is not None:
                continue                                  # a row that does not parse EXISTS: it is not unplaced as deleted
            self.assign_remove(it["worker"], str(uid))
            self.write(p, lambda it: {"worker": "", "reason": "deleted", "at": self.wall(), "rev": _next_rev(it)})
            gone.append(uid)
        return gone

    # The unit a row under `<sub>/placement/` is about, or None when its name is no unit's id — a stray row there
    # raised out of the two passes that walk the placements, and so out of `ensure_placed` and `redistribute`, for
    # every unit (the sixth pass, the follow-up). Skipped, and said once.
    def _placed_id(self, path: str):
        try:
            return self.spec.parse_id(path.rsplit("/", 1)[1])
        except (ValueError, TypeError):
            if path not in self._garbled_rows:
                self._garbled_rows.add(path)
                log.warning("%s: %s is named after no unit; skipped", self.sub.name, path)
            return None

    # Whether this row says the work is over — `retire_when` in the spec, and nothing at all for the
    # subsystems that never end.
    def retired(self, row: dict | None) -> bool:
        if not self.spec.retire_field or row is None:
            return False
        return str(row.get(self.spec.retire_field, "")) in self.spec.retire_values

    # The other half of `retire_when`: a unit that FINISHED while placed gives its assignment back, so the
    # worker drops it and the budget it was holding is free again. Without this the predicate below only
    # stops the next placement, and a cluster's whole capacity ends up held by work that is over.
    #
    # The reason says which value did it, because "done" and "failed" are a very different message to the
    # person reading `/where/<id>`.
    def unplace_retired(self) -> list:
        """Every placement whose unit's row says the work is over loses its assignment."""
        done = []
        for p in self.vars.list(self.sub.config("placement") + "/"):
            uid = self._placed_id(p)
            it = self._placement_items(p)
            row = self.parsed_unit(uid) if uid is not None else GARBLED_ROW
            if not it or not it.get("worker") or row is GARBLED_ROW or not self.retired(row):
                continue                                  # whether a row that does not parse is over, nobody can say
            state = str(row.get(self.spec.retire_field, ""))
            self.assign_remove(it["worker"], str(uid))
            self.write(p, lambda i: {"worker": "", "reason": state, "at": self.wall(), "rev": _next_rev(i)})
            done.append(uid)
        return done

    # The row, or `None` if absent or deleted.
    def unit(self, uid) -> dict | None:
        it, _ = self.vars.get(self.row_key(uid))
        return self.spec.row(it) if it and it.get("deleted") != "true" else None

    # The same for the controller's loops over units ALREADY PLACED (the review's third pass): a row that does not
    # parse is `GARBLED_ROW` — logged once, counted by `units()` in `rows_garbled` like every other — instead of an
    # exception out of `unplace_deleted`, which ran first in `ensure_placed` and `redistribute`: one hand-edited
    # field on a placed unit, and no new unit was placed and no unit of a silent server moved, every pass.
    # Exported (the boundary's step 5): a subsystem's loop that reads a unit it remembers asks this, not the private name.
    def parsed_unit(self, uid):
        try:
            return self.unit(uid)
        except PARSE_ERRORS as e:                     # a `json` field ten thousand deep too (the ninth review's sweep)
            p = self.row_key(uid)
            if p not in self._garbled_rows:
                self._garbled_rows.add(p)
                log.warning("%s: row %s does not parse (%s); skipped", self.sub.name, p, e)
            return GARBLED_ROW

    # Every live row under `<name>/<rows>/`, sorted by `_unit_key`. A row that does not parse — a field edited by
    # hand, a build that wrote another layout — is ONE unit nobody serves, not the end of every caller's pass
    # (the review's second pass, M7): skipped, counted in `rows_garbled` (the pass report; `<sub>_rows_garbled`),
    # logged once per row until it parses again.
    #
    # Whatever a parse raises (`PARSE_ERRORS`: a row nested past what JSON reads, a number past a float, a row that is
    # not a map), and the read of a file store's row that is not JSON at all (the review's ninth pass, beside `7²`). A
    # row whose NAME a unit could not be created under today (`doors.unnamable`, `unit`: a `,`, a digit not ASCII) is
    # served as it stands, and counted and named once (`UNIT_NAMES`): somebody is to create it again under another name.
    def units(self) -> list[dict]:
        out, garbled = [], 0
        for p in self.vars.list(self.sub.config(self.spec.rows) + "/"):
            try:
                it, _ = self.vars.get(p)
                if not it or it.get("deleted") == "true":
                    continue
                out.append(self.spec.row(it))
            except PARSE_ERRORS as e:
                garbled += 1
                if p not in self._garbled_rows:
                    self._garbled_rows.add(p)
                    log.warning("%s: row %s does not parse (%s); skipped", self.sub.name, p, e)
                continue
            self._garbled_rows.discard(p)
            if (bad := unnamable(out[-1]["id"], unit=True)):
                UNIT_NAMES.garbled(p, f"its name holds {', '.join(repr(c) for c in bad)}")
            else:
                UNIT_NAMES.parsed(p)
        self.rows_garbled = garbled
        return sorted(out, key=lambda r: _unit_key(str(r["id"])))

    # -- placement ---------------------------------------------------------------------
    # The stored decision, `None` if no row or the worker is empty (unplaced).
    #
    # WHAT THE ROW DECIDES IS `worker` (the sixth pass, the follow-up); `reason`, `at` and `rev` are for a person.
    # All four were parsed bare, and the row of ONE unit is read while others are placed (`together`, `apart`), by
    # `unplaced()`, by `ensure_home`: an `at` with a word in it stopped them all. The decision is read as it stands;
    # what does not parse beside it is 0, and the row is said once.
    def placement(self, uid) -> Placement | None:
        key = self.sub.config("placement", str(uid))
        it = self._placement_items(key)
        if not it or not it.get("worker"):
            return None
        return self._placement(uid, it)

    # A placement row the store holds and cannot read (`Garbled`; the eleventh review, a minor): read bare, it took every
    # route and pass that asks where a unit is down whole. Read as placed nowhere — said once — and the controller's next
    # write of it replaces it whole (`Controller.write`): a unit whose decision nobody can read is placed again.
    def _placement_items(self, key: str) -> dict | None:
        try:
            it, _ = self.vars.get(key)
        except Garbled as e:
            if key not in self._garbled_rows:
                self._garbled_rows.add(key)
                log.warning("%s: %s; read as placed nowhere — it is placed again, and the row written whole",
                            self.sub.name, e)
            return None
        return it

    def _placement(self, uid, it: dict) -> Placement:
        key = self.sub.config("placement", str(uid))
        try:
            at, rev = float(it["at"]), int(it["rev"])
            self._garbled_rows.discard(key)
        except PARSE_ERRORS:                          # `rev: 1e999` too: `placement()` raised under every pass and route (the tenth round)
            at, rev = 0.0, 0
            if key not in self._garbled_rows:
                self._garbled_rows.add(key)
                log.warning("%s: placement row %s does not parse beyond its worker (%r); read as placed on %s",
                            self.sub.name, key, it, it["worker"])
        return Placement(self.spec.parse_id(uid), it["worker"], str(it.get("reason", "")), at, rev)

    # Assigned units on that worker — from the assignment row, not from the heartbeat.
    def load(self, worker: str) -> int:
        return len(self.assignment(worker).units)

    # Workers passing the spec's constraint against their labels.
    def eligible(self, row: dict, workers: list[str]) -> list[str]:
        rule = CONSTRAINTS[self.spec.constraint]
        out = [w for w in workers if rule(row, self.labels_of(w))]
        out = [w for w in out if self.server_of(w) not in self.servers_taken(row)]
        if self.spec.affinity:
            out = [w for w in out if self.admits(row, w)]
        # The group's worker is looked for in the pool as GIVEN, not in what the filters left (the eleventh review, a
        # minor): a channel whose group's worker no longer passed them — its server's row unread this pass, a label
        # given to this one channel — found no group in `out` and was placed alone on another worker, two sessions to one
        # box. Such a unit has no worker: it waits, and `_unplaceable` says beside whom.
        with_group = self.worker_with_group(row, workers)
        return [w for w in out if w == with_group] if with_group else out

    # The worker already carrying a unit of this row's group, if there is one and it is still in the pool.
    #
    # "Still in the pool" is the whole of the care needed here. A placement on a worker that is gone,
    # draining or idle by policy must NOT pin the group to it: that worker's units are on their way out,
    # and honouring its placement would make every unit of the group unplaceable at exactly the moment
    # the group has to move. Read from the live pool and the group re-forms wherever its first unit lands.
    #
    # Ties go to the smallest worker name so two passes agree — after a partial move two peers can sit on
    # two workers, and picking "whichever came first" would walk the group between them.
    def worker_with_group(self, row: dict, pool: list[str]) -> str | None:
        if not self.spec.group_by:
            return None
        value = self.group_value(row)
        if not value:
            return None
        mine, found = str(row["id"]), []
        for other in self._rows_by("group", self.group_value).get(value, ()):
            if str(other["id"]) == mine:
                continue
            pl = self.placement(other["id"])
            if pl is not None and pl.worker in pool:
                found.append(pl.worker)
        return sorted(found)[0] if found else None

    # What `group_by` names, for this row (`SubsystemSpec.group_of`): the field, or the host of the address in it, or
    # that address up to `cut_at`. "" is no group. Nobody overrides it any more (the boundary's step 6).
    def group_value(self, row: dict) -> str:
        return self.spec.group_of(row.get(self.spec.group_by, ""))

    # `affinity` (see the spec): may this unit go to this worker. The table's rows are read once a pass (`_per_pass`);
    # a row that does not parse binds nothing and refuses nothing here — what places a unit is not a row nobody can read.
    def admits(self, row: dict, worker: str) -> bool:
        aff = self.spec.affinity
        rows = self.table_rows(aff["table"])
        place = self.place_of(worker)
        here = rows.get(place)
        if here is not None and str(here.get("admits", "true")).lower() == "false":
            return False                                  # a place that takes nobody
        home = str(row.get(aff["field"]) or "")
        want = rows.get(home) if home else None
        if want is not None and self._binds(want):
            server = str(want.get(aff["server_field"]) or "") if aff["server_field"] else ""
            return place == home and (not server or self.server_of(worker) == server)
        return here is None or not self._binds(here)      # a binding place takes only the units homed on it

    def _binds(self, items: dict) -> bool:
        return all(str(items.get(k, "")).lower() in [x.lower() for x in vals]
                   for k, vals in self.spec.affinity["strict"].items())

    # `{name: items}` of one of this spec's tables, every row that reads — once a pass inside one.
    def table_rows(self, table: str) -> dict[str, dict]:
        prefix = self.sub.config(table, "")

        def read():
            out = {}
            for key in self.vars.list(prefix):
                try:
                    items, _ = self.vars.get(key)
                except (Garbled, *PARSE_ERRORS):
                    continue
                if isinstance(items, dict) and items:
                    out[key[len(prefix):]] = items
            return out
        return self._per_pass(prefix, read, "table", rows=True)

    # -- the spec's tables (`tables.py`; the boundary's step 6) -------------------------------------------------------
    # A row of a declared table written whole, by the console's token (`tables.write_row`: its rules, in words).
    def write_table_row(self, table: str, body: dict, user: str = "", said: dict | None = None) -> tuple[str, dict]:
        from .tables import write_row
        return write_row(self.spec, table, self.vars, body, user, self.wall(), self.sealer, self.units, said)

    def table_rows_shown(self, table: str) -> list[dict]:
        """Every row of a declared table, as a page may see it — a row that does not parse said as one."""
        from .tables import shown
        t = self.spec.table_specs[table]
        prefix, out = self.sub.config(table, ""), []
        for key in sorted(self.vars.list(prefix)):
            name = key[len(prefix):]
            try:
                items, _ = self.vars.get(key)
                if items is not None and not isinstance(items, dict):
                    raise TypeError(type(items).__name__)
            except (Garbled, *PARSE_ERRORS):
                out.append({"name": name, "garbled": True})
                continue
            if items:
                out.append({**shown(items, t.fields), "name": name})
        return out

    def delete_table_row(self, table: str, name: str) -> bool:
        from .tables import delete_row
        return delete_row(self.spec, table, self.vars, name)

    # Every live row by one value of it — the group, the spread field — built once a pass (`_per_pass`). Asked for every
    # unit waiting to be placed, it was every row read and parsed again for each: 500 units waiting of 600 cost a pass
    # 670 000 reads and ten seconds (the scaling pass; `tests/test_read_budget.py`). Rows in `units()` order.
    def _rows_by(self, name: str, value_of) -> dict[str, list[dict]]:
        def read():
            out: dict[str, list[dict]] = {}
            for r in self.units():
                out.setdefault(value_of(r), []).append(r)
            return out
        return self._per_pass(self.sub.config(self.spec.rows) + "/", read, name, rows=True)

    # The servers already carrying a unit that shares this row's `spread_by` value — where this one may
    # therefore NOT go. Empty when the subsystem does not ask to spread, which is every subsystem today.
    #
    # Read the whole rule in one sentence: two copies of one unit's work exist to survive one server, so
    # putting them on one server is not a compromise, it is the failure the operator was buying insurance
    # against. `near` pulls each copy towards the holder of what it follows and would otherwise pull BOTH copies to
    # the same place — the preference loses to the filter, and the reason says which.
    def servers_taken(self, row: dict) -> set[str]:
        field = self.spec.spread_by
        if not field:
            return set()
        value = row.get(field)
        if value in (None, ""):
            return set()
        mine, taken = str(row["id"]), set()
        for other in self._rows_by(f"spread:{field}", lambda r: str(r.get(field))).get(str(value), ()):
            if str(other["id"]) == mine:
                continue
            pl = self.placement(other["id"])
            if pl is not None:
                taken.add(self.server_of(pl.worker))
        return taken

    # -- the administrator's knobs: one row, `<name>/policy`, written by the console ---------------
    # `servers`: `shared` (default) — every worker is a place to put units, two on one server included (a
    # box IS several workers on one server). `distinct` — one worker per server carries units; a second worker
    # started on the same server idles by policy. Under either, a server whose worker and resource both fall
    # silent is gone (`gone_servers`) and its units move to the workers that are there: under an orchestrator
    # `shared` waited for the scheduler to bring the worker back on a neighbour, and without one nothing would
    # (М11, the rework without an orchestrator) — what the living have no room for is offered to a spare
    # (`offer_spares`). The administrator chooses on the console.
    POLICY_CHOICES = {"servers": ("distinct", "shared")}

    @property
    def POLICY_DEFAULTS(self) -> dict:                                   # the spec's `placement.servers` is the default; the row overrides
        return {"servers": self.spec.servers}

    def policy(self) -> dict:
        items, _ = self.vars.get(self.sub.config("policy"))
        out = dict(self.POLICY_DEFAULTS)
        for k, v in (items or {}).items():
            if k in self.POLICY_CHOICES and v in self.POLICY_CHOICES[k]:
                out[k] = v
        return out

    def set_policy(self, changes: dict) -> dict:
        for k, v in changes.items():
            if k not in self.POLICY_CHOICES or v not in self.POLICY_CHOICES[k]:
                raise Refused(f"policy {k} must be one of {', '.join(self.POLICY_CHOICES.get(k, ()))}")
        self.write(self.sub.config("policy"), lambda it: {**(it or {}), **{k: str(v) for k, v in changes.items()}})
        return self.policy()

    # Under `servers: distinct`, the workers that a server's OTHER workers must yield to: for each server,
    # the worker with units (the most, ties to the first name), else the first by name; the rest idle by
    # policy. Under `shared`, nobody.
    def idle_by_policy(self, workers) -> list[str]:
        if self.policy()["servers"] != "distinct":
            return []
        by_place: dict[str, list[str]] = {}
        for w in sorted(workers, key=slot_number):
            by_place.setdefault(self.place_of(w), []).append(w)
        idle = []
        for server, ws in by_place.items():
            if server == "?" or len(ws) < 2:
                continue
            keep = max(ws, key=lambda w: (self.load(w), -slot_number(w)))
            idle += [w for w in ws if w != keep]
        return idle

    # -- what the worker's server must have: a resource, when the spec says so ---------------------
    # The state of the resource on a server (`Controller.resource_state`: `live`, `silent`, `unknown`). The
    # server's units put a worker where disks are declared; this is the live fact: whether the resource
    # there still answers.

    # Workers whose server's resource is silent, when the spec requires one: not placed on, and (in
    # `redistribute`) moved off. A worker on a server whose resource was never seen passes — "silent" is
    # a fact, "unknown" is not one.
    # Live workers that say they hold no place, in a subsystem that places by one — spares. Not a fault in
    # itself; it is one when such a worker still has units assigned (`redistribute`).
    def placeless(self, workers) -> list[str]:
        if self.spec.place_by == "server":
            return []
        return [w for w in workers if self.place_of(w) == ""]

    # Live workers whose place is a row of the `affinity` table saying `admits: false`, `{worker: place}` (ADR 0056, its
    # addition; it was the product's `Unfit` hook). A place that takes no unit gives up the ones it has: "no new ones, the
    # old ones stay" kept units where the administrator closed the place, for ever, and said nothing. A row that does not
    # read and a table that does not list give nothing up — a unit is not moved on a guess. No spec key: `affinity` says
    # it already.
    def admitting_none(self, workers) -> dict[str, str]:
        if not self.spec.affinity:
            return {}
        try:
            rows = self.table_rows(self.spec.affinity["table"])
        except Exception as e:                           # noqa: BLE001 — a store that does not answer: nothing moves on it
            self._failed("admitting_none", f"the places of {self.spec.affinity['table']} could not be read ({e}); "
                                           f"no unit leaves a place for its `admits` until they are")
            return {}
        self._works("admitting_none")
        out = {}
        for w in workers:
            place = self.place_of(w)
            here = rows.get(place)
            if here is not None and str(here.get("admits", "true")).lower() == "false":
                out[w] = place
        return out

    def without_resource(self, workers) -> list[str]:
        if self.spec.requires != "resource":
            return []
        return [w for w in workers if self.resource_state(self.server_of(w)) == "silent"]

    # A server that is gone, not a process that crashed: the slot has lapsed and stayed lapsed for another
    # `lost_after` — the server's supervisor's chance to bring the process back under its name — AND the resource on
    # the slot's last known server is silent. One silence is a crash and is left alone; two independent silences from
    # the same server are a fact about the server. Only when the spec requires a resource, under any policy.
    #
    # That is still the rule where the server's resource cannot say who runs on it (`_moves_off_silent`). Where it can,
    # the one rule decides (`Controller.slot_fate`; the owner's decisions on the review's eleventh pass and on the
    # rework): a dead process at its slot's end, a silent server, a hung or unsure one past `hung_move_after` — `move`,
    # `hung_moved`, `unsure_moved` (`MOVED_FATES`). The name stays from when it meant only the second.
    def gone_servers(self, lost_after: float = 45.0) -> dict[str, str]:
        """Slots that stopped renewing whose units move now (`slot_fate`: `MOVED_FATES`): {slot: server}."""
        return {w: server for w, (fate, server, _) in self.fates().items()
                if fate in MOVED_FATES and self.assignment(w).units}

    # Under `shared` too: it waited for an orchestrator to reschedule the worker onto a neighbour, and there is none —
    # a gone server's units waited for ever (the rework without an orchestrator).
    def _moves_off_silent(self) -> bool:
        return self.spec.requires == "resource"

    # The given list, or the workers seen heartbeating in the last 45 s; minus those whose resource is
    # silent when the spec requires one; sorted.
    # Who may receive units now. Three exclusions, and the third is the one a catalogue teaches: a worker
    # that RELEASED its slot said it is leaving, and a service catalogue's answer to that is deregistration —
    # gone from the list at once, not in `lost_after` seconds when its heartbeat finally ages out. We have
    # the fact (`Slot.released`) and used it only to move units OFF such a worker (`redistribute`); without
    # this line the very next `place()` could put a new one back ON it, and the pass after that would move
    # it off again. A departure that still collects work is churn at every scale-in and every update.
    # Workers on the server being drained: not placed on, and (in `redistribute`) moved off. The third
    # kind of "not here" beside a released slot and a silent resource — and the only one the operator says
    # BEFORE it is true, which is the whole point of an upgrade.
    def on_draining(self, workers) -> list[str]:
        server = self.draining()
        return [w for w in workers if server and self.server_of(w) == server] if server else []

    # Workers on a server decommissioned (`Controller.decommission`): not placed on, and moved off — whatever comes
    # back on that machine, until the operator brings it back (`recommission`).
    def on_decommissioned(self, workers) -> list[str]:
        gone = self.decommission_requests()
        return [w for w in workers if self.server_of(w) in gone] if gone else []

    def _pool(self, workers):
        pool = sorted(workers if workers is not None else self.workers_seen())
        leaving = {n for n, s in self.slots().items() if s.released}
        gone = set(self.without_resource(pool)) | set(self.idle_by_policy(pool)) | leaving | set(self.on_draining(pool)) \
            | set(self.on_decommissioned(pool))
        return [w for w in pool if w not in gone]

    # The dry run. Which units nothing else could serve if this server went away — asked BEFORE it does,
    # with the machinery that will answer for real afterwards (`eligible` over the pool minus that server).
    # Fifty units leaving a machine have to land somewhere, and "somewhere" is a fact about headroom and
    # labels, not a hope. An upgrade script reads this and stops; the alternative is reading `/unplaceable`
    # after the reboot.
    def would_strand(self, server: str, workers: list[str] | None = None) -> list[str]:
        """Unit ids that nothing left could serve if `server` stopped now."""
        with one_pass(self):
            return self._would_strand(server, workers)

    def _would_strand(self, server: str, workers: list[str] | None) -> list[str]:
        pool = [w for w in self._pool(workers) if self.server_of(w) != server]
        out = []
        for row in self.units():
            uid = row["id"]
            pl = self.placement(uid)
            if pl is not None and self.server_of(pl.worker) != server:
                continue                                   # it is not on that server: not its business
            if not self._eligible_or_none(row, pool, "would_strand"):
                out.append(str(uid))                       # …nor one whose filters raise: nobody can say it lands
        return out

    # `eligible`, or `[]` when this unit's filters raise on its row — one unit's trouble, counted once a spell
    # (`UNIT_JUDGED`), not the end of the walk: a field that read and then raised in a comparison or in a filter took
    # `/unplaceable` and `/drain` down for every unit (the review's tenth pass).
    def _eligible_or_none(self, row: dict, pool: list[str], walk: str) -> list[str]:
        key = f"{self.row_key(row['id'])}#{walk}"
        return UNIT_JUDGED.read(key, lambda: self.eligible(row, pool), [])

    # `near: <sub>`: the worker of that subsystem whose heartbeat status lists this unit's id in phase
    # `running` — `(worker, server)` — or None. testsub2 says `near: {sub: testsub, …}`: its counter's holder.
    #
    # `near.of` names the field of THEIR status entry the value is matched against, instead of their unit
    # id: how a unit finds the worker running a unit of theirs ABOUT it without knowing what the operator named
    # that one. Ties (two of theirs about one of ours) go to the smallest of their ids, so two passes
    # over the same heartbeats reach the same server.
    #
    # FROM ONE LOOK, HANDED IN (the scaling pass). Each call read every heartbeat of the followed subsystem and walked
    # every entry in them — and `ensure_home` asks for every unit, `_pick` for every unit it places: a thousand units
    # beside the units of twenty workers they follow read the store 25 500 times, and walked every such worker's status
    # a thousand times. A caller asking for many units takes one look first — `near_index`, from the heartbeats it has
    # read already, if it has — and hands it in as `near`; a unit asked about alone takes a look of its own.
    def near_index(self, beats: dict | None = None) -> NearIndex:
        """The followed subsystem's live `running` entries, by the value `near` matches. `beats`: its heartbeats as
        `console.heartbeats` returns them, when the caller has read them; else they are read here, once."""
        if self.spec.near == "none":
            return NearIndex({})
        if beats is None:
            # Inside a pass the look is the pass's (`_per_pass`): its heartbeats read once, the index built once — and a
            # step that did not hand one in (`_pick` from `place`, `home_for`) gets the same one.
            from .console import heartbeats                        # the read model's scan, without the age filter
            prefix = f"{self.spec.near}/heartbeats/"
            # Memo names of their own (the review's tenth pass, minor): `""` was the list `Controller._heartbeats` keeps
            # under the same prefix, and the index is by `near_of` — two subsystems that follow one, one by a field and
            # one by id, shared one pass, and one got the other's index.
            beats = self._per_pass(prefix, lambda: heartbeats(self.objects, self.spec.near + "/"), "beats")
            return self._per_pass(prefix, lambda: self._near_index(beats), f"near_index:{self.spec.near_of}")
        return self._near_index(beats)

    def _near_index(self, beats: dict) -> NearIndex:
        by: dict[str, list[tuple[str, str, str]]] = {}
        field = self.spec.near_of
        for w, hb in beats.items():
            # live by what this controller saw change (`Eyes`; the review's thirteenth pass, blocker 4), not by the
            # followed worker's clock against this one
            if not self.eyes.fresh(f"{self.spec.near}/heartbeats/{w}", hb.token, 45.0, hb.ts, self.spec.near):
                continue
            for st in hb.status:
                if st.get("phase") == "running":
                    key = st.get(field) if field else st.get("id")
                    by.setdefault(str(key), []).append((str(st.get("id")), w, hb.extra.get("server", "?")))
        return NearIndex(by)

    def holder_near(self, uid, near: NearIndex | None = None) -> tuple[str, str] | None:
        if self.spec.near == "none":
            return None
        want = self.near_id(uid)                                   # `by`: which value of mine to look for
        if not want:
            return None
        near = self.near_index() if near is None else near
        found = near.by.get(want)                                  # (their unit id, worker, server)
        if not found:
            return None
        if not self.spec.near_of or len(found) == 1:
            return found[0][1], found[0][2]                        # their unit is mine, or one of theirs: nothing to rank

        def ranked(f):
            if not self.spec.near_prefer:
                return 0, f
            if f[0] not in near.ranks:
                near.ranks[f[0]] = 0 if self._preferred(f[0], near.memo) else 1
            return near.ranks[f[0]], f
        _, w, server = sorted(found, key=ranked)[0]
        return w, server

    # `near.prefer` of one of their units: whether its row — or the row its field refs (`home.kind`) — holds one of the
    # values, for every key. Their spec is the catalogue's (`catalog.py`): a controller whose process loaded none of
    # theirs is not built (`catalog.near_known`, ADR 0056) — it preferred nothing, a pass at a time, and said nothing.
    # What the second step reads — a table of theirs — is read once a look (`memo`, `NearIndex`), and each of their rows
    # once.
    def _preferred(self, their_id: str, memo: dict) -> bool:
        from . import catalog
        them = catalog.spec(self.spec.near)
        try:
            items, _ = self.vars.get(them.sub.config(them.rows, str(their_id)))
        except (Garbled, *PARSE_ERRORS):
            return False
        for path, vals in self.spec.near_prefer.items():
            first, _, second = path.partition(".")
            v = str((items or {}).get(first) or "")
            if second:
                f = them.fields.get(first)
                if not v or f is None or not f.ref:
                    return False
                if f.ref not in memo:
                    sub, rows = f.ref.split("/")
                    memo[f.ref] = {}
                    for key in self.vars.list(f"{sub}/{rows}/"):
                        try:
                            it, _ = self.vars.get(key)
                        except (Garbled, *PARSE_ERRORS):
                            continue
                        if isinstance(it, dict):
                            memo[f.ref][key.rsplit("/", 1)[1]] = it
                v = str(memo[f.ref].get(v, {}).get(second) or "")
            if v.lower() not in [x.lower() for x in vals]:
                return False
        return True

    # Whose unit of the followed subsystem this one wants to be beside: its own id by default, or the
    # string in the field `near.by` names. The row is read for the second form only — a subsystem whose
    # units share the other's naming pays nothing for the ones that do not.
    def near_id(self, uid) -> str:
        if self.spec.near_by == "id":
            return str(uid)
        row = self.unit(uid)
        return str(row.get(self.spec.near_by, "") or "") if row else ""

    # Where this unit belongs, for `ensure_home`. `home` is either the name of a field on the row — the
    # server an operator named — or the literal `near`, meaning "wherever the thing I follow is".
    #
    # The second form is what makes one subsystem come home BEHIND another. `near` alone is applied once,
    # when a unit is placed: a unit whose worker was moved while a server was down keeps being held
    # there for ever, because reading its fan-out over the network works and nothing is broken.
    #
    # Exactly one of a following pair may say `home: near`, and that is not a detail. Two subsystems that
    # each follow the other have no anchor: every pass moves each towards where the other was, and they
    # swap places instead of meeting. The anchor is the one with a real home — the one that writes to a
    # disk, because a disk does not move.
    def home_for(self, row: dict, near: NearIndex | None = None) -> str:
        if self.spec.home == "near":
            near = self.holder_near(row["id"], near) if self.spec.near != "none" else None
            return near[1] if near and near[1] != "?" else ""
        return str(row.get(self.spec.home, "") or "") if self.spec.home else ""

    # The same, addressed by id — what `_pick` needs before a unit is placed anywhere.
    def home_of(self, uid) -> str:
        if not self.spec.home or self.spec.home == "near":
            return ""                                     # the `near` form is resolved by `_pick`, which has the holder
        row = self.unit(uid)
        return str(row.get(self.spec.home, "") or "") if row else ""

    # The pick, with the two affinities in order — home first, then `near` — over a pool the FILTERS have
    # already cut (`eligible`: the constraint and `spread_by`). `(worker, free, note)`, and the note says
    # which it was: "at home on srv-a", "beside w-1 holding it", "away from home srv-a" — so the reason
    # tells the operator both where the unit reads its source from and whether it is where it belongs.
    #
    # Home before near, because they disagree exactly when a server is down: `near` would pin a follower to
    # whichever server picked up the unit it follows, and nothing would ever come back.
    def _pick(self, pool: list[str], uid, near: NearIndex | None = None) -> tuple[str | None, int, str]:
        near = self.holder_near(uid, near)
        home = near[1] if self.spec.home == "near" and near else self.home_of(uid)
        follows = self.spec.home == "near"
        if home:
            best, free = self._best([w for w in pool if self.place_of(w) == home])
            if best is not None:
                return best, free, (f", beside {near[0]} holding it" if follows else f", at home on {home}")
        if near is not None and not follows:
            beside = [w for w in pool if self.server_of(w) == near[1]]
            best, free = self._best(beside)
            if best is not None:
                return best, free, f", beside {near[0]} holding it" + (f" (home {home} has no room)" if home else "")
        best, free = self._best(pool)
        note = ""
        if best is not None and near is not None and self.server_of(best) != near[1]:
            note = f", away from {near[0]} on {near[1]} (no room there)"
        if best is not None and home and not follows and self.place_of(best) != home:
            note += f"; away from home {home}"
        return best, free, note

    # Of `pool`, the workers with room for `n` units — a group placed or moved whole — or `pool` as it was when none has
    # it: what fits is placed, as before, rather than nothing. One worker in `pool` (the group pinned already) is the pool.
    def _room_for_group(self, pool: list[str], n: int) -> list[str]:
        if n <= 1 or len(pool) <= 1:
            return pool
        return [w for w in pool if self.capacity_of(w) - self.load(w) >= n] or pool

    # How many units of `row`'s group — `row` with them — have no place yet: what its first placement must make room for.
    def _group_waiting(self, row: dict) -> int:
        return len(self._group_rows_waiting(row))

    # …and those rows, `row` among them.
    def _group_rows_waiting(self, row: dict) -> list[dict]:
        value = self.group_value(row) if self.spec.group_by else ""
        if not value:
            return [row]
        out = [o for o in self._rows_by("group", self.group_value).get(value, ())
               if not self.retired(o) and str(o["id"]) != str(row["id"]) and self.placement(o["id"]) is None]
        return [row] + out

    # `most-free-capacity`: the worker with the largest `capacity_of − load`, strictly positive; ties go to
    # the first in sorted order.
    def _best(self, pool: list[str]) -> tuple[str | None, int]:
        best, free = None, 0
        for w in pool:                                        # most-free-capacity: the one tie-break in the catalogue
            f = self.capacity_of(w) - self.load(w)
            if f > free:
                best, free = w, f
        return best, free

    # Place one unit. An existing placement is returned untouched — adding a worker moves nothing. A missing
    # unit is `None`. Otherwise pick `_best` among the eligible pool; `None` if nothing has free capacity
    # ("the system is full" — or nothing that can reach it; never "w-1 is full"). The reason names the free
    # capacity, the pool size, the labels reached (under `labels-subset`) and the server. Then the row first
    # (CAS decides who won: if another instance placed it meanwhile, the mutator returns `None` and the
    # other's row is used), then `assign_add` on the winner's worker. `test_two_controllers_agree_by_cas`:
    # two threads placing 40 units with opposite preferences end with every unit exactly once across
    # `w-1`/`w-2`.
    def place(self, uid, workers: list[str] | None = None) -> Placement | None:
        """Place ONE unit on the worker with the most free capacity among those
        seen heartbeating (or given) that satisfy the constraint. An existing
        placement is returned untouched: adding a worker moves nothing."""
        have = self.placement(uid)
        if have:
            return have
        row = self.unit(uid)
        if row is None or self.retired(row):
            return None                                 # finished work is not placed, and not "unplaceable" either
        pool = self.eligible(row, self._pool(workers))
        # The FIRST unit of a group placed decides where the group goes (`eligible` pins the rest to it): onto a worker
        # with room for every unit of the group waiting to be placed, when one has it (the product's cross-check of the
        # eleventh review — two channels of four fitted on the near worker, and the other two were unplaceable for good).
        if len(pool) > 1:                               # pinned to its group's worker already: nothing to choose
            # …and onto a worker EVERY waiting unit of the group may go to (the review's twelfth pass, major 6): the
            # first channel's own labels chose the worker, the others were pinned to it, and a channel that needs a label
            # that worker lacks was never placed. Where no worker takes them all, the first goes where it may, as before.
            waiting = self._group_rows_waiting(row)
            if len(waiting) > 1:
                pool = [w for w in pool if all(w in self.eligible(m, pool) for m in waiting if m is not row)] or pool
            pool = self._room_for_group(pool, len(waiting))
        best, free, near = self._pick(pool, uid, self.near_index())      # the pass's one look (`near_index`), not one per unit
        if best is None:
            return None                                 # "the system is full" — or nothing that can reach it; never "w-1 is full"
        reason = f"most free capacity ({free}) among {len(pool)} worker(s)"
        if self.spec.constraint == "labels-subset" and row.get("labels"):
            reason += f" reaching {','.join(sorted(row['labels']))}"
        reason += f"; on {self.server_of(best)}"
        if self.spec.requires == "resource":
            reason += f", whose resource is {self.resource_state(self.server_of(best))}"
        reason += near
        pl = Placement(self.spec.parse_id(uid), best, reason, self.wall(), 0)
        # the row first (CAS decides who won), then the assignment
        def mutate(it):
            if it and it.get("worker"):
                return None                             # the other instance placed it while we thought
            return {"worker": pl.worker, "reason": pl.reason, "at": pl.at, "rev": _next_rev(it)}
        written = self.write(self.sub.config("placement", str(uid)), mutate)
        pl = self._placement(uid, written)             # ours, or the other instance's — which may be the garbled one
        self.assign_add(pl.worker, str(uid))
        return pl

    # The pass: `unplace_deleted`, then `place` every unit; returns what is placed.
    # `test_placement_is_stored_with_a_reason_and_adding_a_worker_moves_nothing`: six units split 3/3 by
    # capacity 3; the seventh waits; a third worker arriving takes only the seventh.
    # THE PASS, as one call that measures itself and says so where anybody can read it (feedback BG). The
    # controller has no port, and its pass used to be three calls in a loop in `__main__`: a pass that raised
    # every time, a unit with nowhere to go, an assignment the rows contradicted — none of it was a number
    # anywhere. `snapshot_age` stayed fresh while the units were served by nobody. The report goes to the object
    # store (`<sub>/controller/pass`), like a heartbeat, and the console exports it:
    #
    #   ts, last_success   when the pass last ran, and when it last ran WITHOUT raising. Both: a pass that does
    #                      not run is a controller that stopped; one that runs and never succeeds is a controller
    #                      that is up and failing — and a fresh snapshot hid exactly that
    #   seconds, failures  how long it took; how many passes have raised since the store was new
    #   unplaced           units that should be somewhere and are nowhere
    #   diverged           assignments this pass had to bring back to what the placement rows say
    #   garbled            rows that do not parse — units nobody serves until somebody mends the row
    #   reach_moves        units moved, or unplaced, because their server no longer reaches them (`ensure_reach`)
    #   slots_released     slots the controller released this pass — a worker its server's resource lists nowhere
    #                      (`release_unlisted`), every slot of a server decommissioned (`apply_decommissions`) — and
    #                      `slots_released_total` since the store was new; `servers_decommissioned` and its `_total` the
    #                      decommissions carried out; `decommission_requests_standing` those whose server still
    #                      answers; `workers_hung` workers whose process runs on a server that answers and that neither
    #                      renew nor speak (`slot_fate`) — the product's names; `name_conflicts` the names a live instance
    #                      holds and another process asks for (`say_name_conflicts`)
    #   units_short, workers_needed, spare_offers, spares_starting
    #                      per label set, where the spec says `offers` (`offer_spares`): what nothing live has room
    #                      for, the workers that makes, the offers standing for them, the offers a spare took whose
    #                      worker is not heard yet
    #
    # The steps each in a `try` of their own (the review's second pass, M7): they shared one, so a
    # `redistribute` that raised on one released slot kept `ensure_home` from ever running, every pass. Four since
    # `ensure_reach` (feedback DQ), in the product's order: placed, reach, redistribute, home. And before them the
    # decommissions (`apply_decommissions`) and the slots nobody runs any more (`release_unlisted`), so `redistribute`
    # moves what they list in the same pass.
    PASS_KEY = CONTROLLER_PASS                        # granted by `acl_objects_controller` (the review's ninth pass)

    # …and each key read ONCE in it (`contract.one_pass`; the scaling pass after the eighth review): its three steps and
    # the report re-read the rows, the placements and the heartbeats per step and per unit — some 41 000 reads at a
    # thousand units on twenty workers, 2 000-odd now (`tests/test_read_budget.py`). The loop that also publishes the
    # snapshot opens the pass around both (`host.placement_pass`), and the snapshot reads nothing again.
    def pass_once(self, home_budget: int = 1) -> dict:
        with one_pass(self):
            return self._pass_once(home_budget)

    def _pass_once(self, home_budget: int) -> dict:
        import json
        started, now = time.monotonic(), self.wall()
        prev = self.pass_report() or {}
        try:
            failures = int(prev.get("failures", 0))
        except PARSE_ERRORS:                          # `1e400` too: `int(inf)` raised out of the pass, every pass (the ninth review's sweep)
            failures = 0                              # a count that is a word: counted from here
        rep = {"ts": now, "ok": True, "error": "", "failures": failures,
               "last_success": prev.get("last_success")}
        self.last_diverged = 0
        errors = []
        self.last_reach_moves = 0
        decom = {"decommissioned": [], "released": [], "standing": {}}
        slots = {"released": {}, "hung": {}, "hung_moved": [], "unjudged": {}, "units_unjudged": 0, "unsure_moved": []}
        # What it judges by, looked at before anything is judged: its eyes see this pass's changes (`Controller.look`) —
        # and its verdict on the names, as of that look (`names_given`, `fates_said`): what this pass then writes (the
        # offers, a release) is not read back for it, and a row it changes is a revision no verdict is for
        judged = {"names_given": {}, "fates": {}, "clock_skew": {}}
        try:
            self.look()
            judged = {"names_given": self.names_given(), "fates": self.fates_said(), "clock_skew": self.say_skews()}
        except Exception:                             # noqa: BLE001 — what could not be read is judged where it is asked
            log.warning("%s: the look at heartbeats, slots and resources did not run through", self.sub.name, exc_info=True)

        # The operator's decommissions and the slots nobody runs any more FIRST (`Controller.apply_decommissions`,
        # `release_unlisted`): a slot they release is then read by `redistribute` below, which moves what it listed in
        # this same pass.
        def apply_decommissions():
            decom.update(self.apply_decommissions())

        def release_unlisted():
            slots.update(self.release_unlisted())
        spares = {}

        def offer_spares():                           # the numbers and the offers LAST: after every move this pass made
            if self.spec.offers:
                spares.update(self.offer_spares())
        names = {"name_conflicts": 0}

        def name_conflicts():                         # two processes that want one name, said (`say_name_conflicts`)
            names["name_conflicts"] = self.say_name_conflicts()
        for step, run in (("apply_decommissions", apply_decommissions),           # a server gone for good, once it is silent
                          ("release_unlisted", release_unlisted),                 # a slot its server's resource lists nowhere
                          ("ensure_placed", self.ensure_placed),                   # deleted rows unplaced; new units onto the workers it sees
                          ("ensure_reach", self.ensure_reach),                     # a unit its server no longer reaches: moved, or unplaced with why
                          ("redistribute", self.redistribute),                     # units of a RELEASED slot (scale-in) onto the rest
                          ("ensure_home", lambda: self.ensure_home(home_budget)),  # a unit back to the server its row names, if it is back
                          ("offer_spares", offer_spares),                          # what nothing live has room for: numbers, and offers to spares
                          ("name_conflicts", name_conflicts)):                     # a name two processes want: said once an episode
            try:
                run()
            except Exception as e:                    # noqa: BLE001
                errors.append(f"{step}: {e}")
                self._failed(step, f"placement pass failed at {step}")
            else:
                self._works(step)
        if errors:
            rep.update(ok=False, error="; ".join(errors), failures=rep["failures"] + 1)
        else:
            rep["last_success"] = now
        rep["seconds"] = round(time.monotonic() - started, 3)
        rep["diverged"] = self.last_diverged
        rep["reach_moves"] = self.last_reach_moves     # units moved or unplaced because their server no longer reaches them
        # …and since the store was new, a counter (the review's tenth pass, minor): the gauge of the last pass showed a
        # third of the moves to a scrape every 15 s
        from .rows import number
        total = lambda field, n: number(f"{self.sub.name}/{self.PASS_KEY}#{field}", prev.get(field, 0), int, 0) + n
        rep["reach_moves_total"] = total("reach_moves_total", self.last_reach_moves)
        released = sorted({*slots["released"], *decom["released"]})
        rep["slots_released"] = released                            # released this pass: unlisted, or on a decommissioned server
        rep["slots_released_total"] = total("slots_released_total", len(released))
        rep["servers_decommissioned"] = decom["decommissioned"]     # decommissions carried out this pass
        rep["servers_decommissioned_total"] = total("servers_decommissioned_total", len(decom["decommissioned"]))
        rep["decommission_requests_standing"] = len(decom["standing"])   # asked, and the server still answers
        rep["workers_hung"] = sorted(slots["hung"])                 # its process runs, and it neither renews nor speaks
        # …and the hung workers whose units moved anyway, past the limit — counted since the store was new (the review's
        # twelfth pass, minor: an alarm in the journal, and no number)
        rep["workers_hung_moved_total"] = total("workers_hung_moved_total", len(slots["hung_moved"]))
        # …and the unsure ones moved past the same limit (the owner's middle way, applied to the doubt)
        rep["workers_unsure_moved_total"] = total("workers_unsure_moved_total", len(slots["unsure_moved"]))
        rep["hung_move_after"] = self.hung_move_after                # …and how long it keeps its units: a spare judges by it
        # …and the names another process may take now, by the revision judged (`Controller.names_given`; the review's
        # thirteenth pass, blockers 2–4): a process looking for a name takes only these — the controller's eyes, not its
        # own — and its verdict on each slot that stopped renewing, for `/servers` (`fates`). None, when the slots did
        # not read: no name is given this pass.
        rep.update(judged)
        # Slots nobody can judge (`slot_fate` `wait`/`unsure`) with units on them, and how many units wait so (the review's
        # twelfth pass, blocker 5) — and the live workers that could not write their name beside their lock (blocker 3)
        rep["workers_unjudged"] = sorted(slots["unjudged"])
        rep["units_unjudged"] = slots["units_unjudged"]
        try:
            rep["workers_presence_unsaid"] = sorted(w for w, hb in self.workers_seen(SLOT_LOST_AFTER).items()
                                                    if hb.extra.get("presence_unsaid"))
        except Exception:                             # noqa: BLE001 — the heartbeats unread: the other numbers stand
            rep["workers_presence_unsaid"] = []
        # Names a live instance holds and another process asks for — of another box, or left nobody on its own (the
        # owner's decision of 4 Oct; the product's name): `<name>_name_conflicts` on the console's `/metrics`
        rep["name_conflicts"] = names["name_conflicts"]
        # The units of groups `ensure_reach` left whole where they are, and the servers whose row did not read on the last
        # read — each was a line in the log or on a page only, for days (the eleventh review, a major and a minor)
        rep["reach_waiting"] = self.last_reach_waiting
        rep["reach_budget"] = self.reach_budget
        # Units `redistribute` could not move off a worker that is leaving — a group no worker takes whole, a unit nothing
        # has room or reach for (the review's twelfth pass, blocker 7: every counter said 0)
        rep["units_left_on_leaving"] = self.last_leaving_waiting
        rep["servers_labels_unread"] = self.labels_unread_count()      # -1: the rows never read since this process started
        # The spares' numbers, per label set (`offer_spares`; the product's names): what the console publishes as
        # `<name>_workers_needed`, `_units_short`, `_spare_offers` while this report is fresh
        rep.update(spares)
        try:
            unplaced = self.unplaced()
            rep["unplaced"] = len(unplaced)
            self.delete_long_unplaced(unplaced)
            rep["unplaced_deleted_total"] = self.unplaced_deleted
            rep["garbled"] = self.rows_garbled
            for name, counts in (("slots_garbled", SLOTS_GARBLED), ("assignments_garbled", ASSIGNMENTS_GARBLED)):
                if counts.get(self.sub.name):         # rows of the contract this process could not read (`contract.py`):
                    rep[name] = counts[self.sub.name] # said when there are any, as a worker's heartbeat says them
            self.objects.put(f"{self.sub.name}/{self.PASS_KEY}", json.dumps(rep).encode())
        except Exception:                             # noqa: BLE001 — a report that cannot be written is an old report, which says so
            self._failed("report", "the pass could not report on itself")
        else:
            self._works("report")
        return rep

    # A STEP THAT FAILS EVERY PASS IS SAID ONCE (the eighth review's minor, closed in the ninth): `log.exception` on every
    # pass put the same trace in the log every five seconds — a policy that refused the report did it for days — and
    # buried the first one, the one that says why. The trace once per spell, as `domain/steps.py` has it for М12's
    # loops; "works again" when the step succeeds; the count of failed passes is the report's `failures`.
    def _failed(self, step: str, what: str) -> None:
        if step not in self._pass_failing:
            self._pass_failing.add(step)
            log.exception("%s: %s; tried again on every pass, said again when it works", self.sub.name, what)

    def _works(self, step: str) -> None:
        if step in self._pass_failing:
            self._pass_failing.discard(step)
            log.warning("%s: %s works again", self.sub.name, step)

    # The last pass's report, or None — and None for one that does not parse (the sixth pass, the follow-up):
    # `pass_once` reads it first, and "it does not raise" is what the loop calling it relies on. Half a write under
    # this key raised out of the pass and out of the loop, the process ended, started, and ended again on the same
    # object — which only a pass that finishes writes over.
    def pass_report(self) -> dict | None:
        import json
        raw = self.objects.get(f"{self.sub.name}/{self.PASS_KEY}")
        if not raw:
            return None
        try:
            rep = json.loads(raw)
        except PARSE_ERRORS:
            log.warning("%s: the last pass's report does not parse; this pass writes it again", self.sub.name)
            return None
        return rep if isinstance(rep, dict) else None

    def unplaced(self) -> list:
        """Units that should be somewhere and are nowhere — whatever the reason; `/unplaceable` says which cannot be."""
        return [r["id"] for r in self.units() if not self.retired(r) and self.placement(r["id"]) is None]

    # A UNIT NOBODY HOLDS FOR `placement.unplaced.delete_after` GOES (ADR-0067; the product's `deleteLongUnplaced`): counted
    # by this controller's own clock (`judge_clock`: monotonic; ADR-0049) from the first pass of an unbroken run that found it with
    # no holder — not from the row's `rev` — its row removed by CAS on the index read, as a console's DELETE leaves it,
    # and `unplace_deleted` does the rest; a line `unit.unplaced_deleted {target, after_s}`. A unit placed again starts
    # its count again; a controller started again starts every count again: later, never sooner. A row changed
    # meanwhile, placed or gone, is the next pass's. Without the key nothing is deleted. It was a worker's sweep in the
    # product (`sweepUnplaced`): where no worker of the subsystem runs, the row and its alarm stood for ever.
    def delete_long_unplaced(self, unplaced: list) -> list:
        after = self.spec.unplaced_delete_after
        if after <= 0:
            return []
        from .contract import judge_clock
        now = judge_clock(self.wall)()                # monotonic — or a test's own wall
        since, still, gone = getattr(self, "_unplaced_since", {}), {}, []
        for uid in unplaced:
            first = since.get(uid, now)
            if now - first < after or not self._delete_unplaced(uid, after):
                still[uid] = first
            else:
                gone.append(uid)
        self._unplaced_since = still
        return gone

    @property
    def unplaced_deleted(self) -> int:
        return getattr(self, "_unplaced_deleted", 0)

    def _delete_unplaced(self, uid, after: int) -> bool:
        path = self.row_key(uid)
        try:
            row, index = self.vars.get(path)
            if not row or row.get("deleted") == "true" or self.placement(uid) is not None:
                return False
            self.vars.delete(path, cas=index)
        except Exception as e:                        # noqa: BLE001 — a conflict, a refusal, a silent store: the next pass
            log.info("unplaced: %s %s, unheld for %d s, was not deleted: %s", self.sub.name, uid, after, e)
            return False
        self._unplaced_deleted = self.unplaced_deleted + 1
        log.info("unplaced: %s %s deleted — nobody held it for %d s (placement.unplaced.delete_after)", self.sub.name,
                 uid, after)
        self.journal.say("unit.unplaced_deleted", sub=self.sub.name, target=str(uid), after_s=after)
        return True

    def ensure_placed(self, workers: list[str] | None = None) -> list[Placement]:
        self.unplace_deleted()
        self.unplace_retired()
        self.last_diverged = len(self.sync_assignments())
        out = []
        for r in self.units():
            # One unit that cannot be placed — a row that does not parse after a field changed its type, a
            # store that refused one write — is one unit waiting, not a pass that stops at it and places
            # nothing after it, every pass (feedback BC).
            try:
                pl = self.place(r["id"], workers)
            except Exception:                           # noqa: BLE001
                log.exception("%s: unit %s not placed this pass", self.sub.name, r.get("id"))
                continue
            if pl:
                out.append(pl)
        return out

    # The placement rows are the DECISION; the assignments carry it out. They are two writes, and a pass can
    # stop between them: a controller killed after the row and before `assign_add` left a unit whose row
    # named a worker that never heard of it — not placed again ("an existing placement is returned
    # untouched"), not in `/unplaceable`, running nowhere, for ever (the platform review; the product lost
    # a unit the same way to ten CAS conflicts in a row, feedback BC). So every pass starts by making the
    # assignments say what the rows say: the unit is added to the worker its row names and taken from any
    # other that lists it. A unit with no placement row is not touched — placing it is `place`'s job.
    def sync_assignments(self) -> list[tuple]:
        fixed = []
        assignments = self.assignments()
        for p in self.vars.list(self.sub.config("placement") + "/"):
            unit = p.rsplit("/", 1)[1]
            it = self._placement_items(p)
            if not it or not it.get("worker"):
                continue
            want = it["worker"]
            for w, a in assignments.items():
                if w != want and unit in a.units:
                    self.assign_remove(w, unit)
                    fixed.append((unit, w, None))
            if unit not in (assignments[want].units if want in assignments else ()):
                self.assign_add(want, unit)
                fixed.append((unit, None, want))
        return fixed

    # Units with no placement that no live worker's labels can serve — the console's honest answer, with the
    # labels named and the live worker count.
    def unplaceable(self) -> list[dict]:
        """Units nothing live can serve — the console's honest answer, with the labels named."""
        with one_pass(self):                          # `eligible` per unit asked the heartbeats per worker, again per unit
            return self._unplaceable()

    def _unplaceable(self) -> list[dict]:
        live = self._pool(None)
        out = []
        for r in self.units():
            if self.placement(r["id"]) is None and not self.retired(r) and not self._eligible_or_none(r, live, "unplaceable"):
                u = {"id": r["id"], "labels": r.get("labels", []), "workers_live": len(live)}
                why = self.unplaced_reason(r["id"])
                beside = self.row_key(r["id"]) + "#unplaceable" not in UNIT_JUDGED.bad and self.worker_with_group(r, live)
                if why and why != "deleted":           # what took its place away — a server that stopped reaching it
                    u["why"] = why
                elif beside:                           # its group is held where it may not go (`eligible`)
                    u["why"] = f"its {self.spec.group_by} is held on {beside}, which does not take it: one {self.spec.group_by}, one worker"
                elif self.row_key(r["id"]) + "#unplaceable" in UNIT_JUDGED.bad:
                    u["why"] = "its row could not be checked against any server: see the log"
                out.append(u)
        return out

    # The placed worker.
    def where(self, uid) -> str | None:
        pl = self.placement(uid)
        return pl.worker if pl else None

    # The one two-writer operation: remove the unit from every assignment that lists it other than `to`
    # (wherever it is listed, not only where the row says), rewrite the placement row, `assign_add` on `to`.
    # The destination takes the next epoch when it starts; the source's lease fences on renewal and it
    # stops. Called by an operator's hand (no door of the console calls it), or by the controller's own steps through
    # `move_from` — a released slot's units (`redistribute`), a unit back home (`ensure_home`), one its server no
    # longer reaches (`ensure_reach`) — each with its reason in the row; never by a rebalance nobody asked for (the
    # review's tenth pass: "never automatic" was untrue since those steps).
    #
    # The order is the row, then the removals, then the addition (feedback BC): the row is the decision, and
    # `sync_assignments` finishes a move a crash cut short — from either side of it. `expect`: the worker the
    # caller saw the unit on. The OPERATOR's move has none — "from wherever it is". A move the CONTROLLER decided
    # names it (`move_from`), and the same CAS that writes the row checks the row still says so: two
    # controllers, overlapping for the seconds of a deploy, each moved the unit where it thought best, and the
    # unit ended in two assignments — which a worker reads as "I am a zombie".
    def move(self, uid, to: str, reason: str, expect: str | None = None) -> Placement:
        """The one two-writer operation: the destination takes the next epoch when
        it starts; the source's lease fences on renewal and it stops. The operator's,
        or a controller step's through `move_from`, with the reason in the row."""
        def mutate(it):
            if expect is not None and (it or {}).get("worker") != expect:
                raise Moved(f"{uid} is on {(it or {}).get('worker') or 'nobody'}, not on {expect}: somebody moved it first")
            return {"worker": to, "reason": reason, "at": self.wall(), "rev": _next_rev(it)}
        new = self.write(self.sub.config("placement", str(uid)), mutate)
        for w, a in self.assignments().items():                     # wherever it is listed, and not only where the row says
            if str(uid) in a.units and w != to:
                self.assign_remove(w, str(uid))
        self.assign_add(to, str(uid))
        return Placement(self.spec.parse_id(uid), to, reason, float(new["at"]), int(new["rev"]))

    def move_from(self, uid, frm: str, to: str, reason: str) -> Placement | None:
        """The controller's own move: only if the row still names `frm`. None if somebody moved it first."""
        try:
            return self.move(uid, to, reason, expect=frm)
        except Moved as e:
            log.info("%s: %s", self.sub.name, e)
            return None

    # The controller's one unasked move: the units of every worker that is LEAVING (`leaving`) go to the live workers
    # with the most free capacity, a channel group whole; what has no room waits, listed where it was, counted. Leaving
    # is: a released slot (an orderly stop, or released by the controller — `release_unlisted`, a decommission), a live
    # worker whose server's resource is silent where the spec requires one, one that holds no place where places are
    # held, one whose place admits no unit (`admitting_none`), one on a drained or decommissioned server, and a slot that stopped renewing whose fate says its units move
    # (`slot_fate`: `MOVED_FATES`). A slot that merely lapsed, or whose worker is hung, or that nobody can judge, is not
    # touched — it is waited for, up to `hung_move_after` for the last two. `test_scale_in_releases_a_slot_and_the_controller_redistributes`: a silent `w-3`
    # moves nothing; after `release_slot()` its two units go to `w-1`/`w-2` with reason `slot w-3 released; …`.
    def redistribute(self, workers: list[str] | None = None) -> list[tuple]:
        """The controller's one unasked move: the units of a worker that is leaving
        (`leaving`: a released slot, a drained, decommissioned or silent server, no
        place or one that admits no unit, a dead slot by `slot_fate`) go to the workers that are here — a channel group
        whole, or not at all. A slot that merely lapsed is not touched: its
        process returns under the same name."""
        self.unplace_deleted()
        moves = []
        seen = sorted(workers if workers is not None else self.workers_seen())
        gone_for = self.leaving(seen)
        idx = None                                    # one look at what is followed, taken when a unit is moved
        self.last_leaving_waiting, waits = 0, set()
        for gone, why in gone_for.items():
            live = [w for w in self._pool(workers) if w != gone]
            done: set[str] = set()
            for unit in sorted(self.assignment(gone).units, key=_unit_key):
                if unit in done:
                    continue
                try:
                    uid = self.spec.parse_id(unit)
                except PARSE_ERRORS as e:
                    # A name in the row that is no unit's id (`read_assignment` reads the list as it stands): that name's
                    # trouble, counted — it raised out of the whole step, and no unit of any leaving slot moved (the
                    # review's seventh pass, the walk over every row read).
                    ASSIGNMENTS.garbled(f"{self.sub.assignment(gone)}#{unit}", e)
                    continue
                row = self.parsed_unit(uid)
                if row is GARBLED_ROW:
                    self.last_leaving_waiting += 1
                    continue                            # its filters cannot be read: it waits where it is, the others move
                # THE GROUP GOES WHOLE, OR STAYS WHOLE (the review's twelfth pass, blocker 7; `ensure_reach`'s rule). The
                # first unit of a group went where IT fitted, the next ones were pinned to that worker
                # (`eligible`) — and with no room or no reach for them there they stayed on the leaving worker: a drained,
                # released, decommissioned or dead slot, a group split, and the channels left behind written by
                # nobody, every counter at 0. Now the units of the group on the leaving worker go together onto a worker
                # that every one of them may go to AND that has room for all of them — or none goes, said once and
                # counted (`units_left_on_leaving` in the pass report, on `/metrics`).
                group = self._reach_group(row, gone) if row else []
                done |= {str(m["id"]) for m in group}
                if len(group) > 1:
                    fits = None
                    for m in group:
                        e = set(self.eligible(m, live))
                        fits = e if fits is None else fits & e
                    pool = [w for w in live if w in fits and self.capacity_of(w) - self.load(w) >= len(group)]
                else:
                    pool = self.eligible(row, live) if row else live
                idx = self.near_index() if idx is None else idx
                best, free, near = self._pick(pool, uid, idx)
                if best is None:
                    # THIS unit (or group) waits, listed where it was — and the next one is looked at: each has filters
                    # of its own, and a `break` here let one unit with a rare label, first in the list, hold every
                    # other unit of a dead worker for ever (the platform review; feedback BC).
                    self.last_leaving_waiting += max(1, len(group))
                    key = (str(uid), gone)
                    waits.add(key)
                    if key not in self._leaving_said:
                        self._leaving_said.add(key)
                        what = (f"{uid} and {len(group) - 1} more of one {self.spec.group_by}" if len(group) > 1 else
                                f"{uid}")
                        log.warning("%s: %s stay on %s (%s): no live worker takes %s — moved when one does, asked again "
                                    "every pass", self.sub.name, what, gone, why, "all of them" if len(group) > 1 else "it")
                        # …and an alarm, once a spell (the review's thirteenth pass, major 16): written by nobody until
                        # a worker with the room comes — the spares' count asks for one (`offer_spares`)
                        from .events import ALARM
                        self.journal.say("units.left_on_leaving", ALARM, sub=self.sub.name, unit=str(uid),
                                         units=max(1, len(group)), worker=gone,
                                         why=(f"{what} stay on {gone} ({why}): no live worker has the reach and the room "
                                              f"for {'all of them' if len(group) > 1 else 'it'} — written by nobody "
                                              f"until one does"))
                    continue
                for m in group or [row]:
                    mid = m["id"] if m else uid
                    reason = (f"{why}; most free capacity ({free}); on {self.server_of(best)}{near}" if mid == uid else
                              f"with {uid}, one {self.spec.group_by}: {why}; on {self.server_of(best)}")
                    if not self.move_from(mid, gone, best, reason):
                        break                           # somebody moved it first: the rest of the group, next pass
                    moves.append((mid, gone, best))
        self._leaving_said &= waits
        return moves

    # The workers whose units must go, and why — `redistribute` moves them, `offer_spares` counts what is left on them
    # as short: `{worker: why}`, `seen` the workers seen heartbeating.
    def leaving(self, seen: list[str]) -> dict[str, str]:
        # a released slot — and, when the spec requires a resource, a live worker whose server's resource
        # went silent: it heartbeats, but it has nowhere to write; its units go to workers that do
        gone_for = {g: f"slot {g} released" for g in self.released_slots()}
        for w in self.without_resource(seen):
            if self.assignment(w).units:
                gone_for.setdefault(w, f"resource on {self.server_of(w)} silent")
        # …and a live worker that holds NO PLACE where the subsystem places by one (feedback BN): a worker
        # that lost its disk — two restarted, the other took it — is alive, keeps its slot and cannot write
        # a byte, and the units assigned to it used to stay there, written by nobody, for as long as it
        # lived. It says so itself (`place` empty in its heartbeat); its units go to a worker that has a place.
        for w in self.placeless(seen):
            if self.assignment(w).units:
                gone_for.setdefault(w, f"{w} holds no {self.spec.place_by} now")
        # …and one whose place now admits no unit (`admits: false` in its `affinity` row; ADR 0056): it keeps no new
        # unit out only — the ones it has go too, or they stay for ever where the administrator closed the place
        for w, place in self.admitting_none(seen).items():
            if self.assignment(w).units:
                gone_for.setdefault(w, f"{w}'s {self.spec.place_by} {place} admits no unit")
        for w in self.on_draining(seen):                               # an operator said this machine is about to stop
            if self.assignment(w).units:
                gone_for.setdefault(w, f"server {self.server_of(w)} draining")
        for w in self.on_decommissioned(seen):                         # …or that it is gone for good, and something on it speaks
            if self.assignment(w).units:
                gone_for.setdefault(w, f"server {self.server_of(w)} decommissioned")
        for w, (fate, server, why) in self.fates().items():           # a slot that stopped renewing, and its units move (`slot_fate`)
            if fate in MOVED_FATES and self.assignment(w).units:
                gone_for.setdefault(w, why)
        return gone_for

    # -- spares: the numbers, and the offers (the М11 rework; the product's c62e236) ------------------------------------
    # THE CONTROLLER NEVER STARTS A PROCESS. Under an orchestrator the scheduler brought a dead server's worker back on a
    # neighbour; without one the host does it — `w2c-spares.sh`, run by root from a timer the operator installed on
    # purpose — and the controller publishes what is missing, and where. Last in the pass (`_pass_once`): after the
    # decommissions, the moves off dead slots and `redistribute` have put every unit they could on the room there is,
    # so a server's death raises no spare while the living have room.
    #
    #   waiting       per label set (a unit's `labels` under `labels-subset`; "" for every unit otherwise): units with no
    #                 placement, and units still on a worker that is leaving (`leaving`: a released slot, a silent
    #                 resource, a drained or decommissioned server, a dead slot whose fate is `move`). Not a hung
    #                 worker's, not a slot's before its fate says move — those are waited for, not short. In PIECES:
    #                 a unit alone is a piece of one; the waiting units of one `group_by` together are one piece, under
    #                 the labels of all of them (the review's thirteenth pass, major 16)
    #   free          the room (`capacity − load`) of each worker in the pool whose labels cover the set
    #   units_short   what of the waiting does not fit that room, a piece whole onto one worker or not at all (`_pack`).
    #                 A set no live worker covers has no free room: short by itself
    #   needed        the workers of `per` places it takes to carry the short pieces whole (`_bins`), at most the
    #                 servers a spare of the set could carry units on, less the offers of the set a spare took and whose
    #                 worker has not been heard yet — for `OFFER_GRACE` (90 s) from the take, as this controller saw it,
    #                 it is a worker on its way. A piece larger than `per` no spare takes: withheld, the reason said
    #
    # …AND ONLY WHAT A SPARE COULD TAKE (the twelfth round's «Вопросы», found rebuilding a scenario by runs). Three
    # things the count did not ask:
    #   per           a spare says its capacity in its first heartbeat, after it was started for the count. The count
    #                 is by the smallest capacity the live workers of the set announce (a spare is started from the
    #                 same unit and environment as the role's workers, so says the same), the spec's
    #                 `placement.capacity.default` only where none is live — never by that default while the workers
    #                 say better; the platform reads no `CAPACITY` (ADR-0030, п. 6: it is the workers' key)
    #   a server      a spare runs on a server: one whose resource is not silent, not drained, not decommissioned, and
    #                 whose labels cover the set (its row; else its workers' word; a server whose labels nobody has said yet
    #                 may cover it). Under `servers: distinct` only a server with no live worker of this subsystem
    #                 can carry a spare's units — on any other it idles by policy, the unit stays unplaced, and the
    #                 next pass offered again: spares raised to `MAX_WORKERS` on every server, each idle
    #   none          no such server: no offer is written — it could only hang, or start a spare that idles. The
    #                 shortage stays counted (`units_short`), the reason is said (`spares_withheld`, on `/metrics`),
    #                 and an alarm goes once an episode (`spares.no_server`)
    #
    # ONE OFFER PER WORKER NEEDED. A nameless process MAKES a slot, `w-(N+1)` — so "the extra spares find no slot and
    # wait" needs a slot only a spare may take: `<sub>/slots/<prefix>-<N>` `{holder:"", until:"0", released:"false",
    # gen:"0", offer:"<set>", offered_at:<ts>}`, created with `cas=0` under the next free number. An offer not needed
    # any more is deleted by CAS — one a spare took a moment ago is not the controller's to delete. A spare
    # (`SPARE_FOR=<set>`) takes only an offer of its set (`Worker._claim_offer`); an ordinary process never takes one
    # (`Slot.claimable`). Only where the spec says `offers: <prefix>`.
    def offer_spares(self) -> dict:
        """`{"units_short", "workers_needed", "spare_offers", "spares_starting"}`, each `{label set: n}` — the empty set
        always there."""
        now = self.wall()
        pool = self._pool(None)
        leaving = self.leaving(sorted(self.workers_seen()))
        subset = self.spec.constraint == "labels-subset"
        key = (lambda row: label_set(row.get("labels") or [])) if subset else (lambda row: "")
        # …BY GROUP (the review's thirteenth pass, major 16): units of one `group_by` waiting together — a box's
        # channels left whole on a leaving slot, a box's new channels — go onto ONE worker or not at all
        # (`redistribute`), and were counted one by one against the room of every worker: a 4-channel box on a released
        # slot beside two workers with 2 places each was "short 0", no offer, no alarm, four channels written by nobody.
        # A group is one piece now, under the labels of all its waiting units together, and it fits only where one
        # worker has room for all of it.
        waiting: dict[str, int] = {"": 0}
        pieces: dict[str, list[int]] = {}
        groups: dict[tuple, list[dict]] = {}
        # …AND WHAT A LIVE WORKER HOLDS AND NO LONGER REACHES (the product's r30, defect B): `ensure_reach` moves such a unit
        # — its group WHOLE — off a worker whose labels stopped covering it, and waits when nothing live can take it; the
        # count did not see it at all (the worker is live, not leaving): short 0, no offer, the units on a worker that
        # no longer reaches them. Each such unit is waiting here, and with it every unit of its group on that worker.
        off = self._off_reach(pool)
        for row in self.units():
            if self.retired(row):
                continue
            pl = self.placement(row["id"])
            short = pl is None or pl.worker in leaving or str(row["id"]) in off
            waiting.setdefault(key(row), 0)                            # every set a unit asks for, 0 too: a row a scrape sees fall
            if not short:
                continue
            value = self.group_value(row) if self.spec.group_by else ""
            if value:
                groups.setdefault((value, pl.worker if pl is not None else ""), []).append(row)
            else:
                pieces.setdefault(key(row), []).append(1)
        # …and a NEW group whose first channels went onto a worker without room for the rest (the product's r29-writers2,
        # decided the other way): the rest wait pinned to that worker (`eligible`) and the group moves only whole
        # (`ensure_reach`), so the piece is the group whole — what waits and what is placed beside it. Counted by what
        # waits alone, it "fitted" the room of a worker it may not go to: short 0, no offer, a channel written by nobody.
        # The product counts the remainder and splits the group; a group is one worker here (`group_by`).
        for (value, on), members in list(groups.items()):
            if on:
                continue
            placed = [o for o in self._rows_by("group", self.group_value).get(value, ()) if not self.retired(o)
                      and (p := self.placement(o["id"])) is not None and p.worker not in leaving]
            beside = {self.placement(o["id"]).worker for o in placed}
            if len(beside) == 1 and self.capacity_of(w := next(iter(beside))) - self.load(w) >= len(members):
                del groups[(value, on)]                 # its worker has the room: placed there on the next pass
            else:
                members += placed
        for members in groups.values():
            labels = label_set({str(l) for m in members for l in (m.get("labels") or [])}) if subset else ""
            pieces.setdefault(labels, []).append(len(members))
            waiting.setdefault(labels, 0)
        prefix = self.sub.name + "/slots/"
        names, offers, starting, heard = [], {}, {}, set(self.workers_seen())
        for path in self.vars.list(prefix):
            name = path[len(prefix):]
            names.append(name)
            items, idx = stored(self.vars, path, SLOTS)
            s = read_slot(path, name, items)
            if s is None or s.offer is None:
                continue
            if s.offered():
                offers.setdefault(label_set(s.offer), []).append((name, idx))
            elif s.holder and not s.released and name not in heard and \
                    self.eyes.age(f"{path}#taken", (s.holder, s.taken_at)) < OFFER_GRACE:
                # since THIS controller saw it taken, by its clock — `taken_at` is the spare's (the thirteenth pass)
                starting[label_set(s.offer)] = starting.get(label_set(s.offer), 0) + 1
        rule = CONSTRAINTS[self.spec.constraint]
        out = {"units_short": {}, "workers_needed": {}, "spare_offers": {}, "spares_starting": {}, "spares_withheld": {}}
        hosts, distinct = self._spare_hosts(), self.policy()["servers"] == "distinct"
        carrying = {self.server_of(w) for w in pool}         # under `distinct`, a server that has its one worker
        for labels in sorted(set(waiting) | set(offers) | set(starting)):
            asks = {"labels": [l for l in labels.split(",") if l]}
            covering = [w for w in pool if rule(asks, self.labels_of(w))]
            # what waits, packed into the room the covering workers have — a group whole or not at all — and what is left
            left = _pack(pieces.get(labels, []), [max(0, self.capacity_of(w) - self.load(w)) for w in covering])
            short = sum(left)
            caps = [self.capacity_of(w) for w in (covering or pool)]
            per = max(1, int(min(caps) if caps else self.capacity))
            reach = None if hosts is None else [h for h, has in hosts.items() if has is None or rule(asks, has)]
            room = None if reach is None else [h for h in reach if h not in carrying] if distinct else reach
            # …and a group a spare could not take whole is no reason to start one (the twelfth round's «Вопросы» for
            # capacity, the thirteenth pass's major 16 for groups): a spare says the capacity the role's workers say
            too_big = [n for n in left if n > per]
            spares = len(_bins([n for n in left if n <= per], per))
            want = spares
            fits = want if room is None or (room and not distinct) else len(room)   # spares that could carry units
            needed = max(0, min(want, fits) - starting.get(labels, 0))
            what = labels or "every unit"
            if want > fits:
                out["spares_withheld"][labels] = (
                    f"no server a spare could run on reaches {what}" if not reach else
                    f"servers: distinct, and {len(reach) - len(room)} of the {len(reach)} servers that reach {what} have "
                    f"their worker already: {len(room)} could carry a spare, {want} needed")
            elif too_big:
                out["spares_withheld"][labels] = (
                    f"{len(too_big)} group(s) of {max(too_big)} units of one {self.spec.group_by} reaching {what} need a "
                    f"worker with room for all of them, and a spare says {per}: raise the role's capacity, or give a "
                    f"worker that has the room the labels")
            have = sorted(offers.get(labels, []), key=lambda o: (slot_number(o[0]), o[0]))
            for name, idx in have[needed:][::-1]:            # the newest first; one a spare took meanwhile is its own
                try:
                    self.vars.delete(prefix + name, cas=idx)
                    have.remove((name, idx))
                except Conflict:
                    pass
            for _ in range(needed - len(have)):
                if self._offer(names, labels, now):
                    have.append(("", 0))
            out["units_short"][labels], out["workers_needed"][labels] = short, needed
            out["spare_offers"][labels], out["spares_starting"][labels] = len(have), starting.get(labels, 0)
        self._said_withheld(out["spares_withheld"])
        return out

    # The ids of the units placed on a live worker of `pool` that no longer passes the constraint — by the test
    # `ensure_reach` moves by: the server's row read, a label it lost that is a label — each with its group on that worker.
    def _off_reach(self, pool: list[str]) -> set[str]:
        if self.spec.constraint == "none" or self.server_labels() is None:
            return set()
        rule, live, unread, out = CONSTRAINTS[self.spec.constraint], set(pool), set(self._server_rows_unread), set()
        for row in self.units():
            pl = self.placement(row["id"])
            if pl is None or pl.worker not in live or self.retired(row) or str(row["id"]) in out:
                continue
            server = self.server_of(pl.worker)
            has = self.labels_of(pl.worker)
            if server in unread or rule(row, has) or self._why_off(row, server, has) is None:
                continue
            out |= {str(m["id"]) for m in self._reach_group(row, pl.worker)}
        return out

    # The servers a spare could run on, and what each reaches: `{server: labels}` — labels None where nobody has said
    # them yet (no row, no worker there ever). Not drained, not decommissioned, its resource not silent (one never heard
    # is a bench's, or a box before its resource starts; one whose door this process cannot reach is there: either may
    # carry one). No server known at all: a bench that says
    # nothing of its servers — every count as before (`offer_spares`).
    def _spare_hosts(self) -> dict[str, frozenset | None] | None:
        known = self.servers_known()
        if not known:
            return None
        node: dict[str, set] = {}
        for hb in self._per_pass(self.sub.heartbeats_prefix(), lambda: self.workers_seen(max_age=1e12), "any_age").values():
            if isinstance(hb.extra.get("server"), str):
                node.setdefault(hb.extra["server"], set()).update(l for l in str(hb.extra.get("labels", "")).split(",") if l)
        gone = set(self.decommission_requests()) | {self.draining()}
        out = {}
        for server in sorted(known):
            if server in gone or self.resource_state(server) == "silent":
                continue                                # gone or leaving: no spare runs on it (one only this process
                                                        # cannot reach — `unreachable` — is there, and may carry one)
            labels, said_by = self.server_labels_of(server)
            if said_by != "node":                       # its row; one not known: what it last said, or no label (`labels_of`)
                out[server] = frozenset(labels or ())
            else:
                out[server] = frozenset(node[server]) if server in node else None
        return out

    # A shortage no offer can answer, said once an episode — an alarm: somebody has to give a server the labels, or
    # start a machine (`offer_spares`).
    def _said_withheld(self, withheld: dict) -> None:
        said = self.__dict__.setdefault("_withheld_said", set())
        from .events import ALARM
        for labels in sorted(set(withheld) - said):
            log.error("%s: spares for labels '%s' are short and none is offered: %s", self.sub.name, labels, withheld[labels])
            self.journal.say("spares.no_server", ALARM, sub=self.sub.name, labels=labels, why=withheld[labels])
        said.clear(); said.update(withheld)

    # One offer for `labels`, created under the next number nobody has (`cas=0`); one made under us: the next number.
    def _offer(self, names: list, labels: str, now: float) -> bool:
        for _ in range(10):
            name = f"{self.spec.slot_prefix}-{max([slot_number(n) for n in names] + [0]) + 1}"
            names.append(name)
            try:
                self.vars.put(self.sub.slot_key(name), {"holder": "", "until": "0", "released": "false", "gen": "0",
                                                        "offer": labels, "offered_at": str(now)}, cas=0)
                return True
            except Conflict:
                continue
        return False

    # Units placed away from the home their row names, moved back — at most `budget` a pass, because every
    # move is a new epoch and a seam in the unit's writes. It is the other half of `home`: the preference in
    # `_pick` decides where a unit goes when it is placed, and this is what happens to one already placed
    # somewhere else when its home comes back.
    #
    # `eligible` runs first, so the filters still beat the preference: a unit whose home is barred by
    # `spread_by` or by its labels stays where it is. A home with no live worker, or no room, is not an
    # error and says nothing — the unit is where it can be, which is the point of a preference.
    def ensure_home(self, budget: int = 1, workers: list[str] | None = None) -> list[tuple]:
        """Units away from the home their row names — or, with `near` and no `home`, away
        from the server holding what they follow — moved back, `budget` a pass."""
        if budget <= 0 or not self.spec.home:
            return []
        moves, pool = [], self._pool(workers)
        idx = None                                    # one look for every unit that follows, taken at the first
        for row in self.units():
            if len(moves) >= budget:
                break
            if idx is None and self.spec.home == "near":
                idx = self.near_index()
            uid, home = row["id"], self.home_for(row, idx)
            pl = self.placement(uid)
            if not home or pl is None or self.place_of(pl.worker) == home:
                continue
            best, free = self._best([w for w in self.eligible(row, pool) if self.place_of(w) == home])
            if best is None:
                continue                                  # home is not back, or has no room: stay put, quietly
            why = f"it follows {self.spec.near} onto" if self.spec.home == "near" else "home is"
            if self.move_from(uid, pl.worker, best, f"{why} {home}; most free capacity ({free}); on {home}"):
                moves.append((uid, pl.worker, best))
        return moves

    # WHAT MAKES A LABEL AN EDIT AND NOT A NOTE (feedback DQ). A placed unit whose worker no longer passes the constraint
    # — its server's labels, or its own, changed after it was placed — moves to a live worker that does; when none does,
    # it gives its place back with the reason, and `/unplaceable` lists it. Without this a label decided only the NEXT
    # placement: a unit stayed on a server that had stopped reaching it, and nothing said so.
    #
    # Only the constraint is asked again — `spread_by` and the subsystem's `admit` decided the place once and are not
    # this step's, though the target is chosen through `eligible`, which asks them — and only of a unit on a LIVE worker
    # of the pool: the units of a worker that is gone, leaving or draining are `redistribute`'s. At most `budget` a pass:
    # every move is a new epoch and a seam in the unit's writes, and an edit that strips a server of its VLAN moves its
    # units over a few passes, not in one. A pass that has never read the servers' rows (`server_labels` is None: the
    # store did not answer since this process started — every server's reach `unknown`) moves nothing; nor does one off
    # a server whose row did not read this pass (the tenth pass).
    #
    # THE GROUP MOVES WHOLE, OR NOT THIS PASS (the review's tenth pass, minor): an administrator of one channel of a
    # four-channel box changed its `labels`, and the channel went alone to another holder — two sessions to one
    # box, for good. A unit with a group (`group_by`: its address's box) moves with every unit of its group on its
    # worker, onto a worker that takes them all, in one pass.
    #
    # …ONTO ANY WORKER THAT HAS ROOM FOR ALL OF IT, AND NEVER SPLIT, NEVER PAST THE BUDGET (the eleventh review: a major,
    # a minor, and the remark on the budget; the product's cross-check). The target was `_pick`'s ONE worker — the near
    # one first — and when that one had two places for a four-channel box the pass gave all four back "nothing live
    # reaches it", while srv-c with fifty reached them; the next placement put two on srv-b and two nowhere, for good.
    # Now the target is picked among the workers that reach every unit of the group AND have room for the whole of it
    # (near and home still first among those). With none, a unit alone gives its place back with the true reason (none
    # reaches it, or none that reaches it has room); a GROUP stays where it is, whole — giving back the units its server
    # stopped reaching split it, and they were then placed beside the others' worker on another — said in the log once
    # and counted (`last_reach_waiting`, `reach_waiting` in the pass report), and asked again next pass. And a group is
    # moved inside the pass's budget: 32 channels with a budget of 10 were 32 epochs and seams in one pass. A group
    # bigger than the budget waits the same way, said with its size — the budget is raised, or it is moved by hand.
    #
    # …and A LABEL NO ROW CAN SAY IS NOT A REASON TO MOVE (the same pass, major): a unit stored with `склад` before the
    # one alphabet was placed by a node's word; a server's row cannot hold the word, so the unit stays where it is,
    # counted once (`UNIT_LABELS`). Each move and each place given back is a line in the log with its reason; the pass
    # report counts them (`reach_moves`, and `reach_moves_total` since the store was new).
    #
    # …COUNTED OVER THE WHOLE PASS (the review's twelfth pass, minor): the walk stopped at the budget, and what it had not
    # reached was not counted — `units_waiting_for_reach` showed 0 while units stood on a server that no longer reached
    # them. The walk goes on past the budget now, moving nothing, and counts every unit it leaves off its reach.
    def ensure_reach(self, budget: int | None = None, workers: list[str] | None = None) -> list[tuple]:
        """Units whose worker no longer passes the constraint, moved to one that does — or unplaced, with the reason."""
        budget = self.reach_budget if budget is None else budget
        self.last_reach_moves = self.last_reach_waiting = 0
        rule = CONSTRAINTS[self.spec.constraint]
        if budget <= 0 or self.spec.constraint == "none" or self.server_labels() is None:
            return []
        unread = set(self._server_rows_unread)
        pool = self._pool(workers)
        live, moves, idx, done, waits = set(pool), [], None, set(), set()

        def wait(group, worker, words):                   # the group stays whole where it is: said once a spell, counted
            key = (str(group[0]["id"]), worker)
            waits.add(key)
            self.last_reach_waiting += len(group)
            if key not in self._reach_said:
                self._reach_said.add(key)
                log.warning("%s: %s and %d more of one %s stay on %s, which no longer reaches %s: %s — asked again every "
                            "pass", self.sub.name, group[0]["id"], len(group) - 1, self.spec.group_by, worker,
                            group[0]["id"], words)

        spent = False                                     # the budget spent: the rest only counted
        for row in self.units():
            spent = spent or len(moves) >= budget
            uid = row["id"]
            if str(uid) in done:
                continue
            pl = self.placement(uid)
            if pl is None or pl.worker not in live or self.retired(row):
                continue
            server = self.server_of(pl.worker)
            if server in unread:
                continue                                  # what its server reaches is not known this pass: it stays
            has = self.labels_of(pl.worker)
            if rule(row, has):
                continue
            why = self._why_off(row, server, has)
            if why is None:
                continue                                  # a label no server's row can say: it stays, counted
            group = self._reach_group(row, pl.worker)
            done |= {str(m["id"]) for m in group}
            if len(group) > budget:
                wait(group, pl.worker, f"its {len(group)} units are more than the {budget} moves a pass may make — "
                                       f"REACH_BUDGET in the controller's environment raises it")
                self._over_budget(group, pl.worker, budget)
                continue
            if spent or len(moves) + len(group) > budget:
                spent = True
                self.last_reach_waiting += len(group)     # the group goes whole, next pass: counted, not said
                waits.add((str(uid), pl.worker))          # …and not said again as waiting for another reason
                continue
            idx = self.near_index() if idx is None else idx
            others = [w for w in pool if w != pl.worker]
            fits = None
            for m in group:
                e = set(self.eligible(m, others))
                fits = e if fits is None else fits & e
            reach = [w for w in others if w in fits]
            roomy = [w for w in reach if self.capacity_of(w) - self.load(w) >= len(group)]
            best, free, near = self._pick(roomy, uid, idx)
            if best is None:
                lack = "nothing live reaches it" if not reach else \
                    f"no live worker that reaches it has room for {'it' if len(group) == 1 else f'its {len(group)} units'}"
                if len(group) > 1:
                    wait(group, pl.worker, lack)
                    continue
                if self.unplace_from(uid, pl.worker, f"{why}; {lack}"):
                    moves.append((uid, pl.worker, None))
                    log.warning("%s: %s gave its place on %s back: %s; %s", self.sub.name, uid, pl.worker, why, lack)
                continue
            for m in group:
                reason = (f"{why}; most free capacity ({free}); on {self.server_of(best)}{near}" if m is row else
                          f"with {uid}, one {self.spec.group_by}: {why}; on {self.server_of(best)}")
                if not self.move_from(m["id"], pl.worker, best, reason):
                    break                                 # somebody moved it first: the rest of the group waits for the next pass
                moves.append((m["id"], pl.worker, best))
                log.warning("%s: %s moved from %s to %s: %s", self.sub.name, m["id"], pl.worker, best, reason)
        moves += self._regroup(pool, budget - len(moves), done, wait)
        self._reach_said &= waits
        self._reach_budget_said &= waits
        self.last_reach_moves = len(moves)
        return moves

    # A NEW MEMBER ITS GROUP'S WORKER MAY NOT TAKE (the review's thirteenth pass, major 17). A channel added to a box
    # whose other channels are placed is pinned to their worker (`eligible`: one group, one worker) — and when it needs
    # a label that worker's server does not reach, it was unplaced for ever: `unplaceable` said so, and no door moves a
    # group by hand. Such a member is a reason to move the group whole: the placed members together onto a worker that
    # EVERY member — placed and waiting — may go to and that has room for all of them; the waiting ones follow it on the
    # next pass (`place`, pinned to the group's new worker). None: it waits, said once a spell, counted in
    # `reach_waiting`. Within the same budget as the moves above, the group whole or not at all.
    def _regroup(self, pool: list[str], budget: int, done: set, wait) -> list[tuple]:
        moves, idx = [], None
        if not self.spec.group_by:
            return moves
        for row in self.units():
            uid = row["id"]
            if str(uid) in done or self.retired(row) or not self.group_value(row) or self.placement(uid) is not None:
                continue
            held = self.worker_with_group(row, pool)
            if held is None:
                continue                                  # no group placed: `place`'s to do
            # …or one its worker HAS NO ROOM FOR (the product's r29-writers2, decided whole): a new group's first channels
            # went onto a worker without room for the rest, which waited pinned to it for ever — while `offer_spares`
            # counts the group whole, a spare came and nothing moved. The same reason to move the group whole.
            waiting = self._group_rows_waiting(row)
            roomless = self.capacity_of(held) - self.load(held) < len(waiting)
            if self.eligible(row, pool) and not roomless:
                continue                                  # its worker takes it: `place`'s to do
            why = f"which {held} has no room for" if roomless and self.eligible(row, pool) else f"which {held} may not take"
            first = next((o for o in self._rows_by("group", self.group_value).get(self.group_value(row), ())
                          if not self.retired(o) and (pl := self.placement(o["id"])) is not None and pl.worker == held), None)
            if first is None:
                continue
            group = self._reach_group(first, held)
            done |= {str(m["id"]) for m in group + waiting}
            if len(group) > budget:
                wait(group, held, f"its {len(group)} units would move with {uid}, a new member {why} — "
                                  f"more than the {budget} moves left this pass")
                continue
            others = [w for w in pool if w != held]
            fits = None
            for m in group + waiting:
                e = set(self.eligible(m, others))
                fits = e if fits is None else fits & e
            roomy = [w for w in others if w in fits and self.capacity_of(w) - self.load(w) >= len(group) + len(waiting)]
            idx = self.near_index() if idx is None else idx
            best, free, near = self._pick(roomy, uid, idx)
            if best is None:
                wait(group, held, f"{uid}, a new member {why}, waits, and no live worker takes all "
                                  f"{len(group) + len(waiting)} of them")
                continue
            for m in group:
                reason = (f"with {uid}, one {self.spec.group_by}, {why}; most free capacity ({free}); "
                          f"on {self.server_of(best)}{near}")
                if not self.move_from(m["id"], held, best, reason):
                    break                                 # somebody moved it first: the rest of the group, next pass
                moves.append((m["id"], held, best))
                log.warning("%s: %s moved from %s to %s: %s", self.sub.name, m["id"], held, best, reason)
            budget -= len(group)
        return moves

    # A group too big for the budget, said once a spell in the journal — an alarm: it waits until somebody raises it.
    def _over_budget(self, group: list[dict], worker: str, budget: int) -> None:
        key = (str(group[0]["id"]), worker)
        if key in self._reach_budget_said:
            return
        self._reach_budget_said.add(key)
        from .events import ALARM
        self.journal.say("units.over_budget", ALARM, sub=self.sub.name, unit=str(group[0]["id"]), units=len(group),
                         worker=worker, budget=budget,
                         why=(f"{len(group)} units of one {self.spec.group_by} stay on {worker}, whose server no longer "
                              f"reaches them: they move together, and that is more than the {budget} moves a pass may "
                              f"make — raise REACH_BUDGET in the controller's environment"))

    # Why a unit is off its server — the labels it needs that the server does not reach — or None when one of them is a
    # word no server's row can hold (`LABEL_WORD`): then it is not moved for it (counted once, `UNIT_LABELS`).
    def _why_off(self, row: dict, server: str, has: set) -> str | None:
        if self.spec.constraint != "labels-subset":
            return f"{server} no longer meets {self.spec.constraint}"
        lost = sorted(set(map(str, row.get("labels") or [])) - set(has))
        key = f"{self.row_key(row['id'])}#labels"
        bad = [l for l in lost if not LABEL_WORD.fullmatch(l)]
        if bad:
            UNIT_LABELS.garbled(key, f"{bad[0]!r} is not a label")
            return None
        UNIT_LABELS.parsed(key)
        return f"{server} no longer reaches {','.join(lost)}"

    # The units of `row`'s group placed on `worker` — `row` first — or `[row]` when the spec groups nothing or the row
    # has no group.
    def _reach_group(self, row: dict, worker: str) -> list[dict]:
        value = self.group_value(row) if self.spec.group_by else ""
        if not value:
            return [row]
        out = [row]
        for other in self._rows_by("group", self.group_value).get(value, ()):
            if str(other["id"]) == str(row["id"]) or self.retired(other):
                continue
            pl = self.placement(other["id"])
            if pl is not None and pl.worker == worker:
                out.append(other)
        return out

    # A unit's place given back — the row says nowhere, and why — only while the row still names `frm`, in the same CAS
    # that writes it (`move`'s rule); then the assignment follows. The next pass places it again if anything live can.
    def unplace_from(self, uid, frm: str, reason: str) -> bool:
        def mutate(it):
            if (it or {}).get("worker") != frm:
                raise Moved(f"{uid} is on {(it or {}).get('worker') or 'nobody'}, not on {frm}: somebody moved it first")
            return {"worker": "", "reason": reason, "at": self.wall(), "rev": _next_rev(it)}
        try:
            self.write(self.sub.config("placement", str(uid)), mutate)
        except Moved as e:
            log.info("%s: %s", self.sub.name, e)
            return False
        self.assign_remove(frm, str(uid))
        return True

    # Why a unit is nowhere, when its placement row says so — a reach lost, a unit finished, deleted — else None.
    def unplaced_reason(self, uid) -> str | None:
        it = self._placement_items(self.sub.config("placement", str(uid)))
        return str(it.get("reason") or "") or None if it and not it.get("worker") else None

    # Up to `budget` moves: each step takes the most and least loaded workers by `load/capacity`, stops if
    # their spread is under the dead band or the low one is full, and moves the lowest-numbered unit of the
    # high one. Only when asked. `test_rebalance_is_explicit_budgeted…`: budget 0 moves nothing; budget 3
    # moves three from `w-1` to `w-2`; a further budget of 5 moves one more and then stops inside the 10 %
    # band.
    def rebalance(self, budget: int, dead_band: float | None = None, workers: list[str] | None = None) -> list[tuple]:
        dead_band = self.spec.dead_band if dead_band is None else dead_band
        workers = self._pool(workers)
        moves = []
        while len(moves) < budget:
            if len(workers) < 2:
                break
            loads = {w: self.load(w) / self.capacity_of(w) for w in workers}
            hi, lo = max(workers, key=loads.get), min(workers, key=loads.get)
            if loads[hi] - loads[lo] < dead_band:
                break
            # A unit goes with its group, inside the budget, onto a worker that takes every unit of it and has room for
            # them all — else the next unit is looked at (the product's cross-check of the eleventh review: this moved
            # `cands[0]` alone, the first unit of a group onto another worker, and asked no filter at all).
            group = None
            for unit in sorted(self.assignment(hi).units, key=_unit_key):
                row = self.parsed_unit(self.spec.parse_id(unit)) if self.spec.group_by else None
                g = self._reach_group(row, hi) if row and row is not GARBLED_ROW else None
                ids = [m["id"] for m in g] if g else [self.spec.parse_id(unit)]
                if len(moves) + len(ids) > budget or self.load(lo) + len(ids) > self.capacity_of(lo):
                    continue
                if g and not all(lo in self.eligible(m, [w for w in workers if w != hi]) for m in g):
                    continue
                group = ids
                break
            if group is None:
                break
            why = f"rebalance from {hi} (spread {(loads[hi] - loads[lo]) * 100:.0f}%)"
            for i, uid in enumerate(group):
                if not self.move_from(uid, hi, lo, why if i == 0 else f"with {group[0]}, one {self.spec.group_by}: {why}"):
                    return moves                          # the picture changed under this pass: the next one looks again
                moves.append((uid, hi, lo))
        return moves

    # -- what the console and the layer above read -------------------------------------------
    # What the console lists: every `status` entry from every worker's latest heartbeat (any age), tagged
    # with `worker`, `server`, `age` and `worker_state` (`live` or `stale`), sorted by unit id.
    # `test_the_failure_arithmetic`: with the controller gone the read model still answers from heartbeats;
    # with the worker gone 100 s the rows say `stale`, age 100. The age is how long THIS reader has seen the heartbeat
    # stand still (`Eyes`; the product's r29-writers2): `now - hb.ts` was the worker's clock against the console's, and
    # a worker 100 s behind read `stale` on every row while it ran them.
    def read_model(self, lost_after: float = 45.0) -> list[dict]:
        rows = []
        for w, hb in self.workers_seen(max_age=1e12).items():
            age = self.eyes.age(self.sub.heartbeat_key(w), hb.token, hb.ts, self.sub.name)
            state = "live" if age <= lost_after else "stale"
            for s in hb.status:
                if "id" not in s:
                    continue                            # an entry that names no unit says nothing about one (the seventh pass)
                rows.append({**s, "worker": w, "server": hb.extra.get("server", "?"), "age": round(age, 1), "worker_state": state})
        return sorted(rows, key=lambda r: _unit_key(str(r["id"])))

    # -- blobs: a field too big for a row ------------------------------------------------------------
    # The bytes of one `blob` field. Written FIRST, before the row that names them: a crash between the
    # two leaves an object nobody points at (harmless, collectable), where the other order would leave a
    # row pointing at nothing — a unit that cannot start. The same order М12's identity store publishes in.
    #
    # The key is the digest, so this is idempotent by construction: writing the same bytes twice writes
    # the same object twice, and two units with the same mask share one object.
    def put_blob(self, data: bytes) -> str:
        """Store the bytes; return the digest to put in the row."""
        d = blob_digest(data)
        # These exact bytes may be sitting on the sweep's list right now — the same mask uploaded again
        # for a second unit, while the copy the first unit stopped naming is marked for collection.
        # Taking it off the list makes the sweep's own CAS fail, and a sweep that loses that CAS deletes
        # nothing at all. The alternative is a lock, for a window two store calls wide.
        key = self.sub.sweep_key()

        def off_the_list(it):
            marked = _sweep_list(it)[0]
            return {**it, "digests": canonical_json([x for x in marked if x != d])} if d in marked else None

        self.write(key, off_the_list)                 # by CAS, tried again on a conflict: the sweeper writes this row too
        # On the platter before the row names it (`FsObjectStore.put_durable`); a store without the barrier puts as it can.
        getattr(self.objects, "put_durable", self.objects.put)(self.sub.blob_key(d), data)
        return d

    # What a worker calls with the digest it read from its row. `None` when the object is not there, which
    # is a real state — the row travelled and the object did not — and the caller must not start on it.
    #
    # The bytes are CHECKED against the digest before they are handed over. Not belt-and-braces: the key
    # says what the bytes are, and nothing but this makes that true. An ACL says who may write the key,
    # which is a different claim and a weaker one — it cannot survive a store shared more widely than
    # intended, an object copied between stores, or a bad disk. `verify` survives all three.
    def blob(self, d: str, check_digest: bool = True) -> bytes | None:
        data = self.objects.get(self.sub.blob_key(d))
        if data is None or not check_digest:
            return data
        return verify(d, data)

    # Every digest any row currently names: what the sweep keeps (`sweep_blobs`, below).
    def blobs_referenced(self) -> set[str]:
        names = [n for n, f in self.spec.fields.items() if f.type == "blob"]
        return {r[n] for r in self.units() for n in names if is_digest(r.get(n) or "")}

    # -- the sweep: collecting blobs nothing names any more ------------------------------------------
    # Besides a worker's marks (`Worker.sweep_marks`) nothing else in the platform deletes an object, and this has to. A blob key is
    # the digest of its bytes, so every edit of a `blob` field makes a NEW permanent object: unlike a
    # heartbeat, whose key is reused by the next instance of the slot, blobs grow with the number of edits
    # over the system's lifetime and nothing ever reclaims them.
    #
    # The obvious implementation is wrong, and it is worth being precise about why. "Delete every blob no
    # row names" races with `put_blob`: the object is written BEFORE the row that names it (Lesson 26), so
    # a sweep landing between those two writes sees an unreferenced blob and deletes the bytes a row is
    # about to point at. The unit then cannot start, and the operator's upload silently did nothing.
    #
    # So noticing and deleting are put in DIFFERENT PASSES:
    #
    #   mark   nothing is deleted. The digests that no row names are written to `<name>/sweep` with the
    #          time. A blob created after this moment is not on the list, which is where the grace period
    #          comes from — no timestamps on objects required, and not every store has them to offer.
    #   sweep  one pass later, and only after `grace`: the marked digests are checked AGAIN, the decision is
    #          written by CAS on the index just read — the doomed digests, `state: deleting` — and only then
    #          are the objects removed, each one read back from the row the moment before.
    #
    # The order of those last two is the whole safety argument. Writing the decision first means a lost CAS —
    # anyone touched the row since the mark — costs nothing: not one object has been deleted yet. Deleting
    # first would mean acting on a decision that something has already contradicted.
    #
    # And the decision STAYS on the row while the bytes go (the review's second pass, m5). It used to be
    # cleared first, so a `put_blob` of a marked digest in the seconds the deletes took found an empty list,
    # took nothing off it, and its bytes were removed under a row about to name them. Now it finds the digest
    # there, as before the decision, and takes it off; the sweeper re-reads the row before each delete and
    # leaves what is gone from it alone. The row is cleared at the end, by CAS; a clear that loses — somebody
    # took a digest off meanwhile — leaves the rest listed for the next pass, which checks them again.
    #
    # That left one window, two store calls wide (the review's third pass): the sweeper reads "still doomed",
    # `put_blob` takes the digest off and writes the object, and the sweeper's delete removes it. It is closed by
    # reading the bytes before the delete and the row AFTER it: a digest that left the list in between is one
    # somebody is uploading, and its object is put back — the same bytes, by construction (the key is their
    # digest), so the restore and the upload write one object, in whichever order they land. Still on the list
    # after the delete means `put_blob` has not taken it off yet, and its own write comes after ours.
    #
    # `limit` is not a nicety either: `<name>/sweep` is a row, and a row has the store's ceiling over it
    # (Lesson 26). The sweep is subject to the rule it was written under.
    SWEEP_LIMIT = 64
    SWEEP_GRACE = 300.0

    def sweep_blobs(self, limit: int = SWEEP_LIMIT, grace: float = SWEEP_GRACE) -> dict:
        """One pass: marks, or sweeps, or waits. `{marked, deleted, waiting}`."""
        names = [n for n, f in self.spec.fields.items() if f.type == "blob"]
        if not names:
            return {"marked": 0, "deleted": 0, "waiting": 0}
        key, now = self.sub.sweep_key(), self.wall()
        items, idx = self.vars.get(key)
        marked, at = _sweep_list(items)

        if not marked:                                   # -- mark: notice, write it down, delete nothing
            referenced = self.blobs_referenced()
            prefix = self.sub.blobs_prefix()
            orphans = sorted(k[len(prefix):] for k in self.objects.list(prefix)
                             if k[len(prefix):] not in referenced)[:limit]
            if orphans:
                self.vars.put(key, {"at": number_text(now), "digests": canonical_json(orphans)}, cas=idx)
            return {"marked": len(orphans), "deleted": 0, "waiting": 0}

        if now - at < grace:
            return {"marked": 0, "deleted": 0, "waiting": len(marked)}

        # -- sweep: check again, write the decision down, and only then remove the bytes
        referenced = self.blobs_referenced()
        # Only digests: an entry of the list that is none is no blob's name — `blob_key` raised on it, every sweep, and the
        # list was never cleared: nothing of the subsystem was reclaimed again (the review's seventh pass).
        doomed = [d for d in marked if isinstance(d, str) and is_digest(d) and d not in referenced]
        self.vars.put(key, {"at": number_text(now), "digests": canonical_json(doomed), "state": "deleting"}, cas=idx)   # Conflict here deletes nothing
        deleted = 0
        for d in doomed:
            items, idx = self.vars.get(key)                                 # still doomed? `put_blob` takes a digest off this list
            if d not in _sweep_list(items)[0]:
                continue
            data = self.objects.get(self.sub.blob_key(d))
            if data is None or not self.objects.delete(self.sub.blob_key(d)):
                continue
            items, idx = self.vars.get(key)                                 # …and after: taken off meanwhile is being uploaded
            if d not in _sweep_list(items)[0]:
                getattr(self.objects, "put_durable", self.objects.put)(self.sub.blob_key(d), data)
                continue
            deleted += 1
        try:
            self.vars.put(key, {"at": str(now), "digests": "[]"}, cas=idx)
        except Conflict:
            pass                                                            # a digest left the list under us: the rest wait for the next pass
        return {"marked": 0, "deleted": deleted, "waiting": 0}

    # Units and placement for the layer above, ONE OBJECT PER WORKER: `<name>/snapshot/<worker>` holding
    # `{cluster, worker, ts, <rows>: [{id, <snapshot fields>, revision, worker, server}]}`, plus
    # `<name>/snapshot/unplaced` for the units nobody holds. A copy with an age — never the rows
    # themselves, which do not leave raft.
    #
    # The shape is the heartbeat's, and that is the point. Every other object in the platform is already
    # sharded by its writer — one heartbeat per worker, one resource heartbeat per server — and stays small
    # whatever the cluster does. The snapshot was the exception: one object for every unit in the cluster,
    # under a store with a ceiling. See `Subsystem.snapshot_key` for the arithmetic that made this a defect
    # rather than a preference.
    def snapshot_shards(self) -> dict[str, dict]:
        """The snapshot as one object per worker, keyed by shard name."""
        with one_pass(self):                          # `server_of` per unit read every heartbeat per unit (the scaling pass)
            return self._snapshot_shards()

    def _snapshot_shards(self) -> dict[str, dict]:
        keep = ["id"] + [f for f in self.spec.snapshot if f != "id"] + ["revision"]
        now, out = self.wall(), {}
        for r in self.units():
            w = self.where(r["id"])
            self.sub.snapshot_key(w)              # refuses a worker named `unplaced` before it shadows the shard
            sh = out.setdefault(w or UNPLACED, {"cluster": self.cluster, "worker": w, "ts": now, self.spec.rows: []})
            # An address leaves with no credential in it (`hide_in_url`; the eleventh review, blocker 4): a row stored before
            # the refusal, or by another build, carried its `?pwd=` into the domain's directory.
            sh[self.spec.rows].append({**{k: hide_in_url(r[k]) for k in keep if k in r}, "worker": w,
                                       "server": self.server_of(w or "")})
        return out

    # The shards merged back, for a reader inside this process. What М12 does over the wire is the same
    # merge, out of `objects.list(snapshot_prefix())` — see `Cluster.snapshot` there.
    def snapshot(self) -> dict:
        """Every shard merged: what the layer above ends up seeing."""
        shards = self.snapshot_shards()
        units = [u for sh in shards.values() for u in sh[self.spec.rows]]
        return {"cluster": self.cluster, "ts": self.wall(), self.spec.rows: units}

    # How old the published snapshot is, in seconds — `None` when nothing has been published.
    #
    # Read from the STORE, not kept in this process: the controller has no port to serve it from, it is
    # restarted freely, and two of them may be running. Whoever can read the objects can answer this, which
    # is what makes it a number a console can put on `/metrics`.
    #
    # The age of the whole is the age of the STALEST shard, the same rule М12's reader uses: a directory is
    # only as fresh as its oldest part, and taking the newest would report an RPO better than the real one —
    # which is exactly the direction a number like this must never be wrong in.
    #
    # BY WHAT THE READER SAW CHANGE (the product's r29-writers2; the ninth pass's minor before it). The age was `now − ts`,
    # the controller's clock against the reader's: a controller an hour ahead that then stopped wrote shards that read
    # "fresh" for that hour (the ninth pass bounded it at `FUTURE_TOLERANCE`), and one 100 s behind read 100 s stale
    # while it published every pass. Now a shard's age is how long THIS reader has seen it stand still (`Eyes`, by its
    # own clock; the shard's `ts` a token that changes with every publish, and the skew measured where it changes) —
    # the oldest of them, the directory's age. A reader started a minute ago has watched a minute: its ages begin at 0,
    # as every judge's here does (`Eyes`), rather than believe a writer's clock. A shard that does not parse has no age
    # anybody can vouch for: the oldest there can be, counted once (`fields_garbled`).
    def snapshot_age(self, now: float | None = None) -> float | None:
        import json
        from .rows import FIELDS
        now = self.wall() if now is None else now
        oldest = None
        prefix = self.sub.snapshot_prefix()
        for key in self.objects.list(prefix):
            raw = self.objects.get(key)
            if not raw:
                continue
            try:
                ts = finite(json.loads(raw).get("ts", 0))   # `nan` passes every `min` and read as fresh (the review's eighth pass)
            except PARSE_ERRORS as e:
                FIELDS.garbled(f"{key}#ts", e)
                return now                            # a shard that does not parse has no age: the oldest there can be
            FIELDS.parsed(f"{key}#ts")
            age = self.eyes.age(key, ts, ts, self.sub.name)
            oldest = age if oldest is None else max(oldest, age)
        return oldest

    # Writes one object per worker under `<name>/snapshot/`.
    def publish_snapshot(self) -> None:
        with one_pass(self):
            self._publish_snapshot()

    def _publish_snapshot(self) -> None:
        import json
        shards = self.snapshot_shards()
        prefix = self.sub.snapshot_prefix()
        # A worker that is GONE — scaled in, or its units moved away — keeps its last shard forever: nothing
        # in the platform deletes an object. Its units would go on being reported to М12 from a worker that
        # no longer exists. So every shard already in the store that this pass did not fill is written EMPTY.
        for key in self.objects.list(prefix):
            shards.setdefault(key[len(prefix):], {"cluster": self.cluster, "worker": None, "ts": self.wall(),
                                                  self.spec.rows: []})
        # A cluster with no units at all — a subsystem's before its first unit — would publish NOTHING, and "published that there are none" would read as
        # "never published" (feedback AA). М12's member that has not published does not report (Lesson 10),
        # so such a cluster stayed "never reported" for ever. An empty `unplaced` shard is the statement.
        if not shards:
            shards[UNPLACED] = {"cluster": self.cluster, "worker": None, "ts": self.wall(), self.spec.rows: []}
        for name, shard in shards.items():
            try:
                self.objects.put(prefix + name, json.dumps(shard).encode())
            except TooLarge as e:
                # The store refuses with bytes; the caller knows what those bytes WERE. A shard is one
                # worker's assignment, so an oversized shard is not a shape problem any more — it is a
                # store too small to hold what a single worker carries, and `OBJECTS` is what names it.
                raise TooLarge(e.key, e.size, e.limit,
                               f"{len(shard[self.spec.rows])} units on {name}; the snapshot is already one "
                               f"object per worker, so the store is the thing to change (OBJECTS=…)") from e

    # Per worker: the gap between the last heartbeat of the previous instance and this instance's start.
    #
    # ON ONE CLOCK (the review's ninth pass, minor; the product's sibling D). `started − previous_hb` subtracted the clock
    # of the box the replacement runs on from the clock of the box the instance before it ran on: on two machines their
    # disagreement was IN the number — ten minutes of drift, a ten-minute failover, or a negative one. Two ways now,
    # each on one clock:
    #
    #   the same server   the instance before ran where this one runs (`previous_server` = `server`, written by the
    #                     replacement from the heartbeat it found): `started − previous_hb`, both by that box's clock
    #   another server    what THIS reader saw, by its own clock: when the heartbeat under that name last moved, and
    #                     when another instance was first there — as late as the reader looks (the console reads it on
    #                     every scrape, the stand when a scene says so)
    #
    # Neither — another server, and this reader did not see the instance before alive — is not measured: no number made
    # of two clocks. Nor is a negative gap (one clock that stepped back). Both are counted (`failovers_unmeasured`, on
    # `/metrics`). Every number through `rows.number`: `previous_hb: -inf` made `worst` infinite and the alert burn for
    # ever. `failover_worst` is the largest this process has measured: the largest of the LAST ones forgot a failover as
    # soon as the same worker had a shorter one.
    #
    # …AND A GAP HAS A CEILING (the eleventh review: the ninth's remainder, not touched in the tenth). A finite absurd
    # `previous_hb` — `-1e308` — passed `rows.number` and made `worst` 1e308, for the life of the process: the alert
    # burned for ever on one garbled field. A gap longer than `FAILOVER_CEILING` is not measured — a unit held by nobody
    # for a month is a worker brought back, not a failover anybody alerts on, and a `previous_hb` that gives one is far
    # more often not a time at all — and is counted with the other unmeasured ones, the field said once.
    FAILOVER_CEILING = 30 * 86400.0

    def failover_seconds(self) -> dict[str, float]:
        """Per worker: the gap between the heartbeat before its current instance started and that instance's start —
        on one clock, or not at all."""
        from .rows import FIELDS, number
        now, out, unmeasured = self.wall(), {}, 0
        for w, hb in self.workers_seen(max_age=1e12).items():
            hk = self.sub.heartbeat_key(w)
            instance = str(hb.extra.get("instance", ""))
            was = self._hb_moved.get(w)                   # (instance, ts, when this reader saw it move)
            if was is not None and was[0] != instance:
                self._failover_seen[w] = round(now - was[2], 1)   # another instance, seen by this reader: its clock only
            if was is None or was[:2] != (instance, hb.ts):
                self._hb_moved[w] = (instance, hb.ts, now)
            prev = number(f"{hk}#previous_hb", hb.extra.get("previous_hb"), float, None)
            if not prev:
                continue                                  # no instance before this one under that name: no failover
            server = hb.extra.get("server")
            if server is not None and hb.extra.get("previous_server") == server:
                started = number(f"{hk}#started", hb.extra.get("started"), float, None) if "started" in hb.extra else hb.ts
                gap = None if started is None else round(started - prev, 1)
            else:
                gap = self._failover_seen.get(w)
            if gap is not None and gap < 0:
                FIELDS.garbled(f"{hk}#previous_hb", ValueError(f"{gap} s before this instance started: a clock stepped back"))
                gap = None
            elif gap is not None and gap > self.FAILOVER_CEILING:
                FIELDS.garbled(f"{hk}#previous_hb", ValueError(f"a gap of {gap:.3g} s is no failover: past {self.FAILOVER_CEILING:.0f} s"))
                gap = None
            if gap is None:
                unmeasured += 1
                continue
            out[w] = gap
            self.failover_worst = max(self.failover_worst, gap)
        self.failovers_unmeasured = unmeasured
        return out
