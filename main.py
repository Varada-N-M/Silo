"""
main.py
───────
Entry point for the FullStack Agent.
Bootstraps both the knowledge base RAG and the project ingestion store,
then starts the CLI chat loop.
"""

import sys
import argparse


def bootstrap_knowledge_rag(persist_dir: str = ".chroma") -> "RAGEngine":
    from agent.rag_engine import RAGEngine
    from knowledge_base.fastapi_patterns import FASTAPI_KNOWLEDGE
    from knowledge_base.nextjs_patterns import NEXTJS_KNOWLEDGE
    from knowledge_base.db_auth_patterns import DATABASE_KNOWLEDGE, AUTH_KNOWLEDGE

    print("🔧 Initialising knowledge base RAG...")
    rag = RAGEngine(persist_dir=persist_dir)

    all_snippets = FASTAPI_KNOWLEDGE + NEXTJS_KNOWLEDGE + DATABASE_KNOWLEDGE + AUTH_KNOWLEDGE
    print(f"📚 Indexing {len(all_snippets)} knowledge snippets (skips already-indexed)...")
    rag.index_knowledge(all_snippets)

    stats = rag.stats()
    print(f"✅ Knowledge base ready — {stats['total_snippets']} snippets\n")
    return rag


def bootstrap_project_store(persist_dir: str = ".chroma") -> "ProjectStore":
    from ingestion.project_store import ProjectStore
    return ProjectStore(persist_dir=persist_dir)


def main():
    parser = argparse.ArgumentParser(description="FullStack Agent — FastAPI + Next.js")
    parser.add_argument("--reindex",  action="store_true", help="Force re-index knowledge base")
    parser.add_argument("--ingest",   type=str, metavar="PATH", help="Ingest a project directory then start")
    parser.add_argument("--name",     type=str, default=None, help="Project name for --ingest")
    parser.add_argument("--load",     type=str, default=None, help="Load a project by name on startup")
    parser.add_argument("--query",    type=str, default=None, help="Single query, non-interactive mode")
    parser.add_argument("--persist",  type=str, default=".chroma", help="ChromaDB persist directory")
    args = parser.parse_args()

    # ── Bootstrap ──────────────────────────────────────────────────────────
    rag          = bootstrap_knowledge_rag(persist_dir=args.persist)
    proj_store   = bootstrap_project_store(persist_dir=args.persist)

    if args.reindex:
        print("🔄 Force re-indexing knowledge base...")
        from knowledge_base.fastapi_patterns import FASTAPI_KNOWLEDGE
        from knowledge_base.nextjs_patterns import NEXTJS_KNOWLEDGE
        from knowledge_base.db_auth_patterns import DATABASE_KNOWLEDGE, AUTH_KNOWLEDGE
        snippets = FASTAPI_KNOWLEDGE + NEXTJS_KNOWLEDGE + DATABASE_KNOWLEDGE + AUTH_KNOWLEDGE
        rag.index_knowledge(snippets, force_reindex=True)
        print("✅ Re-index complete\n")

    if args.ingest:
        print(f"📂 Ingesting project: {args.ingest}")
        proj_store.ingest(args.ingest, project_name=args.name)
        print()

    # ── Agent ──────────────────────────────────────────────────────────────
    from agent.agent import FullStackAgent
    agent = FullStackAgent(rag_engine=rag, project_store=proj_store)

    if args.load:
        agent.load_project(args.load)

    if args.query:
        agent.chat(args.query)
        sys.exit(0)

    agent.run_cli()


if __name__ == "__main__":
    main()