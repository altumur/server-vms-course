"""A device needs a login and a password; the platform's job is to let exactly
two parties see the second one — the operator who writes it and the worker that
opens the camera — and nobody in between."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from vms.config import SPEC
from vms.console import serve
from vms.controller import VmsController
from w2cplatform.secrets import SECRET_MASK, is_secret_field, mask_secrets
from w2cplatform.spec import Refused, SubsystemSpec
from tests.vmsconftest import Box, published_snapshot


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
    base = {"name": "x", "unit": {"fields": {"host": {"type": "string"}, "api_secret": {"type": "string"}}}, "placement": {"capacity": {"from": "capacity", "default": 4}}}
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
            assert "carries a login" in str(e) and "hunter2" not in str(e)
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
    srv = serve(con, box.resource_root, port=0, wall=box.wall)
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
    srv = serve(con, box.resource_root, port=0, wall=box.wall)
    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/cameras").read().decode()
        upd = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/cameras/{ok['id']}", method="PUT",
                                     data=json.dumps({"name": "nvr 2"}).encode(), headers={"Idempotency-Key": "n2"})
        one = urllib.request.urlopen(upd).read().decode()            # the reply to an edit, kept for a retry
    finally:
        srv.shutdown()
    # the password hidden, the login said: it identifies (`secret_in.login`, the final form)
    assert "Hunter2" not in page and "Hunter2" not in one and "videostream.cgi?usr=admin&pwd=***" in page
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
            st2, cmd = _call(base, "POST", "/requests", {"unit": f"vms/{made[0]['id']}", "action": "output", "port": "1",
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
    """The pairs of the path and the chains (the twelfth review) are read by position, in one pass, and so are the
    hosts and the addresses nested in a parameter (the thirteenth): an address ten times longer costs about ten times
    as much — for each kind of body the regexes once choked on, a run with no `@` among them. Measured as a RATIO of
    the best of a few runs at 100 000 and at 10 000 characters, in the process's own CPU time with the collector held,
    not as a wall time: the suite runs on a loaded machine too, and a bound in seconds failed there (the coordinator,
    the thirteenth round). One scan is about 10; a scan from every position, as the unanchored `[^/@]*@` was, is
    about 100 — the bound, 35, keeps both apart."""
    import gc
    import time
    from vms.config import device_of
    from w2cplatform.secrets import address_refusal, hide_in_url

    def cost(body: str, runs: int) -> float:
        best = float("inf")
        for r in range(runs):                                    # another host each run: no reader's cache answers it
            src = f"rtsp://10.0.{r}.5/x" + body
            gc.collect()
            gc.disable()                                         # a collection's cost is the heap's, not the scan's
            try:
                t = time.process_time()                          # CPU time: the other processes' load is not ours
                hide_in_url(src), address_refusal(src), device_of(src)
                best = min(best, time.process_time() - t)
            finally:
                gc.enable()
        return best

    kinds = (lambda n: "/" * n, lambda n: "&" * n, lambda n: "=" * n, lambda n: ";" * n, lambda n: "@" * n,
             lambda n: "x" * n, lambda n: "_=" * (n // 2), lambda n: "a=b_" * (n // 4), lambda n: "/pwd" * (n // 4),
             lambda n: "/%41" * (n // 4), lambda n: "?a=x%3A%2F%2F" * (n // 13), lambda n: "&a=x://" * (n // 7))
    for kind in kinds:
        small, big = cost(kind(10_000), 5), cost(kind(100_000), 3)
        assert big / max(small, 1e-6) < 35, (kind(8), small, big)


# The thirteenth review's probes: an address inside a parameter (go2rtc's `?src=`), escaped once, twice and not at all, in
# a query and in a path segment; and a host in the path whose port is a password (`driverpack://`), with the vendor's and
# the host's pairs a row stored before the rules may hold.
NESTED_FORMS = [
    "http://proxy/relay?src=rtsp%3A%2F%2Fadmin%3AHunter2%40cam%2Fs",
    "http://proxy/relay?src=rtsp://admin:Hunter2@cam/s",
    "http://proxy/relay?src=http%3A%2F%2Fcam%2Fx.cgi%3Fusr%3Dadmin%26pwd%3DHunter2",
    "http://proxy/relay?src=http%253A%252F%252Fp2%252F%253Fsrc%253Drtsp%25253A%25252F%25252Fadmin%25253AHunter2%252540cam",
    "http://proxy/rtsp%3A%2F%2Fadmin%3AHunter2%40cam%2Fs",
    "http://proxy/x;src=rtsp%3A%2F%2Fcam%2Fs%3Fuser%3Dadmin_password%3DHunter2",
]
HOST_IN_PATH_FORMS = [
    "driverpack://acme/admin:Hunter2%4010.0.0.5/ch/1",
    "driverpack://acme/10.0.0.5:Hunter2/ch/1",
    "driverpack://acme/admin:Hunter2/ch/1",
    "driverpack://acme:Hunter2/10.0.0.5/ch/1",
    "driverpack://acme/10.0.0.5&password=Hunter2/ch/1",
    "driverpack://acme/10.0.0.5_pwd=Hunter2/ch/1",
    "driverpack://acme;pwd=Hunter2/10.0.0.5/ch/1",
    "driverpack://acme/pwd=Hunter2/ch/1",
]
# …and the review's 38 ordinary addresses (`probe_false_positives.py`): 8 of them were refused by a stem found inside
# another word (`token_bucket`, `passage`, `authmode`, `bypass`, `compass`, a path segment `pass` or `pw`).
FALSE_FRIENDS = [
    "rtsp://10.0.0.5/Streaming/Channels/101", "rtsp://10.0.0.5/streaming/channels/101",
    "rtsp://10.0.0.5:554/cam/realmonitor?channel=1&subtype=0", "rtsp://10.0.0.5/h264/ch1/main/av_stream",
    "rtsp://10.0.0.5/live?token_bucket=10", "http://10.0.0.5/keypad/snapshot.jpg", "http://10.0.0.5/passage/cam1.mjpg",
    "http://10.0.0.5/authority/live.sdp", "rtsp://10.0.0.5/passage=north_channel=1", "rtsp://10.0.0.5/live?passage=north",
    "rtsp://10.0.0.5/live?authmode=digest", "rtsp://10.0.0.5/live?bypass=1",
    "http://10.0.0.5/axis-cgi/mjpg/video.cgi?resolution=640x480&compression=30", "rtsp://10.0.0.5/onvif1",
    "rtsp://10.0.0.5:554/11", "rtsp://10.0.0.5/MediaInput/h264/stream_1",
    "rtsp://10.0.0.5/Streaming/Channels/101?transportmode=multicast&profile=Profile_1",
    "http://10.0.0.5/cgi-bin/mjpg/video.cgi?channel=1&subtype=1", "rtsp://10.0.0.5/user_stream=1",
    "rtsp://10.0.0.5/live/ch00_0", "rtsp://10.0.0.5/0/video1", "rtsp://10.0.0.5/stream1?keyframe=1",
    "rtsp://10.0.0.5/stream1?keyint=25", "rtsp://10.0.0.5/stream1?sessiontimeout=60",
    "rtsp://10.0.0.5/stream1?accountless=1", "rtsp://10.0.0.5/videoMain?usrname_hint=0",
    "rtsp://10.0.0.5/live/pass/stream", "rtsp://10.0.0.5/pw/1", "rtsp://10.0.0.5/live.sdp?compass=1",
    "http://10.0.0.5/snapshot.cgi?chn=1&u=1", "rtsp://10.0.0.5/av0_0", "rtsp://10.0.0.5/ch01.264?dev=1",
    "rtsp://10.0.0.5/tcp/av0_0", "rtsp://10.0.0.5/cam1/h264?key_frame_interval=2",
    "rtsp://10.0.0.5/stream?apikey_required=false", "rtsp://10.0.0.5/live?sid_hint=1",
    "http://10.0.0.5/webcapture.jpg?command=snap&channel=1", "driverpack://acme/10.0.0.50/ch/17",
    # the product's own false refusals, and a relay told to fetch an address with no login in it
    "rtsp://10.0.0.5/live?monkey=1", "rtsp://10.0.0.5/live?hotkey=F1", "http://proxy/relay?src=rtsp%3A%2F%2Fcam%2Fs",
]


def test_an_address_inside_a_parameter_is_an_address_and_a_camera_asks_the_platforms_one_rule():
    """The thirteenth review, blocker 6 — a run: `http://proxy/relay?src=rtsp%3A%2F%2Fadmin%3A…%40cam%2Fs`, how a relay
    like go2rtc is told what to fetch, was 201: the camera's rule was its own copy (`SubsystemSpec.refuse`, `@` read in
    the netloc and the path), and the password stood in the row, `GET /cameras`, the reply to an edit, the snapshot and
    the device's key; unescaped, it was 201 too, hidden on the page but in the row in the clear. Now the camera asks
    `secrets.address_refusal`, which reads a value that is an address once unescaped as an address (`_nested`, three
    levels; deeper is refused for that alone). Every form is refused at create and at an edit, through the console, in
    words that never say it, and no idempotency copy keeps it; the sibling door that asks the same rule — a volume's
    url — refuses it too (the domain's: М12's suite); a stored one is said by no reader; a relay told to fetch an
    address with no login in it is taken."""
    from tests.test_console_gate import _call, _console
    from vms.config import device_of
    from vms.volumes import write as declare_volume       # the spec's table rules (`tables.volumes`, step 6)
    from w2cplatform.secrets import address_refusal, hide_in_url
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        cam = _call(base, "POST", "/cameras", {"name": "c", "source": "rtsp://10.0.0.5/s"})[1]
        for src in NESTED_FORMS:
            st, b = _call(base, "POST", "/cameras", {"name": "relay", "source": src})
            st2, b2 = _call(base, "PUT", f"/cameras/{cam['id']}", {"source": src})
            assert st == st2 == 400 and not _leaks(b) and not _leaks(b2), (src, b, b2)
            assert address_refusal(src) and not _leaks(address_refusal(src)) and not _leaks(hide_in_url(src)), src
            assert not _leaks(device_of(src)), src
        ok = _call(base, "POST", "/cameras", {"name": "relay", "source": "http://proxy/relay?src=rtsp%3A%2F%2Fcam%2Fs"})
        assert ok[0] == 201 and ok[1]["source"] == "http://proxy/relay?src=rtsp%3A%2F%2Fcam%2Fs"
        # …a stored one (an older build's): said by no reader
        key = f"vms/cameras/{cam['id']}"
        writer = box.vars.as_writer("console", SPEC.acl_console())
        snap = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
        for src in NESTED_FORMS:
            items, idx = box.vars.get(key)
            writer.put(key, {**items, "source": src}, cas=idx)
            page = _call(base, "GET", "/cameras")[1]
            one = _call(base, "PUT", f"/cameras/{cam['id']}", {"name": "c2"})[1]
            snap.publish_snapshot()
            assert not _leaks(page) and not _leaks(one) and not _leaks(published_snapshot(box.objects, "vms")), src
    finally:
        srv.shutdown()
    assert box.vars.list("vms/idem/") and not _leaks(json.dumps([box.vars.get(k)[0] for k in box.vars.list("vms/idem/")]))
    for src in NESTED_FORMS:                                     # the sibling door on the same rule: a volume's url
        try:
            declare_volume(Box().vars, {"name": "cold", "kind": "network", "url": src, "quota_bytes": 1})
            raise AssertionError(f"a volume took {src}")
        except Refused as e:
            assert not _leaks(e), str(e)
    deep = "rtsp://cam/s"                                        # bounded: nested deeper than it reads is refused
    for _ in range(5):
        deep = "http://proxy/relay?src=" + urllib.parse.quote(deep, safe="")
    assert "more than 3 deep" in (address_refusal(deep) or "") and hide_in_url(deep).endswith("src=***")


def test_a_host_in_the_path_is_read_for_its_port_and_neither_a_refusal_nor_a_device_key_says_the_password():
    """The thirteenth review, majors 8 and 9 — runs: `driverpack://acme/admin:Hunter2%4010.0.0.5/ch/1` was 400 with the
    password in the words ("the port in '…:Hunter2…' is not a port"), kept a day in `vms/idem/*`: `driverpack://` names
    its host in the path, where `hide_in_url` did not look for a port. And a row stored before the rules
    (`acme:hunter2/10.0.0.5`, `acme/10.0.0.5&password=hunter2`) kept the password in its device key (`device_of`) — in
    `POST /requests`, `vms/requests/*`, the heartbeat and `vms/devices/<key>`. Now the host in the path is read for its
    port (`secrets._hosts`) where an address is refused and where it is said, `source_refusal` quotes no address, and
    `device_of` says its key as a page says an address. A key with nothing in it is the key it was."""
    from tests.test_console_gate import _call, _console
    from vms.config import device_of, source_refusal
    from w2cplatform.secrets import address_refusal, hide_in_url
    for src in HOST_IN_PATH_FORMS:
        assert address_refusal(src) and not _leaks(address_refusal(src)) and not _leaks(hide_in_url(src)), src
        assert not _leaks(device_of(src)) and not _leaks(source_refusal(src) or ""), (src, device_of(src))
    assert device_of("driverpack://acme/10.0.0.50/ch/17") == "acme/10.0.0.50"
    assert device_of("driverpack://Acme/10.0.0.50:8000/ch/1") == "acme/10.0.0.50:8000"
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        cam = _call(base, "POST", "/cameras", {"name": "c", "source": "driverpack://acme/10.0.0.50/ch/1"})[1]
        for src in HOST_IN_PATH_FORMS:
            st, b = _call(base, "POST", "/cameras", {"name": "c", "source": src})
            st2, b2 = _call(base, "PUT", f"/cameras/{cam['id']}", {"source": src})
            assert st == st2 == 400 and not _leaks(b) and not _leaks(b2), (src, b, b2)
        key = f"vms/cameras/{cam['id']}"
        writer = box.vars.as_writer("console", SPEC.acl_console())
        for src in HOST_IN_PATH_FORMS:                           # stored by an older build: the device key says none
            items, idx = box.vars.get(key)
            writer.put(key, {**items, "source": src}, cas=idx)
            st, cmd = _call(base, "POST", "/requests", {"unit": f"vms/{cam['id']}", "action": "output", "port": "1", "state": "on"})
            assert st == 202 and not _leaks(cmd) and not _leaks(_call(base, "GET", "/cameras")[1]), (src, cmd)
    finally:
        srv.shutdown()
    kept = [box.vars.get(k)[0] for k in box.vars.list("vms/idem/") + box.vars.list("vms/requests/")]
    assert kept and not _leaks(json.dumps(kept))


def test_a_credentials_name_is_read_by_whole_words_and_every_listed_form_goes_the_right_way():
    """The thirteenth review, minor — a run: the stems of the rule were matched anywhere in a name, and 8 of the review's
    38 ordinary addresses were refused (`?token_bucket=`, `/passage=north_channel=1`, `?authmode=`, `?bypass=`,
    `?compass=`, a path segment `pass` or `pw`); the product found `?monkey=` and `?hotkey=` refused in its own. The
    name is read as words now (`secrets.is_credential_param`). Both ways, counted: every form of `LOGIN_FORMS`,
    `NESTED_FORMS` and `HOST_IN_PATH_FORMS` refused, every form of `FALSE_FRIENDS` and `PLAIN_FORMS` taken and said as
    typed — at the rule and at a camera's create."""
    from w2cplatform.secrets import address_refusal, hide_in_url, is_credential_param, is_login_param
    bad = LOGIN_FORMS + NESTED_FORMS + HOST_IN_PATH_FORMS
    good = FALSE_FRIENDS + PLAIN_FORMS
    refused = [s for s in bad if address_refusal(s)]
    taken = [s for s in good if address_refusal(s) is None and hide_in_url(s) == s]
    assert (len(refused), len(taken)) == (len(bad), len(good)) == (57, 50), \
        (sorted(set(bad) - set(refused)), sorted(set(good) - set(taken)))
    box = Box()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    for i, s in enumerate(good):                                 # one at a time: two of them are one channel spelt twice
        made = con.create_camera({"name": f"f{i}", "source": s})
        assert made["source"] == s
        con.delete(made["id"])
    # the names, word by word: a credential's — and a word that only begins a name, or `pass` glued at its end, is not
    for n in ("pwd", "PassWord", "pass_word", "access_token", "authToken", "X-Amz-Signature",
              "aws_secret_access_key", "api_key", "pwd_md5", "userpwd", "clientsecret", "ｐｗｄ",
              "Authorization", "session_id", "passcode", "loginpas"):
        assert is_credential_param(n) and not is_login_param(n), n
    # …a login's: refused, said — an access key's id among them (the product's decision: the id of a key is no key)
    for n in ("user_id", "usr", "user", "User-Name", "loginuse", "login", "account", "AWSAccessKeyId", "accessKeyId",
              "uname"):
        assert is_login_param(n) and not is_credential_param(n), n
    for n in ("token_bucket", "passage", "authmode", "auth_mode", "bypass", "compass", "passthrough", "monkey", "hotkey",
              "keyframe", "key_frame_interval", "apikey_required", "sid_hint", "usrname_hint", "user_stream", "authority",
              "sessiontimeout", "accountless", "channel", "u"):
        assert not is_credential_param(n), n


