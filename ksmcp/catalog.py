"""Tiny stand-in for the KeyScout API catalog: API name -> key env-var patterns.
In production this comes from the ~4,942-API KeyScout catalog."""
from __future__ import annotations

import re

CATALOG = {
    "github": {
        "label": "GitHub",
        "env": [r"^GITHUB_(PERSONAL_ACCESS_)?TOKEN$", r"^GH_TOKEN$", r"^GITHUB_PAT$"],
        "aliases": ["github", "gh", "github token", "personal access token", "pat"],
        "official_ns": ["io.github.github"],
        "get_key": "https://github.com/settings/tokens",
        "free_tier": "Free",
    },
    "openai": {
        "label": "OpenAI",
        "env": [r"^OPENAI_API_KEY$"],
        "aliases": ["openai", "gpt"],
        "official_ns": ["com.openai"],
        "get_key": "https://platform.openai.com/api-keys",
        "free_tier": "check",
    },
    "anthropic": {
        "label": "Anthropic",
        "env": [r"^ANTHROPIC_API_KEY$", r"^CLAUDE_API_KEY$"],
        "aliases": ["anthropic", "claude"],
        "official_ns": ["com.anthropic"],
        "get_key": "https://console.anthropic.com/settings/keys",
        "free_tier": "check",
    },
    "stripe": {
        "label": "Stripe",
        "env": [r"^STRIPE_(SECRET_|API_)?KEY$"],
        "aliases": ["stripe"],
        "official_ns": ["com.stripe"],
        "get_key": "https://dashboard.stripe.com/apikeys",
        "free_tier": "test mode free",
    },
    "brave": {
        "label": "Brave Search",
        "env": [r"^BRAVE_(SEARCH_)?API_KEY$"],
        "aliases": ["brave"],
        "official_ns": ["io.github.brave"],
        "get_key": "https://brave.com/search/api/",
        "free_tier": "check",
    },
    "notion": {
        "label": "Notion",
        "env": [r"^NOTION_(API_)?(KEY|TOKEN)$", r"^NOTION_INTEGRATION_TOKEN$"],
        "aliases": ["notion"],
        "official_ns": ["com.notion", "io.github.makenotion"],
        "get_key": "https://www.notion.so/my-integrations",
        "free_tier": "Free",
    },
    "slack": {
        "label": "Slack",
        "env": [r"^SLACK_(BOT_)?TOKEN$"],
        "aliases": ["slack"],
        "official_ns": [],
        "get_key": "https://api.slack.com/apps",
        "free_tier": "Free",
    },
}

PREFIXES = [
    ("ghp_", "github"),
    ("github_pat_", "github"),
    ("sk_test_", "stripe"),
    ("sk_live_", "stripe"),
    ("rk_", "stripe"),
    ("sk-ant-", "anthropic"),
    ("sk-", "openai"),
    ("secret_", "notion"),
    ("ntn_", "notion"),
    ("xoxb-", "slack"),
]

GENERIC_NAMES = re.compile(
    r"^(API[_-]?KEY|TOKEN|ACCESS[_-]?TOKEN|AUTH[_-]?TOKEN|SECRET[_-]?KEY|BEARER)$",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")


def identify_key(key: str) -> str | None:
    for p, api in PREFIXES:
        if key.startswith(p):
            return api
    return None


def env_matches(api: str, name: str | None, description: str | None = None) -> bool:
    """True if an env/header name (or description for generic names) belongs to this API."""
    name = name or ""
    if any(re.match(p, name, re.IGNORECASE) for p in CATALOG[api]["env"]):
        return True
    # Authorization-style headers matched via placeholder extraction elsewhere
    if GENERIC_NAMES.match(name) and description:
        blob = description.lower()
        return any(a in blob for a in CATALOG[api].get("aliases", []))
    return False


def extract_placeholders(value: str | None) -> list[str]:
    if not value:
        return []
    return PLACEHOLDER_RE.findall(value)
