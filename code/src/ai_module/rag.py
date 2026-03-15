import os
import json
import numpy as np
from src.ai_module.client import MistralClient

DB_FILE = os.path.join(os.path.dirname(__file__), "..", "errors_db.json")

# Lazy-loaded globals — only initialized on first use
_embedder = None
_index = None
documents = []

def _get_embedder_and_index():
    """Lazy-initialize the SentenceTransformer and FAISS index on first use."""
    global _embedder, _index
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
    embedder, index = _get_embedder_and_index()
    with open(DB_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    for key, value in raw.items():
        text = f"Error: {key}\nCategory: {value['category']}\nSolution: {value['solution']}"
        embedding = embedder.encode(text)
        index.add(np.array([embedding], dtype="float32"))
        documents.append(text)

def rag_query(error_text: str):
    """Retrieve context from FAISS and query Mistral."""
    embedder, index = _get_embedder_and_index()
    query_embedding = embedder.encode(error_text)
    D, I = index.search(np.array([query_embedding], dtype="float32"), k=3)

    context = "\n".join([documents[i] for i in I[0] if 0 <= i < len(documents)])
    ai_client = MistralClient()
    
    prompt = f"[INST] You are a troubleshooting assistant. Explain the following error and provide a step-by-step fix.\n\nError: {error_text}\nRelevant context from similar errors:\n{context} [/INST]"
    
    ai_response = ai_client.generate(prompt)
    return ai_response.get("response") or ai_response.get("text")

def cache_suggestion(error_text: str, suggestion: str):
    """Save new AI suggestion into FAISS (and JSON for backup)."""
    embedder, index = _get_embedder_and_index()
    embedding = embedder.encode(error_text)
    index.add(np.array([embedding], dtype="float32"))
    documents.append(f"Error: {error_text}\nCategory: AI-generated\nSolution: {suggestion}")

    # Optional: still update JSON
    db = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    db[error_text] = {"category": "AI-generated", "solution": suggestion}
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)