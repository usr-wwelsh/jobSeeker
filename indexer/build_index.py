"""
Build (or incrementally update) the ChromaDB portfolio_code collection.

Full run (default):
    python -m indexer.build_index

Incremental upsert only (skips collection wipe):
    python -m indexer.build_index --incremental
"""
import argparse
import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

from indexer.clone_repos import clone_all
from indexer.fetch_repos import fetch_repos

load_dotenv()

CHROMA_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma_data"
REPOS_DIR = Path(__file__).resolve().parent.parent / "data" / "repos"

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".cpp", ".zig", ".md",
    ".kt", ".rs", ".go", ".java", ".c", ".h",
}

EXTENSION_TO_LANGUAGE = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".cpp": "cpp", ".c": "c", ".h": "c",
    ".zig": "zig", ".md": "markdown", ".kt": "kotlin",
    ".rs": "rust", ".go": "go", ".java": "java",
}


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def iter_repo_files(repo_path: Path):
    for root, dirs, files in os.walk(repo_path):
        # Skip .git internals
        dirs[:] = [d for d in dirs if d != ".git"]
        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext in ALLOWED_EXTENSIONS:
                yield Path(root) / fname


def index_repos(incremental: bool = False):
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="intfloat/e5-small-v2"
    )

    if not incremental:
        print("Wiping existing collection...")
        try:
            client.delete_collection("portfolio_code")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name="portfolio_code",
        embedding_function=emb_fn,
    )

    # Build a map of repo name → default_branch for URL construction
    github_user = os.environ.get("GITHUB_USERNAME", "").strip()
    branch_map: dict[str, str] = {}
    try:
        repo_list = fetch_repos()
        branch_map = {r["name"]: r["default_branch"] for r in repo_list}
    except Exception as e:
        print(f"WARNING: could not fetch repo metadata from GitHub API: {e}")

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    total_chunks = 0

    for repo_path in sorted(REPOS_DIR.iterdir()):
        if not repo_path.is_dir():
            continue
        repo_name = repo_path.name
        branch = branch_map.get(repo_name, "main")
        base_url = f"https://github.com/{github_user}/{repo_name}/blob/{branch}"

        for file_path in iter_repo_files(repo_path):
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                print(f"Skipping {file_path}: {e}")
                continue

            rel_path = file_path.relative_to(repo_path)
            ext = file_path.suffix.lower()
            language = EXTENSION_TO_LANGUAGE.get(ext, "unknown")
            full_url = f"{base_url}/{rel_path}"
            chunks = chunk_text(content)

            for i, chunk in enumerate(chunks):
                chunk_id = f"{repo_name}-{rel_path}-chunk{i}"
                documents.append(chunk)
                metadatas.append(
                    {
                        "repo": repo_name,
                        "file": str(rel_path),
                        "full_url": full_url,
                        "language": language,
                        "content_preview": chunk[:500],
                    }
                )
                ids.append(chunk_id)
                total_chunks += 1

                # Upsert in batches of 500 to avoid memory spikes
                if len(documents) >= 500:
                    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                    documents, metadatas, ids = [], [], []

    if documents:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    print(f"Done. Indexed {total_chunks} chunks from {REPOS_DIR}.")
    return total_chunks


def main():
    parser = argparse.ArgumentParser(description="Build ChromaDB portfolio index")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Upsert only — do not wipe the collection first",
    )
    parser.add_argument(
        "--skip-clone",
        action="store_true",
        help="Skip cloning/pulling repos (use existing data/repos/)",
    )
    args = parser.parse_args()

    if not args.skip_clone:
        print("=== Step 1: Clone / pull repos ===")
        clone_all()

    print("\n=== Step 2: Build ChromaDB index ===")
    index_repos(incremental=args.incremental)


if __name__ == "__main__":
    main()
