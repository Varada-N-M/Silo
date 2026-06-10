"""
add_knowledge.py
────────────────
Utility to add your own project-specific snippets to the RAG knowledge base.
Run this whenever you want to teach the agent new patterns.

Usage:
    python add_knowledge.py                    # add example snippet interactively
    python add_knowledge.py --file my_code.py # ingest a Python/TS file as a snippet
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.rag_engine import RAGEngine


CATEGORIES = [
    "project_structure",
    "boilerplate",
    "endpoints",
    "schemas",
    "database",
    "migrations",
    "auth",
    "data_fetching",
    "routing",
    "config",
    "error_handling",
    "async",
    "testing",
    "deployment",
    "custom",
]


def add_snippet_interactive(rag: RAGEngine):
    print("\nAdd a new snippet to the knowledge base")
    print("─" * 40)

    snippet_id = input("Unique ID (e.g. 'my_custom_middleware'): ").strip()
    title = input("Title (e.g. 'Custom rate-limiting middleware'): ").strip()

    print(f"Category options: {', '.join(CATEGORIES)}")
    category = input("Category: ").strip() or "custom"

    print("Paste your code/content (type END on a new line to finish):")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    content = "\n".join(lines)

    snippet = {"id": snippet_id, "category": category, "title": title, "content": content}
    rag.index_knowledge([snippet])
    print(f"✅ Snippet '{title}' added to the knowledge base!")


def add_snippet_from_file(rag: RAGEngine, filepath: str):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r") as f:
        content = f.read()

    filename = os.path.basename(filepath)
    snippet_id = filename.replace(".", "_").replace(" ", "_").lower()
    title = f"File: {filename}"

    # Try to detect category from extension
    if filepath.endswith((".ts", ".tsx")):
        category = "custom_nextjs"
    elif filepath.endswith(".py"):
        category = "custom_fastapi"
    else:
        category = "custom"

    snippet = {"id": snippet_id, "category": category, "title": title, "content": content}
    rag.index_knowledge([snippet])
    print(f"✅ File '{filename}' indexed as snippet '{snippet_id}'")


def list_snippets(rag: RAGEngine):
    data = rag.collection.get(include=["metadatas"])
    if not data["ids"]:
        print("No snippets indexed yet.")
        return
    print(f"\n{'ID':<40} {'Category':<20} {'Title'}")
    print("─" * 90)
    for sid, meta in zip(data["ids"], data["metadatas"]):
        print(f"{sid:<40} {meta.get('category',''):<20} {meta.get('title','')}")


def main():
    parser = argparse.ArgumentParser(description="Manage the FullStack Agent knowledge base")
    parser.add_argument("--file",   type=str, help="Path to a file to ingest as a snippet")
    parser.add_argument("--list",   action="store_true", help="List all indexed snippets")
    parser.add_argument("--delete", type=str, metavar="ID", help="Delete a snippet by ID")
    args = parser.parse_args()

    rag = RAGEngine(persist_dir="./chroma_db")

    if args.list:
        list_snippets(rag)
    elif args.file:
        add_snippet_from_file(rag, args.file)
    elif args.delete:
        rag.collection.delete(ids=[args.delete])
        print(f"✅ Deleted snippet: {args.delete}")
    else:
        add_snippet_interactive(rag)


if __name__ == "__main__":
    main()