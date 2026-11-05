# Векторы переводчика нейтрального плана — V/11.13

Переводчик нейтрального плана в тело контракта (глава 13 Н1.4) и его отказы. Модели нет: план дан готовым. Ожидания выведены записью нормы, независимой от кода пилота; реализацией не проверены.

Текст производный от `vectors/rules-neutral/README.md`, руками не правится: источник — английский [`vectors/rules-neutral/README.md`](../../../vectors/rules-neutral/README.md), правка идёт в него, русский пересобирается переводом (ADR-0121).

## Файлы

| Файл | Что |
|---|---|
| `cases.json` | `world` — камеры, дети, папки, расписания, режимы, роли, правила, как у [`rules-words`](../rules-words/README.md); `cases` — `{id, note, plan, body, errors}`: `plan` — нейтральный `edits`, `body` — `AssistRuleEdit` по порядку, `errors` — слова отказа перевода |

- `body` — только то, что переводчик выводит из плана: умолчаний `Rule` и `logOnly` нового правила здесь нет, их ставят перевод и запись (Н1.4, Н1.7).
- `body` — словами контракта 0.2.0 (глава 13 Н1.3, Н1.4; ADR-0116 доп. (9)): триггер — `{source: unit, kinds, event, target, match}`, `kinds` — его строки `triggers` [`rule-catalog.json`](../../../data/rule-catalog.json); действие объекта — `{type: unitAction, action, target, params}`, `state` у `output` — `true`, `false`; действие системы — `{source: rule, action: runrule, ruleId}`; цель — `RuleTarget`: `include` `{uid}`, папка `{area: folder, uid}`, `exclude` по `uid`. Каждый триггер, шаг и условие при выводе сверены со схемой контракта, каталогом и [`kinds.json`](../../../data/kinds.json); id — знаки, `format: uuid` не судится.
- Id контракта — знаками `<вид>:<id мира>`: `device:<камера>`, `child:<ключ>`, `folder:`, `rule:`, `role:`, `schedule:`, `mode:`. Настоящий id — UUID по V/11.4 Н1.6, вектор его не судит.
- `errors` не пусты — `body` `null`: план не переведён, слои не судят.

В мире две камеры с одинаковыми детьми «Вход 1», «Реле 1», две камеры «Lift», два правила «Alarm», две папки «Floor 1» под разными родителями: имена с камерой и путём, отказы `several`, `is named with its camera`, `is named by its path`. `default`, `stop`, `via` переводчик несёт как есть: суды `default_yes`, `reset`, `via` — слои по строке, векторы [`rules-words`](../rules-words/README.md).

**Предел:** круг строка → тело → нейтральная → тело → строка эти векторы не проходят: перевод тела в строку V/07 (V/11.3 Н1.3) здесь не судится.
