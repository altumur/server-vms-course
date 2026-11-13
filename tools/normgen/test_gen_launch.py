"""Test the unmodified launch daemon, Empty core and KIT documentation (ADR-0083 addendum 95, items2/3). Build launch_judge.stand and run a process: check sockets/permissions, role-socket GET, 413, SIGTERM exit 0 and socket cleanup. Expect exit 2 for no-raft group startup, foreign FORMAT/unmarked directories without byte changes, invalid rights and unknown inherited sockets; inherited admin is accepted. Compile kit/examples and vet an all-part kit. Linux CT103, Go 1.22 only."""
import lesson as output_lesson
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))
import build_kit  # noqa: E402
import gen_launch  # noqa: E402
import launch_judge  # noqa: E402

RIGHTS = {"roles": {"acc": {"group": "acc", "read": ["acc/*"], "write": ["acc/*"], "delete": ["acc/*"]}}}


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=5)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(5)
        self.sock.connect(self.path)


def request(path, method, target, body=None):
    c = UnixHTTP(path)
    c.request(method, target, body=body)
    r = c.getresponse()
    out = r.status, r.read()
    c.close()
    return out


def tree(d):
    return {str(p.relative_to(d)): p.read_bytes() for p in Path(d).rglob("*") if p.is_file()}


