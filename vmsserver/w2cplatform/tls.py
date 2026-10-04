"""Mutual TLS between the platform's own processes: one CA per installation, one certificate per server and role.

Used by the store daemon's `-api` door first (`configstore.py`); written so that every other door between processes
can take it as it is — a role is a name in the certificate, not a property of the door."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # tls.py — who is calling, said by a certificate
#
# **Role.** Until the cluster without an orchestrator, a door between two of the platform's processes trusted
# whoever reached it (inter-process authentication was deferred). A raft group cannot: a daemon that accepts
# `POST /v1/join` from anybody hands the cluster's whole store to anybody, and the store holds the keys of the
# domain. So the store's daemons speak mutual TLS on their `-api` door, and this file is everything about it that
# is not the store's: where the files are, how the two contexts are built, and how a role is read out of the
# certificate on the other side.
#
# ## The layout (the product takes the same names)
#   /etc/w2c/tls/ca.pem        the installation's CA — the only one a door trusts
#   /etc/w2c/tls/server.pem    this server's certificate for the store daemon: CN `configstore.<server>`,
#                              SAN DNS `<server>`, SAN URI `urn:w2c:role:configstore`
#   /etc/w2c/tls/server.key    its key (0600)
#   /etc/w2c/tls/raft.secret   the raft port's shared secret (pysyncobj `password=`; `configstore.py`)
# `deploy/w2c-ca.sh init` makes the CA and the secret, `w2c-ca.sh issue <server> [role…]` a server's bundle. Other
# roles' certificates (a later round) sit beside it as `<role>.pem` / `<role>.key`.
#
# ## A role is read from SAN URIs, then from the CN
# A certificate says which roles it may act as with `urn:w2c:role:<role>` SAN URIs — any one of them grants — and
# a certificate without one says it with its CN, `<role>.<server>`. The CA is the installation's own and signs only
# what `w2c-ca.sh` issues, so a role in a certificate it signed is a role somebody installed.
#
# ## Both sides check
# - The SERVER requires a client certificate signed by the CA (`server_context`), and the door asks
#   `require_role` for the role it serves. No certificate: the handshake fails. A certificate of another role
#   (a recorder's, a console's): the door answers 403.
# - The CLIENT checks that the server's certificate is the CA's AND that its SAN DNS is the server it dialled
#   (`client_context` + `server_hostname`). An address is often an IP or a name the certificate does not carry, so
#   the name to check is given apart from it: `srv-a@10.0.0.7:8300` (`split_address`); a bare `srv-a:8300` checks
#   `srv-a`. The client then asks the role of the server, too (`require_role`): a recorder's certificate for
#   `srv-a` is a valid certificate for `srv-a` and still not the store.
# ================================================================================================
from __future__ import annotations

import os
import ssl

from .runtime import ETC

TLS_DIR = ETC + "/tls"                             # the platform's configuration: `runtime.ETC`
ROLE_URI = "urn:w2c:role:"


class Bundle:
    """The files of one server's TLS directory, by the names above."""

    def __init__(self, directory: str, name: str = "server"):
        self.dir = directory
        self.ca = os.path.join(directory, "ca.pem")
        self.cert = os.path.join(directory, f"{name}.pem")
        self.key = os.path.join(directory, f"{name}.key")
        self.raft_secret = os.path.join(directory, "raft.secret")

    def missing(self) -> list[str]:
        return [p for p in (self.ca, self.cert, self.key) if not os.path.exists(p)]


def server_context(directory: str, name: str = "server") -> ssl.SSLContext:
    """A door's context: our certificate, and a client certificate signed by our CA REQUIRED."""
    b = Bundle(directory, name)
    if b.missing():
        raise FileNotFoundError(f"TLS files missing: {', '.join(b.missing())} (made by deploy/w2c-ca.sh)")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(b.cert, b.key)
    ctx.load_verify_locations(b.ca)
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def client_context(directory: str, name: str = "server") -> ssl.SSLContext:
    """A caller's context: our certificate as the client's, the server's checked against our CA and its name."""
    b = Bundle(directory, name)
    if b.missing():
        raise FileNotFoundError(f"TLS files missing: {', '.join(b.missing())} (made by deploy/w2c-ca.sh)")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(b.cert, b.key)
    ctx.load_verify_locations(b.ca)
    ctx.check_hostname = True                    # SAN DNS = the server we dialled (`server_hostname`)
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def raft_secret(directory: str) -> str:
    """The raft port's shared secret; refused when it is not there or empty — an open raft port is not a default."""
    path = Bundle(directory).raft_secret
    with open(path) as f:
        secret = f.read().strip()
    if not secret:
        raise ValueError(f"{path} is empty")
    return secret


def split_address(address: str) -> tuple[str, str, int]:
    """`srv-a@10.0.0.7:8300` → (`srv-a`, `10.0.0.7`, 8300); `srv-a:8300` → (`srv-a`, `srv-a`, 8300)."""
    name, _, where = address.rpartition("@")
    host, sep, port = where.rpartition(":")
    if not sep or not host or not port.isdigit():
        raise ValueError(f"not an address: {address!r} (host:port, or server@host:port)")
    return (name or host), host, int(port)


def _subject_cn(cert: dict) -> str:
    for rdn in cert.get("subject", ()):
        for k, v in rdn:
            if k == "commonName":
                return v
    return ""


def peer_roles(cert: dict | None) -> set[str]:
    """The roles a peer's certificate (as `getpeercert()` gives it) may act as: its `urn:w2c:role:` SAN URIs, or —
    a certificate with none — the first label of its CN."""
    if not cert:
        return set()
    roles = {v[len(ROLE_URI):] for k, v in cert.get("subjectAltName", ()) if k == "URI" and v.startswith(ROLE_URI)}
    if roles:
        return roles
    cn = _subject_cn(cert)
    return {cn.split(".", 1)[0]} if "." in cn else set()


def peer_server(cert: dict | None) -> str:
    """The server a peer's certificate names: the CN after its role, else its first SAN DNS."""
    if not cert:
        return ""
    cn = _subject_cn(cert)
    if "." in cn:
        return cn.split(".", 1)[1]
    return next((v for k, v in cert.get("subjectAltName", ()) if k == "DNS"), "")


def require_role(sock, role: str) -> dict:
    """The peer of a TLS socket acts as `role`, or `PermissionError` naming what it is instead."""
    cert = sock.getpeercert()
    roles = peer_roles(cert)
    if role not in roles:
        who = ", ".join(sorted(roles)) or "no role"
        raise PermissionError(f"the peer's certificate is for {who} of {peer_server(cert) or 'no server'}, not {role}")
    return cert
