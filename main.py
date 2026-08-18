# STEPS
# 1. Implementing the FastAPI backend and uvicorn server [packages used - uvicorn, fastapi]
    # fastAPI is the backend which is used to serve requests, it executes whatever is written below the get fn when a GET request is raised
    # uvicorn is the server that transfers data from frontend to backend and vice-versa

    # these both only service when a GET request is raised from the root

    # use the command on the terminal %uvicorn main:app --reload%
    
# 2. Loading in the api key as an environment variable from the .env file [packages used - dotenv, os]
    # next step is to secure the backend (FastAPI) from the API keys of the AI model being exposed, this is done by setting up environment variables (.env)
    # a .gitignore file is added and .env is written inside so the .env is ignored, while pushing to git
    # the AI model API key should not be hardcoded in the main file. we use .env to store these locally and use Python's os or pydantic-setting to inject them into application at runtime

# 3. Chunking the PDF input, vectorizing them, storing them in vectordb. [packages used - langchain -> core splitting engine [RecursiveCharacterTextSplitter to split the text and also maintain semantic meaning], 
# langchain-community -> interacting with 3rd party tools [like PyPDFLoader, ChromaDB], 
# langchain-google-genai -> api connectors to transmit data to google servers [GoogleGenerativeAIEmbeddings - convert chunks to vectors],
# pypdf -> PyPDFLoader opens file, decodes binary and extracts English text
# chromadb -> Saves the vector input in storage, also performs semantic similarity analysis]

# 4. Passing the user query through the embeddings model, comparing with chromadb, passing context and prompt to LLM [packages used (new) - langchains.chains -> create_stuff_documents_chain: to stuff documents into a prompt & create_retreival_chain: creates a RAG pipeline that automatically feeds the user query to embeddings model, compares to chromadb and outputs top k chunks with the help of retriever. 
# pydantic: to ensure that queries from frontend to backend have some required attributes
# fastapi.middleware.cors(CORSMiddleware): bouncer, ensures that only frontend (port 5173) is allowed to ask server for data
# langchain_core.prompt: used to design the prompt structure]


import os # to use the API Key from .env
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from langchain_chroma import Chroma
from pydantic import BaseModel
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

load_dotenv() # parses and loads all .env variables as enviroment var.s

# accessing the API Key securely from machine memory
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # getenv used to get the env var.

app = FastAPI() # creates server instance

# Used to set up the CORS Middleware
app.add_middleware(CORSMiddleware, allow_origins = ['http://localhost:5173', 'http://127.0.0.1:5173'], allow_methods = ["*"], allow_headers = ["*"], allow_credentials = True)

# Initializing the vector db with physical folder
embeddings = GoogleGenerativeAIEmbeddings(model='gemini-embedding-001')
vector_db = Chroma(persist_directory="./chroma", embedding_function=embeddings)

# Retriever is the wrapper over vector_db and allows to specify number of chunks passed
retriever = vector_db.as_retriever(search_kwargs = {'k': 3})

# initializing the llm
llm = ChatGoogleGenerativeAI(model = 'gemini-3.5-flash', api_key = GEMINI_API_KEY)

# setting up the prompt structure
prompt = PromptTemplate.from_template(
    """You are a highly intelligent study assistant. Answer the user's question usign ONLY the provided context from their documents.
    If the answer is not contained in the context, do not guess. Simply say: "I cannot find this in your documents"
    
    Context: {context}
    
    Question: {input}
        
    Answer:"""
)

# wiring the RAG pipeline
# linking LLM and prompt
combine_docs_chain = create_stuff_documents_chain(llm, prompt)
# linking vector db (retriever) to LLM process
rag_chain = create_retrieval_chain(retriever, combine_docs_chain)

# The API routes
class ChatRequest(BaseModel):
    message: str
@app.get('/') # path operation decorator, it tells the server to listen for GET req.s at root URL
def read_root(): # root handler
    return {"status":"AI backend is running"}

@app.post('/api/chat')
def chat_with_ai(req: ChatRequest):
    print(f"User asked: {req.message}")
    # pass user's message into the pipeline
    response = rag_chain.invoke({'input': req.message})
    
    # pipeline returns dict, display only the answer
    return({"reply": response['answer']})
    
 


