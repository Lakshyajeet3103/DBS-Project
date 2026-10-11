"""Folio Multi-Format Ingestion & Tagged ChromaDB Pipeline (Person 2).

Implements Tasks 2.1, 2.2, 2.3, and 2.4:
- Task 2.1: Multi-format document loaders (PDF via PyPDFLoader/pypdf, Plain Text & Markdown,
  Images via `services.ocr_service.extract_text_from_image`, and SQL Registry loader).
- Task 2.2: Semantic text splitting (`chunk_size=800`, `chunk_overlap=150`, `length_function=len`)
  and strict ACL metadata injection (`document_id`, `title`, `level`, `category`, `type`, `year`, `chunk_index`).
- Task 2.3: Configurable embedding selector (`EMBEDDING_PROVIDER=gemini` or `local`) and
  idempotent ChromaDB persistence (`persist_directory="./chroma"`, `collection_name="folio_knowledge_base"`)
  using deterministic chunk IDs (`f"{doc.id}_chunk_{idx}"`).
- Task 2.4: CLI entrypoint and post-ingestion metadata filter pushdown verification.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database.connection import Base, SessionLocal, engine
from database.models import Document
from database.seed import seed_database
from services.ocr_service import SUPPORTED_IMAGE_EXTENSIONS, extract_text_from_image
from services.rag_service import (
    DEFAULT_CHROMA_DIR,
    DEFAULT_COLLECTION_NAME,
    get_embedding_model,
    get_vector_db,
)

load_dotenv()

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
REQUIRED_METADATA_KEYS = {
    "document_id",
    "title",
    "level",
    "category",
    "type",
    "year",
    "chunk_index",
}


# ---------------------------------------------------------------------------
# Task 2.1: Multi-Format Document Loaders
# ---------------------------------------------------------------------------

def load_pdf_file(pdf_path: Union[str, Path]) -> str:
    """Extract text from a PDF file using pypdf (with PyPDFLoader fallback)."""
    path_str = str(pdf_path)
    if not os.path.isfile(path_str):
        raise FileNotFoundError(f"PDF file not found: {path_str}")

    try:
        from pypdf import PdfReader

        reader = PdfReader(path_str)
        extracted = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(t.strip() for t in extracted if t.strip())
    except ImportError:
        from langchain_community.document_loaders import PyPDFLoader

        loader = PyPDFLoader(path_str)
        pages = loader.load()
        return "\n\n".join(p.page_content.strip() for p in pages if getattr(p, "page_content", "").strip())


def load_text_or_markdown_file(file_path: Union[str, Path]) -> str:
    """Load UTF-8 content directly from a .txt or .md file."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Text/Markdown file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_image_file(image_path: Union[str, Path]) -> str:
    """Extract text from a .png, .jpg, or .jpeg file using the OCR service."""
    return extract_text_from_image(image_path)


def load_file_content(file_path: Union[str, Path]) -> str:
    """Dispatch to the appropriate loader based on file extension."""
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return load_pdf_file(path)
    if ext in {".txt", ".md"}:
        return load_text_or_markdown_file(path)
    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return load_image_file(path)
    raise ValueError(f"Unsupported file format: {ext!r} for {path}")


def load_sql_registry_documents(db: Optional[Session] = None) -> List[Document]:
    """Load all canonical document records from the SQLite `documents` table."""
    Base.metadata.create_all(bind=engine)
    own_session = db is None
    session = SessionLocal() if own_session else db
    try:
        count = session.query(Document).count()
        if count == 0:
            seed_database()
        return session.query(Document).order_by(Document.id).all()
    finally:
        if own_session:
            session.close()


# ---------------------------------------------------------------------------
# Task 2.2: Text Splitting & Strict Metadata Injection
# ---------------------------------------------------------------------------

