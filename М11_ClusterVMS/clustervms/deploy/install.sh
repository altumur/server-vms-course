#!/bin/sh
# install.sh — make this machine a server of the cluster: the code, the users, the store's rights, the units.
#
#   deploy/install.sh [--spares]                as root, on every server, from a checkout of the course
#
#   --spares   also `w2c-spares.sh` and its timers (М10's `vmsserver/deploy/`): every minute it reads the console's
#              numbers and starts the spares this server can serve — never stops one (lesson 4) — each from its role's
#              template (`vms-vmsworker-spare@.service`, `vms-recworker-spare@.service`; macOS: the role's plist).
#              On Linux it runs as `w2c-spares` (`w2c-cluster.sysusers`), and the polkit rule `w2c-spares.rules` lets
#              that user `systemctl start` those templates' instances and nothing else
#
# Both: /etc/w2c -> /data/platform/etc and /etc/vms -> /data/vms/etc (mutable configuration on the data partition).
# Linux (systemd): /opt/w2c/{vmsserver,clustervms,bin/w2c-run.sh}; `w2c-cluster.sysusers` and `.tmpfiles`; the archive's
# engine by М10's own installer (`install-obsd.sh`), its unit aliased `vms-obsd.service`; the rights file
# `/etc/w2c/configstore-rights.json` (checked against the spec first: a stale file is refused, not installed); the two
# env files from their examples when absent (never overwritten); the units, enabled and started — `configstore` first.
# macOS (launchd): the same code and files; `deploy/launchd/*.plist` into /Library/LaunchDaemons with this host's
# name in place of @HOST@, bootstrapped.
#
# What it does NOT do: make the certificates. `/etc/w2c/tls` is the installation's CA and this server's bundle
# (`vmsserver/deploy/w2c-ca.sh issue <server> configstore`), made once on the operator's machine and copied here; the
# daemon refuses its -api door without it. And it starts no store group: the first server's w2c.env has no
# CONFIGSTORE_JOIN (a group of one), every other's names a member (`srv-a@10.0.0.1:8300`) — lesson 2.
set -eu
[ "$(id -u)" = 0 ] || { echo "run it as root: it creates users and writes /etc and /opt" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"                 # clustervms/deploy
CLUSTERVMS="$(dirname "$HERE")"
VMSSERVER="$(cd "$CLUSTERVMS/../../vmsserver" && pwd)"
W2C_HOME=/opt/w2c
SPARES=no
for a in "$@"; do
  case "$a" in
    --spares) SPARES=yes ;;
    *) echo "install.sh [--spares]" >&2; exit 2 ;;
  esac
done

UNITS="configstore w2c-resource vms-console vms-vmscontroller vms-reccontroller vms-vmsworker vms-recworker"
# A spare is its role's unit but the name (the twelfth review, blocker 6): installed with the spares, never enabled —
# `w2c-spares.sh` starts `vms-<role>-spare@<n>`.
SPARE_UNITS="vms-vmsworker-spare@ vms-recworker-spare@"

# -- the code -----------------------------------------------------------------------------------------------------
mkdir -p "$W2C_HOME/bin"
rm -rf "$W2C_HOME/vmsserver.new" "$W2C_HOME/clustervms.new"
cp -R "$VMSSERVER" "$W2C_HOME/vmsserver.new"
cp -R "$CLUSTERVMS" "$W2C_HOME/clustervms.new"
for d in vmsserver clustervms; do                     # a whole tree swapped in, never a half-copied one
  rm -rf "$W2C_HOME/$d.old"; [ -d "$W2C_HOME/$d" ] && mv "$W2C_HOME/$d" "$W2C_HOME/$d.old"
  mv "$W2C_HOME/$d.new" "$W2C_HOME/$d"
done
rm -f "$W2C_HOME/bin/w2c-run.sh"                       # rm + cp, never cp over a running script
cp "$HERE/w2c-run.sh" "$W2C_HOME/bin/w2c-run.sh"; chmod 0755 "$W2C_HOME/bin/w2c-run.sh"

# -- the rights, checked against the spec ---------------------------------------------------------------------------
W2C_HOME="$W2C_HOME" "$W2C_HOME/bin/w2c-run.sh" rights --check "$HERE/configstore-rights.json" \
  || { echo "deploy/configstore-rights.json is not what the spec generates: python3 -m cluster rights > it, commit, again" >&2; exit 1; }