class Launch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="nl-", dir="/tmp"))     # Keep paths short for AF_UNIX limits.
        launch_judge.stand(cls.tmp / "stand", "0" * 40)
        store = cls.tmp / "stand/01-store"
        done = subprocess.run(["go", "build", "-o", str(cls.tmp / "cs"), "./cmd/configstore"], cwd=store,
                              capture_output=True, text=True)
        if done.returncode:
            raise AssertionError(done.stderr)
        done = subprocess.run(["go", "vet", "./..."], cwd=store, capture_output=True, text=True)
        if done.returncode:
            raise AssertionError(done.stderr)
        cls.exe = cls.tmp / "cs"
        (cls.tmp / "rights.json").write_text(json.dumps(RIGHTS), encoding="utf-8")
        cls.k = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fresh(self):
        type(self).k += 1
        d = self.tmp / f"r{self.k}"
        d.mkdir()
        return d

    def start(self, d, *extra, rights=True, **kw):
        argv = [str(self.exe), "-id", "s1", "-dir", str(d / "data"), "-sockets", str(d / "run")]
        argv += ["-rights", str(self.tmp / "rights.json")] if rights else []
        return subprocess.Popen(argv + list(extra), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)

    def wait_ready(self, p, *socks):
        for _ in range(200):
            if p.poll() is not None:
                self.fail(f"exited {p.returncode}: {p.stderr.read().decode()}")
            if all(os.path.exists(s) for s in socks):
                return
            time.sleep(0.02)
        self.fail("no sockets")

    def test_out_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for rel, text in gen_launch.render().items():
            self.assertEqual((gen_launch.DEFAULT_OUT / "go" / rel).read_text(encoding="utf-8"), text, rel)

    def test_serve_and_stop(self):
        d = self.fresh()
        p = self.start(d)
        run = d / "run"
        self.wait_ready(p, run / "admin.sock", run / "acc.sock")
        self.assertEqual(oct(os.stat(run / "admin.sock").st_mode & 0o777), "0o600")
        self.assertEqual(oct(os.stat(run / "acc.sock").st_mode & 0o777), "0o660")
        mark = json.loads((d / "data/FORMAT").read_text(encoding="utf-8"))
        self.assertEqual(set(mark), {"format", "version", "impl"})
        st, body = request(str(run / "acc.sock"), "GET", "/v1/get?key=acc/x/c1")
        self.assertEqual((st, json.loads(body)), (200, {"items": None, "index": ""}))
        st, _ = request(str(run / "acc.sock"), "GET", "/nope")
        self.assertEqual(st, 404)
        st, body = request(str(run / "admin.sock"), "POST", "/v1/write", b"x" * (1048576 + 1))
        self.assertEqual((st, json.loads(body)["kind"]), (413, "toolarge"))
        p.terminate()
        self.assertEqual(p.wait(10), 0)
        self.assertEqual(sorted(os.listdir(run)), [])
        p = self.start(d)                                  # Own FORMAT permits another startup.
        self.wait_ready(p, run / "admin.sock")
        p.terminate()
        self.assertEqual(p.wait(10), 0)

    def test_without_rights_only_admin(self):
        d = self.fresh()
        p = self.start(d, rights=False)
        self.wait_ready(p, d / "run/admin.sock")
        time.sleep(0.1)
        self.assertEqual(os.listdir(d / "run"), ["admin.sock"])
        p.terminate()
        self.assertEqual(p.wait(10), 0)

    def refused(self, d, *extra, rights=True, **kw):
        p = self.start(d, *extra, rights=rights, **kw)
        try:
            code = p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()
            self.fail("alive, want exit 2")
        err = p.stderr.read().decode()
        self.assertEqual(code, 2, err)
        return err

    def test_refusals(self):
        no_tls = self.fresh()
        self.assertIn("-tls", self.refused(no_tls, "-join", "127.0.0.1:9"))
        self.assertFalse((no_tls / "data").exists(), "TLS admission must refuse before opening the store")
        for extra in (["-join", "127.0.0.1:9", "-tls", str(self.tmp / "tls")],
                      ["-group-size", "3"], ["-door", "-voters", "a@127.0.0.1:9"]):
            with self.subTest(extra=extra):
                self.assertIn("no raft", self.refused(self.fresh(), *extra))
        d = self.fresh()
        (d / "data").mkdir()
        (d / "data/junk").write_text("x")
        before = tree(d / "data")
        self.refused(d)
        self.assertEqual(tree(d / "data"), before)                       # Leave unmarked directories unchanged.
        (d / "data/FORMAT").write_text('{"format":"other","version":1,"impl":"x"}')
        before = tree(d / "data")
        self.assertIn("foreign FORMAT", self.refused(d))
        self.assertEqual(tree(d / "data"), before)
        (d / "data/FORMAT").write_text('{"format":"configstore"}')
        self.assertIn("out of form", self.refused(d))
        bad = self.tmp / "bad-rights.json"
        bad.write_text("[1]")
        d = self.fresh()
        p = subprocess.Popen([str(self.exe), "-id", "s1", "-dir", str(d / "data"), "-sockets", str(d / "run"),
                              "-rights", str(bad)], stderr=subprocess.PIPE)
        self.assertEqual(p.wait(10), 2)
        self.assertIn("-no-such-flag", self.refused(self.fresh(), "-no-such-flag", "x"))

    def inherited(self, d, name):
        s = socket.socket(socket.AF_UNIX)
        s.bind(str(d / "inh.sock"))
        s.listen(4)

        argv = [str(self.exe), "-id", "s1", "-dir", str(d / "data"), "-sockets", str(d / "run")]
        fd = s.fileno()                                   # sh assigns fd3, where sd_listen_fds starts.
        sh = 'LISTEN_PID=$$ LISTEN_FDS=1 LISTEN_FDNAMES=%s exec "$@" 3<&%d' % (name, fd)
        p = subprocess.Popen(["sh", "-c", sh, "sh"] + argv, pass_fds=(fd,), stderr=subprocess.PIPE)
        return p, s

    def test_inherited(self):
        d = self.fresh()
        p, s = self.inherited(d, "nobody")
        self.assertEqual(p.wait(10), 2)
        self.assertIn("foreign name", p.stderr.read().decode())
        s.close()
        d = self.fresh()
        p, s = self.inherited(d, "admin")
        for _ in range(200):
            try:
                st, _ = request(str(d / "inh.sock"), "GET", "/v1/get?key=acc/x/c1")
                break
            except OSError:
                time.sleep(0.02)
        else:
            self.fail("the inherited admin socket does not answer")
        self.assertEqual(st, 200)
        self.assertFalse((d / "run/admin.sock").exists())            # Do not recreate an inherited socket.
        p.terminate()
        self.assertEqual(p.wait(10), 0)
        s.close()


