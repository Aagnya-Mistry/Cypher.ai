# Backend (Agent 1 + Agent 2)

## Features
- Agent 1: Upload compliance report PDF, extract text, chunk, BGE embeddings, FAISS storage.
- Agent 2: Domain-based iterative RAG + LLM reasoning with Groq API and max 6 loops.
- Agent 3: Deterministic risk scoring, threshold comparison, domain-score storage, aggregate final report, Excel export.

## Run
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Configure these in `.env` before running Agent 2:
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `GROQ_REQUESTS_PER_MINUTE`
- `GROQ_MAX_RETRIES`

## API
- `GET /api/v1/health`
- `POST /api/v1/agent1/process`
- `GET /api/v1/agent2/domains`
- `POST /api/v1/agent2/chat`
- `POST /api/v1/agent3/score-domain`
- `GET /api/v1/agent3/report`
- `GET /api/v1/agent3/report/excel`

### Auth
Header: `x-api-key: demo-key-123`
