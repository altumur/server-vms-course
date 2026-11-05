#!/usr/bin/env python3
"""Compare static as-built snapshots of one lesson with its specification (ADR-0123).

The specification is read from the export repository at the pin named in the
snapshot header (ADR-0123 доп. (1) п. 3), never from the working tree:

  params    the table «Флаги демона» / «Daemon flags» of the lesson norms
            (by flag name), environment names in the norms prose, `#lim`
            forms of the lesson data when the pin has them;
  refusals  the Н4 tables of every chapter of the lesson and the lesson
            OpenAPI (code + kind pairs, body fields, quoted words).

`deps` has no machine pair yet (доп. (1) п. 1): it is reference only.

Outcomes — a closed list of six (ADR-0123 доп. (2) п. 2); any other value is
a schema error:
  match         built as specified;
  extra         built, not in the specification;
  absent        static snapshot: in the specification, not found in code;
  unobserved    run snapshot: in the specification, not met although the run
                executed a step that checks it (the run passport names them);
  differs       the value or code differs;
  out_of_scope  no applicable scope or pair for this fact in this snapshot
                (also a norm whose checking step the run did not execute);
                not a negative result of the comparison.
A row whose pairing is a heuristic carries fuzzy=1.

Writes compare.tsv and compare.md next to the snapshots.

Usage: compare.py --snap tools/asbuilt/out/<impl>/<lesson> --spec-repo <export repo> [--impl-root <root>]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import yamlio  # noqa: E402
from asbuilt import check_leaks, mask  # noqa: E402

COLUMNS = ["snapshot", "unit", "status", "fuzzy", "spec_ref", "spec", "code_ref", "code", "note"]
STATUSES = ["match", "extra", "absent", "unobserved", "differs", "out_of_scope"]
# Outcomes that count against the build; out_of_scope is not one of them.
NEGATIVE = ("extra", "absent", "unobserved", "differs")
BASE_KINDS = {"badrequest", "badkey", "forbidden", "toolarge", "notfound", "refused", "unavailable",
              "conflict", "expired", "early", "guard", "ambiguous"}
CELL_SPLIT = re.compile(r"(?<!\\)\|")
BACKTICK = re.compile(r"`([^`]+)`")
FLAG_TOKEN = re.compile(r"(?<![\w-])--?([a-z][a-z0-9-]*)")


class Spec:
    """Pinned lesson specification read with `git show <pin>:<path>`."""

    def __init__(self, repo, pin, lesson):
        self.repo, self.pin, self.lesson = repo, pin, lesson
        base = "Platform/%s" % lesson
        names = self.git("ls-tree", "-r", "--name-only", pin, base).split("\n")
        self.files = sorted(n for n in names if n)
        self.norms = {f: self.show(f) for f in self.files if f.startswith(base + "/spec/") and f.endswith(".norms.md")}
        api = [f for f in self.files if f.startswith(base + "/spec/") and f.endswith(".openapi.yaml")]
        self.openapi_path = api[0] if api else None
        self.openapi = self.show(api[0]) if api else ""
        self.lim_files = [f for f in self.files if f.startswith(base + "/data/") and f.endswith(".tsv")
                          and "#lim" in self.show(f)]

    def git(self, *args):
        p = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            raise RuntimeError("git %s: %s" % (" ".join(args[:2]), p.stderr.strip()))
        return p.stdout

    def show(self, path):
        return self.git("show", "%s:%s" % (self.pin, path))

    @property
    def prose(self):
        return "\n".join(self.norms[f] for f in sorted(self.norms))


def chapter_of(path):
    m = re.search(r"/(\d\d(?:\.\d+)?)-[^/]*\.norms(?:\.en)?\.md$", path)
    return "P/" + m.group(1) if m else path


def cells(line):
    parts = [c.strip() for c in CELL_SPLIT.split(line.strip())]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return [p.replace("\\|", "|") for p in parts]


def tables(text):
    """Yield (section, header cells, rows) for each markdown table; section is the nearest Н-heading."""
    section, lines, i = "", text.split("\n"), 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r"^#{2,4}\s+(Н\d+(?:\.\d+)?|N\d+(?:\.\d+)?)\b", l)
        if m:
            section = m.group(1)
        if l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1]):
            head = cells(l)
            rows, j = [], i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append(cells(lines[j]))
                j += 1
            yield section, head, rows
            i = j
            continue
        i += 1


def section_of(text, needle):
    sec = ""
    for l in text.split("\n"):
        m = re.match(r"^#{2,4}\s+(Н\d+(?:\.\d+)?|N\d+(?:\.\d+)?)\b", l)
        if m:
            sec = m.group(1)
        if needle in l:
            return sec
    return None


# ---------------- OpenAPI (line-based, for the subset lessons use) ----------------


def openapi_blocks(text, section):
    """Return {name: [lines]} for components.<section>."""
    out, cur, inside, comp = {}, None, False, False
    for l in text.split("\n"):
        if re.match(r"^\S", l):
            comp = l.startswith("components:")
            inside = False
            continue
        if comp and re.match(r"^  \S", l):
            inside = l.strip() == section + ":"
            cur = None
            continue
        if inside:
            m = re.match(r"^    ([A-Za-z0-9_]+):\s*$", l)
            if m:
                cur = m.group(1)
                out[cur] = []
            elif cur:
                out[cur].append(l)
    return out


REF = re.compile(r"\$ref:\s*['\"]?#/components/(responses|schemas)/([A-Za-z0-9_]+)")


def openapi_units(text):
    """Return list of (method, path, code, kind, required fields, schema)."""
    schemas = openapi_blocks(text, "schemas")
    responses = openapi_blocks(text, "responses")

    def schema_kinds(name, depth=0):
        body = schemas.get(name, [])
        kind, req = None, []
        for i, l in enumerate(body):
            m = re.search(r"\bkind:\s*\{\s*const:\s*([a-z_]+)\s*\}", l)
            if m:
                kind = m.group(1)
            elif re.match(r"^\s+kind:\s*$", l):
                for l2 in body[i + 1:i + 4]:
                    m2 = re.search(r"const:\s*([a-z_]+)", l2)
                    if m2:
                        kind = m2.group(1)
                        break
            m = re.match(r"^\s+required:\s*\[(.*)\]", l)
            if m:
                req = [x.strip() for x in m.group(1).split(",") if x.strip()]
            elif re.match(r"^\s+required:\s*$", l):
                for l2 in body[i + 1:]:
                    m2 = re.match(r"^\s+-\s+([A-Za-z_]+)\s*$", l2)
                    if not m2:
                        break
                    req.append(m2.group(1))
        if kind:
            return [(kind, sorted(set(req) - {"kind", "error"}), name)]
        if depth > 3:
            return []
        res = []
        for _, (sec, n) in enumerate(REF.findall("\n".join(body))):
            if sec == "schemas":
                res += schema_kinds(n, depth + 1)
        return res

    def resolve(refs, depth=0):
        res = []
        for sec, n in refs:
            if sec == "schemas":
                res += schema_kinds(n)
            elif depth < 3:
                res += resolve(REF.findall("\n".join(responses.get(n, []))), depth + 1)
        return res

    units, path, method, code, buf = [], None, None, None, []
    in_paths = False

    def flush():
        if path and method and code and int(code) >= 400:
            kinds = resolve(REF.findall("\n".join(buf)))
            if not kinds:
                units.append((method, path, int(code), None, [], None))
            for k, req, sch in kinds:
                units.append((method, path, int(code), k, req, sch))

    for l in text.split("\n"):
        if re.match(r"^\S", l):
            flush()
            code, buf = None, []
            in_paths = l.startswith("paths:")
            continue
        if not in_paths:
            continue
        m = re.match(r"^  (/\S*):\s*$", l)
        if m:
            flush()
            path, method, code, buf = m.group(1), None, None, []
            continue
        m = re.match(r"^    (get|post|put|delete|patch|head):", l)
        if m:
            flush()
            method, code, buf = m.group(1).upper(), None, []
            continue
        m = re.match(r"^        ['\"]?(\d{3})['\"]?:(.*)$", l)
        if m:
            flush()
            code, buf = m.group(1), [m.group(2)]
            continue
        if re.match(r"^      \S", l):
            flush()
            code, buf = None, []
            continue
        if code:
            buf.append(l)
    flush()
    fault_names = {}
    for name in schemas:
        for k, _, _ in schema_kinds(name):
            if name.endswith("Fault") or name == "Refused":
                fault_names[name] = k
    return units, fault_names


# ---------------- spec facts ----------------


def spec_flags(spec):
    flags = []
    for path in sorted(spec.norms):
        for section, head, rows in tables(spec.norms[path]):
            if not head or head[0] not in ("Флаг", "Flag"):
                continue
            for n, row in enumerate(rows, 1):
                if len(row) < 3:
                    continue
                names = [t for t in BACKTICK.findall(row[0]) if t.startswith("-")]
                defaults = [row[2]]
                if len(names) > 1:
                    parts = [p.strip() for p in row[2].split(",")]
                    defaults = parts if len(parts) == len(names) else [row[2]] * len(names)
                for name, d in zip(names, defaults):
                    flags.append({
                        "name": name.lstrip("-"), "type": row[1], "default": d,
                        "meaning": row[3] if len(row) > 3 else "",
                        "ref": "%s %s «%s» #%d" % (chapter_of(path), section, "Флаги демона", n),
                    })
    return flags


def norm_default(cell):
    """Spec default cell -> (value or None for 'none', kind: exact|ref|prose)."""
    c = cell.strip()
    if c.startswith("`"):
        tok = BACKTICK.findall(c)[0]
        if tok.startswith("-"):
            return tok, "ref"
        return tok, "exact"
    low = c.lower()
    if low.startswith("нет") or low.startswith("none") or low.startswith("no "):
        return None, "exact"
    if low.startswith("выключен") or low.startswith("off") or low.startswith("false"):
        return "false", "exact"
    if re.fullmatch(r"-?\d+", c):
        return c, "exact"
    return c, "prose"


def type_cat(spec_type):
    t = spec_type.lower()
    if "без значения" in t or "no value" in t:
        return "bool"
    if t.startswith("целое") or t.startswith("integer") or re.match(r"^`\d+`(\s*\|\s*`\d+`)+$", spec_type.strip()):
        return "int"
    if t.startswith("срок") or t.startswith("duration"):
        return "duration"
    if t.startswith("байты") or t.startswith("bytes"):
        return "size"
    return "string"


CODE_TYPE = {"bool": "bool", "int": "int", "int64": "int", "uint": "int", "uint64": "int",
             "duration": "duration", "string": "string", "float64": "float"}


def spec_refusals(spec, fault_names):
    """Units from the Н4 tables: list of dicts."""
    kinds = BASE_KINDS | set(fault_names.values())
    kind_re = re.compile(r"(?<![\w-])(%s)(?![\w-])" % "|".join(sorted(kinds, key=len, reverse=True)))
    fault_re = re.compile(r"\b(%s)\b" % "|".join(sorted(fault_names, key=len, reverse=True))) if fault_names else None
    rows_out, skipped = [], []
    for path in sorted(spec.norms):
        for section, head, rows in tables(spec.norms[path]):
            if section not in ("Н4", "N4") or not head:
                continue
            for n, row in enumerate(rows, 1):
                if len(row) < 3:
                    continue
                ref = "%s %s #%d" % (chapter_of(path), section, n)
                reason, mid = row[0], " ".join(row[1:-1]) if len(row) > 2 else row[1]
                codes = [int(c) for c in re.findall(r"(?<![\d.])([45]\d\d)(?![\d.])", mid)]
                found = [m.group(1) for m in kind_re.finditer(mid)]
                if fault_re:
                    for m in fault_re.finditer(mid):
                        found.append(fault_names[m.group(1)])
                ks = []
                for k in found:
                    if k not in ks:
                        ks.append(k)
                exit_ = None
                if re.search(r"код 2|code 2", mid):
                    exit_ = "2"
                elif re.search(r"код ≠ 0|code ≠ 0|code != 0", mid):
                    exit_ = "nonzero"
                elif re.search(r"не стартует|does not start|не выполняется|отказ|refus", mid, re.I):
                    exit_ = "refusal"
                words = re.findall(r"«([^»]+)»", mid) + re.findall(r"\"([^\"]+)\"", mid)
                words = [w for w in words if w not in kinds]
                pairs = []
                if codes:
                    if len(ks) == len(codes):
                        pairs = list(zip(codes, ks))
                    elif len(codes) == 1:
                        pairs = [(codes[0], k) for k in ks] or [(codes[0], None)]
                    elif len(ks) == 1:
                        pairs = [(c, ks[0]) for c in codes]
                    else:
                        pairs = list(zip(codes, ks)) + [(c, None) for c in codes[len(ks):]]
                if not pairs and exit_ is None:
                    skipped.append(ref)
                    continue
                rows_out.append({"ref": ref, "reason": reason, "pairs": pairs, "exit": exit_, "words": words,
                                 "fuzzy_pairs": bool(codes) and len(codes) != len(ks) and len(codes) > 1})
    return rows_out, skipped


# ---------------- word matching ----------------


def _word_regex(w, spec_side):
    out, i = "", 0
    ph = re.compile(r"<[^<>]+>" if spec_side else r"\{[^{}]*\}")
    pos = 0
    for m in ph.finditer(w):
        out += re.escape(w[pos:m.start()]) + ".+?"
        pos = m.end()
    out += re.escape(w[pos:])
    if spec_side:
        out = re.sub(r"([\w-]+)\\\|([\w-]+)", r"(?:\1|\2)", out)
    return re.compile("^" + out + "$", re.I | re.S)


def _sample(w, spec_side):
    if spec_side:
        w = re.sub(r"<[^<>]+>", "X", w)
        return re.sub(r"([\w-]+)\|([\w-]+)", r"\1", w)
    return re.sub(r"\{[^{}]*\}", "X", w)


def word_match(spec_w, code_w):
    """Return None, 'exact' or 'fuzzy'."""
    a = re.sub(r"<[^<>]+>", "*", spec_w).strip().lower()
    b = re.sub(r"\{[^{}]*\}", "*", code_w).strip().lower()
    if a == b:
        return "exact"
    if _word_regex(spec_w.replace("|", "\\|"), True).match(_sample(code_w, False)):
        return "fuzzy"
    if _word_regex(code_w, False).match(_sample(spec_w, True)):
        return "fuzzy"
    sa = _sample(spec_w, True).lower()
    sb = _sample(code_w, False).lower()
    if len(sa) >= 6 and sa in sb or len(sb) >= 6 and sb in sa:
        return "fuzzy"
    return None


# ---------------- comparison ----------------


def check_status(status):
    """Reject an outcome outside the closed list (ADR-0123 доп. (2) п. 2)."""
    if status not in STATUSES:
        raise ValueError("compare: unknown outcome %r; allowed: %s" % (status, ", ".join(STATUSES)))
    return status


def run_outcome(seen, step, executed):
    """Outcome of a specified fact in a run snapshot (ADR-0123 доп. (1) п. 1).

    seen: the fact was met in the run; step: the acceptance step that checks
    it; executed: steps the run passport names as executed. A fact not met is
    `unobserved` only when its step ran, otherwise `out_of_scope`.
    """
    if seen:
        return "match"
    return "unobserved" if step and step in executed else "out_of_scope"


class Report:
    def __init__(self):
        self.rows = []

    def add(self, snapshot, unit, status, fuzzy=False, spec_ref="", spec="", code_ref="", code="", note=""):
        check_status(status)
        self.rows.append({"snapshot": snapshot, "unit": unit, "status": status, "fuzzy": "1" if fuzzy else "0",
                          "spec_ref": spec_ref, "spec": spec, "code_ref": code_ref, "code": code, "note": note})


def compare_params(rep, params, spec):
    sflags = spec_flags(spec)
    by_name = {}
    for f in params["flags"]:
        by_name.setdefault(f["name"], []).append(f)
    seen = set()
    for sf in sflags:
        name = sf["name"]
        seen.add(name)
        unit = "flag:-" + name
        sd, how = norm_default(sf["default"])
        sd_m = mask(sd) if sd is not None else None
        spec_txt = "type=%s default=%s" % (sf["type"], mask(sf["default"]))
        code = by_name.get(name, [])
        if not code:
            rep.add("params", unit, "absent", spec_ref=sf["ref"], spec=spec_txt)
            continue
        best, notes = None, []
        cat = type_cat(sf["type"])
        for cf in code:
            cd = cf["default"]
            cd_n = None if cd in ("", None) else cd
            if how == "exact":
                ok_def = (sd_m == cd_n) or (sd_m == "false" and cd == "false") or (sd_m is None and cd in ("", "0", "false"))
            elif how == "ref":
                ok_def = cd_n is None
            else:
                ok_def = cd_n is None and re.search(r"\bнет\b|\bnone\b", sf["default"], re.I) is not None
            ctype = CODE_TYPE.get(cf["type"], cf["type"])
            ok_type = ctype == cat or (cat == "size" and ctype == "string")
            score = (ok_def and ok_type, ok_def, ok_type)
            if best is None or score > best[0]:
                best = (score, cf, ok_def, ok_type)
        _, cf, ok_def, ok_type = best
        code_txt = "type=%s default=%s set=%s" % (cf["type"], cf["default"], cf["set"])
        unbound = sorted({c["set"] for c in code if not c["bound"]})
        if unbound:
            notes.append("declared but value discarded in set %s" % ",".join(unbound))
        if len(code) > 1:
            notes.append("also in sets: " + ",".join(sorted({c["set"] for c in code if c is not cf})))
        if how == "ref":
            notes.append("spec default refers to %s" % sd)
        if how == "prose":
            notes.append("spec default is prose")
        if cat == "size" and CODE_TYPE.get(cf["type"]) == "string":
            notes.append("size parsed from string")
        fuzzy = how != "exact"
        status = "match" if ok_def and ok_type else "differs"
        if not ok_def:
            notes.insert(0, "default differs")
        if not ok_type:
            notes.insert(0, "type differs")
        rep.add("params", unit, status, fuzzy, sf["ref"], spec_txt, cf["at"], code_txt, "; ".join(notes))
    prose = spec.prose
    for name in sorted(set(by_name) - seen):
        cf = by_name[name][0]
        mentioned = re.search(r"(?<![\w-])--?%s(?![\w-])" % re.escape(name), prose) is not None
        sets = ",".join(sorted({c["set"] for c in by_name[name]}))
        rep.add("params", "flag:-" + name, "extra", mentioned, "", "", cf["at"],
                "type=%s default=%s set=%s" % (cf["type"], cf["default"], sets),
                "named in norms prose, not in the flags table" if mentioned else "")
    for name in sorted({e["name"] for e in params["env"]}):
        e = [x for x in params["env"] if x["name"] == name][0]
        hit = None
        for path in sorted(spec.norms):
            if re.search(r"(?<![A-Z0-9_])%s(?![A-Z0-9_])" % re.escape(name), spec.norms[path]):
                hit = "%s %s" % (chapter_of(path), section_of(spec.norms[path], name) or "")
                break
        if hit:
            rep.add("params", "env:" + name, "match", True, hit.strip(), "named in norms", e["at"], e["call"],
                    "name only; norms prose, not a table")
        else:
            rep.add("params", "env:" + name, "extra", False, "", "", e["at"], e["call"], "name only")
    lim_note = ("#lim forms at pin: %s; pairing by form not implemented" % ",".join(spec.lim_files)) if spec.lim_files \
        else "no #lim form at the pin"
    nums = set(re.findall(r"(?<![\d.])\d{3,}(?![\d.])", prose + "\n" + spec.openapi))
    for c in params["consts"]:
        note = lim_note
        if c["value"] in nums:
            note += "; value occurs in pinned spec text"
        rep.add("params", "const:%s.%s" % (c["pkg"].rsplit("/", 1)[-1], c["name"]), "out_of_scope", False, "", "",
                c["at"], "%s = %s" % (c["type"], c["value"]), note)
    for h in params["help"]:
        static = {f["name"]: f for f in params["flags"]
                  if f["at"].startswith(h["package"] + "/") and (not h.get("set") or f["set"] == h["set"])}
        if h["status"] != "ok":
            rep.add("params", "help:" + h["package"], "out_of_scope", False, "", "", h["package"], h["status"],
                    "-h not available")
            continue
        hnames = {f["name"]: f for f in h["flags"]}
        for name in sorted(set(static) | set(hnames)):
            s, hh = static.get(name), hnames.get(name)
            if s and hh:
                sd = s["default"] if s["default"] not in ("", "false", "0") else None
                same = (sd == hh["default"]) or (sd is None and hh["default"] is None)
                rep.add("params", "help:-" + name, "match" if same else "differs", False, "", "", s["at"],
                        "static=%s -h=%s" % (s["default"], hh["default"]), "static vs -h of the built binary")
            else:
                rep.add("params", "help:-" + name, "differs", False, "", "", (s or {}).get("at", h["package"]),
                        "static=%s -h=%s" % ("yes" if s else "no", "yes" if hh else "no"),
                        "flag seen by one path only")


def compare_refusals(rep, refusals, deps, spec):
    units, fault_names = openapi_units(spec.openapi)
    rows, skipped = spec_refusals(spec, fault_names)
    main_pkgs = {p["path"] for p in deps["packages"] if p["name"] == "main"}
    main_exits = sorted({x["code"] for x in refusals["exits"] if x["pkg"] in main_pkgs})

    # Code pairs.
    code_pairs = {}
    for r in refusals["http"]:
        code_pairs.setdefault((r["code"], r["kind"]), []).append(r)

    # Spec pairs from Н4 and OpenAPI.
    spec_pairs = {}
    for row in rows:
        for c, k in row["pairs"]:
            spec_pairs.setdefault((c, k), {"refs": [], "fields": [], "fuzzy": row["fuzzy_pairs"]})["refs"].append(row["ref"])
    api_fields = {}
    for method, path, c, k, req, sch in units:
        e = spec_pairs.setdefault((c, k), {"refs": [], "fields": [], "fuzzy": False})
        e["refs"].append("openapi %s %s %d" % (method, path, c))
        if k and sch:
            api_fields.setdefault((c, k), {})[sch] = req

    consumed = set()
    for (c, k) in sorted(spec_pairs, key=lambda p: (p[0], p[1] or "")):
        e = spec_pairs[(c, k)]
        refs = sorted(set(e["refs"]))
        ref = "; ".join(refs[:6]) + (" (+%d)" % (len(refs) - 6) if len(refs) > 6 else "")
        unit = "pair:%d %s" % (c, k or "?")
        if k is None:
            hits = [p for p in code_pairs if p[0] == c]
            if hits:
                consumed.update(hits)
                rep.add("refusals", unit, "match", True, ref, "code %d, kind not named" % c, "",
                        ",".join("%d %s" % h for h in sorted(hits)), "kind not named in spec row")
            else:
                rep.add("refusals", unit, "absent", True, ref, "code %d" % c)
            continue
        if (c, k) in code_pairs:
            consumed.add((c, k))
            sites = code_pairs[(c, k)]
            rep.add("refusals", unit, "match", e["fuzzy"], ref, "%d %s" % (c, k), sites[0]["at"],
                    "%d sites" % len(sites))
            for sch, req in sorted(api_fields.get((c, k), {}).items()):
                if not req:
                    continue
                ok = [s for s in sites if set(req) <= set(s["fields"])]
                have = sorted({f for s in sites for f in s["fields"]})
                rep.add("refusals", "fields:%d %s %s" % (c, k, sch), "match" if ok else "differs", False,
                        "openapi %s required" % sch, ",".join(req), (ok or sites)[0]["at"], ",".join(have) or "-",
                        "" if ok else "no site sets all required body fields (static)")
        else:
            other = [p for p in code_pairs if p[1] == k and p not in spec_pairs]
            if other:
                consumed.update(other)
                rep.add("refusals", unit, "differs", True, ref, "%d %s" % (c, k), code_pairs[other[0]][0]["at"],
                        ",".join("%d %s" % o for o in sorted(other)), "same kind under another code")
            else:
                rep.add("refusals", unit, "absent", False, ref, "%d %s" % (c, k))
    for p in sorted(set(code_pairs) - consumed - set(spec_pairs)):
        sites = code_pairs[p]
        rep.add("refusals", "pair:%d %s" % p, "extra", False, "", "", sites[0]["at"], "%d sites" % len(sites))

    # Words and non-HTTP refusals.
    http_words = [r for r in refusals["http"] if r["word_source"] not in ("constructor-default", "none")]
    errors = refusals["errors"]
    used = set()

    def find(word, pool):
        best = None
        for i, r in enumerate(pool):
            for w in r["words"]:
                m = word_match(word, w)
                if m and (best is None or (m == "exact" and best[0] != "exact")):
                    best = (m, i, r, w)
        return best

    for row in rows:
        for w in row["words"]:
            unit = "word:%s" % w
            spec_txt = ("%s" % ",".join("%d %s" % (c, k or "?") for c, k in row["pairs"])) if row["pairs"] \
                else "exit %s" % row["exit"]
            if row["pairs"]:
                hit = find(w, http_words)
                pool = "http"
                if not hit:
                    hit = find(w, errors)
                    pool = "error"
            else:
                hit = find(w, errors)
                pool = "error"
                if not hit:
                    hit = find(w, http_words)
                    pool = "http"
            if not hit:
                rep.add("refusals", unit, "absent", True, row["ref"], spec_txt, "", "",
                        "no code literal carries this word (words of HTTP refusals are not normative)")
                continue
            m, i, r, cw = hit
            # Every site that carries the same word is paired with this spec row.
            for p2, pool_rs in (("http", http_words), ("error", errors)):
                for r2 in pool_rs:
                    if any(word_match(w, w2) for w2 in r2["words"]):
                        used.add((p2, id(r2)))
            notes, status = [], "match"
            if pool == "http" and row["pairs"]:
                if (r["code"], r["kind"]) not in row["pairs"]:
                    status = "differs"
                    notes.append("word under %d %s" % (r["code"], r["kind"]))
            elif pool == "error" and row["exit"] in ("2", "nonzero"):
                if r["pkg"] in main_pkgs:
                    if row["exit"] == "2" and 2 not in main_exits:
                        status = "differs"
                    notes.append("main exits %s" % (",".join(map(str, main_exits)) or "-"))
                else:
                    notes.append("exit code not traced across packages")
                    m = "fuzzy"
            elif pool == "http" and not row["pairs"]:
                notes.append("spec: non-HTTP outcome; code: HTTP %d %s" % (r["code"], r["kind"]))
                m = "fuzzy"
            rep.add("refusals", unit, status, m != "exact", row["ref"], spec_txt, r["at"], cw, "; ".join(notes))
        if row["pairs"] or row["words"]:
            continue
        # Non-HTTP rows without quoted words: match sub-reasons by backticked tokens.
        for j, sub in enumerate(split_reasons(re.sub(r"^[^:]{1,20}:\s*", "", row["reason"])), 1):
            toks = [t.split()[0] for t in BACKTICK.findall(sub) if t.strip()]
            strong = [t for t in toks if is_strong(t)]
            unit = "reason:%s/%d" % (row["ref"], j)
            spec_txt = "exit %s: %s" % (row["exit"], mask(sub.strip())[:120])
            if not toks:
                rep.add("refusals", unit, "absent", True, row["ref"], spec_txt, "", "",
                        "no literal token to match by")
                continue
            need = toks
            cands = []
            for r in errors:
                if r["scope"] != "lesson":
                    continue
                for w in r["words"]:
                    if all(re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(t), w, re.I) for t in need):
                        cands.append((len(w), r["at"], w, r))
            cands.sort(key=lambda c: (c[0], c[1]))
            hit = (cands[0][3], cands[0][2]) if cands else None
            if hit:
                used.add(("error", id(hit[0])))
                note = "matched by %s tokens %s (shortest of %d candidates)" % (
                    "strong" if strong else "weak", ",".join(need), len(cands))
                if hit[0]["pkg"] in main_pkgs:
                    note += "; main exits %s" % (",".join(map(str, main_exits)) or "-")
                    status = "differs" if row["exit"] == "2" and 2 not in main_exits else "match"
                else:
                    status = "match"
                rep.add("refusals", unit, status, True, row["ref"], spec_txt, hit[0]["at"], hit[0]["words"][0], note)
            else:
                rep.add("refusals", unit, "absent", True, row["ref"], spec_txt, "", "",
                        "no lesson error word carries tokens %s" % ",".join(need))

    for r in http_words:
        if ("http", id(r)) in used:
            continue
        rep.add("refusals", "word:%s" % r["words"][0], "extra", False, "", "", r["at"],
                "%d %s" % (r["code"], r["kind"]), "word of an HTTP refusal; words are not normative")
    for r in errors:
        if ("error", id(r)) in used:
            continue
        if r["scope"] == "lesson":
            rep.add("refusals", "error:%s" % r["words"][0], "extra", False, "", "", r["at"], r["func"],
                    "error word in the lesson code, no spec row names it")
        else:
            rep.add("refusals", "error:%s" % r["words"][0], "out_of_scope", False, "", "", r["at"], r["func"],
                    "shared package; its pair is in the lesson that owns it")
    for ref in skipped:
        rep.add("refusals", "row:" + ref, "out_of_scope", False, ref, "no code, exit or refusal outcome", "", "",
                "Н4 row is not a refusal outcome")


def split_reasons(text):
    """Split a reason cell on ';' outside parentheses."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == ";" and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def is_strong(tok):
    """Flag names, constants and snake_case words identify a refusal; plain words do not."""
    return tok.startswith("-") or "_" in tok or (tok.isupper() and len(tok) > 2)


