# Договор права: функция `may`, слова отказа

Общий договор модуля «Платформа» (ADR-0083 доп. (13) и доп. (14): общий алгоритм нескольких процессов — договор, а не
копии в главах; решение «Архитектора» 2026-10-20, ADR-0083 доп. (14) п. 1; разбор ревью стадии A 8–10). Владелец — урок
P/08, [глава 8.4](../../08-domain/spec/08.4-domain.norms.md) (Н1.4 — указатель сюда): люди, гранты и
право по грантам. Функцию `may` исполняют:

| Кто | Где | `grants`, `as_of`, `disabled` |
|---|---|---|
| консоль кластера ([P/06.3](../../06-console/spec/06.3-console.norms.md) Н1.3 `identity` шаг 3, `need`; глава 6.7 — сессия с грантами) | [P/06.7](../../06-console/spec/06.7-console.norms.md) Н1.9 `cluster`, `session` (действующие строки — шаг 5) | копия `domain/grants` этого кластера и её `as_of`; `domain/disabled` этого хранилища |
| консоль домена ([урок P/10](../../10-domain-console/spec/10-domain-console.norms.md) Н1.5) и процесс `domain` (8.4) | [P/08.4](../../08-domain/spec/08.4-domain.norms.md) Н1.5 `domain`; Н3 «дверь людей» шаг 2, «гранты» шаг 1 | `domain/grants/domain`, `as_of` — `null` |

Шаг 5 (действующие строки) читают ещё доставка книги по гранту ([P/08.5](../../08-domain/spec/08.5-domain.norms.md)
Н1.3 `grant`) и индекс имён (P/08.5 Н1.7 `delivery`); модуль консоли считает подсказку по рангу и области
([P/07](../../07-console-module/spec/07-console-module.norms.md) Н1.5 `may`), сервер проверяет всегда.

Перенесено из М11/9 Н1.4 (вход, вывод, шаги 1–8) и Н4 (слова `may`) без изменения поведения; номера шагов прежние. У
владельца остаются: строка гранта ([P/08.4](../../08-domain/spec/08.4-domain.norms.md) Н1.3: `lines`, `line`, ранги `cap` — `view < edit < admin`, `scope`,
`until`, `GRANT_LIFETIME`, `unreadable` — значение и правило входа повторены ниже, «Функция `may`»; копия члена — [P/09.1](../../09-agent/spec/09.1-agent.norms.md) Н1.4), проверка у процесса
`domain` и что дверь отвечает на `deny` (P/08.4 Н1.5: 403 `denied`, `detail` у `stale`), аварийная учётка у держателя
(P/08.4 Н1.6); сторожевая с грантами и аварийный вход у консоли кластера — P/06.7 Н1.9, Н1.10, у консоли домена — P/10 Н1.5. Ссылка
«Н1.6» в перенесённом тексте — М11/9 Н1.6, теперь P/06.7 Н1.10 (аварийная сессия консоли); `rank` — порядок `cap`
P/08.4 Н1.3; метки — [договор азбуки меток](labels.md).

Нормативные слова — по [канону курса](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Форма

Входы функции: `grants` — копия `domain/grants` члена и `domain/grants/domain` у консоли домена и процесса `domain` — `Platform/09-agent/data/grants.form.yaml`, `Platform/09-agent/data/grants.outcomes.tsv`; `Platform/08-domain/data/grants.form.yaml`, `Platform/08-domain/data/grants.outcomes.tsv`; `disabled` — строка `domain/disabled`: `Platform/08-domain/data/disabled.form.yaml`, `Platform/08-domain/data/disabled.outcomes.tsv` (аудит раскладки, В-36, В-37; решение «Архитектора» 2026-10-25).

## Функция `may`

Из М11/9 Н1.4 «Право — функция `may`»:

```yaml
input:     {grants: <doc {lines}> | null, as_of: <число> | null, disabled: [<имя>…], user, glass, cap, unit, now}
  unit:    null — дверь без единицы; "*" — право на всё; {sub, id, labels: [<метка>…], about?: {sub, id, labels}}
  glass:   true — сессия аварийного входа (Н1.6)
output:    {result: allow} | {result: deny, reason: disabled | stale | no_grant}
```

```
1. glass                                                                → allow
2. user ∈ disabled                                                      → deny disabled
3. grants = null                                                        → deny no_grant
4. as_of ≠ null и now − as_of > GRANT_LIFETIME                          → deny stale
5. строки: subject = user, until = 0 или now < until
6. unit = null и cap = view: хоть одна строка                           → allow
7. строка с rank(cap строки) ≥ rank(cap) и область покрывает unit        → allow
   * — любую (и "*"); unit:<s>/<i> — unit с (sub, id) = (s, i) или его about с (s, i);
   labels:L — все метки L у about, если about есть, иначе у самого unit; null и "*" ни одна область, кроме *, не покрывает
8.                                                                      → deny no_grant
```

Постоянная и вход строк (из P/08.4 Н1.3 `GRANT_LIFETIME`, `unreadable` и Н5 `exit` без изменения поведения; владелец
текста — P/08.4; разбор ревью стадии B 8–10, № 4, Claude С-7):

```yaml
GRANT_LIFETIME: 86400   # с — шаг 4: копия члена старше as_of + GRANT_LIFETIME не даёт прав
lines_in:       функция получает только строки lines по форме P/08.4 Н1.3 (файлы семьи — Platform/09-agent/data/grants.form.yaml,
                grants.outcomes.tsv; C04-DEP-OBS-HEARTBEAT-01): нечитаемую строку отбрасывает вызывающий до
                вызова — пропуск с диагностикой у двери члена над копией из ответа держателя (P/08.4 Н1.3 unreadable;
                копия — P/09.1 Н1.4 member_copy, holder_copy); строка не по форме во входе функции — вход не по форме, код
                выхода 2, не пропуск (P/08.4 Н5 exit). Противоречия «пропускается» (Н1.3) и «2, не пропуск» (Н5) нет: пропуск
                — у вызывающего, код 2 — у функции
```

Какой вход не по форме (строки `grants` — доверенный вход) — README векторов [`may`](../vectors/may/README.md) «Форма входа команды `may`» (MAY-G01/G02); коды выхода команды `may` — [P/08.4](../../08-domain/spec/08.4-domain.norms.md) Н5 `exit`.

## Слова отказа

Из М11/9 Н4: слова `may`: `disabled`, `stale`, `no_grant`.

## Векторы

Пакет [`may`](../vectors/may/README.md): 25 строк — 24 — входы команды `may` приёмки М11/9 (сц. 07) без изменения значений, кроме `labels: []` у единицы
`may-24` (решение «Архитектора» 2026-10-20; README пакета);
одна строка — вход не по форме (`@exit 2`; разбор ревью стадии B 8–10, № 22); `may-25` — `subject` "" (`@exit 2`, MAY-G03). Сценарий и входы сняты переносом урока 8 — таблица единственный
источник этих случаев.

## Соответствие прежним урокам

Из М11/9 (решение «Архитектора» 2026-10-20, ADR-0083 доп. (14) п. 1; разбор ревью стадии A 8–10): Н1.4 целиком (здесь
«Функция `may`»; в М11/9 — указатель) и фраза Н4 о словах `may` (здесь «Слова отказа»). Норма М11/9-05 (`may` по порядку)
— по `note` [id-map](../id-map.tsv).
