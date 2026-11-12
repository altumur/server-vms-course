"""Closed P/01, P/06 and P/08 numeric carriers (ADR-0129).

The roster is closed by coord103: 139 author carriers, two canonical book
carriers and five form equalities. Read source only; no generator imports.
"""
import hashlib
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml
from markdown_it import MarkdownIt

DOMAIN = "Platform/08-domain"
API = DOMAIN + "/spec/08-domain.api.openapi.yaml"
BOOK_SCHEMAS = (
    "alarm-history", "anywhere", "backups", "batches", "book", "book-all", "book-keys", "book-part", "book-seal",
    "break-glass", "deleting", "disabled", "domain-folders", "domain-memberof", "folder-counts", "folder-log",
    "folder-rev", "folder-units", "folder-units-head", "from-nothing", "grants", "groups", "holder", "idem", "issued",
    "keepers", "keys", "knocks", "member-ca-certs", "member-count", "member-report", "member-report-delta",
    "member-reported", "member-tables", "members", "move-ask", "names-index", "outcomes", "partial", "pending",
    "placement", "placement-record", "ref-claims", "relay-members", "revoked", "roles", "root", "shadow", "shared",
    "shared-docs", "signer", "signer-pending", "signer-turn", "stranded", "topology", "users", "view", "view-rows",
)
BOOK_POINTER = "/$defs/common.book_row/properties//properties"
P06_FOLDER_BINDINGS = (
    ("Platform/06-console/data/folders.schema.json", "/$defs/writer/properties/members/maxItems", "FOLDERS_MEMBERS_MAX"),
    ("Platform/06-console/data/memberof.schema.json", "/$defs/writer/properties/folders/maxItems", "FOLDERS_PER_UNIT_MAX"),
)
P08_RELAY_BINDINGS = (
    ("Platform/08-domain/data/relay-members.schema.json", "/properties/members/maxProperties"),
    ("Platform/10-domain-console/spec/10-domain-console.api.openapi.yaml",
     "/paths/~1domain~1relays~1{relay}/get/responses/200/content/application~1json/schema/properties/members/maxItems"),
)
P06_API = "Platform/06-console/spec/06-console.api.openapi.yaml"
# Literal public owner coordinates; values always come from the independent owner.
P06_API_BINDINGS = (
    (P06_API, "/components/schemas/Changes/properties/changes/maxItems", "06-console", "CHANGES_HISTORY", "count"),
    (P06_API, "/paths/~1changes/get/parameters/1/schema/maximum", "06-console", "CHANGES_WAIT", "s"),
    (P06_API, "/paths/~1changes/head/parameters/1/schema/maximum", "06-console", "CHANGES_WAIT", "s"),
    (P06_API, "/components/schemas/VerifyInput/properties/need/properties/units/maxItems", "06-console", "VERIFY_UNITS_MAX", "count"),
)
P06_READER_BINDINGS = (
    ("Platform/06-console/data/folders.schema.json", "/properties/name/x-max-bytes", "06-console", "FOLDER_NAME_MAX", "bytes"),
    ("Platform/06-console/data/folders.schema.json", "/properties/members/maxItems", "06-console", "FOLDERS_MEMBERS_MAX", "count"),
    ("Platform/06-console/data/memberof.schema.json", "/properties/folders/maxItems", "06-console", "FOLDERS_PER_UNIT_MAX", "count"),
    ("Platform/06-console/data/sweep.schema.json", "/properties/digests/maxItems", "06-console", "SWEEP_LIMIT", "count"),
)
P06_SWEEP_BINDINGS = (
    ("Platform/06-console/data/sweep.schema.json", "/$defs/writer/properties/digests/maxItems", "06-console", "SWEEP_LIMIT", "count"),
)
P09_READER_BINDINGS = (
    ("Platform/09-agent/data/outcomes.schema.json", "/maxProperties", "09-agent", "OUTCOMES_KEEP", "count"),
    ("Platform/09-agent/data/alarms.schema.json", "/properties/events/maxItems", "09-agent", "ALARM_PAGE", "count"),
)
P09_WRITER_BINDINGS = (
    ("Platform/09-agent/data/outcomes.schema.json", "/$defs/writer/maxProperties", "09-agent", "OUTCOMES_KEEP", "count"),
    ("Platform/09-agent/data/alarms.schema.json", "/$defs/writer/properties/events/maxItems", "09-agent", "ALARM_PAGE", "count"),
)
P08_NEW_BINDINGS = (
    ("Platform/08-domain/data/outcomes.schema.json", "/x-max-names", "08-domain", "OUTCOMES_LIMIT", "count"),
    ("Platform/08-domain/data/pending.schema.json", "/x-max-names", "08-domain", "KEPT_LIMIT", "count"),
)
HISTORY_OWNER = "Platform/common/contracts/alarm-history.md"
HISTORY_CARRIER = "Platform/08-domain/data/alarm-history.schema.json"

