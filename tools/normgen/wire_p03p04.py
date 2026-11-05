"""Черновик провода векторов P/03, P/04 для gen_vectors.WIRE — ВРЕМЕННАЯ ПРОЕКЦИЯ (ADR-0125 доп. (5) п. 5).

Форма Platform/common/vectors/wire.tsv ещё не опубликована (spec103 2026-11-05: «черновик WIRE по каноническим README …
пометь временной проекцией с точными источниками; после публикации общей формы черновик заменяется ею, без второго
канона»). Объявления выписаны из README пакетов (Platform/common/vectors/<пакет>/README.md, Platform/0N-*/vectors/<пакет>/
README.md), общего README приёмки («Vectors», «The unified command of a vector package», «Platform vector commands») и
сверены с раннером cammeta-acceptance cc17c86 (c_*.py); источники — в `src` каждого объявления; сводка и открытые
вопросы — /home/pilot/wire-p03p04-draft.md (на сверку spec103). Пакеты P/01 (crl, revoked, log-mask, store-client,
family-read) идут через common_vectors.py, как у P/02.

Объявление — как у gen_vectors.WIRE: surface vectors | stand:<ключ>; inputs — cells; files — фикстуры (путь от пакета
или «@root/<путь>»); select(r) — True или причина исключения строки; frames(r) — половины строки (values-by-type);
expect(r, d) → (код, значение | None, сырые байты | None); compare — value | raw | subset | fields:<a,b> | setarrays |
events | row | secret | turn | vbt-write (правила — README пакета, Go — gen_vectors.COMPARE_GO).
"""
import json


def jv(c):
    """Ячейка — значение JSON, если это JSON; иначе — JSON-строка (слово, маркер) — общее правило «Vectors»."""
    try:
        return json.loads(c)
    except ValueError:
        return c


def or_exit2(r, d, col="expect"):
    return (2, None, None) if r[col] == "@exit 2" else (0, jv(r[col]), None)


def value(col="expect"):
    return lambda r, d: (0, jv(r[col]), None)


def by_input(field, allowed):
    def sel(r):
        v = json.loads(r["input"]).get(field)
        return True if v in allowed else f"{field} {v!r}: not this consumer (README «Who performs it»)"
    return sel


def worker_participant(r):
    """events-merge README «Who performs»: participant {"worker": […]} — the worker; "console" — the console."""
    p = json.loads(r["input"]).get("participant")
    return True if isinstance(p, dict) and "worker" in p else f"participant {p!r}: the console's row"


def by_col(col, allowed, why="not this consumer (README «Who performs it»)"):
    return lambda r: True if r[col] in allowed else f"{col} {r[col]!r}: {why}"


# --- общие объявления по пакету (урок добавляет выбор и сравнение) ---

def instance(table):
    return {"package": "common/instance", "table": table, "surface": "vectors", "fn": "Instance", "args": "cells",
            "inputs": ["input"], "compare": "value", "expect": value(),
            "doc": "the instance contract: box.tsv → {box, source} or \"@refuse\"; cases.tsv → {instance} or \"@refuse\" "
                   "(code 0, not 2 — README «Native outcome»)",
            "src": "instance/README.md:9-24,30-36; runner c_resource_vectors.py:36-37,57-58"}


def journal(table, inputs):
    return {"package": "common/journal", "table": table, "surface": "vectors", "fn": "Journal", "args": "cells",
            "inputs": inputs, "compare": "value", "expect": value(),
            "doc": "the journal contract by table: append.tsv → the bucket text after the write or \"@refuse\"; names.tsv → "
                   "the component, \"@skip\", or the words write/keep/refuse; years.tsv → the bucket name or \"@refuse\"",
            "src": "journal/README.md:23-42,56-71; runner c_resource_vectors.py:27,36-47,63-66,162-163"}


def labels(ops):
    return {"package": "common/labels", "table": "cases.tsv", "surface": "vectors", "fn": "Labels", "args": "cells",
            "inputs": ["op", "input"], "select": by_col("op", ops), "compare": "setarrays", "expect": value(),
            "doc": "the label contract by op: label → \"ok\" | \"@refuse\"; set_write → the text; text_read, env_labels → "
                   "the list of labels (compared as a set)",
            "src": "labels/README.md:13-23,32-40; runner c_resource_vectors.py:13-14,38-39,138-140,167-168,186-190"}


