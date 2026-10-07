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
# A REVOCATION IS NEVER LIFTED BY ACCIDENT (the product's cross-check). A change of the file was seen by its inode, size
# and mtime: a list rewritten in place with the same size and mtime (`cp -p`, a restored backup) was never read, and
# its revocation never reached the door; a list deleted while the door ran shut it on everybody. The list is seen by
# its CONTENT now (a hash per connection — a small file), and a list that went missing or does not load (half a copy)
# leaves the door the list it holds, said on stderr and tried again on the next caller; missing at start, no door.
# A revocation reaches NEW connections: one opened before it lives until it is answered (the door answers one request
# and closes), and a revoked server that is a member stays a voter of the group over the raft port — `revoke` is
# followed by `configstore leave <server>` and a new raft secret (below).
# Open, and said by `w2c-ca.sh revoke`: the revoked server still knows `raft.secret`, which the TLS list does not
# cover — the raft port takes whoever holds it. Until mTLS is on the raft port too (the product's `hashicorp/raft`
# runs TLS there), a revocation is finished by a new secret on every member and a restart of the group.
#
# ## A role is read from SAN URIs, then from the CN
# A certificate says which roles it may act as with `urn:w2c:role:<role>` SAN URIs — any one of them grants — and
# a certificate without one says it with its CN, `<role>.<server>`. The CA is the installation's own and signs only
# what `w2c-ca.sh` issues, so a role in a certificate it signed is a role somebody installed.
# A DAEMON'S CERTIFICATE CARRIES ONE ROLE (the product's cross-check of its hashicorp/raft store). «Any one grants»
# made a certificate of `configstore` and a worker role a store daemon at every door that asked for the store — and a
# worker that holds its key a daemon of the group. The store's role is never shared (`SOLE_ROLES`): `w2c-ca.sh issue`
# refuses it with another, a door refuses a peer whose certificate carries it with another whatever role the door
# asks (`require_role`), and no context is built on such a certificate of our own (`_context`) — the daemon does not
# start with one.
#
# ## The CA is one certificate (the product's cross-check)
# `load_verify_locations(ca.pem)` trusts every certificate in the file: a CA appended to it — and its list appended
# to `crl.pem`, which the leaf check asks — let that CA's daemon through the door. `ca.pem` holds exactly one CA
# certificate block, else nothing is built (`_installation_ca`); the context trusts the DER of that block only, so
# text around it (a comment, CRLF line ends) is neither trust nor refusal. A new CA is a new bundle on every server.
#
# ## Both sides check
# - The SERVER requires a client certificate signed by the CA (`server_context`), and the door asks
#   `require_role` for the role it serves. No certificate: the handshake fails. A certificate of another role
#   (a worker's, a console's): the door answers 403.
# - The CLIENT checks that the server's certificate is the CA's AND that its SAN DNS is the server it dialled
#   (`client_context` + `server_hostname`). An address is often an IP or a name the certificate does not carry, so
#   the name to check is given apart from it: `srv-a@10.0.0.7:8300` (`split_address`); a bare `srv-a:8300` checks
#   `srv-a`. The client then asks the role of the server, too (`require_role`): a worker's certificate for
#   `srv-a` is a valid certificate for `srv-a` and still not the store.
# ================================================================================================
from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import ssl
import sys
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


