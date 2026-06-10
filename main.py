"""
main.py
───────
Entry point for the FullStack Agent.
Bootstraps the RAG knowledge base and starts the CLI chat loop.
"""

import sys
import argparse

def bootstrap_rag() -> "RAGEngine":
    """Import all knowledge bases and index them into ChromaDB."""
    from agent.rag_engine import RAGEngine
    from knowledge_base.fastapi_patterns import FASTAPI_KNOWLEDGE
    from knowledge_base.nextjs_patterns import NEXTJS_KNOWLEDGE
    from knowledge_base.db_auth_patterns import DATABASE_KNOWLEDGE, AUTH_KNOWLEDGE

    print("🔧 Initialising RAG engine...")
    rag = RAGEngine(persist_dir="./chroma_db")

    all_snippets = FASTAPI_KNOWLEDGE + NEXTJS_KNOWLEDGE + DATABASE_KNOWLEDGE + AUTH_KNOWLEDGE

    print(f"📚 Indexing {len(all_snippets)} knowledge snippets (skips already-indexed)...")
    rag.index_knowledge(all_snippets)

    stats = rag.stats()
    print(f"✅ Knowledge base ready — {stats['total_snippets']} snippets in ChromaDB")
    return rag


def main():
    parser = argparse.ArgumentParser(description="FullStack Agent — FastAPI + Next.js")
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force re-index all knowledge base snippets",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Run a single query and exit (non-interactive mode)",
    )
    args = parser.parse_args()

    # ── Bootstrap ──────────────────────────────────────────────────────────
    rag = bootstrap_rag()

    if args.reindex:
        print("🔄 Force re-indexing...")
        from knowledge_base.fastapi_patterns import FASTAPI_KNOWLEDGE
        from knowledge_base.nextjs_patterns import NEXTJS_KNOWLEDGE
        from knowledge_base.db_auth_patterns import DATABASE_KNOWLEDGE, AUTH_KNOWLEDGE
        all_snippets = FASTAPI_KNOWLEDGE + NEXTJS_KNOWLEDGE + DATABASE_KNOWLEDGE + AUTH_KNOWLEDGE
        rag.index_knowledge(all_snippets, force_reindex=True)
        print("✅ Re-index complete")

    # ── Agent ──────────────────────────────────────────────────────────────
    from agent.agent import FullStackAgent
    agent = FullStackAgent(rag_engine=rag)

    if args.query:
        # Single-shot mode
        agent.chat(args.query)
        sys.exit(0)

    # Interactive CLI mode
    agent.run_cli()


if __name__ == "__main__":
    main()