def object_client(table):
    return {"package": "common/object-client", "table": table, "surface": "vectors", "fn": "ObjectClient",
            "args": "cells", "inputs": ["input"], "compare": "value", "expect": or_exit2,
            "doc": "the object client contract: address.tsv → {kind, dir[, door][, resource]} or code 2; read.tsv → "
                   "\"object\" | \"absent\" | \"unknown\" | \"refused\"",
            "src": "object-client/README.md:8-36; acceptance/README.md:46-50; runner c_resource_vectors.py:32-33,57-66"}


LOOPBACK = {"package": "common/loopback", "table": "cases.tsv", "surface": "vectors", "fn": "Loopback", "args": "cells",
            "inputs": ["input"], "compare": "value", "expect": or_exit2,
            "doc": "the kind of an address of the own cluster: \"loopback\", \"ip\" or \"name\"; code 2 — not an address",
            "src": "loopback/README.md:32-36; runner c_resource_extras.py:30-47"}

ROW_STATE = {"package": "common/row-check", "table": "state.tsv", "surface": "vectors", "fn": "RowCheck", "args": "cells",
             "inputs": ["name", "unit", "state"], "files": {"testsub2.subsystem.yaml": "@root/Source/tests/testdata/testsub2.subsystem.yaml"},
             "compare": "value", "expect": value(),
             "src": "row-check/README.md:56-78; runner c_value_vectors.py:132-138,273-274"}

SCHEMA = {"package": "common/schema", "table": "cases.tsv", "surface": "vectors", "fn": "Schema", "args": "cells",
          "inputs": ["input"], "compare": "value", "expect": value(),
          "doc": "the schema start check: {start: true, version} | {refuse: \"too_new\", n} | {refuse: \"not_a_form\"} (code 0)",
          "src": "schema/README.md:11-26; runner c_resource_vectors.py:15,57,117,168-173"}


def slot(compare):
    return {"package": "common/slot", "table": "cases.tsv", "surface": "vectors", "fn": "Slot", "args": "cells",
            "inputs": ["input"], "compare": compare, "expect": value(),
            "doc": "the slot state of a row: {state[, takeable]} (takeable only at torn)",
            "src": "slot/README.md:11-25; runner c_env_slot_vectors.py:46,71-84"}


def slot_name(ops):
    return {"package": "common/slot-name", "table": "cases.tsv", "surface": "vectors", "fn": "SlotName", "args": "cells",
            "inputs": ["op", "input"], "select": by_col("op", ops), "compare": "value", "expect": value(),
            "doc": "the slot name contract by op: order → the names in order; next → the next name; role → {server, n} | "
                   "\"not_role\"",
            "src": "slot-name/README.md:11-27; runner c_observation_vectors.py:10-12,58,76-93"}


def secret_hidden(raw, masked):
    """Скрытые части raw: подстроки, которые masked закрывает «***» (секция «Native outcome», п. 3), от 4 байт."""
    parts, pos, hidden = masked.split("***"), 0, []
    if len(parts) == 1:
        return []
    for k, part in enumerate(parts):
        at = raw.find(part, pos) if k else (0 if raw.startswith(part) else -1)
        if at < 0:
            return []                                  # выравнивание не нашлось — проверяется только fault
        if k:
            gap = raw[pos:at]
            if len(gap.encode("utf-8")) >= 4:
                hidden.append(gap)
        pos = at + len(part)
    if parts[-1] == "" and pos < len(raw):
        gap = raw[pos:]
        if len(gap.encode("utf-8")) >= 4:
            hidden.append(gap)
    return hidden


def secret_in(item):
    if item == "refusal":
        exp = lambda r, d: (0, {"fault": r["fault"], "hidden": secret_hidden(r["raw"], r["masked"])}, None)  # noqa: E731
        compare = "secret"
    else:
        exp = lambda r, d: (0, {"masked": r["masked"]}, None)  # noqa: E731
        compare = "value"
    return {"package": "common/secret-in", "table": "cases.tsv", "surface": "vectors", "fn": "SecretIn", "args": "cells",
            "header": None, "fields": ["field", "raw", "masked", "fault", "note"], "inputs": ["field", "raw"],
            "files": {"fields.yaml": "fields.yaml"}, "compare": compare, "expect": exp,
            "doc": "the credentials of an address: the display (item 1) → {masked}; the refusal (items 2-3) → {fault[, text]} "
                   "(text only at a non-empty fault, never repeating the password of the row)",
            "src": "secret-in/README.md:14-23,46-63; runner c_value_vectors.py:20-21,92-117,254-264,317-332"}


