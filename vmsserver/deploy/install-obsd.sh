#!/bin/sh
# install-obsd.sh — prepare the box for the archive's engine and start it: its user and group, the directories
# the units mount, the volumes it owns, the unit. Run as root, from this directory or anywhere:
#   deploy/install-obsd.sh [<volume directory> ...]
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # install-obsd.sh — the box's half of obsd.service
#
# **Role.** `obsd.service` runs the daemon as `vms-obsd:vms-obsd`, and nothing on a fresh box made that user, that group,
# /run/vms or the box's own volume — the unit failed with 217/USER, the units mounting /run/vms with it; on a box
# upgraded from a daemon that ran as root, the rings were root's and the daemon could not open them: the volume
# `wrong`, nothing recorded (the review's fourth pass, blocker 2). This script does once what the box needs, and
# hands the rest to systemd, which does it again at every boot:
#
# 1. `obsd.sysusers` → /etc/sysusers.d/obsd.conf, applied: the user and the group `vms-obsd`, the group with gid 2101.
# 2. The gid checked: the recorders join the group BY NUMBER (`GroupAdd=2101` — a container has no /etc/group of
#    the host's), so a `vms-obsd` made earlier with another number is a recorder the daemon refuses. Said, not fixed
#    — and on a box set up under the course's old names (`obsd`, `vms-rec`), whose `vms-rec` still holds 2101, the
#    old user and group are named as what to remove.
# 3. `w2c.tmpfiles` → /etc/tmpfiles.d/w2c.conf (the platform's: /data/platform, /data/secrets) and `vms.tmpfiles` →
#    /etc/tmpfiles.d/vms.conf (the VMS's: /run/vms, /run/vms-obsd, /run/vms-console, /data/volume), applied. Both
#    here because the box has no installer of the platform's own (the product's is its install.sh), and a unit that
#    mounts a directory nobody made does not start.
# 4. WHICH VOLUMES (the review's sixth pass, minor: the script knew /data/volume and what it was told, and a volume
#    declared on another disk of this box stayed root's unless somebody remembered its path). /data/volume; each
#    directory named on the command line; and every volume DECLARED for this box — the rows `rec/volumes/*` of the
#    box's own store (`$PLATFORM_DIR/config`) that name this server and a directory. Each one found is named. A
#    cluster whose store is not a directory (М11: Nomad variables) has no rows here to read: its paths are named on
#    the command line, and the script says it found none.
# 5. THE UPGRADE, and THE DAEMON STOPPED FOR IT — only for it (the fifth pass, major; the sixth, minor). A volume is
#    handed to `vms-obsd:vms-obsd` if anything in it is not `vms-obsd`'s yet: a ring formatted by a daemon that ran as
#    root, or as the course's old user `obsd`.
#    That daemon was still writing while the volumes were handed over, and made new blocks — root's — behind the
#    `chown -R`: nothing is handed over while a daemon runs. So one that runs is stopped first — and CHECKED to be
#    down: `stop`'s failure used to be thrown away (`|| true`), and a daemon that did not stop was chowned under.
#    The unit not active and no process called `obsd`, or the script ends with 3 and nothing handed over. And when
#    nothing needs handing over, nothing is stopped: run again on a box that is in order, the script used to stop
#    and restart the daemon every time — every recording interrupted for nothing.
# 6. `obsd.service` → /etc/systemd/system when it differs from the one there, enabled, and the daemon RESTARTED when
#    the unit changed or it was stopped above; started when it is not running; left as it is otherwise. Never
#    `enable --now`: it starts a unit that is stopped and leaves a running one as it is — the old root daemon went
#    on under the old unit, its socket where the recorders no longer look, and every volume stayed `away` until
#    somebody restarted it by hand. `restart` runs the unit as it is now written. A restart of the daemon is not a
#    writer coming back to it: its writers end with it, and each recorder mounts its volume again (`away`, then
#    `remounted` — never `reattached`, which is the SAME daemon taking back a recorder whose session dropped). A new
#    BINARY in place is not this script's to notice: `systemctl restart obsd.service`.
#
# Exit codes: 0 done; 1 the group exists with another gid; 2 not root; 3 a running daemon would not stop.
# ================================================================================================
set -eu
[ "$(id -u)" = 0 ] || { echo "run it as root: it creates a user and writes /etc" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
running() {                                         # the unit active, or a process called obsd whoever started it
  systemctl is-active --quiet obsd.service && return 0
  command -v pgrep >/dev/null 2>&1 && pgrep -x obsd >/dev/null 2>&1
}

install -D -m 0644 "$HERE/obsd.sysusers" /etc/sysusers.d/obsd.conf     # -D: a minimal box has no /etc/sysusers.d yet
systemd-sysusers /etc/sysusers.d/obsd.conf

GID="$(getent group vms-obsd | cut -d: -f3)"
if [ "$GID" != 2101 ]; then
  echo "the group vms-obsd has gid $GID, and the recorders join 2101 (GroupAdd=2101 in recworker@.container):" >&2
  # a box set up under the course's old names: its `vms-rec` holds 2101, and sysusers gave `vms-obsd` another number
  if getent group vms-rec >/dev/null 2>&1; then
    echo "the old group vms-rec still holds a number: stop obsd, 'userdel obsd; groupdel vms-rec', run this again" >&2
  fi
  echo "change one of them so that they agree, then run this again" >&2
  exit 1
fi

install -D -m 0644 "$HERE/w2c.tmpfiles" /etc/tmpfiles.d/w2c.conf
install -D -m 0644 "$HERE/vms.tmpfiles" /etc/tmpfiles.d/vms.conf
systemd-tmpfiles --create /etc/tmpfiles.d/w2c.conf /etc/tmpfiles.d/vms.conf

# 4: the volumes — the box's own, the ones named, the ones declared for this box in its own store
VOLS="$(mktemp)"; HAND="$(mktemp)"
trap 'rm -f "$VOLS" "$HAND"' EXIT
printf '%s\n' /data/volume "$@" > "$VOLS"
STORE="${PLATFORM_DIR:-/data/platform}/config/vars"
SERVER="${SERVER_NAME:-$(hostname)}"
FOUND=0
for ROW in "$STORE"/rec%2Fvolumes%2F*.json; do
  [ -f "$ROW" ] || continue
  grep -q "\"server\": \"$SERVER\"" "$ROW" || continue          # another box's disk, or an address any box serves
  DIR="$(sed -n 's/.*"url": "\([^"]*\)".*/\1/p' "$ROW")"
  DIR="${DIR#file://}"
  case "$DIR" in /*) ;; *) continue ;; esac                      # a directory on this box, not a bucket
  FOUND=$((FOUND + 1))
  echo "declared for $SERVER: $DIR ($(basename "$ROW" .json | sed 's/.*%2F//'))"
  grep -qxF "$DIR" "$VOLS" || printf '%s\n' "$DIR" >> "$VOLS"
done
[ "$FOUND" -gt 0 ] || echo "no volume declared for $SERVER in $STORE: only /data/volume and the paths named here are looked at"

# 5: what is not vms-obsd's yet — and the daemon stopped for the handing over, only for it, and seen to be down
while IFS= read -r VOL; do
  mkdir -p "$VOL"
  if [ -n "$(find "$VOL" \( ! -user vms-obsd -o ! -group vms-obsd \) -print -quit)" ]; then
    printf '%s\n' "$VOL" >> "$HAND"
  fi
done < "$VOLS"
STOPPED=no
if [ -s "$HAND" ]; then
  if running; then
    echo "stopping obsd: nothing writes while volumes change hands"
    systemctl stop obsd.service || echo "systemctl stop obsd.service failed" >&2
    STOPPED=yes
  fi
  if running; then
    echo "obsd is still running — the unit would not stop, or a daemon was started by hand: NOTHING was handed over." >&2
    echo "stop it, see that no process called obsd is left, and run this again" >&2
    exit 3
  fi
  while IFS= read -r VOL; do
    echo "$VOL: handing it to vms-obsd:vms-obsd (formatted when the daemon ran as another user)"
    chown -R vms-obsd:vms-obsd "$VOL"
  done < "$HAND"
fi
while IFS= read -r VOL; do
  chmod 0750 "$VOL"
done < "$VOLS"

# 6: the unit as written now, and the daemon restarted only when something changed under it
CHANGED=no
if ! cmp -s "$HERE/obsd.service" /etc/systemd/system/obsd.service; then
  install -m 0644 "$HERE/obsd.service" /etc/systemd/system/obsd.service
  systemctl daemon-reload
  CHANGED=yes
fi
systemctl enable obsd.service
if [ "$CHANGED" = yes ] || [ "$STOPPED" = yes ]; then
  systemctl restart obsd.service                   # a running one is not left as it was
elif ! systemctl is-active --quiet obsd.service; then
  systemctl start obsd.service
else
  echo "nothing changed: the running daemon is left as it is, and no recording is interrupted"
fi
echo "obsd: $(systemctl is-active obsd.service), socket /run/vms-obsd/obsd.sock"
