"""Attack-case tests for the inject proxy (destination pinning + caller auth)."""
import http.client
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ksmcp.proxy import DestinationError, InjectProxy, TOKEN_HEADER, build_upstream_url

FAKE = "ghp_" + "A" * 36


class _Vault:
    def get(self, ref):
        return FAKE


def _server():
    hits = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            hits.append((self.path, self.headers.get("Authorization"), self.headers.get(TOKEN_HEADER)))
            if self.path == "/redir":
                self.send_response(302); self.send_header("Location", "http://127.0.0.1:1/x"); self.end_headers(); return
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, hits


@pytest.fixture
def env():
    up, up_hits = _server()
    evil, evil_hits = _server()
    p = InjectProxy(_Vault(), "gh", f"http://127.0.0.1:{up.server_address[1]}/api")
    p.start()
    yield p, up_hits, evil, evil_hits
    p.stop(); up.shutdown(); evil.shutdown()


def _raw(p, target, token=True):
    c = http.client.HTTPConnection("127.0.0.1", p.port, timeout=5)
    c.putrequest("GET", target, skip_host=True, skip_accept_encoding=True)
    c.putheader("Host", "127.0.0.1")
    if token:
        c.putheader(TOKEN_HEADER, p.session_token)
    c.endheaders()
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, body


def test_happy_path_injects_and_strips_token(env):
    p, up_hits, *_ = env
    assert _raw(p, "/v1/x?a=1") == (200, b"ok")
    path, auth, tok = up_hits[-1]
    assert path == "/api/v1/x?a=1" and auth == f"Bearer {FAKE}" and tok is None


@pytest.mark.parametrize("bad", [
    "http://127.0.0.1:{evil}/steal",
    "https://evil.example/steal",
    "//127.0.0.1:{evil}/steal",
    "///127.0.0.1:{evil}/steal",
    "/\\127.0.0.1:{evil}/steal",
    "/@127.0.0.1:{evil}/steal",
    "127.0.0.1:{evil}/steal",
])
def test_host_changing_targets_rejected(env, bad):
    p, up_hits, evil, evil_hits = env
    status, _ = _raw(p, bad.format(evil=evil.server_address[1]))
    assert status == 400
    assert evil_hits == [] and up_hits == []


def test_missing_or_wrong_token_rejected(env):
    p, up_hits, *_ = env
    assert _raw(p, "/x", token=False)[0] == 401
    c = http.client.HTTPConnection("127.0.0.1", p.port, timeout=5)
    c.request("GET", "/x", headers={TOKEN_HEADER: "wrong"})
    assert c.getresponse().status == 401
    assert up_hits == []


def test_redirects_not_followed(env):
    p, up_hits, *_ = env
    status, body = _raw(p, "/../redir")  # path normalisation stays on upstream origin
    assert status in (302, 404, 200)
    assert FAKE.encode() not in body


def test_upstream_redirect_not_followed():
    up, hits = _server()
    p = InjectProxy(_Vault(), "gh", f"http://127.0.0.1:{up.server_address[1]}/")
    p.start()
    try:
        status, body = _raw(p, "/redir")
        assert status == 302 and FAKE.encode() not in body
        assert len(hits) == 1
    finally:
        p.stop(); up.shutdown()


def test_build_upstream_url_unit():
    b = "https://api.github.com/"
    assert build_upstream_url(b, "/repos?x=1") == "https://api.github.com/repos?x=1"
    for bad in ["https://evil.com/", "//evil.com/", "evil.com", "", "/a\r\nHost: evil"]:
        with pytest.raises(DestinationError):
            build_upstream_url(b, bad)


def test_non_loopback_bind_requires_opt_in():
    with pytest.raises(ValueError):
        InjectProxy(_Vault(), "gh", "https://api.github.com/", host="0.0.0.0")


def test_bad_upstream_rejected():
    for bad in ["ftp://x/", "https://user:pw@api.github.com/", "notaurl"]:
        with pytest.raises(DestinationError):
            InjectProxy(_Vault(), "gh", bad)


def test_session_tokens_unique_and_not_key():
    a = InjectProxy(_Vault(), "gh", "https://api.github.com/")
    b = InjectProxy(_Vault(), "gh", "https://api.github.com/")
    assert a.session_token != b.session_token and FAKE not in a.session_token
    assert len(a.session_token) >= 32
