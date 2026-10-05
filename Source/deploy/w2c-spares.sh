#!/bin/sh
# w2c-spares.sh — start spare workers for what the console says is missing. Never stops one.
#
#   w2c-spares.sh [role ...]        roles as arguments, else $SPARES_ROLES (spaces or commas), else recworker
#
#   role         the console's number                                   this server's ceiling
#   recworker    rec_workers_needed{labels=""}  on /rec/metrics         MAX_RECORDERS  (8)
#   vmsworker    vms_workers_needed{labels}     on /metrics             MAX_WORKERS    (4)
#   liveworker   live_workers_needed{labels}    on /live/metrics        MAX_GATEWAYS   (4)
#   autoworker   auto_workers_needed{labels}    on /auto/metrics        MAX_EVALUATORS (4)
#
# It runs on the HOST, from `w2c-spares[-<role>].timer` — and that placement is the whole point of the file. Starting a
# process means talking to systemd (launchd); a console that could do it would be a console holding the power to
# start processes on its own machine, and "the platform does not start processes" would be a sentence with an
# exception in it. So the controller publishes NUMBERS and OFFERS (`SpecController.offer_spares`) and this script,
# which the operator installed deliberately, does the starting.
#
# NOT AS ROOT on Linux (the product's cross-check, 4 Oct): as `w2c`, the platform's user, whom
# polkit lets do one thing — `systemctl start` of an instance of a spare template (М11's `w2c-spares.rules`: the verb
# `start`, the units `vms-vmsworker-spare@<n>`, `vms-recworker-spare@<n>`) — and nothing else: no stop, no other
# unit, no `reset-failed`. What it writes for a spare is read by the spare's runner one line deep (`w2c-run.sh`: `SPARE_FOR=`,
# checked against the labels' alphabet), so the file it may write sets no other variable in a process holding the
# role's key. On macOS it runs as the box's user (`install.sh --box`, the thirteenth review, major 15): the roles' plists
# are that user's (`~/Library/LaunchAgents`), a spare is bootstrapped into that user's launchd domain (`gui/<uid>`) and
# runs as its role does — as that user, with no more than the box already has.
#
# The rules it follows:
#
#   1. It reads numbers, never a command. Running a string that arrived over HTTP on the host is remote code execution
#      with extra steps, however friendly the source.
#   2. A console that does not answer, or whose controller's pass is older than a minute (the numbers are not on its
#      page then), is a reason to start NOTHING.
#   3. Only the label sets THIS server covers: a camera on `vlan:cctv-dmz` is no use to a worker on a server that does
#      not reach that VLAN. The server's labels are the console's (`<prefix>_server_labels{server=…,source="console"}`
#      — what the administrator wrote for it), else this host's `$LABELS`.
#   4. Its own ceiling per role, counting the spares already running here: a bug on the other side that reported
#      "nine hundred missing" costs a log line, not nine hundred processes.
#   5. A camera worker, gateway or evaluator starts as a SPARE (`SPARE_FOR=<label set>`): it takes only an offer of
#      its set (`<sub>/slots/<w-N>` with `offer`), by CAS, and with none it waits holding nothing — two scripts on two
#      servers racing for one missing worker start two spares, and exactly one takes the slot. A recorder needs no
#      offer: it is placed by volume, and a recorder with no free volume to hold is already a spare.
#
# It never stops anything. A spare costs a few megabytes and is what makes the NEXT shortage get served in a pass
# instead of a deploy; deciding that a box has too many is a person's call, on purpose.
#
# A SPARE IS ITS ROLE'S UNIT, NOT A ROOT SHELL (the twelfth review, blocker 6). It ran as `systemd-run … $SPARES_RUN`:
# as root, without the cluster's key, without the fan-out opened — the cameras of a dead server whose passwords are
# sealed did not start on the very process started for them, and what it wrote was root's. Now it is started from a
# TEMPLATE that is the role's regular unit line for line but the name (`vms-<role>-spare@.service`, installed with
# the units: the same user, groups, socket, key, umask and watchdog — `tests/test_units.py` holds the two together),
# so whatever the role's unit is given, a spare is given; and the set it is for goes in a file of one line the
# template names (`SPARE_FILE=$SPARES_ENV/<unit>.env`, of which its runner takes `SPARE_FOR=` alone), the only thing
# this script says to it. No template for the role: nothing started, and said — never a process with less than its
# unit has.
#
#   Linux   SPARE_FOR=<set> into $SPARES_ENV/vms-<role>-spare@<n>.service.env; systemctl start vms-<role>-spare@<n>
#   macOS   the role's own plist ($LAUNCHD_DIR/com.w2c.vms.<role>.plist) copied as com.w2c.vms.<role>.spare-<n> — no
#           name, SPARE_FOR=<set>, its doors on ports the OS gives, its log beside its role's — into $SPARES_DIR, and
#           `launchctl bootstrap gui/<uid>`ped
set -eu

