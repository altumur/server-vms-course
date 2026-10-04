#!/bin/sh
# w2c-run.sh — what every unit of a cluster server runs: `ExecStart=/opt/w2c/bin/w2c-run.sh <program>` (systemd),
# `ProgramArguments` of the same in a plist (launchd), `$SPARES_RUN <verb>` in `w2c-spares.sh`.
#
#   w2c-run.sh configstore                  this server's member of the store's raft group, a socket per role
#   w2c-run.sh worker|recorder|controller|reccontroller|console|resource      python3 -m cluster <verb>
#   w2c-run.sh rights                       print the rights file generated from the spec
#   w2c-run.sh spares <role>...             a box on macOS: `w2c-spares.sh` with the box's two files read (a Linux
#                                           server's timers give it them by `EnvironmentFile=`)
#
# The environment comes from two files, the platform's and the subsystem's (the product's split):
#
#   /etc/w2c/w2c.env    PLATFORM_DIR, SERVER_NAME, BOX_ID, LABELS, the store's addresses (CONFIGSTORE_*), secrets
#   /etc/vms/vms.env    the VMS subsystem's settings: CAPACITY, ARCHIVE, ports, budgets
#
# read here — not by `EnvironmentFile=` — so a launchd plist, a spare started from its template and a person at a
# shell all get the same. What the unit itself said WINS: a line of a file sets a name only when the unit did not
# (a unit's `PLATFORM_STORE=configstore:///run/configstore/<role>.sock` and `WORKER_NAME=w-%l-1` are the unit's,
# never a file's). A line is `NAME=value`; `#` starts a comment; nothing in the files is run as a command.
#
# A SPARE'S SET is the one thing its own file says, and the only thing read from it (the product's cross-check, 4 Oct).
# A spare's template names that file (`Environment=SPARE_FILE=/run/w2c-spares/%n.env`, written by `w2c-spares.sh`
# under its own user); it was `EnvironmentFile=` before, and whoever could write the file could set ANY variable —
# `LD_PRELOAD`, `PYTHONPATH` — in a process that holds the role's key and groups. Here only its FIRST line is read,
# and it must be `SPARE_FOR=<set>` — what `w2c-spares.sh` writes, and nothing after it is looked at (the thirteenth
# review, minor: the first such line anywhere in the file was taken) — checked against the labels' alphabet
# (`spec.LABEL_WORD`, comma-joined; empty is the empty set); another first line, or a set outside the alphabet: the
# spare does not start (exit 2, which its template does not restart). Neither name is taken from the two shared files:
# a regular unit never becomes a spare by a line there.
#
# WHAT IT WRITES IS ITS GROUP'S (the thirteenth review, major 13): `umask 0007` before anything runs. A unit says
# `UMask=0007`, but Nomad's `raw_exec` (the appendix, `deploy/nomad/`) hands on the agent's 0022 — the events
# archive's buckets came out 2755 `vms:w2c-events`, the resource (`w2c`) could not delete them, and its retention
# stopped. The archive and the objects are setgid directories shared by a group; this makes it so however it was run.
#
# A BOX ON macOS (`install.sh --box <dir>`, the thirteenth review, major 15): there is no /data and no /etc/w2c there,
# and everything is under the box. A plist says `W2C_BOX=<dir>`, and the defaults below are the box's: the code and
# this runner, `w2c.env`, `vms.env` and `configstore-rights.json` in it, `tls/` beside them, the store's journal and its
# sockets under `state/`.
set -eu
umask 0007

BOX="${W2C_BOX:-}"
W2C_ENV="${W2C_ENV:-${BOX:+$BOX/w2c.env}}"; W2C_ENV="${W2C_ENV:-/etc/w2c/w2c.env}"
VMS_ENV="${VMS_ENV:-${BOX:+$BOX/vms.env}}"; VMS_ENV="${VMS_ENV:-/etc/vms/vms.env}"
W2C_HOME="${W2C_HOME:-${BOX:-/opt/w2c}}"    # vmsserver/ and clustervms/, as `install.sh` copied them

load() {
    [ -r "$1" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in ''|'#'*) continue ;; esac
        name=${line%%=*}
        case "$name" in *[!A-Za-z0-9_]*|[0-9]*|''|SPARE_FOR|SPARE_FILE) continue ;; esac
        eval "set=\${$name+x}"
        # shellcheck disable=SC2154
        [ -n "$set" ] && continue                       # the unit said it
        export "$name=${line#*=}"
    done <"$1"
}
load "$W2C_ENV"
load "$VMS_ENV"

