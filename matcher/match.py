"""
Query ChromaDB to find portfolio code chunks relevant to a job description.

Diversity strategy: fetch a large candidate pool, then keep only the single
best-scoring chunk per repo so the prompt draws from multiple projects.
"""
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma_data"

# How many raw candidates to pull before diversity filtering.
# Needs to be large enough to surface good chunks across many repos.
_CANDIDATE_MULTIPLIER = 5


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="intfloat/e5-small-v2"
    )
    return client.get_collection(name="portfolio_code", embedding_function=emb_fn)


def find_relevant_chunks(job_description: str, n_results: int = 6) -> list[dict]:
    """
    Returns up to n_results chunks most relevant to the job description,
    with at most one chunk per repo to ensure portfolio diversity.
    Each item: {repo, file, full_url, content, distance}
    """
    collection = _get_collection()

    # Pull a larger candidate set so diversity filtering has room to work
    candidate_count = min(n_results * _CANDIDATE_MULTIPLIER, collection.count())
    candidate_count = max(candidate_count, n_results)  # never ask for fewer than needed

    results = collection.query(
        query_texts=[job_description],
        n_results=candidate_count,
    )

    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    # Keep only the best (lowest distance) chunk per repo, in ranked order
    seen_repos: set[str] = set()
    diverse_chunks: list[dict] = []

    for chunk_id, doc, meta, dist in zip(ids, docs, metas, distances):
        repo = meta.get("repo", "")
        if repo in seen_repos:
            continue
        seen_repos.add(repo)
        diverse_chunks.append(
            {
                "repo": repo,
                "file": meta.get("file", ""),
                "full_url": meta.get("full_url", ""),
                "content": doc,
                "distance": dist,
            }
        )
        if len(diverse_chunks) == n_results:
            break

    return diverse_chunks
