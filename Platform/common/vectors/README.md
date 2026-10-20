# Векторы платформы (ADR-0083)

Пакет алгоритмов, общих для микромодулей: вход → ожидаемый выход. Каждый микромодуль реализует алгоритм сам и проходит
векторы. Байты пишет «Спецификация»; соответствие продукта — его приёмкой по этим таблицам (ADR-0080 доп. 16, ADR-0083;
«Паритет» снят). Владелец — урок, который вводит алгоритм первым (записка модуля, «Векторы»).

На стадии A таблицы паритета лежат на прежнем месте, `Source/tests/testdata/`: их читает и продукт (`sync-course.sh`).
Они переезжают в каталог урока-владельца, `NN-<процесс>/vectors/<алгоритм>/`, вместе с уроком на стадии B. Тогда же продукт один раз переключает пути.
Новые векторы стадии A лежат здесь сразу.

| Вектор | Где сейчас | Владелец (стадия A) | Норма |
|---|---|---|---|
| JCS | `Source/tests/testdata/canonical_json.tsv` | М10/1 | ADR-0072, RFC 8785 |
| словарь `fault` отказов дверей | `Source/tests/testdata/fault.tsv` | М10/3 | двери М10/3, 4, 9, 10 |
| `cut_at: host` | `Source/tests/testdata/group_of.tsv` | P/04 | P/04 Н1.3 `group_by` |
| `rid` | `Source/tests/testdata/rid.tsv` | М10/8 | М10/8 Н1.5 |
| сериализация тела просьбы | `Source/tests/testdata/requests_body.tsv` | М10/8 | М10/8 Н1.5, ADR-0072 |
| digest просьбы | [`06-console/vectors/request-digest/`](../../06-console/vectors/request-digest/) | М10/8 | М10/8 Н1.5 `digest` |
| секреты в адресе | `Source/tests/testdata/secret_in.tsv` | М10/7 | М10/7 Н1.1а |
| маска лога | `Source/tests/testdata/log_mask.tsv` | М10/7 | М10/7 Н1.4 |
| секретные строки платформы | `Source/tests/testdata/platform_lists.tsv` | М10/7 | P/02.5 Н1.3, P/02.5 Н1.4 |
| корпус спеки | [`02-installer/acceptance/1/`](../../02-installer/acceptance/1/) (`cases/`, `verdicts.tsv`, `classes.tsv`, `diagnostics.tsv`); прежние `spec_verdicts.tsv` и `spec_verdicts/` читает замороженный свидетель, не вектор | P/02.1 | P/02.1 Н1, Н4, Н5 |
| оценщик прав (буквальные образцы, префикс, отрицание) | [`01-store/vectors/rights-evaluator/`](../../01-store/vectors/rights-evaluator/) | P/01.2 | P/01.2 Н1.2 `pattern`, Н1.3 |
| копия хранилища | [`01-store/acceptance/3/inputs/`](../../01-store/acceptance/3/inputs/) | P/01.3 | P/01.3 Н1.3 `copy` |
| вывод прав из спеки (по смыслу) | [`02-installer/acceptance/5/variants/`](../../02-installer/acceptance/5/variants/) | P/02.5 | P/02.5 Н1.4, Н3 |
| текстовые формы значений (`values_by_type`) | векторов нет — шаги приёмки М10/03; пакет — с переносом урока 6 | М10/3 | М10/3 Н1.2 |
| id события | векторов нет — норма формы; кандидат пакета — после урока 5 | P/05 | [договор журнала событий](../contracts/event-journal.md) `id` |
| разбор адреса | частью — `secret_in.tsv`, `group_of.tsv`; отдельного пакета нет | М10/7 | М10/7 Н1.1а, P/02.1 Н1.2а `schemes` |
| конверт `enc:v2`, путь AAD, открытие, файл кольца | [`sealing/`](sealing/README.md) | common | [договор запечатывания](../contracts/sealing.md) |
| «принять консолью» | векторов нет — шаги приёмки М11/08 | М11/8 | М11/8 Н3 |
| `view`, `keys`, `token`, `seal`, `accept`, `assemble`, `issue`, `peer`, `may`, `record`, `follow`, `ask-sig`, `resolve`, `alarms` | входы приёмки `Source/tests/testdata/acceptance/М11_Domain/NN/inputs/` | уроки М11 | Н3 уроков М11 |
| нехватка набора меток и заказ по серверам (`в пути`, `per`, кандидаты, раздача) | [`04-controller/vectors/order/`](../../04-controller/vectors/order/) | P/04 | P/04 Н3 «нехватка(), заказать()»; ADR-0084 доп. (1)–(3) |
| жертва сокращения | [`04-controller/vectors/shrink-victim/`](../../04-controller/vectors/shrink-victim/) | P/04 | P/04 Н3 «сократить()», Р4, Р22 |
| скрипт воркеров по заказу (что запустить, что остановить) | [`02-installer/vectors/workers-script/`](../../02-installer/vectors/workers-script/) | М10/11 | P/02.4 Н1.5 rules 2–4 |
| порядок наборов меток над общей ёмкостью | [`04-controller/vectors/order/`](../../04-controller/vectors/order/) — случаи `two-sets-*` (набор берёт до своей потребности, остаток следующему) | P/04 | P/04 Н3 «порядок наборов» |
| снятие заказа по сроку, поздний старт, сокращение по выдержке, пробный процесс при `distinct` | шагом приёмки — [P/04](../../04-controller/acceptance/README.md) сц. 14–17 | P/04 | P/04 Н3; ADR-0084 |
| `YIELD_SAME_TERM`, `SET_GUARD` (набор следования) | шагом приёмки — М11/10 сц. 09; вход `follow` наборов ответов не несёт | М11/10 | М11/10 Н1.6 `yields`, Н3 «следовать» 1а |
| `put_at` по индексу до подтверждения очереди, CAS своей строки очереди (G6, T6) | чтением — стенд не останавливает процесс между шагами | М11/12 | М11/12 Н1.7, Н3 «очередь» |

Векторы М11 — входы команд стенда своих уроков. Общим пакетом они станут при переносе уроков 8–10. Строки «векторов нет»
— алгоритмы записки модуля, у которых пока только шаги приёмки (ревью стадии A, Gemini 4.5).
