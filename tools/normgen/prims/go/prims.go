package checks

// Примитивы #fn таблиц проверок (ADR-0120 п. 2 (а)), написаны руками один раз; генератор копирует файл в пакет.
// Имя примитива — prim + имя #fn в CamelCase; ответ (значение, ошибка), ошибка — ошибка CEL.
// Аргументы уже проверены по типам объявления #fn. #fn без примитива здесь (allowed) — поле обратного вызова в Fns.

import (
	"errors"
	"math"
	"net"
	"strings"
)

// primKeyOk — Н1 row.key: не пуст, не начинается с /, нет сегмента .., не длиннее 1024 байт UTF-8.
func primKeyOk(k string) (bool, error) {
	if k == "" || strings.HasPrefix(k, "/") || len(k) > 1024 {
		return false, nil
	}
	for _, seg := range strings.Split(k, "/") {
		if seg == ".." {
			return false, nil
		}
	}
	return true, nil
}

// primWeight — Н1: сумма длин в байтах UTF-8 всех имён и значений items; не строка — ошибка.
func primWeight(items map[string]any) (int64, error) {
	var total int64
	for name, value := range items {
		s, ok := value.(string)
		if !ok {
			return 0, errors.New("weight: items is not an object of strings")
		}
		total += int64(len(name) + len(s))
	}
	return total, nil
}

// primFinite — конечно в binary64 (1e400 — нет).
func primFinite(x float64) (bool, error) {
	return !math.IsInf(x, 0) && !math.IsNaN(x), nil
}

// primLoopback — хост адреса host:port на петле: 127.0.0.0/8, ::1 или localhost (ADR-0125 доп. (2) п. 4).
// IPv4 в форме ::ffff:a.b.c.d — как IPv4; зона (%lo) и прочие имена — не петля. Не host:port — ошибка CEL.
func primLoopback(addr string) (bool, error) {
	host, _, err := net.SplitHostPort(addr)
	if err != nil {
		return false, errors.New("loopback: not host:port")
	}
	if strings.EqualFold(host, "localhost") {
		return true, nil
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return false, nil
	}
	if v4 := ip.To4(); v4 != nil {
		return v4[0] == 127, nil
	}
	return ip.Equal(net.IPv6loopback), nil
}
