#!/bin/sh
# w2c-ca.sh — the installation's own CA for mutual TLS between the platform's processes (w2cplatform/tls.py).
#
#   w2c-ca.sh init                      the CA (ca.key, ca.pem), its empty revocation list (crl.pem) and the raft
#                                       port's secret (raft.secret)
#   w2c-ca.sh issue <server> [role…]    one server's bundle in <ca dir>/<server>/: ca.pem, crl.pem, raft.secret and a
#                                       certificate with CN <first role>.<server>, SAN DNS <server> and one SAN URI
#                                       urn:w2c:role:<role> per role (default role: configstore). The store daemon's is
#                                       server.pem / server.key, its role alone (configstore with another is
#                                       refused); another role's is <role>.pem / <role>.key.
#   w2c-ca.sh revoke <server>           every certificate ever issued for <server> onto the revocation list, and a
#                                       new crl.pem (in the CA directory and in every bundle under it)
#   w2c-ca.sh crl                       crl.pem made again from what is revoked — before the list's nextUpdate, and
#                                       for a CA directory from before the list (the test fixtures were)
#   w2c-ca.sh own <tls dir> <user>      hand a bundle copied to a server to the user whose daemon reads it: every file
#                                       that user's, its keys and raft.secret 0600, the certificates and the list 0644,
#                                       the directory 0750 to the user's group — `install.sh` runs it on /etc/w2c/tls
#                                       for `configstore` (М11)
#
# The CA directory is $W2C_CA_DIR (default ./w2c-ca) and stays on the operator's machine: ca.key never goes to a
# server. A server gets its bundle copied to /etc/w2c/tls, and then given to the daemon's user (`own`): the store's
# member runs as `configstore`, not root, and a bundle copied as root with keys 0600 was a `PermissionError` — the
# store came up on no server (the thirteenth review, major 14). The raft secret stays its owner's alone (`tls.py`
# refuses one others may read, a group included), so the files are the user's, not a group's. Every server of a group
# gets the SAME raft.secret — it is the raft port's password, made once by `init`. After `revoke`, crl.pem goes to
# EVERY server's /etc/w2c/tls (and `own` again): a door re-reads it when the file changes (the review's thirteenth
# pass, major 5).
#
# Every certificate `issue` signs is kept in <ca dir>/issued/<server>/<serial>.pem, so `revoke` finds the ones a
# re-issue has replaced in the bundle — a stolen bundle is an old certificate as often as the current one.
#
#   W2C_CA_DAYS      a certificate's life in days (default 825)
#   W2C_CA_CA_DAYS   the CA's (default 3650)
#   W2C_CA_CRL_DAYS  the revocation list's (default 3650): past its nextUpdate no door takes any certificate
#   W2C_CA_SAN       more subject alt names for `issue`, comma separated: "IP:10.0.0.7,DNS:srv-a.lan"
#
# The test fixtures under Source/tests/tls/ were made by this recipe, long-lived:
#   W2C_CA_DIR=tests/tls W2C_CA_DAYS=36500 W2C_CA_CA_DAYS=36500 deploy/w2c-ca.sh init
#   W2C_CA_DIR=tests/tls W2C_CA_DAYS=36500 deploy/w2c-ca.sh issue srv-a   (and srv-b, srv-c)
#   W2C_CA_DIR=tests/tls W2C_CA_DAYS=36500 deploy/w2c-ca.sh issue srv-a testsub2worker
#   W2C_CA_DIR=tests/tls W2C_CA_CRL_DAYS=36500 deploy/w2c-ca.sh crl      (their list, made after them)
set -eu

CA_DIR=${W2C_CA_DIR:-./w2c-ca}
DAYS=${W2C_CA_DAYS:-825}
ROLE_URI=urn:w2c:role:          # w2cplatform/tls.py ROLE_URI: the same prefix, said once in each
STORE_ROLE=configstore         # the store daemon's role: its files are server.pem / server.key
CA_DAYS=${W2C_CA_CA_DAYS:-3650}
CRL_DAYS=${W2C_CA_CRL_DAYS:-3650}

