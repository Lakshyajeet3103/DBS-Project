from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def generate_embeddings(chunks):
    """Convert text chunks into numerical vector embeddings."""
    model = SentenceTransformer(MODEL_NAME)

    embeddings = model.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    return embeddings.astype("float32")


if __name__ == "__main__":
    from chunking import load_document, chunk_text

    text = load_document("data/sample_documents.txt")
    chunks = chunk_text(text)

    embeddings = generate_embeddings(chunks)

    print("Number of chunks:", len(chunks))
    print("Embedding dimensions:", embeddings.shape[1])
    print("Embedding matrix shape:", embeddings.shape)