def test_the_idempotency_claim_keeps_no_digest_a_dictionary_can_turn_back_into_the_password():
    """The thirteenth review, major 7 — a run: the camera's row held `cred_secret` sealed, and the idempotency claim
    beside it (`vms/idem/<key>`, a day) held the sha256 of the raw body; `admin123` and `qwerty2024` came back from it
    with a dictionary of seven words. Now, with the cluster's key ring, the claim holds an HMAC under a key derived
    from the ring's (`Sealer.mac`), which the store never sees; without one, the sha256 of the body as a page says it
    (`*_secret` masked, addresses hidden). Either way the dictionary finds nothing; the same body under the same key is
    still the same request — on another console holding the same ring, and on one a rotation ahead (the kid names the
    key) — and another body is still 422. And on a console whose ring no longer holds the claim's kid, the masked digest
    kept beside the HMAC answers (the product's r28-secrets2)."""
    import hashlib
    import os
    from tests.test_sealing import _key
    from w2cplatform.console import IdempotencyKeys
    from w2cplatform.sealing import Sealer, is_sealed
    words = ["12345", "admin", "password", "admin123", "Hunter2", "qwerty2024", "888888"]

    def reversed_(claims, row):
        found = []
        for v in claims:
            digests = {str(v.get(k, "")).split(":")[-1] for k in ("mac", "digest", "sha256")}
            for w in words:
                for body in ({"cred_secret": w}, {"name": row["name"], "source": row["source"],
                                                  "cred_username": row["cred_username"], "cred_secret": w}):
                    for text in (json.dumps(body), json.dumps(body, sort_keys=True)):
                        if hashlib.sha256(text.encode()).hexdigest() in digests:
                            found.append(w)
        return found

    for keyed in (True, False):
        box = Box()
        if keyed:
            os.environ["SECRETS_KEY"] = _key("k1")
        try:
            con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
        finally:
            os.environ.pop("SECRETS_KEY", None)
        srv = serve(con, box.resource_root, port=0, wall=box.wall)
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def send(method, path, body, k):
            req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method=method,
                                         headers={"Idempotency-Key": k, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())
        try:
            first = {"name": "gate", "source": "driverpack://file/gate.mp4", "cred_username": "admin", "cred_secret": "admin123"}
            made = send("POST", "/cameras", first, "s1")
            assert made[0] == 201 and send("POST", "/cameras", first, "s1") == made       # a retry: the same reply
            assert send("POST", "/cameras", {**first, "name": "yard"}, "s1")[0] == 422      # another body under it
            # …another password alone is another body only to a digest that holds it: with a key. Without one the
            # digest holds no secret, and a retry with another password is the first request — said, not a hole: the
            # first reply, no second camera
            again = send("POST", "/cameras", {**first, "cred_secret": "x"}, "s1")
            assert again[0] == 422 if keyed else again == made
            assert send("PUT", "/cameras/1", {"cred_secret": "qwerty2024"}, "s2")[0] == 200
        finally:
            srv.shutdown()
        row = box.vars.get("vms/cameras/1")[0]
        claims = [box.vars.get(k)[0] for k in box.vars.list("vms/idem/")]
        assert is_sealed(row["cred_secret"]) == keyed and len(con.cameras()) == 1
        assert all(("mac" in c) == keyed and "digest" in c and "sha256" not in c for c in claims), claims
        assert reversed_(claims, row) == [], reversed_(claims, row)

    # …and across consoles: one ring, a rotation ahead, and a ring without the claim's kid
    k1, k2 = os.urandom(32), os.urandom(32)
    box = Box()
    w = box.vars.as_writer("console", SPEC.acl_console())
    a = IdempotencyKeys(w, "vms/idem/", box.wall, sealer=Sealer({"k1": k1}, "k1"))
    ahead = IdempotencyKeys(w, "vms/idem/", box.wall, sealer=Sealer({"k1": k1, "k2": k2}, "k2"), sleep=lambda s: None)
    other = IdempotencyKeys(w, "vms/idem/", box.wall, sealer=Sealer({"k3": k2}, "k3"), sleep=lambda s: None)
    body = json.dumps({"name": "gate", "cred_secret": "admin123"}).encode()
    assert a.claim("r1", "anna", body) is None
    a.store("r1", (201, {"id": 1}))
    assert box.vars.get("vms/idem/r1")[0]["mac"].startswith("k1:")
    assert ahead.claim("r1", "anna", body) == (201, {"id": 1})                  # the same request, by the kid it names
    assert ahead.claim("r1", "anna", body + b" ")[0] == 422                      # another body
    # …and a ring whose kid was REMOVED within the claim's day (the product's r28-secrets2): the claim's `mac` is one no
    # console can make any more, and a correct retry was 422. The masked digest beside it answers then — the same body,
    # the first reply; another body, 422 still. A claim with no digest and a kid gone is not answered.
    assert other.claim("r1", "anna", body) == (201, {"id": 1})
    assert other.claim("r1", "anna", json.dumps({"name": "yard", "cred_secret": "admin123"}).encode())[0] == 422
    assert other.claim("r1", "boris", body)[0] == 422                            # another caller: never
    items, idx = box.vars.get("vms/idem/r1")
    box.vars.put("vms/idem/r1", {k: v for k, v in items.items() if k != "digest"}, cas=idx)
    assert other.claim("r1", "anna", body)[0] == 422


