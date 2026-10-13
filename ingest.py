# this is run when the ai needs to read a new doc; only run once, then the chromaDB will store the embeddings

import os
from typing import Any, Optional

from dotenv import load_dotenv

from database.connection import Base, SessionLocal, engine
from database.models import Document
from database.seed import seed_database
from services.rag_service import (
    DEFAULT_CHROMA_DIR,
    DEFAULT_COLLECTION_NAME,
    build_registry_chunks,
    get_embedding_model,
    get_vector_db,
    ingest_registry_documents,
)

load_dotenv()  # loads the key to the environment variables


def process_and_save_pdf(
    pdf_path: str = "data/sample_document.pdf",
    document_id: str = "getting-started",
    level: str = "junior",
    persist_directory: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_function: Any = None,
):
    """Load a PDF, attach canonical SQL registry metadata, and upsert into the shared Chroma collection."""
    from langchain_chroma import Chroma
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    print(f"Loading {pdf_path}")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        reg_doc = db.query(Document).filter(Document.id == document_id).first()
        if reg_doc is None:
            seed_database()
            reg_doc = db.query(Document).filter(Document.id == document_id).first()
        doc_meta = {
            "document_id": reg_doc.id if reg_doc else document_id,
            "title": reg_doc.title if reg_doc else "Getting started at Folio",
            "level": reg_doc.level if reg_doc else level,
            "category": reg_doc.category if reg_doc else "Onboarding",
            "type": reg_doc.type if reg_doc else "Guide",
            "year": str(reg_doc.year) if reg_doc else "2026",
        }
    finally:
        db.close()

    # Extracting the PDF Text from the pdf file
    loader = PyPDFLoader(pdf_path)
    raw_pages = loader.load()  # reading raw pages out of pdf

    # To chunk the data, we instantiate and use the RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        length_function=len,
    )
    chunks = text_splitter.split_documents(raw_pages)

    ids = []
    for idx, chunk in enumerate(chunks):
        chunk.metadata = {
            **doc_meta,
            "chunk_index": idx,
        }
        ids.append(f"{doc_meta['document_id']}_pdf_chunk_{idx}")

    print(f"Chunked the pdf into {len(chunks)} metadata-tagged chunks.")

    embed_model = embedding_function or get_embedding_model()

    print(f"Converting to vectors and saving to ChromaDB collection '{collection_name}'")
    vector_db = Chroma(
        persist_directory=persist_directory,
        embedding_function=embed_model,
        collection_name=collection_name,
    )
    # Ensure canonical SQL registry documents are also indexed with full ACL metadata
    ingest_registry_documents(vector_db=vector_db)
    if chunks:
        vector_db.add_documents(documents=chunks, ids=ids)

    print("Success! Chunks were converted to vector embeddings and stored in chromadb. AI database is ready.")
    return vector_db


def ingest_all(
    persist_directory: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_function: Any = None,
    pdf_path: Optional[str] = "data/sample_document.pdf",
) -> int:
    """Ingest all canonical SQL registry documents (and optional sample PDF) with ACL metadata."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Document).count() == 0:
            seed_database()
    finally:
        db.close()

    if pdf_path and os.path.isfile(pdf_path):
        vdb = process_and_save_pdf(
            pdf_path=pdf_path,
            persist_directory=persist_directory,
            collection_name=collection_name,
            embedding_function=embedding_function,
        )
        return len(build_registry_chunks()["texts"])

    vector_db = get_vector_db(
        persist_directory=persist_directory,
        collection_name=collection_name,
        embedding_function=embedding_function,
    )
    return ingest_registry_documents(vector_db=vector_db)


if __name__ == "__main__":
    process_and_save_pdf("data/sample_document.pdf")