# Mutable configuration lives on the data partition, and /etc points there (the owner's decision): /etc/w2c ->
# /data/platform/etc (w2c.env, the rights file, tls/, secrets/), /etc/vms -> /data/vms/etc (vms.env). Units and
# code say /etc/…, never the target. A real directory already at /etc/… is MOVED into /data first — nothing deleted:
# its files go where the link will point, one that is already there is kept and the moved one beside it.
link_etc() {                                          # $1 /etc/… $2 its home on /data
  mkdir -p "$2"
  if [ -L "$1" ]; then
    [ "$(readlink "$1")" = "$2" ] || { echo "$1 is a link to $(readlink "$1"), not $2: left as it is" >&2; return; }
  elif [ -d "$1" ]; then
    for f in "$1"/* "$1"/.[!.]*; do
      [ -e "$f" ] || continue
      if [ -e "$2/$(basename "$f")" ]; then mv "$f" "$2/$(basename "$f").from-etc"; else mv "$f" "$2/"; fi
    done
    rmdir "$1" && ln -s "$2" "$1"
  else
    ln -s "$2" "$1"
  fi
}
link_etc /etc/w2c /data/platform/etc
link_etc /etc/vms /data/vms/etc
mkdir -p /var/log/w2c
install -m 0644 "$HERE/configstore-rights.json" /etc/w2c/configstore-rights.json
[ -f /etc/w2c/w2c.env ] || install -m 0644 "$HERE/systemd/w2c.env.example" /etc/w2c/w2c.env
[ -f /etc/vms/vms.env ] || install -m 0644 "$HERE/systemd/vms.env.example" /etc/vms/vms.env
[ -f /etc/w2c/tls/server.pem ] || echo "warning: no /etc/w2c/tls/server.pem — the store's -api door will not open (w2c-ca.sh issue $(hostname -s) configstore)" >&2
[ -f /etc/w2c/secrets/platform.key ] || echo "warning: no /etc/w2c/secrets/platform.key — the same key on every server (python3 -m w2cplatform.sealing new …)" >&2

if command -v systemctl >/dev/null 2>&1; then
  # -- Linux ------------------------------------------------------------------------------------------------------
  install -D -m 0644 "$HERE/systemd/w2c-cluster.sysusers" /etc/sysusers.d/w2c-cluster.conf
  systemd-sysusers /etc/sysusers.d/w2c-cluster.conf
  install -D -m 0644 "$HERE/systemd/w2c-cluster.tmpfiles" /etc/tmpfiles.d/w2c-cluster.conf
  systemd-tmpfiles --create /etc/tmpfiles.d/w2c-cluster.conf
  # The archive's engine: М10's installer installs and enables М10's unit; the product's name for it is an ALIAS
  # (a symlink in /etc/systemd/system), so the recorder's `After=vms-obsd.service` is that one unit — never a second
  # daemon on the same socket.
  sh "$VMSSERVER/deploy/install-obsd.sh"
  [ -e /etc/systemd/system/vms-obsd.service ] || ln -s obsd.service /etc/systemd/system/vms-obsd.service
  for u in $UNITS; do
    install -m 0644 "$HERE/systemd/$u.service" "/etc/systemd/system/$u.service"
  done
  if [ "$SPARES" = yes ]; then
    for u in $SPARE_UNITS; do
      install -m 0644 "$HERE/systemd/$u.service" "/etc/systemd/system/$u.service"
    done
    # What the spares' user may ask systemd for: `start` of these templates' instances, nothing else. polkitd reads
    # its rules directory again by itself; without the rule the script's `systemctl start` is refused, and it says so.
    install -D -m 0644 "$HERE/systemd/w2c-spares.rules" /etc/polkit-1/rules.d/50-w2c-spares.rules
    rm -f /usr/local/bin/w2c-spares.sh
    cp "$VMSSERVER/deploy/w2c-spares.sh" /usr/local/bin/w2c-spares.sh; chmod 0755 /usr/local/bin/w2c-spares.sh
    for f in "$VMSSERVER"/deploy/w2c-spares*.service "$VMSSERVER"/deploy/w2c-spares*.timer; do
      install -m 0644 "$f" "/etc/systemd/system/$(basename "$f")"
    done
  fi
  systemctl daemon-reload
  for u in $UNITS; do systemctl enable --now "$u.service"; done
  if [ "$SPARES" = yes ]; then
    systemctl enable --now w2c-spares.timer w2c-spares-vmsworker.timer
  fi
elif [ "$(uname)" = Darwin ]; then
  # -- macOS --------------------------------------------------------------------------------------------------------
  HOST="$(hostname -s)"
  # WHICH BOX, as systemd's %m says it on Linux: this Mac's hardware UUID — the same across restarts and renames.
  BOXID="$(ioreg -rd1 -c IOPlatformExpertDevice | sed -n 's/.*"IOPlatformUUID" = "\(.*\)"/\1/p')"
  for p in "$HERE"/launchd/com.w2c.*.plist; do
    name="$(basename "$p")"
    case "$name" in com.w2c.spares*) [ "$SPARES" = yes ] || continue ;; esac
    dest="/Library/LaunchDaemons/$name"
    launchctl bootout system "$dest" >/dev/null 2>&1 || true
    sed -e "s/@HOST@/$HOST/g" -e "s/@BOXID@/$BOXID/g" "$p" > "$dest"
    chmod 0644 "$dest"
    launchctl bootstrap system "$dest"
  done
  if [ "$SPARES" = yes ]; then
    rm -f /usr/local/bin/w2c-spares.sh
    cp "$VMSSERVER/deploy/w2c-spares.sh" /usr/local/bin/w2c-spares.sh; chmod 0755 /usr/local/bin/w2c-spares.sh
  fi
else
  echo "neither systemd nor launchd here: the code and the files are in place, nothing was started" >&2
fi
echo "installed: $UNITS$( [ "$SPARES" = yes ] && echo ' + spares')"
