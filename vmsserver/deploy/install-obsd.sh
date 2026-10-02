#!/bin/sh
# install-obsd.sh — prepare the box for the archive's engine and start it: its user and group, the directories
# the units mount, the volumes it owns, the unit. Run as root, from this directory or anywhere:
#   deploy/install-obsd.sh [<volume directory> ...]
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # install-obsd.sh — the box's half of obsd.service
#
# **Role.** `obsd.service` runs the daemon as `obsd:vms-rec`, and nothing on a fresh box made that user, that group,
# /run/vms or the box's own volume — the unit failed with 217/USER, the units mounting /run/vms with it; on a box
# upgraded from a daemon that ran as root, the rings were root's and the daemon could not open them: the volume
# `wrong`, nothing recorded (the review's fourth pass, blocker 2). This script does once what the box needs, and
# hands the rest to systemd, which does it again at every boot:
#
# 1. `obsd.sysusers` → /etc/sysusers.d/obsd.conf, applied: the user `obsd`, the group `vms-rec` with gid 2101.
# 2. The gid checked: the recorders join the group BY NUMBER (`GroupAdd=2101` — a container has no /etc/group of
#    the host's), so a `vms-rec` made earlier with another number is a recorder the daemon refuses. Said, not fixed.
# 3. `vms.tmpfiles` → /etc/tmpfiles.d/vms.conf, applied: /run/vms, /run/obsd, /data/volume.
# 4. THE DAEMON STOPPED, if one runs (the review's fifth pass, major). On a box upgraded from a daemon that ran as
#    root, that daemon was still writing while the volumes were handed over: it made new blocks — root's — behind
#    the `chown -R`, and the new unit's daemon then could not open them. Nothing is handed over while it runs.
# 5. THE UPGRADE: every volume directory — /data/volume, and each one named on the command line (a declared local
#    volume on another disk of this box) — made if missing, and handed to `obsd:vms-rec` if anything in it is not
#    `obsd`'s yet: a ring formatted by a daemon that ran as root. Once; `chown -R` over a ring of millions of blocks
#    is not something to do at every boot.
# 6. `obsd.service` → /etc/systemd/system, enabled, and RESTARTED — before any recorder (`After=obsd.service` in
#    theirs). `enable --now` starts a unit that is stopped and leaves a running one as it is: the old root daemon
#    went on under the old unit, its socket where the recorders no longer look, and every volume stayed `away` until
#    somebody restarted it by hand. `restart` runs the unit as it is now written, whatever ran before. Running the
#    script again restarts the daemon again: the recorders wait it out (`away`, then `reattached`).
#
# Exit codes: 0 done; 1 the group exists with another gid; 2 not root.
# ================================================================================================
set -eu
[ "$(id -u)" = 0 ] || { echo "run it as root: it creates a user and writes /etc" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"

install -D -m 0644 "$HERE/obsd.sysusers" /etc/sysusers.d/obsd.conf     # -D: a minimal box has no /etc/sysusers.d yet
systemd-sysusers /etc/sysusers.d/obsd.conf

GID="$(getent group vms-rec | cut -d: -f3)"
if [ "$GID" != 2101 ]; then
  echo "the group vms-rec has gid $GID, and the recorders join 2101 (GroupAdd=2101 in recworker@.container):" >&2
  echo "change one of them so that they agree, then run this again" >&2
  exit 1
fi

install -D -m 0644 "$HERE/vms.tmpfiles" /etc/tmpfiles.d/vms.conf
systemd-tmpfiles --create /etc/tmpfiles.d/vms.conf

systemctl stop obsd.service 2>/dev/null || true    # 4: nothing writes while the volumes change hands (a new box: no unit yet)

for VOL in /data/volume "$@"; do
  mkdir -p "$VOL"
  if [ -n "$(find "$VOL" \( ! -user obsd -o ! -group vms-rec \) -print -quit)" ]; then
    echo "$VOL: handing it to obsd:vms-rec (formatted when the daemon ran as another user)"
    chown -R obsd:vms-rec "$VOL"
  fi
  chmod 0750 "$VOL"
done

install -m 0644 "$HERE/obsd.service" /etc/systemd/system/obsd.service
systemctl daemon-reload
systemctl enable obsd.service
systemctl restart obsd.service                     # 6: the unit as written now — a running one is not left as it was
echo "obsd: $(systemctl is-active obsd.service), socket /run/obsd/obsd.sock"