# Whether $1 is a label set as offers say it: words of `spec.LABEL_WORD` (a letter or digit, then up to 63 of letters,
# digits, `_.:-`) joined by single commas, or nothing. The letters spelled out, not `A-Z`: a range is the locale's, and
# in some a Cyrillic letter falls inside it.
label_set() {
    [ -z "$1" ] && return 0
    case "$1" in *[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:,-]*|,*|*,|*,,*) return 1 ;; esac
    old_ifs=$IFS; IFS=,
    for word in $1; do
        case "$word" in [ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789]*) ;; *) IFS=$old_ifs; return 1 ;; esac
        [ "${#word}" -le 64 ] || { IFS=$old_ifs; return 1; }
    done
    IFS=$old_ifs
}
if [ -n "${SPARE_FILE:-}" ]; then
    said=no
    line=
    if [ -r "$SPARE_FILE" ]; then
        IFS= read -r line <"$SPARE_FILE" || true          # the first line, and only it
        case "$line" in SPARE_FOR=*) spare=${line#SPARE_FOR=}; said=yes ;; esac
    fi
    if [ "$said" != yes ]; then
        echo "w2c-run.sh: the first line of $SPARE_FILE is not SPARE_FOR=<set> — a spare whose set is not said does not start" >&2
        exit 2
    fi
    if ! label_set "$spare"; then
        echo "w2c-run.sh: SPARE_FOR in $SPARE_FILE is not a label set (letters, digits, _.:- in words joined by commas) — not started" >&2
        exit 2
    fi
    export SPARE_FOR="$spare"
fi

export PYTHONPATH="$W2C_HOME/clustervms:$W2C_HOME/vmsserver${PYTHONPATH:+:$PYTHONPATH}"
export VMSSERVER_PATH="$W2C_HOME/vmsserver"
PYTHON="${PYTHON:-python3}"

program="${1:?w2c-run.sh configstore | worker | recorder | controller | reccontroller | console | resource | rights | spares}"
shift
case "$program" in
    configstore)
        # The daemon's flags from the platform's file. `-bootstrap` on the first server of a cluster (CONFIGSTORE_JOIN
        # empty), `-join <member>` on every other; both count only the first time — a daemon taken into a group starts
        # from its journal, so systemd restarting it with the same flags just brings it back.
        start="-bootstrap"
        [ -n "${CONFIGSTORE_JOIN:-}" ] && start="-join $CONFIGSTORE_JOIN"
        if [ -n "$BOX" ]; then                          # a box on macOS: its own places (`install.sh --box`)
            : "${CONFIGSTORE_DIR:=$BOX/state/configstore}" "${CONFIGSTORE_SOCKETS:=$BOX/state/run/configstore}"
            : "${CONFIGSTORE_RIGHTS:=$BOX/configstore-rights.json}" "${W2C_TLS:=$BOX/tls}"
        fi
        # shellcheck disable=SC2086
        exec "$PYTHON" -m w2cplatform.configstore -id "${SERVER_NAME:?SERVER_NAME in $W2C_ENV}" \
            -dir "${CONFIGSTORE_DIR:-/data/platform/configstore}" -raft "${CONFIGSTORE_RAFT:?CONFIGSTORE_RAFT in $W2C_ENV}" \
            -api "${CONFIGSTORE_API:?CONFIGSTORE_API in $W2C_ENV}" -sockets "${CONFIGSTORE_SOCKETS:-/run/configstore}" \
            -rights "${CONFIGSTORE_RIGHTS:-/etc/w2c/configstore-rights.json}" -tls "${W2C_TLS:-/etc/w2c/tls}" \
            -tuning "${CONFIGSTORE_TUNING:-lan}" $start "$@" ;;
    worker|recorder|controller|reccontroller|console|resource|rights)
        exec "$PYTHON" -m cluster "$program" "$@" ;;
    spares)
        exec sh "$W2C_HOME/bin/w2c-spares.sh" "$@" ;;
    *)
        echo "w2c-run.sh: no such program: $program" >&2
        exit 2 ;;
esac
