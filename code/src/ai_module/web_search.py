import os

import requests


class WebSearch:
    """Small Tavily client used for questions that need current information."""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.url = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 5) -> str:
        if not self.api_key:
            return ""

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