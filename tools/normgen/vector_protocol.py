"""Derive the public structural vector-adapter protocol from its canonical table.

Only package/surface, input transport shapes, and native output shapes are public.
Fixture-dependent selectors, fixture columns/files, expectations and comparison
rules are never protocol material. Owner-only selectors remain. The native output
variants are a union: a case-varying constant becomes its JSON type; a constant
invariant across the named variant remains. The complete source identity and
classification are returned separately for a receipt outside the model-readable tree.
"""
import csv
import hashlib
import io
import json
import re


COLUMNS = ("package", "table", "surface", "header", "inputs", "files", "expect",
           "compare", "markers", "native", "norm")
PRIVATE_COLUMNS = ("table", "header", "files", "expect", "compare", "markers", "norm")
TYPES = {"null", "boolean", "object", "array", "number", "integer", "string"}
SCHEMA_KEYS = {"type", "properties", "required", "additionalProperties", "items",
               "oneOf", "anyOf", "allOf", "const", "enum", "minLength", "maxLength",
               "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
               "minItems", "maxItems", "minProperties", "maxProperties", "uniqueItems"}


class ProtocolError(ValueError):
    pass


def _load(text, where):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProtocolError(f"{where}: duplicate JSON member")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              ProtocolError(f"{where}: non-finite JSON number")))
    except (ValueError, TypeError) as exc:
        raise ProtocolError(f"{where}: malformed JSON") from exc


def read_rows(data):
    if not isinstance(data, bytes):
        raise ProtocolError("canonical table must be UTF-8 bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("canonical table is not UTF-8") from exc
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="\t", strict=True)
    try:
        header = next(reader)
        if tuple(header) != COLUMNS:
            raise ProtocolError("canonical table has an unsupported header")
        rows = []
        for line, values in enumerate(reader, 2):
            if len(values) != len(COLUMNS):
                raise ProtocolError(f"canonical table line {line}: column count")
            row = dict(zip(COLUMNS, values))
            for name in ("inputs", "files", "expect", "markers"):
                row[name] = _load(row[name], f"line {line}/{name}")
            row["native"] = None if row["native"] == "-" else _load(
                row["native"], f"line {line}/native")
            if not isinstance(row["inputs"], list) or not isinstance(row["expect"], list):
                raise ProtocolError(f"canonical table line {line}: expected input/expect lists")
            if not isinstance(row["files"], dict) or not isinstance(row["markers"], list):
                raise ProtocolError(f"canonical table line {line}: expected files/markers containers")
            row["_line"] = line
            rows.append(row)
    except (csv.Error, StopIteration) as exc:
        raise ProtocolError("malformed canonical table") from exc
    return rows


def _schema(value):
    if isinstance(value, bool):
        return value
    if not isinstance(value, dict) or set(value) - SCHEMA_KEYS:
        raise ProtocolError("unsupported native schema shape")
    result = {}
    for key, item in value.items():
        if key == "properties":
            if not isinstance(item, dict):
                raise ProtocolError("native properties must be an object")
            result[key] = {name: _schema(child) for name, child in item.items()}
        elif key in ("additionalProperties", "items"):
            result[key] = _schema(item)
        elif key in ("oneOf", "anyOf", "allOf"):
            if not isinstance(item, list) or not item:
                raise ProtocolError("native schema alternatives must be a nonempty list")
            result[key] = [_schema(child) for child in item]
        elif key == "type":
            values = item if isinstance(item, list) else [item]
            if not values or any(not isinstance(x, str) or x not in TYPES for x in values):
                raise ProtocolError("unsupported native schema type")
            result[key] = item
        elif key == "required":
            if not isinstance(item, list) or any(not isinstance(x, str) for x in item):
                raise ProtocolError("native required must be a list of field names")
            result[key] = item
        elif key == "enum":
            if not isinstance(item, list) or not item:
                raise ProtocolError("native enum must be a nonempty list")
            result[key] = item
        else:
            result[key] = item
    return result