class Frame(unittest.TestCase):
    """HTTP framing is implementation-owned internal/frame/frame.go (ADR-0125 addendum 1, item 2). launch has no net/http; its temporary frame is labeled and carries N2.1 anchors. Edits must affect the running daemon and survive rebuild; missing App.Frame exits1."""
    MOD = "example.com/w2c/store"

    def test_frame_is_yours(self):
        with tempfile.TemporaryDirectory(prefix="nlf-", dir="/tmp") as t:
            dst = Path(t)
            m = build_kit.build(dst, self.MOD, ["door", "flags", "refusals", "stagetests", "launch", "admin"])
            own = {f["path"] for f in m["files"] if f.get("editable")}
            self.assertIn("01-store/internal/frame/frame.go", own)
            self.assertIn("01-store/cmd/configstore/main.go", own)
            self.assertNotIn("01-store/internal/launch/launch.go", own)
            store = dst / "01-store"
            launch_go = (store / "internal/launch/launch.go").read_text(encoding="utf-8")
            self.assertNotIn('"net/http"', launch_go)
            frame = store / "internal/frame/frame.go"
            text = frame.read_text(encoding="utf-8")
            self.assertIn("TEMPORARY FRAME ON net/http -- REPLACE IT", text)
            self.assertNotIn("DO NOT EDIT", text)
            for a in ("P/01.1-R049", "P/01.1-R050", "P/01.1-R052", "P/01.1-R242", "P/01.1-R054"):
                self.assertIn(f"req: {a}", text)
            doc = (dst / "KIT.md").read_text(encoding="utf-8")
            self.assertIn("is a temporary frame on `net/http`; the raw HTTP acceptance requires the strict parse of\n> "
                          "N2.1 — replace it.", doc)
            # Edit the frame to add a response header; the daemon must use that implementation frame.
            frame.write_text(text.replace("\t\tw.WriteHeader(code)", '\t\tw.Header().Set("X-Frame", "mine")\n\t\tw.WriteHeader(code)'),
                             encoding="utf-8")
            build_kit.build(dst, self.MOD, ["door", "flags", "refusals", "stagetests", "launch", "admin"])
            self.assertIn("X-Frame", frame.read_text(encoding="utf-8"))
            (store / "go.mod").write_text(f"module {self.MOD}\n\ngo 1.22\n", encoding="utf-8")
            done = subprocess.run(["go", "build", "-o", str(dst / "cs"), "./cmd/configstore"], cwd=store,
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            (dst / "rights.json").write_text(json.dumps(RIGHTS), encoding="utf-8")
            run = dst / "run"
            p = subprocess.Popen([str(dst / "cs"), "-id", "s1", "-dir", str(dst / "data"), "-sockets", str(run),
                                  "-rights", str(dst / "rights.json")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for _ in range(200):
                    if (run / "acc.sock").exists() or p.poll() is not None:
                        break
                    time.sleep(0.02)
                c = UnixHTTP(str(run / "acc.sock"))
                c.request("GET", "/v1/get?key=acc/x")
                r = c.getresponse()
                self.assertEqual((r.status, r.getheader("X-Frame")), (200, "mine"))
                r.read()
                c.close()
            finally:
                p.terminate()
                self.assertEqual(p.wait(10), 0)
                p.stdout.close()
                p.stderr.close()
            # Missing App.Frame exits1 with a reason.
            main = store / "cmd/configstore/main.go"
            src = main.read_text(encoding="utf-8")
            start, end = src.index("\t\tFrame: func("), src.index("\t\t},\n", src.index("\t\tFrame: func(")) + 5
            main.write_text((src[:start] + src[end:]).replace(f'\t"{self.MOD}/internal/frame"\n', ""), encoding="utf-8")
            done = subprocess.run(["go", "build", "-o", str(dst / "cs0"), "./cmd/configstore"], cwd=store,
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            done = subprocess.run([str(dst / "cs0"), "-id", "s1", "-dir", str(dst / "data0"), "-sockets", str(dst / "run0")],
                                  capture_output=True, text=True, timeout=10)
            self.assertEqual(done.returncode, 1)
            self.assertIn("App.Frame is nil", done.stderr)


class Connect(unittest.TestCase):
    def test_examples_compile(self):
        """Compile KIT.md connection examples with all kit parts."""
        with tempfile.TemporaryDirectory(prefix="nlc-") as t:
            dst = Path(t)
            mod = "example.com/w2c/store"
            parts = ["door", "flags", "refusals", "families", "vectors", "stagetests", "launch", "admin"]
            build_kit.build(dst, mod, parts)
            store = dst / "01-store"
            (store / "go.mod").write_text(f"module {mod}\n\ngo 1.22\n", encoding="utf-8")
            ex = store / "internal/kitexample"
            ex.mkdir()
            for f in sorted(build_kit.EXAMPLES.glob("*.go")):
                (ex / f.name).write_text(f.read_text(encoding="utf-8").replace('"kitmodule/internal/', f'"{mod}/internal/'),
                                         encoding="utf-8")
            done = subprocess.run(["go", "vet", "./..."], cwd=store, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            doc = (dst / "KIT.md").read_text(encoding="utf-8")
            for part in ["writecheck", *parts]:
                self.assertIn(f"### `{part}`", doc)
            self.assertIn("## Exported names (by package)", doc)
            self.assertIn("`NotImplemented`", doc)
            self.assertNotIn("kitmodule", doc)

    def test_launch_needs_parts(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(build_kit.KitError):
                build_kit.build(t, "example.com/x", ["launch", "door", "flags"])


if __name__ == "__main__":
    unittest.main()
