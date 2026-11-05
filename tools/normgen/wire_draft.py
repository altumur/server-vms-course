"""Черновик провода векторов P/03, P/04, P/06 для gen_vectors.WIRE — ВРЕМЕННАЯ ПРОЕКЦИЯ (ADR-0125 доп. (5) п. 5).

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
        if at < 0:                                     # проверку утечки не ослаблять (spec103, сверка п. 8)
            raise ValueError(f"secret-in: masked {masked!r} does not align with raw — the hidden parts are unknown")
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
    if item == "all":                                  # консоль: отображение и отказ (README «Who performs it»)
        exp = lambda r, d: (0, {"masked": r["masked"], "fault": r["fault"],  # noqa: E731
                                "hidden": secret_hidden(r["raw"], r["masked"])}, None)
        compare = "secret"
    elif item == "refusal":
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


def values_by_type(halves, sealed=False):
    def frames(r):
        out = []
        if "@sealed" in (r["json"], r["row"]) and not sealed:
            return out                                 # только консоль (README «Who performs it»)
        dirs = ["write", "read"] if r["dir"] == "both" else [r["dir"]]
        for v in dirs:
            if v not in halves:
                continue
            if v == "write":
                cell = r["row"]
                if cell == "@absent":
                    exp = {"status": "absent"}
                elif cell == "@sealed":                # консоль: конверт enc:v2:…, plaintext — открытие (README «Write»)
                    exp = {"status": "ok", "sealed": True, "plaintext": json.loads(r["json"])}
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
            "select": lambda r: True if sealed or "@sealed" not in (r["json"], r["row"]) else "@sealed: only the console seals",
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
         "src": "03-worker/vectors/creates-key/README.md:9-33; acceptance/README.md:40-49; spec103 сверка п. 1: stand — "
                "канон"},
        {"package": "03-worker/creates-key", "table": "cases.tsv", "surface": "vectors", "fn": "CreatesKeyCells",
         "args": "cells", "inputs": ["input"], "compare": "raw",
         "expect": lambda r, d: (0, None, r["expect"].encode("utf-8")),
         "doc": "the id of a created row through the unified command (cells input): Raw — the id bytes exactly",
         "src": "spec103 сверка п. 1: совместимая привязка общего провода, исход raw"},
    ],
    "04-controller": [
        {"package": "common/fresh-age", "table": "fresh.tsv", "surface": "vectors", "fn": "FreshAge", "args": "cells",
         "inputs": ["age"], "compare": "value", "expect": value("fresh"), "doc": "the freshness of an age: true | false",
         "src": "wire.tsv common/fresh-age (cells age, value fresh); fresh-age/README.md:28-55"},
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


def contains(col, needle, why):
    return lambda r: True if needle not in r[col] else why


def subset_pkg(pkg, fn, doc, src, markers=True, table="cases.tsv"):
    return {"package": pkg, "table": table, "surface": "vectors", "fn": fn, "args": "cells", "inputs": ["input"],
            "compare": "subset", "expect": or_exit2 if markers else value(), "doc": doc, "src": src}


def value_pkg(pkg, fn, doc, src, table="cases.tsv", inputs=("input",), col="expect"):
    return {"package": pkg, "table": table, "surface": "vectors", "fn": fn, "args": "cells", "inputs": list(inputs),
            "compare": "value", "expect": value(col), "doc": doc, "src": src}


def rid_stand_input(r):
    """rid README «Stand command»: {"rid": <лексема ячейки как есть>} — без повторного кодирования."""
    return ('{"rid":' + r["rid"] + "}").encode("utf-8")


def digest_stand_input(r):
    """request-digest README «Stand command»: {"sender": <слово>, "input": <текст ячейки как JSON-строка>}."""
    return json.dumps({"sender": r["sender"], "input": r["input"]}, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def said_read_input(r):
    """said-id README «said-read»: {"fetched": <ячейка>, "rid": <ячейка>} — лексемы ячеек как есть."""
    return ('{"fetched":' + r["fetched"] + ',"rid":' + r["rid"] + "}").encode("utf-8")


DIGEST_EXPECT = lambda r, d: (0, {"canonical": r["canonical"], "sha256": r["sha256"]}, None)  # noqa: E731
RID_EXPECT = lambda r, d: (0, {"status": r["verdict"]}, None)  # noqa: E731

WIRE["06-console"] = [
    subset_pkg("common/agent-sig", "AgentSig", "the agent signature check: {result: ok} | {result: refused, reason} (subset)",
               "agent-sig/README.md:16-20; runner c_console_vectors.py:22,36-101", markers=False),
    {**subset_pkg("common/ask-sig", "AskSig", "the ask signature check (backup, move): {result: ok} | {result: refused, "
                  "reason} (subset); code 2 — out of form", "ask-sig/README.md:18-36; runner c_console_vectors.py:23,76-84"),
     "select": contains("input", '"ask":"prepare"', "ask prepare: only 08-domain")},
    value_pkg("common/contender-fresh", "ContenderFresh", "the freshness of a contender: true | false",
              "contender-fresh/README.md:27-37; runner c_console_vectors.py:24,70-71", table="fresh.tsv", inputs=("age",),
              col="fresh"),
    value_pkg("common/deadline", "Deadline", "the deadline of a request: {written} | {status: 400, error: \"bad deadline\"}",
              "deadline/README.md:17-27; runner c_console_vectors.py:25"),
    {"package": "common/domain-token", "table": "cases.tsv", "surface": "vectors", "fn": "DomainToken", "args": "cells",
     "inputs": ["input"], "compare": "subset", "expect": or_exit2,
     "doc": "the domain token check: {result: ok, payload} | {result: refused, reason} (subset), code 2 — out of form",
     "src": "domain-token/README.md:21-24; runner c_vector_packages.py:94, c_value_vectors.py:160-167"},
    {"package": "common/door-token", "table": "issue.tsv", "surface": "vectors", "fn": "DoorTokenIssue", "args": "cells",
     "inputs": ["seed_hex", "kid", "now", "claims"], "compare": "value",
     "expect": lambda r, d: (0, {"claims_jcs": r["claims_jcs"], "token": r["token"]}, None),
     "doc": "the issue of a door token: exactly {claims_jcs, token} (object and LF)",
     "src": "door-token/README.md:22-33; acceptance/README.md:165-173; runner c_sdk_json.py:141-158,302-316"},
    {"package": "common/events-merge", "table": "cases.tsv", "surface": "vectors", "fn": "EventsMerge", "args": "cells",
     "inputs": ["input"], "compare": "events", "expect": value(),
     "select": lambda r: True if json.loads(r["input"]).get("participant") == "console" else "participant worker: 03's row",
     "doc": "the merge of the console's events: {events, state, truncated, …, withheld}; expect is a subset, events by "
            "their listed fields", "src": "events-merge/README.md:18-41; runner c_events_merge.py:9,32-89"},
    {"package": "common/fault", "table": "fault.tsv", "surface": "vectors", "fn": "Fault", "args": "cells", "inputs": [],
     "header": None, "fields": ["word", "status"], "compare": "value",
     "whole": {"case": "fault.tsv", "expect": lambda rows: (0, {r["word"]: int(r["status"]) for _, r in rows}, None)},
     "doc": "the fault words of the console doors: one call for the table, {<word>: <HTTP status>} of exactly its words",
     "src": "fault/README.md:38-53; acceptance/README.md:165-173; runner c_sdk_json.py:96-118,303-330"},
    value_pkg("common/fresh-age", "FreshAge", "the freshness of an age: true | false",
              "wire.tsv common/fresh-age (cells age, value fresh); fresh-age/README.md:44-55",
              table="fresh.tsv", inputs=("age",), col="fresh"),
    {"package": "common/group-of", "table": "cases.tsv", "surface": "vectors", "fn": "GroupOf", "args": "cells",
     "header": None, "fields": ["raw", "group", "fault"], "inputs": ["raw"], "compare": "value",
     "expect": lambda r, d: (0, {"group": "" if r["group"] == "<none>" else r["group"],
                                 "fault": "" if r["fault"] in ("<none>", "") else r["fault"]}, None),
     "doc": "the group of a source address: {group, fault} (\"\" — none; fault bad_url or \"\")",
     "src": "group-of/README.md:13-30 (06 has no stand key; runner has no 06 target — open question)"},
    HEARTBEAT_CASES,
    {**HEARTBEAT_CASES, "table": "worker.tsv", "inputs": ["key", "object"]},
    value_pkg("common/hold-state", "HoldState", "the state of a hold: {active: bool}",
              "hold-state/README.md:14-28; runner c_observation_vectors.py:23-93"),
    instance("box.tsv"), instance("cases.tsv"),
    journal("append.tsv", ["file", "line"]), journal("names.tsv", ["input"]), journal("years.tsv", ["t"]),
    subset_pkg("common/keys", "Keys", "the keyset take: {result: took|holding, rev} | {result: refused, reason[, rev]}",
               "keys/README.md:16-20; runner c_console_vectors.py:26", markers=False),
    labels(("label", "set_write", "text_read")),
    value_pkg("common/log-mask", "LogMaskIn", "whether a value is masked in a log: {mask: bool}",
              "log-mask/README.md:39-50; runner c_resource_vectors.py:20,53-56,132", table="mask_in.tsv", inputs=("value",)),
    LOOPBACK,
    subset_pkg("common/may", "May", "the right check: {result: allow} | {result: deny, reason} | {result: unavailable} "
               "(subset); covers.tsv — true | false; code 2 — out of form", "may/README.md:77-95; runner c_console_vectors.py:27"),
    {**subset_pkg("common/may", "May", "", "may/README.md:77,93-95; acceptance/README.md:168-173", table="covers.tsv"),
     "compare": "value"},
    object_client("address.tsv"), object_client("read.tsv"),
    {"package": "common/password-hash", "table": "cases.tsv", "surface": "stand:password-hash", "fn": "PasswordHash",
     "args": "input", "input": "input", "compare": "value", "expect": value(),
     "select": contains("input", '"salt"', "a salted hash: only 08-domain writes"),
     "doc": "the password check (stand password-hash): true | false (a JSON value and LF)",
     "src": "password-hash/README.md:17-28; acceptance/README.md:158-159,171-173"},
    subset_pkg("common/peer", "Peer", "the peer certificate check: {result: ok} | {result: refused, reason} (subset)",
               "peer/README.md:17-38; runner c_console_vectors.py:17-101"),
    {"package": "common/pool", "table": "cases.tsv", "surface": "vectors", "fn": "Pool", "args": "cells",
     "inputs": ["input"], "compare": "without:fates", "expect": value(),
     "doc": "the pool of a manifest: {pool, keepers, idle_by_policy, placeable, load, count[, capacity]} (fates — the "
            "controller's, not compared)", "src": "pool/README.md:32,43; runner c_state_vectors.py:88-90,132-136"},
    subset_pkg("common/record", "Record", "the shared record check: {result[, term][, reason]} (subset)",
               "record/README.md:16-42; runner c_console_vectors.py:29,48-49", markers=False, table="shared.tsv"),
    {"package": "common/resource-state", "table": "cases.tsv", "surface": "vectors", "fn": "ResourceState",
     "args": "cells", "inputs": ["history", "at"], "compare": "value", "expect": lambda r, d: (0, r["state"], None),
     "doc": "the state of a resource at a moment: \"live\" | \"unreachable\" | \"unknown\" | \"silent\"",
     "src": "resource-state/README.md:16-40; runner c_state_vectors.py:17,29-34"},
    {"package": "common/row-check", "table": "cases.tsv", "surface": "vectors", "fn": "RowCheck", "args": "cells",
     "inputs": ["unit", "op", "body", "stored", "rows"],
     "files": {"testsub.subsystem.yaml": "@root/Source/tests/testdata/testsub.subsystem.yaml",
               "testsub2.subsystem.yaml": "@root/Source/tests/testdata/testsub2.subsystem.yaml"},
     "compare": "row",
     "expect": lambda r, d: (0, dict({"result": r["expect"]},
                                     **({"row": json.loads(r["row"])} if r["expect"] == "ok" and r["row"] else {}),
                                     **({"word": r["word"], "field": r["field"] or "@absent"}
                                        if r["expect"] == "refused" else {})), None),
     "doc": "the preparation and check of a row (all units of the console door): {result: ok, row} | {result: refused, "
            "word[, field]}", "src": "row-check/README.md:11-54; runner c_value_vectors.py:22-24,118-131,289-314"},
    ROW_STATE,
    {"package": "common/said-id", "table": "said.tsv", "surface": "stand:said-id", "fn": "SaidID", "args": "input",
     "input": "rid", "compare": "value", "expect": value("said"),
     "doc": "said-id (stand said-id): the SaidID as a JSON string; read.tsv (stand said-read): true | false",
     "src": "said-id/README.md:25-61; acceptance/README.md:162-164; runner c_sdk_json.py:52-55,216-249"},
    {"package": "common/said-id", "table": "read.tsv", "surface": "stand:said-read", "fn": "SaidRead", "args": "input",
     "input": said_read_input, "compare": "value", "expect": value("reported"),
     "doc": "the said-read check (stand said-read): {input} — {fetched, rid}; true | false",
     "src": "said-id/README.md:40-61; runner c_sdk_json.py:224-244"},
    SCHEMA,
    secret_in("all"),
    *[dict(x, doc=x.get("doc", "").replace("(the worker only opens)", "(the console seals and opens)")) for x in SEALING],
    {"package": "common/sealing", "table": "envelope.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
     "inputs": ["key_hex", "kid", "nonce_b64url", "row_key", "pointer", "plaintext"], "compare": "value",
     "expect": lambda r, d: (0, r["envelope"], None)},
    {"package": "common/sealing", "table": "reseal.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
     "inputs": ["input"], "compare": "value", "expect": value()},
    slot_name(("order", "role")),
    {"package": "common/tombstone", "table": "cases.tsv", "surface": "vectors", "fn": "Tombstone", "args": "cells",
     "inputs": ["op", "input"], "select": by_col("op", ("peers",), "ack and remove: 05-store-peer"),
     "compare": "setarrays", "expect": value(),
     "doc": "the tombstone peers: {peers: [...]} (a set) | \"no_delete\"",
     "src": "tombstone/README.md:11-26; runner c_resource_vectors.py:21-22,90-203"},
    values_by_type(("write", "read"), sealed=True),
    # свои пакеты урока
    value_pkg("06-console/contender-projection", "ContenderProjection", "the contender projection: {name_conflict, "
              "name_conflicts[, name_conflict_unreadable]}", "06-console/vectors/contender-projection/README.md:13-31"),
    value_pkg("06-console/key-families", "KeyFamilies", "the key families present: {<id>: [<key>…]} (order matters)",
              "06-console/vectors/key-families/README.md:12-33", inputs=("decls", "present")),
    value_pkg("06-console/metrics", "Metrics", "the metrics lines: {lines, garbled}",
              "06-console/vectors/metrics/README.md:12-39"),
    {**value_pkg("06-console/op-step", "OpStep", "op-step: key.tsv — the key (64 hex) as a JSON string; expected.tsv — "
                 "the expected object", "06-console/vectors/op-step/README.md:10-36", table="key.tsv", inputs=("id", "i")),
     "expect": lambda r, d: (0, r["expect"], None)},
    value_pkg("06-console/op-step", "OpStep", "", "06-console/vectors/op-step/README.md:22-36", table="expected.tsv"),
    value_pkg("06-console/reap", "Reap", "the reaping of a request: {write_mark, remove_row}",
              "06-console/vectors/reap/README.md:13-43"),
    {**subset_pkg("06-console/resolve", "Resolve", "the resolution of a shared value: {value, from} | {groups, from} "
                  "(subset); code 2 — out of form", "06-console/vectors/resolve/README.md:19-35")},
    {"package": "06-console/request-digest", "table": "digest.tsv", "surface": "stand:request-digest",
     "fn": "RequestDigest", "args": "input", "input": digest_stand_input, "compare": "value", "expect": DIGEST_EXPECT,
     "doc": "the digest of a request: exactly {canonical, sha256} (object and LF); stand {input} — {sender, input}",
     "src": "06-console/vectors/request-digest/README.md:18-65; acceptance/README.md:155-157 (runner: vectors frame — "
            "both surfaces declared)"},
    {"package": "06-console/request-digest", "table": "digest.tsv", "surface": "vectors", "fn": "RequestDigestCells",
     "args": "cells", "inputs": ["sender", "input"], "compare": "value", "expect": DIGEST_EXPECT,
     "doc": "the digest of a request through the unified command (cells sender, input): {canonical, sha256}",
     "src": "runner c_request_vectors.py:69-112"},
    {"package": "06-console/rid", "table": "rid.tsv", "surface": "stand:rid", "fn": "Rid", "args": "input",
     "header": None, "fields": ["rid", "verdict"], "input": rid_stand_input, "compare": "value", "expect": RID_EXPECT,
     "doc": "the request id check: {status: ok | refused} (object and LF); stand {input} — {rid}",
     "src": "06-console/vectors/rid/README.md:19-74; acceptance/README.md:155-157 (runner: vectors frame — both declared)"},
    {"package": "06-console/rid", "table": "rid.tsv", "surface": "vectors", "fn": "RidCells", "args": "cells",
     "header": None, "fields": ["rid", "verdict"], "inputs": ["rid"], "compare": "value", "expect": RID_EXPECT,
     "doc": "the request id check through the unified command (cells rid; rid.tsv), template.tsv (cells key, body): "
            "the object of expect", "src": "runner c_request_vectors.py:74-86"},
    {"package": "06-console/rid", "table": "template.tsv", "surface": "vectors", "fn": "RidCells", "args": "cells",
     "inputs": ["key", "body"], "compare": "value", "expect": value(),
     "src": "06-console/vectors/rid/README.md:37-57; runner c_request_vectors.py:31-62"},
]


# --- P/08, P/09, P/10 (процесс домена, агент, консоль домена): черновик по README, сверка с раннером 37b733b ---

def env_open(r, d):
    """x25519-open / m1-open: ячейка в кавычках — {result: ok, plain}; слово — {result: refused, reason}."""
    if r["expect"].startswith('"'):
        return (0, {"result": "ok", "plain": json.loads(r["expect"])}, None)
    return (0, {"result": "refused", "reason": r["expect"]}, None)


def env_round(r, d):
    """x25519-round / m1-round: ok — {result: ok, opened: [plain, plain], distinct: true}; иначе отказ со словом."""
    if r["expect"] == "ok":
        p = json.loads(r["plain"])
        return (0, {"result": "ok", "opened": [p, p], "distinct": True}, None)
    return (0, {"result": "refused", "reason": r["expect"]}, None)


def secret_domain():
    return {"package": "common/secret-in", "table": "cases.tsv", "surface": "vectors", "fn": "SecretIn", "args": "cells",
            "header": None, "fields": ["field", "raw", "masked", "fault", "note"], "inputs": ["field", "raw"],
            "files": {"fields.yaml": "fields.yaml"}, "compare": "secret-domain",
            "expect": lambda r, d: (0, {"fault": r["fault"], "hidden": secret_hidden(r["raw"], r["masked"])}, None),
            "doc": "the refusal of an address by its credentials (item 2): {fault[, text]} — fault judged only as empty or "
                   "not (its word is yours), text never repeats a hidden part of the row",
            "src": "secret-in/README.md:46-63 (the process domain)"}


def stand_subset(pkg, key, fn, doc, src):
    return {"package": pkg, "table": "cases.tsv", "surface": f"stand:{key}", "fn": fn, "args": "input", "input": "input",
            "compare": "subset", "expect": or_exit2, "doc": doc, "src": src}


ACCEPT = {"package": "common/accept", "table": "cases.tsv", "surface": "vectors", "fn": "Accept", "args": "cells",
          "inputs": ["input"], "compare": "subset", "expect": or_exit2,
          "files": {"testsub.subsystem.yaml": "@root/Source/tests/testdata/testsub.subsystem.yaml",
                    "testsub2.subsystem.yaml": "@root/Source/tests/testdata/testsub2.subsystem.yaml"},
          "doc": "the acceptance of a member request: the object of expect (subset; @absent — no key, @any — any value)",
          "src": "accept/README.md:19-47; runner c_vector_packages.py:170-178, c_domain_packages.py:89-99"}


def turn_signer():
    return {"package": "common/turn", "table": "cases.tsv", "surface": "vectors", "fn": "Turn", "args": "cells",
            "inputs": ["input"], "select": by_input("kind", ("signer",)), "compare": "value", "expect": value(),
            "doc": "the signer turn: the actions one per event (no @new/@same in the signer rows)",
            "src": "turn/README.md:53; runner c_state_vectors.py:73-85"}


def alarm_history(ops):
    return {"package": "common/alarm-history", "table": "cases.tsv", "surface": "vectors", "fn": "AlarmHistory",
            "args": "cells", "inputs": ["op", "input"], "select": by_col("op", ops), "compare": "value",
            "expect": value(),
            "doc": "the alarm history by op: same → bool; page → the ids; write → {ids, cut_before, written}",
            "src": "alarm-history/README.md:9-30; runner c_domain_packages.py:44-45,61-99"}


FRESH_VECTORS = {"package": "common/fresh-age", "table": "fresh.tsv", "surface": "vectors", "fn": "FreshAge",
                 "args": "cells", "inputs": ["age"], "compare": "value", "expect": value("fresh"),
                 "doc": "the freshness of an age through the unified command (no stand key for this lesson): true | false",
                 "src": "fresh-age/README.md:42-55 (09, 10 — no stand key in their profiles)"}


def record_09(r):
    inp = json.loads(r["input"])
    doc = (inp.get("row") or {}).get("doc") if isinstance(inp.get("row"), dict) else None
    try:
        tag = json.loads(doc) if isinstance(doc, str) else {}
    except ValueError:
        tag = {}
    return "the grant document: only 08 (record README «Who performs it»)" if isinstance(tag, dict) and "grant" in tag else True


WIRE["08-domain"] = [
    ACCEPT,
    subset_pkg("common/agent-sig", "AgentSig", "the agent signature check: {result: ok} | {result: refused[, reason]} "
               "(subset); batch-knock.tsv — the batch knock", "agent-sig/README.md:16-22", markers=False),
    subset_pkg("common/agent-sig", "AgentSig", "", "agent-sig/README.md:22; runner c_vector_packages.py:179-182",
               markers=False, table="batch-knock.tsv"),
    alarm_history(("same", "write")),
    {**subset_pkg("common/ask-sig", "AskSig", "the ask signature check (move, prepare): {result: ok} | {result: refused, "
                  "reason} (subset); code 2 — out of form", "ask-sig/README.md:18-36; runner c_domain_packages.py:40-41"),
     "select": lambda r: True if json.loads(r["input"]).get("ask") in ("move", "prepare") else "ask backup: 06-console"},
    {"package": "common/domain-backup-key", "table": "cases.tsv", "surface": "vectors", "fn": "DomainBackupKey",
     "args": "cells", "inputs": ["root_key", "backup_key_rev"], "compare": "value",
     "expect": lambda r, d: (0, r["expect"], None),
     "doc": "the domain backup copy key (HMAC-SHA256 of root_key and backup_key_rev): \"<64 hex>\" or \"@refuse\"",
     "src": "domain-backup-key/README.md (as P/02); runner c_domain_vectors.py:72"},
    {"package": "common/domain-envelopes", "table": "x25519-open.tsv", "surface": "vectors", "fn": "DomainEnvelopes",
     "args": "cells", "inputs": ["seed_hex", "envelope", "member", "source_path", "item", "pointer"], "compare": "subset",
     "expect": env_open,
     "doc": "the domain envelopes by table: *-open → {result: ok, plain} | {result: refused, reason}; *-round → {result: "
            "ok, opened: [plain, plain], distinct: true, envelopes|sealed: [two distinct]} | refused",
     "src": "domain-envelopes/README.md:21-37; runner c_domain_packages.py:16-21,46-48,76-148"},
    {"package": "common/domain-envelopes", "table": "x25519-round.tsv", "surface": "vectors", "fn": "DomainEnvelopes",
     "args": "cells", "inputs": ["book_seal_hex", "seed_hex", "plain", "member", "source_path", "item", "pointer"],
     "compare": "round:envelopes:x25519:v1:", "expect": env_round},
    {"package": "common/domain-envelopes", "table": "m1-round.tsv", "surface": "vectors", "fn": "DomainEnvelopes",
     "args": "cells", "inputs": ["key_hex", "seed_hex", "plain"], "compare": "round:sealed:m1:", "expect": env_round},
    value_pkg("common/domain-founding", "DomainFoundingClaim", "the founding claim of a domain: {doc}",
              "domain-founding/README.md:17-26; runner c_domain_vectors.py:39-42", table="claim.tsv"),
    {"package": "common/domain-token", "table": "cases.tsv", "surface": "vectors", "fn": "DomainToken", "args": "cells",
     "inputs": ["input"], "compare": "subset", "expect": or_exit2,
     "doc": "the domain token check: {result: ok, payload} | {result: refused, reason} (subset), code 2 — out of form",
     "src": "domain-token/README.md:21-24"},
    {**HEARTBEAT_CASES, "table": "worker.tsv", "inputs": ["key", "object"], "compare": "fields:others,fields"},
    instance("box.tsv"), instance("cases.tsv"),
    journal("append.tsv", ["file", "line"]), journal("names.tsv", ["input"]), journal("years.tsv", ["t"]),
    subset_pkg("common/keys", "Keys", "the keyset take: {result: took|holding, rev} | {result: refused, reason[, rev]}",
               "keys/README.md:16-20", markers=False),
    {**labels(("label",)), "compare": "value"},
    LOOPBACK,
    subset_pkg("common/may", "May", "the right check: {result: allow|deny|unavailable[, reason]} (subset); code 2 — out "
               "of form", "may/README.md:77-95"),
    object_client("address.tsv"), object_client("read.tsv"),
    {"package": "common/password-hash", "table": "cases.tsv", "surface": "stand:password-hash", "fn": "PasswordHash",
     "args": "input", "input": "input", "compare": "value", "expect": value(),
     "doc": "the password hash and check (stand password-hash; 08 also hashes with salt): the JSON value of expect",
     "src": "password-hash/README.md:17-28; runner c_targets.py:111, c_sdk_json.py:236-247"},
    subset_pkg("common/peer", "Peer", "the peer certificate check: {result: ok} | {result: refused, reason} (subset)",
               "peer/README.md:17-38"),
    subset_pkg("common/record", "Record", "the record check: the object of expect (subset); code 2 — out of form",
               "record/README.md:16-42"),
    SCHEMA,
    secret_domain(),
    *[dict(x) for x in SEALING],
    {"package": "common/sealing", "table": "envelope.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
     "inputs": ["key_hex", "kid", "nonce_b64url", "row_key", "pointer", "plaintext"], "compare": "value",
     "expect": lambda r, d: (0, r["envelope"], None)},
    turn_signer(),
    values_by_type(("read",)),
    stand_subset("08-domain/assemble", "assemble", "Assemble", "the assembly of the domain view (stand assemble): "
                 "{rows, report} (subset)", "08-domain/vectors/assemble/README.md:20-42; acceptance/README.md:451"),
    stand_subset("08-domain/issue", "issue", "Issue", "the token issue (stand issue): {result: ok, claims} | {result: "
                 "refused, status, reason} (subset)", "08-domain/vectors/issue/README.md:22-47; acceptance/README.md:451"),
    stand_subset("08-domain/view", "view", "View", "the view of a member (stand view): {view, shadow} (subset; as_of "
                 "not compared)", "08-domain/vectors/view/README.md:23-45; acceptance/README.md:447"),
]

WIRE["09-agent"] = [
    ACCEPT,
    subset_pkg("common/agent-sig", "AgentSig", "the agent signature check: {result: ok} | {result: refused, reason}",
               "agent-sig/README.md:20", markers=False),
    {"package": "common/domain-envelopes", "table": "m1-open.tsv", "surface": "vectors", "fn": "DomainEnvelopes",
     "args": "cells", "inputs": ["seed_hex", "sealed"], "compare": "subset", "expect": env_open,
     "doc": "the domain envelopes: m1-open → {result: ok, plain} | {result: refused, reason}; x25519-round → the round",
     "src": "domain-envelopes/README.md:21-37; runner c_domain_packages.py:19,79-85"},
    {"package": "common/domain-envelopes", "table": "x25519-round.tsv", "surface": "vectors", "fn": "DomainEnvelopes",
     "args": "cells", "inputs": ["book_seal_hex", "seed_hex", "plain", "member", "source_path", "item", "pointer"],
     "compare": "round:envelopes:x25519:v1:", "expect": env_round},
    FRESH_VECTORS,
    instance("box.tsv"), instance("cases.tsv"),
    journal("append.tsv", ["file", "line"]), journal("names.tsv", ["input"]), journal("years.tsv", ["t"]),
    subset_pkg("common/keys", "Keys", "the keyset: cases.tsv — the take (subset); revoked.tsv — the jtis text (value)",
               "keys/README.md:16-36", markers=False),
    {**value_pkg("common/keys", "Keys", "", "keys/README.md:20,36; runner c_domain_packages.py:98", table="revoked.tsv")},
    LOOPBACK,
    object_client("address.tsv"), object_client("read.tsv"),
    subset_pkg("common/peer", "Peer", "the peer certificate check: {result: ok} | {result: refused, reason} (subset)",
               "peer/README.md:21"),
    {**subset_pkg("common/record", "Record", "the record check: cases.tsv, shared.tsv, take.tsv — the object of expect "
                  "(subset); code 2 — out of form", "record/README.md:16-42; runner c_domain_packages.py:29-39"),
     "select": record_09},
    subset_pkg("common/record", "Record", "", "record/README.md:23-24", markers=False, table="shared.tsv"),
    subset_pkg("common/record", "Record", "", "record/README.md:18,21 (no runner target)", markers=False, table="take.tsv"),
    SCHEMA,
    *[dict(x) for x in SEALING],
    {"package": "common/sealing", "table": "envelope.tsv", "surface": "vectors", "fn": "Sealing", "args": "cells",
     "inputs": ["key_hex", "kid", "nonce_b64url", "row_key", "pointer", "plaintext"], "compare": "value",
     "expect": lambda r, d: (0, r["envelope"], None)},
    turn_signer(),
    values_by_type(("read",)),
    stand_subset("09-agent/follow", "follow", "Follow", "the follow decision of the agent (stand follow): {result: "
                 "follow|stay[, term]} (subset)", "09-agent/vectors/follow/README.md:18-21; 09.1-agent.norms.md:1597-1643"),
]

WIRE["10-domain-console"] = [
    alarm_history(("same", "page")),
    {"package": "common/domain-token", "table": "cases.tsv", "surface": "vectors", "fn": "DomainToken", "args": "cells",
     "inputs": ["input"], "compare": "subset", "expect": or_exit2,
     "doc": "the domain token check: {result: ok, payload} | {result: refused, reason} (subset), code 2 — out of form",
     "src": "domain-token/README.md:24"},
    FRESH_VECTORS,
    instance("box.tsv"), instance("cases.tsv"),
    journal("append.tsv", ["file", "line"]), journal("names.tsv", ["input"]), journal("years.tsv", ["t"]),
    LOOPBACK,
    subset_pkg("common/may", "May", "the right check (subset); covers.tsv — true | false", "may/README.md:77-95"),
    {**subset_pkg("common/may", "May", "", "may/README.md:93-95", table="covers.tsv"), "compare": "value"},
    object_client("address.tsv"), object_client("read.tsv"),
    {**subset_pkg("common/peer", "Peer", "the peer certificate check (the role rows): {result: refused, reason} (subset)",
                  "peer/README.md:21-23; runner c_domain_packages.py:42-43"),
     "select": lambda r: True if r["expect"] != "@exit 2" and json.loads(r["expect"]).get("reason") in
     ("no_role", "wrong_role") else "not a role row: 06, 08, 09"},
    SCHEMA,
    value_pkg("common/trust-set", "TrustSet", "the trust set by op: set → the sorted fingerprints; check → trusted | refused",
              "trust-set/README.md:13-29; runner c_domain_packages.py:61,91", inputs=("op", "input")),
    stand_subset("10-domain-console/alarms", "alarms", "Alarms", "the alarm view (stand alarms): {events, members, "
                 "complete, sentence} (subset)", "10-domain-console/vectors/alarms/README.md:19-44; acceptance/README.md:452"),
]

WIRE["05-resource"] = [
    {"package": "common/events-merge", "table": "resource.tsv", "surface": "vectors", "fn": "EventsMerge", "args": "cells",
     "inputs": ["input"], "compare": "value", "expect": value(),
     "doc": "the resource's filter and cut of events (resource.tsv): {events, query} → the full ResourceEvents",
     "src": "events-merge/README.md#resourcetsv; wire.tsv (spec103 3ad5d3b2a)"},
    FRESH_VECTORS,
    value_pkg("common/holds", "Holds", "whether a row holds a bucket: {hold}", "holds/README.md:31-45",
              inputs=("holds", "types", "row", "bucket")),
    instance("box.tsv"), instance("cases.tsv"),
    journal("append.tsv", ["file", "line"]),
    {**journal("bucket.tsv", ["file"]), "doc": "the journal contract: bucket.tsv → {ids, torn, garbled, duplicate}; "
     "append.tsv, names.tsv, years.tsv as for the other readers/writers", "src": "journal/README.md:12-69 (bucket.tsv — "
     "the reader of buckets, the resource)"},
    journal("names.tsv", ["input"]), journal("years.tsv", ["t"]),
    LOOPBACK,
    object_client("address.tsv"), object_client("read.tsv"),
    value_pkg("common/presence-room", "PresenceRoom", "the room and the live slots of a server: {room, live}",
              "presence-room/README.md:6-19 (the resource counts; the controller reads)"),
    SCHEMA,
    {"package": "common/tombstone", "table": "cases.tsv", "surface": "vectors", "fn": "Tombstone", "args": "cells",
     "inputs": ["op", "input"], "select": by_col("op", ("ack", "remove"), "peers: 06-console"),
     "compare": "setarrays", "expect": value(),
     "doc": "the tombstone of the resource: ack → the acknowledgements; remove → the removal decision (arrays as sets)",
     "src": "tombstone/README.md:1-24 (the resource: ack and remove, P/05 Н1.1)"},
    value_pkg("05-resource/relieve", "Relieve", "the relieve step of the resource pass: cases.tsv → {action, free}; "
              "short.tsv → the heartbeat field short", "05-resource/vectors/relieve/README.md:5-30"),
    value_pkg("05-resource/relieve", "Relieve", "", "05-resource/vectors/relieve/README.md:20", table="short.tsv"),
]

# Таблицы состава урока, которые пакет не исполняет (опись: excluded с причиной).
_FAULT_LAYOUT = ("layout (as 03): the process speaks no fault.tsv word of its own refusals (fault README «Who performs "
                 "it»; no word in the lesson's norms); no native fault command")
SKIP_LESSON = {
    "08-domain": {("common/fault", "fault.tsv"): _FAULT_LAYOUT},
    "09-agent": {("common/fault", "fault.tsv"): _FAULT_LAYOUT},
    "10-domain-console": {("common/fault", "fault.tsv"): _FAULT_LAYOUT},
    "06-console": {("06-console/requests-body", "requests_body.tsv"): "layout (Architect, wire P/06 item 5): an unperformed "
                   "duty of the real HTTP stand of the README «Stand» (POST and round trip on a fresh stand) — the runner "
                   "checks the publication; no vector function, not a PASS"},
    "03-worker": {("common/fault", "fault.tsv"): "layout (Architect, ADR-0125 add. (1) item 5): bad_url of the customer "
                  "library is judged by the norm and the lesson acceptance through the real group-of and row-check; 03 "
                  "has no native fault command"},
}
