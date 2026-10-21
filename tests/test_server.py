"""MCP server tests: real stdio round-trip + direct tool calls. Offline via KSMCP_FIXTURE."""
import json
import os
import sys
import tempfile

import anyio
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixture.json")
os.environ["KSMCP_FIXTURE"] = FIX

from ksmcp import server  # noqa: E402


def test_list_apis_has_github():
    assert any(a["api"] == "github" for a in server.list_apis())


def test_find_servers_ranked():
    res = server.find_servers("github")
    assert res and res[0]["server"] == "io.github.github/github-mcp-server"
    assert all("not an audit" in r["disclaimer"] for r in res)


def test_alias_and_unknown_api():
    assert server.find_servers("gh")
    with pytest.raises(ValueError):
        server.find_servers("nope-api")


def test_preview_writes_nothing_and_no_plaintext():
    with tempfile.TemporaryDirectory() as sb:
        out = server.preview_config("github", "cursor,vscode", sandbox_dir=sb)
        assert all(r["dry_run"] for r in out["results"])
        assert not any(os.path.exists(r["path"]) for r in out["results"])
        blob = json.dumps(out)
        assert "keyscout-run" in blob and "ghp_" not in blob


def test_apply_default_is_dry_run():
    with tempfile.TemporaryDirectory() as sb:
        out = server.apply_setup("github", sb, "cursor")
        assert out["results"][0]["dry_run"] is True
        assert not os.path.exists(out["results"][0]["path"])


def test_apply_writes_in_sandbox_and_backs_up():
    with tempfile.TemporaryDirectory() as sb:
        p = server.apply_setup("github", sb, "cursor", dry_run=False)["results"][0]["path"]
        assert p.startswith(os.path.realpath(sb)) and os.path.exists(p)
        with open(p, "w") as f:
            json.dump({"mcpServers": {}}, f)
        r2 = server.apply_setup("github", sb, "cursor", dry_run=False)["results"][0]
        assert r2["backup"] and os.path.exists(r2["backup"])


def test_apply_refuses_real_home():
    with pytest.raises(ValueError):
        server.apply_setup("github", os.path.expanduser("~"), "cursor", dry_run=False)


def test_unknown_client():
    with tempfile.TemporaryDirectory() as sb, pytest.raises(ValueError):
        server.preview_config("github", "notepad", sandbox_dir=sb)


def test_stdio_roundtrip():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "ksmcp.server"], cwd=ROOT,
                                       env={**os.environ, "KSMCP_FIXTURE": FIX, "PYTHONPATH": ROOT})
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
            assert {"list_apis", "detect_clients", "find_servers", "preview_config", "apply_setup"} <= names
            res = await s.call_tool("find_servers", {"api": "github", "limit": 2})
            assert not getattr(res, "is_error", getattr(res, "isError", False)) and "github-mcp-server" in res.content[0].text

    anyio.run(run)
