# this is run when the ai needs to read a new doc; only run once, then the chromaDB will store the embeddings

import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma # it uses chromadb package

load_dotenv() # loads the key to the environment variables
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY is not in the .env file!")

def process_and_save_pdf(pdf_path: str):
    print(f"Loading {pdf_path}")
    
    # Extracting the PDF Text from the pdf file
    loader = PyPDFLoader(pdf_path)
    raw_pages = loader.load() # reading raw pages out of pdf
    
    # To chunk the data, we instantiate and use the RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(chunk_size = 1000, chunk_overlap = 200, length_function = len) # 1000 chars each chunk and 200 overlapping chars between chunks
    chunks = text_splitter.split_documents(raw_pages) # split_page is used to split a single page into chunks but split_documents is used to split multiple pages
    
    print(f"Chunked the pdf into {len(chunks)} chunks.")
    
    # Vectorize the chunks using the embeddings ai model and store in chromadb
    embed_model = GoogleGenerativeAIEmbeddings(model = 'gemini-embedding-001')
    
    print("Converting to vectors and saving to ChromaDB")
    # creating a chromadb in a folder ./chroma
    vector_db = Chroma.from_documents(documents = chunks, embedding = embed_model, persist_directory='./chroma')
    
    print("Success! Chunks were converted to vector embeddings and stored in chromadb. AI database is ready.")
    
if __name__ == "__main__": # the __name__ variable is set to the file name that is being currently run. so when we do python ingest.py or add import ingest while in main.py, the __name__ is set to __main__
    process_and_save_pdf("data/sample_document.pdf")        