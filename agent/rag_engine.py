"""
rag_engine.py
─────────────
Manages the ChromaDB vector store and Ollama embedding model.
Indexes all knowledge base snippets and provides semantic retrieval.
"""

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from typing import List, Dict

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL        = "http://localhost:11434"
EMBED_MODEL       = "nomic-embed-text"   # pull with: ollama pull nomic-embed-text
COLLECTION_NAME   = "fullstack_knowledge"
TOP_K             = 4                    # number of snippets to retrieve per query


class RAGEngine:
    """Handles indexing and retrieval of fullstack code patterns."""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.embed_fn = OllamaEmbeddingFunction(
            url=OLLAMA_URL,
            model_name=EMBED_MODEL,
        )
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Indexing ──────────────────────────────────────────────────────────────

    def index_knowledge(self, snippets: List[Dict], force_reindex: bool = False) -> None:
        """
        Index a list of knowledge snippets into ChromaDB.

        Args:
            snippets: List of dicts with keys: id, category, title, content
            force_reindex: If True, delete and re-add existing docs
        """
        existing_ids = set(self.collection.get()["ids"])

        ids, documents, metadatas = [], [], []

        for snippet in snippets:
            if snippet["id"] in existing_ids and not force_reindex:
                continue  # already indexed

            ids.append(snippet["id"])
            # Combine title + content for richer embedding
            documents.append(f"{snippet['title']}\n\n{snippet['content']}")
            metadatas.append({
                "category": snippet["category"],
                "title":    snippet["title"],
            })

        if not ids:
            return  # nothing new to index

        if force_reindex and existing_ids:
            self.collection.delete(ids=list(existing_ids))

        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"  ✓ Indexed {len(ids)} snippets")

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        """
        Retrieve the top-k most relevant snippets for a query.

        Returns:
            List of dicts: { title, category, content, distance }
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        snippets = []
        if not results["ids"] or not results["ids"][0]:
            return snippets

        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            snippets.append({
                "title":    meta.get("title", ""),
                "category": meta.get("category", ""),
                "content":  doc,
                "distance": round(dist, 4),
            })

        return snippets

    def format_context(self, snippets: List[Dict]) -> str:
        """Format retrieved snippets into a context block for the LLM prompt."""
        if not snippets:
            return "No relevant patterns found in the knowledge base."

        parts = []
        for i, s in enumerate(snippets, 1):
            parts.append(
                f"--- Pattern {i}: {s['title']} (category: {s['category']}) ---\n"
                f"{s['content']}"
            )
        return "\n\n".join(parts)

    def stats(self) -> Dict:
        return {
            "collection": COLLECTION_NAME,
            "total_snippets": self.collection.count(),
            "embed_model": EMBED_MODEL,
        }