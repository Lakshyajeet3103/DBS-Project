from pathlib import Path


def load_document(file_path):
    """Load text from a document."""
    return Path(file_path).read_text(encoding="utf-8")


def chunk_text(text, chunk_size=300, overlap=50):
    """Split document into overlapping chunks."""
    chunks = []

    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return chunks


if __name__ == "__main__":
    text = load_document("data/sample_documents.txt")
    chunks = chunk_text(text)

    print("Document length:", len(text))
    print("Number of chunks:", len(chunks))

    for i, chunk in enumerate(chunks[:3]):
        print(f"\n--- Chunk {i + 1} ---")
        print(chunk)    