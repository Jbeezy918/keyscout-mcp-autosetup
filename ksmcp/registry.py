"""Official MCP Registry client (read-only) with a local cache."""
import json
import os
import time
import urllib.parse
import urllib.request

BASE = "https://registry.modelcontextprotocol.io/v0/servers"

def fetch(search, cache_dir, max_pages=5, ttl=86400):
    os.makedirs(cache_dir, exist_ok=True)
    cp = os.path.join(cache_dir, f"reg_{urllib.parse.quote(search, safe='')}.json")
    if os.path.exists(cp) and time.time() - os.path.getmtime(cp) < ttl:
        return json.load(open(cp))
    out, cursor = [], None
    for _ in range(max_pages):
        q = {"search": search, "limit": 100, "version": "latest"}
        if cursor: q["cursor"] = cursor
        req = urllib.request.Request(BASE + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "keyscout-mcp-proto"})
        d = json.load(urllib.request.urlopen(req, timeout=30))
        out += d.get("servers", [])
        cursor = d.get("metadata", {}).get("nextCursor")
        if not cursor: break
    json.dump(out, open(cp, "w"))
    return out
