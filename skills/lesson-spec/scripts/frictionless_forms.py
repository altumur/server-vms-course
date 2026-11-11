"""Validate the selected course TSV forms with Frictionless Table Schema.

Only physical UTF-8/LF/TAB transport and Source identity are handled here.
Columns, cells, constraints, primary keys and foreign keys are judged by the
pinned framework. Existing semantic readers still receive the original files.
"""
import copy
from importlib import metadata
import json
from pathlib import Path
import re

ENGINE_VERSION = "5.18.1"
PACKAGE = "Platform/forms.datapackage.json"
RESOURCES = {
    "stages_p01": "01-store/forms/stages.tsv",
    "stages_kit_p01": "01-store/forms/stages.kit.tsv",
    "code_rules_p01": "01-store/forms/code-rules.tsv",
    "code_kinds": "common/acceptance/forms/code-rules.tsv",
    "daemon_flags_p01": "01-store/forms/daemon-flags.tsv",
    "refusals_p01": "01-store/forms/refusals.tsv",
    "runtime_constants_p01": "01-store/forms/runtime-constants.tsv",
    "write_checks_p01": "01-store/forms/write-checks.tsv",
    "write_checks_probes_p01": "01-store/forms/write-checks.probes.tsv",
    "engine_code_rules": "common/acceptance/forms/engine-code-rules.tsv",
}


class FormInputError(ValueError):
    pass


def _ordinary(root, relative):
    if not isinstance(relative, str):
        raise FormInputError("form metadata path is not a string")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise FormInputError(f"{relative}: form metadata path is not local to the Source root")
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise FormInputError(f"{current}: a form Source input is a symbolic link")
    if not current.is_file():
        raise FormInputError(f"{current}: expected an ordinary form Source file")
    return current


def _unique_object(pairs):
    out = {}
    for name, value in pairs:
        if name in out:
            raise ValueError(f"duplicate JSON metadata key {name!r}")
        out[name] = value
    return out


def _nonfinite(word):
    raise ValueError(f"non-finite JSON metadata value {word}")


def _read_json(path):
    try:
        return json.loads(path.read_bytes().decode("utf-8"),
                          object_pairs_hook=_unique_object,
                          parse_constant=_nonfinite)
    except (OSError, UnicodeError, ValueError) as exc:
        raise FormInputError(f"{path}: invalid form metadata JSON: {exc}") from exc


def prepare(root):
    """Load every declared known resource, preserving physical row numbers."""
    root = Path(root).resolve()
    descriptor_path = _ordinary(root, PACKAGE)
    source = _read_json(descriptor_path)
    if not isinstance(source, dict) or not isinstance(source.get("resources"), list):
        raise FormInputError(f"{descriptor_path}: expected the selected form data package")
    names = [item.get("name") for item in source["resources"] if isinstance(item, dict)]
    if len(names) != len(source["resources"]) or any(not isinstance(name, str) for name in names) or \
            len(names) != len(set(names)) or set(names) != set(RESOURCES):
        raise FormInputError(f"{descriptor_path}: resources differ from the selected form group")
    prepared = copy.deepcopy(source)
    physical = {}
    for resource in prepared["resources"]:
        name = resource["name"]
        relative = RESOURCES[name]
        if resource.get("path") != relative or resource.get("schema") != relative + ".schema.json":
            raise FormInputError(f"{descriptor_path}: wrong Source path or schema for {name}")
        if "data" in resource or resource.get("format") != "tsv" or resource.get("encoding") != "utf-8" or \
                resource.get("type", "table") != "table":
            raise FormInputError(f"{descriptor_path}: {name} is not the declared physical UTF-8 TSV resource")
        dialect = resource.get("dialect")
        if not isinstance(dialect, dict) or dialect.get("commentChar") != "#" or \
                not isinstance(dialect.get("csv"), dict) or dialect["csv"].get("delimiter") != "\t":
            raise FormInputError(f"{descriptor_path}: {name} has no declared literal TAB/comment transport")
        path = _ordinary(root, "Platform/" + relative)
        schema_path = _ordinary(root, "Platform/" + relative + ".schema.json")
        schema = _read_json(schema_path)
        if not isinstance(schema, dict) or not isinstance(schema.get("fields"), list) or \
                any(not isinstance(field, dict) or field.get("type") != "string"
                    for field in schema["fields"]):
            raise FormInputError(f"{schema_path}: expected Table Schema fields with raw string types")
        try:
            lines = path.read_bytes().decode("utf-8").split("\n")
        except (OSError, UnicodeError) as exc:
            raise FormInputError(f"{path}: unreadable UTF-8 form: {exc}") from exc
        if lines and lines[-1] == "":
            lines.pop()
        header = next((number for number, line in enumerate(lines, 1)
                       if line and not line.startswith("#")), None)
        declared = dialect.get("headerRows")
        if header is None or declared != [header] or \
                any(type(number) is not int for number in declared):
            raise FormInputError(f"{descriptor_path}: {name}: headerRows must equal physical header [{header}]")
        physical[name] = {
            "path": path,
            "header": header,
            "columns": lines[header - 1].split("\t"),
            "rows": [line.split("\t") for line in lines[header:]
                     if line and not line.startswith("#")],
        }
        # Inline arrays retain every original physical row, including comments,
        # and preserve headerRows. Literal TSV does not have CSV quote syntax:
        # no column-width decision is made by this transport step.
        resource["data"] = [line.split("\t") for line in lines]
        resource["schema"] = schema
        del resource["path"]
        resource["format"] = "inline"
    return prepared, physical


def check(root, *, tables=None):
    try:
        actual = metadata.version("frictionless")
    except metadata.PackageNotFoundError:
        return [f"form environment: frictionless is missing, pinned {ENGINE_VERSION}"], {}
    if actual != ENGINE_VERSION:
        return [f"form environment: frictionless {actual}, pinned {ENGINE_VERSION}"], {}
    try:
        from frictionless import validate
        descriptor, physical = prepare(root)
    except (FormInputError, ImportError) as exc:
        return [str(exc)], {}
    try:
        report = validate(descriptor)
    except re.error as exc:
        return [f"{PACKAGE}: Frictionless table-schema pattern is invalid: {exc}"], {}
    errors = [f"{PACKAGE}: Frictionless {error.type}: {error.message}" for error in report.errors]
    task_names = [task.name for task in report.tasks]
    if len(task_names) != len(physical) or set(task_names) != set(physical):
        errors.append(f"{PACKAGE}: Frictionless did not validate all declared form resources")
    if any(task.type != "table" for task in report.tasks):
        errors.append(f"{PACKAGE}: Frictionless did not use table validation for every selected resource")
    for task in report.tasks:
        path = physical[task.name]["path"] if task.name in physical else PACKAGE
        for error in task.errors:
            errors.append(f"{path}: Frictionless {error.type}: {error.message}")
    stats = {"standard_form_tables": len(report.tasks),
             "standard_form_rows": sum(task.stats.get("rows", 0) for task in report.tasks)}
    if not report.valid and not errors:
        errors.append(f"{PACKAGE}: Frictionless reported an invalid form package")
    if not errors and tables is not None:
        for table in physical.values():
            tables[table["path"]] = table
    return errors, stats
