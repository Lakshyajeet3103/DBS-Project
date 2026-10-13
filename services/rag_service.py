"""RAG retrieval and generation service with dual-layer ACL (Chroma filter pushdown + SQL registry verification).

Implements Task 3.2 & Task 3.3 with defense-in-depth SQL registry enforcement:
1. Pre-retrieval metadata filter pushdown (`build_acl_filter`) derived strictly from the server session role.
2. Vector similarity search against ChromaDB (`retrieve_authorized_chunks`) with unified collection resolution.
3. Post-retrieval SQL registry verification (`verify_and_filter_chunks`, `is_chunk_authorized`) ensuring every
   retrieved chunk resolves to a currently existing and role-authorized `Document` record in the SQL database
   before prompt construction and source citation.
4. Grounded LLM prompt engineering (`RAG_PROMPT_TEMPLATE`, `build_prompt`) with strict refusal on missing context.
5. Deduplicated, registry-verified source citations (`extract_unique_sources`) and end-to-end RAG (`query_rag`).
"""
import copy
import os
import sqlite3
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from core.access import allowed_levels, can_access_level
from database.connection import SessionLocal
from database.models import Document

DEFAULT_CHROMA_DIR = "./chroma"
DEFAULT_COLLECTION_NAME = "folio_knowledge_base"
LEGACY_COLLECTION_NAME = "langchain"
DEFAULT_TOP_K = 3
DEFAULT_LLM_MODEL = "gemini-3.5-flash-lite"

NO_CONTEXT_REPLY = "I cannot find this in your documents."

RAG_PROMPT_TEMPLATE = (
    "You are the Folio knowledge assistant. Answer the user's question using ONLY the provided context from their authorized documents.\n"
    "If the answer cannot be found in the context, do not speculate or use outside knowledge. Say: \"I cannot find this in your documents.\"\n\n"
    "Context:\n"
    "{context}\n\n"
    "Question:\n"
    "{question}\n\n"
    "Answer:"
)


def build_acl_filter(user_role: str, document_id: Optional[str] = None) -> Dict[str, Any]:
    """Construct a Chroma `where` metadata filter for the given session role and optional document scope.

    Raises PermissionError if `user_role` is not a recognized role ('junior' or 'senior').
    """
    allowed_levels(user_role)

    if user_role == "junior":
        level_filter: Dict[str, Any] = {"level": "junior"}
    elif user_role == "senior":
        level_filter = {"level": {"$in": ["junior", "senior"]}}
    else:
        raise PermissionError("Invalid user role")

    if document_id:
        return {"$and": [level_filter, {"document_id": document_id}]}
    return level_filter


def _extract_metadata(chunk: Any) -> Dict[str, Any]:
    """Safely extract metadata dictionary from a LangChain Document or dict-like chunk."""
    if hasattr(chunk, "metadata") and isinstance(chunk.metadata, dict):
        return chunk.metadata
    if isinstance(chunk, dict) and isinstance(chunk.get("metadata"), dict):
        return chunk["metadata"]
    return {}


def _load_authorized_registry_map(
    user_role: Optional[str] = None,
    document_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Dict[str, str]]:
    """Query the SQL `documents` registry and return a map of currently authorized documents by ID.

    If `user_role` is provided, only documents whose current SQL `level` is permitted for `user_role`
    are included. If `document_id` is provided, restricts the map to that single document ID.
    """
    levels = allowed_levels(user_role) if user_role is not None else ("junior", "senior")
    own_session = db is None
    session = SessionLocal() if own_session else db
    try:
        query = session.query(Document).filter(Document.level.in_(levels))
        if document_id is not None:
            query = query.filter(Document.id == document_id)
        docs = query.all()
        return {
            doc.id: {
                "id": doc.id,
                "title": doc.title,
                "level": doc.level,
            }
            for doc in docs
        }
    finally:
        if own_session:
            session.close()


