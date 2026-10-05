"""The boundary between the platform and its subsystems (ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md §2.7; the product's
`w2cplatform/boundary_test.go`, whose dictionary this one copies): the platform knows nothing about any subsystem;
all it knows is the specs, `<sub>.subsystem.yaml`. Three checks:

    1. imports  no module under `w2cplatform/` — every subpackage — and no test of the platform (`PLATFORM_TESTS`)
                imports a subsystem's package (`SUBSYSTEM_PACKAGES`), directly, or through a module of `tests/`.
    2. words    no word of the video product anywhere in the platform's tree: Python with its docstrings, comments,
                log and error strings, the HTML and JS of the page, YAML, Markdown — and the platform's tests.
                Russian included. Words and parts of identifiers (camelCase, snake_case), never substrings:
                `alive`, `receive`, `recover`, `automatic`, `deliver`, `record` are not words of the product.
                Some words are the product's by meaning and not by letters (`live`, `volume`, `rec`, `запис*`):
                `BY_MEANING` says when.
    3. runs     the platform's pieces — the contract, the controller, the console, the resource — come up on
                `testdata/testsub.subsystem.yaml` alone, each in a process of its own where importing a
                subsystem's package fails; and a platform entry point loads a directory of specs.

What is known to be wrong today is the debt, `boundary_debt.txt`: one line per occurrence,

    <step> | <file>:<line> | <what> | <fingerprint>

`step` is the step of the plan (§5, 2…8) that removes it; `what` is a word, `import <package>` or `run <why>`;
the fingerprint is the first eight hex digits of the sha1 of the line's text, stripped. The test fails on anything
not in the debt AND on a line of the debt that is no longer true — so the debt only ever shrinks.

What is compared is the COUNT of each (file, what): a line that moved, or was edited and still says the word, is the
same debt (the product compares the same way). Line numbers and fingerprints say where each one is; they go stale
as the file is edited, and

    W2C_BOUNDARY_SHRINK=1 python3 tests/run.py      (or: python3 -m tests.test_boundary --shrink)

rewrites the debt from what is found — lines that went are dropped, the rest renumbered, each keeping its step (by
fingerprint, else by the nearest old line of the same file and word). It never adds a line and never raises a count:
with anything new it refuses and writes nothing.

This file and `boundary_debt.txt` are the only files that name the product's words on purpose: they are the
dictionary, and are not scanned.
"""
from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                  # the code root, `Source/`
DEBT = os.path.join(HERE, "boundary_debt.txt")
TESTSUB = os.path.join(HERE, "testdata", "testsub.subsystem.yaml")

PLATFORM_TREE = "w2cplatform"                                  # walked whole, every subpackage
SUBSYSTEM_PACKAGES = ("vms", "gstvms", "domain", "cluster")    # what the platform must not reach (`Source/<name>/`)

# The platform's tests: what tests a mechanism of the platform. They are the platform's like its modules — scanned for
# words and imports. Two kinds: the ones that already import no subsystem, and the ones whose subject is a platform
# mechanism but which bring a subsystem up to drive it (debt, step 5: «tests on testsub»). A test whose subject is a
# subsystem's route or loop on the platform — the console's gate over the VMS's rows, garbled rows in every worker's
# loop, a camera's three subsystems on one timeline — is the subsystem's, and is not here until it is split.
PLATFORM_TESTS = (
    # on the platform alone
    "tests/test_configstore.py", "tests/test_configstorevars.py", "tests/test_console_page.py",
    "tests/test_memvariables.py", "tests/test_portability.py", "tests/test_resource_objects.py",
    "tests/test_store_durable.py", "tests/test_storemachine.py", "tests/test_variables_contract.py",
    # a mechanism of the platform as the subject, a subsystem brought up to drive it
    "tests/test_lesson1_platform.py", "tests/test_alarm_tree.py", "tests/test_blobs.py", "tests/test_doors.py",
    "tests/test_doors_shut.py", "tests/test_epoch_meaning.py", "tests/test_event_line.py", "tests/test_journal.py",
    "tests/test_lease_step.py", "tests/test_limits.py", "tests/test_names.py", "tests/test_near_by.py",
    "tests/test_pass_failures.py", "tests/test_placement_decides.py", "tests/test_retire.py", "tests/test_sealing.py",
    "tests/test_slot_fate.py", "tests/test_slot_fence.py", "tests/test_snapshot_shards.py", "tests/test_stand_in.py",
    "tests/test_store_outage.py", "tests/test_sweep.py",
    "tests/test_units_about.py", "tests/test_spec_keys.py", "tests/test_host.py", "tests/testdata/testsub.subsystem.yaml",
    "tests/test_spec_declarations.py",
)
SCANNED = (".py", ".html", ".htm", ".js", ".css", ".yaml", ".yml", ".json", ".md", ".sh", ".txt", ".hcl", ".service")


