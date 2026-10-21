"""Write/merge MCP configs for AI clients inside a SANDBOX root. No plaintext keys:
- stdio servers launch via `keyscout-run <vault-ref> --env VAR -- <cmd>` which injects the key at runtime.
- Cursor remote headers use ${env:VAR}; VS Code uses a promptString password ${input:...}."""
import json
import os
import shutil
import sys
import time

if sys.platform == "darwin":
    _CLAUDE = "Library/Application Support/Claude/claude_desktop_config.json"
elif sys.platform.startswith("win"):
    _CLAUDE = "AppData/Roaming/Claude/claude_desktop_config.json"
else:  # Linux: unofficial Claude Desktop builds use XDG config
    _CLAUDE = ".config/Claude/claude_desktop_config.json"

CLIENTS = {  # paths relative to sandbox "home"
    "claude": (_CLAUDE, "mcpServers"),
    "cursor": (".cursor/mcp.json", "mcpServers"),
    "vscode": (".vscode/mcp.json", "servers"),        # workspace-level VS Code file
    "windsurf": (".codeium/windsurf/mcp_config.json", "mcpServers"),
}

def safe_path(root, rel):
    root = os.path.realpath(root); p = os.path.realpath(os.path.join(root, rel))
    home = os.path.realpath(os.path.expanduser("~"))
    if not p.startswith(root + os.sep): raise ValueError("path escapes sandbox")
    if root == home or home.startswith(root + os.sep) or root in ("/", ""):
        raise ValueError("refusing: sandbox must not be (or contain) the real home dir")
    return p

def short_id(name): return name.split("/")[-1].replace(".", "-")

def entry_for(client, cand, api, ref):
    s = cand["server"]; kind, var, t = cand["hits"][0]
    if kind == "env":
        p = t; rt = p.get("runtimeHint") or {"npm": "npx", "pypi": "uvx", "oci": "docker"}.get(p.get("registryType"), "npx")
        ident = p["identifier"] + (f"@{p['version']}" if p.get("version") and rt == "npx" else "")
        args = (["-y", ident] if rt == "npx" else ["run", "-i", "--rm", "-e", var, ident] if rt == "docker" else [ident])
        return {"command": "keyscout-run", "args": [ref, "--env", var, "--", rt] + args}
    # var may be header name OR a placeholder extracted from the value (e.g. GITHUB_TOKEN)
    hdr = next((h for h in t["headers"] if h["name"] == var), None)
    if hdr is None:
        from .catalog import env_matches, extract_placeholders
        hdr = next(h for h in t["headers"] if var in extract_placeholders(h.get("value")) or env_matches(api, h.get("name")))
    val_tpl = hdr.get("value") or "{token}"
    envvar = f"KEYSCOUT_{api.upper()}_KEY"
    if client == "vscode":
        return {"type": "http", "url": t["url"], "headers": {hdr["name"]: _sub(val_tpl, "${input:%s}" % ref)}}
    if client in ("cursor", "windsurf"):
        return {"url": t["url"], "headers": {hdr["name"]: _sub(val_tpl, "${env:%s}" % envvar)}}
    # Claude Desktop: bridge remote via mcp-remote, header injected by keyscout-run
    return {"command": "keyscout-run", "args": [ref, "--env", envvar, "--", "npx", "-y", "mcp-remote", t["url"],
            "--header", f"{hdr['name']}:{_sub(val_tpl, '${' + envvar + '}')}"]}

def _sub(tpl, val):
    import re
    return re.sub(r"\{[^}]+\}", val, tpl) if "{" in tpl else val

def load(path):
    return json.load(open(path)) if os.path.exists(path) else {}

def backup(path):
    if os.path.exists(path):
        b = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns()%100000}"
        shutil.copy2(path, b); return b

def apply(root, client, add=None, remove=None, ref=None, api=None, dry_run=False):
    rel, key = CLIENTS[client]; path = safe_path(root, rel)
    cfg = load(path); before = json.dumps(cfg, sort_keys=True)
    cfg.setdefault(key, {})
    for cand in add or []:
        cfg[key][short_id(cand["server"]["name"])] = entry_for(client, cand, api, ref)
        if client == "vscode" and cand["hits"][0][0] == "header":
            ins = cfg.setdefault("inputs", [])
            if not any(i.get("id") == ref for i in ins):
                ins.append({"type": "promptString", "id": ref, "description": f"{api} key (from KeyScout vault)", "password": True})
    for sid in remove or []:
        cfg[key].pop(sid, None)
    changed = json.dumps(cfg, sort_keys=True) != before
    if dry_run or not changed:
        return {"path": path, "changed": changed, "dry_run": dry_run, "config": cfg, "backup": None}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    b = backup(path)
    tmp = path + ".tmp"; json.dump(cfg, open(tmp, "w"), indent=2); os.replace(tmp, path)
    return {"path": path, "changed": True, "dry_run": False, "config": cfg, "backup": b}
