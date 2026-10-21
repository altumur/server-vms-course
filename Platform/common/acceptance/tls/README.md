# TLS-стенд и четвёртый кластер — данные приёмки уроков 8–10

Долги стенда уроков 8–10 по ADR-0083 доп. (9) (решение владельца, 387a71377): TLS между кластерами
([`stage-a-after-m11.md`](../../stage-a-after-m11.md) пп. 2, 8 и рукопожатие из п. 7) и четвёртый кластер (п. 9). Форма
директив согласована «Архитектором» с «cammeta-acceptance» (2026-10-20); здесь — данные «Спецификации»: описание комплектов,
логические двери и клиенты, закрытый исход пробы и ожидания. Директивы — раздел [«Стенд домена»](../README.md#стенд-домена) общего README приёмки (формы ввёл урок М11/8 — колонка
«Урок» словаря; разбор ревью стадии B 8–10, № 22: М-1). Профиль реализации объявляет `keys.tls_stand: 1`; без него проверки этого стенда не исполнены
(не GREEN). Нормы: серверная сторона класса `signed` — договор сертификата роли «Серверная сторона: класс `signed`»
([P/08.0 Н1.6](../../../08-domain/spec/08.0-domain.norms.md), P/08.0-02); отпечатки центра члена, `on_accept`, `admin` —
[P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md); `client`, `first` и функция `peer` — [договор `peer`](../../contracts/peer.md);
пересылка — [договор пересылки](../../contracts/forwarding.md); класс `role` — [P/10 Н1.4](../../../10-domain-console/spec/10-domain-console.norms.md) `server.role`
(P/10-11); договор сертификата роли — [`role-certificate.md`](../../contracts/role-certificate.md); перенос —
[P/08.8 Н1.8](../../../08-domain/spec/08.8-domain.norms.md). Пункт 3 и «держатель прежней сборки» из п. 7 — проверка чтением
([P/08.4 Н5](../../../08-domain/spec/08.4-domain.norms.md) и [P/08.3 Н5](../../../08-domain/spec/08.3-domain.norms.md)).

## Комплекты: [`stand.json`](stand.json)

Раннер материализует комплекты по описанию в момент `@tls-setup` (до создания стенда), по своим часам: готовых ключей в
курсе нет, сроки всегда годятся реальному времени. Ключи — только тестовые, в отчёт прогона не попадают.

| Поле | Смысл |
|---|---|
| `version` | форма описания, `1` |
| `server` | имя сервера всех кластеров стенда (`localhost`): кластеры различаются именем, центром, портами и каталогами |
| `defaults.ca` | центр кластера: ключ (`ec-p256`), подпись (`sha256` — ECDSA с SHA-256), `not_before` — секунды от момента выпуска (отрицательное — в прошлом), `days` — срок от `not_before`; `CA:true`, `keyCertSign`, `cRLSign`; самоподписан |
| `defaults.leaf` | лист роли по договору сертификата роли `cert`: CN `<роль>.<server>`, SAN DNS `<server>`, SAN URI `urn:w2c:role:<роль>` — ровно одна, EKU `serverAuth` + `clientAuth`, `days` 825; подпись центром своего кластера |
| `clusters` | кластер → роли его комплекта: центр кластера и лист на каждую роль; раскладка — договор `kit` (`ca.pem`, `<роль>/server.pem`, `<роль>/server.key`) в `W2C_TLS_DIR` кластера; `revoked` пуст, `ca.next.pem` нет |
| `foreign` | роли комплекта «чужого» центра: свой центр, который ни один кластер не публикует (`tls_ca`) и не держит |
| `negative` | клиентские листы для проб: `issuer` — кластер, чей центр подписывает; `role` — роль листа; прочие поля заменяют умолчание листа: `uri: null` — без SAN URI, `eku` — свой набор, `sig` — подпись листа (`sha512` — ECDSA с SHA-512, вне закрытого списка договора `sig`), `not_before`, `days` — свой срок |