# -- the dictionary ------------------------------------------------------------------------------------------------
#
# A word of the product, as the debt names it, and the parts of identifiers / words of text that are it:
#   forms   a part equal to one of these, lower-cased
#   stems   (Russian) a word beginning with one of these
#   mean    allowed by its letters: forbidden only where the meaning is the product's (BY_MEANING)
#   whole   also a word written as one whose parts are not it: `XMeye`, `H264`, `h264parse`
#
# The list is the product's (the architect's, 2026-10-04) plus four of the course's own: `driverpack` (the devices'
# library), `gstreamer`, `obsd` (the archive's engine, whose client lay in the platform until step 4) and `webrtc`.
PRODUCT_WORDS = [
    ("vms", dict(forms=("vms",))),
    ("cam", dict(forms=("cam", "cams"))),
    ("camera", dict(forms=("camera", "cameras"))),
    ("rec", dict(forms=("rec", "recs"), mean=True)),         # the subsystem; `record` (a row, a write) is allowed
    # the detectors; `detect`/`detection` ("detects a conflict") are the language's
    ("det", dict(forms=("det", "dets", "detector", "detectors"))),
    ("auto", dict(forms=("auto", "automation"))),            # the scenarios; `automatic(ally)` and CSS `auto` are allowed
    ("live", dict(forms=("live",), mean=True)),
    ("archive", dict(forms=("archive", "archives", "archived"))),
    ("footage", dict(forms=("footage",))),
    ("video", dict(forms=("video", "videos"))),
    ("rtsp", dict(forms=("rtsp", "rtsps"))),
    ("device", dict(forms=("device", "devices"))),
    ("recorder", dict(forms=("recorder", "recorders"))),
    ("recording", dict(forms=("recording", "recordings"))),
    ("volume", dict(forms=("volume", "volumes"), mean=True)),
    ("whep", dict(forms=("whep",))),
    ("timeline", dict(forms=("timeline", "timelines"))),
    ("ptz", dict(forms=("ptz",), whole=True)),
    ("codec", dict(forms=("codec", "codecs"), whole=True)),
    ("mp4", dict(forms=("mp4",), whole=True)),
    ("h264", dict(forms=("h264",), whole=True)),
    ("h265", dict(forms=("h265",), whole=True)),
    ("fps", dict(forms=("fps",), whole=True)),
    ("bitrate", dict(forms=("bitrate", "bitrates"), whole=True)),
    ("onvif", dict(forms=("onvif",), whole=True)),
    ("nvr", dict(forms=("nvr", "nvrs"), whole=True)),
    ("xmeye", dict(forms=("xmeye",), whole=True)),
    ("hikvision", dict(forms=("hikvision",), whole=True)),
    ("dahua", dict(forms=("dahua",), whole=True)),
    ("driverpack", dict(forms=("driverpack",), whole=True)),
    ("gstreamer", dict(forms=("gstreamer",), whole=True)),
    ("obsd", dict(forms=("obsd",), whole=True)),
    ("webrtc", dict(forms=("webrtc",), whole=True)),
    ("камер", dict(stems=("камер",))),
    ("видео", dict(stems=("видео",))),
    ("архив", dict(stems=("архив",))),
    ("регистратор", dict(stems=("регистратор",))),
    ("рекордер", dict(stems=("рекордер",))),
    ("устройств", dict(stems=("устройств",))),
    ("запис", dict(stems=("запис",), mean=True)),
]

# A part made of a product stem and a word of a process or a row — `recworker`, `vmsconsole`, `livefeed`,
# `volumeseen` — is the stem's word, always (a name of the product's, whatever the stem means alone).
COMPOUND_STEMS = {"vms": "vms", "cam": "cam", "rec": "rec", "det": "det", "auto": "auto", "live": "live",
                  "video": "video", "rtsp": "rtsp", "volume": "volume"}
COMPOUND_TAILS = {"worker", "workers", "controller", "console", "ctl", "dev", "server", "subsystem", "cam", "act",
                  "proc", "front", "feed", "push", "fan", "box", "start", "stop", "state", "err", "job", "list", "add",
                  "seen", "stream", "id", "ids"}


def _regs(*src):
    return [re.compile(s) for s in src]


# BY_MEANING: where a word allowed by its letters is the product's by its meaning (the architect's rulings,
# 2026-10-04). An occurrence counts when a `forbid` match covers it, or when its line has one of `context` (parts,
# lower-cased; a Russian context is a stem) — the product's words around it say which sense it is in — unless an
# `allow` match covers it: the platform's own name for the thing.
#
#   live    allowed as "alive" (a fresh heartbeat, a live server, `state == "live"`); the product's as the
#           live-video subsystem (LIVE_NAME, live_url, /live/, the live gateway, the player's `live`).
#   volume  allowed as the resource's volume (a place with a quota the resource measures, `place_by: volume`);
#           the product's as the archive's volume (rec/volumes, a recorder's volume, a network volume).
#   rec     allowed as a record — a row, a write; the product's as the recording subsystem: `rec/…`, `"rec"`,
#           `sub: rec`, the rec controller, a line about recordings, recorders and cameras.
#   запис*  allowed as a write to the store; the product's as recording video.
BY_MEANING = {
    "live": dict(
        forbid=_regs(r"(?i)\blive[ _-]?(gateway|gateways|controller|picture|feed|video|view|viewer|stream|streams|session)\b",
                     r"\bLIVE_NAME\b", r"\blive_url\b", r"/live\b", r"\blive/", r"\blive and det\b",
                     r"(?i)watch(ing|ed)?:?\s+live\b", r"['`\"]live( ?:| ·| refused)", r"\blive\.(pc|session|timer|since|seen)\b",
                     r"\blet live\b", r"\blive, detectors\b", r"\blive events\b", r"\bLIVE_SPEC\b",
                     r"(?i)\bsub(system)?[=:]\s*['\"]?live\b"),
        context=("gateway", "gateways", "whep", "webrtc", "video", "viewer", "viewers", "watching", "picture")),
    "volume": dict(
        allow=_regs(r"place_by:\s*volume\b", r"\bvolume_stuck\b", r"\bvolumes_stuck\b"),
        forbid=_regs(r"\brec/volume\w*", r"\bvolume_error\b", r"(?i)\bnetwork volumes?\b", r"\barchive\.volume\b"),
        context=("archive", "archives", "footage", "recorder", "recorders", "recording", "recordings", "rec",
                 "camera", "cameras", "cam", "vms", "obsd")),
    "rec": dict(
        forbid=_regs(r"\brec/", r"/rec\b", r"[\"'`]rec[\"'`]", r"(?m)^\s*rec:", r"\b(sub|near|by):\s*rec\b",
                     r"(?i)\bthe rec\b", r"\brec (subsystem|controller|worker|workers|spec|unit|units)\b",
                     r"\brecs?\.(subsystem|yaml)\b", r"\bREC_SPEC\b"),
        context=("recording", "recordings", "recorder", "recorders", "camera", "cameras", "cam", "footage", "archive",
                 "vms", "live", "det")),
    "запис": dict(
        forbid=_regs(r"(?i)\bзаписыва(ть|ется|ются)\b", r">Записи<"),
        context=("камер", "видео", "архив", "регистратор", "рекордер")),
}

