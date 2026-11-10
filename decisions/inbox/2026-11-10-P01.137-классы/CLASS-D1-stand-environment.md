# D1 — стенд без окружения P/02.4 N1.2: кандидат не стартует, движок `blocked readiness:role`

**Случаев:** 281 «раннер GREEN, движок нет» — rights 67, daemon 111, group 103; ещё 78 «не GREEN у обоих» (daemon 10, group 68: раннер red по существу, движок заблокирован — совпадение цвета, не существа). Ворота добавляются в P01.125.

## Суть
Движок запускает стендовую команду профиля `store` (`./bin/configstore -dir {data}/configstore -sockets {rundir} -rights {rights} …`) с урезанным окружением (только PATH, HOME, LANG и т. п.), без `PLATFORM_DIR`, `SERVER_NAME`, `BOX_ID`. Кандидат dcdc0bfe без `-id` и без `SERVER_NAME` отказывает в старте и сокетов не открывает; движок ждёт `admin.sock` и сокеты ролей и пишет `blocked readiness:role`, все шаги — `not_executed stand`. Раннер на тех же бинарниках исполняет цели (rights 67/67 GREEN, daemon 111/121, group 103/171).

Проба (та же песочница `calib-p0110`, тот же бинарник, те же флаги и файл прав главы 2 — `/home/pilot/owner-receipts/P01.110-engine-vs-p0193-20261110/probe-start.sh`):
- без окружения: `configstore: … start_flags flag=-id cause="member id or SERVER_NAME is required"`, rc=2, каталог сокетов пуст;
- с `SERVER_NAME=srv-a PLATFORM_DIR=<data>`: через 4 с есть `admin.sock`, `console.sock`, `testsubcontroller.sock`, `testsubworker.sock`, `testsub2worker.sock`.

## Норма
`Platform/common/acceptance/README.md`, строки 128–131 («One data directory»): «The stand translates the substitutions into the environment of P/02.4 N1.2: `PLATFORM_DIR={data}`, `PLATFORM_STORE=configstore://<role socket>`, `CONSOLE_PORT={port}`, `RESOURCE_PORT={rport}`, `BOX_ID`, `SERVER_NAME`, `SECRETS_KEY=…`». Строка 115: «`SERVER_NAME` (`srv-a` on a single-server stand; P/02.4 N1.2)». Строка 203 (таблица окружения): «Every process, platform | `PLATFORM_DIR`, `PLATFORM_STORE`, `BOX_ID`, `SERVER_NAME`, …». Для группы — строка 519: «with the environment `BOX_ID=<id>`, `SERVER_NAME=<id>`, `PLATFORM_DIR={data}/<id>`».

## Образцы
| Цель / шаг | Движок (`/srv/calib-p0180/p0110/out/…/engine.json`) | Раннер (`…-court/acc/…`) |
|---|---|---|
| rights `08-role-header:21` | `P_01_2_rights`: result `blocked`, reason `readiness:role`; шаг `not_executed`, reason `stand` | `P_01_2_rights/P-01.2-rights.json`: step 2, line 21, `ok: true` |
| daemon `08-floor-replay:24` | `P_01_3_daemon`: шаг `not_executed stand` | `P_01_3_daemon/P-01.3-daemon.json`: step 2, line 24, `ok: true` |
| group `07-group-size:19` | `P_01_3_group`: шаг `not_executed stand` | `P_01_3_group/P-01.3-group.json`: step 15, line 19, `ok: false` (группа кандидата не собирается — красное по существу) |

## Код движка
`internal/engine/run_stand.go:227–236` — окружение запуска стенда:
```go
func (c *runContext) limitedEnvironment() []string {
	allowed := []string{"PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "LC_CTYPE", "TZ"}
	out := make([]string, 0, len(allowed))
	for _, name := range allowed {
		if value, ok := os.LookupEnv(name); ok {
			out = append(out, name+"="+value)
		}
	}
	return out
}
```
`run_stand.go:83` (`startShell(template, owner.Dir, c.limitedEnvironment())`); `run_stand.go:455–466` (`waitForStoreReady`: `admin.sock` и `<роль>.sock` по файлу прав); `scenario_verdict.go:52–59` (`addBlocked("readiness:role")`). Поиск `SERVER_NAME|PLATFORM_DIR` по коду движка — 0 совпадений.

## Мнение представителя
Исход — **движок**: норма однозначна (README 128–131, 203), раннер её исполняет, движок нет. По схеме: главная причина — модель; вторая — **цикл**: заглушка ворот P01.107/P01.114 запускает экземпляр без требования окружения, поэтому ворота `roles` («a target of it is not blocked … for a socket or readiness») зелёные на заглушке и не видят этого. Правило для ворот P01.125 (предлагаемое): заглушка стенда проверяет, что процесс экземпляра получил `PLATFORM_DIR` (= `{data}`) и `SERVER_NAME`, `BOX_ID` по таблице окружения README, и без них отказывает в старте так же, как настоящий кандидат; цель с таким отказом — красное ворот.

## Вопросы ревьюеру
1. Достаточно ли README 128–131 и 203, чтобы считать окружение обязанностью стенда судьи на любой стендовой цели P/01 (не только «composite stand»)?
2. Значения по умолчанию одиночного стенда — `SERVER_NAME=srv-a`, `BOX_ID=stand-box` (строка 115) — обязательны буквально или любое непустое?
3. Ловит ли предложенное правило класс и не наказывает ли движок, который выставляет окружение верно?
