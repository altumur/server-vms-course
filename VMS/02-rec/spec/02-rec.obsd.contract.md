# Договор движка архива `obsd` (урок V/02)

Договор части `obsd` подсистемы `rec` — протокол сокета и свойства движка, на которые опираются регистратор (главы
V/02.3, V/02.4) и дверь архива (V/02.5). Канон — этот файл; нормы главы [V/02.2](02.2-rec.norms.md) — что `rec` требует от
части (служба, доля, окружение, сроки, версия движка). Движок — ObjectStorage (дерево `2bbee4a`, 2026-10-02) с патчами
01–07 (V/02.2 Н1.4); договор описывает то, что наблюдаемо на сокете и в томе, а не устройство клиента.

## Транспорт

- Сокет unix (`SOCK_STREAM`) — сокет доли `rec.obsd` (V/02.2 Н1.2); путь — короче `sun_path` (107 байт на Linux, 103 на
  macOS), иначе демон не стартует.
- Демон создаёт сокет `0660`; пир чужого uid допускается, только если он в группе `OBSD_CLIENT_GROUP` (Linux — любая группа
  процесса, macOS — основная); иначе соединение отвергнуто.
- Второй демон на том же сокете не стартует (замок `<сокет>.lock`).

## Кадр

```
u32 len | u32 id | u16 op | u16 flags | i32 status | u32 jsonLen | json[jsonLen] | tail
```

- Все целые заголовка — little-endian; `len` — байты после себя (16 + `jsonLen` + длина `tail`).
- `id` выбирает клиент; ответ несёт `id` своего запроса; ответы могут прийти не по порядку — сверка по `id`; ответ с чужим
  `id` клиент отбрасывает.
- `flags` бит 0 — `REPLY`. `status` запроса — 0; ответа — 0 успех, иначе код (ниже) и JSON `{detail}`.
- JSON — объект UTF-8 (пустой читается как `{}`); 64-битные числа и хэндлы — числа JSON, точные беззнаковые.
- `tail` — двоичные данные операции до конца кадра.
- Предел кадра — `maxFrame` из ответа `HELLO` (умолчание 256 МиБ); больше — `FRAME_TOO_LARGE`, соединение закрыто.
- `CANCEL` (op 4) `{id}` — без ответа: ответ на этот `id` больше не нужен.

## Сессия, соединение, хэндлы

- Первый кадр каждого соединения — `HELLO` (op 1): запрос `{proto: [1, 1], client, pid, session, logLevel}`, ответ
  `{proto, server, engine, pid, maxFrame}`. `client` — имя процесса (`[A-Za-z0-9._-]`); `session` — токен сессии клиента.
- Сессия ≠ соединение: хэндлы принадлежат сессии; соединений в сессии может быть несколько, любое пользуется любым её
  хэндлом. Повторный `HELLO` с тем же токеном до истечения `OBSD_SESSION_LINGER_MS` (3000 мс) — та же сессия; позже или
  после перезапуска демона — новая пустая сессия: старые хэндлы отвечают `UNKNOWN_HANDLE` (`pid` в ответе `HELLO` — признак
  нового демона).
- `BYE` (op 2) `{}` → `{}` — после того, как закрыты все хэндлы сессии, писатели тоже. Пропало последнее соединение на
  linger без `BYE` — исчезновение: читатели и тома освобождены, писатели отсоединены (ниже «Отсрочка»).
- Хэндл — `u64`: старший байт — вид (1 том, 2 читатель, 3 писатель), остальное — счётчик демона без повторов. Не того вида —
  `WRONG_HANDLE_KIND`; неизвестный сессии — `UNKNOWN_HANDLE`. Писатель держит свой том: закрыть том раньше писателя
  безвредно.

## Операции