# What is blanked before a line is read: words that look like the product's and are not.
NOT_THE_PRODUCT = _regs(
    r"overflow(-[xy])?\s*:\s*auto\b", r"margin(-[a-z]+)?\s*:[^;}\"]*\bauto\b", r"\b(width|height)\s*:\s*auto\b",   # CSS
    r"\bgrid-template-columns\s*:[^;}\"]*", r"\bdevice-(width|height|pixel-ratio)\b",   # the browser's screen
    r"\(device, inode\)", r"\bdevice and inode\b",                                     # a file's identity: `st_dev`
)

_WORDS = {}
for _w, _o in PRODUCT_WORDS:
    for _f in _o.get("forms", ()):
        _WORDS[_f] = (_w, _o.get("mean", False))
_STEMS = [(s, w, o.get("mean", False)) for w, o in PRODUCT_WORDS for s in o.get("stems", ())]
_WHOLE = {f: w for w, o in PRODUCT_WORDS if o.get("whole") for f in o.get("forms", ())}


def parts_of(line: str) -> list[tuple[str, int, int]]:
    """A line's words (letters and digits; `_` and everything else separate them), each split into the parts of an
    identifier: camelCase, HTTPServer → http server, a letter and a digit apart. `(lower-cased part, start, end)`."""
    out = []
    i, n = 0, len(line)
    while i < n:
        if not line[i].isalnum():
            i += 1
            continue
        j = i
        while j < n and line[j].isalnum():
            j += 1
        start = i
        for k in range(i + 1, j + 1):
            cut = k == j
            if not cut:
                a, b = line[k - 1], line[k]
                cut = ((a.islower() and b.isupper())
                       or (a.isupper() and b.isupper() and k + 1 < j and line[k + 1].islower())
                       or (a.isdigit() != b.isdigit()))
            if cut:
                out.append((line[start:k].lower(), start, k))
                start = k
        i = j
    return out


def _word_of(part: str):
    if part in _WORDS:
        return _WORDS[part]
    for s, w, mean in _STEMS:
        if part.startswith(s):
            return w, mean
    for stem, w in COMPOUND_STEMS.items():
        if part.startswith(stem) and part[len(stem):] in COMPOUND_TAILS:
            return w, False
    return None


def _covered(regs, line: str, a: int, b: int) -> bool:
    return any(m.start() <= a and b <= m.end() for r in regs for m in r.finditer(line))


def words_in(line: str) -> Counter:
    """The product's words in one line, counted."""
    for r in NOT_THE_PRODUCT:
        line = r.sub(lambda m: " " * len(m.group(0)), line)
    parts = parts_of(line)
    out: Counter = Counter()
    # the words of `whole`: a word written as one (`XMeye`, `H264`) is looked at whole as well as by its parts —
    # whose `x` and `meye`, `h` and `264` are nobody's — and so is a letter part with the digits after it
    i = 0
    while i < len(parts):
        j = i + 1
        while j < len(parts) and parts[j - 1][2] == parts[j][1]:
            j += 1
        if j - i > 1:
            run = "".join(p[0] for p in parts[i:j])
            if run in _WHOLE:
                out[_WHOLE[run]] += 1
            else:
                for k in range(i, j - 1):
                    a, b = parts[k], parts[k + 1]
                    if a[0][0].isalpha() and b[0][0].isdigit() and (a[0] + b[0]) in _WHOLE:
                        out[_WHOLE[a[0] + b[0]]] += 1
        i = j
    have = None
    for s, a, b in parts:
        hit = _word_of(s)
        if hit is None:
            continue
        w, mean = hit
        if mean:
            m = BY_MEANING[w]
            if _covered(m.get("allow", ()), line, a, b):
                continue
            if not _covered(m["forbid"], line, a, b):
                if have is None:
                    have = {p[0] for p in parts}
                if not any(c in have or (not c.isascii() and any(q.startswith(c) for q in have)) for c in m["context"]):
                    continue
        out[w] += 1
    return out


# -- where to look ---------------------------------------------------------------------------------------------------