Отпечаток центра — sha256 hex DER ([P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `fingerprint`). Раннер называет каждому кластеру его каталог комплекта
(`W2C_TLS_DIR`) и начальный отпечаток держателя (`DOMAIN_CA` рядом с `DOMAIN_URL`, [договор `peer`](../../contracts/peer.md) «Клиент и первый контакт» `first`). Публикация
`tls_ca`/`tls_ca_certs` — дело реализации по норме: стенд их не подставляет.

## Двери и клиенты пробы `@tls`

| Дверь | Что | Класс (договор сертификата роли «Серверная сторона»; `role` — P/10 Н1.4 `server.role`) |
|---|---|---|
| `holder` | консоль домена на `hold` — приём пересылки с `X-Operator: console`; по маршруту P/06.7 Н1.4 её клиент — консоль кластера `hold`, прямое соединение консоли члена — проба `@tls` (ADR-0083 доп. (18)) | `role` |
| `signer` | процесс `domain` на `hold` — `POST /api/member/<член>`, `GET /api/carry/<член>` | `signed` |
| `member <кластер> console` | консоль кластера (`/domain/at/…`, пересылка) | `signed` для входящих из других кластеров: сертификата клиента не запрашивает, `X-Operator: console` снимает ([P/06.7](../../../06-console/spec/06.7-console.norms.md) Н1.7 `server`; ADR-0083 доп. (18)) |

Клиент — имя листа: `<кластер>-<роль>` (`m2-console`, `m2-domainagent`, `foreign-console`) или ключ `negative`
(`m2-no-role`, …); `null` — без сертификата клиента. Клиент проверяет сервер по центру кластера двери (`client` договора `peer`);
ошибка этой проверки — исход инструмента, не TLS alert.

## Исход пробы — закрытая форма

```json
{"handshake": "ok" | "alert", "version": "TLSv1.2" | "TLSv1.3" | null, "reused": true | false,
 "session_available": true | false, "http": null | {"status": <код>, "body": <JSON | текст>}}
```

- `handshake: ok` — рукопожатие завершено, `http` — ответ двери на `request` пробы (полная форма — контракт двери).
- `handshake: alert` — сервер отказал рукопожатием (TLS alert): `http: null`; `version` — выбранная версия или `null`, если
  отказ раньше выбора; `reused: false`, `session_available: false`.
- `reused` — сессия предъявлена и сервер её возобновил; `session_available` — сервер выдал пригодную сессию (билет или
  идентификатор) за это соединение.
- Отказ соединения, обрыв, таймаут, ошибка проверки сервера клиентом и ошибка инструмента — класс «стенд»: исходом
  пробы не являются и не удовлетворяют ни одному ожиданию. Текст библиотеки и номер alert — диагностика, не слово
  реализации.

Ожидание в строке сценария — `ok <JSON>` (словарь «Стенда домена», `@tls`); JSON сравнивается подмножеством полей поверх закрытой формы.

## Ожидания

Подготовка всех проб: `@clusters hold m1 m2 m3` (п. 9 — четвёртый кластер; для пп. 2, 7, 8 достаточно `hold m1 m2`),
`@tls-setup …/stand.json`, `@domain m1 m2` (или `m1 m2 m3`), затем `@until` записи члена: у `m2` — `Entry.ca` с
отпечатком центра `m2` и строка `domain/members/m2/ca-certs` (`on_accept`, приём отчёта с `tls_ca`, `tls_ca_certs`).

**П. 7 — рукопожатие по `ca-certs`** ([P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; [P/10 Н1.4](../../../10-domain-console/spec/10-domain-console.norms.md) `server.role`): после строки `ca-certs` и `Entry.ca`
дверь `holder`, клиент `m2-console`, пересылаемый запрос с `X-Operator: console` → `{"handshake": "ok"}`, `http` — ответ
двери по сторожевой (не 401/403 со словами `no_role`, `wrong_role`, `bad_chain`).

**П. 2 — серверная сторона** (строки двери `signer` — класс `signed`, P/08.0-02, договор сертификата роли; строки
`holder` — класс `role`, P/10 Н1.4 `server.role`):

| Дверь | Клиент | Ожидание | Норма |
|---|---|---|---|
| `holder` | `m2-console` | `{"handshake": "ok"}`, `http.body.error` ∉ {`no_role`, `wrong_role`, `bad_chain`} | `role`: центр в объединении |
| `holder` | `null` | `{"handshake": "ok", "http": {"status": 401, "body": {"error": "no_role"}}}` | нет сертификата клиента — 401 |
| `holder` | `m2-domainagent` | `{"handshake": "ok", "http": {"status": 403, "body": {"error": "wrong_role"}}}` | шаги 6–7 peer: роль не `console` |
| `holder` | `m2-no-role` | `{"handshake": "ok", "http": {"status": 403, "body": {"error": "no_role"}}}` | лист без роли |
| `holder` | `m2-sig-sha512` | `{"handshake": "ok", "http": {"status": 403, "body": {"error": "bad_chain"}}}` | закрытый список `sig` — после рукопожатия |
| `holder` | `foreign-console` | `{"handshake": "alert", "http": null}` | центр вне объединения |
| `holder` | `m2-expired` | `{"handshake": "alert", "http": null}` | срок листа |
| `holder` | `m2-server-only` | `{"handshake": "alert", "http": null}` | EKU без `clientAuth` |
| `holder` | `m3-console`, `m3` без `Entry.ca` (до отчёта с `tls_ca`) | `{"handshake": "alert", "http": null}` | член вне объединения |
| `signer` | `null` | `{"handshake": "ok"}`, `http` — по подписи запроса (не 401 `no_role`) | `signed`: сертификат клиента не требуется |
| `signer` | `foreign-console` | `{"handshake": "ok"}`, `http` — как у `null` | `signed`: предъявленный не проверяется |

Смена объединения видна новым соединениям: `@stop agent m2`, затем `holder POST /domain/members/m2/ca {"ca": []}` (грант
admin; агент остановлен — его отчёт с `tls_ca` вернул бы центр, [P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; решение «Архитектора» 2026-10-21, как № 14) → следующая проба
`holder` / `m2-console` — `{"handshake": "alert", "http": null}`; возврат `{"ca": [<отпечаток m2>], "ca_certs": [<PEM m2>]}` →
снова `{"handshake": "ok"}`.

**П. 8 — возобновление** (P/10 Н1.4 `server.role`: сессий не возобновляет; решение «Архитектора» 2026-10-20 — проходят
оба исхода):

1. Положительный контроль до пробы: контрольный сервер оснастки выдаёт сессию, клиент предъявляет её и получает
   `reused: true`. Нет — проверка не исполнена (стенд), не провал реализации.
2. `holder` / `m2-console`, `save_session: s1` → `{"handshake": "ok", "reused": false}`; исход (а) `session_available:
   false` или (б) `session_available: true`.
3. При (б): `holder` / `m2-console`, `resume_session: s1` → `{"handshake": "ok", "reused": false}` (полное рукопожатие).
4. Снять центр: `@stop agent m2`, затем `holder POST /domain/members/m2/ca {"ca": []}`, без перезапуска сервера (агент
   остановлен — его отчёт с `tls_ca` вернул бы центр, [P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; решение «Архитектора» 2026-10-21, как № 14).
5. `holder` / `m2-console` новым соединением → `{"handshake": "alert", "http": null}`; при (б) — и с `resume_session: s1` →
   `{"handshake": "alert", "http": null}` (возобновления нет: билет прошлой сессии центр не возвращает). При (а) предъявление
   не исполняется и исполненным не объявляется.

**Пересылка через дверь роли и ветки `admin`** (разбор ревью стадии B 8–10, № 14; разбор ревью стадии A 8–10, № 36).
Данные «Спецификации»; шаги и сценарий пишет TLS-этап «cammeta-acceptance»; до того — долг стенда. Подготовка — как у п. 2.
Нормы: [договор пересылки](../../contracts/forwarding.md) «Пересылка — одна функция» `answer`, `journal`, `tls`;
[P/06.7 Н1.7](../../../06-console/spec/06.7-console.norms.md) `server` (переход 1 — класс `signed`);
[P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `admin`, Н4; [P/10 Н1.4](../../../10-domain-console/spec/10-domain-console.norms.md) `server.role`.

| Шаг | Ожидание | Норма |
|---|---|---|
| `member m2 console GET /domain` (центр `m2` в объединении) | ответ консоли домена как пришёл: не 502, `error` ∉ {`no_role`, `wrong_role`, `bad_chain`} | `answer`, `tls` |
| после снятия центра `m2` (ниже): проба `holder` / `m2-console` — прямое соединение консоли члена с дверью роли держателя | `{"handshake": "alert", "http": null}` | `server.role`: центр `m2` вне объединения |
| после того же снятия: `member m2 console GET /domain`; журнал пересылающей | `200` — ответ консоли домена как пришёл, как в строке 1; `domain.forwarded {cluster, path, user, status: 200}` | снятие центра — не снятие членства: переход 1 — класс `signed`, к двери роли идёт консоль кластера держателя (P/10 Н1.4 `server.role`); `journal` |
| `holder POST /domain/members/m2/ca {"ca": []}`, затем `holder POST /domain/members/m2/ca {"ca": [<отпечаток m2>]}` без `ca_certs` | оба — `200`; строки `ca-certs` нет (снята `[]`), проба `holder` / `m2-console` → `{"handshake": "alert", "http": null}` — член вне объединения, пока сертификатов под отпечатками нет | `admin`: «без ca_certs строка не меняется» |
| `holder POST /domain/members/m2/ca {"ca": [<отпечаток m2>], "ca_certs": [<PEM центра foreign>]}` | `400 {"error": "refused"}`; `Entry.ca` и строка `ca-certs` не меняются | `admin`, Н4: sha256 не сходится |
| `holder POST /domain/members/m2/ca {"ca": [<sha256 DER листа m2-console>], "ca_certs": [<PEM листа m2-console>]}` | `400 {"error": "refused"}` — лист не центр (`CA:true`) | `admin`: «в том числе CA:true (иначе 400)» |
| `holder POST /domain/members/m2/ca` с теми же `ca`, `ca_certs` дважды | оба — `200`, `rev` второго ответа = `rev` первого + 1 | `admin`: «тот же ca снова — новая запись» |

Строки 2–3 — шаги (решение «Архитектора» 2026-10-21 по № 14, способ согласован с TLS-этапом «cammeta-acceptance»;
Т-правка по ADR-0083 доп. (18): прежние «502 у пересылающей» и журнал со `status: 502` сняты — по маршруту P/06.7 Н1.4
к двери роли держателя идёт консоль кластера `hold`, чей центр в объединении всегда, а не консоль `m2`). Положительный
контроль строки 1 — до снятия, и сразу её журнал тем же чтением, что ниже: `events[0]` ⊇ `{kind: domain.forwarded,
cluster: hold, path: /domain, status: 200, id: $positive_forward_id}` — связать `id` ([P/05](../../../05-resource/spec/05-resource.norms.md)
Н1.3 `row`; словарь «Стенда домена» `$имя`); затем остановить агент `m2` (`@stop agent m2`: отчёт агента не вернёт центр в
объединение) и `holder POST /domain/members/m2/ca {"ca": []}`; после этого строка 2 — проба `@tls` двери `holder`
клиентом `m2-console`, строка 3 — `member m2 console GET /domain` → `200`. Журнал пересылающей (строка 3) читается
штатной дверью ресурса, без новой директивы: `@until 30 member m2 resource GET
/events?kind=domain.forwarded&unit=audit/console&keep=newest&limit=1` → `200`, `events[0]` ⊇ `{kind: domain.forwarded,
cluster: hold, path: /domain, user: <имя токена стенда>, status: 200, id: @not($positive_forward_id)}`
([P/05](../../../05-resource/spec/05-resource.norms.md) Н1.3 `query`, `row`): обе пересылки дают `200`, и без `@not` по `id`
прежняя запись строки 1 дала бы ложный проход (замечание «cammeta-acceptance» 2026-10-21 к 967baf9ad).

## Четвёртый кластер — ветви ER (п. 9; [P/08.8 Н1.8](../../../08-domain/spec/08.8-domain.norms.md) шаг 6)

Подготовка: `@clusters hold m1 m2 m3`, `@domain m1 m2 m3`; хранители при `BACKUP_HOLDERS` 2 — по хеш-порядку `m3`, `m1`
(подтвердить на живом состоянии — строки `domain/keepers/<член>` держателя, [P/08.8 Н1.5](../../../08-domain/spec/08.8-domain.norms.md)); цель без своей резервной копии —
`m2`; `@until` у `m2` записи срока ≥ 1 (следование, [P/09.1](../../../09-agent/spec/09.1-agent.norms.md) Н3) и резервной копии у обоих хранителей; затем `@stop domain`.

- **«Сосед не ответил»** (ER, добавлено моделью Quint М11): `@cut-route m2 hold console`, `@cut-route m2 m1 console`,
  `@cut-route m2 m3 console` — ни один сосед не отвечает (держатель держит свою копию `domain/backups/rev-N` и иначе отдал бы
  её); `@start domain on m2`; `@move m2` (без `copy` и `why`) → `409 {"error": "refused", "detail": "~did not answer"}`;
  нового срока нет: `@move m2 why=…` на **другом экземпляре** той же подготовки → `200 {"holder": "m2", "restored_from":
  null}`, срок — прежний + 1.
- **«Копии нет нигде, все ответили»** (без `why` — 409, с `why` — «из ничего») и **«нет ни записи, ни копии»** (шаг 6,
  `nothing to restore from`): на публичных дверях стенда недостижимы детерминированно — первая резервная копия делается
  первым проходом держателя, держатель и хранители её отдают; член без записи срока не получает и грантов (личность
  переноса). Снять копии подготовкой стенда тоже нельзя: резервные копии — объекты (`domain/backup` у хранителя,
  `domain/backups/rev-*` у держателя; P/08.8 Н1.5), admin-операции хранилища удаляют строки (снять можно лишь указатель
  `domain/backup-taken`), общего договора удаления объектов нет; частные файлы реализации стенд не трогает (согласовано с
  «cammeta-acceptance», решение «Архитектора» 2026-10-20). Проверка чтением — [P/08.8 Н5](../../../08-domain/spec/08.8-domain.norms.md) («Проверяются чтением», шаг 6
  переноса), как п. 3; README приёмки [главы 8.8](../../../08-domain/acceptance/8/README.md), сц. 03.