P01_API = "Platform/01-store/spec/01-store.api.openapi.yaml"
P01_CONSTANT_BINDINGS = (
    (P01_API, "/components/schemas/Status/properties/admission_ahead/exclusiveMinimum", "CLOCK_SKEW", "s", None),
    (P01_API, "/components/schemas/Key/description", "KEY_BYTES", "bytes",
     r"N1: a key is not empty, does not start with /, no segment between / equals \.\.; "
     r"\.\.foo is admissible\. The limit of (?P<value>[1-9][0-9]*) UTF-8 bytes "
     r"(?:applies to every implementation and is checked separately|and a smaller file limit are checked separately)"
     r"; maxLength does not express a number of bytes\."),  # the second form until P01.257 (R021 withdrawn) is merged
    ("Platform/01-store/data/configstore-doors.schema.json", "/properties/seen_at/description", "DOOR_SEEN_EVERY", "s",
     r"the wall time of the last confirmation of the door \(every (?P<value>[1-9][0-9]*) s\)"),
)


def schema_bindings():
    """(file, JSON pointer, owner, constant), including the empty book property."""
    out = [(f"{DOMAIN}/data/{name}.schema.json", f"{BOOK_POINTER}/{field}/maxItems", "08-domain", "MISSING_SHOWN")
           for name in BOOK_SCHEMAS for field in ("missing", "stale")]
    out += [("Platform/common/data/common.schema.json", f"{BOOK_POINTER}/{field}/maxItems", "08-domain", "MISSING_SHOWN")
            for field in ("missing", "stale")]
    out += [(f"{DOMAIN}/data/{name}.schema.json", "/properties/title/maxLength", "08-domain", "GROUP_TITLE_MAX")
            for name in ("users", "groups", "roles")]
    out += [(f"{DOMAIN}/data/{name}.schema.json", "/properties/comment/maxLength", "08-domain", "COMMENT_MAX")
            for name in ("groups", "roles")]
    out.append((f"{DOMAIN}/data/domain-memberof.schema.json", "/$defs/writer/properties/folders/maxItems",
                "06-console", "FOLDERS_PER_UNIT_MAX"))
    for family in ("users", "groups", "roles"):
        for suffix, method in (("", "post"), ("~1{name}", "put")):
            prefix = f"/paths/~1domain~1{family}{suffix}/{method}/requestBody/content/application~1json/schema/properties"
            out.append((API, prefix + "/title/maxLength", "08-domain", "GROUP_TITLE_MAX"))
            if family != "users":
                out.append((API, prefix + "/comment/maxLength", "08-domain", "COMMENT_MAX"))
    for name in ("RolePutFields", "PersonView", "GroupView", "RoleView"):
        prefix = f"/components/schemas/{name}/properties"
        out.append((API, prefix + "/title/maxLength", "08-domain", "GROUP_TITLE_MAX"))
        if name != "PersonView":
            out.append((API, prefix + "/comment/maxLength", "08-domain", "COMMENT_MAX"))
    return out


FORM_EQUALITIES = (
    ("08-domain", "SERVERS_MAX", "08-domain", "MISSING_SHOWN", 1, "count"),
    ("08-domain", "BATCH_LIMIT", "08-domain", "BODY_LIMIT", 4, "bytes"),
    ("08-domain", "BOOK_PARTS_PASS", "09-agent", "BOOK_PARTS_PASS", 1, "count"),
    ("08-domain", "REPORT_EVERY", "09-agent", "REPORT_EVERY", 1, "s"),
    ("08-domain", "BODY_LIMIT", "09-agent", "BODY_LIMIT", 1, "bytes"),
)
PASSWORD_CASES = "Platform/common/vectors/password-hash/cases.tsv"
# Independent, already published PBKDF2 witnesses and their one actual wire binding.
PASSWORD_CASES_SHA = "a485e8d50c03e61c55f8d643a9a81625c51d037c82899a106bd6acb1dfa44077"
PASSWORD_WIRE_SHA = "a85e54e42d2a4e5e699d6b03106124acf288563959d485f0b0842c866dd18357"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


