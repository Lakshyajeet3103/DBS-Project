from pathlib import Path


def load_document(file_path):
    """Load text from a document."""
    return Path(file_path).read_text(encoding="utf-8")


def chunk_text(text, chunk_size=300, overlap=50, min_chunk_size=20):
    """
    Split document into overlapping chunks, breaking on word boundaries.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end < text_len:
            next_space = text.find(" ", end)
            if next_space != -1 and next_space - end < 50:
                end = next_space

        chunk = text[start:end].strip()
        if len(chunk) >= min_chunk_size:
            chunks.append(chunk)

        if end >= text_len:
            break
        start += chunk_size - overlap

    return chunks


def chunk_by_tokens(text, tokenizer, chunk_size=256, overlap=32):
    """Token-aware chunking — use for actual embedding-model input sizing."""
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    tokens = tokenizer.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(tokenizer.decode(tokens[start:end]))
        if end >= len(tokens):
            break
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
