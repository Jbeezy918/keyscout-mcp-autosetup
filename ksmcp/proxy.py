"""Local inject proxy: Agent B talks to localhost; the proxy adds the Authorization
header from the vault. Agent B never receives the raw key.

Security model:
  * Destination pinning: every request is resolved against the configured upstream
    and must keep exactly the same scheme, host and port. Absolute-form targets
    (``http://evil/``), scheme-relative targets (``//evil/``), backslash tricks,
    userinfo (``@``), CR/LF and other host-changing forms are rejected with 400 and
    the credential is never attached. Upstream redirects are not followed.
  * Caller authentication: each proxy has a random per-session token. Callers must
    send it in the ``X-KeyScout-Proxy-Token`` header; it is compared in constant
    time and stripped before forwarding.
  * Loopback bind by default; binding to a non-loopback address requires
    ``allow_remote=True``.
"""
from __future__ import annotations

import hmac
import ipaddress
import json
import os
import secrets
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit

from .vault import Vault

TOKEN_HEADER = "X-KeyScout-Proxy-Token"
_HOP_HEADERS = {
    "host", "content-length", "connection", "proxy-connection", "keep-alive",
    "transfer-encoding", "te", "trailer", "upgrade", "proxy-authorization",
}
_DEFAULT_PORTS = {"http": 80, "https": 443}


class DestinationError(ValueError):
    """Raised when a request path would leave the configured upstream."""


def _origin(scheme: str, host: str | None, port: int | None) -> tuple[str, str, int]:
    scheme = (scheme or "").lower()
    if scheme not in _DEFAULT_PORTS:
        raise DestinationError("unsupported scheme")
    if not host:
        raise DestinationError("missing host")
    return scheme, host.lower(), port or _DEFAULT_PORTS[scheme]


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_upstream_url(target_base: str, request_path: str) -> str:
    """Return the upstream URL for ``request_path`` or raise DestinationError.

    Only origin-form paths (starting with a single ``/``) are accepted. The result
    is guaranteed to share scheme, host and port with ``target_base``.
    """
    base = urlsplit(target_base)
    if base.username or base.password:
        raise DestinationError("upstream must not contain credentials")
    want = _origin(base.scheme, base.hostname, base.port)

    p = request_path or ""
    if not p.startswith("/") or p.startswith("//"):
        raise DestinationError("only origin-form paths are allowed")
    if any(c in p for c in ("\\", "\r", "\n", "\t", " ", "\x00")) or "@" in p.split("?", 1)[0]:
        raise DestinationError("illegal characters in path")
    req = urlsplit(p)
    if req.scheme or req.netloc:
        raise DestinationError("absolute or authority-bearing path")

    base_path = base.path.rstrip("/")
    url = urlunsplit((base.scheme, base.netloc, base_path + req.path, req.query, ""))
    got = urlsplit(url)
    if (got.username or got.password
            or _origin(got.scheme, got.hostname, got.port) != want):
        raise DestinationError("destination does not match upstream")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # never follow: would re-send the credential
        return None


_opener = urllib.request.build_opener(_NoRedirect)


class InjectProxy:
    def __init__(
        self,
        vault: Vault,
        ref: str,
        target_base: str,
        *,
        header_name: str = "Authorization",
        header_template: str = "Bearer {key}",
        host: str = "127.0.0.1",
        port: int = 0,
        allow_remote: bool = False,
        session_token: str | None = None,
    ):
        tb = urlsplit(target_base)
        _origin(tb.scheme, tb.hostname, tb.port)  # validate early
        if tb.username or tb.password:
            raise DestinationError("upstream must not contain credentials")
        if not allow_remote and not _is_loopback(host):
            raise ValueError("refusing non-loopback bind without allow_remote=True")
        self.vault = vault
        self.ref = ref
        self.target_base = target_base.rstrip("/") + "/"
        self.header_name = header_name
        self.header_template = header_template
        self.host = host
        self.port = port
        self.session_token = session_token or secrets.token_urlsafe(32)
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        vault, ref, target_base = self.vault, self.ref, self.target_base
        header_name, header_template = self.header_name, self.header_template
        expected = self.session_token.encode()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # quiet
                pass

            def _reply(self, code: int, msg: bytes):
                self.send_response(code)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)

            def _forward(self, method: str):
                supplied = (self.headers.get(TOKEN_HEADER) or "").encode()
                if not hmac.compare_digest(supplied, expected):
                    return self._reply(401, b"missing or invalid proxy token")
                try:
                    # Use the raw request-target: http.server may collapse a leading "//".
                    parts = (self.requestline or "").split(" ")
                    raw_target = parts[1] if len(parts) >= 2 else self.path
                    url = build_upstream_url(target_base, raw_target)
                except DestinationError as e:
                    return self._reply(400, f"rejected: {e}".encode())
                try:
                    length = int(self.headers.get("Content-Length", 0) or 0)
                except ValueError:
                    return self._reply(400, b"bad content-length")
                body = self.rfile.read(length) if length > 0 else None
                headers = {k: v for k, v in self.headers.items()
                           if k.lower() not in _HOP_HEADERS and k.lower() != TOKEN_HEADER.lower()
                           and k.lower() != header_name.lower()}
                key = vault.get(ref)
                headers[header_name] = header_template.replace("{key}", key)
                req = urllib.request.Request(url, data=body, headers=headers, method=method)
                try:
                    try:
                        resp = _opener.open(req, timeout=60)
                    except urllib.error.HTTPError as he:  # non-2xx incl. unfollowed redirects
                        resp = he
                    with resp:
                        data = resp.read()
                        self.send_response(resp.status if hasattr(resp, "status") else resp.code)
                        for k, v in resp.headers.items():
                            if k.lower() in ("transfer-encoding", "connection", "content-length"):
                                continue
                            self.send_header(k, v)
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                except Exception as e:
                    self._reply(502, str(e).replace(key, "[REDACTED]").encode())

            def do_GET(self):
                self._forward("GET")

            def do_POST(self):
                self._forward("POST")

            def do_PUT(self):
                self._forward("PUT")

            def do_PATCH(self):
                self._forward("PATCH")

            def do_DELETE(self):
                self._forward("DELETE")

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def info(self) -> dict:
        return {
            "listen": f"http://{self.host}:{self.port}",
            "target": self.target_base,
            "header": self.header_name,
            "ref": self.ref,
            "auth_header": TOKEN_HEADER,
            "session_token": self.session_token,
            "note": (f"Agent B should call the listen URL only, sending {TOKEN_HEADER}. "
                     "The session token is not the API key; the raw key stays in the vault/proxy."),
        }


def write_proxy_info(path: str, info: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(info, f, indent=2)
