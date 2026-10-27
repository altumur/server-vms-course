// Раннер стандартного стека В7 на Go (ADR-0092): JSON Schema 2020-12 и CEL. Пока — закрепление модулей стенда.
package main

import (
	_ "github.com/google/cel-go/cel"
	_ "github.com/google/cel-go/ext"
	_ "github.com/santhosh-tekuri/jsonschema/v6"
)

func main() {}