class Judge:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.errors, self.stats = [], Counter()
        self.texts, self.documents, self.forms = {}, {}, {}

    def error(self, path, message):
        self.errors.append((self.root / path, message))

    def text(self, path):
        if path not in self.texts:
            try:
                self.texts[path] = (self.root / path).read_bytes().decode("utf-8")
            except (OSError, UnicodeError) as exc:
                self.error(path, str(exc))
                self.texts[path] = None
        return self.texts[path]

    def document(self, path):
        if path not in self.documents:
            text = self.text(path)
            self.documents[path] = None
            if text is not None:
                try:
                    if path.endswith(".json"):
                        self.documents[path] = json.loads(text, parse_float=Decimal, object_pairs_hook=unique_object)
                    else:
                        # Same YAML 1.2 source grammar as check_spec; retain exact numeric
                        # values so a fractional bound cannot round to the integer source.
                        from check_spec import UniqueLoader

                        class NumericLoader(UniqueLoader):
                            pass

                        NumericLoader.add_constructor("tag:yaml.org,2002:float",
                                                      lambda loader, node: Decimal(loader.construct_scalar(node)))
                        self.documents[path] = yaml.load(text, Loader=NumericLoader)
                    if not isinstance(self.documents[path], dict):
                        raise ValueError("a numeric carrier document must be an object")
                except (ValueError, ArithmeticError, yaml.YAMLError) as exc:
                    self.error(path, f"cannot parse numeric carrier: {exc}")
        return self.documents[path]

    def constant(self, owner, name, unit):
        path = f"Platform/{owner}/forms/runtime-constants.tsv"
        if owner not in self.forms:
            from check_forms import CONST_COLUMNS, read
            self.forms[owner] = {}
            if self.text(path) is not None:
                problems, rows = read(self.root / path, CONST_COLUMNS)
                for problem in problems:
                    self.error(path, problem)
                for row in rows:
                    if row["name"] in self.forms[owner]:
                        self.error(path, f"ambiguous constant {row['name']}: duplicate row")
                    if not re.fullmatch(r"[1-9][0-9]*", row["value"]) or len(row["value"]) > 19:
                        self.error(path, f"{row['name']}: expected a positive unpadded ASCII integer")
                    else:
                        self.forms[owner][row["name"]] = (int(row["value"]), row["unit"])
        value = self.forms[owner].get(name)
        if value is None:
            self.error(path, f"missing constant {name}")
            return None
        if value[1] != unit:
            self.error(path, f"{name}: unit {value[1]!r}, expected {unit}")
            return None
        if not 0 < value[0] <= 9223372036854775807:
            self.error(path, f"{name}: outside positive int64")
            return None
        return value[0]

    def pointer(self, path, pointer):
        node = self.document(path)
        for token in pointer.lstrip("/").split("/") if pointer else ():
            key = token.replace("~1", "/").replace("~0", "~")
            node = node[int(key)] if isinstance(node, list) and re.fullmatch(r"0|[1-9][0-9]*", key) else node[key]
        return node

    def effective(self, path, pointer):
        """Return every applicable ref/allOf copy, resolving refs at their real base.

        anyOf/oneOf are deliberately not flattened into unconditional constraints.
        """
        def walk(file, node, tokens, active=()):
            if not isinstance(node, dict):
                return []
            marker = (file, id(node), tuple(tokens))
            if marker in active:
                raise ValueError("cyclic effective numeric carrier")
            active = (*active, marker)
            out = []
            if tokens:
                key = tokens[0]
                if key in node:
                    if len(tokens) == 1:
                        out.append(node[key])
                    else:
                        out += walk(file, node[key], tokens[1:], active)
            ref = node.get("$ref")
            if ref is not None:
                if not isinstance(ref, str):
                    raise ValueError("non-string numeric carrier ref")
                url = urlsplit(ref)
                if url.scheme or url.netloc or url.query:
                    raise ValueError("nonlocal numeric carrier ref")
                target = (self.root / file).parent / unquote(url.path) if url.path else self.root / file
                target = target.resolve()
                if not target.is_relative_to(self.root):
                    raise ValueError("numeric carrier ref escapes Source root")
                target = target.relative_to(self.root).as_posix()
                fragment = unquote(url.fragment)
                if fragment and not fragment.startswith("/"):
                    raise ValueError("numeric carrier ref requires a JSON pointer")
                # First resolve the reference target; never reapply root allOf to
                # the fragment tokens (which would recursively prepend the ref).
                out += walk(target, self.pointer(target, fragment), tokens, active)
            all_of = node.get("allOf", [])
            if not isinstance(all_of, list) or any(not isinstance(part, dict) for part in all_of):
                raise ValueError("invalid numeric carrier allOf")
            for part in all_of:
                out += walk(file, part, tokens, active)
            return out
        tokens = [k.replace("~1", "/").replace("~0", "~") for k in pointer[1:].split("/")]
        return walk(path, self.document(path), tokens)

    def declared_equalities(self, bindings, counter, effective=False):
        for path, pointer, owner, name, unit in bindings:
            expected = self.constant(owner, name, unit)
            try:
                values = self.effective(path, pointer) if effective else [self.pointer(path, pointer)]
                if not values:
                    raise KeyError(pointer)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                self.error(path, f"missing/invalid numeric carrier {pointer}: {exc}")
                continue
            if expected is None or any(type(v) is not int or v != expected for v in values):
                self.error(path, f"{pointer}: expected integer {owner}/{name}={expected} {unit}, got {values!r}")
            else:
                self.stats[counter] += 1

    def console_numeric(self):
        self.declared_equalities(P06_API_BINDINGS, "p06_api_equalities")
        self.declared_equalities(P06_SWEEP_BINDINGS, "p06_sweep_equalities")
        self.declared_equalities(P06_READER_BINDINGS, "p06_effective_reader_equalities", effective=True)

    def agent_numeric(self):
        self.declared_equalities(P09_WRITER_BINDINGS, "p09_writer_equalities")
        self.declared_equalities(P09_READER_BINDINGS, "p09_effective_reader_equalities", effective=True)

    def domain_numeric(self):
        self.declared_equalities(P08_NEW_BINDINGS, "p08_new_named_equalities")
        text = self.text(HISTORY_OWNER)
        matches = re.findall(r"(?m)^HISTORY_LINES: +([1-9][0-9]*)$", text or "")
        expected = int(matches[0]) if len(matches) == 1 and len(matches[0]) <= 19 else None
        if expected is None or not 0 < expected <= 9223372036854775807:
            self.error(HISTORY_OWNER, "missing/duplicate/invalid positive int64 HISTORY_LINES owner")
            expected = None
        try:
            value = self.pointer(HISTORY_CARRIER, "/properties/events/maxItems")
        except (KeyError, IndexError, TypeError):
            value = None
        if expected is None or type(value) is not int or value != expected:
            self.error(HISTORY_CARRIER, f"events/maxItems: expected HISTORY_LINES={expected}, got {value!r}")
        else:
            self.stats["p08_history_lines_equalities"] += 1

    def entry_url_bytes(self):
        """Declared Entry field constraint, never a new runtime constant or codec binding."""
        owner = "Platform/08-domain/spec/08.10-domain.norms.md"
        path = API
        pointer = "/components/schemas/Entry/properties/url/x-max-bytes"
        text = self.text(owner)
        matches = re.findall(r"(?m)^ENTRY_MAX: forms/runtime-constants\.tsv; bytes with class, url ≤ ([1-9][0-9]*), via, batch;", text or "")
        expected = int(matches[0]) if len(matches) == 1 and len(matches[0]) <= 19 else None
        if expected is None or not 0 < expected <= 9223372036854775807:
            self.error(owner, "missing/duplicate/invalid Entry.url byte constraint")
            expected = None
        try:
            value = self.pointer(path, pointer)
        except (KeyError, IndexError, TypeError):
            value = None
        if expected is None or type(value) is not int or value != expected:
            self.error(path, f"{pointer}: expected Entry.url byte constraint={expected}, got {value!r}")
        else:
            self.stats["p08_entry_url_byte_equalities"] += 1

    def schemas(self):
        for path, pointer, owner, name in schema_bindings():
            expected = self.constant(owner, name, "count")
            node = self.document(path)
            if node is None:
                continue
            try:
                for key in pointer[1:].split("/"):
                    node = node[key.replace("~1", "/").replace("~0", "~")]
            except (KeyError, TypeError):
                self.error(path, f"missing numeric carrier {pointer}")
                continue
            numeric = type(node) is int or isinstance(node, Decimal) and node.is_finite()
            if not numeric or node != expected:
                self.error(path, f"{pointer}: expected {owner}/{name}={expected}, got {node!r}")
            else:
                self.stats["p08_schema_equalities"] += 1
        for a, left, b, right, factor, unit in FORM_EQUALITIES:
            lhs, rhs = self.constant(a, left, unit), self.constant(b, right, unit)
            if lhs is None or rhs is None or lhs != factor * rhs:
                self.error(f"Platform/{a}/forms/runtime-constants.tsv",
                           f"form equality {a}/{left} = {factor} * {b}/{right} fails")
            else:
                self.stats["p08_form_equalities"] += 1

    def folder_schemas(self):
        """Two assigned P06 writer carriers, literal integer type (never bool)."""
        for path, pointer, name in P06_FOLDER_BINDINGS:
            expected = self.constant("06-console", name, "count")
            node = self.document(path)
            if node is None:
                continue
            try:
                for key in pointer[1:].split("/"):
                    node = node[key]
            except (KeyError, TypeError):
                self.error(path, f"missing numeric carrier {pointer}")
                continue
            if type(node) is not int or node != expected:
                self.error(path, f"{pointer}: expected integer 06-console/{name}={expected}, got {node!r}")
            else:
                self.stats["p06_folder_equalities"] += 1

    def relay_members(self):
        """One P08 writer owner and its P10 reader copy, never a second value row."""
        expected = self.constant("08-domain", "RELAY_MEMBERS_MAX", "count")
        if expected is not None and not 0 < expected <= 9223372036854775807:
            self.error("Platform/08-domain/forms/runtime-constants.tsv", "RELAY_MEMBERS_MAX is outside positive int64")
        for path, pointer in P08_RELAY_BINDINGS:
            node = self.document(path)
            if node is None:
                continue
            try:
                for key in pointer[1:].split("/"):
                    node = node[key.replace("~1", "/").replace("~0", "~")]
            except (KeyError, TypeError):
                self.error(path, f"missing numeric carrier {pointer}")
                continue
            if type(node) is not int or node != expected:
                self.error(path, f"{pointer}: expected integer 08-domain/RELAY_MEMBERS_MAX={expected}, got {node!r}")
            else:
                self.stats["p08_relay_member_equalities"] += 1
        follower = "Platform/10-domain-console/forms/runtime-constants.tsv"
        if self.text(follower) is not None:
            from check_forms import CONST_COLUMNS, read
            errors, rows = read(self.root / follower, CONST_COLUMNS)
            for error in errors:
                self.error(follower, error)
            if any(row["name"] == "RELAY_MEMBERS_MAX" for row in rows):
                self.error(follower, "RELAY_MEMBERS_MAX is owned by P08; a P10 value row duplicates its owner")

    def store_constants(self):
        """Three assigned P01 carriers; descriptions are exact closed source sentences."""
        for path, pointer, name, unit, pattern in P01_CONSTANT_BINDINGS:
            expected = self.constant("01-store", name, unit)
            node = self.document(path)
            if node is None:
                continue
            try:
                keys = pointer[1:].split("/")
                for key in keys[:-1]:
                    node = node[key]
                parent, node = node, node[keys[-1]]
            except (KeyError, TypeError):
                self.error(path, f"missing numeric carrier {pointer}")
                continue
            if pattern is None:
                numeric = type(node) is int or isinstance(node, Decimal) and node.is_finite()
                if not numeric or node != expected:
                    self.error(path, f"{pointer}: expected 01-store/{name}={expected}, got {node!r}")
                    continue
                if parent.get("type") != "number" or "minimum" in parent:
                    self.error(path, f"{pointer}: admission_ahead must remain a number strictly greater than {name}")
                    continue
            else:
                match = re.fullmatch(pattern, node) if isinstance(node, str) else None
                if match is None or int(match["value"]) != expected:
                    self.error(path, f"{pointer}: expected closed {unit} description for 01-store/{name}={expected}")
                    continue
                if name == "KEY_BYTES" and (parent.get("type") != "string" or "maxLength" in parent):
                    self.error(path, f"{pointer}: KEY_BYTES is a UTF-8 byte limit, never a maxLength character limit")
                    continue
            self.stats["p01_constant_equalities"] += 1

    def contract(self, path, keys, names, phrases):
        text = self.text(path)
        if text is None:
            return {}
        blocks, links, declarations = [], [], []
        stack = []
        for token in MarkdownIt("commonmark").parse(text):
            if token.type == "inline" and "blockquote_open" not in stack:
                targets = [child.attrGet("href") or "" for child in token.children or [] if child.type == "link_open"]
                links.extend(target for target in targets if "runtime-constants.tsv" in target)
                if all(name in token.content for name in names) and any("runtime-constants.tsv" in t for t in targets):
                    declarations.append(" ".join(token.content.split()))
            if token.type == "fence" and token.info.strip() == "yaml" and not stack:
                fields, last, duplicates = {}, None, []
                for line in token.content.splitlines():
                    match = re.match(r"^([A-Za-z_][A-Za-z_0-9]*):[ \t]*(.*)", line)
                    if match:
                        last = match[1]
                        if last in fields:
                            duplicates.append(last)
                        fields[last] = match[2]
                    elif line.startswith((" ", "\t")) and last:
                        fields[last] += " " + line.strip()
                if set(fields) & set(keys):
                    blocks.append(fields)
                    for key in duplicates:
                        self.error(path, f"duplicate contract field {key}")
            if token.nesting == 1:
                stack.append(token.type)
            elif token.nesting == -1:
                stack.pop()
        target = urlsplit(links[0]) if len(links) == 1 else None
        expected = self.root / DOMAIN / "forms/runtime-constants.tsv"
        if target is None or target.scheme or target.netloc or \
                (self.root / path).parent.joinpath(unquote(target.path)).resolve() != expected:
            self.error(path, "closed reference needs exactly one binding to the P/08 runtime-constants form")
        if len(declarations) != 1 or any(phrase not in declarations[0] for phrase in phrases):
            self.error(path, "missing or ambiguous closed-reference declaration/strictness")
        if len(blocks) != 1 or set(blocks[0]) != set(keys):
            self.error(path, "expected one actual YAML fence with exactly the declared contract fields")
            return {}
        self.stats["p08_closed_contracts"] += 1
        return {key: " ".join(value.split()) for key, value in blocks[0].items()}

    def contracts(self):
        self.constant("08-domain", "KNOCKS", "count")
        self.constant("08-domain", "BATCH_LIMIT", "bytes")
        for ru in (False, True):
            home = "Platform/common/" + ("ru/" if ru else "") + "contracts/"
            path = home + "password-hash.md"
            phrases = (("имеет ровно одну привязку:", "десятичными ASCII-цифрами без ведущих нулей",
                        "другого числа итераций, alias, настройки или дополнительного принимаемого формата нет") if ru else
                       ("has exactly one binding:", "unpadded ASCII decimal digits",
                        "no other iteration count, alias, setting or additional accepted format"))
            fields = self.contract(path, ("form", "hash", "verify", "secret"), ("PBKDF2_ITERATIONS",), phrases)
            salt, key, iterations = ("соль", "ключ", "итераций") if ru else ("salt", "key", "iterations")
            form = f"pbkdf2-sha256$<PBKDF2_ITERATIONS>$<{salt}: 32 " + ("строчных hex>" if ru else "lowercase hex>")
            form += f"$<{key}: 64 " + ("строчных hex>" if ru else "lowercase hex>")
            operands = re.findall(r"PBKDF2-HMAC-SHA256\([^,\n]+,[^,\n]+,\s*([^,;\n]+),", fields.get("hash", ""))
            if fields.get("form") != form or operands != [f"PBKDF2_ITERATIONS {iterations}"]:
                self.error(path, "form/hash must use only the closed PBKDF2_ITERATIONS reference")

            path = home + "accept.md"
            phrases = (("имеют единственный числовой источник", "новых настроек или полей провода нет") if ru else
                       ("have one numeric source:", "there is no new setting or wire field"))
            fields = self.contract(path, ("BATCH_LIMIT", "KNOCKS", "holder", "answer"), ("BATCH_LIMIT", "KNOCKS"), phrases)
            ref = "значение формы P/08" if ru else "the P/08 form value"
            if fields.get("BATCH_LIMIT", "").split("#")[0].strip() != ref or \
                    fields.get("KNOCKS", "").split(";")[0].strip() != ref:
                self.error(path, "BATCH_LIMIT/KNOCKS must use only the closed P/08 row references")
            required = (("KNOCKS незнакомцев", "незнакомец KNOCKS + 1", "стуков в пакете больше KNOCKS",
                         "первых KNOCKS по имени", "не больше BATCH_LIMIT") if ru else
                        ("KNOCKS strangers", "stranger KNOCKS + 1", "more than KNOCKS knocks",
                         "first KNOCKS by name", "at most BATCH_LIMIT"))
            body = " ".join(fields.values())
            if any(phrase not in body for phrase in required):
                self.error(path, "relay limit uses must retain the closed BATCH_LIMIT/KNOCKS names")

    def vectors(self):
        from check_forms import read
        cost = self.constant("08-domain", "PBKDF2_ITERATIONS", "count")
        text = self.text(PASSWORD_CASES)
        if text is not None:
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != PASSWORD_CASES_SHA:
                self.error(PASSWORD_CASES, "the 13 independent password vectors must remain byte-exact")
            errors, rows = read(self.root / PASSWORD_CASES, ["case", "input", "expect", "note"])
            for error in errors:
                self.error(PASSWORD_CASES, error)
            pattern = rf"pbkdf2-sha256\${cost}\$[0-9a-f]{{32}}\$[0-9a-f]{{64}}"
            hashes, accepted, refused = 0, 0, 0
            for row in rows:
                try:
                    inp = json.loads(row["input"], object_pairs_hook=unique_object)
                    result = json.loads(row["expect"])
                    value = result if "salt" in inp else inp["hash"]
                    if "salt" in inp or result is True:
                        if not isinstance(value, str) or not re.fullmatch(pattern, value):
                            self.error(PASSWORD_CASES, f"{row['case']}: wire cost/form differs from PBKDF2_ITERATIONS={cost}")
                    hashes += "salt" in inp
                    accepted += result is True
                    refused += result is False
                except (ValueError, KeyError, TypeError) as exc:
                    self.error(PASSWORD_CASES, f"{row['case']}: invalid password witness: {exc}")
            if (len(rows), hashes, accepted, refused) != (13, 3, 2, 8):
                self.error(PASSWORD_CASES, "expected 13 password witnesses: 3 hashes, 2 accepted and 8 refused")
            self.stats["p08_password_vectors"] = len(rows)
        wire = "Platform/common/vectors/wire.tsv"
        text = self.text(wire)
        if text is not None:
            rows = [line for line in text.split("\n") if line.startswith("common/password-hash\t")]
            if len(rows) != 1 or hashlib.sha256(rows[0].encode("utf-8")).hexdigest() != PASSWORD_WIRE_SHA:
                self.error(wire, "the actual common/password-hash wire binding must remain byte-exact and unique")


def check_p08_constants(root):
    judge = Judge(root)
    judge.schemas()
    judge.contracts()
    judge.vectors()
    judge.relay_members()
    return judge.errors, dict(judge.stats)


def check_p08_relay_constants(root):
    judge = Judge(root)
    judge.relay_members()
    return judge.errors, dict(judge.stats)


def check_p06_folder_constants(root):
    judge = Judge(root)
    judge.folder_schemas()
    return judge.errors, dict(judge.stats)


def check_p01_constants(root):
    judge = Judge(root)
    judge.store_constants()
    return judge.errors, dict(judge.stats)


def check_p09_numeric_constants(root):
    judge = Judge(root)
    judge.agent_numeric()
    return judge.errors, dict(judge.stats)


def check_p06_numeric_constants(root):
    judge = Judge(root)
    judge.console_numeric()
    return judge.errors, dict(judge.stats)


def check_p08_named_constants(root):
    judge = Judge(root)
    judge.domain_numeric()
    return judge.errors, dict(judge.stats)


def check_p08_entry_url_bytes(root):
    judge = Judge(root)
    judge.entry_url_bytes()
    return judge.errors, dict(judge.stats)
