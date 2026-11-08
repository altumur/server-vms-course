"""Preserve existing family-read cases across the published P08 form changes.

This is a source migration, not a judge: no observed implementation result is used
as an expectation. transition owns the TSV wire. The corpus keeps its IDs and
mutations; only newly required baseline fields and explicitly changed reader
rules are migrated. A ledger records every changed cell for review.
"""
import hashlib
import json
from pathlib import Path

from v7 import spec

REVISION_FAMILIES = {
    "domain/users/<name>": "users",
    "domain/grants/<cluster>": "grants",
    "domain/break-glass/<cluster>": "break-glass",
    "domain/groups/<name>": "groups",
    "domain/roles/<name>": "roles",
    "domain/folders/<id>": "domain-folders",
}


def pending_reader_outcomes(rules, paths, who):
    """Resolve pending root/name/seq outcomes from public table cells, not a judge.

    A named-element outcome replaces its root fallback for that child alone.
    An independent root refusal still participates in the final priority choice.
    """
    rows, properties = rules["rows"], rules["properties"]
    result = {}
    for role in who:
        selected = set()
        for path in paths:
            name = path.split("/")[1] if path.startswith("/") else None
            applicable = [i for i, row in enumerate(rows) if row[1] in {role, "*"} and (
                row[0] == "" or row[0] == path or
                (row[0] == "/*" and name is not None and name not in properties))]
            depth = max((rows[i][0].count("/") for i in applicable), default=0)
            deepest = [i for i in applicable if rows[i][0].count("/") == depth]
            selected.update(deepest if any(rows[i][4] != "row" for i in deepest) else applicable)
        if selected:
            priority = min(int(rows[i][3]) for i in selected)
            result[role] = [row[0] for i, row in enumerate(rows) if i in selected and int(row[3]) == priority]
        else:
            result[role] = []
    return result


