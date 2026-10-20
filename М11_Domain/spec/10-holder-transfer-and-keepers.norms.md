# М11/10 — Передача держателя, резервная копия и восстановление, хранители: нормы

Канон урока. [Лекция](../10-holder-transfer-and-keepers.md), [HTTP-контракт](10-holder-transfer-and-keepers.api.openapi.yaml),
[инструкция](10-holder-transfer-and-keepers.README.md), [приёмка](../../Source/tests/testdata/acceptance/М11_Domain/10/README.md).
Канон Н1.4, Н1.9, строки `member` Н1.5, Н3 «следовать» и «проверить резервную копию», команды `follow` и пунктов
М11/10-04, -09 — до переноса уроков 9 и 10 (стадия B). Остальное перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) (стадия B; урок 8): вступление
Н1, Н1.1–Н1.3, Н1.5 без `member`, Н1.6–Н1.8, строки Н2 `/api/prepare`, `/api/take`, `/domain/move`, `/domain/handover`,
`/domain/stranded/apply`, «Гонки» Н3, строки Н4 процесса, сц. 02–04, 08–10, 12, пп. 2, 3 «Решает реализация», пункты
М11/10-01…03, -05…08, -10, -11. После переноса урока 10 файл снимается целиком.

## Н0 Словарь слов

Нормативные слова — по [канону курса](../../НОРМАТИВНЫЕ-СЛОВА.md). Порядок массивов вывода — урок 1 Н0 (общее М11).

## Н1 Форма

