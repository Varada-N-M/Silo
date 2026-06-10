# FullStack Agent 🤖
**A local CLI agent that helps you build FastAPI + Next.js apps — powered by CodeLlama and RAG (ChromaDB + Ollama embeddings).**

No API keys. No internet. Runs entirely on your machine.

---

## How It Works

```
You (CLI)  →  Agent  →  RAG retrieval (ChromaDB + nomic-embed-text)
                   ↓
          Relevant code patterns injected into prompt
                   ↓
          CodeLlama generates accurate, idiomatic code
```

**Why RAG?** Instead of relying on the LLM's general training, the agent first retrieves the most relevant FastAPI/Next.js patterns from your curated knowledge base and injects them into the prompt. This gives you:
- Consistent, project-specific code style
- Less hallucination
- Knowledge that grows with your projects

---

## Project Structure

```
fullstack-agent/
├── main.py                        # Entry point — starts the CLI agent
├── add_knowledge.py               # Tool to add custom snippets to RAG
├── requirements.txt
├── agent/
│   ├── agent.py                   # FullStackAgent class + CLI loop
│   └── rag_engine.py              # ChromaDB + Ollama embeddings
├── knowledge_base/
│   ├── fastapi_patterns.py        # FastAPI boilerplate & patterns
│   ├── nextjs_patterns.py         # Next.js App Router patterns
│   └── db_auth_patterns.py        # SQLAlchemy, Alembic, JWT auth
└── chroma_db/                     # Auto-created — persistent vector store
```

---

## Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Pull required Ollama models
```bash
# Embedding model (for RAG)
ollama pull nomic-embed-text

# LLM for code generation
ollama pull codellama
```

### 3. Start the agent
```bash
python main.py
```

That's it! The first run indexes all knowledge base snippets into ChromaDB automatically.

---

## Usage

### Interactive CLI
```bash
python main.py
```

**Example prompts:**
```
You: Create a FastAPI endpoint for user registration with email + password
You: How do I set up SQLAlchemy async session with PostgreSQL?
You: Generate a Next.js login page that calls my FastAPI /auth/login endpoint
You: I need JWT refresh token support in FastAPI
You: Create a generic CRUD component in Next.js using React Query
```

### Single-shot mode (non-interactive)
```bash
python main.py --query "Create a FastAPI endpoint for file upload"
```

### Force re-index knowledge base
```bash
python main.py --reindex
```

### CLI Commands (inside the chat)
| Command   | Action                              |
|-----------|-------------------------------------|
| `/reset`  | Clear conversation memory           |
| `/stats`  | Show knowledge base stats           |
| `/exit`   | Quit                                |

---

## Extending the Knowledge Base

### Add a snippet interactively
```bash
python add_knowledge.py
```

### Ingest an entire file
```bash
python add_knowledge.py --file app/api/v1/endpoints/my_custom_endpoint.py
```

### List all indexed snippets
```bash
python add_knowledge.py --list
```

### Delete a snippet
```bash
python add_knowledge.py --delete my_snippet_id
```

### Add snippets in code (for bulk imports)
```python
# In any knowledge_base/*.py file, add to the list:
{
    "id": "my_unique_id",
    "category": "endpoints",       # see CATEGORIES in add_knowledge.py
    "title": "My custom pattern",
    "content": """
# your code here
""",
}
```

Then run `python main.py --reindex` to pick up the new snippets.

---

## Reusing Across Projects

The ChromaDB vector store (`./chroma_db/`) persists between runs. To reuse the agent across multiple projects:

**Option A — Copy the agent folder** into each project and add project-specific snippets via `add_knowledge.py --file`.

**Option B — Point all projects to one shared chroma_db** by changing `persist_dir` in `rag_engine.py`:
```python
rag = RAGEngine(persist_dir="/home/yourname/.fullstack_agent/chroma_db")
```

---

## Models

| Role       | Model              | Pull command                   |
|------------|--------------------|--------------------------------|
| Embeddings | nomic-embed-text   | `ollama pull nomic-embed-text` |
| Code LLM   | codellama          | `ollama pull codellama`        |

To switch to a different LLM, change `LLM_MODEL` in `agent/agent.py`.
Good alternatives: `deepseek-coder`, `qwen2.5-coder`, `llama3.1`.

---

## Tips

- **Be specific in prompts.** "Create a FastAPI endpoint for paginated item listing with JWT auth" retrieves better patterns than "make an endpoint".
- **Use `/reset`** when switching to a very different feature — it clears the conversation so old context doesn't confuse the LLM.
- **Add your own project's code** via `add_knowledge.py --file` to make the agent aware of your specific conventions.
- **The more snippets**, the better the retrieval. Add patterns as you build!