# K3 — log-mask: в `cmd/vector-common` нет ветки пакета

**Случаев:** 39 — `P/01/vectors-log-mask`, все строки `common/vectors/log-mask/cases.tsv`. Движок: `red, class stand, reason command, response malformed` (класс неверен, см. E5).

## Наблюдение
Профиль кандидата объявляет `common/log-mask: ./bin/vector-common {input}`, но в `01-store/cmd/vector-common/main.go:61–73` (`execute`) ветки нет:
```go
switch request.Package {
case "common/store-client": …
case "common/revoked": …
case "common/crl": …
default:
	return nil, 0, fmt.Errorf("unsupported vector package %q", request.Package)
}
```
`main` при ошибке выходит с кодом 2. То же для объявленного `common/family-read`: эта цель в суд не входила.

## Норма
- M: `Platform/common/vectors/consumers.tsv` — потребители пакета `common/log-mask` (P/01 среди них).
- M: `common/vectors/log-mask/README.md` — алгоритм.
- M: PROFILE.md (раздел `vectors`) — команда пакета обязана дать ответ своей формы на каждый конверт.

## Мнение представителя
Исход — **кандидат**: пакет объявлен в профиле, но не реализован. Причина: модель (без обратной связи). Ворота попытки 5 команды векторов не исполняли, догадки нет, теста пакета нет. Вторая причина — **цикл**. Предлагаемое правило — то же, что в K2: команда каждого объявленного пакета проверяется на конверте формы PROFILE.md. Пакет без ветки даёт код 2 и ловится без знания урока.

## Вопросы ревьюеру
1. Должна ли полнота профиля (P01.24, проверка в цикле) ловить «пакет объявлен — ветки нет»? Сейчас она сверяет только ключи.
