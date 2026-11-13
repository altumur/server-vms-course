# Модуль консоли — урок P/07

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом.

Микромодуль: JS-библиотека. Что нормирует и откуда — записка модуля `Platform/module-design.md` (только для судьи: записка для человека, вне выгрузки), таблица «Уроки».

Раскладка каталога (английский источник — на каноническом пути, русский текст для человека — в `ru/`). Урок одноглавный; своего HTTP-контракта, жизненного цикла, семей,
векторов и каталога приёмки у него нет: двери, которые модуль зовёт, — контракт урока P/06, публикация модуля — глава
6.5; проверка публикации — P/07-R264:

```text
README.md                                этот файл
spec/07-console-module.norms.md          нормы (одна глава; N2 — договор библиотеки)
spec/07-console-module.README.md         инструкция реализации
ru/                                      для человека, в выгрузку не входит — лекция ru/07-console-module.md, переводы английского текста тем же путём
```

## Что урок берёт из common

Ниже — общие договоры и интерфейсы других уроков, названные в нормах, инструкции и описании публичной поверхности. Таблица указывает существующие правила и не добавляет поведения модуля.

| Файл | Разделы | Что используется |
|---|---|---|
| [`common/NORMATIVE-TERMS.md`](../../common/ru/NORMATIVE-TERMS.md) | весь договор | нормативные слова |
| [`common/contracts/may.md`](../../common/ru/contracts/may.md) | [Функция `may`](../../common/ru/contracts/may.md#функция-may) | grants сессии, scope, ярусы групп и неизвестный вход папок |
| [`common/contracts/forwarding.md`](../../common/ru/contracts/forwarding.md) | [Двери домена](../../common/ru/contracts/forwarding.md#двери-домена) | закрытый список дверей домена и пересылка |
| [`common/contracts/gate-and-pass.md`](../../common/ru/contracts/gate-and-pass.md) | [Сторожевая](../../common/ru/contracts/gate-and-pass.md#сторожевая) | session и login_url |
| [`01-store/spec/01.1-store.norms.md`](../../01-store/ru/spec/01.1-store.norms.md) | [N0 Словарь слов](../../01-store/ru/spec/01.1-store.norms.md#n0-словарь-слов) | общие правила модуля |
| [`02-installer/spec/02.1-installer.norms.md`](../../02-installer/ru/spec/02.1-installer.norms.md) | [N1.2a Сводная таблица ключей](../../02-installer/ru/spec/02.1-installer.norms.md#n12a-сводная-таблица-ключей); [N1.2b Раздел `domain` — глава позднего слоя: вводит урок 8 (P/08.K); корпус держит загрузчик целиком](../../02-installer/ru/spec/02.1-installer.norms.md#n12b-раздел-domain--глава-позднего-слоя-вводит-урок-8-p08k-корпус-держит-загрузчик-целиком) | имена дверей платформы для распознавания таблицы |
| [`02-installer/spec/02.2-installer.norms.md`](../../02-installer/ru/spec/02.2-installer.norms.md) | [N1.2 Строка вида](../../02-installer/ru/spec/02.2-installer.norms.md#n12-строка-вида) | вид манифеста и writes_via |
| [`03-worker/spec/03.6-worker.norms.md`](../../03-worker/ru/spec/03.6-worker.norms.md) | [взгляд держателя (воркер, на проходе; ≤ REQUESTS_HOLD, ≤ COMMANDS_PER_LOOK)](../../03-worker/ru/spec/03.6-worker.norms.md#взгляд-держателя-воркер-на-проходе--requests_hold--commands_per_look) | писатель полей событий команд |
| [`06-console/spec/06-console.api.openapi.yaml`](../../06-console/spec/06-console.api.openapi.yaml) | весь договор | вызываемые HTTP-двери, типы ответов, WorkerRow и FieldView.hidden |
| [`06-console/spec/06-console.README.md`](../../06-console/ru/spec/06-console.README.md) | [Глава 6.5: выдаваемая форма `GET /manifest` и `Where`](../../06-console/ru/spec/06-console.README.md#глава-65-выдаваемая-форма-get-manifest-и-where) | проверка HTTP-двери Where отдельно от библиотеки |
| [`06-console/spec/06.1-console.norms.md`](../../06-console/ru/spec/06.1-console.norms.md) | [N1.1a Запись только по билету: `writes_via`](../../06-console/ru/spec/06.1-console.norms.md#n11a-запись-только-по-билету-writes_via); [Отказ: `error` и `field`](../../06-console/ru/spec/06.1-console.norms.md#отказ-error-и-field); [Версии: `revision`, индекс, `ETag`, `If-Match`](../../06-console/ru/spec/06.1-console.norms.md#версии-revision-индекс-etag-if-match); [Лента изменений](../../06-console/ru/spec/06.1-console.norms.md#лента-изменений); [память повторов — двери записи людей](../../06-console/ru/spec/06.1-console.norms.md#память-повторов--двери-записи-людей) | записи единиц/таблиц, версии, отказы поля, лента и владелец повторов |
| [`06-console/spec/06.3-console.norms.md`](../../06-console/ru/spec/06.3-console.norms.md) | [N1.3 Сторожевая](../../06-console/ru/spec/06.3-console.norms.md#n13-сторожевая) | сессия, вход и Сторожевая |
| [`06-console/spec/06.4-console.norms.md`](../../06-console/ru/spec/06.4-console.norms.md) | [N1.5 Просьба](../../06-console/ru/spec/06.4-console.norms.md#n15-просьба) | просьбы страницы через console.api |
| [`06-console/spec/06.5-console.norms.md`](../../06-console/ru/spec/06.5-console.norms.md) | [N1.1 Три части](../../06-console/ru/spec/06.5-console.norms.md#n11-три-части); [N1.2 `display`, `servers`, `console`](../../06-console/ru/spec/06.5-console.norms.md#n12-display-servers-console); [N2 Двери](../../06-console/ru/spec/06.5-console.norms.md#n2-двери); [Статические файлы подсистемы](../../06-console/ru/spec/06.5-console.norms.md#статические-файлы-подсистемы); [N4 Отказы](../../06-console/ru/spec/06.5-console.norms.md#n4-отказы) | байты модуля, параметры mount, display, наблюдения, публикация и отказ версии |
| [`06-console/spec/06.6-console.norms.md`](../../06-console/ru/spec/06.6-console.norms.md) | [N1.1 Строки консоли](../../06-console/ru/spec/06.6-console.norms.md#n11-строки-консоли); [N1.1a Схема](../../06-console/ru/spec/06.6-console.norms.md#n11a-схема); [N1.2 Дренаж](../../06-console/ru/spec/06.6-console.norms.md#n12-дренаж); [N2.1 Входы](../../06-console/ru/spec/06.6-console.norms.md#n21-входы) | настройки, policy, schema, drain и CAS дверей настроек |
| [`06-console/spec/06.7-console.norms.md`](../../06-console/ru/spec/06.7-console.norms.md) | [N1.12 `GET /api/held` у консоли кластера](../../06-console/ru/spec/06.7-console.norms.md#n112-get-apiheld-у-консоли-кластера); [N1.13 `GET /api/backup` у консоли кластера](../../06-console/ru/spec/06.7-console.norms.md#n113-get-apibackup-у-консоли-кластера); [N2 Двери](../../06-console/ru/spec/06.7-console.norms.md#n2-двери); [N1.8 Пересылка подписанту](../../06-console/ru/spec/06.7-console.norms.md#n18-пересылка-подписанту); [N1.11 Семьи ключей домена, `/domain/keys`](../../06-console/ru/spec/06.7-console.norms.md#n111-семьи-ключей-домена-domainkeys) | пересылка домена, held/shared и дверь backup вне вызовов модуля |
| [`06-console/spec/06.8-console.norms.md`](../../06-console/ru/spec/06.8-console.norms.md) | [N2 Двери](../../06-console/ru/spec/06.8-console.norms.md#n2-двери); [N3 Проход](../../06-console/ru/spec/06.8-console.norms.md#n3-проход) | маршруты папок, CAS с индексом хранилища в кавычках и права папок |
| [`06-console/acceptance/5/README.md`](../../06-console/ru/acceptance/5/README.md) | [Стенд: наблюдения](../../06-console/ru/acceptance/5/README.md#стенд-наблюдения) | проверки публикации и HTTP Where по P/07-R264 и P/07-R130; P/07-R266, P/07-01 и P/07-02 задают границу модуля/публикации |
| [`08-domain/spec/08-domain.api.openapi.yaml`](../../08-domain/spec/08-domain.api.openapi.yaml) | весь договор | формы дверей домена и ServedView.unread |
| [`08-domain/spec/08.4-domain.norms.md`](../../08-domain/ru/spec/08.4-domain.norms.md) | [N1.2 Вход, токен человека, отзыв](../../08-domain/ru/spec/08.4-domain.norms.md#n12-вход-токен-человека-отзыв) | login_url и POST /api/login |
| [`08-domain/spec/08.6-domain.norms.md`](../../08-domain/ru/spec/08.6-domain.norms.md) | [N2 Двери](../../08-domain/ru/spec/08.6-domain.norms.md#n2-двери) | версия записи для CAS размещения домена |
| [`08-domain/spec/08.8-domain.norms.md`](../../08-domain/ru/spec/08.8-domain.norms.md) | [N1.3 Вид держателя: поле `term`](../../08-domain/ru/spec/08.8-domain.norms.md#n13-вид-держателя-поле-term); [N1.7 Плановая передача](../../08-domain/ru/spec/08.8-domain.norms.md#n17-плановая-передача); [N1.8 Аварийный перенос](../../08-domain/ru/spec/08.8-domain.norms.md#n18-аварийный-перенос) | срок держателя, пары копий, backup_holders и передача |
| [`09-agent/spec/09.1-agent.norms.md`](../../09-agent/ru/spec/09.1-agent.norms.md) | [следовать (агент члена, в каждом проходе раньше отчёта)](../../09-agent/ru/spec/09.1-agent.norms.md#следовать-агент-члена-в-каждом-проходе-раньше-отчёта) | следование агента члена в описании публичной поверхности |
| [`10-domain-console/spec/10-domain-console.api.openapi.yaml`](../../10-domain-console/spec/10-domain-console.api.openapi.yaml) | весь договор | HTTP-двери консоли домена |
| [`10-domain-console/spec/10-domain-console.norms.md`](../../10-domain-console/ru/spec/10-domain-console.norms.md) | [N1.2 Двери чтения — отвечает сама](../../10-domain-console/ru/spec/10-domain-console.norms.md#n12-двери-чтения--отвечает-сама); [N1.7 Страница держателя](../../10-domain-console/ru/spec/10-domain-console.norms.md#n17-страница-держателя); [N1.8 Список тревог у держателя](../../10-domain-console/ru/spec/10-domain-console.norms.md#n18-список-тревог-у-держателя); [N2 Двери](../../10-domain-console/ru/spec/10-domain-console.norms.md#n2-двери) | непрозрачные страницы домена и unread, страница держателя, тревоги и shared schema |
