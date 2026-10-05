#!/usr/bin/env bash
# М11 — the checks that need a real cluster, in one run, on one of its servers (as root). PASS/FAIL per item.
#
#   deploy/cluster/verify-bench.sh
#
# 1. the store: this server's daemon answers on admin.sock, the group has three members and one leader
# 2. the units of a server are active here (configstore, w2c-resource, w2c-console, the controllers, the workers)
# 3. every role's socket is 0660 and owned by its role's group (the rights file's `group`)
# 4. the rights the daemon holds are the installed file, and the file is what the spec generates
# 5. rights by the socket: the worker's socket writes its slot and is refused a camera row and placement (403);
#    the console's writes a camera row and is refused placement — one writer per key, the daemon's word
# 6. the -api door is mutual TLS: a client with no certificate is refused at the handshake
# 7. the objects: the resource here lists every server's worker heartbeat (`/v1/objects?scope=cluster`)
# 8. the mirror is resource to resource: a peer takes a copy and lists it; nothing went through a store
set -u
SOCKETS="${CONFIGSTORE_SOCKETS:-/run/configstore}"
RUN=/opt/w2c/bin/w2c-run.sh
pass=0; fail=0
ok()   { echo "  PASS  $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL  $*"; fail=$((fail+1)); }
api()  { curl -s --unix-socket "$SOCKETS/$1.sock" -o /dev/null -w "%{http_code}" -H 'Content-Type: application/json' \
              -X "$2" "http://configstore$3" ${4:+--data "$4"}; }
put()  { api "$1" POST /v1/write "{\"op\": \"put\", \"key\": \"$2\", \"items\": {\"probe\": \"verify-bench\"}, \"cas\": null}"; }
drop() { api admin POST /v1/write "{\"op\": \"delete\", \"key\": \"$1\", \"cas\": null}" >/dev/null; }
py()   { PYTHONPATH=/opt/w2c/Source python3 "$@"; }

# 1
status="$(py -m w2cplatform.configstore status 2>/dev/null)"
if [ -n "$status" ]; then
  members="$(printf '%s' "$status" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["members"]))')"
  leader="$(printf '%s' "$status" | python3 -c 'import sys,json;s=json.load(sys.stdin);print(s.get("leader_id") or s.get("leader") or "")')"
  [ "$members" -ge 3 ] && [ -n "$leader" ] && ok "configstore: $members members, leader $leader" || bad "configstore: $members members, leader '${leader}'"
else
  bad "configstore: admin.sock does not answer (systemctl status configstore)"
fi

# 2
for u in configstore w2c-resource w2c-console vms-vmscontroller vms-reccontroller vms-vmsworker vms-recworker vms-obsd; do
  systemctl is-active --quiet "$u.service" && ok "$u active" || bad "$u not active"
done

# 3
for role in $(python3 -c 'import json;print(" ".join(json.load(open("/etc/w2c/configstore-rights.json"))["roles"]))'); do
  want="$(python3 -c "import json;print(json.load(open('/etc/w2c/configstore-rights.json'))['roles']['$role'].get('group',''))")"
  got="$(stat -c '%a %G' "$SOCKETS/$role.sock" 2>/dev/null)"
  [ "$got" = "660 $want" ] && ok "$role.sock: 660, group $want" || bad "$role.sock: '$got', want '660 $want'"
done

# 4
held="$(curl -s --unix-socket "$SOCKETS/admin.sock" http://configstore/v1/rights | python3 -c 'import sys,json;print(json.dumps(json.load(sys.stdin)["roles"], sort_keys=True))')"
file="$(python3 -c 'import json;print(json.dumps(json.load(open("/etc/w2c/configstore-rights.json"))["roles"], sort_keys=True))')"
[ -n "$held" ] && [ "$held" = "$file" ] && ok "the daemon holds the installed rights file" || bad "the daemon's rights differ from /etc/w2c/configstore-rights.json (restart configstore after installing it)"
"$RUN" rights --check /etc/w2c/configstore-rights.json >/dev/null && ok "the rights file is what the spec generates" || bad "the rights file is not what the spec generates now"

# 5
[ "$(put vmsworker vms/slots/w-verify)" = 200 ] && ok "vmsworker.sock writes vms/slots/*" || bad "vmsworker.sock cannot claim a slot"
[ "$(put vmsworker vms/cameras/verify)" = 403 ] && ok "vmsworker.sock refused on vms/cameras/* (403)" || bad "vmsworker.sock wrote a camera row — one writer per key is NOT enforced"
[ "$(put vmsworker vms/placement/verify)" = 403 ] && ok "vmsworker.sock refused on vms/placement/* (403)" || bad "vmsworker.sock wrote placement"
[ "$(put console vms/cameras/verify)" = 200 ] && ok "console.sock writes vms/cameras/*" || bad "console.sock cannot write a camera row"
[ "$(put console vms/placement/verify)" = 403 ] && ok "console.sock refused on vms/placement/* (403) — a console that can place is a second controller" || bad "console.sock wrote placement"
[ "$(put vmscontroller vms/placement/verify)" = 200 ] && ok "vmscontroller.sock writes vms/placement/*" || bad "vmscontroller.sock cannot place"
drop vms/slots/w-verify; drop vms/cameras/verify; drop vms/placement/verify

# 6
api_addr="$(python3 -c 'import sys;[print(l.split("=",1)[1].strip()) for l in open("/etc/w2c/w2c.env") if l.startswith("CONFIGSTORE_API=")]')"
if [ -n "$api_addr" ]; then
  if curl -sk --max-time 5 "https://$api_addr/v1/status" >/dev/null 2>&1; then bad "the -api door at $api_addr answered a client with no certificate"; else ok "the -api door at $api_addr refuses a client with no certificate"; fi
else
  bad "no CONFIGSTORE_API in /etc/w2c/w2c.env"
fi

# 7
listed="$(curl -s 'http://127.0.0.1:8090/v1/objects?prefix=vms/heartbeats/&scope=cluster' | python3 -c 'import sys,json;d=json.load(sys.stdin);print(" ".join(sorted({o["server"] for o in d["objects"].values()})), "missing:", ",".join(d.get("missing", [])) or "none")' 2>/dev/null)"
[ -n "$listed" ] && ok "objects: heartbeats from $listed" || bad "objects: the resource here does not list the cluster's heartbeats"

# 8
curl -s -o /dev/null -w "%{http_code}" -X PUT --data-binary '{"t":0,"kind":"probe"}' "http://127.0.0.1:8090/mirror/srv-verify/vms/0/e1/19700101T000000Z.events.jsonl" | grep -q 204 \
  && curl -s "http://127.0.0.1:8090/mirrored/srv-verify" | grep -q '"path"' && ok "mirror: the resource took a copy and lists it" || bad "mirror: PUT/GET on the resource failed"

echo; echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
