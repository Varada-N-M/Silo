"""
project_store.py
────────────────
Manages per-project ChromaDB collections.

Each ingested project gets its own isolated collection:
    project_<sanitised_name>

This keeps project code separate from the global knowledge base
and allows fast per-project retrieval.
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from ingestion.chunker import Chunk, scan_project

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434"
EMBED_MODEL  = "nomic-embed-text"
TOP_K        = 5
BATCH_SIZE   = 50   # chunks per ChromaDB upsert call (avoids memory spikes)

# Registry file — tracks all ingested projects
REGISTRY_FILE = ".chroma/project_registry.json"


def _sanitise_name(name: str) -> str:
    """Convert any string to a valid ChromaDB collection name."""
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return f"project_{name[:40]}"   # ChromaDB max collection name = 63 chars


# ── Registry ──────────────────────────────────────────────────────────────────

class ProjectRegistry:
    """Persists metadata about all ingested projects."""

    def __init__(self, persist_dir: str):
        self.registry_path = Path(persist_dir) / "project_registry.json"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict = self._load()

    def _load(self) -> Dict:
        if self.registry_path.exists():
            return json.loads(self.registry_path.read_text())
        return {}

    def _save(self):
        self.registry_path.write_text(json.dumps(self._data, indent=2))

    def register(self, project_name: str, project_root: str, collection_name: str, stats: Dict):
        self._data[project_name] = {
            "project_root":     project_root,
            "collection_name":  collection_name,
            "ingested_at":      time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats":            stats,
        }
        self._save()

    def get(self, project_name: str) -> Optional[Dict]:
        return self._data.get(project_name)

    def all(self) -> Dict:
        return self._data

    def remove(self, project_name: str):
        self._data.pop(project_name, None)
        self._save()


# ── Project Store ─────────────────────────────────────────────────────────────

class ProjectStore:
    """
    Ingests a project directory into a dedicated ChromaDB collection
    and retrieves relevant chunks for a given query.
    """

    def __init__(self, persist_dir: str = ".chroma"):
        self.persist_dir = persist_dir
        self.embed_fn = OllamaEmbeddingFunction(
            url=OLLAMA_URL,
            model_name=EMBED_MODEL,
        )
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.registry = ProjectRegistry(persist_dir)

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest(
        self,
        project_root: str,
        project_name: Optional[str] = None,
        force: bool = False,
    ) -> Dict:
        """
        Scan a project directory, chunk all files, embed and store in ChromaDB.

        Args:
            project_root: Path to the project directory
            project_name: Optional friendly name (defaults to directory name)
            force:        Re-ingest even if already indexed

        Returns:
            Ingestion stats dict
        """
        root = Path(project_root).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Project not found: {root}")

        project_name = project_name or root.name
        collection_name = _sanitise_name(project_name)

        # Check if already ingested
        existing = self.registry.get(project_name)
        if existing and not force:
            print(f"  ℹ  '{project_name}' already ingested. Use force=True to re-index.")
            return existing["stats"]

        # Drop and recreate collection on force re-index
        if force:
            try:
                self.client.delete_collection(collection_name)
            except Exception:
                pass

        collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine", "project": project_name},
        )

        # ── Scan + chunk ──────────────────────────────────────────────────────
        print(f"  📂 Scanning '{root}' ...")
        all_chunks: List[Chunk] = list(scan_project(root))

        if not all_chunks:
            print("  ⚠  No supported files found.")
            return {"total_chunks": 0}

        print(f"  ✂  {len(all_chunks)} chunks from {len({c.file_path for c in all_chunks})} files")

        # ── Get already-indexed IDs to skip duplicates ─────────────────────
        existing_ids = set(collection.get()["ids"])

        # ── Batch upsert ──────────────────────────────────────────────────────
        new_chunks = [c for c in all_chunks if c.chunk_id not in existing_ids]
        indexed = 0

        for i in range(0, len(new_chunks), BATCH_SIZE):
            batch = new_chunks[i : i + BATCH_SIZE]
            collection.add(
                ids=[c.chunk_id for c in batch],
                documents=[self._format_document(c) for c in batch],
                metadatas=[self._format_metadata(c) for c in batch],
            )
            indexed += len(batch)
            print(f"  ⬆  {indexed}/{len(new_chunks)} chunks indexed...", end="\r")

        print()  # newline after progress line

        # ── File-type breakdown ───────────────────────────────────────────────
        by_type: Dict[str, int] = {}
        for c in all_chunks:
            by_type[c.file_type] = by_type.get(c.file_type, 0) + 1

        stats = {
            "total_chunks":  len(all_chunks),
            "new_chunks":    indexed,
            "skipped":       len(all_chunks) - indexed,
            "files":         len({c.file_path for c in all_chunks}),
            "by_type":       by_type,
        }

        self.registry.register(project_name, str(root), collection_name, stats)
        print(f"  ✅ Ingested '{project_name}': {stats['files']} files → {indexed} new chunks")
        return stats

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        project_name: str,
        top_k: int = TOP_K,
        file_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        Retrieve the most relevant chunks from a specific project.

        Args:
            query:        Natural language or code query
            project_name: Name used during ingestion
            top_k:        Number of results to return
            file_type:    Optional filter — e.g. "py", "tsx"

        Returns:
            List of dicts: { file_path, file_type, start_line, end_line, content, distance }
        """
        entry = self.registry.get(project_name)
        if not entry:
            raise ValueError(f"Project '{project_name}' not ingested. Run ingest() first.")

        collection = self.client.get_collection(
            name=entry["collection_name"],
            embedding_function=self.embed_fn,
        )

        where = {"file_type": file_type} if file_type else None

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
            where=where,
        )

        chunks = []
        if not results["ids"] or not results["ids"][0]:
            return chunks

        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "file_path":  meta.get("file_path", ""),
                "file_type":  meta.get("file_type", ""),
                "start_line": meta.get("start_line", 0),
                "end_line":   meta.get("end_line", 0),
                "content":    doc,
                "distance":   round(dist, 4),
            })

        return chunks

    def retrieve_multi_project(
        self,
        query: str,
        project_names: List[str],
        top_k_per_project: int = 3,
    ) -> Dict[str, List[Dict]]:
        """Retrieve from multiple projects simultaneously."""
        results = {}
        for name in project_names:
            try:
                results[name] = self.retrieve(query, name, top_k=top_k_per_project)
            except ValueError:
                results[name] = []
        return results

    def format_context(self, chunks: List[Dict], project_name: str) -> str:
        """Format project chunks into a context block for the LLM."""
        if not chunks:
            return f"No relevant code found in project '{project_name}'."

        parts = [f"### Project: {project_name}"]
        for i, c in enumerate(chunks, 1):
            lang = c["file_type"]
            parts.append(
                f"\n**{c['file_path']}** (lines {c['start_line']}–{c['end_line']})\n"
                f"```{lang}\n{c['content']}\n```"
            )
        return "\n".join(parts)

    # ── Management ────────────────────────────────────────────────────────────

    def list_projects(self) -> List[Dict]:
        """Return all registered projects with their stats."""
        projects = []
        for name, data in self.registry.all().items():
            projects.append({
                "name":         name,
                "root":         data["project_root"],
                "ingested_at":  data["ingested_at"],
                "files":        data["stats"].get("files", "?"),
                "chunks":       data["stats"].get("total_chunks", "?"),
            })
        return projects

    def remove_project(self, project_name: str):
        """Delete a project's collection and registry entry."""
        entry = self.registry.get(project_name)
        if not entry:
            print(f"  ⚠  Project '{project_name}' not found.")
            return
        try:
            self.client.delete_collection(entry["collection_name"])
        except Exception:
            pass
        self.registry.remove(project_name)
        print(f"  ✅ Removed project '{project_name}'")

    def stats(self, project_name: str) -> Dict:
        entry = self.registry.get(project_name)
        if not entry:
            return {}
        return entry

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _format_document(chunk: Chunk) -> str:
        """Document string stored in ChromaDB — includes path for context."""
        return f"# File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n\n{chunk.content}"

    @staticmethod
    def _format_metadata(chunk: Chunk) -> Dict:
        return {
            "file_path":  chunk.file_path,
            "file_type":  chunk.file_type,
            "start_line": chunk.start_line,
            "end_line":   chunk.end_line,
        }