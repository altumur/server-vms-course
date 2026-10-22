"""Прогонщик проверки формы манифеста (ADR-0085): текст YAML → форма схемой → ссылки → вердикт и класс.

Проверка рядом с нормой, не норма: норма урока М10/2 — проза. Схема, ссылки и профиль —
Platform/02-installer/spec/02.1-installer.schema.yaml (профиль — её шапка) и .references.tsv (переехали с главой 2.1).

    python run.py [--schema S] [--references R] FILE...   # JSON-строка на файл: {file, verdict, class, layer, errors}
    python run.py [--schema S] [--references R] @LIST     # файлы списком

Порядок (М10/2 Н3): текст (textlayer) → имя → ключи → значения (схема, числа, пустые значения) → ссылки
(references.tsv). Класс — по профилю §6. check_spec зовёт Runner на корпусе урока 2.
Зависимости: jsonschema, ruamel.yaml, regress (references/validation.md).
"""
import argparse
import json
import sys
from pathlib import Path

import regress
from jsonschema import Draft202012Validator, ValidationError, validators
from ruamel.yaml import YAML

if __package__:
    from . import refs, textlayer
else:                                               # запуск файлом: python manifest_schema/run.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import refs  # noqa: E402
    import textlayer  # noqa: E402

COURSE = Path(__file__).resolve().parents[4]
LESSON = "Platform/02-installer/spec/02.1-installer"
SCHEMA = COURSE / f"{LESSON}.schema.yaml"
REFERENCES = COURSE / f"{LESSON}.references.tsv"

# Профиль §1: закрытый перечень ключевых слов; §2 п. 5: у объявленного свойства есть тип.
PROFILE = {"$schema", "$id", "$defs", "$ref", "description", "type", "enum", "const", "properties", "patternProperties",
           "additionalProperties", "propertyNames", "required", "dependentRequired", "items", "minItems", "uniqueItems",
           "minimum", "maximum", "exclusiveMinimum", "pattern", "if", "then", "else", "allOf", "anyOf", "oneOf", "not"}
OPAQUE_OK = {"default", "inherit"}
KEY_KEYWORDS = ("additionalProperties", "unevaluatedProperties")
# Профиль §6: переопределение класса по пути (Н1.2а: внутри domain.* класс задаёт урок М11 раздела).
CLASS_BY_PREFIX = [(("domain", "names"), "reference"), (("domain", "books"), "value"),
                   (("domain", "shared"), "value"), (("domain", "tokens"), "value")]

# Профиль §3: pattern — ECMA-262, как требует 2020-12. jsonschema по умолчанию берёт re Python ($ перед конечным \n
# и др.), поэтому pattern и patternProperties исполняет regress (ECMA-262).
_RX = {}


def _rx(p):
    if p not in _RX:
        _RX[p] = regress.Regex(p)
    return _RX[p]


def _pattern(validator, patrn, instance, schema):
    if validator.is_type(instance, "string") and _rx(patrn).find(instance) is None:
        yield ValidationError("%r does not match %r" % (instance, patrn))


def _pattern_properties(validator, pp, instance, schema):
    if validator.is_type(instance, "object"):
        for patrn, sub in pp.items():
            for k, v in instance.items():
                if _rx(patrn).find(k) is not None:
                    yield from validator.descend(v, sub, path=k, schema_path=patrn)


# Профиль §4: целое — только целый знак YAML; 1.0 и 1e0 (float после слоя текста) — не integer.
Validator = validators.extend(
    Draft202012Validator, {"pattern": _pattern, "patternProperties": _pattern_properties},
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda _, x: isinstance(x, int) and not isinstance(x, bool)))


def _typed(s):
    return s is False or (isinstance(s, dict) and (
        {"type", "enum", "const", "$ref"} & set(s) or ("anyOf" in s and all(_typed(x) for x in s["anyOf"]))))


def profile_errors(schema):
    """Схема против профиля: слова вне перечня (§1), свойство без типа (§2 п. 5), pattern вне ECMA-262 (§3)."""
    out = []

    def walk(s, path):
        if not isinstance(s, dict):
            return
        for k in sorted(set(s) - PROFILE):
            out.append("%s: keyword %s is outside the profile" % (path, k))
        refine = any(x in path.split("/") for x in ("if", "then", "else", "not"))   # уточнения, не объявления
        for k, sub in ({} if refine else (s.get("properties") or {})).items():
            if (sub is True and k not in OPAQUE_OK) or (sub is not True and not _typed(sub)):
                out.append("%s/properties/%s: property without type, enum, const, $ref or false" % (path, k))
        for p in ([s["pattern"]] if isinstance(s.get("pattern"), str) else []) + list(s.get("patternProperties") or {}):
            try:
                _rx(p)
            except Exception as exc:  # noqa: BLE001 — regress names its own error type
                out.append("%s: pattern %r is not ECMA-262: %s" % (path, p, exc))
        for k, v in s.items():
            if k in ("properties", "patternProperties", "$defs", "dependentRequired"):
                for kk, vv in (v or {}).items():
                    walk(vv, "%s/%s/%s" % (path, k, kk))
            elif k in ("enum", "const", "required"):
                continue
            elif isinstance(v, dict):
                walk(v, path + "/" + k)
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, "%s/%s/%d" % (path, k, i))

    walk(schema, "#")
    return out


