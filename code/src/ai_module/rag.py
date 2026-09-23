import os
import json
import threading
import numpy as np
from src.ai_module.client import MistralClient

DB_FILE = os.path.join(os.path.dirname(__file__), "..", "errors_db.json")
AI_CATEGORY = "AI-generated"

# Lazy-loaded globals — only initialized on first use
_embedder = None
_index = None
documents = []
# Guards _index/documents: the index can be rebuilt from a background thread
_lock = threading.RLock()

def _get_embedder_and_index():
    """Lazy-initialize the SentenceTransformer and FAISS index on first use."""
    global _embedder, _index
    with _lock:
        if _embedder is None:
            import faiss
            from sentence_transformers import SentenceTransformer
            print("[RAG] Loading sentence transformer model...")
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            dimension = _embedder.get_sentence_embedding_dimension()
            _index = faiss.IndexFlatL2(dimension)
            print("[RAG] Model loaded.")
        return _embedder, _index

def build_faiss_index():
    """Load existing JSON DB into FAISS vector store."""
    if not os.path.exists(DB_FILE):
        return
    with _lock:
        embedder, index = _get_embedder_and_index()
        with open(DB_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for key, value in raw.items():
            text = f"Error: {key}\nCategory: {value.get('category', '')}\nSolution: {value.get('solution', '')}"
            embedding = embedder.encode(text)
            index.add(np.array([embedding], dtype="float32"))
            documents.append(text)

def rebuild_index():
    """Clear the FAISS index and rebuild it from errors_db.json."""
    global _index
    with _lock:
        embedder, index = _get_embedder_and_index()
        import faiss
        _index = faiss.IndexFlatL2(embedder.get_sentence_embedding_dimension())
        documents.clear()
        build_faiss_index()
        print(f"[RAG] Index rebuilt with {_index.ntotal} entries.")

def delete_ai_generated() -> int:
    """Remove every AI-generated entry from errors_db.json. Returns how many were removed."""
    if not os.path.exists(DB_FILE):
        return 0
    with open(DB_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)
    kept = {k: v for k, v in db.items() if v.get("category") != AI_CATEGORY}
    removed = len(db) - len(kept)
    if removed:
        tmp_path = DB_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(kept, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, DB_FILE)
    return removed

def rag_query(error_text: str):
    """Retrieve context from FAISS and query Mistral."""
    # Build context only if the index has entries
    context = ""
    with _lock:
        embedder, index = _get_embedder_and_index()
        if index.ntotal > 0:
            query_embedding = embedder.encode(error_text)
            D, I = index.search(np.array([query_embedding], dtype="float32"), k=3)
            context = "\n".join([documents[i] for i in I[0] if 0 <= i < len(documents)])

    ai_client = MistralClient()
    prompt = f"[INST] You are a troubleshooting assistant. Explain the following error and provide a step-by-step fix.\n\nError: {error_text}\nRelevant context from similar errors:\n{context} [/INST]"

    ai_response = ai_client.generate(prompt)
    return ai_response.get("response") or ai_response.get("text")

def cache_suggestion(error_text: str, suggestion: str):
    """Save new AI suggestion into FAISS (and JSON for backup)."""
    with _lock:
        embedder, index = _get_embedder_and_index()
        embedding = embedder.encode(error_text)
        index.add(np.array([embedding], dtype="float32"))
        documents.append(f"Error: {error_text}\nCategory: {AI_CATEGORY}\nSolution: {suggestion}")

    # Optional: still update JSON
    db = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    db[error_text] = {"category": AI_CATEGORY, "solution": suggestion}
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)
