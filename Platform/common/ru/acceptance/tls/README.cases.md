# Данные случаев только для судьи

Этот русский текст — производный от `acceptance/tls/README.cases.md`, руками не правится (ADR-0121).

Общие правила остаются в [README.md](README.md). Следующие исходные отрывки сохраняют прежние связи именованных случаев как происхождение только для судьи.

### Исходный отрывок 1

(серверная сторона, возобновление сессий, рукопожатие по `ca-certs`) и четвёртый кластер. Форма
директив согласована «Архитектором» с «cammeta-acceptance» (2026-10-20); здесь — данные «Спецификации»: описание комплектов,
логические двери и клиенты, закрытый исход пробы и ожидания. Директивы — раздел [«Стенд домена»](../README.md#стенд-домена) общего README приёмки (формы ввёл урок M11/8 — колонка
«Урок» словаря; разбор ревью стадии B 8–10, № 22: M-1). Профиль реализации объявляет `keys.tls_stand: 1`; без него проверки этого стенда не исполнены

### Исходный отрывок 2

дверь `holder`, клиент `m2-console`, пересылаемый запрос с `X-Operator: console` → `{"handshake": "ok"}`, `http` — ответ

### Исходный отрывок 3

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
| `signer` | `null` | `{"handshake": "ok"}`, `http` — по подписи запроса (не 401 `no_role`) | `signer`: сертификат клиента не требуется |
| `signer` | `hold-domainconsole` | `{"handshake": "ok"}`, `http` — как у `null` | свой центр, роль `domainconsole` (`X-W2C-Client` стенд не наблюдает) |
| `signer` | лист `domainconsole` следующего центра `hold` (`ca.next.pem`) | `{"handshake": "ok"}`, `http` — как у `null` | ротация: центр из `ca.next.pem`; **долг стенда** — ниже |
| `signer` | `hold-domainconsole-sig-sha512` | `{"handshake": "ok"}`, `http` — как у `null` | подпись вне `sig` — после рукопожатия, только `X-W2C-Client` (стенд не наблюдает) |
| `signer` | `hold-domainconsole-expired` | `{"handshake": "alert", "http": null}` | срок листа |
| `signer` | `hold-domainconsole-server-only` | `{"handshake": "alert", "http": null}` | EKU без `clientAuth` |
| `signer` | `foreign-console` | `{"handshake": "alert", "http": null}` | центр не свой |
| `signer` | `m2-domainagent` | `{"handshake": "alert", "http": null}` | центр другого кластера: его клиенты лист сюда не предъявляют (договор сертификата роли `clients`) |

### Исходный отрывок 4

Смена объединения видна новым соединениям: `@stop agent m2`, затем `holder POST /domain/members/m2/ca {"ca": []}` (грант
admin; агент остановлен — его отчёт с `tls_ca` вернул бы центр, [P/08.3 N1.6](../../../../08-domain/ru/spec/08.3-domain.norms.md) `on_accept`; решение «Архитектора» 2026-10-21, как № 14) → следующая проба
`holder` / `m2-console` — `{"handshake": "alert", "http": null}`; возврат `{"ca": [<отпечаток m2>], "ca_certs": [<PEM m2>]}` →
снова `{"handshake": "ok"}`.

### Исходный отрывок 5

1. Положительный контроль до пробы: контрольный сервер оснастки выдаёт сессию, клиент предъявляет её и получает
   `reused: true`. Нет — проверка не исполнена (стенд), не провал реализации.
2. `holder` / `m2-console`, `save_session: s1` → `{"handshake": "ok", "reused": false}`; исход (а) `session_available:
   false` или (б) `session_available: true`.
3. При (б): `holder` / `m2-console`, `resume_session: s1` → `{"handshake": "ok", "reused": false}` (полное рукопожатие).
4. Снять центр: `@stop agent m2`, затем `holder POST /domain/members/m2/ca {"ca": []}`, без перезапуска сервера (агент
   остановлен — его отчёт с `tls_ca` вернул бы центр, [P/08.3 N1.6](../../../../08-domain/ru/spec/08.3-domain.norms.md) `on_accept`; решение «Архитектора» 2026-10-21, как № 14).
5. `holder` / `m2-console` новым соединением → `{"handshake": "alert", "http": null}`; при (б) — и с `resume_session: s1` →
   `{"handshake": "alert", "http": null}` (возобновления нет: билет прошлой сессии центр не возвращает). При (а) предъявление
   не исполняется и исполненным не объявляется.

### Исходный отрывок 6

