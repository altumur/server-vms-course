"""probe_spec_loaders.py — BOTH trees (ADR-0012 strict loader, ADR-0019 one YAML): the same mutated specs are fed to
the course's loader (`SubsystemSpec.load`, PyYAML) and the product's (`w2cplatform.LoadSpec`, probes/go/specload), and
their verdicts compared. Expected: every case the same verdict on both sides (ACCEPT/REFUSE), and every case marked
`must=REFUSE` refused by both. A row `DIFFER` or `MISSED` is a finding.
Usage: python probe_spec_loaders.py <course root> <product root> <specload binary> [workdir]"""
import os, subprocess, sys, tempfile, time

course, product, specload = sys.argv[1], sys.argv[2], sys.argv[3]
work = sys.argv[4] if len(sys.argv) > 4 else tempfile.mkdtemp(prefix="specprobe-")
os.makedirs(work, exist_ok=True)
PY = sys.executable

BASE = """name: probe
unit:
  rows: counters
  id: name
  fields:
    name:   {type: string, required: true}
    start:  {type: int,    default: 0}
    kind:   {type: string, enum: [a, b], default: a}
    labels: {type: list}
placement:
  capacity:   {from: capacity, default: 4}
  headroom:   {from: headroom}
  constraint: labels-subset
  tie_break:  most-free-capacity
requests:
  schema:
    type: object
    required: [unit, add]
    additionalProperties: false
    properties: {unit: {type: string}, add: {type: integer}, valid_until: {type: number}}
  valid_for: 30
  most_valid: 600
snapshot: [name, start]
display:
  unit: counter
  units: counters
  fields: {name: Name, start: Start}
  options:
    kind: {a: Alpha, b: Beta}
  form:
    - title: Main
      fields: [name, start, kind]
      status:
        - {field: seen, title: Seen}
LEASE
"""

def spec(lease="lease: {unconfirmed_max: off}", **repl):
    t = BASE.replace("LEASE", lease)
    for a, b in repl.items():
        a = a.replace("__", " ")
    return t

def sub(old, new, lease="lease: {unconfirmed_max: off}"):
    t = BASE.replace("LEASE", lease)
    assert old in t, old
    return t.replace(old, new, 1)

def big(mb):                                    # a spec of `mb` megabytes: display.kinds words (free on both sides)
    n = mb * 1024 * 1024 // 40
    words = "".join(f"    k{i:07d}: a word of the kind number {i:07d}\n" for i in range(n))
    return BASE.replace("LEASE", "lease: {unconfirmed_max: off}") + "  kinds:\n" if False else \
        sub("  unit: counter\n", "  unit: counter\n  kinds:\n" + words)

def deep_flow(n):                               # requests.schema nested n deep in one flow line (opaque/free on both)
    return sub("    properties: {unit: {type: string}, add: {type: integer}, valid_until: {type: number}}",
               "    properties: {unit: {type: string}, add: {type: integer}, valid_until: {type: number}, x: " + "{a: " * n + "1" + "}" * n + "}")

def deep_block(n):                              # requests.schema nested n deep as block mappings
    lines = "".join("  " * (i + 3) + "a:\n" for i in range(n)) + "  " * (n + 3) + "b: 1\n"
    return sub("    additionalProperties: false\n", "    additionalProperties: false\n    deep:\n" + lines)

