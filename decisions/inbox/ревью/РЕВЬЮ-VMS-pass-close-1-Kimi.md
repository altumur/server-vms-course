---
kind: ревью
date: 2026-11-01
author: Kimi
to: «Архитектор»
object: разбор прохода V/01, V/02, V/11, ветка vms/pass-close-1, вершина 4ad9e50b8
---

# Ревью разбора прохода V/01, V/02, V/11 — Kimi

Срез: `git diff origin/main...4ad9e50b8` в ветке `vms/pass-close-1`. Разбор —
`decisions/inbox/2026-11-01-запрос-vms-разбор-прохода-01-02-11.md` (269 мест → 243 строки: ВЕРНО 160, НЕВЕРНО 60,
СПОРНО 23). Проверял по нормам и коду дерева, не по словам разбора.

## Итог

Возражений против вливания нет. Все проверенные правки по строкам ВЕРНО закрывают свои места и не ломают соседние;
выборка из 19 строк НЕВЕРНО — все отклонения обоснованы; отступления 1–7 подтверждены текстом; сценарий
`10-archives` сходится с нормой. Две мелочи (М-1, М-2) ниже — на вливание не влияют.

## 1. Правки по строкам ВЕРНО

Проверены все группы правок дельты:

- **V/01.5**: класс двери `mixed`; `id` без pattern; `from > to` судится только при обоих заданных; OpenAPI
  `Refusal` required `[error, detail]`, `RoleRefusal` — `[error]` (соответствует Н4 «Тело отказа — {error, detail}»
  и Н2 `{error, detail?}`); `max_playbacks` — обязательный integer без `null`; `coverage` — объект
  `{from, to, fragments, said_at}` с `x-time`/`x-integer` в layers.tsv, `additionalProperties: false`; `taken_by` —
  array string minLength 1. Сходится с нормами и свидетелем.
- **V/02**: `stop_timeout: 45` (манифест, README, 02.4 Н1.6; 31 с = WRITE_WINDOW 40 − RENEW_EVERY); вход только
  H.264 со словом статуса `codec not supported: <кодек>`; CONNECTIONS 256 / PER_ADDRESS 64 (02.9 Н1.3); PACE_FLOOR
  не на поток/удержание; `owed` только `unknown`, числа — `owed_s`/`owed_gaps`; obsd.contract (HELLO session/logLevel,
  SMPL Annex B, `end` = begin + 40 мс, новая последовательность может начаться раньше); VOLUME_FORMAT с
  tunables/label/checkSpace:false, последовательность MOUNT_RO→READER_INFO→READER_CLOSE→RECOVER→MOUNT_RW→второй
  UNCLEAN→away; rec/used identity байт-в-байт; block_small — поле пульса, не тревога; 02.5: подводка не режется,
  fenced, равный ключ → меньший слот, bytes не пересчитывается, avcC из первого ключевого, 404 `nothing recorded`,
  журнал только /segment; `url` тома сужен до `schemes: {file, s3}`.
- **V/11**: `repeats.steps` → string (потолок json 4000 байт подтверждён P/06.1); `held_by` подтверждён
  (P/06.1, rec.subsystem.yaml `placement.places.table: volumes`); порядок отказов 428→422→404→412; надгробия
  `{id, index, revision}`; opstep → 204 (P/06.9 код не фиксирует); NAME_TAKEN/NAME_REQUIRED; mapping.tsv:
  archiveKinds [local, cloud], volumeStates [ready, off], deviceModels [], cam/devices → none; `online` =
  `held_by ≠ null`, `state` = off|ready, `usedPercent` = 0.
- **Приёмка**: `@oneof` существует (Platform/common/acceptance/README.md); V/01 acc/4 переписан со строкой в
  corrections.tsv; V/02 acc/1 README и манифест auto; V/11 acc/4 — `10-archives` из 21 шага, README «десять
  сценариев, 246 шагов», profile-tests.tsv 15/8/70; шаги 13–15 retentionDays сходятся с 11.3 Н1.3.
