"""
Query ChromaDB to find portfolio code chunks relevant to a job description.
"""
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma_data"


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    return client.get_collection(name="portfolio_code", embedding_function=emb_fn)


def find_relevant_chunks(job_description: str, n_results: int = 6) -> list[dict]:
    """
    Returns up to n_results chunks most relevant to the job description.
    Each item: {repo, file, full_url, content, distance}
    """
    collection = _get_collection()
    results = collection.query(
        query_texts=[job_description],
        n_results=n_results,
    )

    chunks = []
    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    for chunk_id, doc, meta, dist in zip(ids, docs, metas, distances):
        chunks.append(
            {
                "repo": meta.get("repo", ""),
                "file": meta.get("file", ""),
                "full_url": meta.get("full_url", ""),
                "content": doc,
                "distance": dist,
            }
        )

    return chunks