def get_text_splitter(chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
    """Return a configured RecursiveCharacterTextSplitter (`chunk_size=800`, `chunk_overlap=150`)."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )


def split_text_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """Split raw document text into semantic chunks of `chunk_size` with `chunk_overlap`."""
    clean = (text or "").strip()
    if not clean:
        return []
    try:
        splitter = get_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        return splitter.split_text(clean)
    except ImportError:
        step = max(1, chunk_size - chunk_overlap)
        return [clean[i : i + chunk_size] for i in range(0, len(clean), step)]


def build_chunk_metadata(
    document_id: str,
    title: str,
    level: str,
    category: str,
    doc_type: str,
    year: Union[str, int],
    chunk_index: int,
) -> Dict[str, Any]:
    """Construct and validate the mandatory ACL metadata dictionary for a vector chunk."""
    normalized_level = (level or "").strip().lower()
    if normalized_level not in ("junior", "senior"):
        raise ValueError(f"Chunk metadata level must be 'junior' or 'senior', got {level!r}")

    doc_id = (document_id or "").strip()
    if not doc_id:
        raise ValueError("Chunk metadata document_id cannot be empty.")

    return {
        "document_id": doc_id,
        "title": (title or doc_id).strip(),
        "level": normalized_level,
        "category": (category or "General").strip(),
        "type": (doc_type or "Guide").strip(),
        "year": str(year).strip(),
        "chunk_index": int(chunk_index),
    }


def chunk_document_record(
    doc: Document,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
    """Split a SQL `Document` record into `(texts, metadatas, ids)` with deterministic IDs."""
    pieces = split_text_into_chunks(doc.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    for idx, piece in enumerate(pieces):
        meta = build_chunk_metadata(
            document_id=doc.id,
            title=doc.title,
            level=doc.level,
            category=doc.category,
            doc_type=doc.type,
            year=doc.year,
            chunk_index=idx,
        )
        texts.append(piece)
        metadatas.append(meta)
        ids.append(f"{doc.id}_chunk_{idx}")

    return texts, metadatas, ids


def scan_external_documents(
    documents_dir: Union[str, Path] = "data/documents",
    db: Optional[Session] = None,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
    """Scan `data/documents/` for PDF, TXT, MD, and image files and build tagged chunks."""
    base_path = Path(documents_dir)
    if not base_path.exists():
        return [], [], []

    registry_docs = {d.id: d for d in load_sql_registry_documents(db=db)}
    supported_exts = {".pdf", ".txt", ".md"} | SUPPORTED_IMAGE_EXTENSIONS

    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    for file_path in sorted(base_path.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in supported_exts:
            continue

        content = load_file_content(file_path)
        if not content:
            continue

        stem = file_path.stem.lower().replace("_", "-").replace(" ", "-")
        reg_doc = registry_docs.get(stem)

        # Infer access level from parent folder ('junior' or 'senior') if not in registry
        parent_names = {p.name.lower() for p in file_path.parents}
        inferred_level = "senior" if "senior" in parent_names else "junior"

        doc_id = reg_doc.id if reg_doc else stem
        title = reg_doc.title if reg_doc else file_path.stem.replace("-", " ").replace("_", " ").title()
        level = reg_doc.level if reg_doc else inferred_level
        category = reg_doc.category if reg_doc else "Knowledge Base"
        doc_type = reg_doc.type if reg_doc else "Guide"
        year = str(reg_doc.year) if reg_doc else "2026"

        pieces = split_text_into_chunks(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for idx, piece in enumerate(pieces):
            meta = build_chunk_metadata(
                document_id=doc_id,
                title=title,
                level=level,
                category=category,
                doc_type=doc_type,
                year=year,
                chunk_index=idx,
            )
            texts.append(piece)
            metadatas.append(meta)
            ids.append(f"{doc_id}_chunk_{idx}")

    return texts, metadatas, ids


# ---------------------------------------------------------------------------
# Task 2.3 & 2.4: ChromaDB Persistence, CLI Entrypoint & Verification
# ---------------------------------------------------------------------------

def process_and_save_pdf(
    pdf_path: str = "data/sample_document.pdf",
    document_id: str = "getting-started",
    level: str = "junior",
    persist_directory: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_function: Any = None,
):
    """Load a PDF file, chunk with `RecursiveCharacterTextSplitter`, tag with ACL metadata, and save to Chroma."""
    print(f"Loading {pdf_path}")

    registry_docs = {d.id: d for d in load_sql_registry_documents()}
    reg_doc = registry_docs.get(document_id)

    pdf_text = load_pdf_file(pdf_path)
    pieces = split_text_into_chunks(pdf_text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    for idx, piece in enumerate(pieces):
        meta = build_chunk_metadata(
            document_id=reg_doc.id if reg_doc else document_id,
            title=reg_doc.title if reg_doc else "Your first week, made simple",
            level=reg_doc.level if reg_doc else level,
            category=reg_doc.category if reg_doc else "Getting started",
            doc_type=reg_doc.type if reg_doc else "Guide",
            year=reg_doc.year if reg_doc else "2026",
            chunk_index=idx,
        )
        texts.append(piece)
        metadatas.append(meta)
        ids.append(f"{meta['document_id']}_pdf_chunk_{idx}")

    print(f"Chunked the pdf into {len(texts)} metadata-tagged chunks.")

    vector_db = get_vector_db(
        persist_directory=persist_directory,
        collection_name=collection_name,
        embedding_function=embedding_function,
    )
    if texts:
        vector_db.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    print("Success! Chunks were converted to vector embeddings and stored in chromadb. AI database is ready.")
    return vector_db


def verify_ingestion(vector_db: Any = None) -> bool:
    """Task 2.4 verification: confirm junior filter returns 0 senior chunks and senior filter returns senior chunks."""
    vdb = vector_db if vector_db is not None else get_vector_db()

    junior_hits = vdb.similarity_search("strategy", k=5, filter={"level": "junior"})
    if not junior_hits:
        raise AssertionError("Verification failed: expected junior chunks for filter={'level': 'junior'}, got 0.")
    if not all(h.metadata.get("level") == "junior" for h in junior_hits):
        raise AssertionError("Verification failed: senior or untagged chunk leaked into junior filter results!")

    senior_hits = vdb.similarity_search("strategy", k=5, filter={"level": "senior"})
    if not senior_hits:
        raise AssertionError("Verification failed: expected senior chunks for filter={'level': 'senior'}, got 0.")
    if not all(h.metadata.get("level") == "senior" for h in senior_hits):
        raise AssertionError("Verification failed: non-senior chunk returned for filter={'level': 'senior'}!")

    print("Metadata filter pushdown verified! (0 senior leaks in junior query; senior query succeeded)")
    return True


def ingest_all(
    persist_directory: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    documents_dir: Union[str, Path] = "data/documents",
    sample_pdf_path: Optional[str] = "data/sample_document.pdf",
    embedding_function: Any = None,
    db: Optional[Session] = None,
    run_verification: bool = True,
) -> Dict[str, Any]:
    """Ingest SQL registry documents + external files in `data/documents/` + sample PDF into ChromaDB."""
    sql_docs = load_sql_registry_documents(db=db)

    chunk_map: Dict[str, Tuple[str, Dict[str, Any]]] = {}

    # 1. Load canonical documents from SQL registry
    for doc in sql_docs:
        texts, metas, ids = chunk_document_record(doc)
        for text, meta, cid in zip(texts, metas, ids):
            chunk_map[cid] = (text, meta)

    # 2. Scan external multi-format documents in data/documents/
    ext_texts, ext_metas, ext_ids = scan_external_documents(documents_dir=documents_dir, db=db)
    for text, meta, cid in zip(ext_texts, ext_metas, ext_ids):
        chunk_map[cid] = (text, meta)

    all_ids = list(chunk_map.keys())
    all_texts = [chunk_map[cid][0] for cid in all_ids]
    all_metadatas = [chunk_map[cid][1] for cid in all_ids]

    vector_db = get_vector_db(
        persist_directory=persist_directory,
        collection_name=collection_name,
        embedding_function=embedding_function,
    )

    # Remove legacy untagged 'langchain' collection if present and prune stale chunk IDs
    client = getattr(vector_db, "_client", None)
    if client is not None:
        try:
            existing_names = {
                c.name if hasattr(c, "name") else str(c) for c in client.list_collections()
            }
            if "langchain" in existing_names and collection_name != "langchain":
                client.delete_collection("langchain")
        except Exception:
            pass

    collection_handle = getattr(vector_db, "_collection", None)
    if collection_handle is not None:
        try:
            existing_ids = set(collection_handle.get().get("ids") or [])
            stale_ids = list(existing_ids - set(all_ids))
            if stale_ids:
                collection_handle.delete(ids=stale_ids)
        except Exception:
            pass

    if all_texts:
        print(f"Upserting {len(all_texts)} tagged chunks into ChromaDB collection '{collection_name}'...")
        vector_db.add_texts(texts=all_texts, metadatas=all_metadatas, ids=all_ids)

    # 3. Validate data/sample_document.pdf loader path
    if sample_pdf_path and os.path.isfile(sample_pdf_path):
        pdf_text = load_pdf_file(sample_pdf_path)
        pdf_chunks = split_text_into_chunks(pdf_text)
        print(f"Verified PDF loader on {sample_pdf_path} ({len(pdf_chunks)} chunks extracted).")

    if run_verification:
        verify_ingestion(vector_db=vector_db)

    return {
        "total_chunks": len(all_texts),
        "collection_name": collection_name,
        "persist_directory": persist_directory,
    }


if __name__ == "__main__":
    ingest_all()