# The product's r28-secrets2 defects, checked in the course: refused, and said by no reader.
R28_FORMS = [
    "http://h:1984/api/stream.mp4?src=rtsp://admin:Hunter2@cam",
    "http://h:1984/api/stream.mp4?src=rtsp://admin:Hunter2@cam:554/live",
    "http://h:1984/api/stream.mp4?src=rtsp://cam/live?pwd=Hunter2",
    "http://h:1984/proxy/rtsp%3A%2F%2Fadmin%3AHunter2%40cam/live",
    "http://h/proxy/rtsp%3A//admin%3AHunter2%40cam/live",
    "rtsp://10.0.0.5/live?pass%3DHunter2=1",
    "rtsp://10.0.0.5/live?x=1&pwd%3DHunter2%26a=1",
    "rtsp://10.0.0.5/live?psk=Hunter2", "rtsp://10.0.0.5/live?wpa_psk=Hunter2", "rtsp://10.0.0.5/live?privkey=Hunter2",
    "rtsp://10.0.0.5/live?\uff50\uff41\uff53\uff53\uff57\uff4f\uff52\uff44=Hunter2",
    "rtsp://10.0.0.5/live?pa\u017f\u017fword=Hunter2",
    "rtsp://10.0.0.5/live?pass\u200bword=Hunter2", "rtsp://10.0.0.5/live?\U0001d429\U0001d430\U0001d41d=Hunter2",
    "rtsp://10.0.0.5/live?\u24df\u24e6\u24d3=Hunter2",
]


