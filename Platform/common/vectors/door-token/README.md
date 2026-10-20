# Векторы токена двери

Векторы [договора токена двери](../../contracts/door-token.md): выпуск `door1.<kid>.<claims>.<sig>` (claims в JCS, подпись
Ed25519) и проверка у держателя по строке `door/keys`. Владелец договора — урок P/06, глава
[6.5](../../../06-console/spec/06.5-console.norms.md) (Н3 «`/where/<id>`»: консоль выдаёт токен); проверяющий — держатель
двери, глава [3.4](../../../03-worker/spec/03.4-worker.norms.md) Н3 «токен двери у держателя» (P/03.4-08). Пакет — общий:
алгоритм пишет один процесс, читают другие (решение «Архитектора» 2026-10-20, разбор ревью стадии B 3–5: подпись Ed25519
без векторов — молчаливое расхождение реализаций). Байты пишет «Спецификация» (ADR-0083); соответствие продукта — его
приёмкой по этим таблицам (ADR-0080 доп. 16).

## Прогон

Без стенда: консоль проходит `issue.tsv` своей функцией выпуска, держатель — `verify.tsv` своей функцией проверки; каждая
сторона может пройти обе таблицы. Время — входом `now` (стенные секунды), не часами процесса.

- `issue.tsv` — выпуск(`seed_hex`, `kid`, `claims`) даёт `claims_jcs` и `token` байт в байт. Ed25519 (RFC 8032)
  детерминирован: тот же seed и та же строка дают ту же подпись.
- `verify.tsv` — проверка(`keys`, `token`, `now`, `unit`, `holder`, `path`) даёт `ok` и прочитанные claims, равные
  колонке `claims`, или `forbidden`.

## Ключи

Зерно Ed25519 — 32 байта `sha256("w2c test <слово>")` (как ключи [векторов запечатывания](../sealing/README.md)); слова
порождения таблицы не называют — зерно и открытый ключ зафиксированы байтами, реализация берёт их отсюда и заново не
порождает (SA67-Б3). Зерно — то, что строка `door/signer` держит в `seed_secret` (64 строчных hex); открытый ключ — значение
строки `door/keys` под тем же `kid`.

| kid в векторах | seed_hex | открытый ключ (door/keys) |
|---|---|---|
| `c1` | `72207cdee579aae6185325025d5d4f82594247e8301c16b85909b5c363c2b8a9` | `865e70360600cb7dd29abc35426a83480f2d4039240f75d4d1ba2bcf894ea0db` |
| `c2-0123456789-abcdefghijklmnopqr` | `8e94e9035d25f0d2247b327ad5337ada38f934acd24c03e1aad23b4742f7f21a` | `3a42558c6b12b6e1dbcfc146e59401bffa3bd524e151493b65e2817e248d2428` |
| — (подделка) | `cc7b7d5d5b400b7efbf2053fae514d14d8daf638546d30bee836e95d671159ea` | `b3bfa2c840017b6309526eed5e4c0285630ab9b9db612d503afd1961cd3ae146` |

Третье зерно подписывает строку `forged_signer`; в `door/keys` векторов его ключа нет.

## Файлы

UTF-8, LF, поля через TAB; строки с `#` и пустые пропускаются, первая непропущенная — заголовок; `case` — имя строки,
`note` — зачем строка.

| Файл | Вход → ожидание |
|---|---|
| [`issue.tsv`](issue.tsv), 7 строк | `seed_hex`, `kid`, `now`, `claims` — объект `{user, unit, holder, routes, expires}` текстом JSON, как передан выпускающему (`expires` = `now` + 120) → `claims_jcs` — его форма RFC 8785 (UTF-8), `token` — `door1.<kid>.<base64url без «=» claims_jcs>.<base64url без «=» подписи над ASCII «door1.<kid>.<claims>»>`. Случаи: обычный, порядок полей (тот же токен), порядок `routes` (массив не сортируется), кириллица и символ вне BMP, экранирование, число с порядком, `kid` в 32 знака |
| [`verify.tsv`](verify.tsv), 56 строк: 8 `ok`, 48 `forbidden` | `keys` — значение строки `door/keys` текстом JSON; `token`; `now`; `unit`, `holder` — свои у держателя (`unit` — `<sub>/<id>`, `holder` — `instance` его пульса); `path` — путь запроса к двери держателя, его первый сегмент сравнивается с элементами `routes` → `ok` и `claims` (текст части claims) или `forbidden` (колонка `claims` пуста) |

## Отказы

Отказ проверки — одно слово `forbidden`, ответ двери держателя 403 с телом `{"error": "forbidden"}` без причины ([P/03.4](../../../03-worker/spec/03.4-worker.norms.md)
Н4, [договор](../../contracts/door-token.md) «Ключи `door/keys`») (решение «Архитектора» 2026-10-20, векторы door-token). Порядок проверок
вектор не фиксирует: причина в ответе не видна. Строки отказа — по списку проверки договора:

| Проверка договора | Строки |
|---|---|
| четыре части | `three_parts`, `five_parts`, `token_empty` |
| `door1` | `prefix_door2`, `prefix_upper` |
| `kid` в `door/keys` (нечитаемая строка — `kid` не найден, [исход семьи](../../../06-console/data/door-keys.outcomes.tsv)) | `unknown_kid`, `empty_keys`, `keys_upper_hex`, `keys_short_hex`, `keys_not_object` |
| подпись | `foreign_key`, `forged_signer`, `sig_bit`, `sig_last_bit`, `sig_short`, `claims_swapped` |
| части — строгий base64url без «=», хвостовые биты последнего знака — нули | `sig_padded`, `claims_padded`, `claims_std_base64`, `sig_trailing_bits`, `claims_trailing_bits` |
| claims ровно `{user, unit, holder, routes, expires}` | `extra_field`, `missing_user`, `missing_expires`, `missing_unit`, `missing_holder`, `missing_routes`, `claims_not_json` |
| типы claims: `user`, `unit`, `holder` — строки; `routes` — массив строк без повторов; `expires` — целое ≤ 2^53−1 (решение «Архитектора» 2026-10-20, Kimi SB67-01) | `user_number`, `unit_number`, `holder_null`, `routes_not_array`, `routes_item_number`, `routes_dup`, `expires_string`, `expires_float`, `expires_over_2_53` |
| `now < expires` (граница `now = expires` — отказ) | `expired_boundary`, `expired_after` |
| `unit` и `holder` свои | `other_unit`, `other_sub`, `other_holder` |
| первый сегмент пути запроса, сырым без раскодирования `%XX`, — элемент `routes` байт в байт | `route_not_in_routes`, `route_segment_prefix`, `route_second_segment`, `route_root`, `route_case`, `route_percent` |

Строка `ok_expires_max` — контроль границы типа: `expires` = 2^53−1 даёт `ok`. Строка `claims_not_jcs` ждёт `ok`: выпускающий обязан писать claims в JCS, а проверяющий канон не проверяет, потому что
подпись покрывает байты части claims (решение «Архитектора» 2026-10-20, векторы door-token).

Векторы получены эталонными Ed25519 (RFC 8032) и JCS (RFC 8785, проверен на [`jcs`](../../../01-store/vectors/jcs/README.md))
по договору, не по коду реализаций; при расхождении прав договор, вектор правит «Спецификация».
