# М11/10 — Передача держателя, резервная копия и восстановление, хранители: нормы

Канон урока. [Лекция](../10-holder-transfer-and-keepers.md), [HTTP-контракт](10-holder-transfer-and-keepers.api.openapi.yaml),
[инструкция](10-holder-transfer-and-keepers.README.md), [приёмка](../../Source/tests/testdata/acceptance/М11_Domain/10/README.md).
Строка `member` Н1.5, Н3 «следовать», «проверить резервную копию», команда `follow` и пункт М11/10-09 — [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md)
(стадия B; урок 9). Канон Н1.4, Н1.9 и пункта М11/10-04 — до переноса урока 10 (стадия B). Остальное перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) (стадия B; урок 8): вступление
Н1, Н1.1–Н1.3, Н1.5 без `member`, Н1.6–Н1.8, строки Н2 `/api/prepare`, `/api/take`, `/domain/move`, `/domain/handover`,
`/domain/stranded/apply`, «Гонки» Н3, строки Н4 процесса, сц. 02–04, 08–10, 12, пп. 2, 3 «Решает реализация», пункты
М11/10-01…03, -05…08, -10, -11. После переноса урока 10 файл снимается целиком.

## Н0 Словарь слов

Нормативные слова — по [канону курса](../../НОРМАТИВНЫЕ-СЛОВА.md). Порядок массивов вывода — урок 1 Н0 (общее М11).

## Н1 Форма