| op | Имя | Запрос → ответ |
|---|---|---|
| 3 | `PING` | `{}` → `{}` |
| 5 | `STATS` | `{}` → `{uptimeSec, sessions, writers: [{key, owner, state, graceLeftMs, progress}], jobs: [{op, volume, client, state, ageMs}]}` |
| 10 | `VOLUME_OPEN` | `{uri}` или `{params: {k: v}}`, `maxParallelReads?` → `{volume}`; params файла — `{schema: file, path}`, бакета — `{schema, host, port?, region, bucket, path, access_key, secret_key}`; том узнаётся по `schema://host/path`, не по учётным данным |
| 11 | `VOLUME_CLOSE` | `{volume}` → `{}` |
| 12 | `VOLUME_EXISTS` | `{volume}` → `{exists}` |
| 13 | `VOLUME_FORMAT` | `{volume, size, tunables?: {maxBlockSize, optimalReadSize, lockRefreshSec}, label, checkSpace}` → `{info}` |
| 14 | `VOLUME_RECOVER` | `{volume}` → `{result}`: 0 чист, 1 восстановлен, 2 ошибка |
| 15 | `VOLUME_SPACE` | `{volume}` → `{available, capacity, free}` |
| 16 | `VOLUME_MOUNT_RO` | `{volume}` → `{reader}` |
| 17 | `VOLUME_MOUNT_RW` | `{volume, owner}` → `{writer, reattached}` |
| 20 | `READER_CLOSE` | `{reader}` → `{}` |
| 21 | `READER_INFO` | `{reader}` → `{info: {formatVersion, uuid, createdAtUnixSec, maxVolumeSize, tunables, label}, label}` |
| 22 | `READER_STATUS` | `{reader}` → `{status: {firstBlockId, numBlocks, usedSize, availableSize, totalWritten, reindexBlockId?}}`; `usedSize`, `availableSize`, `totalWritten` — байты; `totalWritten` — счётчик движка: байты, записанные в том с его форматирования, растёт, кольцо его не уменьшает |
| 23 | `READER_STREAMS` | `{reader}` → `{streams: [name]}` |
| 24 | `READER_TIMELINE` | `{reader, stream, from, to, minGap, mode}` → `{intervals: [{start, end, size, streamId}], ready}`; `mode`: `""` — построить, `boundary` — из памяти, `quick` — только из памяти, иначе `ready: false` и чтения запущены |
| 25 | `READER_SEQUENCES` | `{reader, stream, from, to, pageHint}` → `{entries: [{streamId, tag, start, end, blockId, offset, size}]}` (`pageHint` — 1000) |
| 26 | `READER_FIND` | `{reader, stream, from, backwards}` → `{found, entry}` |
| 27 | `READ_SEQUENCE` | `{reader, entry}` → `{info, count}`, в `tail` — `count` записей SMPL |
| 30 | `WRITER_CONFIGURE` | `{writer, settings: {maxBlockSize, optimalReadSize, incomingBufferSize, blockFlushPeriodSec, sequenceFlushPeriodMs, secureSealBlocks}}` → `{}`; 0 — умолчание движка; после `reattached` уже заданные настройки — успех |
| 31 | `PUT_MEDIA` | `tail`: `writer:u64le streamLen:u16le stream[streamLen] SMPL`; ответ — статус (ниже) |
| 32 | `FINISH_MEDIA` | `tail`: `writer:u64le streamLen:u16le stream`; `EMPTY_RESULT` — открытой последовательности не было |
| 33 | `WRITER_FLUSH` | `{writer}` → `{}`: хвост на носитель, блок не закрывается |
| 34 | `WRITER_RESIZE` | `{writer, size}` → `{status}`; меньше записанного — старейшие блоки освобождаются шагами `OBSD_RESIZE_STEP_MB` (1024), запись в это время стоит |
| 35 | `WRITER_CLOSE` | `{writer}` → `{}` после сброса (до 30 с); после ответа записанное читаемо; сколько клиент ждёт ответа — V/02.4 Н1.5 «конец закрытия» |
| 36 | `WRITER_ABANDON` | `{writer}` → `{}`: отдать том без записи (ни очереди, ни статуса, ни индекса); замок снимается, только если он ещё этого писателя; следующий монтаж может потребовать восстановления |

**`PUT_MEDIA`:** `OK` — взят; `SEQUENCE_LOST` — взят, но более ранняя последовательность потеряна; `WRITER_STOPPED` — не
взят, писатель больше ничего не возьмёт; `SEQUENCE_TOO_LARGE` и прочие `SEQUENCE_*` — не взят.

**Повтор:** обрыв соединения после отправки неидемпотентного запроса (`PUT_MEDIA`, `FINISH_MEDIA`, `VOLUME_FORMAT`,
`VOLUME_MOUNT_RW`, `WRITER_CLOSE`, `WRITER_RESIZE`) не значит «не выполнен»: демон мог его выполнить, потерян только ответ;
такой запрос клиент не повторяет вслепую. Ответ с ненулевым статусом — ответ, не обрыв.

## Время и запись SMPL

- Время архива — миллисекунды с 1900-01-01 UTC: `archive_ms = r(unix_s × 1000) + 2208988800000`, где `unix_s` — число
  binary64, произведение — одно умножение binary64 (с округлением к ближайшему), `r(p)` — половина вверх: `⌊p⌋ + 1`, если
  дробная часть `p` (точно) ≥ 0,5, иначе `⌊p⌋` (не функция языка). Примеры: `1700000000.0004` → `p` = `1700000000000.4001…`
  → `3908988800000`; `1700000000.0005` → `p` = `1700000000000.5` → `3908988800001` (к ближайшему чётному дало бы `…800000`);
  `1700000000.0006` → `3908988800001`. Векторы — с семьёй данных VMS (разбор ревью V/01, вопрос 5).
- Запись SMPL — big-endian: `"SMPL" major:u32 subtype:u32 flags:u32 begin:u64 end:u64 subLen:u32 bodyLen:u32 sub body`.
  Видео — `major = 2`; `subtype` — FourCC в u32 LE (`H264`, `H265`); `sub` — `width:u32le height:u32le`.
- Флаги: `NEED_KEY_FRAME = 1<<0`, `NEED_PREVIOUS_FRAME = 1<<3`; ключевой кадр — ни одного из двух.

## Свойства движка