# Both sides alike: our certificate, the peer's REQUIRED, signed by our CA — the one certificate of `ca.pem` — and not
# on its revocation list.
def _context(directory: str, name: str, side) -> ssl.SSLContext:
    b = Bundle(directory, name)
    if b.missing():
        raise FileNotFoundError(f"TLS files missing: {', '.join(b.missing())} (made by deploy/w2c-ca.sh; a bundle "
                                f"from before the revocation list gets its crl.pem from `w2c-ca.sh crl`)")
    shared = _sole_refusal(own_roles(directory, name))
    if shared:
        raise ValueError(f"{b.cert}: {shared} — issue the server's store certificate again (w2c-ca.sh issue)")
    ctx = ssl.SSLContext(side)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(b.cert, b.key)
    ctx.load_verify_locations(cadata=_installation_ca(b.ca))   # that block alone: nothing else in the file is trusted
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
    with the file, not with a restart. `get()` per connection: one small file read and hashed. A list that went
    missing or does not load leaves the door the list it holds (the notes: never lifted by accident)."""

    def __init__(self, directory: str, name: str = "server"):
        self.directory, self.name = directory, name
        self.crl = Bundle(directory, name).crl
        self.lock = threading.Lock()
        self.said = ""                               # the last trouble with the list, said once on stderr
        self.seen = self._digest()
        self.ctx = server_context(directory, name)   # missing or unloadable at start: no door

    # The list's content, not its inode, size or mtime: a list rewritten in place with the same three is another list.
    def _digest(self) -> str | None:
        try:
            with open(self.crl, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except FileNotFoundError:
            return None

    def get(self) -> ssl.SSLContext:
        digest = self._digest()
        with self.lock:
            if digest == self.seen:
                return self.ctx
            try:
                if digest is None:
                    raise FileNotFoundError(f"{self.crl} is missing")
                ctx = server_context(self.directory, self.name)
            except (OSError, ssl.SSLError, ValueError) as e:
                if str(e) != self.said:
                    self.said = str(e)
                    print(f"configstore: the revocation list {self.crl} could not be read ({e}); the door goes on "
                          f"with the list it read before, revocations and all — copy crl.pem there again",
                          file=sys.stderr, flush=True)
                return self.ctx                      # not taken as seen: the next caller reads the file again
            self.ctx, self.seen, self.said = ctx, digest, ""
            return self.ctx


# THE SECRET IS CHECKED, AND SALTED BY THE INSTALLATION (the review's twelfth pass, minor). It was taken as it was: a
# file anybody on the server could read, one character long, would do. So it is refused when its mode lets anybody but
# its owner read it (`w2c-ca.sh` writes it 0600) and when it is shorter than `SECRET_CHARS` (`w2c-ca.sh` writes 64
# hex characters, 256 bits). And pysyncobj derives its key with one PBKDF2 salt for every installation in the world
# (`pysyncobj/encryptor.py`, `SALT`), so the password it is handed is the secret keyed with this installation's CA
# (`ca.pem`, which every member holds): a key worked out for one installation's secret is no use against another's.
#
# KEYED WITH THE CA, NOT WITH THE FILE'S BYTES (the review's thirteenth pass, minor). The key was the hash of
# `ca.pem` as bytes: one more newline from an editor, and that member's password changed — it dropped out of its group
# without a word. The key is now the CA certificate itself: the DER of the one certificate in `ca.pem`
# (`_installation_ca`), whatever text surrounds it. A second certificate beside it is refused, here as at the doors
# (the product's cross-check: `ca.pem` is exactly one CA — the notes above).
SECRET_CHARS = 32
_PEM_CERT = re.compile(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", re.S)
# Every block OpenSSL takes as a trusted certificate: `CERTIFICATE`, `TRUSTED CERTIFICATE`, `X509 CERTIFICATE`.
_ANY_CERT = re.compile(r"-----BEGIN (?:TRUSTED |X509 )?CERTIFICATE-----")


def _installation_ca(path: str) -> bytes:
    """The DER of the one CA certificate in `path`; `ValueError` for none, or for more than one."""
    with open(path, encoding="ascii", errors="replace") as f:
        text = f.read()
    blocks, every = _PEM_CERT.findall(text), len(_ANY_CERT.findall(text))
    if len(blocks) != 1 or every != 1:
        raise ValueError(f"{path} holds {every} certificates, not one CA certificate: a door trusts every certificate "
                         f"in its CA file, so ca.pem is the installation's CA alone (deploy/w2c-ca.sh)")
    try:
        return base64.b64decode("".join(blocks[0].split()), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(f"{path}: its CA certificate block is not base64 (deploy/w2c-ca.sh)") from None


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


# Roles a certificate never carries with another (the notes: one role) — the store's: its daemon is a member of the group.
SOLE_ROLES = frozenset({"configstore"})


def _sole_refusal(roles: set[str]) -> str:
    shared = roles & SOLE_ROLES
    if shared and len(roles) > 1:
        return (f"the certificate carries {', '.join(sorted(roles))}: a daemon's certificate carries one role, and "
                f"{', '.join(sorted(shared))} is never shared")
    return ""


def own_roles(directory: str, name: str = "server") -> set[str]:
    """The roles of our own certificate in `directory`, read as a peer reads them."""
    # `_test_decode_cert` is the `ssl` module's own reading of a PEM file into `getpeercert()`'s form (CPython's).
    return peer_roles(ssl._ssl._test_decode_cert(Bundle(directory, name).cert))


def require_role(sock, role: str) -> dict:
    """The peer of a TLS socket acts as `role`, or `PermissionError` naming what it is instead. A certificate that
    carries a sole role with another is refused whatever `role` is asked."""
    cert = sock.getpeercert()
    roles = peer_roles(cert)
    shared = _sole_refusal(roles)
    if shared:
        raise PermissionError(f"the peer's certificate for {peer_server(cert) or 'no server'}: {shared}")
    if role not in roles:
        who = ", ".join(sorted(roles)) or "no role"
        raise PermissionError(f"the peer's certificate is for {who} of {peer_server(cert) or 'no server'}, not {role}")
    return cert
