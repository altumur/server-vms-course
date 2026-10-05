#!/usr/bin/env bash
# М11 Lesson 8 — the power pull, measured. Three runs, worst case kept.
#
#   deploy/cluster/failover-drill.sh <server> <console host:port> [runs] [server|process]
#
# `server` (the default): every unit of <server> stops at once over ssh — the store's member, its resource, its
# workers — standing in for the power cut (М9's bench/outage.sh power-cut for the real thing). Nothing restarts the
# worker anywhere else: the controller moves its cameras by assignment after two silences — the slot out (45 s) and
# out by the margin (45 s more), and the server's resource silent — some 90 s and a pass.
# `process`: only the worker's process is killed (SIGKILL). systemd starts the unit again in two seconds under the same
# name; the cameras do not move, and the number is the restart.
#
# For each run: note which cameras w-<server>-1 holds, pull, wait until every one of them is live on another worker
# (or, `process`, on the same name again), read the console's numbers, bring the server back, and read
# vms_epoch_conflicts after its old instance has woken: the old one fenced by the epochs, its footage kept.
set -u
SERVER="${1:?the server to pull, e.g. srv-a}"; CONSOLE="${2:?console host:port, e.g. 10.0.0.12:8080}"
RUNS="${3:-3}"; MODE="${4:-server}"
WORKER="w-$SERVER-1"
UNITS="vms-vmsworker vms-recworker w2c-console vms-vmscontroller vms-reccontroller w2c-resource configstore"

held() {                      # the cameras a worker holds, live, from the console's /cameras rows
  W="$1" python3 -c '
import sys, json, os
try:
    rows = json.load(sys.stdin)["rows"]
except ValueError:
    rows = []
print(" ".join(str(r["id"]) for r in rows if r["worker"] == os.environ["W"] and r["worker_state"] == "live"))'
}
where() {                     # "<worker>" for each of the cameras named, "" while one is not live anywhere
  CAMS="$1" python3 -c '
import sys, json, os
want = set(os.environ["CAMS"].split())
try:
    rows = {str(r["id"]): r for r in json.load(sys.stdin)["rows"]}
except ValueError:
    rows = {}
live = [rows[c]["worker"] for c in want if c in rows and rows[c]["worker_state"] == "live"]
print(" ".join(sorted(set(live))) if len(live) == len(want) else "")'
}

worst=0
for i in $(seq 1 "$RUNS"); do
  cams="$(curl -s "http://$CONSOLE/cameras" | held "$WORKER")"
  [ -n "$cams" ] || { echo "$WORKER holds no live camera: nothing to measure"; exit 1; }
  t0=$(date +%s)
  echo "run $i: $WORKER holds cameras $cams; pulling ($MODE) at $(date -u +%H:%M:%S)"
  if [ "$MODE" = process ]; then
    ssh "$SERVER" systemctl kill -s KILL vms-vmsworker.service
  else
    ssh "$SERVER" systemctl kill -s KILL $UNITS
    ssh "$SERVER" systemctl stop $UNITS
  fi
  now=""
  for _ in $(seq 1 240); do
    now="$(curl -s "http://$CONSOLE/cameras" | where "$cams")"
    if [ -n "$now" ]; then
      [ "$MODE" = process ] && [ "$now" = "$WORKER" ] && break
      [ "$MODE" != process ] && [ "$now" != "$WORKER" ] && break
    fi
    now=""; sleep 1
  done
  [ -n "$now" ] || { echo "run $i: cameras $cams not live again within 240 s"; exit 1; }
  t1=$(date +%s)
  echo "run $i: cameras $cams live on $now after wall-clock $((t1 - t0))s"
  worst="$(python3 -c "print(max($worst, $((t1 - t0))))")"
  if [ "$MODE" != process ]; then
    ssh "$SERVER" systemctl start $UNITS
    sleep 30
    conflicts="$(curl -s "http://$CONSOLE/metrics" | awk -v w="$WORKER" '$0 ~ "vms_epoch_conflicts\\{worker=\"" w "\"" {print $2; exit}')"
    echo "run $i: $SERVER returned; vms_epoch_conflicts{$WORKER}: ${conflicts:-?}   (the old instance fenced by the epochs, its footage kept under its epoch; nothing moves back)"
  fi
done
echo
echo "failover worst case over $RUNS runs ($MODE): ${worst}s   <- the datasheet number"
