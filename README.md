# FullStack Agent 🤖

> **A fully local CLI coding agent for FastAPI + Next.js projects — powered by CodeLlama and dual RAG (ChromaDB + Ollama embeddings).**
> No API keys. No internet. Runs entirely on your machine.

---

## Project Status

> 🟡 **Active Development — v0.2.0**

| Area | Status |
|---|---|
| Knowledge base RAG (FastAPI, Next.js, SQLAlchemy, JWT) | ✅ Complete |
| CodeLlama code generation with streaming | ✅ Complete |
| Multi-turn conversation memory | ✅ Complete |
| Project directory ingestion | ✅ Complete |
| Smart file chunker (Python, TS, Markdown) | ✅ Complete |
| Per-project ChromaDB collections | ✅ Complete |
| Dual retrieval (knowledge base + project code) | ✅ Complete |
| Standalone project ingestion CLI | ✅ Complete |
| Web UI | 🔲 Not planned (CLI by design) |
| Tests | 🔲 Planned |
| Support for more LLMs (Gemma, Mistral) | 🔲 Planned |

---

## How It Works

```
You (CLI)
    │
    ▼
 Query
    │
    ├──▶ Knowledge Base RAG          ──▶ FastAPI / Next.js / SQLAlchemy / Auth patterns
    │    (ChromaDB + nomic-embed-text)
    │
    └──▶ Project Code RAG            ──▶ Your actual project files (chunked + embedded)
         (per-project ChromaDB collection)
    │
    ▼
 Merged context injected into prompt
    │
    ▼
 CodeLlama (via Ollama) ──▶ Streamed response
```

**Why dual RAG?**
- The **knowledge base** provides curated best-practice patterns for FastAPI and Next.js
- The **project store** gives the LLM your actual code — so it matches your naming conventions, understands your existing models, and avoids rewriting what's already there
- Together they produce code that fits your project, not generic boilerplate

---

## Project Structure

```
fullstack-agent/
├── main.py                        # Entry point — starts the CLI agent
├── ingest_project.py              # Standalone CLI for project ingestion
├── add_knowledge.py               # Tool to add custom snippets to the knowledge base
├── requirements.txt
│
├── agent/
│   ├── agent.py                   # FullStackAgent — dual retrieval + CLI loop
│   └── rag_engine.py              # Knowledge base RAG (ChromaDB + Ollama)
│
├── ingestion/
│   ├── chunker.py                 # Directory scanner + smart file chunker
│   └── project_store.py          # Per-project ChromaDB collections + registry
│
├── knowledge_base/
│   ├── fastapi_patterns.py        # FastAPI boilerplate & patterns
│   ├── nextjs_patterns.py         # Next.js 14 App Router patterns
│   └── db_auth_patterns.py        # SQLAlchemy, Alembic, JWT auth, NextAuth
│
└── .chroma/                       # Auto-created — persistent vector store
```

---

## Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Pull required Ollama models
```bash
# Embedding model (used for both knowledge base and project RAG)
ollama pull nomic-embed-text

# LLM for code generation
ollama pull codellama
```

### 3. Start the agent
```bash
python main.py
```

The first run auto-indexes all knowledge base snippets into ChromaDB. Subsequent runs skip already-indexed snippets.

---

## Usage

### Basic — knowledge base only
```bash
python main.py
```

```
You: Create a FastAPI endpoint for user registration with email + password
You: How do I set up SQLAlchemy async session with PostgreSQL?
You: Generate a Next.js login page that calls my FastAPI /auth/login endpoint
You: I need JWT refresh token support in FastAPI
```

### With your project loaded
```bash
# Step 1 — ingest your project (one-time, persists between runs)
python ingest_project.py ingest ./my-fastapi-app --name backend

# Step 2 — start agent with project pre-loaded
python main.py --load backend
```

Now the agent understands your existing code before answering:
```
You: How does auth work in my project?
You: Add rate limiting to my existing user endpoints
You: Generate a schema that matches my User model
```

### Ingest + load in one command
```bash
python main.py --ingest ./my-fastapi-app --name backend --load backend
```

### Single-shot mode (non-interactive / scripting)
```bash
python main.py --query "Create a FastAPI endpoint for file upload"
```

### Force re-index knowledge base
```bash
python main.py --reindex
```

---

## CLI Commands (inside the chat)

| Command | Action |
|---|---|
| `/ingest <path> [name]` | Ingest a project directory |
| `/load <name>` | Load a project for retrieval |
| `/unload` | Unload current project (knowledge base only) |
| `/projects` | List all ingested projects |
| `/remove <name>` | Delete a project from the store |
| `/reset` | Clear conversation memory |
| `/stats` | Show knowledge base + project stats |
| `/exit` | Quit |

---

## Project Ingestion CLI

Manage projects without starting the full agent:

```bash
# Preview what will be chunked (no indexing)
python ingest_project.py inspect ./my-project

# Ingest a project
python ingest_project.py ingest ./my-fastapi-app --name backend
python ingest_project.py ingest ./my-nextjs-app  --name frontend

# List all ingested projects
python ingest_project.py list

# Search a project's code directly
python ingest_project.py search backend "how is the DB session handled"

# Remove a project
python ingest_project.py remove backend
```

---

## How Files Are Chunked

| File type | Chunking strategy |
|---|---|
| `.py` | Split on `class` / `def` / `async def` boundaries |
| `.ts` / `.tsx` | Split on `export function` / component boundaries |
| `.md` | Split on heading (`##`) boundaries |
| `.json`, `.yaml`, `.sql`, etc. | Fixed 60-line window with 10-line overlap |

Files and directories automatically skipped: `node_modules`, `.next`, `__pycache__`, `.git`, `venv`, `dist`, `build`, `alembic/versions`.

---

## Extending the Knowledge Base

### Add a snippet interactively
```bash
python add_knowledge.py
```

### Ingest a file as a snippet
```bash
python add_knowledge.py --file app/api/v1/endpoints/my_endpoint.py
```

### List / delete snippets
```bash
python add_knowledge.py --list
python add_knowledge.py --delete my_snippet_id
```

### Add snippets in bulk (code)
```python
# In any knowledge_base/*.py file, append to the list:
{
    "id": "my_unique_id",
    "category": "endpoints",
    "title": "My custom middleware",
    "content": "# your code here",
}
```
Then run `python main.py --reindex`.

---

## Models

| Role | Model | Pull command |
|---|---|---|
| Embeddings | nomic-embed-text | `ollama pull nomic-embed-text` |
| Code LLM | codellama | `ollama pull codellama` |

To switch the LLM, change `LLM_MODEL` in `agent/agent.py`.
Good alternatives: `deepseek-coder`, `qwen2.5-coder`, `llama3.1`.

---

## Tips

- **Be specific.** "Create a FastAPI endpoint for paginated item listing with JWT auth" retrieves better patterns than "make an endpoint".
- **Ingest both sides.** Ingest your FastAPI backend AND your Next.js frontend as separate named projects for the best cross-stack answers.
- **Use `/reset`** when switching to a very different feature — old conversation context can confuse the LLM.
- **Use `/unload`** when asking general questions not related to your project.
- **The more you ingest**, the smarter the retrieval. Add new services as you create them.

---

## .gitignore

Add these to your `.gitignore` — the vector store is auto-regenerated on first run:

```
.chroma/
__pycache__/
*.pyc
.env
```