def _value_shape(expr):
    if not isinstance(expr, dict):
        raise ProtocolError("unsupported input expression")
    if set(expr) <= {"column", "decode"} and "column" in expr:
        if not isinstance(expr["column"], str):
            raise ProtocolError("input column must be a name")
        decode = expr.get("decode", "text")
        if decode == "text":
            return {"type": "string"}
        if decode in ("json", "raw-json", "cell"):
            return {}
        raise ProtocolError("unsupported input decode")
    if set(expr) == {"object"} and isinstance(expr["object"], dict):
        fields = expr["object"]
        return {"type": "object", "properties": {name: _value_shape(child)
                for name, child in fields.items()}, "required": list(fields),
                "additionalProperties": False}
    if set(expr) == {"literal"}:
        value = expr["literal"]
        if value == {}:
            return {"type": "object", "properties": {}, "additionalProperties": False}
        if isinstance(value, (str, bool, int, float)) or value is None:
            return {"const": value}
    raise ProtocolError("input expression needs a structural projection")


def input_shape(value):
    if not isinstance(value, dict) or set(value) - {
            "variant", "when", "case", "group_by", "cells", "arg_file"}:
        raise ProtocolError("unsupported input declaration")
    result = {"variant": value.get("variant", "")}
    if not isinstance(result["variant"], str):
        raise ProtocolError("input variant must be a string")
    condition = owner_condition(value.get("when", "true"))
    if condition is not None:
        result["when"] = condition
    if ("cells" in value) == ("arg_file" in value):
        raise ProtocolError("input needs exactly one transport")
    if "cells" in value:
        cells = value["cells"]
        if not isinstance(cells, dict):
            raise ProtocolError("input cells must be an object")
        result["cells"] = {name: _value_shape(expr) for name, expr in cells.items()}
    else:
        expr = value["arg_file"]
        if not isinstance(expr, dict):
            raise ProtocolError("input file declaration must be an object")
        if set(expr) == {"json"}:
            result["argument_file"] = {"encoding": "json", "schema": _value_shape(expr["json"])}
        elif set(expr) == {"literal"} and expr["literal"] == "{}":
            result["argument_file"] = {"encoding": "json", "schema": _value_shape({"literal": {}})}
        elif set(expr) == {"column"} and isinstance(expr["column"], str):
            result["argument_file"] = {"encoding": "opaque"}
        elif set(expr) == {"path_column", "base"} and expr["base"] == "root" and isinstance(expr["path_column"], str):
            result["argument_file"] = {"encoding": "opaque"}
        else:
            raise ProtocolError("input file declaration needs a structural projection")
    return result


def native_shape(value):
    if not isinstance(value, dict) or set(value) - {"variant", "when", "type", "frame", "schema"}:
        raise ProtocolError("unsupported native declaration")
    if "type" not in value or "frame" not in value:
        raise ProtocolError("native output needs type and frame")
    native_types = value["type"] if isinstance(value["type"], list) else [value["type"]]
    if not native_types or any(x not in TYPES | {"value", "bytes"} for x in native_types):
        raise ProtocolError("unsupported native output type")
    if value["frame"] not in ("json", "json-lf", "raw"):
        raise ProtocolError("unsupported native frame")
    result = {"variant": value.get("variant", ""), "type": value["type"], "frame": value["frame"]}
    if not isinstance(result["variant"], str):
        raise ProtocolError("native variant must be a string")
    condition = owner_condition(value.get("when", "true"))
    if condition is not None:
        result["when"] = condition
    if "schema" in value:
        result["schema"] = _schema(value["schema"])
    return result


def contains_expect_literal(value):
    if isinstance(value, dict):
        return "literal" in value or any(contains_expect_literal(x) for x in value.values())
    return isinstance(value, list) and any(contains_expect_literal(x) for x in value)


def _unique(values):
    by_encoding = {json.dumps(value, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False, allow_nan=False): value for value in values}
    return [by_encoding[key] for key in sorted(by_encoding)]


def structural_row(row):
    surface = row["surface"]
    if surface == "layout":
        if row["inputs"] or row["native"] is not None:
            raise ProtocolError("layout declaration unexpectedly contains a command shape")
        return None
    if surface == "vectors":
        entrypoint = {"surface": "vectors"}
    elif surface.startswith("stand:") and surface[6:]:
        entrypoint = {"surface": "stand", "command": surface[6:]}
    else:
        raise ProtocolError("unsupported command surface")
    if not isinstance(row["package"], str) or not row["package"]:
        raise ProtocolError("package must be a nonempty name")
    native = row["native"]
    native = native if isinstance(native, list) else [native]
    if not row["inputs"] or not native or any(value is None for value in native):
        raise ProtocolError("command needs input and native output declarations")
    return {"package": row["package"], "entrypoint": entrypoint,
            "inputs": _unique(input_shape(value) for value in row["inputs"]),
            "outputs": _unique(native_shape(value) for value in native)}


