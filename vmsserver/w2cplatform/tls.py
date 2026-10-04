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
#   /etc/w2c/tls/crl.pem       the certificates the CA has revoked — every door asks it, both sides
# `deploy/w2c-ca.sh init` makes the CA, its empty revocation list and the secret, `w2c-ca.sh issue <server> [role…]` a
# server's bundle, `w2c-ca.sh revoke <server>` puts every certificate issued for the server on the list. Other roles'
# certificates (a later round) sit beside it as `<role>.pem` / `<role>.key`.
#
# ## A certificate can be taken back (the review's thirteenth pass, major 5)
# There was no revocation: a decommissioned or stolen server's bundle — 825 days of it — joined the group under its
# own id, and with `raft.secret` read every row. Now the CA keeps a revocation list (`crl.pem`, made by `w2c-ca.sh`
# from its `index.txt`), every bundle carries it, and both contexts below load it and verify the peer's certificate
# against it (`VERIFY_CRL_CHECK_LEAF`): a revoked daemon's handshake fails at the `-api` door — no status, no join —
# and a daemon dialling a revoked one refuses it. The list is REQUIRED: a door that could not hear of a revocation
# is not opened. A door re-reads the list when the file changes (`ServerContext`), so the operator copies the new
# `crl.pem` to every server and no daemon needs a restart. A list has a `nextUpdate` (`W2C_CA_CRL_DAYS`, ten years by
# default): past it OpenSSL takes no certificate at all — make a new list (`w2c-ca.sh crl`) before then.
# Open, and said by `w2c-ca.sh revoke`: the revoked server still knows `raft.secret`, which the TLS list does not
# cover — the raft port takes whoever holds it. Until mTLS is on the raft port too (the product's `hashicorp/raft`
# runs TLS there), a revocation is finished by a new secret on every member and a restart of the group.
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
import re
import ssl
import threading

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
        self.crl = os.path.join(directory, "crl.pem")

    def missing(self) -> list[str]:
        return [p for p in (self.ca, self.cert, self.key, self.crl) if not os.path.exists(p)]


# Both sides alike: our certificate, the peer's REQUIRED, signed by our CA and not on its revocation list.
def _context(directory: str, name: str, side) -> ssl.SSLContext:
    b = Bundle(directory, name)
    if b.missing():
        raise FileNotFoundError(f"TLS files missing: {', '.join(b.missing())} (made by deploy/w2c-ca.sh; a bundle "
                                f"from before the revocation list gets its crl.pem from `w2c-ca.sh crl`)")
    ctx = ssl.SSLContext(side)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(b.cert, b.key)
    ctx.load_verify_locations(b.ca)
    ctx.load_verify_locations(b.crl)             # a PEM file of lists: OpenSSL takes the CRLs in it
    ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def server_context(directory: str, name: str = "server") -> ssl.SSLContext:
    """A door's context: our certificate, and a client certificate signed by our CA, not revoked, REQUIRED."""
    return _context(directory, name, ssl.PROTOCOL_TLS_SERVER)


def client_context(directory: str, name: str = "server") -> ssl.SSLContext:
    """A caller's context: our certificate as the client's, the server's checked against our CA, its revocation list
    and its name."""
    ctx = _context(directory, name, ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = True                    # SAN DNS = the server we dialled (`server_hostname`)
    return ctx


class ServerContext:
    """A door's context, made again when the revocation list on disk changes — a revocation reaches a running door
    with the file, not with a restart. `get()` per connection: a `stat` of one file."""

    def __init__(self, directory: str, name: str = "server"):
        self.directory, self.name = directory, name
        self.crl = Bundle(directory, name).crl
        self.lock = threading.Lock()
        self.seen, self.ctx = self._stamp(), server_context(directory, name)

    def _stamp(self):
        try:
            st = os.stat(self.crl)
            return st.st_ino, st.st_size, st.st_mtime_ns
        except FileNotFoundError:
            return None

    def get(self) -> ssl.SSLContext:
        stamp = self._stamp()
        with self.lock:
            if stamp != self.seen:
                # A list that went missing or does not load keeps the door shut, not open: no context, no handshake.
                self.ctx = server_context(self.directory, self.name)
                self.seen = stamp
            return self.ctx


# THE SECRET IS CHECKED, AND SALTED BY THE INSTALLATION (the review's twelfth pass, minor). It was taken as it was: a
# file anybody on the server could read, one character long, would do. So it is refused when its mode lets anybody but
# its owner read it (`w2c-ca.sh` writes it 0600) and when it is shorter than `SECRET_CHARS` (`w2c-ca.sh` writes 64
# hex characters, 256 bits). And pysyncobj derives its key with one PBKDF2 salt for every installation in the world
# (`pysyncobj/encryptor.py`, `SALT`), so the password it is handed is the secret keyed with this installation's CA
# (`ca.pem`, which every member holds): a key worked out for one installation's secret is no use against another's.
#
# KEYED WITH THE CA, NOT WITH THE FILE'S BYTES (the review's thirteenth pass, minor). The key was the hash of
# `ca.pem` as bytes: one more newline from an editor, or a second CA added to the bundle for a rotation, and that
# member's password changed — it dropped out of its group without a word. The key is now the CA certificate itself:
# the DER of the FIRST certificate in `ca.pem` (`_installation_ca`), whatever text surrounds it; a CA added for a
# rotation goes AFTER it, and the password stays.
SECRET_CHARS = 32
_PEM_CERT = re.compile(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.S)


def _installation_ca(path: str) -> bytes:
    with open(path, encoding="ascii", errors="replace") as f:
        block = _PEM_CERT.search(f.read())
    if block is None:
        raise ValueError(f"{path} holds no certificate: the installation's CA is ca.pem (deploy/w2c-ca.sh)")
    return ssl.PEM_cert_to_DER_cert(block.group(0))


def raft_secret(directory: str) -> str:
    """The raft port's password: `raft.secret`, refused when it is not there, readable by others or short — an open
    raft port is not a default — keyed with the installation's CA."""
    import hashlib
    import hmac
    import stat
    b = Bundle(directory)
    with open(b.raft_secret) as f:
        mode = stat.S_IMODE(os.fstat(f.fileno()).st_mode)
        secret = f.read().strip()
    if mode & 0o077:
        raise ValueError(f"{b.raft_secret} is readable by others (mode {mode:04o}): chmod 600 — it is the raft port's "
                         f"password")
    if len(secret) < SECRET_CHARS:
        raise ValueError(f"{b.raft_secret} holds {len(secret)} characters, fewer than {SECRET_CHARS}: make it again "
                         f"(deploy/w2c-ca.sh init writes 64)")
    salt = hashlib.sha256(_installation_ca(b.ca)).digest()
    return hmac.new(salt, secret.encode(), hashlib.sha256).hexdigest()


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
    """The server a peer's certificate names: the CN after its role, else its first SAN DNS; "" when it names none
    (a door that acts on the name refuses that: `configstore._peer_role`)."""
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
