"""KeyScout MCP Auto-Setup as an MCP server (stdio).

Tools never accept or return raw API keys. Config writes only happen inside a
sandbox folder (the real home dir is refused) and only when dry_run=False.
Set KSMCP_FIXTURE to a registry JSON file to run offline.
"""
from __future__ import annotations

import json
import os

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server
from mcp.types import ToolAnnotations

from . import clients, match, registry
from .catalog import CATALOG

mcp = _Server("keyscout-mcp-autosetup")
_RO = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


def _entries(api: str, cache_root: str):
    fx = os.environ.get("KSMCP_FIXTURE")
    if fx:
        with open(fx) as f:
            return json.load(f)
    return registry.fetch(api, os.path.join(cache_root, ".ksmcp-cache"))


def _api(api: str) -> str:
    a = (api or "").strip().lower()
    for k, v in CATALOG.items():
        if a == k or a in v.get("aliases", []):
            return k
    raise ValueError(f"unknown API '{api}'. Known: {', '.join(sorted(CATALOG))}")


def _clients(names: str | list[str]) -> list[str]:
    lst = names.split(",") if isinstance(names, str) else list(names)
    lst = [n.strip().lower() for n in lst if n.strip()]
    bad = [n for n in lst if n not in clients.CLIENTS]
    if bad:
        raise ValueError(f"unknown client(s) {bad}. Known: {', '.join(clients.CLIENTS)}")
    return lst


def _cache_root() -> str:
    return os.environ.get("KSMCP_CACHE", os.path.join(os.path.expanduser("~"), ".keyscout"))


@mcp.tool(annotations=_RO)
def list_apis() -> list[dict]:
    """List the APIs this tool can match MCP servers for, with where to get a key."""
    return [{"api": k, "label": v["label"], "get_key": v["get_key"], "free_tier": v["free_tier"]} for k, v in CATALOG.items()]


@mcp.tool(annotations=_RO)
def detect_clients() -> list[dict]:
    """Report which MCP clients (Claude Desktop, Cursor, VS Code, Windsurf) have a config file in the
    user's home folder. Read-only: checks existence and server names only, never prints values."""
    home = os.path.expanduser("~")
    out = []
    for name, (rel, key) in clients.CLIENTS.items():
        p = os.path.join(home, rel)
        servers: list[str] = []
        if os.path.exists(p):
            try:
                with open(p) as f:
                    servers = sorted((json.load(f).get(key) or {}).keys())
            except Exception:  # noqa: BLE001 - unreadable config is reported, not fatal
                servers = ["(unreadable)"]
        out.append({"client": name, "config_path": p, "exists": os.path.exists(p), "servers": servers})
    return out


@mcp.tool(annotations=_RO)
def find_servers(api: str, limit: int = 10) -> list[dict]:
    """Find MCP servers in the official registry that accept a key for `api` (e.g. "github"),
    ranked by an A-F safety score (automated heuristics, not an audit)."""
    a = _api(api)
    res = []
    for c in match.candidates(_entries(a, _cache_root()), a)[: max(1, limit)]:
        s = c["safety"]
        res.append({"server": c["server"]["name"], "grade": s["grade"], "score": s["score"],
                    "flags": c["flags"], "key_via": f"{c['hits'][0][0]}:{c['hits'][0][1]}",
                    "disclaimer": s["disclaimer"]})
    return res


def _plan(api: str, client_list, top: int, root: str, dry_run: bool):
    a = _api(api)
    picks = match.bundle(match.candidates(_entries(a, root), a), max(1, top))
    if not picks:
        return {"api": a, "servers": [], "results": [], "note": "no matching servers"}
    ref = f"keyscout-{a}"
    results = []
    for cl in _clients(client_list):
        r = clients.apply(root, cl, add=picks, ref=ref, api=a, dry_run=dry_run)
        results.append({"client": cl, "path": r["path"], "changed": r["changed"], "dry_run": r["dry_run"],
                        "backup": r["backup"], "config": r["config"]})
    return {"api": a, "vault_ref": ref, "servers": [c["server"]["name"] for c in picks], "results": results,
            "next_step": (f"Store the key once (you'll be prompted, it never passes through the AI): "
                          f"ksmcp --sandbox {root} vault-put {ref}  then set "
                          f"KEYSCOUT_VAULT={os.path.join(root, '.keyscout', 'vault.json')} for keyscout-run.")}


@mcp.tool(annotations=_RO)
def preview_config(api: str, clients_csv: str = "cursor", top: int = 3, sandbox_dir: str | None = None) -> dict:
    """Show the MCP config that would be written for `api` in each client (comma-separated:
    claude,cursor,vscode,windsurf). Writes nothing. Configs launch servers via `keyscout-run`,
    so no plaintext key appears."""
    root = os.path.abspath(sandbox_dir) if sandbox_dir else os.path.join(_cache_root(), "preview-sandbox")
    return _plan(api, clients_csv, top, root, dry_run=True)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
def apply_setup(api: str, sandbox_dir: str, clients_csv: str = "cursor", top: int = 3, dry_run: bool = True) -> dict:
    """Write MCP configs for `api` into `sandbox_dir` (a folder that is NOT your home dir; the real home is
    refused). dry_run defaults to True; pass dry_run=False to actually write. Existing files are backed up
    first. Never takes or stores a key."""
    return _plan(api, clients_csv, top, os.path.abspath(sandbox_dir), dry_run=dry_run)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