def merge_structural_rows(values):
    by_entrypoint = {}
    for row in values:
        if row is None:
            continue
        key = (row["package"], json.dumps(row["entrypoint"], sort_keys=True))
        if key not in by_entrypoint:
            by_entrypoint[key] = {"package": row["package"], "entrypoint": row["entrypoint"],
                                  "inputs": [], "outputs": []}
        result = by_entrypoint[key]
        result["inputs"] = _unique(result["inputs"] + row["inputs"])
        result["outputs"] = _unique(result["outputs"] + row["outputs"])
    result = [by_entrypoint[key] for key in sorted(by_entrypoint)]
    for entry in result:
        entry["outputs"] = normalize_native_union(entry["outputs"])
    return result


_QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"')
_OWNER_TOKEN = re.compile(r'\s+|"(?:[^"\\]|\\.)*"|owner\b|true\b|false\b|in\b|==|!=|&&|\|\||[!(),\[\]]')


def owner_condition(condition):
    if not isinstance(condition, str):
        raise ProtocolError("selector must be a string")
    unquoted = _QUOTED.sub('""', condition)
    if re.search(r'\brow\s*\[', unquoted):
        return None
    if condition.strip() == "true":
        return None
    tokens = []
    position = 0
    while position < len(condition):
        token = _OWNER_TOKEN.match(condition, position)
        if token is None:
            raise ProtocolError("selector is neither owner-only nor a row selector")
        position = token.end()
        if not token.group().isspace():
            tokens.append(token.group())
    cursor = 0

    def take(value):
        nonlocal cursor
        if cursor < len(tokens) and tokens[cursor] == value:
            cursor += 1
            return True
        return False

    def string():
        nonlocal cursor
        if cursor >= len(tokens) or not tokens[cursor].startswith('"'):
            raise ProtocolError("owner selector needs a string")
        _load(tokens[cursor], "owner selector")
        cursor += 1

    def atom():
        if take("!"):
            atom()
        elif take("("):
            expression()
            if not take(")"):
                raise ProtocolError("unclosed owner selector")
        elif take("true") or take("false"):
            pass
        elif take("owner"):
            if take("==") or take("!="):
                string()
            elif take("in"):
                if not take("["):
                    raise ProtocolError("owner selector needs a list")
                if not take("]"):
                    string()
                    while take(","):
                        string()
                    if not take("]"):
                        raise ProtocolError("unclosed owner selector list")
            else:
                raise ProtocolError("owner selector needs a comparison")
        else:
            raise ProtocolError("unsupported owner selector atom")

    def conjunction():
        atom()
        while take("&&"):
            atom()

    def expression():
        conjunction()
        while take("||"):
            conjunction()

    expression()
    if cursor != len(tokens):
        raise ProtocolError("extra tokens in owner selector")
    return condition


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _common_constants(maps):
    if not maps:
        return {}
    result = dict(maps[0])
    for other in maps[1:]:
        result = {key: value for key, value in result.items()
                  if key in other and _encoded(value) == _encoded(other[key])}
    return result


def _constants(schema, path=()):
    if isinstance(schema, bool):
        return {}
    result = {}
    if "const" in schema:
        result[path] = schema["const"]
    if "enum" in schema and len(schema["enum"]) == 1:
        result[path] = schema["enum"][0]
    for name, child in schema.get("properties", {}).items():
        result.update(_constants(child, path + ("properties", name)))
    if isinstance(schema.get("items"), (dict, bool)):
        result.update(_constants(schema["items"], path + ("items",)))
    if isinstance(schema.get("additionalProperties"), dict):
        result.update(_constants(schema["additionalProperties"], path + ("additionalProperties",)))
    for kind in ("oneOf", "anyOf"):
        if kind in schema:
            result.update(_common_constants([_constants(child, path) for child in schema[kind]]))
    if "allOf" in schema:
        for child in schema["allOf"]:
            for key, value in _constants(child, path).items():
                if key in result and _encoded(result[key]) != _encoded(value):
                    raise ProtocolError("contradictory native constant declarations")
                result[key] = value
    return result


def _json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise ProtocolError("unsupported JSON value")


