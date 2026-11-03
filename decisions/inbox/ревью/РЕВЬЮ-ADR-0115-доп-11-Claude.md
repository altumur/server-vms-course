adr: 0115 (11)

# Ревью текста: ADR-0115 доп. (11) (Claude)

Доп. (11) на main cf5f197e0. Сверено с ключами `display` P/02.1 (`02.1-installer.norms.md:489`–`:544`) и psim-sdk c3d9ebb `plugin.schema.json`: у `object_types[]` есть `type`, `parent`, `name_key`, `parameters`, `events`, и описания у вида нет.

**Счёт: Б 0, С 0, М 1.** Места для подписи вида правда нет. `unit` / `units` / `units_count` — подпись единицы-плагина, `section` — одна, `fields` — поля, `kinds` — события. Форма `строка | {key, text}` и переводы `display.langs` — те же, что у `display.unit`. Подсказки у вида psim нет, второго ключа не нужно.

**М1. Подпись не для вида и нет подписи.**
- `<т>_seen` — `status` вида `<т>`, а не вид (ADR-0116 доп. (3) п. 3). Ключ `display.tables.<т>_seen` подписывать нечего. Предлагаю отказ загрузчика: генератор такой строки не даёт, а ручной манифест не должен.
- Нет `name_key` у `object_type`: в psim он необязателен. Тогда ключа `display.tables.<т>` нет. Назвать умолчание `UnitKind.label` — имя таблицы, как у `display.unit` умолчание «единица».
