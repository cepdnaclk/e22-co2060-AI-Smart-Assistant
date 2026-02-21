import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from src.ai_module.client import MistralClient

DB_FILE = os.path.join(os.path.dirname(__file__), "..", "errors_db.json")

# Initialize FAISS index
embedder = SentenceTransformer("all-MiniLM-L6-v2")
dimension = embedder.get_sentence_embedding_dimension()
index = faiss.IndexFlatL2(dimension)

# Keep mapping FAISS IDs → documents
documents = []

def build_faiss_index():
    """Load existing JSON DB into FAISS vector store."""
    if not os.path.exists(DB_FILE):
        return
    with open(DB_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    for key, value in raw.items():
        text = f"Error: {key}\nCategory: {value['category']}\nSolution: {value['solution']}"
        embedding = embedder.encode(text)
        index.add(np.array([embedding], dtype="float32"))
        documents.append(text)

def rag_query(error_text: str):
    """Retrieve context from FAISS and query Mistral."""
    query_embedding = embedder.encode(error_text)
    D, I = index.search(np.array([query_embedding], dtype="float32"), k=3)

    context = "\n".join([documents[i] for i in I[0] if i < len(documents)])
    ai_client = MistralClient()
    ai_response = ai_client.generate(
        f"You are a troubleshooting assistant.\n"
        f"Error: {error_text}\n"
        f"Relevant context:\n{context}\n"
        f"Explain the error and provide a step-by-step fix."
    )
    return ai_response.get("response") or ai_response.get("text")

def cache_suggestion(error_text: str, suggestion: str):
    """Save new AI suggestion into FAISS (and JSON for backup)."""
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