def platform_files() -> list[str]:
    """Every file of the platform's tree the words are looked for in, relative to the code root."""
    out = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, PLATFORM_TREE)):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for f in sorted(filenames):
            if f.lower().endswith(SCANNED):
                out.append(os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, "/"))
    return out + [t for t in PLATFORM_TESTS if os.path.exists(os.path.join(ROOT, t))]


def fingerprint(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:8]


# A finding: (file, line, what, fingerprint). `what` is a word, `import <package>`, or `run <why>`.
def word_findings() -> list[tuple[str, int, str, str]]:
    out = []
    for rel in platform_files():
        with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as f:
            for ln, text in enumerate(f, 1):
                for w, n in sorted(words_in(text).items()):
                    out += [(rel, ln, w, fingerprint(text))] * n
    return out


def _module_file(mod: str) -> str | None:
    """The file of a module of the code root (`w2cplatform.x`, `tests.y`), or None for anything else."""
    base = os.path.join(ROOT, *mod.split("."))
    for cand in (base + ".py", os.path.join(base, "__init__.py")):
        if os.path.exists(cand):
            return cand
    return None


# `vms.x`, `domain.access:cluster_access` — a dotted module path or a `module:function` (an entry point); not a file
# name (`vms.subsystem.yaml`) and not the bare word, which is a subsystem's NAME and a word of the dictionary.
_BY_NAME = re.compile(r"^(%s)((\.[A-Za-z_]\w*)+(:[A-Za-z_]\w*)?|:[A-Za-z_]\w*)$(?<!\.yaml)(?<!\.yml)(?<!\.json)(?<!\.py)"
                      % "|".join(SUBSYSTEM_PACKAGES))


def _imports(path: str) -> list[tuple[int, str]]:
    """`(line, module)` for every import in a file — at the top, inside a function, or a module of a subsystem named
    in a string (`"vms.x"`, `"domain.access:cluster_access"`: what `importlib` would import). Relative imports are
    resolved against the file's package."""
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src, path)
    pkg = os.path.relpath(os.path.dirname(path), ROOT).replace(os.sep, ".")
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".")[: len(pkg.split(".")) - node.level + 1]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            out.append((node.lineno, mod))
            out += [(node.lineno, f"{mod}.{a.name}") for a in node.names if _module_file(f"{mod}.{a.name}")]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and _BY_NAME.match(node.value):
            # a module named in a string — `importlib.import_module(name)` of a default like
            # `"domain.access:cluster_access"` — is an import that happens at run time
            out.append((node.lineno, node.value.partition(":")[0]))
    return out