CASES = [
    # (name, text or bytes, must)  must: REFUSE = ADR-0012 says refused; ACCEPT = must load; "" = both must only agree
    ("base", spec(), "ACCEPT"),
    ("unknown_depth1", spec() + "bogus: 1\n", "REFUSE"),
    ("unknown_depth2", sub("  tie_break:  most-free-capacity\n", "  tie_break:  most-free-capacity\n  fallbak: 1\n"), "REFUSE"),
    ("unknown_depth3", sub("{from: capacity, default: 4}", "{from: capacity, default: 4, fallbak: 1}"), "REFUSE"),
    ("unknown_depth4", sub("{type: string, required: true}", "{type: string, required: true, requried: true}"), "REFUSE"),
    ("unknown_in_lease", spec("lease: {unconfirmed_max: off, grace: 5}"), "REFUSE"),
    ("display_unknown_section", sub("  unit: counter\n", "  unit: counter\n  colour: red\n"), "REFUSE"),
    ("display_field_not_in_fields", sub("{name: Name, start: Start}", "{name: Name, start: Start, nosuch: X}"), "REFUSE"),
    ("display_field_help_not_in_fields", sub("  unit: counter\n", "  unit: counter\n  field_help: {nosuch: help}\n"), "REFUSE"),
    ("display_fields_platform_key_age", sub("{name: Name, start: Start}", "{name: Name, start: Start, age: Age}"), ""),
    ("display_fields_platform_key_epoch", sub("{name: Name, start: Start}", "{name: Name, start: Start, epoch: Epoch}"), ""),
    ("display_fields_status_field", sub("{name: Name, start: Start}", "{name: Name, start: Start, seen: Seen}"), "ACCEPT"),
    ("display_fields_nested_map", sub("{name: Name, start: Start}", "{name: Name, start: {x: 1}}"), "REFUSE"),
    ("display_options_not_in_enum", sub("{a: Alpha, b: Beta}", "{a: Alpha, b: Beta, c: Gamma}"), "REFUSE"),
    ("display_options_field_without_enum", sub("    kind: {a: Alpha, b: Beta}\n", "    kind: {a: Alpha, b: Beta}\n    start: {0: zero}\n"), "REFUSE"),
    ("display_options_not_a_field", sub("    kind: {a: Alpha, b: Beta}\n", "    kind: {a: Alpha, b: Beta}\n    nosuch: {x: X}\n"), "REFUSE"),
    ("display_options_platform_key_server", sub("    kind: {a: Alpha, b: Beta}\n", "    kind: {a: Alpha, b: Beta}\n    server: {s1: One}\n"), ""),
    ("display_options_status_field", sub("    kind: {a: Alpha, b: Beta}\n", "    kind: {a: Alpha, b: Beta}\n    seen: {x: X}\n"), "ACCEPT"),
    ("display_form_fields_status_field", sub("fields: [name, start, kind]", "fields: [name, start, kind, seen]"), ""),
    ("display_form_fields_unknown", sub("fields: [name, start, kind]", "fields: [name, start, kind, nosuch]"), "REFUSE"),
    ("display_form_unknown_key", sub("    - title: Main\n", "    - title: Main\n      colour: red\n"), "REFUSE"),
    ("display_tree_word_remove", sub("  unit: counter\n", "  unit: counter\n  tree: {group_by: kind, remove: Remove}\n"), ""),
    ("display_tree_group_by_unknown", sub("  unit: counter\n", "  unit: counter\n  tree: {group_by: nosuch}\n"), "REFUSE"),
    ("display_tree_column_unknown", sub("  unit: counter\n", "  unit: counter\n  tree: {columns: [{field: nosuch, title: X}]}\n"), "REFUSE"),
    ("display_word_not_string", sub("  unit: counter\n", "  unit: {x: 1}\n"), "REFUSE"),
    ("requests_unknown_stamp", sub("  valid_for: 30\n", "  valid_for: 30\n  stamp: [by, who]\n"), "REFUSE"),
    ("requests_unknown_key", sub("  valid_for: 30\n", "  valid_for: 30\n  vaild_for: 30\n"), "REFUSE"),
    ("worker_requests_unknown_sub", spec() + "worker: {requests: [nosuchsub]}\n", ""),
    ("lease_minus1", spec("lease: {unconfirmed_max: -1}"), "REFUSE"),
    ("lease_forever_quoted", spec('lease: {unconfirmed_max: "forever"}'), "ACCEPT"),
    ("lease_forever", spec("lease: {unconfirmed_max: forever}"), "ACCEPT"),
    ("lease_zero", spec("lease: {unconfirmed_max: 0}"), "REFUSE"),
    ("lease_1e308", spec("lease: {unconfirmed_max: 1e308}"), ""),
    ("lease_1.0e308", spec("lease: {unconfirmed_max: 1.0e+308}"), ""),
    ("lease_inf", spec("lease: {unconfirmed_max: inf}"), "REFUSE"),
    ("lease_Infinity", spec("lease: {unconfirmed_max: Infinity}"), "REFUSE"),
    ("lease_.inf", spec("lease: {unconfirmed_max: .inf}"), "REFUSE"),
    ("lease_nan", spec("lease: {unconfirmed_max: nan}"), "REFUSE"),
    ("lease_true", spec("lease: {unconfirmed_max: true}"), "REFUSE"),
    ("lease_false", spec("lease: {unconfirmed_max: false}"), ""),
    ("lease_no", spec("lease: {unconfirmed_max: no}"), ""),
    ("lease_OFF", spec("lease: {unconfirmed_max: OFF}"), ""),
    ("lease_90_quoted", spec('lease: {unconfirmed_max: "90"}'), "REFUSE"),
    ("lease_90s", spec("lease: {unconfirmed_max: 90s}"), "REFUSE"),
    ("lease_90", spec("lease: {unconfirmed_max: 90}"), "ACCEPT"),
    ("lease_hex_0x10", spec("lease: {unconfirmed_max: 0x10}"), ""),
    ("lease_1_000", spec("lease: {unconfirmed_max: 1_000}"), ""),
    ("lease_huge_int", spec("lease: {unconfirmed_max: 99999999999999999999999}"), ""),
    ("lease_null", spec("lease:"), ""),
    ("lease_empty_map", spec("lease: {}"), "REFUSE"),
    ("lease_absent", spec(""), "ACCEPT"),
    ("dup_top_key_name", spec() + "name: other\n", "REFUSE"),
    ("dup_key_lease_value", spec("lease: {unconfirmed_max: off}\nlease: {unconfirmed_max: forever}"), "REFUSE"),
    ("dup_key_in_flow_map", spec("lease: {unconfirmed_max: off, unconfirmed_max: forever}"), "REFUSE"),
    ("dup_block_hides_unknown", sub("placement:\n", "placement:\n  fallbak: 1\nplacement:\n", ) , "REFUSE"),
    ("anchor_alias_display_keys", sub("  fields: {name: Name, start: Start}\n", "  fields: &f {name: Name, start: Start}\n  field_help: *f\n"), ""),
    ("anchor_merge_key", sub("  headroom:   {from: headroom}\n", "  headroom:   &h {from: headroom}\n  capacity2: {<<: *h}\n"), "REFUSE"),
    ("block_scalar_hides_tail", sub("  unit: counter\n", "  unit: |\n    counter\n    of things\n") + "bogus_after: 1\n", "REFUSE"),
    ("block_scalar_hides_lease", sub("  unit: counter\n", "  unit: >\n    counter\n", lease="") + "lease: {unconfirmed_max: forever}\n", ""),
    ("overindent_hides_tail", sub("    labels: {type: list}\n", "    labels: {type: list}\n       stray: 1\n") + "bogus_after: 1\n", "REFUSE"),
    ("multiline_plain_scalar", sub("  unit: counter\n", "  unit: counter\n    of things\n") + "bogus_after: 1\n", "REFUSE"),
    ("tab_indent", sub("  headroom:   {from: headroom}\n", "\theadroom:   {from: headroom}\n"), ""),
    ("non_utf8_in_word", sub("  unit: counter\n", "  unit: count\xffer\n").encode("latin-1"), ""),
    ("non_utf8_in_comment", (spec() + "# \xff\xfe comment\n").encode("latin-1"), ""),
    ("bom_utf8", b"\xef\xbb\xbf" + spec().encode(), ""),
    ("nul_byte_in_word", sub("  unit: counter\n", "  unit: count\x00er\n"), ""),
    ("deep_flow_200", deep_flow(200), ""),
    ("deep_flow_5000", deep_flow(5000), ""),
    ("deep_block_500", deep_block(500), ""),
    ("size_10mb", big(10), ""),
    ("yaml_list_toplevel", "- a\n- b\n", "REFUSE"),
    ("yaml_two_documents", spec() + "---\nname: second\n", ""),
    ("json_default_map", sub("    labels: {type: list}\n", "    labels: {type: list}\n    doc: {type: json, default: {a: 1}}\n"), "ACCEPT"),
    ("inherit_map", sub("    labels: {type: list}\n", "    labels: {type: list}\n    doc: {type: json, inherit: {a: 1}}\n"), ""),
    ("display_kinds_nested", sub("  unit: counter\n", "  unit: counter\n  kinds: {motion: {x: 1}}\n"), ""),
    ("display_actions_nested", sub("  unit: counter\n", "  unit: counter\n  actions: {pulse: {x: 1}}\n"), ""),
    ("display_options_bool_enum", sub("    kind:   {type: string, enum: [a, b], default: a}", "    kind:   {type: string, enum: [a, b], default: a}\n    flag:   {type: bool, enum: [true, false]}").replace("    kind: {a: Alpha, b: Beta}\n", "    kind: {a: Alpha, b: Beta}\n    flag: {true: \"Yes\", false: \"No\"}\n"), ""),
    ("display_word_On_Off_unquoted", sub("    kind: {a: Alpha, b: Beta}", "    kind: {a: On, b: Off}"), ""),
    ("display_options_yes_key", sub("    kind:   {type: string, enum: [a, b], default: a}", "    kind:   {type: string, enum: [a, b, yes], default: a}").replace("    kind: {a: Alpha, b: Beta}\n", "    kind: {a: Alpha, b: Beta, yes: Yes}\n"), ""),
    ("snapshot_unknown_field", sub("snapshot: [name, start]", "snapshot: [name, nosuch]"), "REFUSE"),
    ("spread_by_unknown_field", sub("  tie_break:  most-free-capacity\n", "  tie_break:  most-free-capacity\n  spread_by: nosuch\n"), "REFUSE"),
    ("group_by_unknown_field", sub("  tie_break:  most-free-capacity\n", "  tie_break:  most-free-capacity\n  group_by: nosuch\n"), "REFUSE"),
    ("retire_when_unknown_field", sub("  tie_break:  most-free-capacity\n", "  tie_break:  most-free-capacity\n  retire_when: {field: nosuch, in: [x]}\n"), "REFUSE"),
    ("requests_key_unknown_field", sub("  valid_for: 30\n", "  valid_for: 30\n  key: \"{nosuch}\"\n"), "REFUSE"),
    ("enum_default_not_in_enum", sub("enum: [a, b], default: a}", "enum: [a, b], default: c}"), "REFUSE"),
    ("requests_key_stray_brace", sub("  valid_for: 30\n", "  valid_for: 30\n  key: \"x-{unit\"\n"), "REFUSE"),
    ("requests_stamp_group_without_group_by", sub("  valid_for: 30\n", "  valid_for: 30\n  stamp: [group]\n"), "REFUSE"),
    ("spread_by_not_string", sub("  tie_break:  most-free-capacity\n", "  tie_break:  most-free-capacity\n  spread_by: 5\n"), "REFUSE"),
    ("key_true_yaml11", spec() + "on: 1\n", "REFUSE"),
]

