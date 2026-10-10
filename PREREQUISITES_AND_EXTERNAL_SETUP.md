# Prerequisites, API Keys & External Setup Guide

This document specifies all system installations, environment variables, and external service configurations required to run and build the **Folio Access-Controlled RAG Engine** and the **FAISS Research Benchmarking Suite**.

---

## 1. System Requirements

| Component | Minimum Version | Verified Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Python** | 3.10+ | 3.12.3 | Backend API, SQLAlchemy ORM, ChromaDB vector store, FAISS research |
| **Node.js** | 18+ | 20+ / 18.3+ | Folio React 18 + Vite 5 frontend workspace |
| **npm** | 9+ | 10+ | Frontend package management |
| **SQLite** | 3.35+ | Built-in | User accounts, session store, document registry |
| **Tesseract OCR** (Optional) | 4.0+ | Ubuntu `tesseract-ocr` | Image text extraction in `services/ocr_service.py` (has graceful fallback) |

---

## 2. Python Environment & Installation

### 2.1 Virtual Environment Setup
Always run the backend within a dedicated virtual environment:
```bash
# 1. Create Python virtual environment
python3 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install all requirements
pip install -r requirements.txt
```

### 2.2 Optional System Packages (For OCR)
If you intend to ingest scanned images (.png, .jpg) via OCR:
```bash
# Debian / Ubuntu
sudo apt update && sudo apt install -y tesseract-ocr

# macOS (Homebrew)
brew install tesseract
```
*Note: If Tesseract is not installed, the application continues to run normally, gracefully skipping optical character extraction on raw images.*

---

## 3. Environment Variables & API Keys Configuration

Copy the template to create your active `.env`:
```bash
cp .env.example .env
```

### 3.1 Configuration Reference

| Environment Variable | Default / Recommended Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./data/folio.db` | Connection string for SQLite user and document database. |
| `SECRET_KEY` | `folio-secret-key-local-development-2026` | Cryptographic secret used for session salt and token validation. Change in production. |
| `SESSION_DURATION_DAYS` | `7` | Duration in days before HttpOnly cookie sessions expire. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of allowed frontend origins for CORS. |
| `GEMINI_API_KEY` | `""` (Empty by default) | Google Gemini API Key. Required for cloud embeddings and cloud LLM generation. |
| `EMBEDDING_PROVIDER` | `gemini` (or `local`) | Choose `gemini` for Google GenAI or `local` for offline `sentence-transformers`. |
| `LLM_PROVIDER` | `gemini` (or `local`) | Choose `gemini` for Google GenAI chat or `local` for local model inference. |
| `LLM_MODEL` | `gemini-1.5-flash` | The generative Gemini model name for the RAG assistant. |

### 3.2 Obtaining a Google Gemini API Key
1. Visit [Google AI Studio](https://aistudio.google.com/).
2. Sign in with your Google account.
3. Click **"Get API key"** and create a new key.
4. Add the key to your `.env` file:
   ```ini
   GEMINI_API_KEY=AIzaSy...YourKeyHere...
   ```

### 3.3 Running in Zero-API-Key Local Mode
If you do not have a Gemini API key or wish to operate in an offline air-gapped environment:
1. Set in `.env`:
   ```ini
   EMBEDDING_PROVIDER=local
   LLM_PROVIDER=local
   ```
2. The system uses `sentence-transformers/all-MiniLM-L6-v2` locally for all vector embeddings without making external network calls.

---

## 4. Frontend Environment Setup

In the `frontend/` directory, create your local configuration:
```bash
cd frontend
cp .env.example .env.local
```

Contents of `frontend/.env.local`:
```ini
# Switch between 'demo' (mock UI) and 'api' (live FastAPI backend)
VITE_DATA_MODE=api
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Install frontend packages:
```bash
npm install
npm test
```
