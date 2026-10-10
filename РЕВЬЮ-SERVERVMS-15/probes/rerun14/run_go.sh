#!/bin/zsh
# usage: run_go.sh <before|after>
S=/private/tmp/claude-501/-Users-murat-w2c/9fcfbba6-c100-4841-b1c3-27ac748a363f/scratchpad/r15
L=$1
if [ "$L" = before ]; then PR=$S/product-before; C=$S/course-before; else PR=$S/product; C=$S/course; fi
cd $PR
echo "=== vet/compile w2cplatform ($L) $(date +%H:%M:%S)"
W2C_COURSE_DIR=$C perl -e 'alarm 900; exec @ARGV' -- go vet ./vmsworker/w2cplatform/ ./vmsworker/vms/ 2>&1 | tail -40
echo "=== go test ($L) $(date +%H:%M:%S)"
W2C_COURSE_DIR=$C perl -e 'alarm 1500; exec @ARGV' -- go test -count=1 -v -run 'TestR14|TestProbe' ./vmsworker/w2cplatform/ ./vmsworker/vms/ > $S/logs/rerun14-go-$L.log 2>&1
echo "exit=$?" >> $S/logs/rerun14-go-$L.log
echo "=== done ($L) $(date +%H:%M:%S)"
grep -E '^(--- |=== RUN|ok|FAIL|PASS|exit=)|MEASURED|DEFECT|TWO_WRITERS|TAKEN_BACK|REV0|failures=|panic|cannot|undefined|not declared' $S/logs/rerun14-go-$L.log | head -200
