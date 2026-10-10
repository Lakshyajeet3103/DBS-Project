"""RAG retrieval and generation service with ChromaDB ACL filter pushdown and source citations.

Implements Task 3.2 & Task 3.3:
1. Pre-retrieval metadata filter pushdown (`build_acl_filter`) derived strictly from the server session role.
2. Vector similarity search against ChromaDB (`retrieve_authorized_chunks`).
3. Post-retrieval defense-in-depth verification (`verify_and_filter_chunks`) ensuring no unauthorized
   or untagged chunk ever reaches the LLM context.
4. Grounded LLM prompt engineering (`RAG_PROMPT_TEMPLATE`, `build_prompt`) with strict refusal on missing context.
5. Deduplicated source citations (`extract_unique_sources`) and end-to-end RAG execution (`query_rag`).
"""
import os
from typing import Any, Dict, List, Optional, Sequence

from core.access import allowed_levels, can_access_level

DEFAULT_CHROMA_DIR = "./chroma"
DEFAULT_COLLECTION_NAME = "folio_knowledge_base"
DEFAULT_TOP_K = 3
DEFAULT_LLM_MODEL = "gemini-1.5-flash"

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
    # Validate against canonical role hierarchy first (fails closed on unknown roles)
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


def is_chunk_authorized(
    chunk: Any,
    user_role: str,
    document_id: Optional[str] = None,
) -> bool:
    """Defense-in-depth check: verify a single retrieved chunk is permitted for `user_role`."""
    metadata = _extract_metadata(chunk)
    chunk_level = metadata.get("level")
    if not isinstance(chunk_level, str) or not can_access_level(user_role, chunk_level):
        return False

    if document_id is not None and metadata.get("document_id") != document_id:
        return False

    return True


def verify_and_filter_chunks(
    chunks: Sequence[Any],
    user_role: str,
    document_id: Optional[str] = None,
) -> List[Any]:
    """Post-retrieval ACL verification gate.

    Ensures that even if the underlying vector store misconfigured or bypassed a filter,
    no Senior chunk (or untagged chunk) is ever returned to a Junior session.
    """
    allowed_levels(user_role)
    return [
        chunk
        for chunk in chunks
        if is_chunk_authorized(chunk, user_role=user_role, document_id=document_id)
    ]


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
    collection = collection_name or os.getenv("CHROMA_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
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
) -> List[Any]:
    """Execute similarity search with pre-retrieval ACL filter pushdown and post-retrieval verification."""
    acl_filter = build_acl_filter(user_role=user_role, document_id=document_id)
    db = vector_db if vector_db is not None else get_vector_db()

    raw_chunks = db.similarity_search(query=query, k=k, filter=acl_filter)
    return verify_and_filter_chunks(raw_chunks, user_role=user_role, document_id=document_id)


def _extract_page_content(chunk: Any) -> str:
    """Safely extract text content from a LangChain Document or dict-like chunk."""
    if hasattr(chunk, "page_content") and isinstance(chunk.page_content, str):
        return chunk.page_content
    if isinstance(chunk, dict) and isinstance(chunk.get("page_content"), str):
        return chunk["page_content"]
    return str(chunk)


def format_context(chunks: Sequence[Any]) -> str:
    """Combine authorized chunk passages into a single context string for the LLM prompt."""
    passages: List[str] = []
    for chunk in chunks:
        text = _extract_page_content(chunk).strip()
        if not text:
            continue
        metadata = _extract_metadata(chunk)
        title = metadata.get("title")
        if isinstance(title, str) and title.strip():
            passages.append(f"[{title.strip()}]\n{text}")
        else:
            passages.append(text)
    return "\n\n---\n\n".join(passages)


def build_prompt(question: str, chunks: Sequence[Any]) -> str:
    """Populate the strict grounded RAG prompt template with authorized context and user question."""
    context_text = format_context(chunks)
    return RAG_PROMPT_TEMPLATE.format(context=context_text, question=question.strip())


def extract_unique_sources(chunks: Sequence[Any]) -> List[Dict[str, str]]:
    """Extract deduplicated [{'id': doc_id, 'title': title}] source citations preserving retrieval order."""
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
        seen_ids.add(doc_id)
        raw_title = metadata.get("title")
        title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else doc_id
        sources.append({"id": doc_id, "title": title})
    return sources


def get_chat_model(model_name: Optional[str] = None):
    """Initialize the Gemini chat model via ChatGoogleGenerativeAI."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment.")
    resolved_model = model_name or os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
    return ChatGoogleGenerativeAI(model=resolved_model, api_key=api_key, temperature=0.0)


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
) -> Dict[str, Any]:
    """End-to-end permission-aware RAG pipeline returning `{'reply': ..., 'sources': [...]}`.

    1. Retrieves top-k chunks with Chroma metadata filter pushdown and post-retrieval verification.
    2. Short-circuits with `NO_CONTEXT_REPLY` and empty sources if no authorized context is found.
    3. Builds the grounded prompt and generates an answer with Gemini.
    4. Returns deduplicated source citations (`[{'id': doc_id, 'title': title}]`), or `[]` when the
       assistant states the answer cannot be found in the user's documents.
    """
    authorized_chunks = retrieve_authorized_chunks(
        query=query,
        user_role=user_role,
        document_id=document_id,
        k=k,
        vector_db=vector_db,
    )

    if not authorized_chunks:
        return {"reply": NO_CONTEXT_REPLY, "sources": []}

    prompt = build_prompt(question=query, chunks=authorized_chunks)
    chat_model = llm if llm is not None else get_chat_model()
    answer_text = _invoke_llm(chat_model, prompt)

    if not answer_text or _is_refusal_reply(answer_text):
        return {"reply": answer_text or NO_CONTEXT_REPLY, "sources": []}

    return {
        "reply": answer_text,
        "sources": extract_unique_sources(authorized_chunks),
    }