def is_chunk_authorized(
    chunk: Any,
    user_role: str,
    document_id: Optional[str] = None,
    db: Optional[Session] = None,
    authorized_registry: Optional[Dict[str, Dict[str, str]]] = None,
) -> bool:
    """Dual-layer defense-in-depth check: verify both chunk metadata AND canonical SQL registry state.

    A chunk is authorized if and only if:
    1. `user_role` is a valid role ('junior' or 'senior').
    2. The chunk has a non-empty string `document_id` (and it matches `document_id` scope if provided).
    3. The chunk's vector metadata `level` is permitted for `user_role`.
    4. The `document_id` resolves to an existing row in the SQL `documents` table whose current
       SQL `level` is permitted for `user_role` (preventing mis-tagged Senior docs, reclassified docs
       with stale vector metadata, and nonexistent/deleted document IDs from reaching the LLM).
    """
    allowed_levels(user_role)

    metadata = _extract_metadata(chunk)
    raw_doc_id = metadata.get("document_id")
    if not isinstance(raw_doc_id, str) or not raw_doc_id.strip():
        return False
    doc_id = raw_doc_id.strip()

    if document_id is not None and doc_id != document_id:
        return False

    chunk_level = metadata.get("level")
    if not isinstance(chunk_level, str) or not can_access_level(user_role, chunk_level):
        return False

    registry = (
        authorized_registry
        if authorized_registry is not None
        else _load_authorized_registry_map(user_role=user_role, document_id=document_id, db=db)
    )
    reg_doc = registry.get(doc_id)
    if reg_doc is None:
        return False

    if not can_access_level(user_role, reg_doc["level"]):
        return False

    return True