def source_rules(root):
    """Require the exact public rules this migration implements before any write."""
    home = Path(root) / "Platform/08-domain"
    sources = {}
    revision_outcomes = {}

    def read(relative):
        path = home / relative
        raw = path.read_bytes()
        sources[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
        return raw.decode("utf-8")

    norms = read("spec/08.0-domain.norms.md")
    if "An existing row without the field or with an unreadable field is unreadable by its current family" not in norms:
        raise ValueError("P08.0 N1.9 existing-row revision rule is missing")
    for family, name in REVISION_FAMILIES.items():
        doc = json.loads(read("data/" + name + ".schema.json"))
        if "revision" not in doc.get("required", []):
            raise ValueError(name + ": revision must be required by the current public schema")
        prop = doc["properties"]["revision"]
        if (prop.get("x-codec") != ["integer"] or not prop.get("x-whole") or prop.get("$ref") != "#/$defs/common.pos53"
                or doc["$defs"]["common.pos53"].get("minimum") != 1):
            raise ValueError(name + ": current revision is a positive whole item integer")
        outcomes = read("data/" + name + ".outcomes.tsv")
        rows = [line.split("\t") for line in outcomes.splitlines() if line and not line.startswith("#")][1:]
        if name != "domain-folders" and not any(r[0] == "/revision" and r[4] == "row" for r in rows):
            raise ValueError(name + ": revision must use the whole-row unreadable outcome")
        if name in {"groups", "roles"} and not all(r[3:5] == ["0", "row"] for r in rows if r[0] == ""):
            raise ValueError(name + ": whole-row outcomes must have priority zero")
        roles = [r[1] for r in rows if r[0] == ""]
        revision_outcomes[family] = {}
        for role in roles:
            applicable = [r for r in rows if r[0] in {"", "/revision"} and r[1] in {role, "*"}]
            priority = min(int(r[3]) for r in applicable)
            revision_outcomes[family][role] = [r[0] for r in applicable if int(r[3]) == priority]
    for name in ("pending", "outcomes"):
        doc = json.loads(read("data/" + name + ".schema.json"))
        if doc.get("x-max-names") != 50:
            raise ValueError(name + ": current reader root name bound must be 50")
    pending_doc = json.loads(read("data/pending.schema.json"))
    pending_rows = [line.split("\t") for line in read("data/pending.outcomes.tsv").splitlines()
                    if line and not line.startswith("#")]
    if pending_rows[0] != ["path", "reader", "outcome", "priority", "unit", "norm"]:
        raise ValueError("pending: current outcomes header is required")
    # Validate the published table with the unchanged strict input loader;
    # expectation selection below still uses only its explicit public cells.
    spec.load_outcomes(home / "data/pending.outcomes.tsv", pending_doc)
    pending_rows = pending_rows[1:]
    if any(len(row) != 6 or row[0] not in {"", "/*", "/seq"} or not row[3].isdigit()
           or row[4] not in spec.UNITS for row in pending_rows):
        raise ValueError("pending: expected public root, name and counter outcome rows")
    revision_outcomes["domain/pending/<member>"] = {
        "rows": pending_rows, "properties": list(pending_doc.get("properties", {}))}
    if "The reader and writer use the same current family bound" not in read("spec/08.6-domain.norms.md"):
        raise ValueError("P08.6 current reader family bound is missing")
    doc = json.loads(read("data/view.schema.json"))
    knock = doc["$defs"]["knock"]
    if "class" not in knock["required"] or knock["properties"]["class"]["enum"] != ["server", "camera"]:
        raise ValueError("view.knocking: class must be required, server or camera")
    if "class retained by the report-reception knock owner" not in read("spec/08.1-domain.norms.md"):
        raise ValueError("P08.1 current knocking.class rule is missing")
    doc = json.loads(read("data/alarm-history.schema.json"))
    maximum = doc["properties"]["events"].get("maxItems")
    if maximum != 2000 or "The reader and writer both apply HISTORY_LINES to events" not in read("spec/08.9-domain.norms.md"):
        raise ValueError("alarm-history: current reader and writer must both apply HISTORY_LINES=2000")
    return sources, maximum, revision_outcomes


def migrated(row, maximum, revision_outcomes):
    """One row under those explicit source rules; return a copy, retaining its mutation."""
    out = dict(row)
    family, mode, case = row["family"], row["mode"], row["case"]
    if family in REVISION_FAMILIES:
        # The two deliberate missing-revision controls retain their missing field.
        absent = case in {"g08-groups-revision-absent-" + mode, "g08-roles-revision-absent-" + mode}
        try:
            value = json.loads(row["text"])
        except ValueError:
            value = None
        if isinstance(value, dict) and "revision" not in value and not absent:
            end = len(row["text"].rstrip()) - 1
            out["text"] = row["text"][:end] + ("," if value else "") + '"revision":"1"' + row["text"][end:]
        # Current priority and row units come from the published outcome table,
        # independently of Family.judge and spec.outcomes_for.
        if absent and mode == "reader":
            out["verdict"] = "refused"
            out["paths"] = json.dumps(["/revision"])
        if mode == "reader" and json.loads(out["paths"]) == ["/revision"]:
            out["outcome"] = json.dumps({role: revision_outcomes[family][role]
                                          for role in json.loads(row["who"])}, ensure_ascii=False)
    if family == "domain/view" and row["note"] == ": optional knocking":
        value = json.loads(row["text"])
        if any("class" not in knock for knock in value["knocking"]):
            if len(value["knocking"]) != 1 or '"knocking":[{' not in row["text"]:
                raise ValueError("unexpected optional-knocking baseline representation")
            out["text"] = row["text"].replace('"knocking":[{', '"knocking":[{"class":"server",', 1)
    if family == "domain/alarm-history/<member>" and mode == "reader" and row["note"] == "events: max_items":
        value = json.loads(row["text"])
        if len(value["events"]) > maximum:
            out["verdict"] = "refused"
            out["paths"] = json.dumps(["/events"])
            out["outcome"] = json.dumps({role: [""] for role in json.loads(row["who"])}, ensure_ascii=False)
    if (family in {"domain/pending/<member>", "domain/outcomes/<member>"}
            and mode == "reader" and row["note"] == ": names over max_items"):
        value = json.loads(row["text"])
        if len(set(value) - ({"seq"} if family == "domain/pending/<member>" else set())) > 50:
            paths = json.loads(row["paths"])
            if "" not in paths:
                out["paths"] = json.dumps([""] + paths)
            if family == "domain/pending/<member>":
                out["outcome"] = json.dumps(pending_reader_outcomes(
                    revision_outcomes[family], json.loads(out["paths"]), json.loads(row["who"])), ensure_ascii=False)
            # The outcomes family already has a whole-row outcome. Pending uses
            # its actual published root/name priorities, including combined faults.
    return out


def refresh(root, ledger):
    """Write only 08.tsv, after validating sources; keep a complete per-cell ledger."""
    from v7.transition import tsv, write_tsv
    root = Path(root).resolve()
    ledger_path = Path(ledger).absolute()
    ledger_target = ledger_path.resolve()
    if ledger_path.is_relative_to(root) or ledger_target.is_relative_to(root):
        raise ValueError("family-read proof ledger must be outside the course root")
    if not ledger_target.parent.is_dir():
        raise ValueError("family-read proof ledger parent directory must exist")
    sources, maximum, revision_outcomes = source_rules(root)
    path = root / spec.FAMILY_READ / "08.tsv"
    old = path.read_bytes()
    records = tsv(path)
    if records[0] != spec.FR_HEADER:
        raise ValueError("08.tsv: expected the current family-read header")
    rows = [dict(zip(spec.FR_HEADER, cols, strict=True)) for cols in records[1:]]
    if len({r["case"] for r in rows}) != len(rows):
        raise ValueError("08.tsv: case IDs must be unique")
    changed, built = [], []
    for row in rows:
        new = migrated(row, maximum, revision_outcomes)
        cells = {k: {"old": row[k], "new": new[k]} for k in spec.FR_HEADER if row[k] != new[k]}
        if cells:
            rules = []
            if row["family"] in REVISION_FAMILIES:
                rules.append({"norm": "Platform/08-domain/spec/08.0-domain.norms.md:95",
                              "schema": "Platform/08-domain/data/" + REVISION_FAMILIES[row["family"]] + ".schema.json#/required",
                              "outcomes": "Platform/08-domain/data/" + REVISION_FAMILIES[row["family"]] + ".outcomes.tsv"})
            elif row["family"] == "domain/view":
                rules.append({"norm": "Platform/08-domain/spec/08.1-domain.norms.md:391",
                              "schema": "Platform/08-domain/data/view.schema.json#/$defs/knock/required"})
            elif row["family"] == "domain/alarm-history/<member>":
                rules.append({"norm": "Platform/08-domain/spec/08.9-domain.norms.md:264",
                              "schema": "Platform/08-domain/data/alarm-history.schema.json#/properties/events/maxItems"})
            else:
                name = "pending" if row["family"] == "domain/pending/<member>" else "outcomes"
                rules.append({"norm": "Platform/08-domain/spec/08.6-domain.norms.md:383",
                              "schema": "Platform/08-domain/data/" + name + ".schema.json#/x-max-names",
                              "outcomes": "Platform/08-domain/data/" + name + ".outcomes.tsv"})
            changed.append({"case": row["case"], "family": row["family"], "mode": row["mode"],
                            "note": row["note"], "public_rules": rules, "cells": cells})
        built.append([new[k] for k in spec.FR_HEADER])
    write_tsv(path, [], spec.FR_HEADER, built)
    proof = {"sources": sources, "table": str(path.relative_to(root)), "rows_before": len(rows),
             "rows_after": len(built), "roster_sha256": hashlib.sha256("\n".join(r["case"] for r in rows).encode()).hexdigest(),
             "old_sha256": hashlib.sha256(old).hexdigest(), "new_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
             "changes": changed}
    ledger_target.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"rows": len(rows), "changed": len(changed), "ledger": str(ledger)}
