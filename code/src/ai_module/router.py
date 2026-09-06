from src.ai_module.search_module import web_search_tavily
from src.ai_module.client import MistralClient


def handle_user_query(query: str, history=None):
    decision_prompt = (
        "You are a router. If the user query requires fresh info from the web, "
        "respond ONLY with 'WEB_SEARCH: <query>'. Otherwise, answer normally."
    )
    # Use the provided history (with user profile context) and append router decision
    if history:
        routing_history = history.copy()
        # Replace the system prompt to include routing instructions
        routing_history[0] = {
            "role": "system",
            "content": history[0]["content"] + "\n\n" + decision_prompt
        }
    else:
        routing_history = [
            {"role": "system", "content": decision_prompt},
            {"role": "user", "content": query},
        ]
    result = MistralClient().chat(routing_history)

    # Strip whitespace immediately so the startswith check below is reliable
    response_text = result.get("response", "").strip()

    print(f"[DEBUG] Router raw response: {response_text}")

    if response_text.startswith("WEB_SEARCH:"):
        search_query = response_text.split("WEB_SEARCH:", 1)[1].strip()
        print(f"[DEBUG] Ollama requested web search for: {search_query}")

        try:
            results = web_search_tavily(search_query)
        except Exception as e:
            print(f"[DEBUG] Tavily error: {e}")
            results = []

        if results:
            print(f"[DEBUG] Tavily returned {len(results)} results")
            for idx, r in enumerate(results, 1):
                print(f"[DEBUG] Result {idx}: {r}")
        else:
            print("[DEBUG] Tavily returned no results")

        if results:
            context = "\n".join(results)
            prompt = (
                f"Summarize and answer based on these search results:\n{context}\n\n"
                f"Question: {query}"
            )
            summary_result = MistralClient().chat([{"role": "user", "content": prompt}])
            return summary_result.get("response", "⚠️ AI summary unavailable.")
        else:
            return "⚠️ No Tavily search results found."
    else:
        return response_text