def values_by_type(halves):
    def frames(r):
        out = []
        if "@sealed" in (r["json"], r["row"]):
            return out                                 # только консоль (README «Who performs it»)
        dirs = ["write", "read"] if r["dir"] == "both" else [r["dir"]]
        for v in dirs:
            if v not in halves:
                continue
            if v == "write":
                cell = r["row"]
                if cell == "@absent":
                    exp = {"status": "absent"}
                elif cell.startswith("@refuse"):
                    exp = {"status": "refused"}
                    if cell.startswith("@refuse "):
                        exp["fault"] = cell[len("@refuse "):]
                elif cell.startswith("@json "):
                    exp = {"status": "ok", "rowjson": json.loads(cell[len("@json "):])}
                else:
                    exp = {"status": "ok", "row": json.loads(cell)}
                out.append(("write", {"type": r["type"], "json": r["json"]}, (0, exp, None), "vbt-write"))
            else:
                cell = r["json"]
                if cell == "@unset":
                    exp = {"status": "absent"}
                elif cell == "@unreadable":
                    exp = {"status": "unreadable"}
                else:
                    exp = {"status": "ok", "value": json.loads(cell)}
                out.append(("read", {"type": r["type"], "row": r["row"]}, (0, exp, None), "value"))
        return out
    return {"package": "common/values-by-type", "table": "cases.tsv", "surface": "vectors", "fn": "ValuesByType",
            "args": "cells+variant", "inputs": ["type", "json", "row"], "frames": frames,
            "select": lambda r: True if "@sealed" not in (r["json"], r["row"]) else "@sealed: only the console seals",
            "compare": "value", "expect": None,          # сравнение — у половины (frames)
            "doc": "values by type, one frame per half of a row: write {type, json} → {status: ok, row} | {status: absent} | "
                   "{status: refused[, fault]}; read {type, row} → {status: ok, value} | {status: absent} | {status: unreadable}",
            "src": "values-by-type/README.md:15-24,42-80; runner c_value_vectors.py:139-159,219-238,335-366"}


def group_of(compare):
    return {"package": "common/group-of", "table": "cases.tsv", "surface": "stand:group-of", "fn": "GroupOf",
            "args": "input", "header": None, "fields": ["raw", "group", "fault"], "input": "raw", "compare": compare,
            "expect": lambda r, d: (0, {"group": "" if r["group"] == "<none>" else r["group"],
                                        "fault": "" if r["fault"] in ("<none>", "") else r["fault"]}, None),
            "doc": "the group of a source address: {group, fault} (\"\" — none; fault bad_url or \"\")",
            "src": "group-of/README.md:13-30; runner c_targets.py:102-109, c_sdk_json.py:199-211,268-281"}


HEARTBEAT_CASES = {"package": "common/heartbeat-read", "table": "cases.tsv", "surface": "vectors", "fn": "HeartbeatRead",
                   "args": "cells", "inputs": ["object"], "compare": "value", "expect": value(),
                   "doc": "the reading of a heartbeat: cases.tsv → {readable[, fields]}; worker.tsv → {rows, others, fields}",
                   "src": "heartbeat-read/README.md:11-52; runner c_state_vectors.py:15-25,81-87,122-137"}


def ring_select(r):
    return True if not r["case"].startswith("rotate") else "rotate*: only 02-installer (sealing README «Who performs it»)"


SEALING = [
    {"package": "common/sealing", "table": "aad.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
     "inputs": ["row_key", "path"], "compare": "value",
     "expect": lambda r, d: (0, {"pointer": r["pointer"], "aad_hex": r["aad_hex"]}, None),
     "doc": "the sealing contract (the worker only opens): aad.tsv → {pointer, aad_hex}; open.tsv → \"sealed\" or the value "
            "of expect; ring.tsv → the word or value of expect",
     "src": "sealing/README.md:24-40; runner c_value_vectors.py:177-201"},
    {"package": "common/sealing", "table": "open.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
     "inputs": ["key_hex", "envelope", "row_key", "pointer"], "compare": "value",
     "expect": lambda r, d: (0, "sealed" if r["expect"] == "sealed" else jv(r["expect"]), None)},
    {"package": "common/sealing", "table": "ring.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
     "inputs": ["file"], "select": ring_select, "compare": "value", "expect": lambda r, d: (0, r["expect"], None)},
]


def door_token_verify_input(r):
    """README door-token «door-token-verify»: {keys, now — JSON ячеек; authorization, unit, holder, path — строки}."""
    obj = {"keys": json.loads(r["keys"]), "now": json.loads(r["now"]), "authorization": r["authorization"],
           "unit": r["unit"], "holder": r["holder"], "path": r["path"]}
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def door_token_expect(r, d):
    return (0, {"result": "ok", "claims": json.loads(r["claims"])} if r["expect"] == "ok" else {"result": "forbidden"},
            None)