def tsv_cell(s):
    return str(s).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def write_reports(snap_dir, rep, hdr, stale):
    order = {s: i for i, s in enumerate(STATUSES)}
    rows = sorted(rep.rows, key=lambda r: (r["snapshot"], order[r["status"]], r["fuzzy"], r["unit"], r["code_ref"], r["spec_ref"]))
    lines = ["\t".join(COLUMNS)] + ["\t".join(tsv_cell(r[c]) for c in COLUMNS) for r in rows]
    tsv = "\n".join(lines) + "\n"
    check_leaks("compare.tsv", tsv)
    (snap_dir / "compare.tsv").write_text(tsv, encoding="utf-8")

    md = ["# Сверка «как построено»: %s %s" % (hdr["implementation"], hdr["lesson"]), ""]
    md.append("- реализация: `%s` commit `%s`%s" % (hdr["implementation"], hdr["commit"][:12],
                                                     " — **снимок устарел**: вершина `%s`" % stale[:12] if stale else ""))
    md.append("- спецификация: выгрузка на пине `%s` (пин реализации)" % hdr["spec"][:12])
    md.append("- экстрактор: `%s`, источник `%s`; `deps` — справочный снимок без сверки (ADR-0123 доп. (1) п. 1)"
              % (hdr["extractor"], hdr["source"]))
    md.append("")
    md.append("Число единиц; в скобках — из них с неуверенным сопоставлением (`fuzzy`). "
              "`out_of_scope` — у факта нет применимой области или пары, это не отрицательный итог "
              "(ADR-0123 доп. (2) п. 2).")
    md.append("")
    md.append("| снимок | " + " | ".join(STATUSES) + " |")
    md.append("|---|" + "---|" * len(STATUSES))

    def cell(rs, s):
        n = sum(1 for r in rs if r["status"] == s)
        f = sum(1 for r in rs if r["status"] == s and r["fuzzy"] == "1")
        return "%d (%d)" % (n, f) if f else str(n)

    for snap in sorted({r["snapshot"] for r in rows}):
        rs = [r for r in rows if r["snapshot"] == snap]
        md.append("| %s | %s |" % (snap, " | ".join(cell(rs, s) for s in STATUSES)))
    for status, title in (("extra", "Лишнее (в коде есть, в спецификации нет)"),
                          ("absent", "Недостающее (в спецификации есть, в коде не найдено)"),
                          ("unobserved", "Не встретилось в прогоне (шаг проверки исполнен)"),
                          ("differs", "Разошлось")):
        rs = [r for r in rows if r["status"] == status]
        if not rs and status == "unobserved":
            continue  # a static report has no run outcomes
        md += ["", "## %s — %d, первые 20" % (title, len(rs)), ""]
        if not rs:
            md.append("нет")
            continue
        md.append("| снимок | единица | fuzzy | спецификация | код | пометка |")
        md.append("|---|---|---|---|---|---|")
        for r in rs[:20]:
            md.append("| %s | `%s` | %s | %s | %s | %s |" % (
                r["snapshot"], r["unit"].replace("|", "\\|"), r["fuzzy"],
                (r["spec_ref"] + " " + r["spec"]).strip().replace("|", "\\|"),
                (r["code_ref"] + " " + r["code"]).strip().replace("|", "\\|"), r["note"].replace("|", "\\|")))
    md.append("")
    text = "\n".join(md)
    check_leaks("compare.md", text)
    (snap_dir / "compare.md").write_text(text, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snap", required=True, help="snapshot directory <out>/<impl>/<lesson>")
    ap.add_argument("--spec-repo", required=True, help="export repository (read with git show at the pin)")
    ap.add_argument("--impl-root", help="implementation root, to report a stale snapshot")
    args = ap.parse_args(argv)
    snap = Path(args.snap)
    params = yamlio.load((snap / "params.yaml").read_text(encoding="utf-8"))
    refusals = yamlio.load((snap / "refusals.yaml").read_text(encoding="utf-8"))
    deps = yamlio.load((snap / "deps.yaml").read_text(encoding="utf-8"))
    hdr = params["header"]
    for other in (refusals["header"], deps["header"]):
        if other != hdr:
            raise SystemExit("compare: snapshot headers differ; rebuild all three")
    if not hdr["spec"]:
        raise SystemExit("compare: snapshot header has no spec pin")
    spec = Spec(args.spec_repo, hdr["spec"], hdr["lesson"])
    stale = ""
    if args.impl_root:
        p = subprocess.run(["git", "-C", args.impl_root, "rev-parse", "HEAD"], capture_output=True, text=True)
        head = p.stdout.strip()
        if head and head != hdr["commit"]:
            stale = head
    rep = Report()
    compare_params(rep, params, spec)
    compare_refusals(rep, refusals, deps, spec)
    write_reports(snap, rep, hdr, stale)
    counts = {s: sum(1 for r in rep.rows if r["status"] == s) for s in STATUSES}
    print("compare: " + " ".join("%s=%d" % kv for kv in counts.items()), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
