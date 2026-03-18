# Cypher - Multi-Agent Compliance System

A sophisticated multi-agent system for document processing, intelligent reasoning, and risk scoring across compliance domains. Combines PDF extraction, semantic search (RAG), LLM reasoning, and deterministic risk assessment.

## Overview

Cypher automates compliance analysis through three specialized agents:

### Agent 1: Document Processing & Embeddings
- Upload compliance report PDFs
- Extract and chunk text intelligently
- Generate embeddings using BGE (BAAI/bge-base-en-v1.5)
- Store vectors in FAISS for semantic search

### Agent 2: RAG + LLM Reasoning
- Domain-aware iterative reasoning
- Semantic retrieval from document chunks
- Structured extraction via Groq LLM
- Coverage validation with automatic loop control (max 6 iterations)
- Interactive chat interface for domain exploration

### Agent 3: Risk Scoring & Reporting
- Deterministic domain-level risk scoring
- Threshold comparison and validation
- Per-report score persistence
- Aggregate reporting with Excel export

## Project Structure

```
cypher/
├── backend/                 # FastAPI services & agent pipelines
│   ├── app/
│   │   ├── agents/         # Agent implementations (Agent 1, 2, 3)
│   │   ├── api/routes/     # REST API endpoints
│   │   ├── core/           # Config & security
│   │   ├── schemas/        # Pydantic models
│   │   ├── services/       # Business logic services
│   │   └── main.py         # FastAPI application
│   ├── data/               # FAISS indices & metadata
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── frontend/               # React + Vite UI
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js         # Backend API client
│   │   └── main.jsx
│   ├── package.json
│   └── README.md
│
├── knowledge_base.json     # Domain configs & thresholds
└── README.md              # This file
```

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- npm or yarn
- Groq API Key (for Agent 2 LLM reasoning)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env and set GROQ_API_KEY

# Run server
uvicorn app.main:app --reload --port 8000
```

The backend API will be available at `http://localhost:8000`

**API Documentation:** Visit `http://localhost:8000/docs` for interactive Swagger UI

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173` (Vite default)

## Authentication

Currently uses API key authentication:
- **Header:** `x-api-key`
- **Default Key:** `demo-key-123`
- **Default User:** `demo_user`

Configure in `.env`:
```
HARDCODED_USERNAME=demo_user
HARDCODED_API_KEY=demo-key-123
```

## Environment Configuration

Create `.env` in the `backend/` directory with the following variables:

```env
# Application
APP_NAME=Cypher Multi-Agent Backend
API_V1_PREFIX=/api/v1
HARDCODED_USERNAME=demo_user
HARDCODED_API_KEY=demo-key-123

# Embeddings
BGE_MODEL_NAME=BAAI/bge-base-en-v1.5
FAISS_INDEX_PATH=data/agent1.index
FAISS_METADATA_PATH=data/agent1_metadata.json
KNOWLEDGE_BASE_PATH=knowledge_base.json
AGENT3_STORE_PATH=data/agent3_scores.json

# LLM (Groq)
GROQ_API_KEY=your-groq-api-key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.1-8b-instant
GROQ_TIMEOUT_SECONDS=60
GROQ_MAX_RETRIES=4
GROQ_REQUESTS_PER_MINUTE=20

# Agent Configuration
AGENT2_MAX_LOOPS=6
CHUNK_SIZE=800
CHUNK_OVERLAP=120
```

## API Endpoints

### Health Check
- `GET /api/v1/health` - Service health status

### Agent 1: Document Processing
- `POST /api/v1/agent1/process` - Upload and process PDF document

### Agent 2: RAG + Reasoning
- `GET /api/v1/agent2/domains` - Get available domains from knowledge base
- `POST /api/v1/agent2/chat` - Chat with reasoning agent for domain analysis

### Agent 3: Risk Scoring
- `POST /api/v1/agent3/score-domain` - Score a specific domain
- `GET /api/v1/agent3/report` - Get current risk report (JSON)
- `GET /api/v1/agent3/report/excel` - Download risk report (Excel format)

## Tech Stack

### Backend
- **Framework:** FastAPI
- **Web Server:** Uvicorn
- **ML/Embeddings:** Sentence Transformers (BGE model)
- **Vector Store:** FAISS
- **LLM:** Groq API (Llama 3.1)
- **PDF Processing:** PyPDF
- **Data Validation:** Pydantic
- **Export:** OpenPyXL (Excel)

### Frontend
- **Framework:** React 19
- **Build Tool:** Vite
- **JavaScript:** ES6+

## Development

### Running Tests
```bash
cd backend
pytest
```

### Building Frontend for Production
```bash
cd frontend
npm run build
```

This creates an optimized build in `dist/` directory.

## Dependencies

### Backend Dependencies
All Python dependencies are listed in `backend/requirements.txt`. Key packages:
- FastAPI & Uvicorn - Web framework
- Sentence Transformers - Embeddings
- FAISS - Vector search
- Groq - LLM API
- PyPDF - PDF parsing
- OpenPyXL - Excel export

### Frontend Dependencies
- React - UI framework
- Vite - Build tool and dev server

## Workflow

1. **Upload Document (Agent 1)**
   - User uploads PDF file through frontend
   - Backend extracts text and splits into chunks
   - BGE model generates embeddings
   - Vectors stored in FAISS index

2. **Ask Questions (Agent 2)**
   - User selects domain from knowledge base
   - System generates control queries
   - FAISS retrieves relevant chunks
   - Groq LLM performs structured extraction
   - Coverage validated; loops continue if needed (max 6)

3. **Generate Risk Report (Agent 3)**
   - Scores calculated for each domain
   - Compared against thresholds
   - Per-report scores stored
   - Final aggregate report generated
   - Export to Excel for stakeholders

## Configuration Files

### knowledge_base.json
Defines domains, control mappings, and risk thresholds:
```json
{
  "domains": [...],
  "risk_thresholds": {...}
}
```

### .env.example
Template for environment variables. Copy to `.env` and customize.

## Common Issues & Solutions

### FAISS Index Not Found
Ensure `data/agent1.index` exists or upload a document first through Agent 1.

### Groq API Key Error
Verify `GROQ_API_KEY` is set in `.env` and valid at `https://console.groq.com/`

### Model Download Delays
First run may take time as BGE model downloads (~300MB). Subsequent runs use cached version.

### CORS Issues
Both backend and frontend run on different ports by default. Ensure CORS is properly configured if deploying.

## Documentation

- Backend detailed documentation: [backend/README.md](backend/README.md)
- Frontend detailed documentation: [frontend/README.md](frontend/README.md)
- API docs: Available at `/docs` when backend is running

## Learning Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Sentence Transformers](https://www.sbert.net/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [Groq API Docs](https://console.groq.com/docs)
