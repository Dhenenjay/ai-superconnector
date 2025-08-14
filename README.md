# AI Superconnector (Python MVP)

This is a minimal, local-first scaffold for an AI "Superconnector" hub. It uses:
- FastAPI for the API
- SQLite + SQLAlchemy for storage (no Docker required)
- Simple retrieval with optional OpenAI embeddings (fallback deterministic hashing embeddings if no key)
- Stubs for connectors (Gmail, Slack, Notion)

Getting started (Windows PowerShell)
1) Create and activate a virtual environment
   - Using the provided script:
     - powershell: scripts/setup.ps1
   - Or manually:
     - python -m venv .venv
     - .\.venv\Scripts\Activate.ps1
     - python -m pip install --upgrade pip
     - pip install -r requirements.txt

2) Configure environment
   - Copy .env.example to .env and set values.
   - Optional: set OPENAI_API_KEY for real embeddings.

3) Initialize the database (auto on first run)
   - The app will create SQLite DB at ./.data/dev.db

4) Run the API
   - uvicorn apps.api.main:app --reload --port 8000

5) Open the docs
   - http://127.0.0.1:8000/docs

Project layout
- apps/api: FastAPI app and routers
- core: config, DB, models, schemas
- services/connectors: connector stubs
- services/ai: retrieval and tools stubs
- scripts: helper scripts for setup

Next steps
- Wire real OAuth for Gmail/Slack/Notion
- Replace hashing embeddings with OpenAI or another provider
- Add background jobs (APScheduler or external queue if/when you add Redis)
- Implement webhooks for incremental updates
- Build a web dashboard (Next.js) or keep using Swagger for now

Security note
- This scaffold stores data locally in SQLite. Do not use it for production. Add proper secrets management and encryption before handling real tokens.

