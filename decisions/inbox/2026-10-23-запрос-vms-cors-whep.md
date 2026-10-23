---
kind: запрос
date: 2026-10-23
author: «Спецификация VMS» (перевод главы V/03.3)
blocks: 03-live — нет (обход ниже)
export: cammeta-specs f6f3895 (курс 175b75527)
status: решён
---

# Запрос: CORS двери процесса для маршрута с записью (WHEP)

**Какая норма мешает.** P/03.4 Н1.7 `cors.allow` (`03.4-worker.norms.md:221–222`): методы `GET`, `HEAD`; заголовки запроса
`Authorization`, `Range`; `Expose-Headers: Content-Range, Accept-Ranges, Content-Length`. Страница консоли (источник из
`CONSOLE_ORIGINS`) несёт оффер на дверь шлюза сама (решение владельца 1, ADR-0015): `POST /whep/<cam>` с
`Content-Type: application/sdp` (не простой запрос — preflight), читает заголовок ответа `Location` (сессия) и вешает трубку
`DELETE /whep/session/<sid>`. По норме браузер такой ответ странице не отдаст.

**Что нужно VMS.** Маршрут `whep` двери шлюза (V/03.3 Н1.4): разрешённому источнику — методы `POST`, `DELETE` (и `GET`,
`HEAD`), заголовки запроса `Authorization`, `Content-Type`, `Access-Control-Expose-Headers` дополнительно `Location`.

**Обход до решения.** V/03.3 Н1.4: шлюз отвечает так на маршруте `whep` правилом подсистемы (сверх `cors` P/03.4 Н1.7, те же
`CONSOLE_ORIGINS`, preflight до допуска); строка долга в `ХОД-Спецификация-VMS.md`.

**Рекомендация.** P/03.4 Н1.7 `cors.allow`: методы — `GET`, `HEAD`, `POST`, `PUT`, `DELETE` (дверь отвечает 405 на то, чего
маршрут не принимает); заголовки запроса — `Authorization`, `Range`, `Content-Type`; `Expose-Headers` — `Content-Range`,
`Accept-Ranges`, `Content-Length`, `Location`. Куки по-прежнему нет.

## Решение
Решён (2026-10-23, «Архитектор») ADR-0091 доп. (16): рекомендация принята — `cors.allow` P/03.4 Н1.7 расширяется для всех маршрутов (методы с записью, `Content-Type`, `Location`); куки нет, допуск маршрута прежний. Норма — «Спецификации» после ревью; обход (правило подсистемы на `whep`) снимается переходом.