ME="${0##*/}"
CONSOLE="${CONSOLE:-http://127.0.0.1:8080}"
SERVER="${SERVER_NAME:-$(hostname -s 2>/dev/null || hostname)}"
# THE PLATFORM'S NAMES — spelled here and nowhere else below, so a rename is these lines: where a spare's set is
# written for its template (Linux), where the roles' plists are and the macOS spares' copies go. What a spare RUNS,
# its environment files and its credentials are its template's — the role's unit's — and nothing this script says. A
# spare itself is a process of a VMS subsystem, and keeps the subsystem's names: the unit `vms-<role>-spare@<n>`
# (macOS: `com.w2c.vms.<role>.spare-<n>`), the group `vms-<role>` of its role's store socket.
SPARES_DIR="${SPARES_DIR:-${W2C_BOX:+$W2C_BOX/state/run/w2c-spares}}"   # macOS: the spares' plists, under the box
SPARES_DIR="${SPARES_DIR:-/var/run/w2c-spares}"
SPARES_ENV="${SPARES_ENV:-/run/w2c-spares}"         # Linux: each spare's set, read by its runner (its timers' RuntimeDirectory)
LAUNCHD_DIR="${LAUNCHD_DIR:-${HOME:-}/Library/LaunchAgents}" # macOS: where `install.sh --box` put the roles' plists
DOMAIN="gui/$(id -u)"                               # macOS: the box's user's launchd domain
NAME=vms
roles=$(printf '%s' "${*:-${SPARES_ROLES:-recworker}}" | tr ',' ' ')

# Whether the label set $1 (comma-joined; "" the empty set) is within the labels $2 (comma-joined).
covers() {
    old_ifs=$IFS; IFS=,
    for l in $1; do
        case ",$2," in *",$l,"*) ;; *) IFS=$old_ifs; return 1 ;; esac
    done
    IFS=$old_ifs
    return 0
}

# Whether spare <n> of a role runs here.
running() {
    if [ "$linux" = 1 ]; then
        systemctl is-active --quiet "$NAME-$1-spare@$2"
    else
        launchctl print "$DOMAIN/com.w2c.$NAME.$1.spare-$2" >/dev/null 2>&1
    fi
}

# Whether this server has the role's spare template: the regular unit's twin (Linux), the regular plist (macOS).
template() {
    if [ "$linux" = 1 ]; then
        systemctl cat "$NAME-$1-spare@.service" >/dev/null 2>&1
    else
        [ -f "$LAUNCHD_DIR/com.w2c.$NAME.$1.plist" ]
    fi
}

