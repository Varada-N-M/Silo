"""
agent.py
────────
FullStack Agent: CLI chatbot powered by CodeLlama + RAG.
Answers questions and generates code for FastAPI + Next.js projects.
"""

import sys
import textwrap
from typing import List, Dict
from ollama import Client

OLLAMA_URL  = "http://localhost:11434"
LLM_MODEL   = "codellama"           # ollama pull codellama

SYSTEM_PROMPT = """You are an expert fullstack developer assistant specializing in:
- FastAPI (Python) — async, SQLAlchemy, Pydantic v2, JWT auth, Alembic
- Next.js 14 (TypeScript) — App Router, Server Components, React Query, NextAuth
- PostgreSQL with SQLAlchemy async ORM
- Best practices: clean architecture, SOLID principles, type safety

You will be given RELEVANT PATTERNS from a curated knowledge base.
Use them as your primary reference when generating code.

Rules:
1. Always generate complete, production-ready code — no placeholders like `# TODO`
2. Follow the patterns from the knowledge base when applicable
3. Add brief comments explaining key decisions
4. If asked for a feature, generate BOTH the FastAPI endpoint AND the Next.js counterpart
5. Be concise in explanations; prioritize code quality
6. If a pattern is not in the knowledge base, use your training knowledge but flag it
"""


class FullStackAgent:
    """CLI agent that uses RAG + CodeLlama to help build fullstack apps."""

    def __init__(self, rag_engine):
        self.rag = rag_engine
        self.llm = Client(host=OLLAMA_URL)
        self.history: List[Dict] = []   # multi-turn conversation memory

    # ── Core: generate one response ───────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        # 1. Retrieve relevant patterns from the knowledge base
        snippets  = self.rag.retrieve(user_message)
        context   = self.rag.format_context(snippets)

        # 2. Build the augmented prompt
        augmented_user_msg = (
            f"## Relevant patterns from the knowledge base:\n\n"
            f"{context}\n\n"
            f"---\n\n"
            f"## User request:\n{user_message}"
        )

        # 3. Append to conversation history
        self.history.append({"role": "user", "content": augmented_user_msg})

        # 4. Call CodeLlama via Ollama (streaming)
        stream = self.llm.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *self.history,
            ],
            stream=True,
        )

        # 5. Stream output + collect full response
        full_response = ""
        print("\n\033[92mAgent:\033[0m ", end="", flush=True)
        for chunk in stream:
            delta = chunk["message"]["content"]
            print(delta, end="", flush=True)
            full_response += delta
        print()   # newline after streaming ends

        # 6. Save assistant turn to history
        self.history.append({"role": "assistant", "content": full_response})

        return full_response

    def reset(self):
        """Clear conversation history (start a new project context)."""
        self.history = []
        print("\033[93m[Memory cleared — starting fresh conversation]\033[0m")

    # ── CLI Loop ──────────────────────────────────────────────────────────────

    def run_cli(self):
        banner = textwrap.dedent("""
        ╔══════════════════════════════════════════════════════════╗
        ║        FullStack Agent — FastAPI + Next.js               ║
        ║  Powered by CodeLlama + ChromaDB RAG (Ollama embeddings) ║
        ╠══════════════════════════════════════════════════════════╣
        ║  Commands:                                               ║
        ║    /reset   — clear conversation memory                  ║
        ║    /stats   — show knowledge base stats                  ║
        ║    /exit    — quit                                        ║
        ╚══════════════════════════════════════════════════════════╝
        """)
        print(banner)

        while True:
            try:
                user_input = input("\n\033[96mYou:\033[0m ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nBye!")
                sys.exit(0)

            if not user_input:
                continue

            # ── Built-in commands ──────────────────────────────────────────
            if user_input.lower() == "/exit":
                print("Bye!")
                sys.exit(0)

            elif user_input.lower() == "/reset":
                self.reset()
                continue

            elif user_input.lower() == "/stats":
                stats = self.rag.stats()
                print(f"\033[93mKnowledge base stats:\033[0m {stats}")
                continue

            elif user_input.lower().startswith("/help"):
                print("Ask anything about FastAPI, Next.js, SQLAlchemy, or JWT auth!")
                continue

            # ── Normal chat ───────────────────────────────────────────────
            self.chat(user_input)