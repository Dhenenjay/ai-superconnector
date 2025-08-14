# 🚀 AI Superconnector - Twilio + OpenAI Realtime Integration

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Dhenenjay/ai-superconnector)

## 📋 Overview

AI Superconnector is a FastAPI backend service that bridges:
- **Twilio**: WhatsApp messaging and Voice calls with bidirectional audio streaming
- **OpenAI**: Realtime API for voice conversations and AI-powered responses
- **Convex DB**: Cloud database for conversation history and user management

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

## 🌟 Features

- ✅ **WhatsApp Integration**: Send/receive messages via Twilio
- ✅ **Voice Calls**: Bidirectional audio streaming with OpenAI Realtime API
- ✅ **WebSocket Bridge**: Real-time communication between Twilio and OpenAI
- ✅ **AI Embeddings**: Semantic search with OpenAI embeddings
- ✅ **User Management**: Complete user CRUD operations
- ✅ **Conversation History**: Store and retrieve chat/call history

## 🚀 Quick Deploy

### Deploy to Render (Recommended)
1. Click the Deploy button above
2. Set environment variables in Render dashboard
3. Your API will be live at `https://your-app.onrender.com`

### Deploy to Railway
```bash
railway login
railway init
railway up
```

## 🔑 Environment Variables

Create a `.env` file based on `.env.example`:

```env
# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-12-17

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_API_KEY=SK...
TWILIO_API_SECRET=your-api-secret
TWILIO_PHONE_NUMBER=+1234567890

# Convex DB (optional)
CONVEX_URL=https://your-instance.convex.cloud
```

## 📱 Twilio Setup

1. **Configure Webhooks** in Twilio Console:
   - WhatsApp: `https://your-api.com/twilio/webhook/whatsapp`
   - Voice: `https://your-api.com/twilio/webhook/voice/outbound`

2. **Enable Media Streams** for bidirectional audio

## 📖 API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🛠️ Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with hot reload
uvicorn apps.api.main:app --reload --port 8000

# Run tests
pytest tests/
```

## 📝 License

MIT License - feel free to use this for your projects!

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

## ⚠️ Security Notes

- Never commit `.env` files or API keys
- Use environment variables in production
- Enable HTTPS for all production deployments
- Implement rate limiting for public APIs