COURSE_ONE = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
sys.setrecursionlimit(10000)
t0 = time.time()
try:
    from w2cplatform.spec import SubsystemSpec
    s = SubsystemSpec.load(sys.argv[2])
    print(f"ACCEPT\tname={s.name} unconfirmed_max={s.unconfirmed_max}\t{time.time()-t0:.2f}s")
except ValueError as e:
    print(f"REFUSE\t{str(e)[:160]}\t{time.time()-t0:.2f}s".replace("\n", " "))
except BaseException as e:
    print(f"CRASH\t{type(e).__name__}: {str(e)[:120]}\t{time.time()-t0:.2f}s".replace("\n", " "))
"""

def run_course(path):
    try:
        r = subprocess.run([PY, "-c", COURSE_ONE, os.path.join(course, "Source"), path], capture_output=True, text=True,
                           timeout=90, cwd=os.path.join(course, "Source"))
        return (r.stdout.strip() or "CRASH\t" + r.stderr.strip()[-160:]).split("\t")
    except subprocess.TimeoutExpired:
        return ["HANG", ">90s", ""]

def verdict(v):                                 # CRASH of a ValueError's cousin is still a refusal of the load
    return "REFUSE" if v in ("REFUSE", "CRASH", "PANIC") else v

paths = []
for name, text, must in CASES:
    p = os.path.join(work, f"{name}.subsystem.yaml")
    with open(p, "wb") as f:
        f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
    paths.append(p)
go = {}
try:
    r = subprocess.run([specload, *paths], capture_output=True, text=True, timeout=600, errors="replace")
    for ln in r.stdout.splitlines():
        f, rest = ln.split("\t", 1)
        go[f] = rest.split("\t")
except subprocess.TimeoutExpired:
    pass
bad = 0
for (name, _, must), p in zip(CASES, paths):
    c = run_course(p)
    g = go.get(p, ["HANG", "no answer (whole run timed out)", ""])
    cv, gv = verdict(c[0]), verdict(g[0])
    flag = "ok"
    if cv != gv:
        flag = "DIFFER"
    elif must and cv != must:
        flag = "MISSED"
    bad += flag != "ok"
    print(f"{flag:6} {name:36} course={c[0]:6} product={g[0]:6}")
    if flag != "ok" or c[0] in ("CRASH", "HANG") or g[0] in ("PANIC", "HANG"):
        print(f"         course:  {' | '.join(c[1:])}\n         product: {' | '.join(g[1:])}")
print(f"{len(CASES)} cases, {bad} differ or missed")
