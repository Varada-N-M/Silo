"""
agent.py
────────
FullStack Agent: CLI chatbot powered by CodeLlama + dual RAG.

Retrieval pipeline per query:
  1. Knowledge base  (curated FastAPI/Next.js patterns)  → RAGEngine
  2. Project store   (your actual project's code)        → ProjectStore
  3. Both contexts merged → CodeLlama prompt → streamed response
"""

import sys
import textwrap
from typing import List, Dict, Optional
from ollama import Client

OLLAMA_URL = "http://localhost:11434"
LLM_MODEL  = "codellama"

SYSTEM_PROMPT = """You are an expert fullstack developer assistant specializing in:
- FastAPI (Python) — async, SQLAlchemy, Pydantic v2, JWT auth, Alembic
- Next.js 14 (TypeScript) — App Router, Server Components, React Query, NextAuth
- PostgreSQL with SQLAlchemy async ORM
- Best practices: clean architecture, SOLID principles, type safety

You will receive two types of context:
  A) KNOWLEDGE BASE PATTERNS — curated best-practice snippets
  B) PROJECT CODE — actual code from the user's project (if a project is loaded)

Use (B) first to understand the user's existing conventions, then (A) to fill gaps.

Rules:
1. Always generate complete, production-ready code — no placeholders like `# TODO`
2. Match the user's existing code style and naming conventions from project context
3. Add brief comments explaining key decisions
4. If asked for a feature, generate BOTH the FastAPI endpoint AND the Next.js counterpart
5. Reference specific files from the project context when relevant (e.g. "in your models/user.py")
6. Be concise in explanations; prioritize code quality
"""