def _module_level(path: str) -> list[str]:
    """The modules a file imports when it is imported: its top-level `import`s (and those under a top-level `if` or
    `try`), not the ones inside a function nor a module named in a string."""
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    pkg = os.path.relpath(os.path.dirname(path), ROOT).replace(os.sep, ".")
    out, todo = [], list(tree.body)
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.If, ast.Try)):
            todo += node.body + node.orelse + getattr(node, "finalbody", []) + [
                n for h in getattr(node, "handlers", []) for n in h.body]
        elif isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                mod = ".".join(pkg.split(".")[: len(pkg.split(".")) - node.level + 1] + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            out.append(mod)
            out += [f"{mod}.{a.name}" for a in node.names if _module_file(f"{mod}.{a.name}")]
    return out


def _reaches(mod: str, seen: dict) -> set[str]:
    """The subsystem packages importing a module of the code root brings in — its module-level imports, followed
    through the other modules of the code root."""
    if mod in seen:
        return seen[mod]
    seen[mod] = set()
    path = _module_file(mod)
    found = set()
    if path:
        for m in _module_level(path):
            top = m.split(".")[0]
            if top in SUBSYSTEM_PACKAGES:
                found.add(top)
            elif top in (PLATFORM_TREE, "tests") and m != mod:
                found |= _reaches(m, seen)
    seen[mod] = found
    return found


def import_findings() -> list[tuple[str, int, str, str]]:
    out, seen = [], {}
    files = [f for f in platform_files() if f.endswith(".py") and os.path.basename(f) != "test_boundary.py"]
    for rel in files:
        path = os.path.join(ROOT, rel)
        lines = open(path, encoding="utf-8").read().splitlines()
        hits = set()
        for ln, m in _imports(path):
            top = m.split(".")[0]
            if top in SUBSYSTEM_PACKAGES:
                hits.add((ln, f"import {top}"))
            elif top in (PLATFORM_TREE, "tests"):
                hits |= {(ln, f"import {s} via {m}") for s in _reaches(m, seen)}
        out += [(rel, ln, what, fingerprint(lines[ln - 1])) for ln, what in sorted(hits)]
    return out


# -- 3. the runs: the platform on testsub alone ---------------------------------------------------------------------
#
# Each piece runs in a process of its own (`run_piece`: `python3 -c` with `_GUARD` first) where a subsystem's package
# does not import: an import of one is `run:<piece> | run import <package>`. A piece that comes up short says why
# (`BOUNDARY-RUN <why>`), and that is `run:<piece> | run <why>`; anything else it raises is `run broken: …` — never
# debt to write down, a piece to mend.
PIECES = ("contract", "controller", "console", "events", "resource", "host")

_GUARD = f"""
import sys
class _Refuse:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in {SUBSYSTEM_PACKAGES!r}:
            raise ImportError("BOUNDARY-IMPORT " + name.split(".")[0])
        return None
sys.meta_path.insert(0, _Refuse())
"""


def _testsub_box():
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.variables import FileVariables

    class Clock:
        def __init__(self, t): self.t = t
        def __call__(self): return self.t
        def advance(self, s): self.t += s
    root = tempfile.mkdtemp(prefix="testsub-")
    return (root, FileVariables(os.path.join(root, "config")), FsObjectStore(os.path.join(root, "objects")),
            Clock(1000.0), Clock(1_757_500_000.0))


def _counter_worker(sub, vars_, objects, clock, wall, instance: str, server: str):
    """testsub's worker, a stub: it holds the counters it was given — takes each one's epoch, lets go of the ones taken
    away — and says so in its heartbeat. Everything else is the platform's `Worker`."""
    from w2cplatform.contract import Worker

    class CounterWorker(Worker):
        def reconcile_once(self, now=None):
            units = self.assignment().units
            for u in units:
                if u not in self.epochs:
                    self.take_epoch(u)
            for u in [u for u in self.epochs if u not in units]:
                self.release(u)
            self.heartbeat([{"id": u, "phase": "running"} for u in units], server=self.server, capacity=4,
                           headroom=4 - len(units))
            return units

    w = CounterWorker(sub, None, vars_, objects, clock=clock, wall=wall, instance=instance)
    w.server = server
    w.claim_slot()
    return w


def _piece_contract():
    """The contract's keys are under the subsystem's name; two workers claim two slots, the one given a unit takes its
    epoch and may write, and is fenced when another takes it."""
    from w2cplatform.contract import Controller, Subsystem
    root, vars_, objects, clock, wall = _testsub_box()
    sub = Subsystem("testsub")
    assert sub.assignment("w-1") == "testsub/workers/w-1" and sub.epoch_key("c1") == "testsub/epoch/c1"
    assert sub.heartbeat_key("w-1") == "testsub/heartbeats/w-1" and sub.acl_controller() == ["testsub/*"]
    a = _counter_worker(sub, vars_, objects, clock, wall, "A", "srv-1")
    b = _counter_worker(sub, vars_, objects, clock, wall, "B", "srv-2")
    assert (a.name, b.name) == ("w-1", "w-2"), (a.name, b.name)
    Controller(sub, vars_, objects, wall=wall).assign("w-1", ["c1"])
    assert a.reconcile_once() == ["c1"] and a.epochs == {"c1": 1} and a.may_act("c1")
    assert b.take_epoch("c1") == 2
    assert a.renew_leases() == ["c1"] and not a.may_act("c1")


def _piece_controller():
    """The controller from the spec: rows are refused and taken by the spec's fields, placed on the workers that
    heartbeat, and each worker holds what it was given."""
    from w2cplatform.spec import Refused, SpecController, SubsystemSpec
    root, vars_, objects, clock, wall = _testsub_box()
    spec = SubsystemSpec.load(TESTSUB)
    assert spec.name == "testsub" and spec.rows == "counters" and spec.capacity_default == 4
    ctl = SpecController(spec, vars_.as_writer("testsubcontroller", spec.acl_controller()), objects, wall=wall)
    con = SpecController(spec, vars_.as_writer("console", spec.acl_console()), objects, wall=wall)   # rows are the console's
    ws = [_counter_worker(spec.sub, vars_, objects, clock, wall, f"I{i}", f"srv-{i}") for i in (1, 2)]
    for w in ws:
        w.reconcile_once()
    for name in ("c1", "c2", "c3"):
        con.create({"name": name})
    try:
        con.create({"start": 3})
        raise AssertionError("a row without its required name was taken")
    except Refused:
        pass
    ctl.ensure_placed()
    held = {u: w.name for w in ws for u in w.reconcile_once()}
    assert sorted(held) == ["c1", "c2", "c3"] and len(set(held.values())) == 2, held
    assert all(w.epochs and all(w.may_act(u) for u in w.epochs) for w in ws)


def _http(base: str, method: str, path: str, body=None) -> tuple[int, object]:
    import json
    import urllib.error
    import urllib.request
    _http.n = getattr(_http, "n", 0) + 1
    req = urllib.request.Request(base + path, method=method, headers={"Idempotency-Key": f"k-{_http.n}"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def _testsub_console(root, vars_, objects, wall, index=None):
    from w2cplatform.console import SpecConsole
    from w2cplatform.spec import SpecController, SubsystemSpec
    spec = SubsystemSpec.load(TESTSUB)
    ctl = SpecController(spec, vars_.as_writer("console", spec.acl_console()), objects, wall=wall)
    con = SpecConsole(ctl, marks_root=os.path.join(root, "events"), index=index, wall=wall)
    srv = con.serve("127.0.0.1", 0)
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _piece_console():
    """The console over the spec: `/spec` describes testsub, a unit is created through the door and listed."""
    import json
    root, vars_, objects, clock, wall = _testsub_box()
    srv, base = _testsub_console(root, vars_, objects, wall)
    try:
        st, spec = _http(base, "GET", "/spec")
        assert st == 200 and spec["name"] == "testsub", (st, spec)
        st, made = _http(base, "POST", "/counters", {"name": "c1", "start": 2})
        assert st in (200, 201), (st, made)
        st, listed = _http(base, "GET", "/counters")
        assert st == 200 and "c1" in json.dumps(listed), (st, listed)
    finally:
        srv.shutdown(); srv.server_close()


def _piece_events():
    """A unit is `<sub>/<id>` wherever the platform names one (§2.1, step 2): testsub's counter is asked for by
    `/events?unit=testsub/c1`, an operator's mark on it is `POST /marks {"unit": "testsub/c1"}`, both answer under
    that one string, and a bare id is refused — the platform has no unit that is a number of somebody's."""
    from w2cplatform.eventdatabase import EventIndex
    from w2cplatform.events import EventLog
    root, vars_, objects, clock, wall = _testsub_box()
    tree = os.path.join(root, "events")
    EventLog(tree, "testsub", "c1", 1).append(wall() - 10, "counted", n=3)
    EventLog(tree, "testsub", "c2", 1).append(wall() - 9, "counted", n=4)
    srv, base = _testsub_console(root, vars_, objects, wall, index=EventIndex(tree, "srv-1", wall))
    try:
        st, out = _http(base, "POST", "/marks", {"unit": "testsub/c1", "note": "look"})
        ok = st == 201
        st, out = _http(base, "GET", "/events?unit=testsub/c1")
        rows = out.get("events", []) if st == 200 and isinstance(out, dict) else []
        # its own line under its own name, and the mark — the console's unit's line — about it; nothing of c2's
        whose = sorted((e.get("kind"), e.get("unit") if e.get("kind") == "counted" else e.get("of")) for e in rows)
        ok = ok and whose == [("counted", "testsub/c1"), ("mark", "testsub/c1")]
        ok = ok and _http(base, "GET", "/events?unit=c1")[0] == 400
        ok = ok and _http(base, "POST", "/marks", {"unit": "c1", "note": "look"})[0] == 400
    finally:
        srv.shutdown(); srv.server_close()
    if not ok:
        print("BOUNDARY-RUN no-unit-refs")
        raise SystemExit(3)


def _piece_resource():
    """The resource over a tree where only testsub wrote: it finds the subsystem's buckets and answers its events."""
    from w2cplatform.eventdatabase import EventIndex
    from w2cplatform.events import EventLog
    from w2cplatform.resource import Resource
    root, vars_, objects, clock, wall = _testsub_box()
    tree = os.path.join(root, "events")
    EventLog(tree, "testsub", "c1", 1).append(wall() - 10, "counted", n=3)
    res = Resource(tree, "srv-1", "", vars_, objects, wall=wall)
    res.index = EventIndex(tree, "srv-1", wall)          # what a host gives its resource (`host` below: none yet)
    res.heartbeat()
    got = res.index.query(0, 1e12)["events"]
    assert [(e["subsystem"], e["kind"], e["n"]) for e in got] == [("testsub", "counted", 3)], got


def _piece_host():
    """The platform's entry point (`python3 -m w2cplatform`, `host.py`, step 5) loads a directory of specs (`SPEC_DIR`,
    §2.3) and runs the platform's processes for whatever it finds there: told nothing it refuses to start, and
    `controller testsub` — the loop a unit runs, one pass of it — places testsub's counters on the workers that
    heartbeat, from the spec alone."""
    import time
    path = os.path.join(ROOT, PLATFORM_TREE, "__main__.py")
    if not os.path.exists(path) or "SPEC_DIR" not in open(path, encoding="utf-8").read():
        print("BOUNDARY-RUN no-spec-dir")
        raise SystemExit(3)
    from w2cplatform import host
    from w2cplatform.contract import Subsystem
    from w2cplatform.spec import SpecController, SubsystemSpec
    root = tempfile.mkdtemp(prefix="testsub-host-")
    env = {"SPEC_DIR": os.path.dirname(TESTSUB), "PLATFORM_DIR": root}
    assert host.main(["controller", "testsub"], {"PLATFORM_DIR": root}) == 2          # no SPEC_DIR: nothing runs
    vars_, objects = host.box_stores(env)
    ws = [_counter_worker(Subsystem("testsub"), vars_, objects, time.monotonic, time.time, f"I{i}", f"srv-{i}")
          for i in (1, 2)]
    for w in ws:
        w.reconcile_once()
    spec = SubsystemSpec.load(TESTSUB)
    con = SpecController(spec, vars_.as_writer("console", spec.acl_console()), objects)
    for name in ("c1", "c2", "c3"):
        con.create({"name": name})
    host.stop.clear()
    host.stop.wait = lambda timeout=None: host.stop.set() or True                     # one pass, then the loop ends
    assert host.main(["controller", "testsub"], env) == 0
    held = {u: w.name for w in ws for u in w.reconcile_once()}
    assert sorted(held) == ["c1", "c2", "c3"] and len(set(held.values())) == 2, held
    assert json_loads(objects.get("testsub/controller/pass")) is not None              # the report `/metrics` reads


def json_loads(raw):
    import json
    return json.loads(raw) if raw else None


def run_piece(name: str) -> str | None:
    """Run one piece in a guarded process; None when it came up, else why not."""
    code = _GUARD + f"import tests.test_boundary as b; b._piece_{name}()"
    env = {**os.environ, "PYTHONPATH": ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")}
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    if p.returncode == 0:
        return None
    err = p.stdout + p.stderr
    m = re.findall(r"BOUNDARY-IMPORT (\w+)", err)
    if m:
        return f"import {m[-1]}"
    m = re.findall(r"BOUNDARY-RUN (\S+)", err)
    if m:
        return m[-1]
    last = [l for l in err.strip().splitlines() if l.strip()]
    return "broken: " + (last[-1].strip() if last else f"exit {p.returncode}")


def run_findings() -> list[tuple[str, int, str, str]]:
    out = []
    for name in PIECES:
        why = run_piece(name)
        if why is not None:
            out.append((f"run:{name}", 0, f"run {why}", "-"))
    return out


# -- the debt ----------------------------------------------------------------------------------------------------------

_DEBT_LINE = re.compile(r"^\s*([2-8])\s*\|\s*(\S+?)(?::(\d+))?\s*\|\s*(.+?)\s*\|\s*(\S+)\s*$")


def read_debt(path: str = DEBT) -> tuple[list[str], list[tuple[int, str, int, str, str]]]:
    """The debt's header (comments) and its lines `(step, file, line, what, fingerprint)`."""
    if not os.path.exists(path):
        return [], []
    head, lines = [], []
    for i, raw in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            if not lines:
                head.append(raw)
            continue
        m = _DEBT_LINE.match(raw)
        assert m, f"{path}:{i}: a debt line is `<step 2…8> | <file>:<line> | <what> | <fingerprint>`: {raw!r}"
        lines.append((int(m.group(1)), m.group(2), int(m.group(3) or 0), m.group(4), m.group(5)))
    while head and not head[-1].strip():
        head.pop()
    return head, lines


def compare(found, debt) -> tuple[list[str], list[str]]:
    """What is new (found more often than the debt owes) and what is no longer true (found less often)."""
    have = Counter((f, w) for f, _, w, _ in found)
    owed = Counter((f, w) for _, f, _, w, _ in debt)
    where = defaultdict(list)
    for f, ln, w, _ in found:
        where[(f, w)].append(ln)
    fresh = [f"{f}:{','.join(map(str, where[(f, w)][:8]))} | {w} — {n} found, the debt owes {owed[(f, w)]}"
             for (f, w), n in sorted(have.items()) if n > owed[(f, w)]]
    stale = [f"{f} | {w} — the debt owes {n}, {have[(f, w)]} found"
             for (f, w), n in sorted(owed.items()) if n > have[(f, w)]]
    return fresh, stale


def shrink(found, head, debt, path: str = DEBT) -> None:
    """Rewrite the debt from what is found: lower counts only — nothing new, nothing raised (the caller checked).
    Each line keeps its step: the old line with the same fingerprint, else the nearest old line of the same file and
    word."""
    pool = defaultdict(list)
    for step, f, ln, w, fp in debt:
        pool[(f, w)].append([step, ln, fp])
    out = []
    for f, ln, w, fp in sorted(found, key=lambda x: (x[0], x[1], x[2])):
        cands = pool[(f, w)]
        same = [c for c in cands if c[2] == fp]
        pick = min(same or cands, key=lambda c: abs(c[1] - ln))
        cands.remove(pick)
        out.append(f"{pick[0]} | {f}:{ln} | {w} | {fp}" if ln else f"{pick[0]} | {f} | {w} | {fp}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(head).rstrip("\n") + "\n\n" + "\n".join(out) + "\n")


def totals(lines) -> dict[str, int]:
    """Counts by part: words, imports, runs — and by step."""
    out = Counter()
    for item in lines:
        what = item[3] if len(item) == 5 else item[2]
        part = "imports" if what.startswith("import ") else "runs" if what.startswith("run ") else "words"
        out[part] += 1
        if len(item) == 5 and isinstance(item[0], int):
            out[f"step {item[0]}"] += 1
    return dict(out)


def everything():
    return word_findings() + import_findings() + run_findings()


# -- the tests -------------------------------------------------------------------------------------------------------

def test_the_platform_crosses_the_boundary_nowhere_but_where_the_debt_says_and_the_debt_only_shrinks():
    """Imports, words and runs against `boundary_debt.txt`: anything new fails, and so does any line of the debt that
    is no longer true. `W2C_BOUNDARY_SHRINK=1` writes the lower debt down instead of failing on it."""
    found = everything()
    head, debt = read_debt()
    fresh, stale = compare(found, debt)
    print(f"  boundary: found {totals(found)}; the debt owes {totals(debt)}")
    if os.environ.get("W2C_BOUNDARY_SHRINK") and not fresh:
        shrink(found, head, debt)                       # lower counts, renumbered lines: never a new one
        stale = []
    problems = []
    if fresh:
        problems.append(f"{len(fresh)} new — the platform crossed the boundary (not in {os.path.basename(DEBT)}, or "
                        "more often than it owes):\n  " + "\n  ".join(fresh))
    if stale:
        problems.append(f"{len(stale)} lines of the debt are no longer true — the debt went down; write it down "
                        "(W2C_BOUNDARY_SHRINK=1):\n  " + "\n  ".join(stale))
    assert not problems, "\n".join(problems)


def test_the_dictionary_reads_words_and_identifiers_and_not_substrings():
    """The dictionary on the examples the architect ruled on (the product's `TestBoundaryDictionary`), and the
    course's own: Python identifiers, the page's JS, Russian prose."""
    cases = {
        "the worker is alive; receive, recover, automatic, deliver, a record, records": {},
        "a short-lived lease, recorded in the row": {},
        "cam_id = row.camera_id  # the vms_cam": {"cam": 2, "camera": 1, "vms": 1},
        "near: {sub: rec, by: cam}; the rec controller; rec/recordings/7": {"rec": 3, "cam": 1, "recording": 1},
        "recworker, vmsconsole, livefeed, rec/volumeseen/*": {"rec": 2, "vms": 1, "live": 1, "volume": 1},
        "N workers live · a live server · workers_live": {},
        "the live gateway's door; LIVE_NAME; live_url": {"live": 3},
        "a volume of the resource, place_by: volume": {},
        "a recorder's volume": {"recorder": 1, "volume": 1},
        "its resource (`live`, `silent`); d.state === 'live'; 'live: waiting'": {"live": 1},
        "overflow:auto; margin:0 auto; auto/scenarios": {"auto": 1},
        '<meta name="viewport" content="width=device-width">': {},
        "Камеры и записи с камеры; видеоархив; устройства": {"камер": 2, "запис": 1, "видео": 1, "устройств": 1},
        "запись прошла мимо заморозки": {},
        "the det tree, a detector, two detectors": {"det": 3},
        "it detects a conflict; detection of a fork; Detected": {},
        "auto/scenarios and the automation subsystem; automatic, automatically": {"auto": 2},
        "PTZ, a codec; H264 and h265 in an MP4 at 25 fps, the bitrate": {"ptz": 1, "codec": 1, "h264": 1, "h265": 1,
                                                                         "mp4": 1, "fps": 1, "bitrate": 1},
        "gst: h264parse ! mp4mux; fmp4.Writer": {"h264": 1, "mp4": 1},
        "an ONVIF NVR: XMeye, Hikvision, Dahua; fmp4 is not mp4": {"onvif": 1, "nvr": 1, "xmeye": 1, "hikvision": 1,
                                                                   "dahua": 1, "mp4": 1},
        "def holdsCamera(self): return self.archiveRoot  # the obsd client": {"camera": 1, "archive": 1, "obsd": 1},
        "the stream of lines; a streaming reply; a DriverPack source": {"driverpack": 1},
        "log.warning('%s: footage of camera %s', sub, unit)": {"footage": 1, "camera": 1},
        "fetch(`/events?cam=${id}`)": {"cam": 1},
    }
    for line, want in cases.items():
        got = dict(words_in(line))
        assert got == want, (line, got, want)


def test_the_debt_lines_are_well_formed_and_name_a_step_of_the_plan():
    """Every line of the debt names its step (2…8) and a file of the platform's tree, its tests, or a piece."""
    head, debt = read_debt()
    assert head and head[0].startswith("#"), "the debt starts with what it is"
    known = set(platform_files())
    for step, f, ln, what, fp in debt:
        assert 2 <= step <= 8
        assert f in known or f.startswith("run:"), f
        assert (what.startswith(("import ", "run ")) or any(what == w for w, _ in PRODUCT_WORDS)), what


def test_the_debt_is_compared_by_count_and_a_shrink_only_lowers_it():
    """A moved or edited line is the same debt; one more of a word in a file is new; one less is a line no longer
    true. The shrink renumbers, drops what went, keeps each line's step — and is never asked when anything is new."""
    debt = [(2, "w2cplatform/a.py", 10, "cam", "aaaa0000"), (2, "w2cplatform/a.py", 20, "cam", "bbbb0000"),
            (6, "w2cplatform/a.py", 30, "volume", "cccc0000")]
    moved = [("w2cplatform/a.py", 12, "cam", "aaaa0000"), ("w2cplatform/a.py", 25, "cam", "dddd0000"),
             ("w2cplatform/a.py", 31, "volume", "cccc0000")]
    assert compare(moved, debt) == ([], [])                                   # moved, edited: the same counts
    fresh, stale = compare(moved + [("w2cplatform/b.py", 1, "camera", "eeee0000")], debt)
    assert len(fresh) == 1 and "b.py:1 | camera" in fresh[0] and stale == []
    fresh, stale = compare(moved[1:], debt)
    assert fresh == [] and len(stale) == 1 and "a.py | cam" in stale[0]
    path = os.path.join(tempfile.mkdtemp(prefix="boundary-"), "debt.txt")
    shrink(moved[1:], ["# the debt"], debt, path)
    head, again = read_debt(path)
    assert head == ["# the debt"] and again == [(2, "w2cplatform/a.py", 25, "cam", "dddd0000"),
                                                (6, "w2cplatform/a.py", 31, "volume", "cccc0000")]


def test_the_testsub_spec_is_nobodys_but_the_platforms():
    """`testsub.subsystem.yaml` has nothing of the product in it, and the platform reads it as it reads any spec."""
    from w2cplatform.spec import SubsystemSpec
    text = open(TESTSUB, encoding="utf-8").read()
    assert not any(words_in(line) for line in text.splitlines())
    spec = SubsystemSpec.load(TESTSUB)
    assert spec.name == "testsub" and set(spec.fields) >= {"name", "start", "labels"}


def _main(argv):
    if argv[:1] == ["--shrink"]:
        os.environ["W2C_BOUNDARY_SHRINK"] = "1"
        test_the_platform_crosses_the_boundary_nowhere_but_where_the_debt_says_and_the_debt_only_shrinks()
        print("the debt is what is found")
        return 0
    if argv[:1] == ["--show"]:                          # where a count comes from: --show <file> [word]
        for f, ln, w, fp in everything():
            if f == argv[1] and (len(argv) < 3 or w == argv[2]):
                print(f"{f}:{ln} | {w} | {fp}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    sys.exit(_main(sys.argv[1:]))
