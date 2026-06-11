"""
ingest_project.py
─────────────────
Standalone CLI tool for managing project ingestion.
Use this to ingest, inspect, and manage projects without starting the full agent.

Usage:
    python ingest_project.py ingest  ./my-fastapi-app
    python ingest_project.py ingest  ./my-nextjs-app --name frontend
    python ingest_project.py list
    python ingest_project.py inspect ./my-fastapi-app
    python ingest_project.py search  my-project "how is auth handled"
    python ingest_project.py remove  my-project
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.project_store import ProjectStore
from ingestion.chunker import summarise_scan


def cmd_ingest(args):
    store = ProjectStore(persist_dir=args.persist)
    store.ingest(
        project_root=args.path,
        project_name=args.name,
        force=args.force,
    )


def cmd_list(args):
    store = ProjectStore(persist_dir=args.persist)
    projects = store.list_projects()
    if not projects:
        print("No projects ingested yet.")
        return
    print(f"\n{'Name':<25} {'Files':>6} {'Chunks':>8}  Ingested At")
    print("─" * 65)
    for p in projects:
        print(f"{p['name']:<25} {p['files']:>6} {p['chunks']:>8}  {p['ingested_at']}")


def cmd_inspect(args):
    """Show what would be chunked without actually indexing."""
    print(f"\nScanning: {args.path}")
    summary = summarise_scan(args.path)
    print(f"\n{'Extension':<12}  Chunks")
    print("─" * 25)
    for ext, count in sorted(summary["by_type"].items()):
        print(f"  {ext:<10}  {count}")
    print("─" * 25)
    print(f"  {'TOTAL':<10}  {summary['total_chunks']}")
    print(f"\nProject root: {summary['project_root']}")


def cmd_search(args):
    """Search a project's indexed code."""
    store = ProjectStore(persist_dir=args.persist)
    print(f"\nSearching '{args.project}' for: {args.query}\n")
    results = store.retrieve(args.query, args.project, top_k=args.top_k)
    if not results:
        print("No results found.")
        return
    for i, r in enumerate(results, 1):
        print(f"{'─'*60}")
        print(f"  [{i}] {r['file_path']}  (lines {r['start_line']}–{r['end_line']})  dist={r['distance']}")
        print(f"{'─'*60}")
        # Print first 20 lines of content
        lines = r["content"].splitlines()[:20]
        print("\n".join(f"  {l}" for l in lines))
        if len(r["content"].splitlines()) > 20:
            print("  ... (truncated)")
        print()


def cmd_remove(args):
    store = ProjectStore(persist_dir=args.persist)
    store.remove_project(args.project)


def main():
    parser = argparse.ArgumentParser(
        description="FullStack Agent — Project Ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--persist", default=".chroma", help="ChromaDB directory (default: .chroma)")

    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest a project directory")
    p_ingest.add_argument("path", help="Path to project root")
    p_ingest.add_argument("--name", default=None, help="Friendly project name")
    p_ingest.add_argument("--force", action="store_true", help="Re-ingest even if already indexed")

    # list
    sub.add_parser("list", help="List all ingested projects")

    # inspect
    p_inspect = sub.add_parser("inspect", help="Preview what will be chunked (no indexing)")
    p_inspect.add_argument("path", help="Path to project root")

    # search
    p_search = sub.add_parser("search", help="Search a project's code")
    p_search.add_argument("project", help="Project name")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--top-k", type=int, default=5, help="Number of results (default: 5)")

    # remove
    p_remove = sub.add_parser("remove", help="Remove a project from the store")
    p_remove.add_argument("project", help="Project name")

    args = parser.parse_args()

    dispatch = {
        "ingest":  cmd_ingest,
        "list":    cmd_list,
        "inspect": cmd_inspect,
        "search":  cmd_search,
        "remove":  cmd_remove,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()