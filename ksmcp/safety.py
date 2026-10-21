"""MCP server safety score (automated heuristics — not an audit)."""
from __future__ import annotations

from typing import Any

from .catalog import CATALOG


def safety_score(server: dict, api: str) -> dict[str, Any]:
    """Return score 0–100, letter grade, and factor list.

    Factors: official/vendor namespace, public source, local package vs third-party
    relay, declared license, recent activity (when meta present).
    """
    factors: list[dict[str, Any]] = []
    score = 50  # baseline
    ns = (server.get("name") or "").split("/")[0]
    official = ns in CATALOG.get(api, {}).get("official_ns", [])
    if official:
        score += 25
        factors.append({"id": "official", "delta": 25, "note": "vendor/official namespace"})
    else:
        factors.append({"id": "official", "delta": 0, "note": "not in known official namespace"})

    repo = (server.get("repository") or {}).get("url") or ""
    if repo.startswith("https://github.com/") or repo.startswith("https://gitlab.com/"):
        score += 15
        factors.append({"id": "public_source", "delta": 15, "note": f"public source: {repo}"})
    else:
        score -= 10
        factors.append({"id": "public_source", "delta": -10, "note": "no public source URL"})

    has_pkg = bool(server.get("packages"))
    has_remote = bool(server.get("remotes"))
    if has_pkg:
        score += 10
        factors.append({"id": "local", "delta": 10, "note": "installable local package"})
    if has_remote and not has_pkg:
        score -= 5
        factors.append({"id": "remote_only", "delta": -5, "note": "remote-only (no local package)"})

    # Third-party relays
    relay_ns = ("ai.smithery", "com.composio", "proxy.")
    if any(ns.startswith(p) or ns == p for p in relay_ns) or "smithery" in ns:
        score -= 20
        factors.append({"id": "third_party_relay", "delta": -20, "note": "third-party relay — key may leave your machine"})

    lic = (
        server.get("license")
        or (server.get("repository") or {}).get("license")
        or server.get("_meta", {}).get("license")
    )
    if lic:
        score += 5
        factors.append({"id": "license", "delta": 5, "note": f"license declared: {lic}"})
    else:
        factors.append({"id": "license", "delta": 0, "note": "no license in registry metadata"})

    # Recent activity from registry meta when present
    meta = server.get("_meta", {}) or {}
    official_meta = meta.get("io.modelcontextprotocol.registry/official", {}) or {}
    updated = official_meta.get("updatedAt") or official_meta.get("publishedAt") or meta.get("updatedAt")
    if updated:
        score += 5
        factors.append({"id": "recent_activity", "delta": 5, "note": f"registry activity: {updated}"})
    else:
        factors.append({"id": "recent_activity", "delta": 0, "note": "no activity timestamp in registry"})

    score = max(0, min(100, score))
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "factors": factors,
        "disclaimer": "automated check, not an audit",
    }