**Время.** Полей времени у оставшихся строк нет; `domain/holder` — [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1 «Время» (стадия B; урок 8).

**Данные** ([каталог](../../Platform/common/data/catalog.tsv)):
- читает: `domain/member-list`.

Строки агента хранителя (`domain/backup`, `domain/backup-taken`, `domain/backup-refused`) — [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md) Н1 «Данные», Н1.9
(стадия B; урок 9); читатель `domain/member-list` — консоль кластера (`/api/backup` Н1.9; до переноса урока 10).

Владение `domain/holder`, `domain/keepers/<член>`, `domain/backups/rev-<rev>`, `domain/stranded`, записи `domain/signer`,
`domain/signer-pending`, `domain/members` и чтения процесса `domain` — [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1 «Данные» (стадия B; урок 8).

Вступление Н1 перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1 (стадия B; урок 8).

### Н1.1 Запись срока `domain/holder`

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.1 (`claim`, `check`; форма — договор записи срока; стадия B; урок 8).

### Н1.2 Список членов при смене держателя

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.2 (стадия B; урок 8).

### Н1.3 Вид держателя: поле `term`

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.3 (стадия B; урок 8).

### Н1.4 `GET /api/held` у консоли кластера

```yaml
answer:     200 {cluster, holder, term, keys, backup}       # все ключи всегда
  cluster:  CLUSTER этой консоли
  holder:   документ domain/holder этого хранилища как объект (Н1.1) | null
  term:     его term | null
  keys:     документ domain/keys этого хранилища как объект (урок 2 Н1.2) | null
  backup:   {term, rev} строки domain/backup-taken этого хранилища | null — какая резервная копия здесь; содержимого нет никогда
refusal:    хранилище не ответило — 503 {error: "unavailable", detail: "the store did not answer"}
open:       без токена (P/06.3 Н1.3 open_routes): запись и набор доказывают себя сами; Authorization дверь не читает —
            негодный Bearer тоже 200 (решение «Архитектора» по сверке М11, X13)
```

### Н1.5 Резервная копия и хранители

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.5 (стадия B; урок 8). Строка `member` — [P/09.1 Н1.9](../../Platform/09-agent/spec/09.1-agent.norms.md) (стадия B; урок 9).

### Н1.6 Смещённый держатель

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.6 (`yields`, `switch`, `start`, `refusal`, `forget`, `stranded`, `apply`; стадия B; урок 8). Сторона
агента точки смены — [P/09.1 Н1.8](../../Platform/09-agent/spec/09.1-agent.norms.md), Н3 «следовать» 1а.

### Н1.7 Плановая передача

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.7 (стадия B; урок 8); дверь консоли домена `POST /domain/handover` — урок P/10.

### Н1.8 Аварийный перенос

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.8 (стадия B; урок 8); дверь `POST /domain/move` у консоли кластера цели (личность, грант admin)
— P/06.7-17, урок 10.

### Н1.9 `GET /api/backup` у консоли кластера

```yaml
ask:        заголовки X-W2C-Member, X-W2C-Time, X-W2C-Signature (договор подписи просьбы, ask = backup)
order:      нет заголовков — 401 {error: "refused", detail: «the backup a cluster keeps is the domain's state: a member
            signs its ask (X-W2C-Member, X-W2C-Time, X-W2C-Signature)»}; прочие отказы — тоже error "refused"; список членов не читается — 503; член не в domain/member-list этого кластера или
            без ключа — 403 «<m> is no member with a key on <c>'s list of members»; ключ отозван (revoked_keys записи,
            revoked_members набора) — 403 «<m>'s key was revoked by the domain's root»; ask-sig не ok — 401 со словом
answer:     200 {cluster, pointer: {term, rev, sha256} | null, backup: <текст документа> | null, shared: <текст общего документа, P/08.9 Н1.2> | null};
            резервная копия не читается — 503 «the copy <c> keeps did not read (…): not "none" — ask again»
```

---

## Н2 Двери

HTTP-контракт: [10-holder-transfer-and-keepers.api.openapi.yaml](10-holder-transfer-and-keepers.api.openapi.yaml). Тело отказа
— `{error, detail}`. Двери `/domain/*` консоли домена — строки [договора пересылки](../../Platform/common/contracts/forwarding.md) «Двери домена» (добавлено М11/10).

| Дверь | Кто | Успех | Отказы |
|---|---|---|---|
| GET `/api/held` | консоль кластера | Н1.4 | 503 |
| GET `/api/backup` | консоль кластера | Н1.9 | Н1.9 |

Двери процесса `domain` (`/api/prepare`, `/api/take`, `/domain/move`, `/domain/handover`, `/domain/stranded/apply`) —
[P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н2 (стадия B; урок 8).

---

## Н3 Проход

### record(keys, row, виды) — запись срока или документ с подписью Н1.1, по порядку

Абзац о видах и шаги 1–6 — [договор записи срока](../../Platform/common/contracts/record.md) «Функция `record`» (владелец [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md); перенесено туда без изменения; номера шагов
прежние; разбор ревью стадии A 8–10, № 13 / решение 2). Векторы — [`common/vectors/record`](../../Platform/common/vectors/record/README.md).

### следовать (агент члена, в каждом проходе раньше отчёта)

Перенесено в [P/09.1 Н3](../../Platform/09-agent/spec/09.1-agent.norms.md) «следовать»; функция `follow` — пакет [`follow`](../../Platform/09-agent/vectors/follow/README.md) (стадия B; урок 9).

### ask-sig — подпись просьбы

Сообщения `backup` и `prepare`, форма `X-W2C-Time`, `X-W2C-Signature` и порядок проверки (`missing`, `bad_time`, `skew`,
`bad_signature`) — [договор подписи просьбы](../../Platform/common/contracts/ask-sig.md) (владелец [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md); перенесено туда без изменения; разбор ревью стадии A 8–10, № 13 /
решение 2). Векторы — [`common/vectors/ask-sig`](../../Platform/common/vectors/ask-sig/README.md).

### проверить резервную копию (агент хранителя)

Перенесено в [P/09.1 Н3](../../Platform/09-agent/spec/09.1-agent.norms.md) «проверить резервную копию» (стадия B; урок 9).

**Гонки** — [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н3 (стадия B; урок 8).

---

## Н4 Отказы

| `error` | Код | Когда |
|---|---|---|
| `refused` | 401 | `/api/backup` без заголовков или ask-sig не ok (`detail` — слово; Н1.9) |
| `no signer here`, `did not answer` | 404, 502 | пересылка подписанту (урок 8 Н1.9) |
| `unavailable` | 503 | хранилище не ответило (`/api/held`, `/api/backup`) |

Строки `deposed`, `frozen`, `called off`, `refused` процесса (формы и отказы переноса, передачи, `apply`), `standby`,
`redo it on the new holder` — [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н4 (стадия B; урок 8).

Слова `record` — [договор записи срока](../../Platform/common/contracts/record.md) «Слова отказа». Слова `ask-sig` — [договор подписи
просьбы](../../Platform/common/contracts/ask-sig.md) «Слова отказа».

---

## Н5 Приёмка

Каталог `Source/tests/testdata/acceptance/М11_Domain/10/` ([README](../../Source/tests/testdata/acceptance/М11_Domain/10/README.md)):
стенд урока 3 с подписантом и на `m1` — сц. 01 (1 сценарий / 9 шагов). Сц. 06 снят: те же случаи — пакет
[`follow`](../../Platform/09-agent/vectors/follow/README.md) ([P/09.1 Н5](../../Platform/09-agent/spec/09.1-agent.norms.md); форма входа, вывод и коды выхода команды
`follow` — там); сц. 11 — [приёмка P/09.1](../../Platform/09-agent/acceptance/1/README.md) (номер прежний; стадия B; урок 9).
Сц. 02–04, 08–10, 12 — приёмка [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) ([`Platform/08-domain/acceptance/8/`](../../Platform/08-domain/acceptance/8/README.md);
стадия B; урок 8). Сц. 05, 07 сняты: те же случаи — [`common/vectors/record`](../../Platform/common/vectors/record/README.md),
[`common/vectors/ask-sig`](../../Platform/common/vectors/ask-sig/README.md); формы команд `record`, `ask-sig` и их коды выхода —
[P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н5 (стадия B; урок 8).

| № | Сценарий | Нормы |
|---|---|---|
| 01 | стенд: `/api/held` у членов, хранители `m1`, `m2`, пара резервной копии в `/api/held` и `view.term`; `/api/backup` без подписи — 401 | Н1.3–Н1.5, Н1.9 |

Сц. 06 снят переносом урока 9: те же случаи — пакет [`follow`](../../Platform/09-agent/vectors/follow/README.md); сц. 11
перенесён в [приёмку P/09.1](../../Platform/09-agent/acceptance/1/README.md) (номер прежний; стадия B, урок 9).

---

## Решает реализация

1. перенесено в [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md) «Решает реализация» п. 1 (команда `follow`; стадия B; урок 9); `record`, `ask-sig` — [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) «Решает реализация» п. 1;
2. и 3. перенесены в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) «Решает реализация» пп. 2, 3 (стадия B; урок 8).

---

## Чеклист готовности

- Пункт М11/10-01 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-01 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-02 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-02 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-03 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-03 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- [ ] **М11/10-04** `/api/held` Н1.4 — сц. 01; сц. 02 приёмки P/08.8; негодный Bearer — тоже 200 — чтением (X13)
- Пункт М11/10-05 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-04 (стадия B; [id-map](../../Platform/common/id-map.tsv)); агент хранителя — P/09.1-30 (стадия B; урок 9).
- Пункт М11/10-06 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-05 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-07 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-06 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-08 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-07 (стадия B; [id-map](../../Platform/common/id-map.tsv)); дверь `POST /domain/move` у консоли кластера цели — P/06.7-17, урок 10.
- Пункт М11/10-09 перенесён в [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md) как P/09.1-11 (стадия B; урок 9; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-10 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-08 (стадия B; [id-map](../../Platform/common/id-map.tsv)); дверь `GET /api/backup` Н1.9 — P/06.7-16, урок 10 (норма здесь до его переноса).
- Пункт М11/10-11 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-09 (стадия B; [id-map](../../Platform/common/id-map.tsv)); точка смены у агента — P/09.1-31 (стадия B; урок 9).

## Соответствие прежним урокам

Нормирует то, что рассказывали шаги 1–7 `М12A_Domain/14-a-domain-holder-on-one-node.md`: срок, что держит только
держатель (резервная копия), перенос, следование за большим сроком, возвращение старого держателя, брошенное, плановая передача.
Шаг 9 (корень вне держателя) — [P/08.2](../../Platform/08-domain/spec/08.2-domain.norms.md) (прежде урок 2); шаги 8 и 10 (камера-держатель, два процесса держателя) — [P/08.10 Н1.7](../../Platform/08-domain/spec/08.10-domain.norms.md) и [P/02.4 Н1.12](../../Platform/02-installer/spec/02.4-installer.norms.md) (прежде урок 12 Н1.7, Н1.8; лекция — [P/08](../../Platform/08-domain/08-domain.md), глава 8.8 «Камера-держатель»). ADR-0066 и его
дополнения, ADR-0075 уточнение 2, решение по `2026-10-15-first-holder-claim-diff`. Исторические исходники сохранены в Git. Вступление Н1, Н1.1–Н1.3, Н1.5
без `member`, Н1.6–Н1.8, строки Н2 и Н4 процесса, «Гонки» Н3, сц. 02–04, 08–10, 12, пп. 2, 3 «Решает реализация» и
пункты М11/10-01…03, -05…08, -10, -11 перенесены в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) (стадия B, урок 8). Строка `member` Н1.5 (здесь
P/09.1 Н1.9), сторона агента Н1.6 `switch` (P/09.1 Н1.8), Н3 «следовать», «проверить резервную копию», сц. 11, п. 1 «Решает
реализация» и пункт М11/10-09 перенесены в [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md); сц. 06 и входы `follow-*.json` сняты — те же случаи в пакете
`09-agent/vectors/follow` (стадия B, урок 9).
