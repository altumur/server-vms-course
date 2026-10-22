# Векторы платформы (ADR-0083)

Пакет алгоритмов, общих для микромодулей: вход → ожидаемый выход. Каждый микромодуль реализует алгоритм сам и проходит
векторы. Байты пишет «Спецификация»; соответствие продукта — его приёмкой по этим таблицам (ADR-0080 доп. 16, ADR-0083;
«Паритет» снят). Владелец — урок, который вводит алгоритм первым (записка модуля, «Векторы»).

Таблицы паритета стадии A лежали в `Source/tests/testdata/`; на стадии B они переехали в каталог урока-владельца,
`NN-<процесс>/vectors/<алгоритм>/`, вместе с уроком (урок 6 — `fault`, `group_of`, `rid`, `requests_body`, `secret_in`,
`log_mask`, `platform_lists`; с ними `canonical_json` — в P/01; прежние файлы сняты), и продукт один раз переключил пути. Общие векторы лежат здесь.

| Вектор | Где сейчас | Владелец (стадия A) | Норма |
|---|---|---|---|
| JCS | [`01-store/vectors/jcs/`](../../01-store/vectors/jcs/) | P/01 | ADR-0072, RFC 8785 |
| словарь `fault` отказов дверей | [`06-console/vectors/fault/`](../../06-console/vectors/fault/) | P/06.1 | двери P/06 (главы 6.1, 6.5, 6.6) |
| `cut_at: host` | [`04-controller/vectors/group-of/`](../../04-controller/vectors/group-of/) | P/04 | P/04 Н1.3 `group_by` |
| `rid` | [`06-console/vectors/rid/`](../../06-console/vectors/rid/) | P/06.4 | P/06.4 Н1.5 |
| сериализация тела просьбы | [`06-console/vectors/requests-body/`](../../06-console/vectors/requests-body/) | P/06.4 | P/06.4 Н1.5, ADR-0072 |
| digest просьбы | [`06-console/vectors/request-digest/`](../../06-console/vectors/request-digest/) | P/06.4 | P/06.4 Н1.5 `digest` |
| секреты в адресе | [`06-console/vectors/secret-in/`](../../06-console/vectors/secret-in/) | P/06.2 | P/06.2 Н1.1а |
| маска лога | [`06-console/vectors/log-mask/`](../../06-console/vectors/log-mask/) | P/06.2 | P/06.2 Н1.4 |
| секретные строки платформы | [`02-installer/vectors/platform-lists/`](../../02-installer/vectors/platform-lists/) | P/02.5 | P/02.5 Н1.3, P/02.5 Н1.4 |
| корпус манифеста | [`02-installer/acceptance/1/`](../../02-installer/acceptance/1/) (`cases/`, `verdicts.tsv`, `classes.tsv`, `diagnostics.tsv`); прежние `spec_verdicts.tsv` и `spec_verdicts/` читает замороженный свидетель, не вектор | P/02.1 | P/02.1 Н1, Н4, Н5 |
| оценщик прав (буквальные образцы, префикс, отрицание) | [`01-store/vectors/rights-evaluator/`](../../01-store/vectors/rights-evaluator/) | P/01.2 | P/01.2 Н1.2 `pattern`, Н1.3 |
| копия хранилища | [`01-store/acceptance/3/inputs/`](../../01-store/acceptance/3/inputs/) | P/01.3 | P/01.3 Н1.3 `copy` |
| вывод прав из манифеста (по смыслу) | [`02-installer/acceptance/5/variants/`](../../02-installer/acceptance/5/variants/) | P/02.5 | P/02.5 Н1.4, Н3 |
| текстовые формы значений (`values_by_type`) | [`06-console/vectors/values-by-type/`](../../06-console/vectors/values-by-type/) | P/06.1 | P/06.1 Н1.2 |
| id события | векторов нет — норма формы; кандидат пакета — после урока 5 | P/05 | [договор журнала событий](../contracts/event-journal.md) `id` |
| бакет журнала: порванный хвост и неверная строка; имена `%h<sha256>` и `.name` | [`journal/`](journal/README.md) | common (договор журнала событий) | [договор журнала событий](../contracts/event-journal.md) `bucket` `torn`, «Имена файлов в общих деревьях»; догадки стадии C EJ-G03, EJ-G04 |
| разбор адреса | частью — пакеты `secret-in`, `group-of`; отдельного пакета нет | P/06.2 | P/06.2 Н1.1а, P/02.1 Н1.2а `schemes` |
| конверт `enc:v2`, путь AAD, открытие, файл кольца | [`sealing/`](sealing/README.md) | common | [договор запечатывания](../contracts/sealing.md) |
| свежесть: возраст наблюдаемой версии → свеж (`≤ LOST_AFTER`) | [`fresh-age/`](fresh-age/README.md) | common (договор наблюдения) | [договор наблюдения](../contracts/observation.md) «Свежесть»; P/04 Н3, главы 6.1, 6.4, 6.5, 6.6 (разбор ревью стадии B 6–7, № 20) |
| SaidID: имя просьбы в `fetched` и его чтение | [`said-id/`](said-id/README.md) | P/03.4 (участник 6.4) | [P/03.4](../../03-worker/spec/03.4-worker.norms.md) Н1.1 `said_id` |
| токен двери `door1`: выпуск (JCS, Ed25519) и проверка у держателя по `door/keys` | [`door-token/`](door-token/README.md) | P/06.5 (участник 3.4) | [договор токена двери](../contracts/door-token.md); P/06.5-05, P/03.4-08 |
| «принять консолью» | векторов нет — шаги приёмки [главы 6.7](../../06-console/acceptance/7/README.md) (сц. 01, 02) | P/06 | [договор пересылки](../contracts/forwarding.md) «Принять консолью» |
| конверты домена `x25519:v1` и `m1`: открытие и круг (`seal`, `seal-round`, `seal-member`, `seal-member-round` приёмки М11) | [`domain-envelopes/`](domain-envelopes/README.md) | common (владелец P/08, главы 8.2, 8.3) | [договор конвертов домена](../contracts/domain-envelopes.md); разбор ревью стадии A 8–10, № 12 |
| подпись агента `X-Agent-Signature`: проверка `agent-sig` (окна, байты, формы) | [`agent-sig/`](agent-sig/README.md) | common (владелец P/09, глава 9.1) | [договор подписи агента](../contracts/agent-signature.md); разбор ревью стадии A 8–10, № 13 |
| набор ключей домена: функция `keys` | [`keys/`](keys/README.md) | common (владелец P/08, глава 8.2) | [договор набора ключей домена](../contracts/keys.md); разбор ревью стадии A 8–10, № 13 |
| запись срока и подпись выпускающего: функция `record` | [`record/`](record/README.md) | common (владелец P/08, глава 8.8) | [договор записи срока](../contracts/record.md); разбор ревью стадии A 8–10, № 13 |
| подпись просьбы `X-W2C-*`: функция `ask-sig` | [`ask-sig/`](ask-sig/README.md) | common (владелец P/08, глава 8.8) | [договор подписи просьбы](../contracts/ask-sig.md); разбор ревью стадии A 8–10, № 13 |
| приём отчёта: функция «принять» (`accept`), дороги | [`accept/`](accept/README.md) | common (владелец P/08, глава 8.3) | [договор приёма отчёта](../contracts/accept.md); разбор ревью стадии A 8–10, № 13 |
| файл отзыва `revoked`: синтаксис, значение серийника, неверный файл | [`revoked/`](revoked/README.md) | common (договор сертификата роли) | [договор сертификата роли](../contracts/role-certificate.md) `revoke`; догадка стадии C S01, решение «Архитектора» 2026-10-23 |
| файл отзыва `crl.pem`: блок на центр, область серийников по издателю, подпись, даты — лог и счёт, дефекты | [`crl/`](crl/README.md) | common (договор сертификата роли) | [договор сертификата роли](../contracts/role-certificate.md) `revoke` `crl`; догадки стадии C RC-02, S03, RC-05, RC-06 |
| право по грантам: функция `may` | [`may/`](may/README.md) | common (владелец P/08, глава 8.4) | [договор права](../contracts/may.md); решение «Архитектора» 2026-10-20, ADR-0083 доп. (14) п. 1 |
| клиент о сервере другого кластера: функция `peer` | [`peer/`](peer/README.md) | common (владелец P/09) | [договор `peer`](../contracts/peer.md); решение «Архитектора» 2026-10-20, ADR-0083 доп. (14) п. 2 |
| токен домена: функция `token` | [`domain-token/`](domain-token/README.md) | common (владелец P/08, глава 8.2) | [договор токена домена](../contracts/domain-token.md); P/08.2-05, -06, -07 |
| вид домена и теневой отчёт: функция `view` | [`08-domain/vectors/view/`](../../08-domain/vectors/view/README.md) | P/08.1 | [P/08.1](../../08-domain/spec/08.1-domain.norms.md) Н1.3–Н1.6, Н3 |
| сборка книги: функция `assemble` | [`08-domain/vectors/assemble/`](../../08-domain/vectors/assemble/README.md) | P/08.5 | [P/08.5](../../08-domain/spec/08.5-domain.norms.md) Н1.3, Н3 |
| выдача токена воркера: функция `issue` | [`08-domain/vectors/issue/`](../../08-domain/vectors/issue/README.md) | P/08.7 | [P/08.7](../../08-domain/spec/08.7-domain.norms.md) Н3 |
| следование: функция `follow` | [`09-agent/vectors/follow/`](../../09-agent/vectors/follow/README.md) | P/09.1 | [P/09.1](../../09-agent/spec/09.1-agent.norms.md) Н3 «следовать» |
| значение при чтении: функция `resolve` | [`06-console/vectors/resolve/`](../../06-console/vectors/resolve/README.md) (11 строк; из М11/11 сц. 03) | P/06.7 | [P/06.7](../../06-console/spec/06.7-console.norms.md) Н1.14, Н3 `resolve` |
| список тревог: функция `alarms` | [`10-domain-console/vectors/alarms/`](../../10-domain-console/vectors/alarms/README.md) (15 строк; из М11/11 сц. 04) | P/10 | [P/10](../../10-domain-console/spec/10-domain-console.norms.md) Н1.8, Н3 `alarms` |
| нехватка набора меток и заказ по серверам (`в пути`, `per`, кандидаты, раздача) | [`04-controller/vectors/order/`](../../04-controller/vectors/order/) | P/04 | P/04 Н3 «нехватка(), заказать()»; ADR-0084 доп. (1)–(3) |
| жертва сокращения | [`04-controller/vectors/shrink-victim/`](../../04-controller/vectors/shrink-victim/) | P/04 | P/04 Н3 «сократить()», Р4, Р22 |
| разрешено ли сокращение: условие и порядок причин отказа (жертва, живые без места при ждущих, выдержка, в пути, гистерезис) | [`04-controller/vectors/shrink-allowed/`](../../04-controller/vectors/shrink-allowed/) | P/04 | P/04 Н3 «сократить (шаг 9а)», условие; Р3, Р13′, Р16′, Р16‴, Р22, Р28 (решение «Архитектора» 2026-10-20, № 12 разбора ревью стадии B 3–5) |
| скрипт воркеров по заказу (что запустить, что остановить) | [`02-installer/vectors/workers-script/`](../../02-installer/vectors/workers-script/) | P/02.4 | P/02.4 Н1.5 rules 2–4 |
| порядок наборов меток над общей ёмкостью | [`04-controller/vectors/order/`](../../04-controller/vectors/order/) — случаи `two-sets-*` (набор берёт до своей потребности, остаток следующему) | P/04 | P/04 Н3 «порядок наборов» |
| снятие заказа по сроку, номер выше want, сокращение по выдержке, пробный процесс при `distinct` | шагом приёмки — [P/04](../../04-controller/acceptance/README.md) сц. 14–17 | P/04 | P/04 Н3; ADR-0084 |
| `YIELD_SAME_TERM`, `SET_GUARD` (набор следования) | шагом приёмки — [P/08.8](../../08-domain/acceptance/8/README.md) сц. 09; вход `follow` наборов ответов не несёт | P/08.8 | [P/08.8](../../08-domain/spec/08.8-domain.norms.md) Н1.6 `yields`; [P/09.1](../../09-agent/spec/09.1-agent.norms.md) Н3 «следовать» 1а |
| `put_at` по индексу до подтверждения очереди, CAS своей строки очереди (G6, T6) | чтением — стенд не останавливает процесс между шагами | P/08.10 | [P/08.10](../../08-domain/spec/08.10-domain.norms.md) Н1.7, Н3 «очередь процесса domain» |

Векторы М11 — бывшие входы команд стенда своих уроков; все они теперь пакеты (урок 8 — пакеты `view`, `assemble`, `issue`
урока и общие пакеты выше, урок 9 — пакет `follow`, урок 10 — `resolve` главы 6.7 и `alarms` урока P/10; их сценарии и
входы в приёмке М11 сняты переносами). Строки «векторов нет»
— алгоритмы записки модуля, у которых пока только шаги приёмки (ревью стадии A, Gemini 4.5).