die() { echo "w2c-ca.sh: $*" >&2; exit 1; }

# `openssl ca` keeps what is revoked in index.txt; it is asked only for the list (`revoke`, `crl`), never to sign.
ca_conf() {
    cat <<EOF
[ca]
default_ca = w2c
[w2c]
database = $CA_DIR/index.txt
certificate = $CA_DIR/ca.pem
private_key = $CA_DIR/ca.key
default_md = sha256
default_crl_days = $CRL_DAYS
unique_subject = no
EOF
}

# The list, made from index.txt and copied into every bundle under the CA directory.
crl() {
    [ -e "$CA_DIR/ca.key" ] || die "no CA in $CA_DIR: w2c-ca.sh init first"
    [ -e "$CA_DIR/index.txt" ] || : >"$CA_DIR/index.txt"
    conf=$(mktemp)
    ca_conf >"$conf"
    openssl ca -config "$conf" -gencrl -out "$CA_DIR/crl.pem" 2>/dev/null || { rm -f "$conf"; die "openssl ca -gencrl failed"; }
    rm -f "$conf"
    for b in "$CA_DIR"/*/; do
        [ -e "${b}ca.pem" ] && cp "$CA_DIR/crl.pem" "${b}crl.pem"
    done
    echo "$CA_DIR/crl.pem"
}

init() {
    [ -e "$CA_DIR/ca.key" ] && die "$CA_DIR/ca.key exists: one CA per installation, not a second one over it"
    mkdir -p "$CA_DIR"
    chmod 700 "$CA_DIR"
    ext=$(mktemp)
    cat >"$ext" <<EOF
[req]
distinguished_name = dn
[dn]
[ca]
basicConstraints = critical, CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
EOF
    openssl ecparam -name prime256v1 -genkey -noout -out "$CA_DIR/ca.key"
    chmod 600 "$CA_DIR/ca.key"
    openssl req -x509 -new -key "$CA_DIR/ca.key" -sha256 -days "$CA_DAYS" -subj "/CN=w2c installation CA" \
        -config "$ext" -extensions ca -out "$CA_DIR/ca.pem"
    rm -f "$ext"
    openssl rand -hex 32 >"$CA_DIR/raft.secret"
    chmod 600 "$CA_DIR/raft.secret"
    crl >/dev/null
    echo "$CA_DIR/ca.pem, $CA_DIR/crl.pem, $CA_DIR/raft.secret"
}

issue() {
    server=${1:-}
    [ -n "$server" ] || die "issue <server> [role…]"
    shift
    [ $# -gt 0 ] || set -- "$STORE_ROLE"
    # The store daemon's certificate carries its role alone (the product's cross-check; tls.py SOLE_ROLES): with
    # another role in it, whoever runs that other role holds a member's key of the group.
    if [ $# -gt 1 ]; then
        for r in "$@"; do
            [ "$r" = "$STORE_ROLE" ] && die "$STORE_ROLE with another role ($*): a daemon's certificate carries one role — issue $STORE_ROLE alone, the others apart"
        done
    fi
    [ -e "$CA_DIR/ca.key" ] || die "no CA in $CA_DIR: w2c-ca.sh init first"
    [ -e "$CA_DIR/crl.pem" ] || crl >/dev/null
    name=$1
    for r in "$@"; do [ "$r" = "$STORE_ROLE" ] && name=server; done
    out="$CA_DIR/$server"
    mkdir -p "$out"
    chmod 700 "$out"
    san="DNS:$server"
    for r in "$@"; do san="$san,URI:$ROLE_URI$r"; done
    [ -n "${W2C_CA_SAN:-}" ] && san="$san,$W2C_CA_SAN"
    ext=$(mktemp)
    cat >"$ext" <<EOF
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
subjectAltName = $san
EOF
    openssl ecparam -name prime256v1 -genkey -noout -out "$out/$name.key"
    chmod 600 "$out/$name.key"
    csr=$(mktemp)
    openssl req -new -key "$out/$name.key" -subj "/CN=$1.$server" -out "$csr"
    openssl x509 -req -in "$csr" -CA "$CA_DIR/ca.pem" -CAkey "$CA_DIR/ca.key" -CAcreateserial \
        -CAserial "$CA_DIR/ca.srl" -days "$DAYS" -sha256 -extfile "$ext" -out "$out/$name.pem" 2>/dev/null
    rm -f "$ext" "$csr"
    serial=$(openssl x509 -in "$out/$name.pem" -noout -serial | sed 's/^serial=//')
    mkdir -p "$CA_DIR/issued/$server"
    cp "$out/$name.pem" "$CA_DIR/issued/$server/$serial.pem"
    cp "$CA_DIR/ca.pem" "$out/ca.pem"
    cp "$CA_DIR/crl.pem" "$out/crl.pem"
    cp "$CA_DIR/raft.secret" "$out/raft.secret"
    chmod 600 "$out/raft.secret"
    echo "$out/$name.pem: CN $1.$server, SAN $san, serial $serial"
}

# Every certificate issued for the server — kept under issued/, and those in its bundle (a CA directory from before
# issued/ was kept) — each once.
revoke() {
    server=${1:-}
    [ -n "$server" ] || die "revoke <server>"
    [ -e "$CA_DIR/ca.key" ] || die "no CA in $CA_DIR: w2c-ca.sh init first"
    [ -e "$CA_DIR/index.txt" ] || : >"$CA_DIR/index.txt"
    conf=$(mktemp)
    ca_conf >"$conf"
    n=0
    for cert in "$CA_DIR/issued/$server"/*.pem "$CA_DIR/$server"/*.pem; do
        [ -e "$cert" ] || continue
        case "$cert" in */ca.pem|*/crl.pem) continue ;; esac
        serial=$(openssl x509 -in "$cert" -noout -serial | sed 's/^serial=//')
        if grep -q "^R.*	$serial	" "$CA_DIR/index.txt"; then continue; fi
        openssl ca -config "$conf" -revoke "$cert" 2>/dev/null || { rm -f "$conf"; die "openssl ca -revoke $cert failed"; }
        echo "revoked $serial ($cert)"
        n=$((n + 1))
    done
    rm -f "$conf"
    [ "$n" -gt 0 ] || grep -q "/CN=[^/]*\.$server\$" "$CA_DIR/index.txt" || die "no certificate issued for $server in $CA_DIR"
    crl >/dev/null
    echo "$CA_DIR/crl.pem: copy it to /etc/w2c/tls/crl.pem on every server (the doors re-read it; a connection opened before lives until it is answered)."
    echo "$server is still a voter if it was a member: configstore leave $server, on a member."
    echo "$server still knows raft.secret: make a new one (openssl rand -hex 32), put it on every member, restart the group."
}

# A bundle on a server, the daemon's: the files its user's, nobody else reading a key or the secret.
own() {
    dir=${1:-}; user=${2:-}
    [ -n "$dir" ] && [ -n "$user" ] || die "own <tls dir> <user>"
    [ -d "$dir" ] || die "$dir: no such directory (copy the server's bundle there first)"
    group=$(id -gn "$user") || die "no user $user"
    for f in "$dir"/*; do
        [ -f "$f" ] || continue
        chown "$user:$group" "$f"
        case "$f" in
            *.key|*/raft.secret) chmod 0600 "$f" ;;
            *) chmod 0644 "$f" ;;
        esac
    done
    chgrp "$group" "$dir"
    chmod 0750 "$dir"
    echo "$dir: $user's (keys and raft.secret 0600, certificates 0644)"
}

case "${1:-}" in
    init) init ;;
    issue) shift; issue "$@" ;;
    revoke) shift; revoke "$@" ;;
    crl) crl ;;
    own) shift; own "$@" ;;
    *) die "usage: w2c-ca.sh init | issue <server> [role…] | revoke <server> | crl | own <tls dir> <user>" ;;
esac
