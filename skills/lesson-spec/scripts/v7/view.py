"""Канонический вид P/02.2 на стандартных файлах В7 (ADR-0089; ADR-0092 слой 6; PLAN-TRANSITION п. 1.2–1.3): схема вида
`02.2-installer.view.schema.json`, раздел «Форма канонического вида», проверка повторов `name` у списков `ordered`.

Схема вида — стандартный файл рядом с нормами 2.2: до перехода её пишет генератор из формы диалекта (форма вида ADR-0089
п. 3: ключ с умолчанием — обязателен, умолчаний нет, сахар приведён, ключ вычисляемого умолчания обязателен, `ordered` —
список объектов `{name, …}`), после — правят руками, как прочие стандартные файлы. Пометки: `x-step` — шаг проекции,
давший ключ; `x-default` — ключ обязателен умолчанием формы манифеста; `x-unique-by` — у списка `ordered` ключ без
повторов (JSON Schema этого не говорит). Проверка `check_spec`: вид каждого принятого входа проходит схему и не
повторяет `name` (unique_names).
"""
import json

from .section import SchemaSection, cell, code  # noqa: F401

FORM = 1                                          # номер формы вида (окно 2.2, В1): ключ …/canonical/1
BEGIN = "<!-- canonical:begin -->"
END = "<!-- canonical:end -->"
UNIQUE_BY = "x-unique-by"

# Шаги проекции урока 2 (P/02.2-02, -03): имя, фаза, норма, когда, что в виде. Исполняет v7.project.
STEPS = [
    ("tables", "sugar", "P/02.2-02", "`tables` списком имён", "`{<имя>: {}}` на каждое имя, по порядку списка"),
    ("bound_to", "sugar", "P/02.2-02", "`bound_to` одним именем (поля единицы и таблиц)", "список из одного имени"),
    ("in", "sugar", "P/02.2-02", "`in` элемента `secret_in` одним словом", "список из одного слова"),
    ("П1", "computed", "P/02.2-03", "нет `snapshot`",
     "имена `unit.fields` в порядке автора без `*_secret`, полей `type: blob` и `server`; явный `[]` остаётся"),
    ("П2", "computed", "P/02.2-03", "нет `tables.<т>.journal` или одного из его ключей",
     "`written` — `\"<т>.written\"`, `deleted` — `\"<т>.deleted\"`; сказанный ключ остаётся"),
    ("П3", "computed", "P/02.2-03", "нет `display.form`", "`[{\"fields\": [<имена unit.fields в порядке автора>]}]`"),
    ("П4", "computed", "P/02.2-03", "нет `default` у описателя поля (единицы и таблиц)",
     "`null` (и у `blob`, и при `inherit`)"),
    ("П5", "computed", "P/02.2-03", "нет `decoded` у элемента `secret_in` с `regex`", "`true`"),
]
PHASE = {s[0]: s[1] for s in STEPS}


# ---------------------------------------------------------------- генерация из диалекта (до перехода)

def from_dialect(root):
    """Схема вида из формы манифеста диалекта (form_source.canonical.view_form) словами стандарта."""
    from pathlib import Path

    from form_source.canonical import view_form
    from form_source.source import load_form

    from . import schema as gen
    form = load_form(Path(root) / "Platform/02-installer/spec/02.1-installer.form.yaml")
    s = gen.Gen(view_form(form)).schema("canonical view of a subsystem manifest, form %d" % FORM)

    def post(x):
        if isinstance(x, dict):
            if x.pop("x-ordered", None) and x.get("type") == "array":
                x[UNIQUE_BY] = "name"
            x.pop("x-class", None)
            if x.pop("x-integer-place", None):       # вид — после загрузчика: границы целого места он уже проверил
                for k in ("minimum", "maximum"):
                    if abs(x.get(k, 0)) == gen.INT53:
                        x.pop(k)
            for v in x.values():
                post(v)
        elif isinstance(x, list):
            for v in x:
                post(v)
    post(s)
    return s


# ---------------------------------------------------------------- проверка вида