class FullStackAgent:
    """CLI agent with dual RAG: knowledge base + project-specific code."""

    def __init__(self, rag_engine, project_store=None):
        self.rag          = rag_engine       # global knowledge base
        self.proj_store   = project_store    # project ingestion store
        self.active_project: Optional[str] = None   # currently loaded project
        self.llm          = Client(host=OLLAMA_URL)
        self.history: List[Dict] = []

    # ── Project management ────────────────────────────────────────────────────

    def load_project(self, project_name: str):
        """Set the active project for retrieval."""
        if not self.proj_store:
            print("  ⚠  No ProjectStore configured.")
            return
        projects = {p["name"] for p in self.proj_store.list_projects()}
        if project_name not in projects:
            print(f"  ⚠  Project '{project_name}' not found. Ingest it first with /ingest.")
            return
        self.active_project = project_name
        print(f"  ✅ Loaded project: \033[92m{project_name}\033[0m")

    def unload_project(self):
        self.active_project = None
        print("  ✅ Project unloaded — using knowledge base only.")

    # ── Core: dual retrieval + generate ──────────────────────────────────────

    def chat(self, user_message: str) -> str:
        context_blocks = []

        # ── 1. Knowledge base retrieval ───────────────────────────────────
        kb_snippets = self.rag.retrieve(user_message)
        if kb_snippets:
            context_blocks.append(
                "## A) Knowledge Base Patterns\n\n"
                + self.rag.format_context(kb_snippets)
            )

        # ── 2. Project retrieval (if a project is loaded) ─────────────────
        if self.active_project and self.proj_store:
            proj_chunks = self.proj_store.retrieve(user_message, self.active_project)
            if proj_chunks:
                context_blocks.append(
                    self.proj_store.format_context(proj_chunks, self.active_project)
                )

        # ── 3. Build augmented prompt ─────────────────────────────────────
        context_str = "\n\n---\n\n".join(context_blocks) if context_blocks else "No context retrieved."
        project_note = (
            f"Active project: **{self.active_project}**"
            if self.active_project
            else "No project loaded (knowledge base only)"
        )

        augmented = (
            f"{context_str}\n\n"
            f"---\n\n"
            f"*{project_note}*\n\n"
            f"## User Request\n{user_message}"
        )

        self.history.append({"role": "user", "content": augmented})

        # ── 4. Stream from CodeLlama ──────────────────────────────────────
        stream = self.llm.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *self.history,
            ],
            stream=True,
        )

        full_response = ""
        print("\n\033[92mAgent:\033[0m ", end="", flush=True)
        for chunk in stream:
            delta = chunk["message"]["content"]
            print(delta, end="", flush=True)
            full_response += delta
        print()

        self.history.append({"role": "assistant", "content": full_response})
        return full_response

    def reset(self):
        self.history = []
        print("\033[93m[Memory cleared]\033[0m")

    # ── CLI Loop ──────────────────────────────────────────────────────────────

    def run_cli(self):
        banner = textwrap.dedent("""
        ╔══════════════════════════════════════════════════════════════╗
        ║         FullStack Agent — FastAPI + Next.js                  ║
        ║   Dual RAG: Knowledge Base + Project Code (CodeLlama)        ║
        ╠══════════════════════════════════════════════════════════════╣
        ║  /ingest  <path> [name]  — ingest a project directory        ║
        ║  /load    <name>         — load a project for retrieval      ║
        ║  /unload                 — unload current project            ║
        ║  /projects               — list all ingested projects        ║
        ║  /remove  <name>         — delete a project from the store   ║
        ║  /reset                  — clear conversation memory         ║
        ║  /stats                  — show knowledge base stats         ║
        ║  /exit                   — quit                              ║
        ╚══════════════════════════════════════════════════════════════╝
        """)
        print(banner)

        while True:
            # Show active project in prompt
            proj_label = f"\033[33m[{self.active_project}]\033[0m " if self.active_project else ""
            try:
                user_input = input(f"\n{proj_label}\033[96mYou:\033[0m ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nBye!")
                sys.exit(0)

            if not user_input:
                continue

            parts = user_input.split()
            cmd   = parts[0].lower()

            # ── Commands ──────────────────────────────────────────────────
            if cmd == "/exit":
                print("Bye!")
                sys.exit(0)

            elif cmd == "/reset":
                self.reset()

            elif cmd == "/stats":
                kb_stats = self.rag.stats()
                print(f"\033[93mKnowledge base:\033[0m {kb_stats}")
                if self.active_project and self.proj_store:
                    ps = self.proj_store.stats(self.active_project)
                    print(f"\033[93mProject '{self.active_project}':\033[0m {ps.get('stats', {})}")

            elif cmd == "/ingest":
                if not self.proj_store:
                    print("  ⚠  ProjectStore not configured.")
                    continue
                if len(parts) < 2:
                    print("  Usage: /ingest <path> [project_name]")
                    continue
                path = parts[1]
                name = parts[2] if len(parts) > 2 else None
                try:
                    self.proj_store.ingest(path, project_name=name)
                except FileNotFoundError as e:
                    print(f"  ❌ {e}")

            elif cmd == "/load":
                if len(parts) < 2:
                    print("  Usage: /load <project_name>")
                    continue
                self.load_project(parts[1])

            elif cmd == "/unload":
                self.unload_project()

            elif cmd == "/projects":
                if not self.proj_store:
                    print("  ⚠  ProjectStore not configured.")
                    continue
                projects = self.proj_store.list_projects()
                if not projects:
                    print("  No projects ingested yet.")
                else:
                    print(f"\n  {'Name':<25} {'Files':>6} {'Chunks':>8}  {'Ingested'}")
                    print("  " + "─" * 60)
                    for p in projects:
                        active = " ◀ active" if p["name"] == self.active_project else ""
                        print(f"  {p['name']:<25} {p['files']:>6} {p['chunks']:>8}  {p['ingested_at']}{active}")

            elif cmd == "/remove":
                if not self.proj_store or len(parts) < 2:
                    print("  Usage: /remove <project_name>")
                    continue
                self.proj_store.remove_project(parts[1])
                if self.active_project == parts[1]:
                    self.active_project = None

            elif cmd == "/help":
                print("  Ask anything about FastAPI, Next.js, SQLAlchemy, or JWT auth!")
                print("  Use /ingest to add your project, then /load to activate it.")

            else:
                # Normal chat
                self.chat(user_input)