"""Match registry servers to a KeyScout API and rank a recommended bundle."""
from __future__ import annotations

from .catalog import CATALOG, env_matches, extract_placeholders
from .safety import safety_score


def _meta(e):
    return e.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})


def _header_matches(api: str, header: dict) -> bool:
    name = header.get("name") or ""
    value = header.get("value") or ""
    desc = header.get("description") or header.get("title") or ""
    if env_matches(api, name, desc):
        return True
    for ph in extract_placeholders(value):
        if env_matches(api, ph):
            return True
        # Authorization: Bearer {GITHUB_TOKEN}
        if env_matches(api, ph, desc):
            return True
    # Loose: value text mentions an alias after stripping braces
    blob = (value + " " + desc).lower()
    if any(a in blob for a in CATALOG[api].get("aliases", [])):
        # Only when header looks secret-ish
        if name.lower() in ("authorization", "x-api-key", "api-key", "x-auth-token") or header.get("isSecret"):
            return True
    return False


def _env_matches_full(api: str, ev: dict) -> bool:
    return env_matches(api, ev.get("name"), ev.get("description") or ev.get("title"))


def key_inputs(srv, api):
    """Return list of (kind, name, transport_info) where the server takes the API key."""
    hits = []
    for p in srv.get("packages", []) or []:
        for ev in p.get("environmentVariables", []) or []:
            if _env_matches_full(api, ev):
                hits.append(("env", ev["name"], p))
    for r in srv.get("remotes", []) or []:
        for h in r.get("headers", []) or []:
            if _header_matches(api, h):
                # Prefer placeholder name when present (for config templating)
                phs = extract_placeholders(h.get("value"))
                label = next((p for p in phs if env_matches(api, p)), h.get("name"))
                hits.append(("header", label, r))
    return hits


def flags(s, api):
    f = []
    ns = s["name"].split("/")[0]
    if ns in CATALOG[api]["official_ns"]:
        f.append("official")
    if s.get("repository", {}).get("url"):
        f.append("has-repo")
    if s.get("packages"):
        f.append("local-package")
    if s.get("remotes"):
        f.append("remote")
    if ns.startswith("ai.smithery") or "smithery" in ns:
        f.append("smithery-proxy")
    return f


def score(s, api):
    """Legacy numeric rank (kept for sort stability). Prefer safety_score for display."""
    f = flags(s, api)
    sc = 0
    sc += 100 if "official" in f else 0
    sc += 10 if "has-repo" in f else -20
    sc += 5 if "local-package" in f else 0
    sc -= 15 if "smithery-proxy" in f else 0
    return sc


def candidates(entries, api):
    res = []
    for e in entries:
        s, m = e.get("server", {}), _meta(e)
        # Attach registry meta onto server for safety_score activity checks
        s = dict(s)
        if e.get("_meta"):
            s["_meta"] = e["_meta"]
        if m.get("status", "active") != "active" or m.get("isLatest") is False:
            continue
        hits = key_inputs(s, api)
        if not hits:
            continue
        safe = safety_score(s, api)
        res.append(
            {
                "server": s,
                "hits": hits,
                "score": score(s, api),
                "safety": safe,
                "flags": flags(s, api),
            }
        )
    res.sort(key=lambda c: (-c["safety"]["score"], -c["score"], c["server"]["name"]))
    return res


def bundle(cands, n=3):
    return cands[:n]