def unique_names(schema, value):
    """Пути JSON Pointer списков с повтором `name` там, где схема говорит UNIQUE_BY (обход по $ref, properties,
    additionalProperties, items и ветвям allOf/anyOf)."""
    defs, out = schema.get("$defs", {}), []

    def deref(s):
        seen = set()
        while isinstance(s, dict) and "$ref" in s and s["$ref"] not in seen:
            seen.add(s["$ref"])
            s = defs.get(s["$ref"].rsplit("/", 1)[1], {})
        return s

    def rec(s, v, p):
        s = deref(s)
        if not isinstance(s, dict):
            return
        for e in s.get("allOf", []) + s.get("anyOf", []):
            if isinstance(e, dict):
                if "if" in e:
                    rec(e.get("then", {}), v, p)
                else:
                    rec(e, v, p)
        if isinstance(v, list):
            if UNIQUE_BY in s:
                names = [x.get(s[UNIQUE_BY]) for x in v if isinstance(x, dict)]
                if len(names) != len(set(map(json.dumps, names))):
                    out.append(p)
            if "items" in s:
                for i, x in enumerate(v):
                    rec(s["items"], x, "%s/%d" % (p, i))
        elif isinstance(v, dict):
            for k, x in v.items():
                c = (s.get("properties") or {}).get(k)
                if c is None and isinstance(s.get("additionalProperties"), dict):
                    c = s["additionalProperties"]
                if c is not None:
                    rec(c, x, "%s/%s" % (p, k.replace("~", "~0").replace("/", "~1")))
    rec(schema, value, "")
    return sorted(set(out))


# ---------------------------------------------------------------- раздел «Форма канонического вида» (глава 2.2)

class ViewSection(SchemaSection):
    def need(self, parent, k, s):
        if parent is None:
            return ""
        d = self.deref(s) if isinstance(s, dict) else {}
        step = (s.get("x-step") or d.get("x-step")) if isinstance(s, dict) else None
        phase = PHASE.get(step)
        if k in parent.get("required", []):
            why = "шаг %s" % step if phase == "computed" else "умолчание формы" if s.get("x-default") else ""
            out = "есть всегда" + (" (%s)" % why if why else "")
        elif phase == "computed":
            out = "есть по правилу отображения (шаг %s)" % step
        else:
            out = "есть, если сказан в манифесте"
        if phase == "sugar":
            out += "; сахар приведён (`%s`)" % step
        return out

    def act(self, t, description=None):
        return super().act(t, description).replace(" (путь — недостающий ключ)", "")

    def type_word(self, s, t):
        w = super().type_word(s, t)
        if t == "array" and s.get(UNIQUE_BY):
            w += "; порядок автора, `%s` без повторов (x-unique-by)" % s[UNIQUE_BY]
        return w


def build_view_section(view_doc):
    """Текст раздела главы 2.2 между маркерами BEGIN и END из схемы вида."""
    sec = ViewSection(view_doc)
    out = ["### Форма канонического вида (построена из стандартных файлов)", "",
           "Значение `manifest` строки `platform/manifest/<sub>/canonical/%d` — JSON (JCS, ADR-0072) этой формы: JSON "
           "Schema 2020-12 `02.2-installer.view.schema.json` (ADR-0089 п. 3, ADR-0092 слой 6). Отображение без имён "
           "автора закрыто: ключа вне таблицы нет. «Есть всегда» — ключ с умолчанием формы манифеста (`default` "
           "`02.1-installer.schema.json`) или шагом проекции; «есть, если сказан в манифесте» — ключ без умолчания, его "
           "отсутствие и есть значение. Отображение `x-ordered` формы манифеста — список объектов `{name, …}` в порядке "
           "автора. Правил и связей формы манифеста здесь нет: принятый манифест проверил установщик." % FORM, "",
           "#### Шаги урока 2", "",
           "Закрытый перечень: сахар — до умолчаний формы, вычисляемые умолчания — после них, до `ordered`.", "",
           "| Шаг | Норма | Когда | Что в виде |", "|---|---|---|---|"]
    for name, phase, norm, what, result in STEPS:
        out.append("| %s | %s | %s | %s |" % ("`%s`" % name if phase == "sugar" else name, norm, cell(what),
                                             cell(result)))
    out += [""] + sec.root_body() + sec.defs_body()
    return "\n".join(out).rstrip("\n") + "\n"
