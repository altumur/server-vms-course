#!/bin/sh
# w2c-ca.sh — the installation's own CA for mutual TLS between the platform's processes (w2cplatform/tls.py).
#
#   w2c-ca.sh init                      the CA (ca.key, ca.pem) and the raft port's secret (raft.secret)
#   w2c-ca.sh issue <server> [role…]    one server's bundle in <ca dir>/<server>/: ca.pem, raft.secret and a
#                                       certificate with CN <first role>.<server>, SAN DNS <server> and one SAN URI
#                                       urn:w2c:role:<role> per role (default role: configstore). The store daemon's is
#                                       server.pem / server.key; another role's is <role>.pem / <role>.key.
#   w2c-ca.sh own <tls dir> <user>      hand a bundle copied to a server to the user whose daemon reads it: every file
#                                       that user's, its keys and raft.secret 0600, the certificates 0644, the
#                                       directory 0750 to the user's group — `install.sh` runs it on /etc/w2c/tls for
#                                       `configstore` (М11)
#
# The CA directory is $W2C_CA_DIR (default ./w2c-ca) and stays on the operator's machine: ca.key never goes to a
# server. A server gets its bundle copied to /etc/w2c/tls, and then given to the daemon's user (`own`): the store's
# member runs as `configstore`, not root, and a bundle copied as root with keys 0600 was a `PermissionError` — the
# store came up on no server (the thirteenth review, major 14). The raft secret stays its owner's alone (`tls.py`
# refuses one others may read, a group included), so the files are the user's, not a group's. Every server of a group
# gets the SAME raft.secret — it is the raft port's password, made once by `init`.
#
#   W2C_CA_DAYS     a certificate's life in days (default 825)
#   W2C_CA_CA_DAYS  the CA's (default 3650)
#   W2C_CA_SAN      more subject alt names for `issue`, comma separated: "IP:10.0.0.7,DNS:srv-a.lan"
#
# The test fixtures under vmsserver/tests/tls/ were made by this recipe, long-lived:
#   W2C_CA_DIR=tests/tls W2C_CA_DAYS=36500 W2C_CA_CA_DAYS=36500 deploy/w2c-ca.sh init
#   W2C_CA_DIR=tests/tls W2C_CA_DAYS=36500 deploy/w2c-ca.sh issue srv-a   (and srv-b, srv-c)
#   W2C_CA_DIR=tests/tls W2C_CA_DAYS=36500 deploy/w2c-ca.sh issue srv-a recworker
set -eu

CA_DIR=${W2C_CA_DIR:-./w2c-ca}
DAYS=${W2C_CA_DAYS:-825}
ROLE_URI=urn:w2c:role:          # w2cplatform/tls.py ROLE_URI: the same prefix, said once in each
STORE_ROLE=configstore         # the store daemon's role: its files are server.pem / server.key
CA_DAYS=${W2C_CA_CA_DAYS:-3650}

die() { echo "w2c-ca.sh: $*" >&2; exit 1; }

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
    echo "$CA_DIR/ca.pem, $CA_DIR/raft.secret"
}

issue() {
    server=${1:-}
    [ -n "$server" ] || die "issue <server> [role…]"
    shift
    [ $# -gt 0 ] || set -- "$STORE_ROLE"
    [ -e "$CA_DIR/ca.key" ] || die "no CA in $CA_DIR: w2c-ca.sh init first"
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
    cp "$CA_DIR/ca.pem" "$out/ca.pem"
    cp "$CA_DIR/raft.secret" "$out/raft.secret"
    chmod 600 "$out/raft.secret"
    echo "$out/$name.pem: CN $1.$server, SAN $san"
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
    own) shift; own "$@" ;;
    *) die "usage: w2c-ca.sh init | issue <server> [role…] | own <tls dir> <user>" ;;
esac
