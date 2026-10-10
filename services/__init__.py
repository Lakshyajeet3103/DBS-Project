"""Business logic services package for Folio."""
from services.rag_service import (
    NO_CONTEXT_REPLY,
    RAG_PROMPT_TEMPLATE,
    build_acl_filter,
    build_prompt,
    extract_unique_sources,
    format_context,
    get_chat_model,
    get_embedding_model,
    get_vector_db,
    is_chunk_authorized,
    query_rag,
    retrieve_authorized_chunks,
    verify_and_filter_chunks,
)

__all__ = [
    "NO_CONTEXT_REPLY",
    "RAG_PROMPT_TEMPLATE",
    "build_acl_filter",
    "build_prompt",
    "extract_unique_sources",
    "format_context",
    "get_chat_model",
    "get_embedding_model",
    "get_vector_db",
    "is_chunk_authorized",
    "query_rag",
    "retrieve_authorized_chunks",
    "verify_and_filter_chunks",
]
