"""Retrieval over the customer-master documents in data/customer_master/.

Written against the versions actually installed in this project:

    chromadb                   1.5.9
    langchain-text-splitters   1.1.2
    langchain-community        0.4.2  (deliberately unused - see below)

We drive the ``chromadb`` client directly rather than going through
``langchain_community.vectorstores.Chroma``. That wrapper is deprecated, defers
to the separate ``langchain-chroma`` package (not installed here), and expects a
LangChain ``Embeddings`` object -- which would mean either an embeddings API key
or ``sentence-transformers``. Chroma's own default embedding function is a local
ONNX all-MiniLM-L6-v2 model, so the demo embeds with no API key at all.

Note for the container build: that model is ~79 MB and is downloaded on first
use into ~/.cache/chroma. Build the index at image build time, not at container
start, or the first request after a cold start pays for the download.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from app.config import CHROMA_PATH, CUSTOMER_MASTER_DIR

logger = logging.getLogger(__name__)

COLLECTION_NAME = "customer_master"

# Documents are short (~1 KB), so small chunks keep each retrieved passage
# specific to one fact rather than returning a whole record every time.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# Module-level flag, as specified. Note that retrieve() re-reads the environment
# on every call instead of trusting this constant: the Streamlit sidebar toggles
# grounding between runs inside one process, so a value frozen at import time
# would make the toggle appear broken.
GROUNDING_ENABLED = _env_flag("GROUNDING_ENABLED")

# Lazily built singletons. Nothing heavy happens at import: with grounding
# switched off the ONNX model is never loaded at all.
#
# Initialisation is lock-guarded because the eval runner calls retrieve() from
# several threads at once. chromadb's PersistentClient is not safe to construct
# concurrently -- two threads racing it raise KeyError from its internal system
# cache, and since retrieve() degrades to [] on error, that failure would
# silently turn a grounded run into an ungrounded one.
_client = None
_embedding_fn = None
_init_lock = threading.Lock()
_index_lock = threading.Lock()


def _get_embedding_fn():
    global _embedding_fn
    if _embedding_fn is None:
        with _init_lock:
            if _embedding_fn is None:
                from chromadb.utils import embedding_functions

                _embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    return _embedding_fn


def _get_client():
    global _client
    if _client is None:
        with _init_lock:
            if _client is None:
                import chromadb

                # CHROMA_PATH is derived from the project root rather than the
                # current working directory, so the UI, the eval runner and the
                # container all agree on where the store lives.
                CHROMA_PATH.mkdir(parents=True, exist_ok=True)
                _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _client


def _load_documents() -> list[tuple[str, str]]:
    """Return (payee_id, text) for every .md file, in a stable order."""
    files = sorted(CUSTOMER_MASTER_DIR.glob("*.md"))
    if not files:
        raise FileNotFoundError(
            f"No .md documents found in {CUSTOMER_MASTER_DIR}. "
            "The customer-master corpus is required for grounding."
        )
    return [(path.stem, path.read_text(encoding="utf-8")) for path in files]


def _chunk(payee_id: str, text: str) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def build_index(force: bool = False):
    """Build or load the Chroma collection over data/customer_master/.

    Idempotent: if the persisted store already holds documents, it is loaded and
    returned unchanged. Pass ``force=True`` to drop and rebuild it after editing
    the corpus.

    Returns:
        The Chroma collection.
    """
    with _index_lock:
        return _build_index_locked(force)


def _build_index_locked(force: bool = False):
    client = _get_client()

    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:  # collection may not exist yet
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_get_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )

    if collection.count() > 0 and not force:
        logger.debug("Chroma collection already populated (%d chunks)", collection.count())
        return collection

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for payee_id, text in _load_documents():
        for i, chunk in enumerate(_chunk(payee_id, text)):
            # Deterministic ids make re-indexing an upsert rather than a
            # duplication, so a repeated build cannot inflate the collection.
            ids.append(f"{payee_id}::{i}")
            documents.append(chunk)
            metadatas.append({"payee_id": payee_id, "source_file": f"{payee_id}.md"})

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    logger.info("Indexed %d chunks from %s", len(ids), CUSTOMER_MASTER_DIR)
    return collection


def retrieve(query: str, k: int = 4) -> list[dict]:
    """Retrieve the k most relevant customer-master passages for a query.

    Returns a list of dicts with "content", "source_file" and "payee_id".

    When grounding is disabled this returns an empty list and reads nothing --
    there is deliberately no fallback to the payee JSON or any other source, so
    the demo can show what the agent does with no grounding at all.
    """
    # Re-read per call rather than using the import-time constant, so the UI
    # toggle takes effect on the next run without restarting the process.
    if not _env_flag("GROUNDING_ENABLED"):
        logger.info("Grounding disabled; returning no context.")
        return []

    try:
        collection = build_index()  # cheap once populated; safety net if missing
        result = collection.query(query_texts=[query], n_results=k)
    except Exception:
        # A broken retrieval backend must not take the demo down: the run
        # continues ungrounded, which the graph reports honestly as
        # grounded=False.
        logger.warning("Retrieval failed; continuing ungrounded.", exc_info=True)
        return []

    # chromadb returns one nested list per query text; we only ever send one.
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    hits: list[dict] = []
    for i, content in enumerate(documents):
        meta = metadatas[i] if i < len(metadatas) else {}
        hit = {
            "content": content,
            "source_file": meta.get("source_file"),
            "payee_id": meta.get("payee_id"),
        }
        if i < len(distances):
            hit["distance"] = distances[i]
        hits.append(hit)
    return hits


if __name__ == "__main__":  # pragma: no cover - convenience for the demo build
    import sys

    build_index(force="--force" in sys.argv)
    print(f"Index ready at {CHROMA_PATH}")