def test_the_products_second_secrets_pass_finds_nothing_in_the_course():
    """The product's r28-secrets2, checked here — runs of each form. (1) go2rtc with a port: `http://h:1984/…?src=
    rtsp://admin:…@cam` was refused, but said with ITS port masked (`h:***`): an `@` anywhere after the host made the
    port a secret, and the inner address's `@` is not the outer's. (2) An `@` in the query was read as the end of a
    login from the path's first segment on: `rtsp://10.0.0.5:554/live?x=y@b` was said `10.0.0.5:***/…@b`. (3) A key
    escaped inside a name, `?pass%3D…=1`, was taken: the name read as one word. Now it is two — a credential's — and the
    refusal names `pass`, never the decoded rest. (4) Credential names the rule did not know: `psk`, `wpa_psk`, `privkey`
    (fullwidth, `ſ`, a zero-width space, mathematical and circled letters were known — NFKC and the format characters).
    (5) False refusals: `?rtsp_auth=`, `?enable_auth=`, `x-auth`, `basic_auth` name how a device authenticates, not what
    with — decided as the product: not a credential; `auth` alone still is. (6) A legacy `driverpack://acme/<login>@
    <host>/ch/<n>` whose password holds a `/`, or a login in the vendor's place, gave an odd device key and no channel —
    the channels of one recorder split: the key is the host without the login. (7) An address escaped WHOLE — no `://`
    to see — was no address: refused now inside a list as anywhere, and said masked."""
    from vms.config import channel_key, device_of
    from w2cplatform.secrets import address_refusal, hide_in_url, is_credential_param, refusal_within
    for src in R28_FORMS:
        why = address_refusal(src)
        assert why and not _leaks(why) and not _leaks(hide_in_url(src)), (src, why, hide_in_url(src))
        assert not _leaks(mask_secrets([{"source": src}])), src
    assert hide_in_url(R28_FORMS[0]) == "http://h:1984/api/stream.mp4?src=***"
    assert hide_in_url(R28_FORMS[1]) == "http://h:1984/api/stream.mp4?src=***"
    assert hide_in_url("rtsp://10.0.0.5:554/live?x=y@b") == "rtsp://10.0.0.5:554/live?x=y@b"   # a login: said
    # …a userinfo's login is said, its password not
    # …a userinfo's password runs to the last `@`: more masked, never less (the product's reading)
    assert hide_in_url("rtsp://a:Hunter2@10.0.0.5:554/live?x=y@b") == "rtsp://a:***@b"
    assert "pass" in address_refusal("rtsp://10.0.0.5/live?pass%3DHunter2=1")
    for n in ("psk", "wpa_psk", "WPA-PSK", "privkey", "private_key", "auth", "Authorization"):
        assert is_credential_param(n), n
    for n in ("rtsp_auth", "enable_auth", "x-auth", "basic_auth", "gpio_pin", "auth_mode"):
        assert not is_credential_param(n), n
    for src in ("rtsp://10.0.0.5/live?rtsp_auth=1", "rtsp://10.0.0.5/live?enable_auth=0", "http://10.0.0.5/io?gpio_pin=3",
                "rtsp://10.0.0.5/live?basic_auth=1", "http://h:1984/api/stream.mp4?src=rtsp%3A%2F%2Fcam%3A554%2Flive"):
        assert address_refusal(src) is None and hide_in_url(src) == src, src
    for src in ("driverpack://acme/admin:Hun/ter2@10.0.0.5/ch/1", "driverpack://admin:Hunter2@acme/10.0.0.5/ch/1",
                "driverpack://acme/admin:Hunter2@10.0.0.5/ch/1", "driverpack://acme/10.0.0.5/ch/1"):
        assert (device_of(src), channel_key(src)) == ("acme/10.0.0.5", "1"), (src, device_of(src), channel_key(src))
    whole = "rtsp%3A%2F%2Fadmin%3AHunter2%40cam%2Fs"
    for value in (whole, [whole], {"a": [whole]}):
        where, why = refusal_within({"source": value})
        assert where.startswith("source") and why and not _leaks(where + why), (value, where, why)
        assert not _leaks(json.dumps(mask_secrets([{"source": value}])))
    assert refusal_within({"source": ["rtsp%3A%2F%2Fcam%2Fs"], "note": "50%25 off"}) is None


