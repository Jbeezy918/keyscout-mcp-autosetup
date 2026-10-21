"""Local inject proxy: Agent B talks to localhost; the proxy adds the Authorization
header from the vault. Agent B never receives the raw key.

Protocol (MVP): HTTP CONNECT is not used. Instead we reverse-proxy plain HTTP to a
target base URL, injecting a header. For MCP streamable-http this is enough for
local demos. TLS upstream is supported via https targets.
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .vault import Vault


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
    ):
        self.vault = vault
        self.ref = ref
        self.target_base = target_base.rstrip("/") + "/"
        self.header_name = header_name
        self.header_template = header_template
        self.host = host
        self.port = port
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def _inject_value(self) -> str:
        key = self.vault.get(self.ref)
        return self.header_template.replace("{key}", key)

    def start(self) -> str:
        vault = self.vault
        ref = self.ref
        target_base = self.target_base
        header_name = self.header_name
        header_template = self.header_template

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # quiet
                pass

            def _forward(self, method: str):
                path = self.path
                url = urljoin(target_base, path.lstrip("/"))
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length) if length else None
                headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
                key = vault.get(ref)
                headers[header_name] = header_template.replace("{key}", key)
                req = Request(url, data=body, headers=headers, method=method)
                try:
                    with urlopen(req, timeout=60) as resp:
                        data = resp.read()
                        self.send_response(resp.status)
                        for k, v in resp.headers.items():
                            if k.lower() in ("transfer-encoding", "connection"):
                                continue
                            self.send_header(k, v)
                        self.end_headers()
                        self.wfile.write(data)
                except Exception as e:
                    msg = str(e).replace(key, "[REDACTED]").encode()
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(msg)

            def do_GET(self):
                self._forward("GET")

            def do_POST(self):
                self._forward("POST")

            def do_PUT(self):
                self._forward("PUT")

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
            self._httpd = None

    def info(self) -> dict:
        return {
            "listen": f"http://{self.host}:{self.port}",
            "target": self.target_base,
            "header": self.header_name,
            "ref": self.ref,
            "note": "Agent B should call listen URL only; raw key stays in the vault/proxy.",
        }


def write_proxy_info(path: str, info: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(info, f, indent=2)
