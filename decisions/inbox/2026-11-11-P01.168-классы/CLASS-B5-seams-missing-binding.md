# B5 — швы `seams.tsv` главы 1.3 без моста: `not_executed MissingBinding`

**Случаев:** 4 шага цели P/01.3/daemon, `Platform/01-store/acceptance/3/seams.tsv` стр. 3–6: s7-loopback-api-no-tls, s8-loopback-join-needs-tls, s9-public-api-needs-tls (`CALL store-start-flags …`), s10-import-floor-resume (`CALL store-copy-floor …`).

## Наблюдение движка
`engine.json`: `kind: seam`, `result: not_executed`, `reason: MissingBinding`. Код движка `ef7dcf9`: `internal/engine/run.go:149–159` ставит `MissingBinding` каждому шву, пока мост не подан. Суд шёл с `--bindings /srv/calib-p0180/bindings-empty` (`all188-diag.sh`), дескриптора моста нет. Повтор replay188 швы не охватывает (INDEX: «строки швов трассой не охвачены»), и повторять нечего: без моста шов не исполним по норме.

## Норма
J-вход `49e62279`:
- `common/acceptance/spec/acceptance.norms.md:61` (P/AC-R030): `MissingBinding` — «when a case outside the target `P/01/production` needs a test-side input of R050 that the invocation does not name»;
- `common/acceptance/README.md:486` и далее, «Explicit test-side seam bridge».

## Код кандидата
В профиле `01-store/acceptance.yaml` моста нет. Это и не обязанность профиля: мост — вход судьи (README:486). У кандидата есть `configstore-tool seam` (`cmd/configstore-tool/dispatch.go:27`), но к вердикту это не относится.

## Что видела модель
`README.md:458–523` (протокол швов) — в M. Модель читала его в вызове 32 (`sed -n 456,523p`, 22 КБ без обрезки). Таблица `seams.tsv` — вход судьи, в M её нет.

## Мнение
Исход — **верно по норме**, как N1 в P01.127. Не красное кандидата. GREEN цели этим снят по R031 (`acceptance.norms.md:65`), и это тоже верно.

## Вопросы ревьюеру
Нет.