WIRE = {
    "03-worker": [
        {"package": "common/domain-token", "table": "cases.tsv", "surface": "vectors", "fn": "DomainToken",
         "args": "cells", "inputs": ["input"], "compare": "subset", "expect": or_exit2,
         "doc": "the domain token check: {result: ok, payload} | {result: refused, reason} (subset), code 2 — out of form",
         "src": "domain-token/README.md:21-24,55-74; runner c_value_vectors.py:160-167,363-364"},
        {"package": "common/door-token", "table": "verify.tsv", "surface": "stand:door-token-verify", "fn": "DoorToken",
         "args": "input", "input": door_token_verify_input, "compare": "value", "expect": door_token_expect,
         "doc": "the door token check (stand door-token-verify): {result: ok, claims} | {result: forbidden}; {input} — "
                "verify.tsv: {keys, authorization, now, unit, holder, path}; place.tsv: the cell input as it is",
         "src": "door-token/README.md:15-44,69-70; runner c_targets.py:81-85, c_door_token.py:85-124"},
        {"package": "common/door-token", "table": "place.tsv", "surface": "stand:door-token-verify", "fn": "DoorToken",
         "args": "input", "input": "input", "compare": "value", "expect": door_token_expect},
        {"package": "common/events-merge", "table": "cases.tsv", "surface": "vectors", "fn": "EventsMerge",
         "args": "cells", "inputs": ["input"], "select": worker_participant, "compare": "events",
         "expect": value(),
         "doc": "the merge of events of the worker: {events, state, truncated, …}; expect is a subset, events element by "
                "element by their listed fields",
         "src": "events-merge/README.md:12-41; runner c_events_merge.py:32-89"},
        group_of("value"),
        instance("box.tsv"), instance("cases.tsv"),
        journal("append.tsv", ["file", "line"]), journal("names.tsv", ["input"]), journal("years.tsv", ["t"]),
        labels(("label", "env_labels")),
        LOOPBACK,
        object_client("address.tsv"), object_client("read.tsv"),
        {"package": "common/row-check", "table": "cases.tsv", "surface": "vectors", "fn": "RowCheck", "args": "cells",
         "inputs": ["unit", "op", "body", "stored", "rows"],
         "files": {"testsub.subsystem.yaml": "@root/Source/tests/testdata/testsub.subsystem.yaml",
                   "testsub2.subsystem.yaml": "@root/Source/tests/testdata/testsub2.subsystem.yaml"},
         "select": by_col("unit", ("testsub2/tallies",), "only the console (the worker writes testsub2/tallies)"),
         "compare": "row",
         "expect": lambda r, d: (0, dict({"result": r["expect"]},
                                         **({"row": json.loads(r["row"])} if r["expect"] == "ok" and r["row"] else {}),
                                         **({"word": r["word"], "field": r["field"] or "@absent"}
                                            if r["expect"] == "refused" else {})), None),
         "doc": "the preparation and check of a row: {result: ok, row: {element: text}} | {result: refused, word[, field]}",
         "src": "row-check/README.md:11-54; runner c_value_vectors.py:22-24,118-131,289-314"},
        ROW_STATE,
        {"package": "common/said-id", "table": "said.tsv", "surface": "stand:said-id", "fn": "SaidID", "args": "input",
         "input": "rid", "compare": "value", "expect": value("said"),
         "doc": "the said id of a request id (stand said-id): the SaidID as a JSON string",
         "src": "said-id/README.md:27-61; acceptance/README.md:162-164; runner c_targets.py:102-111, c_sdk_json.py:224-247"},
        SCHEMA,
        secret_in("refusal"),
        *SEALING,
        slot("value"),
        slot_name(("order", "next")),
        values_by_type(("write", "read")),
        {"package": "03-worker/creates-key", "table": "cases.tsv", "surface": "stand:creates-key", "fn": "CreatesKey",
         "args": "input", "input": "input", "compare": "raw",
         "expect": lambda r, d: (0, None, r["expect"].encode("utf-8")),
         "doc": "the id of a created row (stand creates-key): stdout — the id bytes exactly, no LF, no JSON",
         "src": "03-worker/vectors/creates-key/README.md:9-33; acceptance/README.md:40-49 (runner: vectors frame — open "
                "question 1 of the draft)"},
    ],
    "04-controller": [
        {"package": "common/fresh-age", "table": "fresh.tsv", "surface": "stand:fresh-age", "fn": "FreshAge",
         "args": "input", "input": "age", "compare": "value", "expect": value("fresh"),
         "doc": "the freshness of an age (stand fresh-age): true | false",
         "src": "fresh-age/README.md:28-55; runner c_targets.py:102-109, c_sdk_json.py:50-51,268-270"},
        group_of("fields:group"),
        HEARTBEAT_CASES,
        {"package": "common/heartbeat-read", "table": "worker.tsv", "surface": "vectors", "fn": "HeartbeatRead",
         "args": "cells", "inputs": ["key", "object"], "compare": "fields:others,fields", "expect": value()},
        instance("box.tsv"), instance("cases.tsv"),
        journal("append.tsv", ["file", "line"]), journal("names.tsv", ["input"]), journal("years.tsv", ["t"]),
        labels(("label", "text_read")),
        LOOPBACK,
        object_client("address.tsv"), object_client("read.tsv"),
        {"package": "common/pool", "table": "cases.tsv", "surface": "vectors", "fn": "Pool", "args": "cells",
         "inputs": ["input"], "compare": "value", "expect": value(),
         "doc": "the pool of a manifest: {pool, keepers, idle_by_policy, placeable, load, count[, capacity, fates]}",
         "src": "pool/README.md:13-43; runner c_state_vectors.py:16,82-90"},
        {"package": "common/resource-state", "table": "cases.tsv", "surface": "vectors", "fn": "ResourceState",
         "args": "cells", "inputs": ["history", "at"], "compare": "value", "expect": lambda r, d: (0, r["state"], None),
         "doc": "the state of a resource at a moment: \"live\" | \"unreachable\" | \"unknown\" | \"silent\"",
         "src": "resource-state/README.md:16-40; runner c_state_vectors.py:17,29-34"},
        ROW_STATE,
        SCHEMA,
        secret_in("display"),
        slot("fields:state"),
        slot_name(("order", "role")),
        {"package": "common/turn", "table": "cases.tsv", "surface": "vectors", "fn": "Turn", "args": "cells",
         "inputs": ["input"], "select": by_input("kind", ("placement",)), "compare": "turn", "expect": value(),
         "doc": "the placement turn: the actions one per event; \"@new\" / \"@same\" in the input — substitute your marks",
         "src": "turn/README.md:12-53; runner c_state_vectors.py:20,73-128"},
        values_by_type(("read",)),
        {"package": "04-controller/near-of", "table": "cases.tsv", "surface": "stand:near-of", "fn": "NearOf",
         "args": "input", "input": "input", "compare": "raw", "expect": lambda r, d: (0, None, r["expect"].encode("utf-8")),
         "doc": "the neighbour of a unit (stand near-of): stdout — its id bytes exactly, empty — none; code 2 — out of form",
         "src": "04-controller/vectors/near-of/README.md:9-36; runner c_sdk_json.py:85-87,259-260"},
        {"package": "04-controller/order", "table": "cases.tsv", "surface": "stand:order", "fn": "Order", "args": "input",
         "input": "input", "compare": "value", "expect": or_exit2,
         "doc": "the growth order (stand order): {per, processes, in_flight, need, orders, withheld[, why]} or {sets, "
                "orders, withheld}; code 2 — out of form",
         "src": "04-controller/vectors/order/README.md:9-62; acceptance/README.md:140-148; runner c_sdk_json.py:83-89"},
        {"package": "04-controller/shrink-allowed", "table": "cases.tsv", "surface": "stand:shrink-allowed",
         "fn": "ShrinkAllowed", "args": "input", "input": "input", "compare": "value", "expect": or_exit2,
         "doc": "the shrink decision (stand shrink-allowed): {shrink, why, victim}; code 2 — out of form",
         "src": "04-controller/vectors/shrink-allowed/README.md:11-69; acceptance/README.md:140-148"},
        {"package": "04-controller/shrink-victim", "table": "cases.tsv", "surface": "stand:shrink-victim",
         "fn": "ShrinkVictim", "args": "input", "input": "input", "compare": "value", "expect": or_exit2,
         "doc": "the shrink victim (stand shrink-victim): {victim: <name> | null}; code 2 — out of form",
         "src": "04-controller/vectors/shrink-victim/README.md:8-33; acceptance/README.md:140-148"},
    ],
}

# Таблицы состава урока, которые пакет не исполняет (опись: excluded с причиной).
SKIP_LESSON = {
    "03-worker": {("common/fault", "fault.tsv"): "no consumer target of 03 (fault README «Who performs it» names the door "
                  "words only; the runner has the console target alone) — open question 2 of the draft"},
}
