#!/bin/sh
# install-obsd.sh — prepare the box and start the archive's engine: the platform's user and groups and the engine's,
# the layout on the data partition (/etc/w2c and /etc/vms as links into it), the directories the units mount, the
# volumes the engine owns, its unit. Run as root, from this directory or anywhere:
#   deploy/install-obsd.sh [<volume directory> ...]
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # install-obsd.sh — the box's installer: the platform's users and layout, and obsd.service
#
# **Role.** `obsd.service` runs the daemon as `vms-obsd:vms-obsd`, and nothing on a fresh box made that user, that group,
# /run/vms or the box's own volume — the unit failed with 217/USER, the units mounting /run/vms with it; on a box
# upgraded from a daemon that ran as root, the rings were root's and the daemon could not open them: the volume
# `wrong`, nothing recorded (the review's fourth pass, blocker 2). This script does once what the box needs, and
# hands the rest to systemd, which does it again at every boot:
#
# 1. `obsd.sysusers` → /etc/sysusers.d/obsd.conf and `w2c.sysusers` → /etc/sysusers.d/w2c.conf, applied: the user
#    and the group `vms-obsd` (gid 2101); the platform's user `w2c` (2100) and the groups of its clients,
#    `w2c-events` (2102), `w2c-store` (2103), `w2c-secrets` (2104).
# 2. The numbers checked: the containers run as and join them BY NUMBER (`User=2100`, `GroupAdd=2101` — a container
#    has no /etc/passwd or /etc/group of the host's), so a name made earlier with another number is a recorder the
#    daemon refuses, or a resource that cannot delete what the clients wrote. Said, not fixed — and on a box set up
#    under the course's old names (`obsd`, `vms-rec`), whose `vms-rec` still holds 2101, the old user and group are
#    named as what to remove.
# 3. THE LAYOUT (the owner's decisions, 4 October): all the platform's mutable state under /data/platform, its
#    configuration in /data/platform/etc with /etc/w2c a LINK to it, the VMS's in /data/vms/etc with /etc/vms a link
#    — on an A/B box /etc is on the slot an OS update replaces. Units and code say /etc/…, never the target. Nothing
#    is deleted on the way: a real directory at /etc/w2c or /etc/vms is MOVED into /data first (`link_etc`, the same
#    as М11's install.sh), and the course's old places too — `/data/config/w2c.env` → `/etc/w2c/w2c.env`,
#    `/data/config/vms.env` → `/etc/vms/vms.env`, `/data/secrets/*` → `/etc/w2c/secrets/`, `/data/archive` →
#    `/data/platform/events` (one rename: a writer still running writes on into the same directory). A file already
#    where one goes is kept, and the moved one put beside it as `<name>.from-config`. The old `vms.env` said
#    `ARCHIVE=/data/archive`, and the second file wins: that line is commented out and `w2c.env` given
#    `ARCHIVE=/data/platform/events` — the archive is the platform's. A ring at the old `/data/volume` is not moved
#    under a daemon: `vms.env` is told `ARCHIVE_VOLUME=file:///data/volume`, and the box records where its footage is.
#    A box with no env file yet gets the examples.
# 4. `w2c.tmpfiles` → /etc/tmpfiles.d/w2c.conf (the platform's: /data/platform and its etc/, etc/secrets, config/,
#    objects/, events/) and `vms.tmpfiles` → /etc/tmpfiles.d/vms.conf (the VMS's: /run/vms, /run/vms-obsd,
#    /run/vms-console, /data/vms and its etc/, obsd/, obsd/volume), applied. Both here because the box has no
#    installer of the platform's own (the product's is its install.sh), and a unit that mounts a directory nobody
#    made does not start. Then what is INSIDE the platform's directories, once: config/ and objects/ to the group
#    `w2c-store`, events/ to `w2c-events` — group read-write, setgid directories — if anything there is not yet (a
#    box whose processes all ran as root, umask 0022, and whose resource now is `w2c`); the key ring 0640
#    `w2c-secrets`.
# 5. WHICH VOLUMES (the review's sixth pass, minor: the script knew /data/volume and what it was told, and a volume
#    declared on another disk of this box stayed root's unless somebody remembered its path). /data/vms/obsd/volume
#    (and /data/volume, while a ring is there); each
#    directory named on the command line; and every volume DECLARED for this box — the rows `rec/volumes/*` of the
#    box's own store (`$PLATFORM_DIR/config`) that name this server and a directory. Each one found is named. A
#    cluster whose store is not a directory (М11: Nomad variables) has no rows here to read: its paths are named on
#    the command line, and the script says it found none.
# 6. THE UPGRADE, and THE DAEMON STOPPED FOR IT — only for it (the fifth pass, major; the sixth, minor). A volume is
#    handed to `vms-obsd:vms-obsd` if anything in it is not `vms-obsd`'s yet: a ring formatted by a daemon that ran as
#    root, or as the course's old user `obsd`.
#    That daemon was still writing while the volumes were handed over, and made new blocks — root's — behind the
#    `chown -R`: nothing is handed over while a daemon runs. So one that runs is stopped first — and CHECKED to be
#    down: `stop`'s failure used to be thrown away (`|| true`), and a daemon that did not stop was chowned under.
#    The unit not active and no process called `obsd`, or the script ends with 3 and nothing handed over. And when
#    nothing needs handing over, nothing is stopped: run again on a box that is in order, the script used to stop
#    and restart the daemon every time — every recording interrupted for nothing.
# 7. `obsd.service` → /etc/systemd/system when it differs from the one there, enabled, and the daemon RESTARTED when
#    the unit changed or it was stopped above; started when it is not running; left as it is otherwise. Never
#    `enable --now`: it starts a unit that is stopped and leaves a running one as it is — the old root daemon went
#    on under the old unit, its socket where the recorders no longer look, and every volume stayed `away` until
#    somebody restarted it by hand. `restart` runs the unit as it is now written. A restart of the daemon is not a
#    writer coming back to it: its writers end with it, and each recorder mounts its volume again (`away`, then
#    `remounted` — never `reattached`, which is the SAME daemon taking back a recorder whose session dropped). A new
#    BINARY in place is not this script's to notice: `systemctl restart obsd.service`.
#
# After it: the box's Quadlet units as they are written now (`/etc/containers/systemd/`), `systemctl daemon-reload`,
# and every unit restarted — a unit started before this mounts `/data/archive` and reads `/data/config`.
#
# `INSTALL_ROOT` puts the layout of step 3 under another directory — the test's sandbox; unset on a box.
# Exit codes: 0 done; 1 a user or a group exists with another number; 2 not root; 3 a running daemon would not stop.
# ================================================================================================
set -eu
[ "$(id -u)" = 0 ] || { echo "run it as root: it creates a user and writes /etc" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R="${INSTALL_ROOT:-}"
running() {                                         # the unit active, or a process called obsd whoever started it
  systemctl is-active --quiet obsd.service && return 0
  command -v pgrep >/dev/null 2>&1 && pgrep -x obsd >/dev/null 2>&1
}

# 1, 2: the users and groups, and their numbers — the containers know them by nothing else
install -D -m 0644 "$HERE/obsd.sysusers" /etc/sysusers.d/obsd.conf     # -D: a minimal box has no /etc/sysusers.d yet
install -D -m 0644 "$HERE/w2c.sysusers" /etc/sysusers.d/w2c.conf
systemd-sysusers /etc/sysusers.d/obsd.conf /etc/sysusers.d/w2c.conf

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
BAD=0
while read -r DB NAME WANT; do                      # what the units say (`User=`, `GroupAdd=`), name by name
  GOT="$(getent "$DB" "$NAME" | cut -d: -f3)"
  if [ "$GOT" != "$WANT" ]; then
    echo "$NAME has the number ${GOT:-(none)} ($DB), and the box's units say $WANT (w2c.sysusers)" >&2
    BAD=1
  fi
done <<EOF
passwd w2c 2100
group w2c 2100
group w2c-events 2102
group w2c-store 2103
group w2c-secrets 2104
EOF
[ "$BAD" = 0 ] || { echo "change them so that they agree, then run this again" >&2; exit 1; }

# 3: the layout — configuration in /data with /etc pointing there, the course's old places moved in, nothing deleted
move_file() {                                       # $1 from, $2 to: one already there is kept, the moved one beside it
  [ -e "$1" ] || return 0
  mkdir -p "$(dirname "$2")"
  if [ -e "$2" ]; then
    mv "$1" "$2.from-config"; echo "$2 was there already: $1 kept beside it, as $2.from-config"
  else
    mv "$1" "$2"; echo "moved $1 -> $2"
  fi
}
link_etc() {                                        # $1 /etc/…, $2 its home on /data (М11's install.sh does the same)
  mkdir -p "$2"
  if [ -L "$1" ]; then
    [ "$(readlink "$1")" = "$2" ] || { echo "$1 is a link to $(readlink "$1"), not $2: left as it is" >&2; return 0; }
  elif [ -d "$1" ]; then
    for f in "$1"/* "$1"/.[!.]*; do
      [ -e "$f" ] || continue
      if [ -e "$2/$(basename "$f")" ]; then mv "$f" "$2/$(basename "$f").from-etc"; else mv "$f" "$2/"; fi
    done
    rmdir "$1" && ln -s "$2" "$1" && echo "$1 was a directory: its files moved to $2, and $1 is a link to it"
  else
    mkdir -p "$(dirname "$1")"
    ln -s "$2" "$1"
  fi
}
move_file "$R/data/config/w2c.env" "$R/data/platform/etc/w2c.env"
move_file "$R/data/config/vms.env" "$R/data/vms/etc/vms.env"
for f in "$R/data/secrets"/* "$R/data/secrets"/.[!.]*; do
  [ -e "$f" ] || continue
  move_file "$f" "$R/data/platform/etc/secrets/$(basename "$f")"
done
for d in "$R/data/config" "$R/data/secrets"; do               # emptied: gone; anything else left in it: said
  [ -d "$d" ] || continue
  rmdir "$d" 2>/dev/null || echo "$d is not empty: left as it is (nothing of the box's reads it any more)" >&2
done
link_etc "$R/etc/w2c" "$R/data/platform/etc"
link_etc "$R/etc/vms" "$R/data/vms/etc"
[ -f "$R/etc/w2c/w2c.env" ] || install -m 0644 "$HERE/w2c.env.example" "$R/etc/w2c/w2c.env"
[ -f "$R/etc/vms/vms.env" ] || install -m 0644 "$HERE/vms.env.example" "$R/etc/vms/vms.env"
# The archive is the platform's: its root is a key of w2c.env, and an old vms.env — read second, so it wins — must not
# keep saying /data/archive, where no unit mounts anything any more.
if [ -f "$R/etc/vms/vms.env" ] && grep -q '^ARCHIVE=' "$R/etc/vms/vms.env"; then
  OLD="$(sed -n 's/^ARCHIVE=//p' "$R/etc/vms/vms.env" | tail -n 1)"
  sed 's/^ARCHIVE=/# the events archive is the platform'"'"'s: ARCHIVE is in \/etc\/w2c\/w2c.env (install-obsd.sh) — ARCHIVE=/' \
    "$R/etc/vms/vms.env" > "$R/etc/vms/vms.env.new" && cat "$R/etc/vms/vms.env.new" > "$R/etc/vms/vms.env"
  rm -f "$R/etc/vms/vms.env.new"
  echo "vms.env said ARCHIVE=$OLD: commented out — the events archive is /data/platform/events, set in w2c.env"
  [ "$OLD" = /data/archive ] || echo "$OLD is not /data/archive: its buckets are not moved by this script, move them by hand" >&2
fi
if [ -f "$R/etc/w2c/w2c.env" ] && ! grep -q '^ARCHIVE=' "$R/etc/w2c/w2c.env"; then
  printf '%s\n' "ARCHIVE=/data/platform/events" >> "$R/etc/w2c/w2c.env"
fi
if [ -d "$R/data/archive" ] && [ ! -L "$R/data/archive" ]; then
  if [ ! -e "$R/data/platform/events" ] || rmdir "$R/data/platform/events" 2>/dev/null; then
    mkdir -p "$R/data/platform"
    mv "$R/data/archive" "$R/data/platform/events"                 # one rename, on one file system
    echo "moved $R/data/archive -> $R/data/platform/events: the events archive is the platform's"
  else
    echo "both $R/data/archive and a non-empty $R/data/platform/events: nothing moved — merge them by hand" >&2
  fi
fi
OWN="$R/data/vms/obsd/volume"                                      # the box's own volume (`vms/config.py`, OWN_VOLUME)
if [ -d "$R/data/volume" ] && [ -n "$(ls -A "$R/data/volume" 2>/dev/null)" ] \
   && ! grep -q '^ARCHIVE_VOLUME=' "$R/etc/vms/vms.env" 2>/dev/null; then
  printf '%s\n' "# install-obsd.sh: this box's ring was formatted at /data/volume, before volumes were under /data/vms/obsd —" \
    "# kept where it is, with its footage (move it by hand, the daemon stopped, and drop this line)" \
    "ARCHIVE_VOLUME=file:///data/volume" >> "$R/etc/vms/vms.env"
  echo "the box's ring is at /data/volume: kept there, ARCHIVE_VOLUME=file:///data/volume written to /etc/vms/vms.env"
fi

# 4: the directories, and what is inside the platform's handed to the groups of their clients — once
install -D -m 0644 "$HERE/w2c.tmpfiles" /etc/tmpfiles.d/w2c.conf
install -D -m 0644 "$HERE/vms.tmpfiles" /etc/tmpfiles.d/vms.conf
systemd-tmpfiles --create /etc/tmpfiles.d/w2c.conf /etc/tmpfiles.d/vms.conf
hand_to_group() {                                   # $1 a directory, $2 the group whose clients write there
  [ -d "$1" ] || return 0
  [ -n "$(find "$1" \( ! -group "$2" -o -type d ! -perm -2070 -o -type f ! -perm -0060 \) -print -quit)" ] || return 0
  echo "$1: handing it to the group $2 (written when every process of the box ran as root)"
  chgrp -R "$2" "$1"
  chmod -R g+rwX,o-rwx "$1"
  find "$1" -type d -exec chmod g+s {} +
}
hand_to_group "$R/data/platform/config" w2c-store
hand_to_group "$R/data/platform/objects" w2c-store
hand_to_group "$R/data/platform/events" w2c-events
KEY="$R/data/platform/etc/secrets/platform.key"
if [ -f "$KEY" ]; then
  chgrp w2c-secrets "$KEY"; chmod 0640 "$KEY"      # read by the console, the holders, the recorders: members of it
else
  echo "no /etc/w2c/secrets/platform.key: secrets are stored in the clear until one is made (python3 -m w2cplatform.sealing new /etc/w2c/secrets/platform.key)" >&2
fi

# 5: the volumes — the box's own, the ones named, the ones declared for this box in its own store
VOLS="$(mktemp)"; HAND="$(mktemp)"
trap 'rm -f "$VOLS" "$HAND"' EXIT
printf '%s\n' "$OWN" "$@" > "$VOLS"
if grep -q '^ARCHIVE_VOLUME=file:///data/volume$' "$R/etc/vms/vms.env" 2>/dev/null; then
  printf '%s\n' "$R/data/volume" >> "$VOLS"                         # the old ring, kept where it is (step 3)
fi
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
[ "$FOUND" -gt 0 ] || echo "no volume declared for $SERVER in $STORE: only the box's own and the paths named here are looked at"

# 6: what is not vms-obsd's yet — and the daemon stopped for the handing over, only for it, and seen to be down
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

# 7: the unit as written now, and the daemon restarted only when something changed under it
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
echo "now the box's units as written in deploy/ (/etc/containers/systemd/), systemctl daemon-reload, and each restarted"
