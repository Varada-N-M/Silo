"""
chunker.py
──────────
Scans a project directory, reads supported files, and splits them
into semantically meaningful chunks ready for embedding.

Chunking strategy:
  - Python (.py)      → split on class/def boundaries
  - TypeScript (.ts/.tsx) → split on function/component boundaries
  - Markdown (.md)    → split on heading boundaries
  - Everything else   → fixed-size sliding window with overlap
"""

import os
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Iterator
from dataclasses import dataclass, field


# ── Config ────────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {
    # Backend
    ".py",
    # Frontend
    ".ts", ".tsx", ".js", ".jsx",
    # Config / docs
    ".md", ".env.example", ".json", ".yaml", ".yml", ".toml",
    # SQL
    ".sql",
}

# Directories to always skip
IGNORE_DIRS = {
    "node_modules", ".next", "__pycache__", ".git", ".venv", "venv",
    "env", "dist", "build", ".mypy_cache", ".pytest_cache", "chroma_db",
    ".chroma", "alembic/versions",
}

# Files to always skip
IGNORE_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    ".DS_Store", "*.pyc",
}

CHUNK_SIZE    = 60   # lines per chunk (for fallback splitter)
CHUNK_OVERLAP = 10   # lines of overlap between chunks


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    """A single chunk of code/text from a project file."""
    chunk_id:   str          # stable hash — used as ChromaDB document ID
    file_path:  str          # relative path from project root
    file_type:  str          # extension without dot (e.g. "py", "tsx")
    start_line: int
    end_line:   int
    content:    str
    metadata:   Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = self._make_id()

    def _make_id(self) -> str:
        raw = f"{self.file_path}:{self.start_line}:{self.end_line}"
        return hashlib.md5(raw.encode()).hexdigest()


# ── Splitters ─────────────────────────────────────────────────────────────────

def _split_python(lines: List[str], rel_path: str) -> List[Chunk]:
    """Split Python files on top-level class/def boundaries."""
    chunks = []
    boundary_re = re.compile(r'^(class |def |async def )')

    current_start = 0
    current_lines: List[str] = []

    def flush(start: int, end: int, content_lines: List[str]):
        content = "".join(content_lines).strip()
        if content:
            chunks.append(Chunk(
                chunk_id=f"{rel_path}:{start}",
                file_path=rel_path,
                file_type="py",
                start_line=start + 1,
                end_line=end,
                content=content,
            ))

    for i, line in enumerate(lines):
        if boundary_re.match(line) and current_lines:
            flush(current_start, i, current_lines)
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

    flush(current_start, len(lines), current_lines)
    return chunks


def _split_typescript(lines: List[str], rel_path: str) -> List[Chunk]:
    """Split TS/TSX files on export function/component/class boundaries."""
    chunks = []
    boundary_re = re.compile(
        r'^(export (default )?(function|const|class|async function)|'
        r'const \w+ = \(|'
        r'function \w+)'
    )

    current_start = 0
    current_lines: List[str] = []

    def flush(start: int, end: int, content_lines: List[str]):
        content = "".join(content_lines).strip()
        if content:
            ext = Path(rel_path).suffix.lstrip(".")
            chunks.append(Chunk(
                chunk_id=f"{rel_path}:{start}",
                file_path=rel_path,
                file_type=ext,
                start_line=start + 1,
                end_line=end,
                content=content,
            ))

    for i, line in enumerate(lines):
        if boundary_re.match(line) and current_lines:
            flush(current_start, i, current_lines)
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

    flush(current_start, len(lines), current_lines)
    return chunks


def _split_markdown(lines: List[str], rel_path: str) -> List[Chunk]:
    """Split Markdown on heading (##) boundaries."""
    chunks = []
    heading_re = re.compile(r'^#{1,3} ')

    current_start = 0
    current_lines: List[str] = []

    def flush(start: int, end: int, content_lines: List[str]):
        content = "".join(content_lines).strip()
        if content:
            chunks.append(Chunk(
                chunk_id=f"{rel_path}:{start}",
                file_path=rel_path,
                file_type="md",
                start_line=start + 1,
                end_line=end,
                content=content,
            ))

    for i, line in enumerate(lines):
        if heading_re.match(line) and current_lines:
            flush(current_start, i, current_lines)
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

    flush(current_start, len(lines), current_lines)
    return chunks


def _split_fixed_window(lines: List[str], rel_path: str, ext: str) -> List[Chunk]:
    """Fallback: fixed-size window with overlap for any file type."""
    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP

    for start in range(0, len(lines), step):
        end = min(start + CHUNK_SIZE, len(lines))
        content = "".join(lines[start:end]).strip()
        if content:
            chunks.append(Chunk(
                chunk_id=f"{rel_path}:{start}",
                file_path=rel_path,
                file_type=ext.lstrip("."),
                start_line=start + 1,
                end_line=end,
                content=content,
            ))
        if end == len(lines):
            break

    return chunks


# ── Main chunker ──────────────────────────────────────────────────────────────

def chunk_file(file_path: Path, project_root: Path) -> List[Chunk]:
    """Read a single file and return its chunks."""
    rel_path = str(file_path.relative_to(project_root))
    ext = file_path.suffix.lower()

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    if not text.strip():
        return []

    lines = text.splitlines(keepends=True)

    if ext == ".py":
        return _split_python(lines, rel_path)
    elif ext in {".ts", ".tsx", ".js", ".jsx"}:
        return _split_typescript(lines, rel_path)
    elif ext == ".md":
        return _split_markdown(lines, rel_path)
    else:
        return _split_fixed_window(lines, rel_path, ext)


def scan_project(project_root: str | Path) -> Iterator[Chunk]:
    """
    Walk a project directory and yield Chunk objects for every supported file.

    Args:
        project_root: Absolute or relative path to the project root

    Yields:
        Chunk objects ready for embedding
    """
    root = Path(project_root).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Project root not found: {root}")

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in IGNORE_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            # Skip ignored filenames
            if filename in IGNORE_FILES:
                continue

            file_path = Path(dirpath) / filename
            ext = file_path.suffix.lower()

            if ext not in SUPPORTED_EXTENSIONS:
                continue

            chunks = chunk_file(file_path, root)
            for chunk in chunks:
                yield chunk


def summarise_scan(project_root: str | Path) -> Dict:
    """Return a summary of what would be scanned without indexing."""
    root = Path(project_root).resolve()
    file_counts: Dict[str, int] = {}
    chunk_count = 0

    for chunk in scan_project(root):
        file_counts[chunk.file_type] = file_counts.get(chunk.file_type, 0) + 1
        chunk_count += 1

    return {
        "project_root": str(root),
        "total_chunks": chunk_count,
        "by_type": file_counts,
    }