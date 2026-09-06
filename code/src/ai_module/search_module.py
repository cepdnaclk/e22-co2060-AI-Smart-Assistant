import os
from pathlib import Path
from dotenv import load_dotenv
from tavily import TavilyClient

# Load environment variables from the project's .env file.
# Use an explicit path so .env is found even when the working directory differs.
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
if not ENV_PATH.exists():
    print(f"[DEBUG] .env file not found at {ENV_PATH}")
else:
    load_dotenv(dotenv_path=ENV_PATH)


def web_search_tavily(query, max_results=5):
    """
    Perform a web search using Tavily and return top results as
    formatted strings: "Title - Snippet (URL)"
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("[DEBUG] TAVILY_API_KEY is missing or empty")
        return []

    print("tavily search")

    try:
        client = TavilyClient(api_key=api_key)
        results = client.search(query, max_results=max_results)
    except Exception as e:
        print(f"[DEBUG] Tavily request failed: {e}")
        return []

    snippets = []
    for r in results.get("results", []):
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("content", "")
        snippets.append(f"{title} - {snippet} ({url})")

    return snippets