// Ручная среда маршрутизации двери урока по x-route-priority (ADR-0125 № 2; P/05-R057 и его 4 правила): выбор
// операции по таблицам routes.go. Копируется только уроку, у которого в OpenAPI есть x-route-priority.
//
// Путь не декодируется целиком до совпадения: литералы сравниваются по сырым байтам сегментов, хвостовой «/» не
// нормализуется, «%2F» не делит сегмент. Параметр segment берёт один сырой сегмент, remainder (только последним) —
// сырой остаток пути целиком (пустой хвост и a//b — как есть). Из шаблонов, совпавших по форме, остаются те, у
// которых есть метод запроса; из них — наименьший x-route-priority. Совпадение есть, метода нет — 405 без тела; нет
// совпадения — 404 без тела. Затем параметры декодируются (x-path-decode percent-segment: каждый сегмент отдельно,
// декодированный «/» недопустим) и проверяются по схеме; ошибка параметра — x-path-error[метод] без отката к другому
// маршруту.
package apidoor

import (
	"strings"
	"unicode/utf8"
)

// Match — выбранная операция и параметры пути (декодированные).
type Match struct {
	Op     Op
	Params map[string]string
}

// RouteError — отказ маршрута: Code 404 / 405 (Response "" — без тела) или ошибка параметра Param операции Op по
// x-path-error (Code и Response — схема тела components/schemas или "" — без тела).
type RouteError struct {
	Code     int
	Response string
	Op       Op
	Param    string
	Reason   string
}

func (e *RouteError) Error() string { return e.Reason }

type prioSegment struct {
	lit       string
	param     string
	remainder bool
}

type prioTemplate struct {
	path     string
	segs     []prioSegment
	priority int
}

// pathError — x-path-error параметра по методу: статус и схема тела ("" — без тела).
type pathError struct {
	status   int
	response string
}

func (t prioTemplate) shape(raw []string) (map[string]string, bool) {
	params := map[string]string{}
	for i, s := range t.segs {
		if s.remainder {
			if i >= len(raw) { // остаток — после своего «/»: «/v1/objects» не шаблон «/v1/objects/{key}»
				return nil, false
			}
			params[s.param] = strings.Join(raw[i:], "/")
			return params, true
		}
		if i >= len(raw) {
			return nil, false
		}
		if s.param == "" {
			if raw[i] != s.lit {
				return nil, false
			}
			continue
		}
		params[s.param] = raw[i]
	}
	return params, len(raw) == len(t.segs)
}

// decodeSegment — percent-segment: один сегмент, %XX → байт; декодированный «/» или неверный %XX — ошибка.
func decodeSegment(s string) (string, bool) {
	d, ok := unescapeSegment(s)
	if !ok || strings.Contains(d, "/") {
		return "", false
	}
	return d, true
}

func unescapeSegment(s string) (string, bool) {
	if !strings.Contains(s, "%") {
		return s, true
	}
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] != '%' {
			b.WriteByte(s[i])
			continue
		}
		if i+2 >= len(s) {
			return "", false
		}
		h, ok1 := hexDigit(s[i+1])
		l, ok2 := hexDigit(s[i+2])
		if !ok1 || !ok2 {
			return "", false
		}
		b.WriteByte(h<<4 | l)
		i += 2
	}
	return b.String(), true
}

func hexDigit(c byte) (byte, bool) {
	switch {
	case c >= '0' && c <= '9':
		return c - '0', true
	case c >= 'a' && c <= 'f':
		return c - 'a' + 10, true
	case c >= 'A' && c <= 'F':
		return c - 'A' + 10, true
	}
	return 0, false
}

// Route — операция метода и сырого пути запроса (target без query) по правилам x-route-priority урока.
func Route(method, rawPath string) (Match, *RouteError) {
	if !strings.HasPrefix(rawPath, "/") {
		return Match{}, &RouteError{Code: 404, Reason: "not a request path"}
	}
	raw := strings.Split(rawPath[1:], "/")
	if rawPath == "/" {
		raw = []string{}
	}
	m := strings.ToUpper(method)
	shaped := false
	var best *prioTemplate
	var bestParams map[string]string
	for i := range prioTemplates {
		t := &prioTemplates[i]
		params, ok := t.shape(raw)
		if !ok {
			continue
		}
		shaped = true
		if _, has := byPathMethod[t.path+" "+m]; !has {
			continue
		}
		if best == nil || t.priority < best.priority {
			best, bestParams = t, params
		}
	}
	if best == nil {
		if shaped {
			return Match{}, &RouteError{Code: 405, Reason: "method " + m + " is not of the matched paths"}
		}
		return Match{}, &RouteError{Code: 404, Reason: "no route"}
	}
	op := byPathMethod[best.path+" "+m]
	out := map[string]string{}
	for _, s := range best.segs {
		if s.param == "" {
			continue
		}
		v := bestParams[s.param]
		dec, ok := v, true
		if pathDecode[best.path][s.param] {
			if s.remainder {
				parts := strings.Split(v, "/")
				for k, p := range parts {
					if parts[k], ok = decodeSegment(p); !ok {
						break
					}
				}
				dec = strings.Join(parts, "/")
			} else {
				dec, ok = decodeSegment(v)
			}
		}
		if ok && v == "" {
			ok = false // пустой захват — ошибка параметра операции
		}
		if ok && !utf8.ValidString(dec) {
			ok = false // значение параметра — строка UTF-8 (s32: %FF)
		}
		if ok {
			if name := pathSchemas[best.path][s.param]; name != "" && Validate(name, dec) != nil {
				ok = false
			}
		}
		if !ok {
			pe, has := pathErrors[best.path][s.param][m]
			if !has {
				pe = pathError{status: 404}
			}
			return Match{}, &RouteError{Code: pe.status, Response: pe.response, Op: op, Param: s.param,
				Reason: "parameter " + s.param + " of " + best.path}
		}
		out[s.param] = dec
	}
	return Match{Op: op, Params: out}, nil
}

// Admitted — роль сертификата допущена к операции по door-roles.tsv (режим mtls): «*» — любая роль пакета;
// «<sub>worker» — «<имя>worker» для имени загруженного каталога (isSub). Операция без строки таблицы — не допущена.
func Admitted(op Op, role string, isSub func(string) bool) bool {
	for _, r := range opRoles[op] {
		switch {
		case r == "*":
			return role != ""
		case r == "<sub>worker":
			if strings.HasSuffix(role, "worker") && isSub != nil && isSub(strings.TrimSuffix(role, "worker")) {
				return true
			}
		case r == role:
			return true
		}
	}
	return false
}
