# LRN Voice Interview

Standalone EIGI + Pipecat Client proof of integration for the LRN mock-interview experience.
It intentionally lives outside the production `lrn` repository until the integration contract is approved.

## Architecture

1. The React client optionally uploads a PDF/DOCX resume, which the backend reads in memory and sanitizes without storing the original file.
2. The client sends the selected role, focus, mode, duration and extracted resume context to this backend.
3. The backend sends those values to EIGI and keeps its API key out of the browser.
4. EIGI returns a short-lived Daily room URL and token.
5. Pipecat Client connects through Daily and owns microphone, remote audio and connection state.
6. The client captures final candidate/interviewer transcript events and saves them against a frozen interview attempt.
7. The review screen polls EIGI briefly for structured call analysis and renders it when ready.

EIGI hosts the actual Pipecat/OpenAI agent. This project does not duplicate that runtime.

The prototype attempt store is intentionally in memory and resets with the backend. Production LRN will use its authenticated MongoDB models and private object storage for resumes. The prototype does not retain uploaded resume files.

## Configure

Copy `backend/.env.example` to `backend/.env` and provide:

```env
EIGI_BASE_URL=https://api.eigi.ai
EIGI_API_KEY=your-server-only-key
EIGI_AGENT_ID=your-configured-agent-id
```

The API key must never be added to the frontend.

## Run

Backend (Python 3.11+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8010
```

Frontend (Node 20+):

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend proxies `/api` to port `8010`.

## Verify

```powershell
cd backend
.venv\Scripts\python -m pytest

cd ..\frontend
npm run build
```

Without EIGI credentials, `/api/config` reports `configured: false` and session creation returns a safe `503`; no secret value is returned.

