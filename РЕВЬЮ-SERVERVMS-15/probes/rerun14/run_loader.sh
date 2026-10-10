#!/bin/zsh
S=/private/tmp/claude-501/-Users-murat-w2c/9fcfbba6-c100-4841-b1c3-27ac748a363f/scratchpad/r15
PY=/Users/murat/w2c/vms-nightly/venv/bin/python
P=/Users/murat/w2c/server-vms-course/РЕВЬЮ-SERVERVMS-14/probes
L=$1
if [ "$L" = before ]; then C=$S/course-before; PR=$S/product-before; else C=$S/course; PR=$S/product; fi
D=$S/probes15/loader-$L
mkdir -p $D/work
echo "=== spec_loaders ($L) $(date +%H:%M:%S)"
perl -e 'alarm 1500; exec @ARGV' -- $PY $P/loader/probe_spec_loaders.py $C $PR $D/specload.bin $D/work > $S/logs/rerun14-loader_spec_loaders-$L.log 2>&1
echo "exit=$?" >> $S/logs/rerun14-loader_spec_loaders-$L.log
echo "=== yaml_alike ($L) $(date +%H:%M:%S)"
perl -e 'alarm 300; exec @ARGV' -- $PY $P/loader/probe_yaml_alike.py $C $PR $D/yamldump.bin > $S/logs/rerun14-loader_yaml_alike-$L.log 2>&1
echo "exit=$?" >> $S/logs/rerun14-loader_yaml_alike-$L.log
echo "=== done ($L) $(date +%H:%M:%S)"