def load_schema(path):
    """YAML схемы → дерево JSON, проверенное метасхемой 2020-12 и профилем; иначе ValueError."""
    y = YAML(typ="safe", pure=True)
    y.version = (1, 2)
    with open(path, encoding="utf-8") as f:
        schema = json.loads(json.dumps(y.load(f)))
    Draft202012Validator.check_schema(schema)
    bad = profile_errors(schema)
    if bad:
        raise ValueError("schema outside the profile: " + "; ".join(bad[:8]))
    return schema


def leaves(errors):
    """Ошибки валидатора → (ключевое слово, путь экземпляра, недостающие для required). anyOf/oneOf — лист."""
    out = []
    for e in errors:
        kw = e.validator if e.validator is not None else "false"
        if "propertyNames" in e.relative_schema_path or "propertyNames" in e.absolute_schema_path:
            kw = "propertyNames"
        missing = []
        if kw == "required":
            missing = [p for p in e.validator_value if p not in e.instance]
        if kw == "additionalProperties" and e.validator_value is False:     # путь — до незнакомого ключа
            missing = [k for k in e.instance if k not in e.schema.get("properties", {})
                       and not any(_rx(p).find(k) for p in e.schema.get("patternProperties", {}))]
        out.append((kw, [str(x) for x in e.absolute_path], missing))
    return out


def classify(kw, path, missing):
    if (path[:1] == ["name"]) or (kw == "required" and not path and "name" in missing):
        return "name"
    for prefix, cls in CLASS_BY_PREFIX:
        if tuple(path[:len(prefix)]) == prefix:
            return cls
    return "key" if kw in KEY_KEYWORDS else "value"


class Runner:
    def __init__(self, schema=SCHEMA, references=REFERENCES):
        self.validator = Validator(load_schema(schema))
        self.rows = refs.load_rows(references)

    def judge(self, data):
        """bytes манифеста → {verdict, class, layer, errors, …}; layer — text:<правило>, schema, global или refs."""
        try:
            tree, numbers, empties = textlayer.load_text(data)
        except textlayer.TextRefused as e:
            return {"verdict": "refused", "class": "text", "layer": "text:" + e.rule, "errors": [str(e)],
                    "paths": [], "line": e.line}
        errs = [(kw, p, m, classify(kw, p, m)) for kw, p, m in leaves(self.validator.iter_errors(tree))]
        errs += [("number", [str(x) for x in p], [], "value") for p, _ in numbers]
        errs += [("empty", [str(x) for x in p], [], "name" if [str(x) for x in p] == ["name"] else "value")
                 for p in empties]
        for cls in ("name", "key", "value", "reference"):
            hit = [e for e in errs if e[3] == cls]
            if hit:
                layer = "schema" if any(e[0] not in ("number", "empty") for e in hit) else "global"
                return {"verdict": "refused", "class": cls, "layer": layer,
                        "errors": ["%s %s %s" % (k, "/".join(p), ",".join(m)) for k, p, m, _ in hit][:8],
                        "paths": [p + [x] for _, p, m, _ in hit for x in m] + [p for _, p, m, _ in hit if not m]}
        found = refs.check(tree, self.rows)
        if found:
            cls = "value" if any(c == "value" for c, _, _ in found) else "reference"
            return {"verdict": "refused", "class": cls, "layer": "refs",
                    "errors": ["%s %s: %s" % (c, p, why) for c, p, why in found][:8],
                    "paths": [p.split(".") for _, p, _ in found]}
        return {"verdict": "ok", "class": None, "layer": None, "errors": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", help="manifest files, or @LIST with one path per line")
    parser.add_argument("--schema", type=Path, default=SCHEMA)
    parser.add_argument("--references", type=Path, default=REFERENCES)
    args = parser.parse_args()
    runner = Runner(args.schema, args.references)
    files = []
    for a in args.files:
        files += [line.strip() for line in open(a[1:], encoding="utf-8")] if a.startswith("@") else [a]
    for f in files:
        if not f:
            continue
        with open(f, "rb") as fh:
            r = runner.judge(fh.read())
        r["file"] = f
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
