import re

from src.ai_module.client import MistralClient
from src.ai_module.web_search import WebSearch
from src.settings import load_settings


_WEB_QUERY_PATTERNS = (
    r"\bsearch (?:online|the web|for)\b",
    r"\b(?:latest|current|today|recent|news|weather|price)\b",
    r"\bwhat is happening\b",
)


def needs_web_search(query: str) -> bool:
    return any(re.search(pattern, query, re.IGNORECASE) for pattern in _WEB_QUERY_PATTERNS)


def handle_user_query(query: str, history: list[dict]) -> str:
    if load_settings()["general"].get("offline_mode") or not needs_web_search(query):
        return MistralClient().chat(history).get("response", "")

    search_results = WebSearch().search(query)
    if search_results.startswith("⚠️"):
        return search_results

    prompt = (
        "Answer the user's question using the web results below. "
        "Mention uncertainty when the sources disagree.\n\n"
        f"Web results:\n{search_results}\n\nQuestion: {query}"
    )
    return MistralClient().chat([{"role": "user", "content": prompt}]).get("response", "")