# Start spare $2 of role $1, for the label set $3 — with no SPARE_FOR when $4 is empty (a recorder).
start() {                                           # sh has no locals: the arguments, by number
    if [ "$linux" = 1 ]; then
        if [ -n "$4" ]; then                        # the set, the one line its template reads; written before the start
            mkdir -p "$SPARES_ENV"
            printf 'SPARE_FOR=%s\n' "$3" >"$SPARES_ENV/$NAME-$1-spare@$2.service.env"
        fi
        # `start` alone — the one verb polkit gives this user. A spare that ended is started again by it; one whose
        # restarts ran past systemd's limit is refused, and the next number is tried.
        systemctl start "$NAME-$1-spare@$2"
    else
        # The role's plist, as launchd runs the role: its user, its environment, its log beside. Not its name — a spare
        # has none — and its doors on ports the OS gives: the server's own worker and recorder have 8554 and 8084.
        label="com.w2c.$NAME.$1.spare-$2"
        mkdir -p "$SPARES_DIR"
        plist="$SPARES_DIR/$label.plist"
        cp "$LAUNCHD_DIR/com.w2c.$NAME.$1.plist" "$plist"
        plutil -replace Label -string "$label" "$plist"
        plutil -remove EnvironmentVariables.WORKER_NAME "$plist" 2>/dev/null || true
        if [ -n "$4" ]; then
            plutil -replace EnvironmentVariables.SPARE_FOR -string "$3" "$plist"
        fi
        case "$1" in
            vmsworker) plutil -replace EnvironmentVariables.RTSP_PORT -string auto "$plist" ;;
            recworker) plutil -replace EnvironmentVariables.ARCHIVE_PORT -string 0 "$plist" ;;
        esac
        logs=$(plutil -extract StandardErrorPath raw -o - "$plist" 2>/dev/null) || logs=""
        logs=${logs%/*}
        plutil -replace StandardErrorPath -string "${logs:-.}/$label.log" "$plist"   # beside its role's
        plutil -replace StandardOutPath -string "${logs:-.}/$label.log" "$plist"
        chmod 0644 "$plist"
        launchctl bootout "$DOMAIN/$label" >/dev/null 2>&1 || true             # one that ended leaves its label behind
        launchctl bootstrap "$DOMAIN" "$plist"
    fi
}

if command -v systemctl >/dev/null 2>&1; then
    linux=1
elif [ "$(uname)" = Darwin ]; then
    linux=0
else
    echo "$ME: neither systemd nor macOS here — nothing started" >&2
    exit 0
fi
srv=$(printf '%s' "$SERVER" | sed 's/[.]/\\./g')

for role in $roles; do
    case "$role" in
        recworker)  page=/rec/metrics;  prefix=rec;  cap=${MAX_RECORDERS:-8} ;;
        vmsworker)  page=/metrics;      prefix=vms;  cap=${MAX_WORKERS:-4} ;;
        liveworker) page=/live/metrics; prefix=live; cap=${MAX_GATEWAYS:-4} ;;
        autoworker) page=/auto/metrics; prefix=auto; cap=${MAX_EVALUATORS:-4} ;;
        *) echo "$ME: no role $role (recworker, vmsworker, liveworker, autoworker)" >&2; continue ;;
    esac
    text=$(curl -fsS --max-time 5 "$CONSOLE$page" 2>/dev/null) || {
        echo "$ME: no answer from $CONSOLE$page — nothing started for $role" >&2
        continue                                    # the console being down is not a reason to start anything
    }
    if [ "$role" = recworker ]; then
        # its places nobody holds (`placement.places`): no offer and no labels — a spare takes a free place itself
        wanted=$(printf '%s\n' "$text" | sed -n 's/^rec_workers_needed{labels=""} \([0-9][0-9]*\)$/\1 /p')
        spare=""
        labels=""
    else
        # "<n> <label set>" per set the controller counted, only while its pass is fresh (`metrics_text`)
        wanted=$(printf '%s\n' "$text" | sed -n "s/^${prefix}_workers_needed{labels=\"\([^\"]*\)\"} \([0-9][0-9]*\)\$/\2 \1/p")
        spare=1
        labels=$(printf '%s\n' "$text" |
                 sed -n "s/^${prefix}_server_labels{server=\"$srv\",labels=\"\([^\"]*\)\",source=\"console\"} 1\$/\1/p")
        [ -n "$labels" ] || printf '%s\n' "$text" | grep -q "^${prefix}_server_labels{server=\"$srv\",labels=\"\",source=\"console\"}" \
            || labels="${LABELS:-}"                 # no row for this server in the console: what this host says
    fi
    if [ -z "$wanted" ]; then
        echo "$ME: $CONSOLE$page says no number for $role (its controller's pass is stale, or none ran) — nothing started"
        continue
    fi
    if ! template "$role"; then
        echo "$ME: no spare template for $role on $SERVER ($NAME-$role-spare@.service, or com.w2c.$NAME.$role.plist on macOS) — nothing started: a spare runs as its role's unit or not at all" >&2
        continue
    fi
    n=1
    have=0
    while [ "$n" -le "$cap" ]; do                   # the spares of this role already here count against the ceiling
        running "$role" "$n" && have=$((have + 1))
        n=$((n + 1))
    done
    room=$((cap - have))
    printf '%s\n' "$wanted" | while read -r needed set; do
        [ "$needed" -gt 0 ] || continue
        if ! covers "$set" "$labels"; then
            echo "$ME: $needed $role(s) wanted for labels '$set', which $SERVER does not reach ($labels) — left to a server that does"
            continue
        fi
        n=1
        while [ "$needed" -gt 0 ] && [ "$room" -gt 0 ] && [ "$n" -le "$cap" ]; do
            if ! running "$role" "$n"; then
                if start "$role" "$n" "$set" "$spare"; then
                    echo "$ME: started $NAME-$role-spare@$n${spare:+ for labels '$set'}"
                    needed=$((needed - 1))
                    room=$((room - 1))
                else                                # refused (polkit, systemd's start limit) or failed at once: said
                    echo "$ME: $NAME-$role-spare@$n did not start — the next number is tried" >&2
                fi
            fi
            n=$((n + 1))
        done
        [ "$needed" -eq 0 ] || echo "$ME: $needed $role(s) for labels '$set' not started — the ceiling here is $cap" >&2
    done
done
