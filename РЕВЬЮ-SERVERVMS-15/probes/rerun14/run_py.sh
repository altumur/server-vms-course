#!/bin/zsh
# usage: run_py.sh <label: before|after>
S=/private/tmp/claude-501/-Users-murat-w2c/9fcfbba6-c100-4841-b1c3-27ac748a363f/scratchpad/r15
PY=/Users/murat/w2c/vms-nightly/venv/bin/python
P=/Users/murat/w2c/server-vms-course/РЕВЬЮ-SERVERVMS-14/probes
L=$1
if [ "$L" = before ]; then C=$S/course-before; else C=$S/course; fi
run() { # name script args...
  name=$1; shift
  echo "=== $name ($L) $(date +%H:%M:%S)"
  perl -e 'alarm 300; exec @ARGV' -- $PY "$@" > $S/logs/rerun14-$name-$L.log 2>&1
  echo "exit=$?" >> $S/logs/rerun14-$name-$L.log
  tail -n 40 $S/logs/rerun14-$name-$L.log
}
cd $C/Source
run base_b1 $P/base/b1_restart_failures_wiped.py $C/Source
run base_b3 $P/base/b3_take_epoch_after_lost.py $C/Source
run base_b4 $P/base/b4_claim_hold_by_foreign_clock.py $C/Source
run base_b5 $P/base/b5_backoff_constructor.py $C/Source
run door_course $P/door/door_requests_course.py $C/Source
run filings_course $P/filings/p_r14_filings_course.py $C/Source
run filings_rid_namespace $P/filings/p_r14_rid_namespace_course.py $C/Source
run filings_worker_requests_loader $P/filings/p_r14_worker_requests_loader_course.py $C/Source
run marks_holder_paths $P/marks/p_marks_holder_paths.py $C
run marks_m11_rights $P/marks/p_marks_m11_rights.py $C
run marks_race $P/marks/p_marks_race_closer_vs_holder.py $C
