from tavily import TavilyClient
import os

def test_tavily():
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = client.search("latest graphic cards 2026", max_results=5)

    print("=== Raw Tavily Results ===")
    for r in results["results"]:
        print(f"{r['title']} - {r['content']} ({r['url']})")

if __name__ == "__main__":
    test_tavily()