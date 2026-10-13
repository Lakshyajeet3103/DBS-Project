"""Folio — Access-Controlled RAG Knowledge Engine API Entrypoint.

Developed with FastAPI, SQLite, and ChromaDB.
"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.connection import Base, engine
from routers.auth import router as auth_router

load_dotenv()

# Automatically ensure database tables exist on server startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Folio — Access-Controlled RAG Engine",
    description="Enterprise RAG knowledge base with role-based access control.",
    version="1.0.0"
)

# CORS configuration: must explicitly allow frontend origins when allow_credentials=True
cors_env = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
origins = [o.strip() for o in cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Authentication Router
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "AI backend is running"}
