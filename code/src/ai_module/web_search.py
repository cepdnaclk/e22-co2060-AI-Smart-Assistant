import os
from pathlib import Path

import requests

from src.settings import load_settings


def _load_project_env() -> None:
    """Load simple KEY=VALUE entries from the project's .env file."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"\''))


_load_project_env()


class WebSearch:
    """Small Tavily client used for questions that need current information."""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.url = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 5) -> str:
        if load_settings()["general"].get("offline_mode"):
            return "⚠️ Web search is disabled while Offline mode is enabled."
        if not self.api_key:
            return "⚠️ Web search is unavailable: TAVILY_API_KEY is not configured."

        try:
            response = requests.post(
                self.url,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_answer": True,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return f"⚠️ Web search failed: {exc}"
        except ValueError:
            return "⚠️ Web search failed: Tavily returned invalid JSON."

        results = []

        if data.get("answer"):
            results.append(f"Summary: {data['answer']}")

        for item in data.get("results", []):
            results.append(
                f"Title: {item.get('title', '')}\n"
                f"URL: {item.get('url', '')}\n"
                f"Content: {item.get('content', '')}"
            )

        return "\n\n".join(results)