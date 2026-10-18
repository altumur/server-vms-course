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
| `cut_at: host` | `Source/tests/testdata/group_of.tsv` | М10/4 | М10/4 Н1.3 `group_by` |
| `rid` | `Source/tests/testdata/rid.tsv` | М10/8 | М10/8 Н1.5 |
| сериализация тела просьбы | `Source/tests/testdata/requests_body.tsv` | М10/8 | М10/8 Н1.5, ADR-0072 |
| digest просьбы | [`06-console/vectors/request-digest/`](../../06-console/vectors/request-digest/) | М10/8 | М10/8 Н1.5 `digest` |
| секреты в адресе | `Source/tests/testdata/secret_in.tsv` | М10/7 | М10/7 Н1.1а |
| маска лога | `Source/tests/testdata/log_mask.tsv` | М10/7 | М10/7 Н1.4 |
| секретные строки платформы | `Source/tests/testdata/platform_lists.tsv` | М10/7 | М10/7 Н1.3, М10/6 Н1.4 |
| корпус спеки | `Source/tests/testdata/spec_verdicts.tsv` | М10/2 | М10/2 Н1, Н4 |
| копия хранилища | `Source/tests/testdata/acceptance/М10_Platform/11/inputs/` | М10/11 | М10/11 Н1.3 `copy` |
| `view`, `keys`, `token`, `seal`, `accept`, `assemble`, `issue`, `peer`, `may`, `record`, `follow`, `ask-sig`, `resolve`, `alarms` | входы приёмки `Source/tests/testdata/acceptance/М11_Domain/NN/inputs/` | уроки М11 | Н3 уроков М11 |

Векторы М11 — входы команд стенда своих уроков. Общим пакетом они станут при переносе уроков 8–10.