- **Прочее**: допущение `about` в V/01.1 снято обоснованно (ответ «Архитектора» в запросе 2026-10-26; P/06.1
  «значение field непусто»); `<n>-<k>` → `<p>-<k>` в V/11.5 везде (grep чист); DETECTORS/ARCHIVES_SETUP без
  DEVICES_SETUP → 403; build_webui.py убран из 5 файлов; векторы family-read 01/02 перегенерированы (spot-check
  прошёл); ХОД-Спецификация-VMS.md дополнен.

## 2. Выборка строк НЕВЕРНО — 19 строк

Проверены строки разбора №№ 115, 118, 119, 122, 128, 134, 141, 151, 169, 184, 194, 201, 205, 212, 261, 287, 359,
362, 363 (и 366). Все отклонения обоснованы; ключевые сверки: `Device` required =
[id, type, parentId, domainId, name, online, enabled, version]; `ServerTelemetry` без required; `rec/keeps` и
подобные ключи в VMS/11-backend отсутствуют; enum licence-decision — 4 слова без `none`. Замечание: номера строк в
цитатах разбора местами смещены на 1–3 — на выводы не влияет, не дефект.

## 3. Отступления 1–7 и сценарий 10-archives

Все семь отступлений подтверждены в тексте норм; ссылка отступления 7 на «C42» — это V/01 C42 (класс `mixed`),
правка `role` → `mixed` в acc/5 README ему следует. Ширина `10-archives` сверх буквы разрешения оправдана 11.6 Н1.2
(перенос строки с проверкой). Сценарий сверен с нормой по шагам — расхождений нет.

## 4. Снятие `remote` и сужение `url` тома — потребители

`remote` вне VMS/11-backend не встречается (grep по VMS/ чист); в 11-backend остался только в
`consolem.openapi.json` (3 места) — контракт вендора, не правится. `volumeStates`, `archiveKinds`, `deviceModels`,
`smb://`, `nfs://` вне 11-backend не используются. `usedPercent` потребителей вне 11-backend не имеет, постоянное
`0` ни с чем не конфликтует. Известный остаток: подсказка s3 в `VMS/common/inventory.md:473` не правлена —
историческая опись, признано разбором в разделе «Открыто».

## 5. Не подтверждено мной

- `check_spec` я не прогонял: в дереве нет окружения (ни системный python3, ни venv не имеют yaml,
  openapi_spec_validator, markdown-it, ruamel, regress). Заявление разбора «check_spec PASS» остаётся на авторе
  разбора.
- Приёмка реализацией не прогонялась — разбор это признаёт; сценарии сверены только с нормой.

## Мелочи

- **М-1.** V/01.1 (строка ~86 разбора) цитирует «договор журнала событий шаг 2: при пустом значении поля — сама
  единица» — такой фразы в `Platform/common/contracts/event-journal.md` нет (шаг 2: «of: из about манифеста»).
  Реальное основание — ответ «Архитектора» в запросе 2026-10-26, семантика верна, атрибуция вольная.
- **М-2.** Front matter запроса `decisions/inbox/2026-10-26-запрос-vms-потоки-камеры.md` не обновлён
  (`status: открыт — после стадии C`), хотя ответ «Архитектора» внесён в тело.

## Строка «Архитектору»

Kimi: разбор прохода V/01, V/02, V/11 на 4ad9e50b8 — возражений нет (ВЕРНО-правки подтверждены, выборка НЕВЕРНО
19/19 обоснована, отступления 1–7 и 10-archives сходятся, потребителей remote вне контракта вендора нет); две
мелочи: М-1 атрибуция фразы договора журнала в V/01.1, М-2 устаревший status во front matter запроса 2026-10-26;
check_spec и приёмку не прогонял — на авторе разбора.