def verify_and_filter_chunks(
    chunks: Sequence[Any],
    user_role: str,
    document_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> List[Any]:
    """Post-retrieval ACL and SQL registry verification gate.

    Ensures every chunk:
    - Has valid vector metadata permitted for `user_role`, AND
    - Resolves to a currently authorized document in the SQL `documents` registry.
    """
    allowed_levels(user_role)
    registry = _load_authorized_registry_map(user_role=user_role, document_id=document_id, db=db)

    return [
        chunk
        for chunk in chunks
        if is_chunk_authorized(
            chunk,
            user_role=user_role,
            document_id=document_id,
            authorized_registry=registry,
        )
    ]


def resolve_collection_name(
    persist_directory: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> str:
    """Resolve the agreed ChromaDB collection name across ingestion and retrieval.

    1. Uses explicit `collection_name` argument or `CHROMA_COLLECTION_NAME` env var if set.
    2. Otherwise checks `chroma.sqlite3` in `persist_directory`:
       - Prefers a collection (`folio_knowledge_base` or `langchain`) that contains ACL-tagged
         embeddings (`level` and `document_id` metadata).
       - Otherwise prefers `folio_knowledge_base` if present and non-empty, falling back to `langchain`.
    3. Defaults to `folio_knowledge_base`.
    """
    if isinstance(collection_name, str) and collection_name.strip():
        return collection_name.strip()

    env_collection = os.getenv("CHROMA_COLLECTION_NAME")
    if isinstance(env_collection, str) and env_collection.strip():
        return env_collection.strip()

    directory = persist_directory or os.getenv("CHROMA_PERSIST_DIR", DEFAULT_CHROMA_DIR)
    sqlite_path = os.path.join(directory, "chroma.sqlite3")
    if os.path.isfile(sqlite_path):
        try:
            conn = sqlite3.connect(sqlite_path)
            try:
                tagged_rows = conn.execute(
                    """
                    SELECT c.name, COUNT(DISTINCT e.id)
                    FROM collections c
                    JOIN segments s ON s.collection = c.id
                    JOIN embeddings e ON e.segment_id = s.id
                    JOIN embedding_metadata em ON em.id = e.id
                    WHERE em.key = 'level'
                    GROUP BY c.id, c.name
                    """
                ).fetchall()
                tagged_counts = {name: int(cnt or 0) for name, cnt in tagged_rows if isinstance(name, str)}
                if tagged_counts.get(DEFAULT_COLLECTION_NAME, 0) > 0:
                    return DEFAULT_COLLECTION_NAME
                if tagged_counts.get(LEGACY_COLLECTION_NAME, 0) > 0:
                    return LEGACY_COLLECTION_NAME

                rows = conn.execute(
                    """
                    SELECT c.name, COUNT(e.id)
                    FROM collections c
                    LEFT JOIN segments s ON s.collection = c.id
                    LEFT JOIN embeddings e ON e.segment_id = s.id
                    GROUP BY c.id, c.name
                    """
                ).fetchall()
                counts = {name: int(cnt or 0) for name, cnt in rows if isinstance(name, str)}
                if counts.get(DEFAULT_COLLECTION_NAME, 0) > 0:
                    return DEFAULT_COLLECTION_NAME
                if counts.get(LEGACY_COLLECTION_NAME, 0) > 0:
                    return LEGACY_COLLECTION_NAME
                if DEFAULT_COLLECTION_NAME in counts:
                    return DEFAULT_COLLECTION_NAME
                if LEGACY_COLLECTION_NAME in counts:
                    return LEGACY_COLLECTION_NAME
            finally:
                conn.close()
        except sqlite3.Error:
            pass

    return DEFAULT_COLLECTION_NAME


def _split_text_chunks(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
    """Split document text into overlapping character chunks (uses LangChain splitter when installed)."""
    clean = (text or "").strip()
    if not clean:
        return []
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        return splitter.split_text(clean)
    except ImportError:
        step = max(1, chunk_size - chunk_overlap)
        return [clean[i : i + chunk_size] for i in range(0, len(clean), step)]


def build_registry_chunks(
    db: Optional[Session] = None,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> Dict[str, List[Any]]:
    """Build metadata-tagged chunks (`texts`, `metadatas`, `ids`) from the canonical SQL `documents` table."""
    own_session = db is None
    session = SessionLocal() if own_session else db
    try:
        docs = session.query(Document).order_by(Document.id).all()
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        for doc in docs:
            pieces = _split_text_chunks(doc.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            for idx, piece in enumerate(pieces):
                texts.append(piece)
                metadatas.append(
                    {
                        "document_id": doc.id,
                        "title": doc.title,
                        "level": doc.level,
                        "category": doc.category,
                        "type": doc.type,
                        "year": str(doc.year),
                        "chunk_index": idx,
                    }
                )
                ids.append(f"{doc.id}_chunk_{idx}")
        return {"texts": texts, "metadatas": metadatas, "ids": ids}
    finally:
        if own_session:
            session.close()


def ingest_registry_documents(
    vector_db: Any = None,
    db: Optional[Session] = None,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> int:
    """Ingest all SQL registry documents with full ACL metadata into the agreed vector store collection."""
    payload = build_registry_chunks(db=db, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not payload["texts"]:
        return 0
    vdb = vector_db if vector_db is not None else get_vector_db()
    vdb.add_texts(
        texts=payload["texts"],
        metadatas=payload["metadatas"],
        ids=payload["ids"],
    )
    return len(payload["texts"])


def get_embedding_model():
    """Initialize the configured embedding model (Gemini by default, or local MiniLM)."""
    provider = os.getenv("EMBEDDING_PROVIDER", "gemini").strip().lower()
    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in the environment.")
        model_name = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
        return GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=api_key)
    if provider == "local":
        from langchain_community.embeddings import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider!r}")


def get_vector_db(
    persist_directory: Optional[str] = None,
    collection_name: Optional[str] = None,
    embedding_function: Any = None,
):
    """Return a Chroma vector store handle configured with the project's collection and embeddings."""
    from langchain_chroma import Chroma

    directory = persist_directory or os.getenv("CHROMA_PERSIST_DIR", DEFAULT_CHROMA_DIR)
    collection = resolve_collection_name(persist_directory=directory, collection_name=collection_name)
    embeddings = embedding_function or get_embedding_model()

    return Chroma(
        persist_directory=directory,
        embedding_function=embeddings,
        collection_name=collection,
    )


def retrieve_authorized_chunks(
    query: str,
    user_role: str,
    document_id: Optional[str] = None,
    k: int = DEFAULT_TOP_K,
    vector_db: Any = None,
    db: Optional[Session] = None,
) -> List[Any]:
    """Execute similarity search with pre-retrieval ACL filter pushdown and post-retrieval SQL registry verification."""
    acl_filter = build_acl_filter(user_role=user_role, document_id=document_id)
    vdb = vector_db if vector_db is not None else get_vector_db()

    raw_chunks = vdb.similarity_search(query=query, k=k, filter=acl_filter)
    return verify_and_filter_chunks(
        raw_chunks,
        user_role=user_role,
        document_id=document_id,
        db=db,
    )


def _extract_page_content(chunk: Any) -> str:
    """Safely extract text content from a LangChain Document or dict-like chunk."""
    if hasattr(chunk, "page_content") and isinstance(chunk.page_content, str):
        return chunk.page_content
    if isinstance(chunk, dict) and isinstance(chunk.get("page_content"), str):
        return chunk["page_content"]
    return str(chunk)


def format_context(
    chunks: Sequence[Any],
    user_role: Optional[str] = None,
    db: Optional[Session] = None,
) -> str:
    """Combine registry-verified chunk passages into a single context string for the LLM prompt."""
    registry = _load_authorized_registry_map(user_role=user_role, db=db)
    passages: List[str] = []
    for chunk in chunks:
        text = _extract_page_content(chunk).strip()
        if not text:
            continue
        metadata = _extract_metadata(chunk)
        raw_doc_id = metadata.get("document_id")
        if not isinstance(raw_doc_id, str) or not raw_doc_id.strip():
            continue
        reg_doc = registry.get(raw_doc_id.strip())
        if reg_doc is None:
            continue
        raw_title = metadata.get("title")
        title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else reg_doc["title"]
        passages.append(f"[{title}]\n{text}")
    return "\n\n---\n\n".join(passages)


def build_prompt(
    question: str,
    chunks: Sequence[Any],
    user_role: Optional[str] = None,
    db: Optional[Session] = None,
) -> str:
    """Populate the strict grounded RAG prompt template with SQL-registry-verified context and question."""
    context_text = format_context(chunks, user_role=user_role, db=db)
    return RAG_PROMPT_TEMPLATE.format(context=context_text, question=question.strip())


def extract_unique_sources(
    chunks: Sequence[Any],
    user_role: Optional[str] = None,
    db: Optional[Session] = None,
) -> List[Dict[str, str]]:
    """Extract deduplicated `[{'id': doc_id, 'title': title}]` citations verified against the SQL registry."""
    registry = _load_authorized_registry_map(user_role=user_role, db=db)
    seen_ids = set()
    sources: List[Dict[str, str]] = []
    for chunk in chunks:
        metadata = _extract_metadata(chunk)
        doc_id = metadata.get("document_id")
        if not isinstance(doc_id, str) or not doc_id.strip():
            continue
        doc_id = doc_id.strip()
        if doc_id in seen_ids:
            continue
        reg_doc = registry.get(doc_id)
        if reg_doc is None:
            continue
        seen_ids.add(doc_id)
        raw_title = metadata.get("title")
        title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else reg_doc["title"]
        sources.append({"id": reg_doc["id"], "title": title})
    return sources


def get_chat_model(model_name: Optional[str] = None):
    """Initialize the Gemini chat model via ChatGoogleGenerativeAI."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment.")
    resolved_model = model_name or os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
    return ChatGoogleGenerativeAI(
        model=resolved_model,
        api_key=api_key,
        temperature=0.0,
        timeout=20,
        max_retries=1,
    )


def _invoke_llm(llm: Any, prompt: str) -> str:
    """Invoke a LangChain chat model or callable and normalize its output to a string."""
    if hasattr(llm, "invoke"):
        response = llm.invoke(prompt)
    elif callable(llm):
        response = llm(prompt)
    else:
        raise TypeError("Provided `llm` object must implement `.invoke(prompt)` or be callable.")

    if hasattr(response, "content"):
        content = response.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            ]
            return "".join(parts).strip()
    if isinstance(response, str):
        return response.strip()
    return str(response).strip()


def _is_refusal_reply(reply_text: str) -> bool:
    """Return True if the LLM response is the canonical refusal indicating no matching context."""
    normalized = reply_text.strip().lower().rstrip(".")
    target = NO_CONTEXT_REPLY.lower().rstrip(".")
    return normalized == target or target in normalized


def query_rag(
    query: str,
    user_role: str,
    document_id: Optional[str] = None,
    k: int = DEFAULT_TOP_K,
    vector_db: Any = None,
    llm: Any = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """End-to-end permission-aware RAG pipeline returning `{'reply': ..., 'sources': [...]}`.

    1. Retrieves top-k chunks with Chroma metadata filter pushdown AND post-retrieval SQL registry verification.
    2. Short-circuits with `NO_CONTEXT_REPLY` and empty sources if no authorized registry-verified context is found.
    3. Builds the grounded prompt and generates an answer with Gemini.
    4. Returns deduplicated, SQL-registry-verified source citations (`[{'id': doc_id, 'title': title}]`),
       or `[]` when the assistant states the answer cannot be found in the user's documents.
    """
    authorized_chunks = retrieve_authorized_chunks(
        query=query,
        user_role=user_role,
        document_id=document_id,
        k=k,
        vector_db=vector_db,
        db=db,
    )

    if not authorized_chunks:
        return {"reply": NO_CONTEXT_REPLY, "sources": []}

    prompt = build_prompt(question=query, chunks=authorized_chunks, user_role=user_role, db=db)
    chat_model = llm if llm is not None else get_chat_model()
    answer_text = _invoke_llm(chat_model, prompt)

    if not answer_text or _is_refusal_reply(answer_text):
        return {"reply": answer_text or NO_CONTEXT_REPLY, "sources": []}

    return {
        "reply": answer_text,
        "sources": extract_unique_sources(authorized_chunks, user_role=user_role, db=db),
    }
