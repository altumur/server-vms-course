# Сверка «как построено»: cammeta-c-go 01-store

- реализация: `cammeta-c-go` commit `b3c054d8b91b`
- спецификация: выгрузка на пине `56fc448769ee` (пин реализации)
- экстрактор: `asbuilt/1+goextract/1`, источник `static`; `deps` — справочный снимок без сверки (ADR-0123 доп. (1) п. 1)

Число единиц; в скобках — из них с неуверенным сопоставлением (`fuzzy`).

| снимок | match | extra | absent | differs | out_of_scope |
|---|---|---|---|---|---|
| params | 47 (5) | 3 (2) | 3 | 0 | 21 |
| refusals | 32 (11) | 63 | 17 (17) | 0 | 68 |

## Лишнее (в коде есть, в спецификации нет) — 66, первые 20

| снимок | единица | fuzzy | спецификация | код | пометка |
|---|---|---|---|---|---|
| params | `flag:-input` | 0 |  | 01-store/cmd/configstore/main.go:311 type=string default= set=<command> |  |
| params | `flag:-from` | 1 |  | 01-store/cmd/configstore/main.go:310 type=string default= set=<command> | named in norms prose, not in the flags table |
| params | `flag:-groups` | 1 |  | 01-store/cmd/configstore/main.go:314 type=bool default=false set=<command> | named in norms prose, not in the flags table |
| refusals | `error:-group-size must be 1,3,5` | 0 |  | 01-store/cmd/configstore/main.go:87 run | error word in the lesson code, no spec row names it |
| refusals | `error:-id required in group` | 0 |  | 01-store/cmd/configstore/main.go:93 run | error word in the lesson code, no spec row names it |
| refusals | `error:-max-body: {e}` | 0 |  | 01-store/cmd/configstore/main.go:120 run | error word in the lesson code, no spec row names it |
| refusals | `error:-max-value: {e}` | 0 |  | 01-store/cmd/configstore/main.go:116 run | error word in the lesson code, no spec row names it |
| refusals | `error:LISTEN_FDNAMES count mismatch` | 0 |  | 01-store/cmd/configstore/main.go:280 inheritedListeners | error word in the lesson code, no spec row names it |
| refusals | `error:backup path must be outside data directory {dir}` | 0 |  | 01-store/internal/store/backup_door.go:26 BackupDoor | error word in the lesson code, no spec row names it |
| refusals | `error:backup path must be outside data directory {dir}` | 0 |  | 01-store/internal/store/copy.go:171 Backup | error word in the lesson code, no spec row names it |
| refusals | `error:backup publication: {e}; previous backup retained at {oldLink}: {restore}` | 0 |  | 01-store/internal/store/copy.go:295 publishBackup | error word in the lesson code, no spec row names it |
| refusals | `error:backup publication: {e}; rollback: {restore}` | 0 |  | 01-store/internal/store/copy.go:300 publishBackup | error word in the lesson code, no spec row names it |
| refusals | `error:backup requires a destination file` | 0 |  | 01-store/cmd/configstore/main.go:363 admin | error word in the lesson code, no spec row names it |
| refusals | `error:client certificate required` | 0 |  | 01-store/internal/store/tls.go:41 TLSConfig | error word in the lesson code, no spec row names it |
| refusals | `error:complete: import already finished` | 0 |  | 01-store/internal/store/copy.go:223 Import | error word in the lesson code, no spec row names it |
| refusals | `error:connection limits and leader-wait must be positive` | 0 |  | 01-store/cmd/configstore/main.go:112 run | error word in the lesson code, no spec row names it |
| refusals | `error:group required` | 0 |  | 01-store/internal/store/rights.go:68 ParseRights | error word in the lesson code, no spec row names it |
| refusals | `error:import/restore requires -dir and --from` | 0 |  | 01-store/cmd/configstore/main.go:388 admin | error word in the lesson code, no spec row names it |
| refusals | `error:invalid -tuning` | 0 |  | 01-store/cmd/configstore/main.go:109 run | error word in the lesson code, no spec row names it |
| refusals | `error:invalid LISTEN_FDS` | 0 |  | 01-store/cmd/configstore/main.go:273 inheritedListeners | error word in the lesson code, no spec row names it |

## Недостающее (в спецификации есть, в коде не найдено) — 20, первые 20

| снимок | единица | fuzzy | спецификация | код | пометка |
|---|---|---|---|---|---|
| params | `flag:-isolated` | 0 | P/01.3 Н1.3 «Флаги демона» #13 type=без значения default=выключен |  |  |
| params | `flag:-peers` | 0 | P/01.3 Н1.3 «Флаги демона» #15 type=список `id@<raft host:port>/<api host:port>` через запятую default=нет: у `recover` обязателен |  |  |
| params | `flag:-upper` | 0 | P/01.3 Н1.3 «Флаги демона» #14 type=целое 0 … 2^53 − 1 default=нет |  |  |
| refusals | `reason:P/01.2 Н4 #11/1` | 1 | P/01.2 Н4 #11 exit refusal: файл прав не по форме |  | no literal token to match by |
| refusals | `reason:P/01.2 Н4 #11/2` | 1 | P/01.2 Н4 #11 exit refusal: называет `admin`/`configstore`/`configstore-door` |  | no lesson error word carries tokens admin,configstore,configstore-door |
| refusals | `reason:P/01.2 Н4 #11/3` | 1 | P/01.2 Н4 #11 exit refusal: роль не по грамматике |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #13/1` | 1 | P/01.3 Н4 #13 exit nonzero: `backup` в файл внутри `-dir` демона |  | no lesson error word carries tokens backup,-dir |
| refusals | `reason:P/01.3 Н4 #23/2` | 1 | P/01.3 Н4 #23 exit refusal: база меньше наибольшей версии |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #23/3` | 1 | P/01.3 Н4 #23 exit refusal: строка больше 512 КиБ |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #23/4` | 1 | P/01.3 Н4 #23 exit refusal: эпоха или пол не десятичные |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #23/5` | 1 | P/01.3 Н4 #23 exit refusal: нечитаемая |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #25/1` | 1 | P/01.3 Н4 #25 exit refusal: неизвестен upper, не отсечена старая группа, переполнение |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #27/1` | 1 | P/01.3 Н4 #27 exit nonzero: N не целое 0 … 2^53 − 1 или ниже вычисленного upper |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #28/1` | 1 | P/01.3 Н4 #28 exit nonzero: элемент не `id@<raft host:port>/<api host:port>`, пустой элемент, повтор id или нет `-id` среди них (Н2 `-peers`; догадк |  | no lesson error word carries tokens id@<raft,-id,-peers |
| refusals | `reason:P/01.3 Н4 #5/2` | 1 | P/01.3 Н4 #5 exit 2: размер не 1/3/5 |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #5/4` | 1 | P/01.3 Н4 #5 exit 2: сертификат двери у голосующего |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #6/3` | 1 | P/01.3 Н4 #6 exit 2: флаг вне таблицы «Флаги демона» |  | no literal token to match by |
| refusals | `reason:P/01.3 Н4 #7/2` | 1 | P/01.3 Н4 #7 exit 2: чужие `format` или `version` |  | no lesson error word carries tokens format,version |
| refusals | `word:-isolated` | 1 | P/01.3 Н4 #26 exit nonzero |  | no code literal carries this word (words of HTTP refusals are not normative) |
| refusals | `word:Готово` | 1 | P/01.3 Н4 #14 exit nonzero |  | no code literal carries this word (words of HTTP refusals are not normative) |

## Разошлось — 0, первые 20

нет
