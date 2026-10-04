"""SigV4 against Amazon's published worked example — the GET Object case
from the S3 "Signature Calculations" documentation. If this signature
matches, the canonical request, the string to sign and the key derivation
are all right; nothing else in the adapter is cryptographic."""
import datetime as dt
from cluster.s3 import sign

ACCESS = "AKIAIOSFODNN7EXAMPLE"
SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def test_amazon_worked_example_get_object():
    now = dt.datetime(2013, 5, 24, 0, 0, 0, tzinfo=dt.timezone.utc)
    h = sign("GET", "examplebucket.s3.amazonaws.com", "/test.txt", "",
             {"Range": "bytes=0-9"}, b"", ACCESS, SECRET, "us-east-1", now)
    assert h["x-amz-content-sha256"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert h["authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


def test_amazon_worked_example_put_object():
    """The PUT example from the same page: key test$file.text, body 'Welcome to Amazon S3.'"""
    now = dt.datetime(2013, 5, 24, 0, 0, 0, tzinfo=dt.timezone.utc)
    body = b"Welcome to Amazon S3."
    h = sign("PUT", "examplebucket.s3.amazonaws.com", "/test$file.text", "",
             {"Date": "Fri, 24 May 2013 00:00:00 GMT", "x-amz-storage-class": "REDUCED_REDUNDANCY"},
             body, ACCESS, SECRET, "us-east-1", now)
    assert h["x-amz-content-sha256"] == "44ce7dd67c959e0d3524ffac1771dfbba87d2b6b4b4e99e42034a8b803f8b072"
    assert h["authorization"].endswith("Signature=98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd")


def test_a_read_of_the_object_store_takes_up_to_its_ceiling_and_refuses_past_it():
    """The review's eighth pass, a sibling of the peers' answers: `HttpObjectStore.get` and the S3 `get` read the whole
    body whatever its size — a store or a proxy gone wrong was memory without a ceiling in every reader of heartbeats.
    A read now takes up to `GET_MAX` and is refused past it — a `ValueError`, never half an object."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import cluster.objectstore as o
    import cluster.s3 as s3

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = b"x" * (2048 if "big" in self.path else 10)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    real = o.GET_MAX
    o.GET_MAX = s3.GET_MAX = 1024
    try:
        for store in (o.HttpObjectStore(url), s3.S3ObjectStore(url, "b", access_key="a", secret_key="s")):
            assert store.get("small") == b"x" * 10
            try:
                store.get("big")
                raise AssertionError(f"{type(store).__name__} read past its ceiling")
            except ValueError:
                pass
    finally:
        o.GET_MAX = s3.GET_MAX = real
        srv.shutdown()
