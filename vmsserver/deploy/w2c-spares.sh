#!/bin/sh
# w2c-spares.sh — start spare workers for what the console says is missing. Never stops one.
#
#   w2c-spares.sh [role ...]        roles as arguments, else $SPARES_ROLES (spaces or commas), else recworker
#
#   role         the console's number                                   this server's ceiling
#   recworker    rec_recorders_needed           on /rec/metrics         MAX_RECORDERS  (8)
#   vmsworker    vms_workers_needed{labels}     on /metrics             MAX_WORKERS    (4)
#   liveworker   live_workers_needed{labels}    on /live/metrics        MAX_GATEWAYS   (4)
#   autoworker   auto_workers_needed{labels}    on /auto/metrics        MAX_EVALUATORS (4)
#
# It runs on the HOST, under root, from `w2c-spares[-<role>].timer` — and that placement is the whole point of the
# file. Starting a process means talking to systemd (launchd) as root; a console that could do it would be a console
# holding root on its own machine, and "the platform does not start processes" would be a sentence with an exception
# in it. So the controller publishes NUMBERS and OFFERS (`SpecController.offer_spares`) and this script, which the
# operator installed deliberately, does the starting.
#
# The rules it follows:
#
#   1. It reads numbers, never a command. Running a string that arrived over HTTP as root is remote code execution
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
#   Linux   systemd-run --unit vms-<role>-spare-<n> --setenv SPARE_FOR=<set> $SPARES_RUN <verb>
#   macOS   nohup env SPARE_FOR=<set> $SPARES_RUN <verb>, its pid in $SPARES_DIR/vms-<role>-spare-<n>.pid
set -eu

ME="${0##*/}"
CONSOLE="${CONSOLE:-http://127.0.0.1:8080}"
SERVER="${SERVER_NAME:-$(hostname -s 2>/dev/null || hostname)}"
# THE PLATFORM'S NAMES — spelled here and nowhere else below, so a rename is these lines: what a role's unit runs
# (`<SPARES_RUN> <verb>`), the two environment files every unit reads (handed to a spare too: the platform's, then
# the VMS's — a name in both is the second's), and where the macOS spares keep their pids and logs. The defaults are
# the product's layout (`/opt/w2c`, `/etc/w2c/w2c.env`, `/etc/vms/vms.env`) — the course's box's too, /etc/w2c and
# /etc/vms being links into its data partition; `SPARES_RUN` it sets in `w2c.env`. A spare itself is a process of a VMS subsystem, and keeps
# the subsystem's names: the unit `vms-<role>-spare-<n>`, the group `vms-<role>` of its role's store socket.
SPARES_RUN="${SPARES_RUN:-/opt/w2c/bin/w2c-run.sh}"
W2C_ENV="${W2C_ENV:-/etc/w2c/w2c.env}"
ENV_FILE="${ENV_FILE:-/etc/vms/vms.env}"
SPARES_DIR="${SPARES_DIR:-/var/run/w2c-spares}"
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
        systemctl is-active --quiet "$NAME-$1-spare-$2"
    else
        [ -f "$SPARES_DIR/$NAME-$1-spare-$2.pid" ] && kill -0 "$(cat "$SPARES_DIR/$NAME-$1-spare-$2.pid")" 2>/dev/null
    fi
}

# Start spare $2 of role $1, verb $3, for the label set $4 — with no SPARE_FOR when $5 is empty (a recorder).
start() {                                           # sh has no locals: the arguments, by number
    if [ "$linux" = 1 ]; then
        systemctl reset-failed "$NAME-$1-spare-$2" >/dev/null 2>&1 || true      # a spare that ended leaves its name behind
        group=""
        getent group "$NAME-$1" >/dev/null 2>&1 && group="--property=SupplementaryGroups=$NAME-$1"   # its role's store socket
        if [ -n "$5" ]; then
            # shellcheck disable=SC2086
            systemd-run --unit "$NAME-$1-spare-$2" --property=EnvironmentFile=-"$W2C_ENV" \
                --property=EnvironmentFile=-"$ENV_FILE" $group --setenv SPARE_FOR="$4" "$SPARES_RUN" "$3"
        else
            # shellcheck disable=SC2086
            systemd-run --unit "$NAME-$1-spare-$2" --property=EnvironmentFile=-"$W2C_ENV" \
                --property=EnvironmentFile=-"$ENV_FILE" $group "$SPARES_RUN" "$3"
        fi
    else
        mkdir -p "$SPARES_DIR"
        if [ -n "$5" ]; then
            nohup env SPARE_FOR="$4" "$SPARES_RUN" "$3" >>"$SPARES_DIR/$NAME-$1-spare-$2.log" 2>&1 &
        else
            nohup "$SPARES_RUN" "$3" >>"$SPARES_DIR/$NAME-$1-spare-$2.log" 2>&1 &
        fi
        echo $! >"$SPARES_DIR/$NAME-$1-spare-$2.pid"
    fi
}

if command -v systemd-run >/dev/null 2>&1; then
    linux=1
elif [ "$(uname)" = Darwin ]; then
    linux=0
else
    echo "$ME: neither systemd-run nor macOS here — nothing started" >&2
    exit 0
fi
srv=$(printf '%s' "$SERVER" | sed 's/[.]/\\./g')

for role in $roles; do
    case "$role" in
        recworker)  page=/rec/metrics;  prefix=rec;  cap=${MAX_RECORDERS:-8};  verb=recorder ;;
        vmsworker)  page=/metrics;      prefix=vms;  cap=${MAX_WORKERS:-4};    verb=worker ;;
        liveworker) page=/live/metrics; prefix=live; cap=${MAX_GATEWAYS:-4};   verb=gateway ;;
        autoworker) page=/auto/metrics; prefix=auto; cap=${MAX_EVALUATORS:-4}; verb=autoworker ;;
        *) echo "$ME: no role $role (recworker, vmsworker, liveworker, autoworker)" >&2; continue ;;
    esac
    text=$(curl -fsS --max-time 5 "$CONSOLE$page" 2>/dev/null) || {
        echo "$ME: no answer from $CONSOLE$page — nothing started for $role" >&2
        continue                                    # the console being down is not a reason to start anything
    }
    if [ "$role" = recworker ]; then
        wanted=$(printf '%s\n' "$text" | sed -n 's/^rec_recorders_needed \([0-9][0-9]*\)$/\1 /p')
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
                if start "$role" "$n" "$verb" "$set" "$spare"; then
                    echo "$ME: started $NAME-$role-spare-$n${spare:+ for labels '$set'}"
                    needed=$((needed - 1))
                    room=$((room - 1))
                fi
            fi
            n=$((n + 1))
        done
        [ "$needed" -eq 0 ] || echo "$ME: $needed $role(s) for labels '$set' not started — the ceiling here is $cap" >&2
    done
done