def test_a_value_inside_a_list_or_an_object_is_asked_and_masked_all_the_way_down():
    """The thirteenth review, minor — a run (М12): only a value that was a string was asked, and `{"source":
    ["rtsp://admin:…@…"]}` was 202, kept, applied on the camera and published as typed. `secrets.refusal_within` asks
    every string inside a list or an object (and a key that is an address), naming the place and never the value;
    `mask_secrets` hides an address and masks a `*_secret` at any depth. The domain's door and a camera's own console
    ask it (М12's suite, `test_domain_door.py`)."""
    from w2cplatform.secrets import refusal_within
    for value in (["rtsp://admin:Hunter2@10.0.0.5/s"], {"url": "http://h/x?pwd=Hunter2"},
                  {"a": [{"b": "http://proxy/relay?src=rtsp%3A%2F%2Fadmin%3AHunter2%40cam"}]},
                  {"rtsp://admin:Hunter2@h/s": 1}):
        where, why = refusal_within({"source": value})
        assert where.startswith("source") and why and not _leaks(where + why), (where, why)
        shown = mask_secrets([{"source": value, "extra": {"cred_secret": "Hunter2", "empty_secret": ""}}])[0]
        assert not _leaks(json.dumps(shown, default=str)) and shown["extra"] == {"cred_secret": SECRET_MASK, "empty_secret": ""}
    assert refusal_within({"source": ["rtsp://10.0.0.5/s"], "labels": ["a", "b"], "n": 3}) is None


