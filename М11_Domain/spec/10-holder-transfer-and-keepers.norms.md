# М11/10 — Передача держателя, копия и восстановление, хранители: нормы

Канон урока. [Лекция](../10-holder-transfer-and-keepers.md), [HTTP-контракт](10-holder-transfer-and-keepers.api.openapi.yaml),
[инструкция](10-holder-transfer-and-keepers.README.md), [приёмка](../../Source/tests/testdata/acceptance/М11_Domain/10/README.md).

## Н0 Словарь слов

Нормативные слова — по [общему канону Н0](../../М10_Platform/spec/01-storage.norms.md#н0-словарь-слов).

## Н1 Форма

Общее уроков 1–9 Н1 действует. Держатель держит **срок** — номер, который растёт только переносом или передачей; аренды,
продления и автоматической смены держателя нет. Голосовать нечем: ни один raft не охватывает кластеры. Держатель пишет
только своё хранилище; члены узнают нового держателя сами, по записи, которую проверяют своим набором (ADR-0066, решение
«Архитектора» по вопросам М11/10).

### Н1.1 Запись срока `domain/holder`

```yaml
domain/holder:   {doc: <текст JCS документа>}       # у держателя — пишет процесс domain (claim); у члена — агент (Н3 «следовать»)
  doc:           {domain, term, holder, url, ca?, at, restored_from?, issuer, kid, sig}   # закрытый набор
    domain:      имя домена (урок 2 Н1.1)
    term:        целое ≥ 1
    holder:      имя члена-держателя
    url:         адрес двери процесса domain держателя — SIGNER_URL окружения этого процесса, без него
                 http://localhost:8445 (стенд одной машины) — туда агенты носят отчёты (урок 3); у
                 держателя из нескольких узлов — адрес, который доходит до любого узла кластера, а не одного сервера
                 (очередь процесса domain — урок 12 Н1.7; добавлено М11/12)
    ca?:         [<отпечаток>…], 1–2 — центр держателя (урок 8 Н1.6; ADR-0075 уточнение 2)
    at:          стенные секунды подписи
    restored_from?: {term, rev} — копия, из которой восстановлен этот срок (Н1.5); срок 1 — без поля
    issuer:      hex открытого ключа выпускающего (урок 2 Н1.3 issuing_key_secret)
    kid:         serial выпускающего — первые 16 знаков hex issuer
    sig:         base64url без «=» подписи Ed25519 выпускающего над UTF-8(JCS(doc без kid и sig))
claim:           процесс domain после установки (срок 1), переноса и приёма передачи пишет запись своего срока; запись,
                 равная лежащей, не пишется; затем вносит себя в список членов (урок 3 Н3 «держатель в списке»)
check:           функция record (Н3) по набору этого кластера
```

### Н1.2 Список членов при смене держателя

```yaml
holder:          Entry {how: "holder", since, key} — держатель; форма одна, урока 3 Н1.1 (без by); claim переписывает свою
                 Entry на эту форму, если в списке из копии она иная (урок 3 Н3 «держатель в списке» шаг 1)
former:          Entry {how: "held the domain until term <N>", since, key} — прежний держатель, N — срок, на котором он
                 держал; ключ — holder_member_key копии, из которой восстановлен срок (Н1.5); стоит, пока его не удалил
                 администратор (урок 3 DELETE); при stolen — нет: ключ прежнего — в revoked_members набора (урок 2)
```

### Н1.3 Вид держателя: поле `term`

```yaml
domain/view.term:  {term, holder, url, backup, backup_holders, copies, frozen_for?, stranded?}   # урок 1 Н1.4, добавлено М11/10
  backup:          {term, rev} последней копии | null
  backup_holders:  [<член>…] — выбранные хранители по возрастанию (Н1.5)
  copies:          {<член>: {term, rev} | {garbled: <почему>}} — строка domain/backup-taken из копии каждого члена (урок 3);
                   не хранит — нет ключа
  frozen_for?:     имя цели идущей передачи (Н1.7)
  stranded?:       число элементов domain/stranded этого кластера (Н1.6), если он смещён
```

### Н1.4 `GET /api/held` у консоли кластера

```yaml
answer:     200 {cluster, holder, term, keys, backup}       # все ключи всегда
  cluster:  CLUSTER этой консоли
  holder:   документ domain/holder этого хранилища как объект (Н1.1) | null
  term:     его term | null
  keys:     документ domain/keys этого хранилища как объект (урок 2 Н1.2) | null
  backup:   {term, rev} строки domain/backup-taken этого хранилища | null — какая копия здесь; содержимого нет никогда
refusal:    хранилище не ответило — 503 {error: "unavailable", detail: "the store did not answer"}
open:       без токена (М10/9 Н1.3 open_routes): запись и набор доказывают себя сами
```

### Н1.5 Копия и хранители

```yaml
document:        объект держателя domain/backups/rev-<rev> (М10/8 Н1.1) — JCS {term, rev, holder, at, members, state,
                 objects, backup_key_rev, holder_member_key?, issuer, kid, sig}; подпись — как Н1.1
  members:       имена списка членов
  state:         {<ключ строки>: {<элемент>: <значение>}} — строки, что домен решил и чего нет ни у кого больше:
                 domain/members, domain/topology, domain/placement, domain/placement/*, domain/pending/*,
                 domain/outcomes/*, domain/grants/*, domain/users/*, domain/break-glass/*, domain/disabled,
                 domain/book-seal, domain/revoked (иначе перенос оживил бы отозванные токены), domain/shared (указатель
                 общего документа, урок 11 Н1.2), строки kept и переносимых книг спек каталога (урок 5 Н1.6: их пишет
                 воркер на домене, из строк членов они не собираются)
  objects:       {<ключ объекта>: <JSON>} — текущий общий документ domain/shared-docs/rev-<rev> (урок 11 Н1.2) и история тревог
                 domain/alarm-history/<член> каждого члена (урок 11 Н1.9; добавлено М11/11)
  secrets:       элемент *_secret — конверт ключа копии (ниже), не кольца держателя
  not_in:        domain/signer (ключи едут только передачей, Н1.7), domain/keys (набор у каждого члена), индекс имён и
                 собираемые книги (пересобирает проход из отчётов членов), поколения отчётов, domain/stranded
backup_key:      HMAC-SHA256(ключ: root_key файла восстановления (урок 2 Н1.1), данные: "w2c domain backup secrets" 0x00
                 ‖ ASCII backup_key_rev) — 32 байта; backup_key_rev — целое ≥ 1, при установке 1
  at_holder:     domain/signer.backup_key_secret и backup_key_rev (урок 2 Н1.3, добавлено М11/10) — пишет установка
  envelope:      enc:v2 М10/7 Н1.2 этим ключом, AAD — ключ строки 0x00 «/<элемент>»
rev:             растёт только при смене содержимого — JCS state с открытыми секретами, objects, backup_key_rev,
                 holder_member_key; не чаще BACKUP_EVERY; держатель хранит последние 5 документов
first:           первая копия — в первом проходе держателя, без ожидания BACKUP_EVERY (это предел, не задержка); затем — при
                 смене содержимого, не чаще раза в BACKUP_EVERY
BACKUP_EVERY:    30         # с
BACKUP_HOLDERS:  2          # члены ok (урок 1), кроме держателя, по убыванию hex sha256(UTF-8 «<держатель>/<член>»)
keepers:         domain/keepers/<член> {term, rev, sha256} у держателя — указатель выбранного хранителя; sha256 — hex
                 sha256 JCS документа; указатель невыбранного держатель снимает
carry:           ответ держателя агенту (урок 3 Н1.5) несёт backup: {pointer: {term, rev, sha256}, doc: <текст JCS>}, когда
                 указатель члена есть и ≠ его domain/backup-taken из копии
member:          агент: sha256 текста = pointer.sha256, функция record-подпись документа (Н3 «проверить копию»), term ≥ своей
                 копии → объект domain/backup = doc, затем строка domain/backup-taken {term, rev, sha256}; иначе строка
                 domain/backup-refused {why, term, rev}; копию у члена не выбрасывает никто — последний запасной путь
in_report:       domain/backup-taken — объект отчёта члена (урок 3 Н1.2 member_objects, добавлено М11/10)
limit:           копию открывает ключ копии, выведенный из корня: украденный файл восстановления открывает и все копии
                 (рядом с пределом урока 2 «файл восстановления — всё»)
```

### Н1.6 Смещённый держатель

```yaml
yields:      процесс domain уступает, когда в его хранилище запись domain/holder большего срока проходит record по набору
             этого кластера (её пишет он сам при передаче, Н1.7 шаг 6, или приносит свой агент при переносе, Н3
             «следовать»); слову соседа и непроверенной записи — нет
switch:      у кластера держателя строки domain/keys, domain/revoked, domain/holder, своя domain/break-glass/<кластер> и
             указатель domain/shared пишет процесс domain, а агент этого кластера их не пишет — пока запись domain/holder
             своего хранилища проходит record и называет держателем этот кластер, а domain/signer не forgotten (урок 3 Н1.6
             holder_cluster). Точка смены одна — запись domain/holder большего срока, прошедшая record: при плановой
             передаче её пишет процесс прежнего держателя (Н1.7 шаг 6), при переносе — агент «следованием» (его
             единственная запись в эти строки до точки). С неё процесс уступает и этих строк больше не пишет, агент пишет
             их как у любого члена. У цели — зеркально: claim нового срока (Н1.1) — точка, с неё агент цели их не пишет
start:       после перезапуска — сначала смотрит запись своего хранилища; больший срок — стартует смещённым и не пишет claim.
             Смещён, когда запись хранилища проходит record и: ключи подписанта есть, а запись — другого держателя и срока
             больше того, что этот процесс держал (срок свой неизвестен — любого); или ключи забыты (forget) и запись чужая
refusal:     смещённый процесс на каждую правку (правки консоли домена идут через него, урок 3 Н1.8; консоль отдаёт ответ
             как пришёл) — 409 {error: "deposed", detail: "<n> held the domain at
             term N; <h> holds it at term M — edits go there", holder: <документ записи нового держателя как объект>};
             на отчёт агента — 409 {error: "deposed", holder: <тот же документ>}
forget:      domain/signer := {forgotten: "deposed by term <M>"} — ключи держателя стёрты (обещание, Н1.7 limit)
stranded:    domain/stranded {doc: JCS {term, holder, base: {term, rev}, items: [{path, key, value}]}} — один раз при смене:
             элементы state (Н1.5), которые отличаются от base — копии, из которой восстановлен новый срок, если это
             копия этого держателя (restored_from записи), иначе его последней копии; value — значение элемента как
             хранится (текст), секрет — "<secret: differs>"; сравнение — по открытым значениям;
             строка domain/pending/* засчитывается, только если правка сдвинулась (нет в base или иной at)
apply:       POST /domain/stranded/apply {path, key} у консоли домена смещённого (admin; правку исполняет процесс, урок 3
             Н1.8): элемент domain/pending/<член> — повторить правку урока 6 у нового держателя: asked правки (урок 6 Н1.4)
             как есть — метод, путь, тело, Idempotency-Key = key, Authorization вызвавшего — консоли кластера нового
             держателя CLUSTERS[holder записи] пересылкой урока 8 (с X-W2C-Via: <CLUSTER>; та пересылает своей консоли
             домена, урок 8 Н1.3); ответ — как пришёл (коды двери урока 6 и пересылки); иной элемент —
             400 {error: "redo it on the new holder", detail}; не смещён — 409; элемента нет — 404
```

### Н1.7 Плановая передача

```yaml
door:        POST /domain/handover {to} у консоли домена (admin, урок 9) → процесс domain тем же путём; срок ответа 90 с
target:      член списка с консолью в CLUSTERS, не держатель; иначе 400
order:       1. заморозка: frozen_for = to; правки людей и подписанта — 503 {error: "frozen", detail: "<h> is handing the
                domain over to <to>; edits are refused until it has — seconds, not minutes — and then go there"}; приём
                отчётов и закрытие правок отчётами идут. Заморозку держит процесс domain: правки людей идут через него
                (урок 3 Н1.8), консоль домена отдаёт его 503 как пришёл
             2. копия с force: указатели хранителей и to
             3. ждать отчёт to с этой парой в domain/backup-taken — не дольше HANDOVER_WAIT; нет — снять заморозку,
                409 {error: "called off", detail: "<to> did not take backup rev R; the handover is called off and <h> is
                still the holder"}, журнал domain.handover.called_off
             4. POST <консоль to>/api/prepare — заголовки X-W2C-Time, X-W2C-Signature: подпись ключом токенов над
                prepare|<to>|<время> (Н3 ask-sig); 10 с; ответ {cluster, seal} — X25519 цели (hex); подготовленный ключ —
                domain/signer-pending цели (урок 2 Н1.3), служит один раз
             5. POST <консоль to>/api/take {grant, keys_sealed}; 90 с:
                grant — {doc: JCS {grant: "handover", domain, to, from, term, rev, at, issuer, kid, sig}} — подпись Н1.1;
                keys_sealed — конверт x25519:v1 (урок 2 Н1.5) к seal с AAD «take|<to>» текста JSON {token_key_secret,
                issuing_key_secret, kid, serial, backup_key_secret, backup_key_rev}
             6. ответ цели — её запись срока; держатель проверяет её record, записывает в domain/holder своего хранилища
                (точка смены, Н1.6 switch) и уступает (Н1.6); журнал domain.handover
                {to, term, rev, by}
take:        цель по порядку: подписант держит домен — 409; тела нет по форме — 400; ничего не подготовлено — 409
             «nothing is prepared on <me>: the holder asks POST /api/prepare first»; ключи не открываются — 403; grant не
             проходит record-подпись по набору цели или называет не её — 403; её domain/backup-taken ≠ {term, rev}
             гранта — 409 «<me> did not take backup rev R of term T: the handover restores from nothing older»;
             затем — перенос Н1.8 шаги 5–8 из этой копии с этими ключами: соседей цель не спрашивает, новый срок =
             1 + max(term гранта, term своей записи); журнал domain.taken
HANDOVER_WAIT: 30         # с = 6 × REPORT_EVERY
limit:       передача копирует ключи подписанта на цель; что прежний их забыл (forget) — обещание, не доказательство. Если
             прежнему держателю нельзя доверять (кража, утечка коробки), путь один — аварийный перенос со stolen (Н1.8): он
             меняет выпускающий ключ, ключ токенов и ключ приёма книг (урок 2 «после кражи»)
```

### Н1.8 Аварийный перенос

```yaml
door:        POST /domain/move {recovery, stolen?, copy?, why?} у консоли кластера цели → процесс domain тем же путём
             (урок 8 Н1.9); срок 90 с; w2cctl domain move <дверь> <файл> [stolen] [copy=<term>.<rev> why=<слова>];
             личность — по режиму консоли (М10/9 Н1.3 identity) и грант admin кластера-цели (урок 8 Н1.9 шаг 3); в день
             потери домена его дают копия грантов (срок — GRANT_LIFETIME, урок 9 Н1.3) или аварийный вход (урок 9 Н1.6);
             файл восстановления доказывает домен, а не человека
  recovery:  текст файла восстановления урока 2 Н1.1 {domain, root_key, root_pub}
  copy:      {term, rev} — восстановить ровно эту копию; без why — 400
order:       1. тело не по форме — 400 {error: "refused", detail: "a move is {recovery: <the recovery file, as its text>,
                stolen?: true | false, copy?: {term, rev} with why: <words>} — a planned handover is the holder's (POST
                /domain/handover)"}
             2. перенос уже идёт — 503 «a move is under way here already: seconds, not minutes»
             3. этот кластер держит домен — 409 «<c> holds the domain at term N: there is nothing to move here»
             4. файл не читается или root_pub не от root_key, или не root набора этого кластера — 403 «the recovery file is
                not this domain's»
             5. соседи — консоли CLUSTERS: GET /api/held каждого; копия — GET /api/backup с подписью члена этого кластера
                (Н3 ask-sig); не ответил — пропущен; ответил без копии — ignored
             6. выбор копии: copy — ровно она у любого соседа (и своя), иначе 409 «nothing was restored: no neighbour gave
                the copy named, term T rev R (…)»; без copy — наибольшая (term, rev) из проверенных, а нет ни одной (ни
                сосед, ни своё хранилище копии не дали) — без копии: state не восстанавливается, список членов — копия
                domain/member-list этого кластера, он — holder, ответ 200 с restored_from: null; сосед объявил в
                /api/held копию новее, а не отдал (401, 403, 503) — 409 «nothing was restored: the newest copy this move
                could read is …, and <n> keeps term T rev R and did not give it (<why>) — restoring it would roll the
                domain back. Make the newer copy readable here, or name the copy to restore (copy: {term, rev}) and say
                why»
             7. восстановить state: секреты — ключом копии из файла, затем кольцом этого кластера; ключи — из файла:
                stolen — шаги урока 2 «смена после кражи» (новые ключ токенов, выпускающий, ключ приёма книг, набор);
                без stolen — новые ключ токенов и выпускающий, набор с аварийным rev (урок 2 Н1.2 emergency) с ними в keys/issuing, прежние ключи
                токенов — until now + OLD_KEYS, прежний выпускающий — в revoked_issuing
             8. новый срок = 1 + max(term записей и копий из ответов соседей и своей); claim с restored_from; прежний —
                Н1.2; общий документ — из первой копии, чья сумма совпала (урок 11)
answer:      200 {term, holder, restored_from: {term, rev} | null, ignored: [<член>…], sentence}
journal:     domain.moved {term, restored_from, stolen, copy, why, by} — только при copy или stolen
```

### Н1.9 `GET /api/backup` у консоли кластера

```yaml
ask:        заголовки X-W2C-Member, X-W2C-Time, X-W2C-Signature (Н3 ask-sig, ask = backup)
order:      нет заголовков — 401 «the backup a cluster keeps is the domain's state: a member signs its ask (X-W2C-Member,
            X-W2C-Time, X-W2C-Signature)»; список членов не читается — 503; член не в domain/member-list этого кластера или
            без ключа — 403 «<m> is no member with a key on <c>'s list of members»; ключ отозван (revoked_keys записи,
            revoked_members набора) — 403 «<m>'s key was revoked by the domain's root»; ask-sig не ok — 401 со словом
answer:     200 {cluster, pointer: {term, rev, sha256} | null, backup: <текст документа> | null, shared: <текст общего документа, урок 11 Н1.2> | null};
            копия не читается — 503 «the copy <c> keeps did not read (…): not "none" — ask again»
```

---

## Н2 Двери

HTTP-контракт: [10-holder-transfer-and-keepers.api.openapi.yaml](10-holder-transfer-and-keepers.api.openapi.yaml). Тело отказа
— `{error, detail}`. Двери `/domain/*` консоли домена — строки таблицы пересылки урока 8 (добавлено М11/10).

| Дверь | Кто | Успех | Отказы |
|---|---|---|---|
| GET `/api/held` | консоль кластера | Н1.4 | 503 |
| GET `/api/backup` | консоль кластера | Н1.9 | Н1.9 |
| POST `/api/prepare` | консоль кластера → процесс `domain` (урок 8 Н1.9) | `{cluster, seal}` | 400 подпись не та форма; 403 не ключом токенов текущего набора; 409 этот кластер держит домен |
| POST `/api/take` `{grant, keys_sealed}` | консоль кластера → процесс `domain` | запись срока цели `{record}` | Н1.7 take |
| POST `/domain/move` | консоль кластера → процесс `domain` | Н1.8 | Н1.8 |
| POST `/domain/handover` `{to}` | консоль домена → процесс `domain` | `{term, rev, to, stranded: []}` | 400 цель; 401/403; 409 deposed, called off; 502 консоль домена или пересылка не дождалась (урок 8 Н1.2 «Ожидание» 100 с); 503 frozen, «a handover is under way already» |
| POST `/domain/stranded/apply` `{path, key}` | консоль домена смещённого → процесс `domain` | ответ двери урока 6 нового держателя как пришёл | Н1.6 apply; коды двери урока 6 и пересылки урока 8 — как пришли |

---

## Н3 Проход

### record(keys, row) — запись срока или документ с подписью Н1.1, по порядку

```
1. row не {doc: <текст>}, doc не JSON-объект закрытого набора Н1.1 (или документа копии Н1.5, гранта Н1.7)
   с типами: term — целое ≥ 1, at — число, holder — имя члена, url — непустая строка, ca — 1–2 отпечатка,
   restored_from — {term, rev}, issuer — hex 32 байт                              → not_a_record
2. doc.domain ≠ keys.domain (у документа с domain; документ копии его не несёт —
   к домену его привязывает выпускающий, шаги 3–5)                               → another_domain
3. doc.kid ∈ keys.revoked_issuing                                                → revoked_issuer
4. doc.kid ∉ keys.issuing                                                        → unknown_issuer
5. doc.kid ≠ первые 16 hex doc.issuer, или подпись не сходится                   → bad_signature
6.                                                                               → ok {term, holder}
```

### следовать (агент члена, в каждом проходе раньше отчёта)

```
1. ответы: GET /api/held каждой консоли CLUSTERS (срок 3 с; не ответила — пропуск), запись из 409 deposed прошлого отчёта
   и carry.holder прошлого ответа (урок 3 Н1.5) — наравне: каждая проходит шаги 2–4
1а. keys ответов /api/held — функцией keys урока 2 Н3 по закреплённому корню в свой набор (перенос без stolen меняет
   выпускающий: новый набор приходит так, раньше ответа нового держателя)
2. каждая запись → record по своему набору; не ok — не следовать, журнал domain.follow.refused {cluster, reason}
3. лучшая — наибольший term; тот же term у двух держателей — никуда, журнал «<a> and <b> both claim term T: followed by
   nobody»; тот же term и держатель с другим url — бо́льший at
4. своя запись (если проходит record): term больше лучшей — держать (larger); тот же term и держатель, а её at не меньше —
   держать (holding); тот же term, другой держатель — записать лучшую (два держателя одного срока считаются только среди
   ответов, шаг 3); иначе — записать лучшую domain/holder (CAS); ответов с проверенной записью нет — держать (none)
5. куда носить отчёт: в DOMAIN_URL, пока лучшая запись того же срока, что запись держателя, ответившего на этой двери
   (carry.holder); запись большего срока или 409 deposed этой двери — в url лучшей записи; за ретранслятором (урок 4) —
   к ретранслятору, как прежде
```

Функция `follow` — шаги 2–4 на входе Н5.

### ask-sig — подпись просьбы

```
message:  backup|<кластер>|<член>|<время>   (просьба копии; ключ члена)
          prepare|<цель>|<время>            (подготовка передачи; ключ токенов current набора)
time:     X-W2C-Time — десятичная запись стенных секунд с тремя знаками после точки: (0|[1-9][0-9]*)\.[0-9]{3}
signature: X-W2C-Signature — base64url без «=» подписи Ed25519 над UTF-8(message)
check:    по порядку: заголовка нет — missing (prepare — X-W2C-Time, X-W2C-Signature; backup — ещё X-W2C-Member);
          время не по форме — bad_time; |now − время| > 300 — skew; подпись не base64url без «=», не 64 байта или не
          сходится — bad_signature; иначе ok
```

### проверить копию (агент хранителя)

```
1. sha256 текста doc ≠ pointer.sha256                                → refused «not the copy the pointer names»
2. record по своему набору (документ копии) не ok                    → refused со словом
3. (term, rev) документа ≠ pointer или term < term своей копии        → refused «older than the copy kept here»
4. записать объект domain/backup, затем строку domain/backup-taken
```

**Гонки.** Две записи одного срока у двух держателей — никто не следует (шаг 3), оператор разбирается. Передача и
отчёты: держатель в заморозке принимает отчёты; цель берёт только копию, названную грантом. Перенос в двух местах сразу — у
каждого свой новый срок; члены идут за большим, меньший уступает при первой встрече своей записи. Поздний ответ
`/api/held` старого держателя агент не берёт (`term` меньше своего).

---

## Н4 Отказы

| `error` | Код | Когда |
|---|---|---|
| `deposed` | 409 | держатель смещён: правки и отчёты; `holder` — запись нового |
| `frozen` | 503 | идёт плановая передача |
| `called off` | 409 | цель не взяла копию передачи |
| `refused` | 400, 403, 409 | формы и отказы переноса, передачи и приёма (Н1.7, Н1.8) |
| `unavailable` | 503 | хранилище не ответило (`/api/held`, `/api/backup`) |
| `redo it on the new holder` | 400 | брошенное, кроме правки члена |

Слова `record`: `not_a_record`, `another_domain`, `revoked_issuer`, `unknown_issuer`, `bad_signature`. Слова `ask-sig`:
`missing`, `bad_time`, `skew`, `bad_signature`.

---

## Н5 Приёмка

Каталог `Source/tests/testdata/acceptance/М11_Domain/10/` ([README](../../Source/tests/testdata/acceptance/М11_Domain/10/README.md)):
стенд урока 3 с подписантом и на `m1` и команды `record`, `follow`, `ask-sig` на входах `inputs/`.

```yaml
record:    вход {keys: <документ набора>, row: {doc}}; вывод {result: ok, term, holder} | {result: refused, reason}
follow:    вход {keys, held: {doc} | null, answers: {<кластер>: {doc} | null}};
           вывод {result: follow, term, holder, url} | {result: stay, reason: holding | larger | none | two_holders,
           term?} и refused: {<кластер>: <слово record>}; term у stay — срок своей записи, если она прошла record, иначе
           поля нет — при любой причине, и у two_holders: спорный срок term не подменяет
ask-sig:   вход {ask: backup | prepare, cluster, member?, pub, header: {member?, time?, signature?}, now};
           вывод {result: ok} | {result: refused, reason}
exit:      0 — вычислено; 2 — вход не по форме
```

| № | Сценарий | Нормы |
|---|---|---|
| 01 | стенд: `/api/held` у членов, хранители `m1`, `m2`, пара копии в `/api/held` и `view.term`; `/api/backup` без подписи — 401 | Н1.3–Н1.5, Н1.9 |
| 02 | стенд: аварийный перенос на `m1` по файлу — срок 2, `restored_from`; гранты восстановлены; члены следуют; вернувшийся `hold` смещён — 409 `deposed`, ключи забыты, прежний в списке | Н1.1, Н1.2, Н1.6, Н1.8 |
| 03 | стенд: перенос с `copy` без `why` — 400; копию никто не держит — 409 | Н1.8 |
| 04 | стенд: плановая передача `hold` → `m1` — срок 2 у членов, `stranded` пуст, `hold` смещён | Н1.7 |
| 05 | `record`: верная запись, чужой домен, отозванный и неизвестный выпускающий, kid ≠ issuer, подпись, не запись | Н3 record |
| 06 | `follow`: больший срок, меньший, равный, два держателя, тот же держатель с новым `url`, поддельная запись, ответов нет | Н3 следовать |
| 07 | `ask-sig`: верная просьба копии и подготовки, нет заголовка, время не по форме, сдвиг 301 с, чужая подпись | Н3 ask-sig |

---

## Решает реализация

1. **команды `record`, `follow`, `ask-sig`** — шаблоны с `{input}`;
2. **как раннер поднимает подписанта на другом кластере и переносит домен** — директивы `@start domain on`, `@stop domain`,
   `@move` словаря М11/01;
3. **хранилище документов копии** у держателя (объекты М10/8) и сколько из пяти держать сверх нормы.

---

## Чеклист готовности

- [ ] **М11/10-01** запись срока Н1.1 и `record` — сц. 05; `claim` и держатель в списке — сц. 02, 04
- [ ] **М11/10-02** прежний держатель в списке, при `stolen` — в `revoked_members` — сц. 02; `stolen` — чтением (урок 2 сц. кражи)
- [ ] **М11/10-03** `view.term` — сц. 01
- [ ] **М11/10-04** `/api/held` Н1.4 — сц. 01, 02
- [ ] **М11/10-05** копия Н1.5: состав, ключ копии, ревизия по содержимому, хранители, указатели, агент хранителя — сц. 01, 02; ключ копии и его предел — чтением
- [ ] **М11/10-06** смещённый Н1.6: уступает по проверенной записи, 409 `deposed`, забывает ключи — сц. 02, 04; брошенное и `apply` — чтением
- [ ] **М11/10-07** плановая передача Н1.7 по порядку, заморозка, отмена — сц. 04; заморозка и отмена — чтением; предел — чтением
- [ ] **М11/10-08** аварийный перенос Н1.8 по порядку, новый срок по записям и копиям, выбор копии — сц. 02, 03; «новее не прочитана» — чтением
- [ ] **М11/10-09** следование Н3 — сц. 02, 04, 06
- [ ] **М11/10-10** `ask-sig` и `/api/backup` Н1.9 — сц. 01, 07
- [ ] **М11/10-11** точка смены писателя Н1.6 `switch`: передача — запись процесса прежнего держателя, сц. 04; перенос —
  запись агента «следованием», сц. 02; агент кластера держателя до точки строк процесса не пишет — чтением

## Соответствие прежним урокам

Нормирует то, что рассказывали шаги 1–7 `М12A_Domain/14-a-domain-holder-on-one-node.md`: срок, что держит только
держатель (копия), перенос, следование за большим сроком, возвращение старого держателя, брошенное, плановая передача.
Шаг 9 (корень вне держателя) — урок 2; шаги 8 и 10 (камера-держатель, два процесса держателя) — [урок 12](12-small-members-and-one-node.norms.md) (лекция, Н1.7, Н1.8). ADR-0066 и его
дополнения, ADR-0075 уточнение 2, решение по `2026-10-15-first-holder-claim-diff`. Исторические исходники сохранены в Git.
