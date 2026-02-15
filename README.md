# Cypher - Multiagent System

## Agent 1: Document Processing
- Upload compliance report PDF
- Extract text
- Chunk text
- Embed with BGE (`BAAI/bge-base-en-v1.5`)
- Store vectors in FAISS

## Agent 2: RAG + LLM Reasoning
- User selects domain from `knowledge_base.json`
- Agent generates control query from domain follow-up templates
- Retrieves top-k relevant chunks from FAISS semantic search
- Groq-hosted LLM performs structured extraction
- Coverage is checked; loops continue up to max 6 iterations
- Conversation (control query + LLM answer) is shown in chat UI

## Agent 3: Risk Scoring
- Applies deterministic formula to score each domain
- Compares each domain score against risk threshold in `knowledge_base.json`
- Stores per-domain scores for each report
- Aggregates saved domain scores into final report
- Supports Excel download of final report

## Project Structure
- `backend/` FastAPI services and agent pipelines
- `frontend/` React app for ingestion + reasoning chat

## Backend Quick Start
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Frontend Quick Start
```bash
cd frontend
npm install
npm run dev
```

## Hardcoded Auth
- Header: `x-api-key`
- Default key: `demo-key-123`
- User: `demo_user`
