# C11. extra: раннер на цели extra исполняет 3 группы проб из 15 строк `extra.tsv`

**Суть.** Мутант `red/mut-extra` (коммит `f059dc5`, `01-store/server.go:657`: принимается `Content-Length: +5`). На цели `P/01.1/extra` раннер засчитывает GREEN: «extra probes 84/84; run GREEN». Мутант не пойман, потому что раннер на цели extra исполняет только три группы проб: `full key (R29-01)`, `id fingerprint (run 36)`, `identity (R38-06)`. Форма `extra.tsv` даёт цели 15 строк, в том числе `extra-framing` с `Content-Length: +5`. Движок на extra `blocked readiness:role`, см. C02.

**Случаев:** 1 мутант. На двух кандидатах — 3 + 3 случая (группы проб раннера), они уже входят в C02.

## Норма
- `Platform/common/acceptance/forms/extra.tsv:17`: `P/01.1/extra	extra-framing	…#request-parsing-n21-p011-23	Content-Length: +5; two Content-Length of different values; a Content-Length of 23 nines; a chunk siz…`. Всего строк `P/01.1/extra` — 15 (`grep -c`).
- `forms/targets.routing.tsv`: `P/01.1/extra	extra	…` — «extra — the rows of forms/extra.tsv for the target, the probes of the README of the first directory (scenarios none)».
- `01-store/acceptance/1/README.md:127`: «`Content-Length: +5` — `400`».

## Наблюдения
- Раннер, `out/red-mut-extra/P_01_1_extra/runner/*.txt`: «full key (R29-01) ok 64/64; id fingerprint (run 36) ok 15/15; identity (R38-06) ok 5/5; extra probes 84/84; run GREEN».
- У раннера на цели door эта проба есть: `out/c36e6ac/P_01_1_door/runner/P-01.1-door.txt:25` «raw HTTP probe Content-Length: +5 ok». Мутант на door не прогонялся (план калибровки: мутант только на своей цели).

## Мнение представителя
**Раннер** (выведен — только запись). Маршрут говорит, что extra исполняет строки `extra.tsv` своей цели. Раннер исполняет часть из них, а сырые пробы разбора — на цели door. Мутант `+5` поймала бы проба door. Для красного набора второго круга: мутант `+5` относится и к door, и к extra (`extra-framing`), а судья обязан исполнить все 15 строк `extra.tsv` цели extra.

## Вопросы ревьюеру
1. Норма: пробы разбора (`extra-raw-line`, `extra-framing`, …) — это обязанность цели extra (`extra.tsv`) или door (README главы 1)? Сейчас одна проба названа в обоих местах. Если цели две, нужна явная граница.