- **Видимость:** читатель видит только закрытые блоки, закрытые к моменту его монтирования; `WRITER_FLUSH` блок не
  закрывает. Блок закрывается: заполнен (`maxBlockSize`); прошло `blockFlushPeriodSec` после того, как законченная
  последовательность легла в очередь; писатель закрыт. Незаконченную последовательность движок режет по
  `sequenceFlushPeriodMs`.
- **Последовательность** открывается ключевым кадром: зависимый первый — `SEQUENCE_NEEDS_KEY_SAMPLE`; движок режет
  последовательности по `optimalReadSize` на ключевых кадрах; последовательность не переходит границу блока: кадр, не
  поместившийся в блок, — `SEQUENCE_TOO_LARGE`, следующие до ключевого — `SEQUENCE_NEEDS_KEY_SAMPLE` (кадры потеряны). Блок
  годен для потока, если он ≥ размер чтения + 3 МБ.
- **Поток** — имя; иных метаданных у потока нет.
- **Кольцо:** том форматируется по размеру (квоте), заполненный перезаписывает старейшие блоки; по возрасту ничего не
  удаляется; `firstBlockId > 0` — кольцо замкнулось.
- **Один писатель на том на хосте:** второй `VOLUME_MOUNT_RW` — `ALREADY_LOCKED`.
- **Отсрочка:** писатель исчезнувшей сессии закрывает открытые последовательности (как `FINISH_MEDIA`), отсоединяется,
  помнит `owner` и ждёт `OBSD_WRITER_GRACE_S`; `VOLUME_MOUNT_RW` с тем же непустым `owner` — `reattached: true`, без новой
  блокировки и восстановления; иной — `ALREADY_LOCKED` до конца отсрочки, затем чистый том. `owner` — заявление личности, не
  секрет.
- **Ограда тома** (патч 07): перед каждым блоком, статусом, освобождением, удалением и изменением размера движок сверяет
  замок тома по пути; писатель с чужим замком останавливается — `PUT_MEDIA` → `WRITER_STOPPED`, `detail` «volume lock
  lost»; чужой файл замка не удаляется никогда. Замок мёртвого демона держится, пока не устареет (`lockRefreshSec`, 30 с).
- **`VOLUME_UNCLEAN`** на `VOLUME_MOUNT_RW` — том не закрыт чисто: монтировать после `VOLUME_RECOVER`.
- **Остановка демона** (SIGTERM): закрывает всех писателей параллельно (каждый до 30 с); писатель, который закрывается
  дольше 45 с, называется в журнале, демон выходит с кодом 3.

## Коды статуса

Закрытый список; ненулевой `status` ответа — один из них, `detail` — слова движка:

| Код | Имя |
|---|---|
| 0 | `OK` |
| 1–25 | `GENERIC_ERROR`, `PERMISSION_DENIED`, `OPERATION_IN_PROGRESS`, `OPERATION_CANCELED`, `IO_ERROR`, `INTERNAL_ERROR`, `DATA_CORRUPTED`, `INVALID_CIPHER_KEY`, `ALREADY_FORMATTED`, `PATH_NOT_EMPTY`, `NOT_A_VOLUME`, `ALREADY_LOCKED` (12), `UNSUPPORTED_FORMAT`, `READ_ONLY` (14), `VOLUME_UNCLEAN` (15), `NO_BLOCK`, `INVALID_BLOCK_RANGE`, `PARTIAL_CONTENT`, `EMPTY_RESULT` (19), `NO_SPACE` (20), `BLOCK_ALREADY_EXISTS`, `UNEXPECTED_BLOCK_ID`, `PROTECTED_VOLUME` (23), `DEVICE_OR_RESOURCE_BUSY`, `GENERIC_NETWORK_ERROR` (25) — по порядку |
| 100 | `INVALID_ARGUMENT` |
| 110–118 | `SEQUENCE_SAMPLE_TIME_INVALID`, `SEQUENCE_TIME_INVALID`, `SEQUENCE_TYPE_CHANGED`, `SEQUENCE_DUPLICATE_INIT_DATA`, `SEQUENCE_LATE_INIT_DATA`, `SEQUENCE_MISSING_INIT_DATA`, `SEQUENCE_NEEDS_KEY_SAMPLE`, `SEQUENCE_DISCONTINUITY`, `SEQUENCE_DURATION_INVALID` |
| 120–123 | `QUEUE_FULL`, `WRITER_STOPPED`, `SEQUENCE_TOO_LARGE`, `SEQUENCE_LOST` |
| 130–131 | `WRONG_HANDLE_KIND`, `INDEX_REPLAY_PENDING` |
| 1000–1005 | `PROTOCOL_ERROR` (кадр или JSON не по форме), `UNKNOWN_HANDLE`, `PROTO_VERSION` (общей версии нет — соединение закрыто), `SHUTTING_DOWN`, `UNKNOWN_OP`, `FRAME_TOO_LARGE` |

## Не обслуживается

Многотомные читатели и писатели, защищённые тома, стирание, шифрование, построитель последовательностей, восстановление с
прогрессом.