**Время.** Полей времени у оставшихся строк нет; `domain/holder` — [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1 «Время» (стадия B; урок 8).

**Данные** ([каталог](../../Platform/common/data/catalog.tsv)):
- владеет: `domain/backup`, `domain/backup-taken`, `domain/backup-refused`;
- читает: `domain/member-list`.

Строки владеет агент хранителя (до переноса урока 9); читатель `domain/member-list` — консоль кластера (`/api/backup` Н1.9; до переноса урока 10).

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

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.5 (стадия B; урок 8). Остаётся здесь строка `member` ниже (агент хранителя — урок 9).

```yaml
member:          агент: sha256 текста = pointer.sha256, функция record-подпись документа (Н3 «проверить резервную копию»),
                 term ≥ своей резервной копии → объект domain/backup = doc, затем строка domain/backup-taken {term, rev,
                 sha256}; иначе строка domain/backup-refused {why, term, rev}; резервную копию у члена не выбрасывает никто —
                 последний запасной путь
```

### Н1.6 Смещённый держатель

Перенесено в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.6 (`yields`, `switch`, `start`, `refusal`, `forget`, `stranded`, `apply`; стадия B; урок 8). Сторона
агента точки смены — Н3 «следовать» 1а (урок 9).

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

```
1. ответы: GET /api/held каждой консоли CLUSTERS (срок 3 с; не ответила — пропуск), запись из 409 deposed прошлого отчёта
   и carry.holder прошлого ответа (P/08.3 Н1.5) — наравне: каждая проходит шаги 2–4
1а. keys ответов /api/held — функцией keys урока 2 Н3 по закреплённому корню в набор следования — память агента, с
   начала — строка domain/keys своего хранилища (перенос без stolen меняет выпускающий: новый набор приходит так, раньше
   ответа нового держателя); набор ответа берётся, только если запись срока того же ответа проходит record этим набором и
   её срок не меньше своей записи (SET_GUARD); строку domain/keys агент пишет из набора следования, когда условие Н1.6
   switch этим набором ложно (у кластера держателя — с точки смены; добавлено моделью Quint М11, G1, G7)
2. каждая запись → record по набору следования; не ok — не следовать, журнал domain.follow.refused {cluster, reason}
3. лучшая — наибольший term; тот же term у двух держателей — никуда, журнал «<a> and <b> both claim term T: followed by
   nobody»; тот же term и держатель с другим url — бо́льший at
4. своя запись — только запись срока Н1.1 (документ резервной копии или грант в held — как своей записи нет; сверка
   М11, H10) (если проходит record по набору следования): term больше лучшей — держать (larger); тот же term и держатель, а её at не меньше —
   держать (holding); тот же term, другой держатель — записать лучшую (два держателя одного срока считаются только среди
   ответов, шаг 3); иначе — записать лучшую domain/holder (CAS); ответов с проверенной записью нет — держать (none)
5. куда носить отчёт: в DOMAIN_URL, пока лучшая запись того же срока, что запись держателя, ответившего на этой двери
   (carry.holder); запись большего срока или 409 deposed этой двери — в url лучшей записи; за ретранслятором (урок 4) —
   к ретранслятору, как прежде
```

Функция `follow` — шаги 2–4 на входе Н5.

### ask-sig — подпись просьбы

Сообщения `backup` и `prepare`, форма `X-W2C-Time`, `X-W2C-Signature` и порядок проверки (`missing`, `bad_time`, `skew`,
`bad_signature`) — [договор подписи просьбы](../../Platform/common/contracts/ask-sig.md) (владелец [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md); перенесено туда без изменения; разбор ревью стадии A 8–10, № 13 /
решение 2). Векторы — [`common/vectors/ask-sig`](../../Platform/common/vectors/ask-sig/README.md).

### проверить резервную копию (агент хранителя)

```
1. sha256 текста doc ≠ pointer.sha256                                → refused «not the copy the pointer names»
2. record по своему набору (документ резервной копии) не ok                    → refused со словом
3. (term, rev) документа ≠ pointer или term < term своей резервной копии → refused «older than the copy kept here»
4. записать объект domain/backup, затем строку domain/backup-taken
```

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
стенд урока 3 с подписантом и на `m1` — сц. 01, 11; команда `follow` на входах `inputs/` — сц. 06.
Сц. 02–04, 08–10, 12 — приёмка [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) ([`Platform/08-domain/acceptance/8/`](../../Platform/08-domain/acceptance/8/README.md);
стадия B; урок 8). Сц. 05, 07 сняты: те же случаи — [`common/vectors/record`](../../Platform/common/vectors/record/README.md),
[`common/vectors/ask-sig`](../../Platform/common/vectors/ask-sig/README.md); формы команд `record`, `ask-sig` и их коды выхода —
[P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н5 (стадия B; урок 8).

```yaml
follow:    вход {keys, held: {doc} | null, answers: {<кластер>: {doc} | null}};
           вывод {result: follow, term, holder, url} | {result: stay, reason: holding | larger | none | two_holders,
           term?} и refused: {<кластер>: <слово record>}; term у stay — срок своей записи, если она прошла record, иначе
           поля нет — при любой причине, и у two_holders: спорный срок term не подменяет
exit:      0 — вычислено; 2 — вход не по форме; коды выхода — по принципу «Стенда домена» общего README приёмки («Коды выхода команд-векторов»: 2 — форма доверенного входа, 0 со словом — документ другого кластера; решение «Архитектора» по сверке М11, H14):
           keys у follow — доверенный документ набора урока 2 Н1.2 закрытой формы: поля нет (revoked_issuing,
           sig, domain), issuing не список, keys null — 2; подпись набора проверена при записи (урок 2 Н3 keys), функция её
           не проверяет — испорченный sig не отказ;
           у follow нет held или answers, answers не объект, лишнее поле — 2; held не {doc} (строка, массив) — своя запись не
           прошла record: 0, stay без term или follow; answers.<к> не {doc} и не null — 0, refused.<к>: not_a_record;
           answers: {}, held: {} — 0; ключ answers не имя кластера — посчитан как ответ
```

| № | Сценарий | Нормы |
|---|---|---|
| 01 | стенд: `/api/held` у членов, хранители `m1`, `m2`, пара резервной копии в `/api/held` и `view.term`; `/api/backup` без подписи — 401 | Н1.3–Н1.5, Н1.9 |
| 06 | `follow`: больший срок, меньший, равный, два держателя, тот же держатель с новым `url`, поддельная запись, ответов нет; своя `held` — документ резервной копии или грант — не своя запись (сверка М11, H10) | Н3 следовать |
| 11 | стенд: отзыв после последней резервной копии после переноса не оживает — 401 (модель Quint М11, RV; урок 3 Н1.6) | Н1.5 state, Н1.8; урок 3 Н1.6 |

---

## Решает реализация

1. **команда `follow`** — шаблон с `{input}` (`record`, `ask-sig` — [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) «Решает реализация» п. 1; их сц. 05, 07 сняты переносом урока 8);
2. и 3. перенесены в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) «Решает реализация» пп. 2, 3 (стадия B; урок 8).

---

## Чеклист готовности

- Пункт М11/10-01 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-01 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-02 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-02 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-03 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-03 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- [ ] **М11/10-04** `/api/held` Н1.4 — сц. 01; сц. 02 приёмки P/08.8; негодный Bearer — тоже 200 — чтением (X13)
- Пункт М11/10-05 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-04 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-06 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-05 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-07 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-06 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/10-08 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-07 (стадия B; [id-map](../../Platform/common/id-map.tsv)); дверь `POST /domain/move` у консоли кластера цели — P/06.7-17, урок 10.
- [ ] **М11/10-09** следование Н3 — сц. 06; сц. 02, 04, 09 приёмки P/08.8; набор следования и SET_GUARD (G1, G7) — сц. 09 приёмки P/08.8, чтением (вход вектора follow наборов ответов не несёт)
- Пункт М11/10-10 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-08 (стадия B; [id-map](../../Platform/common/id-map.tsv)); дверь `GET /api/backup` Н1.9 — P/06.7-16, урок 10 (норма здесь до его переноса).
- Пункт М11/10-11 перенесён в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) как P/08.8-09 (стадия B; [id-map](../../Platform/common/id-map.tsv)); сторона агента — урок 9.

## Соответствие прежним урокам

Нормирует то, что рассказывали шаги 1–7 `М12A_Domain/14-a-domain-holder-on-one-node.md`: срок, что держит только
держатель (резервная копия), перенос, следование за большим сроком, возвращение старого держателя, брошенное, плановая передача.
Шаг 9 (корень вне держателя) — урок 2; шаги 8 и 10 (камера-держатель, два процесса держателя) — [урок 12](12-small-members-and-one-node.norms.md) (лекция, Н1.7, Н1.8). ADR-0066 и его
дополнения, ADR-0075 уточнение 2, решение по `2026-10-15-first-holder-claim-diff`. Исторические исходники сохранены в Git. Вступление Н1, Н1.1–Н1.3, Н1.5
без `member`, Н1.6–Н1.8, строки Н2 и Н4 процесса, «Гонки» Н3, сц. 02–04, 08–10, 12, пп. 2, 3 «Решает реализация» и
пункты М11/10-01…03, -05…08, -10, -11 перенесены в [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) (стадия B, урок 8).
