package flags

// Закрытый словарь типов таблицы флагов (шапка forms/daemon-flags.tsv; ADR-0125 № 3), написан руками один раз;
// генератор tools/normgen/gen_flags.py копирует файл в пакет рядом с flags.go. Каждый тип — разбор слова командной
// строки в значение CEL (f[...] в required и bad) и в типизированное значение поля Flags.
//
// Значения CEL: path, dir, file, addr, id, duration, list:… — строка как дана; int:…, bytes:>0 и enum из одних целых —
// int64; прочий enum — строка; bool — true.

import (
	"errors"
	"net"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Member — элемент списка id@addr или id@addr/addr: id и адреса по порядку записи.
type Member struct {
	ID    string
	Addrs []string
}

var memberID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$`) // P/01.3 Н2: 1–128 ASCII, первый — буква или цифра

func valNonEmpty(raw string) (string, error) {
	if raw == "" {
		return "", errors.New("empty value")
	}
	return raw, nil
}

// valAddr — host:port по шапке формы (P/01.3-R031): хост непустой — имя, IPv4 или [IPv6]; порт — десятичное 1…65535
// без ведущих нулей.
func valAddr(raw string) (string, error) {
	host, port, err := net.SplitHostPort(raw)
	if err != nil {
		return "", errors.New("not host:port")
	}
	if !digits(port) || port[0] == '0' || len(port) > 5 {
		return "", errors.New("the port is not a decimal number 1–65535")
	}
	if n, _ := strconv.Atoi(port); n > 65535 {
		return "", errors.New("the port is above 65535")
	}
	switch {
	case host == "":
		return "", errors.New("an empty host")
	case strings.HasPrefix(raw, "["):
		if ip := net.ParseIP(host); ip == nil || !strings.Contains(host, ":") {
			return "", errors.New("[…] is not an IPv6 address")
		}
	case ipv4ish.MatchString(host):
		if ip := net.ParseIP(host); ip == nil || ip.To4() == nil {
			return "", errors.New("not an IPv4 address")
		}
	case !hostName.MatchString(host):
		return "", errors.New("the host is not a name, IPv4 or [IPv6]")
	}
	return raw, nil
}

var (
	ipv4ish  = regexp.MustCompile(`^[0-9.]+$`)
	hostName = regexp.MustCompile(`^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*$`)
	duration = regexp.MustCompile(`^([1-9][0-9]*)(ms|s|m|h)$`)
)

func valID(raw string) (string, error) {
	if !memberID.MatchString(raw) {
		return "", errors.New("not a member id (1–128 ASCII: a letter or a digit, then letters, digits, _ . -)")
	}
	return raw, nil
}

// typeInt — десятичное целое со знаком минус или без знака, без ведущих нулей, в границах [min, max] (hasMax — есть ли max).
func valInt(raw string, min, max int64, hasMax bool) (int64, error) {
	body := strings.TrimPrefix(raw, "-")
	if !digits(body) || (len(body) > 1 && body[0] == '0') {
		return 0, errors.New("not a decimal integer")
	}
	n, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return 0, errors.New("the integer is out of int64")
	}
	if n < min || (hasMax && n > max) {
		return 0, errors.New("the integer is out of range")
	}
	return n, nil
}

// typeBytes — bytes:>0: целое число байт > 0, десятичное, без суффиксов.
func valBytes(raw string) (int64, error) {
	n, err := valInt(raw, 1, 0, false)
	if err != nil {
		return 0, errors.New("not an integer of bytes > 0")
	}
	return n, nil
}

// valDuration — длительность по шапке формы: [1-9][0-9]*(ms|s|m|h), больше 0 (5s, 250ms; не 1h30m, не 1.5s, не µs).
func valDuration(raw string) (time.Duration, error) {
	m := duration.FindStringSubmatch(raw)
	if m == nil {
		return 0, errors.New("not a duration <integer>(ms|s|m|h) > 0")
	}
	n, err := strconv.ParseInt(m[1], 10, 64)
	unit := map[string]time.Duration{"ms": time.Millisecond, "s": time.Second, "m": time.Minute, "h": time.Hour}[m[2]]
	if err != nil || n > int64((1<<63-1)/unit) {
		return 0, errors.New("the duration is out of range")
	}
	return time.Duration(n) * unit, nil
}

// typeEnum — одно из значений; ints — все значения целые: значение CEL — int64.
func valEnum(raw string, values []string, ints bool) (any, error) {
	for _, v := range values {
		if raw == v {
			if ints {
				n, _ := strconv.ParseInt(v, 10, 64)
				return n, nil
			}
			return raw, nil
		}
	}
	return nil, errors.New("not one of " + strings.Join(values, " | "))
}

// typeList — list:id@addr (addrs = 1) и list:id@addr/addr (addrs = 2): через запятую, не пуст, каждый элемент полный.
func valList(raw string, addrs int) ([]Member, error) {
	if raw == "" {
		return nil, errors.New("an empty list")
	}
	var out []Member
	for _, el := range strings.Split(raw, ",") {
		id, rest, ok := strings.Cut(el, "@")
		if !ok {
			return nil, errors.New("the element " + strconv.Quote(el) + " is not id@address")
		}
		if _, err := valID(id); err != nil {
			return nil, errors.New("the element " + strconv.Quote(el) + ": " + err.Error())
		}
		parts := strings.Split(rest, "/")
		if len(parts) != addrs {
			return nil, errors.New("the element " + strconv.Quote(el) + " has not " + strconv.Itoa(addrs) + " address(es)")
		}
		for _, a := range parts {
			if _, err := valAddr(a); err != nil {
				return nil, errors.New("the element " + strconv.Quote(el) + ": " + err.Error())
			}
		}
		out = append(out, Member{ID: id, Addrs: parts})
	}
	return out, nil
}

func digits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}