def _generalize(schema, stable, path=()):
    if isinstance(schema, bool):
        return schema
    result = dict(schema)
    constants = [schema["const"]] if "const" in schema else schema.get("enum")
    if constants is not None:
        invariant = (len(constants) == 1 and path in stable
                     and _encoded(stable[path]) == _encoded(constants[0]))
        if not invariant:
            result.pop("const", None)
            result.pop("enum", None)
            if "type" not in result:
                types = sorted({_json_type(value) for value in constants})
                result["type"] = types[0] if len(types) == 1 else types
    if "properties" in schema:
        result["properties"] = {name: _generalize(child, stable, path + ("properties", name))
                                for name, child in schema["properties"].items()}
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), (dict, bool)):
            result[key] = _generalize(schema[key], stable, path + (key,))
    for key in ("oneOf", "anyOf", "allOf"):
        if key in schema:
            alternatives = [_generalize(child, stable, path) for child in schema[key]]
            if key == "oneOf":
                result.pop("oneOf", None)
                result["anyOf"] = alternatives
            else:
                result[key] = alternatives
    return result


def normalize_native_union(outputs):
    by_variant = {}
    for value in outputs:
        by_variant.setdefault(value["variant"], []).append(value)
    result = []
    for variant in sorted(by_variant):
        values = by_variant[variant]
        stable = _common_constants([_constants(value.get("schema", {})) for value in values])
        for value in values:
            item = dict(value)
            if "schema" in item:
                item["schema"] = _generalize(item["schema"], stable)
            result.append(item)
    return _unique(result)


CANONICAL_PATH = "Platform/common/vectors/wire.tsv"
PUBLIC_PATH = "Platform/common/contracts/vector-adapter.protocol.json"


def derive(data):
    rows = read_rows(data)
    artifact = {"adapters": merge_structural_rows(structural_row(row) for row in rows)}
    public = (json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2,
                         allow_nan=False) + "\n").encode("utf-8")
    receipt = {"source_sha256": hashlib.sha256(data).hexdigest(), "source_bytes": len(data),
               "source_path": CANONICAL_PATH, "public_path": PUBLIC_PATH,
               "public_sha256": hashlib.sha256(public).hexdigest(), "public_bytes": len(public),
               "source_rows": len(rows), "public_entrypoints": len(artifact["adapters"]),
               "classification": []}
    for row in rows:
        receipt["classification"].append({
            "line": row["_line"], "package": row["package"], "table": row["table"],
            "surface": row["surface"], "layout_only": row["surface"] == "layout",
            "expectation_contains_literal": contains_expect_literal(row["expect"]),
            "private_columns": list(PRIVATE_COLUMNS),
            "input_selectors_removed": sum(owner_condition(value.get("when", "true")) is None
                                            and value.get("when", "true") != "true"
                                            for value in row["inputs"]),
            "policy": "structural adapter retained; expectation and fixture selectors excluded"})
    return public, receipt


def check_consistency(data, public):
    expected, _ = derive(data)
    if public != expected:
        raise ProtocolError("public protocol differs from its canonical derivation")


def main(argv=None):
    import argparse
    import os
    from pathlib import Path
    import subprocess

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--public-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = args.source_root.resolve(strict=True)
    public_root = args.public_root.resolve()
    receipt_path = args.receipt.resolve()
    if receipt_path == public_root or public_root in receipt_path.parents:
        parser.error("derivation receipt must be outside the public tree")
    try:
        def git(*values):
            actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                             text=True).strip()
            if Path(actual).resolve() != root:
                raise ProtocolError("source root is not the exact Git worktree root")
            return subprocess.check_output(["git", "-C", str(root), *values])
        commit = git("rev-parse", "--verify", args.source_ref + "^{commit}").decode().strip()
        entry = git("ls-tree", commit, "--", CANONICAL_PATH).decode().strip().split()
        if len(entry) != 4 or entry[0:2] != ["100644", "blob"] or entry[3] != CANONICAL_PATH:
            raise ProtocolError("canonical input is not its declared regular Git blob")
        data = git("show", commit + ":" + CANONICAL_PATH)
        public, receipt = derive(data)
        target = public_root / PUBLIC_PATH
        if public_root not in target.resolve().parents:
            raise ProtocolError("public artifact escapes the public tree")
        if args.check:
            check_consistency(data, target.read_bytes())
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(public)
                stream.flush()
                os.fsync(stream.fileno())
        receipt.update({"source_commit": commit, "source_blob": entry[2],
                        "deriver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        "consistency": "MATCH", "mode": "check" if args.check else "derive"})
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        print(json.dumps({"artifact": str(target), "status": "MATCH"}, sort_keys=True))
    except (ProtocolError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"vector protocol: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