| Шаг | Ожидание | Норма |
|---|---|---|
| `member m2 console GET /domain` (центр `m2` в объединении) | `200` — ответ консоли домена как пришёл (не 401/403 со словами `no_role`, `wrong_role`, `bad_chain`; ADR-0083 доп. (19) п. 2; разбор ревью ADR-0090, № 27) | `answer`, `tls` |
| после снятия центра `m2` (ниже): проба `holder` / `m2-console` — прямое соединение консоли члена с дверью роли держателя | `{"handshake": "alert", "http": null}` | `server.role`: центр `m2` вне объединения |
| после того же снятия: `member m2 console GET /domain`; журнал пересылающей | `200` — ответ консоли домена как пришёл, как в строке 1; `domain.forwarded {cluster, path, user, status: 200}` | снятие центра — не снятие членства: переход 1 — класс `signed`, к двери роли идёт консоль кластера держателя (P/10 N1.4 `server.role`); `journal` |
| `holder POST /domain/members/m2/ca {"ca": []}`, затем `holder POST /domain/members/m2/ca {"ca": [<отпечаток m2>]}` без `ca_certs` | оба — `200`; строки `ca-certs` нет (снята `[]`), проба `holder` / `m2-console` → `{"handshake": "alert", "http": null}` — член вне объединения, пока сертификатов под отпечатками нет | `admin`: «без ca_certs строка не меняется» |
| `holder POST /domain/members/m2/ca {"ca": [<отпечаток m2>], "ca_certs": [<PEM центра foreign>]}` | `400 {"error": "refused"}`; `Entry.ca` и строка `ca-certs` не меняются | `admin`, N4: sha256 не сходится |
| `holder POST /domain/members/m2/ca {"ca": [<sha256 DER листа m2-console>], "ca_certs": [<PEM листа m2-console>]}` | `400 {"error": "refused"}` — лист не центр (`CA:true`) | `admin`: «в том числе CA:true (иначе 400)» |
| `holder POST /domain/members/m2/ca` с теми же `ca`, `ca_certs` дважды | оба — `200`, `rev` второго ответа = `rev` первого + 1 | `admin`: «тот же ca снова — новая запись» |

### Исходный отрывок 7

Строки 2–3 — шаги (решение «Архитектора» 2026-10-21 по № 14, способ согласован с TLS-этапом «cammeta-acceptance»;
Т-правка по ADR-0083 доп. (18): прежние «502 у пересылающей» и журнал со `status: 502` сняты — по маршруту P/06.7 N1.4
к двери роли держателя идёт консоль кластера `hold`, чей центр в объединении всегда, а не консоль `m2`). Положительный
контроль строки 1 — до снятия, и сразу её журнал тем же чтением, что ниже: `events[0]` ⊇ `{kind: domain.forwarded,
cluster: hold, path: /domain, status: 200, id: $positive_forward_id}` — связать `id` ([P/05](../../../../05-resource/ru/spec/05-resource.norms.md)
N1.3 `row`; словарь «Стенда домена» `$name`); затем остановить агент `m2` (`@stop agent m2`: отчёт агента не вернёт центр в
объединение) и `holder POST /domain/members/m2/ca {"ca": []}`; после этого строка 2 — проба `@tls` двери `holder`
клиентом `m2-console`, строка 3 — `member m2 console GET /domain` → `200`. Журнал пересылающей (строка 3) читается
штатной дверью ресурса, без новой директивы: `@until 30 member m2 resource GET
/events?kind=domain.forwarded&unit=audit/console&keep=newest&limit=1` → `200`, `events[0]` ⊇ `{kind: domain.forwarded,
cluster: hold, path: /domain, user: <имя токена стенда>, status: 200, id: @not($positive_forward_id)}`
([P/05](../../../../05-resource/ru/spec/05-resource.norms.md) N1.3 `query`, `row`): обе пересылки дают `200`, и без `@not` по `id`
прежняя запись строки 1 дала бы ложный проход (замечание «cammeta-acceptance» 2026-10-21 к 967baf9ad).

### Исходный отрывок 8