def test_a_closed_consoles_gate_never_quotes_a_source_it_refuses():
    """The product's cross-check of the thirteenth review: a closed console's gate quoted a password read as a port
    («invalid port ":Hunter2"»). The course's gate asks who and may, from the headers and the units the body names, and
    its refusals name a caller, a capability and a unit — checked here over every form this file holds: whatever the
    caller (none, one with a grant on another camera, an administrator), no reply says the password."""
    from tests.test_console_gate import Tokens, _call, _console
    from w2cplatform.access import TRUST_KEYS
    box = Box()
    ctl, rec, m, srv, base = _console(box, Tokens({"one": [("admin", "vms/2", ())], "admin": [("admin", None, ())]}))
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.50/ch/1"}, token="admin")[0] == 201
        box.vars.put(TRUST_KEYS, {"current": "k1", "key:k1": "00" * 32})   # in a domain: the gate is shut to strangers
        said = 0
        for token in (None, "one", "admin"):
            for src in LOGIN_FORMS + NESTED_FORMS + HOST_IN_PATH_FORMS + ["rtsp://admin:Hunter2@h:Hunter2/s"]:
                for method, path in (("POST", "/cameras"), ("PUT", "/cameras/1")):
                    st, b = _call(base, method, path, {"source": src}, token=token)
                    assert st >= 400 and not _leaks(b), (token, method, src, st, b)
                    said += 1
        assert said == 3 * 2 * (43 + 6 + 8 + 1)
    finally:
        srv.shutdown()


