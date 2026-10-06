#!/bin/sh
# Runs marks_probe_test.go (PRODUCT, ADR-0054) inside package w2cplatform via -overlay; the product tree is not touched.
# Usage: sh run_marks_probe.sh <product-root> [-run regex]
set -e
ROOT=$(cd "$1" && pwd); shift
HERE=$(cd "$(dirname "$0")" && pwd)
OV=$(mktemp -t marksov).json
printf '{"Replace":{"%s/vmsworker/w2cplatform/zz_marks_probe_test.go":"%s/marks_probe_test.go"}}' "$ROOT" "$HERE" > "$OV"
cd "$ROOT/vmsworker"
go test -count=1 -overlay "$OV" -run "${2:-TestProbe}" -v ./w2cplatform/ 2>&1 | grep -E "MEASURED|DEFECT|^(--- |ok|FAIL|PASS)|panic" 