| Шаг | Ожидание | Норма |
|---|---|---|
| `member hold console GET /domain` (исходный комплект) | `200` | `answer`, `tls` |
| журнал hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <имя>, status: 200, id: $hold_forward_ok}` | `journal` |
| `@tls-kit hold console foreign` | `ok` | — |
| `member hold console GET /domain` | `502 {"error": "did not answer", "detail": "!contains peer"}` — дверь роли отказала листу чужого центра рукопожатием | `answer`: отказ рукопожатия — сеть; P/10 N1.4 `server.role` |
| журнал hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <имя>, status: 502, id: @not($hold_forward_ok)}` | `journal`: отказ рукопожатия двери роли — 502 |
| `@tls-kit hold console hold` | `ok` | — |
| `member hold console GET /domain` | `200` | возврат |
| журнал hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <имя>, status: 200, id: @not($hold_forward_ok)}` — запись после возврата (запись отказа — `status: 502`) | `journal` |

### Исходный отрывок 9

| Шаг | Ожидание | Норма |
|---|---|---|
| `@tls`: дверь `member m1 console`, клиент `foreign-console`, запрос `GET /domain` | `{"handshake": "ok"}` | `signed`: по центру не отказывает |
| `@tls`: дверь `member m1 console`, клиент `null`, запрос `GET /domain` | `{"handshake": "ok"}` | `signed`: сертификата клиента не требует |
| `@person -`, затем `member m1 console @header X-Operator: console GET /domain/users` | `401` — сторожевая: токена нет, заголовок личностью не служит | `x_operator`, P/06.7 N1.9 |

### Исходный отрывок 10

| Шаг | Ожидание | Норма |
|---|---|---|
| `@kit-start console named` | `ok` — консоль с комплектом слушает на `CONSOLE_HOST` умолчания `127.0.0.1` | P/02.4 N1.6 `console`: TLS и на петле |
| `@tls`: дверь `kit`, `url` `https://127.0.0.1:{port}`, клиент `null`, `GET /healthz` | `{"handshake": "ok", "peer": "ok"}` | `own_client`: литерал петли — `host` = `box-n`, лист несёт `box-n` |
| `@tls`: дверь `kit`, `url` `https://localhost:{port}`, клиент `null`, `GET /healthz` | `{"peer": "wrong_name", "http": null}` | `loopback`: `localhost` — имя; у листа его нет; системный хост стенда не трогается |
| `@kit-start domainconsole none` | `@exit 2` | `DOMAIN_CONSOLE_HOST` умолчание `0.0.0.0` без комплекта — отказ старта (N1.6 `console`, `process`) |
| `@kit-start domain none` | `@exit 2` | `SIGNER_HOST` нет — умолчание процесса `0.0.0.0` не явный адрес: без комплекта — отказ старта ((5) п. 4) |
| `@kit-start domain none SIGNER_HOST=0.0.0.0` | `ok ~domain listens on ~without a certificate kit` | явный адрес вне петли без комплекта — старт с громкой строкой (N1.6 `process`) |
| `@kit-start console none TIMEZONE=` | `@exit 2` | [договор файла окружения](../../contracts/env-file.md) `TIMEZONE`: пустое значение не по форме (ADR-0094 B6; P/06.3-06) |
| `@kit-start console none TIMEZONE=+03:00` | `@exit 2` | то же: значение вне грамматики |
| `@kit-start console none TIMEZONE=Etc/GMT+5` | `ok` | значение по форме; у консоли на петле комплект не нужен, поэтому `@exit 2` строк выше дала сама переменная |
| `@kit-start console none TIMEZONE=No/Such_Zone` | `ok` | сверяется только форма: консоль базы поясов не читает |

### Исходный отрывок 11

Подготовка: `@clusters hold m1 m2 m3`, `@domain m1 m3`; хранители при `BACKUP_HOLDERS` 2 — `m3`, `m1` (порядок по убыванию
sha256 «hold/<член>»: `m3`, `m1`, `m2`; подтвердить на живом состоянии — строки `domain/keepers/<member>` держателя,
[P/08.8 N1.5](../../../../08-domain/ru/spec/08.8-domain.norms.md)); `@until` резервной копии у обоих хранителей; только затем — приём цели `m2` теми же шагами, что
`@domain`: `@start agent m2`, приём по отпечатку из `knocking` (`POST /domain/members`), `@join m2`, `@until` `m2` — `ok` и
держит набор держателя. Так `m2` не бывает хранителем ни на один проход и своей резервной копии не имеет: при
`@domain m1 m2 m3` член, принятый раньше прочих, успевал стать временным хранителем, а копию у члена не выбрасывает никто
(P/08.8 N1.5; без `copy` перенос восстановил бы её — N1.8 шаг 6 — вместо отказа; находка ER cammeta-go на 3e65002,
класс «данные», поручение «Архитектора» 2026-10-22). Затем `@until` у `m2` записи срока ≥ 1 (следование,
[P/09.1](../../../../09-agent/ru/spec/09.1-agent.norms.md) N3) и резервной копии у обоих хранителей; затем `@stop domain`.

### Исходный отрывок 12

- **«Сосед не ответил»** (ER, добавлено моделью Quint M11): `@cut-route m2 hold console`, `@cut-route m2 m1 console`,
  `@cut-route m2 m3 console` — ни один сосед не отвечает (держатель держит свою копию `domain/backups/rev-N` и иначе отдал бы
  её); `@start domain on m2`; `@move m2` (без `copy` и `why`) → `409 {"error": "refused", "detail": "~did not answer"}`;
  нового срока нет: `@move m2 why=…` на **другом экземпляре** той же подготовки → `200 {"holder": "m2", "restored_from":
  null}`, срок — прежний + 1.
