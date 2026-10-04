"""A device needs a login and a password; the platform's job is to let exactly
two parties see the second one — the operator who writes it and the worker that
opens the camera — and nobody in between."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from vms.config import SPEC
from vms.console import serve
from vms.controller import VmsController
from w2cplatform.secrets import SECRET_MASK, is_secret_field, mask_secrets
from w2cplatform.spec import Refused, SubsystemSpec
from tests.conftest import Box, published_snapshot


def test_the_rule_is_a_suffix_and_masking_is_a_copy():
    """One suffix, declared once, and every subsystem has it — the same move `type: int` is.

    A registry of secret field names would be a second place to keep in step with the specs, and the
    specs would win."""
    assert is_secret_field("cred_secret") and not is_secret_field("cred_username")
    assert not is_secret_field("secret_note")            # the suffix is the rule, not the word

    rows = [{"id": "7", "cred_username": "admin", "cred_secret": "Hunter2"}, {"id": "8", "cred_secret": ""}]
    out = mask_secrets(rows)
    assert out[0]["cred_secret"] == SECRET_MASK and out[0]["cred_username"] == "admin"
    assert out[1]["cred_secret"] == ""                   # empty stays empty: a page must tell "not set" from "set"
    assert rows[0]["cred_secret"] == "Hunter2"           # a copy — the caller still holds the row a worker will read


def test_a_spec_may_not_put_a_secret_in_the_snapshot():
    """`vms/snapshot/*` is what leaves the cluster for М12's directory. So this is refused at LOAD time,
    which is a different thing from being watched for at review time: a subsystem written a year from now
    cannot make the mistake, and nobody has to remember the rule to be protected by it."""
    base = {"name": "x", "unit": {"fields": {"host": {"type": "string"}, "api_secret": {"type": "string"}}}}
    try:
        SubsystemSpec.from_dict({**base, "snapshot": ["host", "api_secret"]})
        raise AssertionError("a secret was accepted into the snapshot")
    except ValueError as e:
        assert "may not be in the snapshot" in str(e)

    # …and the DEFAULT snapshot — "every field" — leaves secrets out rather than refusing: a spec that
    # said nothing made no mistake, and the safe reading of silence is the one that keeps the secret in.
    spec = SubsystemSpec.from_dict(base)
    assert spec.snapshot == ["host"]
    # a snapshot naming a field that does not exist is a typo, and typos in this list are expensive
    try:
        SubsystemSpec.from_dict({**base, "snapshot": ["hsot"]})
        raise AssertionError("accepted a snapshot naming no field")
    except ValueError as e:
        assert "names no field" in str(e)


def test_a_url_field_refuses_a_login():
    """The quiet path a password takes into a system that thinks it has none.

    `source` is `type: url` and `source` is in the snapshot. A userinfo pasted in here would reach М12's
    directory and every console screen, past a mask that only looks at `*_secret`. Refused — not moved
    quietly into the credential fields, because an operator who pasted a browser URL should learn that
    this system keeps the two apart."""
    box = Box()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    for bad in ("driverpack://root:hunter2@10.0.0.7/cam", "driverpack://admin@10.0.0.7/cam"):
        try:
            con.create_camera({"name": "gate", "source": bad})
            raise AssertionError(f"a credential rode in on the URL: {bad}")
        except Refused as e:
            assert "may not carry a login" in str(e)
    assert con.cameras() == []                                   # nothing was created on the way to the refusal

    cam = con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"})
    try:                                                          # and an edit is the same door
        con.update_camera(cam["id"], {"source": "driverpack://root:hunter2@10.0.0.7/cam"})
        raise AssertionError("an update let a credential in")
    except Refused:
        pass


def test_the_console_never_hands_out_the_secret_and_the_store_holds_one_copy():
    """The three ways a row leaves the console, and the one that is easy to miss.

    A create's reply is what the Idempotency-Key store keeps in order to answer a retry the same way. An
    unmasked reply therefore writes a SECOND copy of the secret into the config store, under a key nobody
    would think to look at — so the last thing this test does is walk the whole store."""
    secret = "Hunter2-not-in-any-reply"
    box = Box()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    srv = serve(con, box.archive, port=0, wall=box.wall)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    try:
        body = json.dumps({"name": "gate", "source": "driverpack://acme/10.0.0.5",
                           "cred_username": "admin", "cred_secret": secret}).encode()
        req = urllib.request.Request(f"{base}/cameras", data=body, method="POST", headers={"Idempotency-Key": "c1"})
        raw = urllib.request.urlopen(req).read()
        r = json.loads(raw)
        assert secret not in raw.decode() and r["cred_secret"] == SECRET_MASK and r["cred_username"] == "admin"

        again = urllib.request.urlopen(req).read()                # the retry is answered from the store
        assert secret not in again.decode(), "the retry replayed the secret"

        upd = urllib.request.Request(f"{base}/cameras/1", data=json.dumps({"cred_secret": secret + "-2"}).encode(),
                                     method="PUT", headers={"Idempotency-Key": "c2"})
        assert secret not in urllib.request.urlopen(upd).read().decode()
        assert secret not in urllib.request.urlopen(f"{base}/cameras").read().decode()
    finally:
        srv.shutdown()

    # The row itself still holds it: the worker has to read it to open the camera.
    assert con.camera(1)["cred_secret"] == secret + "-2"
    # …and that row is the ONLY place in the store that does.
    for path in box.vars.list(""):
        items, _ = box.vars.get(path)
        for k, v in (items or {}).items():
            if secret in str(v):
                assert path == "vms/cameras/1" and k == "cred_secret", f"the secret is also stored at {path}[{k}]"


def test_neither_half_of_the_credential_leaves_the_cluster():
    """Two different reasons, and they are worth keeping apart.

    The SECRET is out of the snapshot because the snapshot leaves the cluster — `SubsystemSpec.from_dict`
    refuses a spec that names it there, so this is a rule, not a choice.

    The LOGIN is out because **nothing above the cluster reads it**. М12's directory takes exactly `ref`,
    `worker` and `server` from each row; it has never looked at a credential. And the snapshot is one
    object under a 64 KiB cap, so a field with no consumer is paid for by every camera in the cluster.
    "Not a secret" is a reason not to hide it — never a reason to publish it."""
    assert "cred_secret" not in SPEC.snapshot        # refused by the spec: it would leave the cluster
    assert "cred_username" not in SPEC.snapshot      # allowed there, and still pointless: nobody reads it
    assert "cred_username" in SPEC.fields and "cred_secret" in SPEC.fields
    box = Box()
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    con.create_camera({"name": "gate", "source": "driverpack://acme/10.0.0.5",
                       "cred_username": "admin", "cred_secret": "Hunter2"})
    ctl.publish_snapshot()
    snap = published_snapshot(box.objects, "vms")     # every shard, the way М12 reads them
    row = snap["cameras"][0]
    assert "cred_secret" not in row and "cred_username" not in row
    assert "Hunter2" not in json.dumps(snap) and "admin" not in json.dumps(snap)
    # what the snapshot IS for — М12 reads these three and nothing else about a row
    assert row["worker"] is None and "server" in row and "ref" in row


# A camera's login in the parameters of its address: (what is typed, the parameter the refusal names).
CRED_QUERIES = [("http://10.0.0.5/videostream.cgi?usr=admin&pwd=Hunter2", "usr"),
                ("http://10.0.0.5/snap.jpg?user=admin&password=Hunter2", "user"),
                ("rtsp://10.0.0.5/live?channel=1&token=Hunter2", "token"),
                ("http://10.0.0.5/ISAPI/stream?auth=SHVudGVyMg==", "auth"),
                ("https://cam.example/v1/live?api_key=Hunter2", "api_key"),
                ("http://10.0.0.5/mjpg?loginuse=admin&loginpas=Hunter2", "loginuse"),
                ("rtsp://10.0.0.5/live;password=Hunter2", "password"),
                ("http://10.0.0.5/live?P%77D=Hunter2", "P%77D"),
                ("http://10.0.0.5/live?access-key=Hunter2&sig=Hunter2", "access-key")]


def test_a_credential_in_an_addresss_parameters_is_refused_and_a_stored_one_is_said_nowhere():
    """The eleventh review, blocker 4 — a run: `http://10.0.0.5/videostream.cgi?usr=admin&pwd=…` was 201 and `GET
    /cameras` handed the password to anybody who may view the camera, while `cred_secret` read `***`; the product's
    cross-check found every kind of key it tried taken, in the domain's snapshot, and raw in the log. Now a parameter
    whose NAME is a credential's (`secrets.is_credential_param`) is refused where a url field is written, the refusal
    names it and never its value; a query that carries none is taken; and a row stored before the rule shows no
    password on the page, in the snapshot, in the device's key, in a refusal or in the element's error."""
    from gstvms.uri import resolve
    from vms.config import device_of, shown_source
    from w2cplatform.secrets import hide_in_url
    box = Box()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    for src, named in CRED_QUERIES:
        try:
            con.create_camera({"name": "gate", "source": src})
            raise AssertionError(f"a credential rode in on the parameters: {src}")
        except Refused as e:
            assert named in str(e) and "Hunter2" not in str(e) and "SHVudGVyMg" not in str(e), str(e)
    assert con.cameras() == []
    ok = con.create_camera({"name": "nvr", "source": "rtsp://10.0.0.5/cam/realmonitor?channel=1&subtype=0"})
    assert ok["source"].endswith("?channel=1&subtype=0")             # a query that says what to send is a query
    try:                                                              # an edit is the same door
        con.update_camera(ok["id"], {"source": CRED_QUERIES[0][0]})
        raise AssertionError("an update let a credential in")
    except Refused:
        pass

    # …one stored before the rule (or by another build): said nowhere
    key = f"vms/cameras/{ok['id']}"
    items, idx = box.vars.get(key)
    box.vars.as_writer("console", SPEC.acl_console()).put(key, {**items, "source": CRED_QUERIES[0][0]}, cas=idx)
    srv = serve(con, box.archive, port=0, wall=box.wall)
    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/cameras").read().decode()
        upd = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/cameras/{ok['id']}", method="PUT",
                                     data=json.dumps({"name": "nvr 2"}).encode(), headers={"Idempotency-Key": "n2"})
        one = urllib.request.urlopen(upd).read().decode()            # the reply to an edit, kept for a retry
    finally:
        srv.shutdown()
    assert "Hunter2" not in page and "Hunter2" not in one and "videostream.cgi?usr=***&pwd=***" in page
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    ctl.publish_snapshot()
    assert "Hunter2" not in json.dumps(published_snapshot(box.objects, "vms"))
    for src, _ in CRED_QUERIES:
        assert "Hunter2" not in device_of(src) and "Hunter2" not in shown_source(src) and "Hunter2" not in hide_in_url(src)
        try:
            resolve(src)
            raise AssertionError("the element opened an address that is not a file")
        except ValueError as e:
            assert "Hunter2" not in str(e) and "SHVudGVyMg" not in str(e), str(e)


# A camera's login written every way the twelfth review, its probes and the product's cross-check found one written: the
# path (XMeye/Xiongmai `user=…_password=…`, `&`, `;`, name segments), the query (case, `%`-escapes once and twice, `+`,
# the names the list lacked), S3's signed forms, and a userinfo cut short by an unescaped `/`, `?`, `#` or an escaped `@`.
# The password is `Hunter2` (or a piece of it: `ter2`), or base64 of it.
LOGIN_FORMS = [
    "rtsp://10.0.0.9:554/user=admin_password=Hunter2_channel=1_stream=0.sdp?real_stream",
    "rtsp://10.0.0.9:554/user=admin&password=Hunter2&channel=1&stream=0.sdp",
    "rtsp://10.0.0.9:554/password=Hunter2&user=admin&channel=1&stream=0.sdp",
    "rtsp://10.0.0.9:554/user=admin_password=Hun_ter2_channel=1_stream=0.sdp",
    "rtsp://10.0.0.9:554/USER=admin_PASSWORD=Hunter2_CHANNEL=1",
    "rtsp://10.0.0.9/live;user=admin;pwd=Hunter2",
    "rtsp://10.0.0.9/live;user=admin;password=Hunter2/ch1",
    "http://10.0.0.5/cgi-bin/snapshot.cgi?usr=admin&pwd=Hunter2",
    "http://10.0.0.5/cgi-bin/snapshot.cgi?loginuse=admin&loginpas=Hunter2",
    "http://10.0.0.5/videostream.cgi?USR=admin&PWD=Hunter2",
    "http://10.0.0.5/videostream.cgi?Usr=admin&PassWord=Hunter2",
    "http://10.0.0.5/x.cgi?p%77d=Hunter2",
    "http://10.0.0.5/x.cgi?%2570wd=Hunter2",
    "http://10.0.0.5/x.cgi?pass%5Fword=Hunter2",
    "http://10.0.0.5/x.cgi?pwd+=Hunter2",
    "http://10.0.0.5/user/admin/password/Hunter2/snap.jpg",
    "http://10.0.0.5/snap.cgi?pw=Hunter2",
    "http://10.0.0.5/snap.cgi?psd=Hunter2",
    "http://10.0.0.5/snap.cgi?passwd=Hunter2",
    "http://10.0.0.5/snap.cgi?user_id=admin&pwd=Hunter2",
    "http://10.0.0.5/x?pwd=ab#Hunter2",
    "http://10.0.0.5/x#pwd=Hunter2",
    "http://10.0.0.5/x?token=SHVudGVyMg==",
    "https://s3.example.com/b/o?X-Amz-Credential=AKIA%2F20261004&X-Amz-Signature=Hunter2",
    "https://s3.example.com/b/o?X-Amz-Signature=Hunter2",
    "https://s3.example.com/b/o?AWSAccessKeyId=AKIA&Signature=Hunter2&Expires=1",
    "https://s3.example.com/b/o?aws_secret_access_key=Hunter2",
    "https://h/x?secret=Hunter2",
    "https://h/x?access_key=Hunter2",
    "https://h/x?access_token=Hunter2",
    "rtsp://admin:Hunter2@10.0.0.5/s",
    "rtsp://:Hunter2@10.0.0.5/s",
    "rtsp://admin:Hunter2%40cam/s",
    "rtsp://admin:Hun/ter2@10.0.0.5/s",
    "rtsp://admin:Hun?ter2@10.0.0.5/s",
    "rtsp://admin:Hun#ter2@10.0.0.5/s",
    "rtsp://admin:Hun+ter2=@10.0.0.5/s",
    "rtsp://admin:12/ter2@10.0.0.5/s",
    "rtsp://admin:Hunter2＠cam/s",
    "driverpack://acme/admin:Hunter2@10.0.0.5/ch/1",
    "driverpack://acme/10.0.0.5;password=Hunter2/ch/1",
    "driverpack://acme/10.0.0.5/ch/1?pwd=Hunter2",
    "onvif://10.0.0.5/?pwd=Hunter2",
]
# …and addresses that carry none, as cameras are commonly reached: taken, and said as typed.
PLAIN_FORMS = [
    "rtsp://10.0.0.5:554/cam/realmonitor?channel=1&subtype=0",
    "rtsp://10.0.0.5/Streaming/Channels/101?transportmode=unicast",
    "rtsp://10.0.0.5/h264/ch1/main/av_stream",
    "rtsp://10.0.0.5/onvif-media/media.amp?profile=profile_1_h264&sessiontimeout=60&streamtype=unicast",
    "rtsp://10.0.0.5/axis-media/media.amp?videocodec=h264&resolution=640x480",
    "rtsp://10.0.0.9:554/channel=1_stream=0.sdp?real_stream",
    "http://10.0.0.5/cgi-bin/auth/snapshot.jpg",
    "rtsp://[fe80::1]:554/live",
    "driverpack://acme/10.0.0.50/ch/17",
]


def _leaks(text) -> bool:
    return any(m in str(text) for m in ("Hunter2", "ter2", "SHVudGVyMg"))


def test_a_login_in_any_part_of_an_address_is_refused_and_a_stored_one_is_said_nowhere():
    """The twelfth review, blocker 8 — a run: `rtsp://10.0.0.9:554/user=admin_password=…_channel=1_stream=0.sdp`, how
    XMeye/Xiongmai recorders and many cheap cameras take their login, was 201, and the password stood in the reply,
    `GET /cameras`, the snapshot and the device's key (`device_of`: the heartbeat, `/devices`, `vms/requests/*`); of the
    review's 38 spellings 16 were said as stored (and the product's own detection caught 10 of 38). Pairs are read in
    path segments and in `_` chains now (`secrets._pairs`), a password's name segment gives the next one, the list has
    `pw`, `psd`, `user_id`, `X-Amz-Signature`, `AWSAccessKeyId`, escapes are undone to the end, and a port that is no
    number is hidden. Every form of `LOGIN_FORMS` is refused at create and at an edit in words that never quote it; put
    in the store as an older build would have, it is said by no reader — the page, the snapshot, `device_of`,
    `shown_source`, the element's refusal, a command's reply and its row. Every form of `PLAIN_FORMS` is taken and said
    as typed."""
    from gstvms.uri import resolve
    from vms.config import device_of, shown_source, source_refusal
    from w2cplatform.secrets import address_refusal, credential_params, hide_in_url
    from tests.test_console_gate import _call, _console
    box = Box()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    refused = 0
    for src in LOGIN_FORMS:
        try:
            con.create_camera({"name": "c", "source": src})
        except Refused as e:
            assert not _leaks(e), (src, str(e))
            refused += 1
        assert address_refusal(src) and not _leaks(address_refusal(src)) and not _leaks(credential_params(src)), src
    assert refused == len(LOGIN_FORMS) == 43, f"{refused} of {len(LOGIN_FORMS)} refused"
    assert con.cameras() == []
    for src in PLAIN_FORMS:
        assert address_refusal(src) is None and hide_in_url(src) == src, src
    made = [con.create_camera({"name": f"p{i}", "source": src}) for i, src in enumerate(PLAIN_FORMS)]
    assert [m["source"] for m in made] == PLAIN_FORMS
    try:
        con.update_camera(made[0]["id"], {"source": LOGIN_FORMS[0]})
        raise AssertionError("an edit let a login in")
    except Refused as e:
        assert not _leaks(e)

    # …one stored before the rule: said nowhere. Every form, in turn, as camera `made[0]`'s source.
    ctl2, rec, m, srv, base = _console(box)
    key = f"vms/cameras/{made[0]['id']}"
    writer = box.vars.as_writer("console", SPEC.acl_console())
    snap = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    said = 0
    try:
        for src in LOGIN_FORMS:
            items, idx = box.vars.get(key)
            writer.put(key, {**items, "source": src}, cas=idx)
            st, page = _call(base, "GET", "/cameras")
            st2, cmd = _call(base, "POST", "/requests", {"unit": str(made[0]["id"]), "action": "output", "port": "1",
                                                         "state": "on"})
            snap.publish_snapshot()
            element = ""
            try:
                resolve(src)
            except ValueError as e:
                element = str(e)
            outs = [page, cmd, published_snapshot(box.objects, "vms"), device_of(src), shown_source(src), hide_in_url(src),
                    mask_secrets([{"source": src}]), source_refusal(src), element]
            assert st == 200 and st2 == 202 and not any(_leaks(json.dumps(o, default=str)) for o in outs), (src, outs)
            said += 1
    finally:
        srv.shutdown()
    assert said == len(LOGIN_FORMS)
    rows = [box.vars.get(k)[0] for k in box.vars.list("vms/requests/")]
    assert rows and not _leaks(json.dumps(rows))


def test_a_refusal_never_quotes_a_password_and_the_idempotency_copy_keeps_none():
    """The twelfth review, major 16 — a run: `rtsp://admin:Hunter2?x@…` (a password with an unescaped `?`, `#` or `/`)
    is read by `urlsplit` as host `admin`, port `Hunter2`, and the refusal said `…is not an address: Port could not be
    cast to integer value as 'Hunter2'` — in the reply, and in the reply's copy under its `Idempotency-Key`
    (`vms/idem/*`, 4 of 5). The words name what is wrong and never the value (`secrets.NOT_AN_ADDRESS`), at the spec's
    refusal, at `source_refusal` and at the element; and the idempotency copy says every address in a reply as a page
    does (`IdempotencyKeys.store` → `hide_in_reply`), whatever the reply that came to it — the sibling the review did
    not name."""
    from w2cplatform.console import IdempotencyKeys
    from tests.test_console_gate import _call, _console
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        cam = _call(base, "POST", "/cameras", {"name": "c", "source": "rtsp://10.0.0.5/s"})[1]
        for src in ("rtsp://admin:Hunter2?x@10.0.0.5/s", "rtsp://admin:Hunter2#x@10.0.0.5/s",
                    "rtsp://admin:Hunter2/x@10.0.0.5/s", "rtsp://admin:Hunter2%40h/s", "rtsp://admin:Hunter2＠h/s",
                    "rtsp://admin:Hunter2@10.0.0.5:554/s"):
            st, b = _call(base, "POST", "/cameras", {"name": "c", "source": src})
            st2, b2 = _call(base, "PUT", f"/cameras/{cam['id']}", {"source": src})
            assert st == st2 == 400 and not _leaks(b) and not _leaks(b2), (src, b, b2)
        st, ev = _call(base, "GET", f"/events?from=0&to={box.wall() + 1}")
        assert not _leaks(ev)
    finally:
        srv.shutdown()
    kept = [box.vars.get(k)[0] for k in box.vars.list("vms/idem/")]
    assert len(kept) >= 6 and not _leaks(json.dumps(kept))

    # …and whatever reply reaches the copy, it keeps no address as typed.
    seen = IdempotencyKeys(box.vars.as_writer("console", SPEC.acl_console()), "vms/idem/", box.wall)
    assert seen.claim("raw") is None
    seen.store("raw", (400, {"detail": "rtsp://admin:Hunter2@h/user=a_password=Hunter2_channel=1 is not taken",
                             "rows": [{"source": "http://h/x?pwd=Hunter2"}]}))
    assert not _leaks(json.dumps(box.vars.get("vms/idem/raw")[0]))
    assert seen.claim("raw")[0] == 400


def test_hiding_a_login_is_one_scan_of_the_address_whatever_its_length():
    """The pairs of the path and the chains (the twelfth review) are read by position, in one pass: an address of
    100 000 characters of each kind the regexes once choked on is hidden, refused and keyed in well under a second."""
    import time
    from vms.config import device_of
    from w2cplatform.secrets import address_refusal, hide_in_url
    n = 100_000
    for body in ("/" * n, "&" * n, "=" * n, ";" * n, "@" * n, "_=" * (n // 2), "a=b_" * (n // 4), "/pwd" * (n // 4)):
        src = "rtsp://10.0.0.5/x" + body
        t = time.monotonic()
        hide_in_url(src), address_refusal(src), device_of(src)
        assert time.monotonic() - t < 1.0, body[:8]