def test_the_page_asks_a_secret_in_a_password_field_and_never_fills_it_with_the_mask():
    """The thirteenth review, minor: the page drew `cred_secret` as `type="text"` — the password on the screen while it
    is typed, where `access_secret` beside it was a password field. Every `*_secret` of a spec is a password field now
    (`input` in the VMS's page, `vms/shell.html`); and the edit form leaves it empty, its placeholder saying whether one is set — filled
    with the row's `***` it saved `***` as the camera's password on the next Save."""
    import os
    import re
    page = open(os.path.join(os.path.dirname(__file__), "..", "vms", "shell.html"), encoding="utf-8").read()
    body = page[page.index("function input(f, adding)"):]
    body = body[:body.index("\n}\n")]
    first = body.index("if (f.name.endsWith('_secret'))")
    assert 'type="password"' in body[first:body.index("\n", first)] and first < body.index('type="text"')
    fill = page[page.index("function fillEdit(c)"):]
    fill = fill[:fill.index("\n}\n")]
    assert re.search(r"endsWith\('_secret'\)\) \{ el\.value = '';", fill)


def test_the_vms_says_how_its_cameras_spell_a_login_and_the_platform_reads_it_from_the_spec():
    """The boundary's step 4: the name lists, the XMeye chain, a password's name segment, DriverPack's host in the path
    and go2rtc's `?src=` were `secrets.py`'s own; they are the `secret_in` of `source` in `vms.subsystem.yaml` now, with
    `schemes` and `credentials`. Without those rules the platform refuses an `@`, a port that is no number and its few
    common names of a credential (`COMMON_RULES`: `pwd`, `token`…), and no vendor's spelling — the
    forms below stand; with them every one is refused, its password hidden, and the refusal names `cred_secret` — and
    `cred_username` beside it where a login was found too."""
    from w2cplatform.secrets import NO_RULES, address_refusal, hide_in_url
    source = SPEC.fields["source"]
    assert source.credentials == {"login": "cred_username", "secret": "cred_secret"} and "driverpack" in source.schemes
    spelt = ["http://10.0.0.5/cgi-bin/snapshot.cgi?usr=admin&loginpas=Hunter2",
             "rtsp://10.0.0.9:554/channel=1_user=admin_password=Hunter2_stream=0.sdp",
             "http://10.0.0.5/user/admin/password/Hunter2/snap.jpg",
             "driverpack://acme/admin:Hunter2/ch/1", "driverpack://acme/admin:Hunter2%4010.0.0.5/ch/1",
             "http://proxy/relay?src=rtsp%3A%2F%2Fadmin%3AHunter2%40cam%2Fs"]
    for src in spelt:
        assert address_refusal(src, NO_RULES) is None, src                  # the platform's own names: no vendor's
        assert address_refusal(src, source.rules) and not _leaks(hide_in_url(src, source.rules)), src
        try:
            SPEC.refuse({"source": src})
            raise AssertionError(f"taken: {src}")
        except Refused as e:
            assert "cred_secret" in str(e) and not _leaks(str(e)), str(e)
            assert ("cred_username" in str(e)) == ("login" in str(e).split(".")[0]), str(e)
    try:
        SPEC.refuse({"source": "gopher://10.0.0.5/live"})
        raise AssertionError("a scheme no camera is reached by was taken")
    except Refused as e:
        assert "gopher" in str(e) and "driverpack" in str(e)
