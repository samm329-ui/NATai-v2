# N.A.T. AI Assistant

An intelligent AI assistant built with FastAPI, LangChain, Groq AI, and a modern glass-morphism web UI. N.A.T. (Natasha) provides two chat modes (General and Realtime with web search), streaming responses, text-to-speech, voice input, and learns from your personal data files. Everything runs on one server with one command.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Technologies Used](#technologies-used)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- **Python 3.10+** with pip
- **OS**: Windows, macOS, or Linux
- **API Keys** (set in `.env` file):
  - `GROQ_API_KEY` (required) - Get from https://console.groq.com  
    You can use **multiple Groq API keys** (`GROQ_API_KEY_2`, `GROQ_API_KEY_3`, ...) for automatic fallback when one hits rate limits or fails.
  - `TAVILY_API_KEY` (optional, for Realtime mode) - Get from https://tavily.com

### Installation

1. **Clone or download** this repository.

2. **Install dependencies**:

```bash
pip install -r requirements.txt
```

3. **Create a `.env` file** in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
# Optional: multiple keys for fallback when one hits rate limit
# GROQ_API_KEY_2=second_key
# GROQ_API_KEY_3=third_key
TAVILY_API_KEY=your_tavily_api_key_here

# Optional
GROQ_MODEL=llama-3.3-70b-versatile
ASSISTANT_NAME=Natasha
JARVIS_USER_TITLE=Boss
TTS_VOICE=en-US-AriaNeural
TTS_RATE=+0%
```

4. **Start the server**:

```bash
python run.py
```

5. **Open in browser**: http://localhost:8000

That's it. The server hosts both the API and the frontend on port 8000.

---

## Features

### Chat Modes

- **General Mode**: Pure LLM responses using Groq AI. Uses your learning data and conversation history as context. No internet access.
- **Realtime Mode**: Searches the web via Tavily before answering. Smart query extraction converts messy conversational text into focused search queries. Uses advanced search depth with AI-synthesized answers.
- **Intelligence Mode**: Analyze companies, industries, brands, or sectors with structured financial and market intelligence.

### Text-to-Speech (TTS)

- Server-side TTS using `edge-tts` (Microsoft Edge's free cloud TTS, no API key needed).
- Audio is generated on the server and streamed inline with text chunks via SSE.
- Sentences are detected in real time as text streams in, converted to speech in background threads.
- The client plays audio segments sequentially in a queue.

### Voice Input

- Browser-native speech recognition (Web Speech API).
- Speak your question, and it auto-sends when you finish.

### Learning System

- Put `.txt` files in `database/learning_data/` with any personal information, preferences, or context.
- Past conversations are saved as JSON in `database/chats_data/`.
- At startup, all learning data and past chats are chunked, embedded with HuggingFace sentence-transformers, and stored in a FAISS vector index.
- For each question, only the most relevant chunks are retrieved (semantic search) and sent to the LLM.

### Session Persistence

- Conversations are saved to disk after each message and survive server restarts.
- General, Realtime, and Intelligence modes share the same session, so context carries over between modes.

### Multi-Key API Fallback

- Configure multiple Groq API keys (`GROQ_API_KEY`, `GROQ_API_KEY_2`, `GROQ_API_KEY_3`, ...).
- Primary-first: every request tries the first key. If it fails (rate limit, timeout), the next key is tried automatically.

### Frontend

- Dark glass-morphism UI with animated WebGL orb in the background.
- The orb animates when the AI is speaking (TTS playing) and stays subtle when idle.
- Responsive: works on desktop, tablets, and mobile.
- No build tools, no frameworks — vanilla HTML/CSS/JS.

---

## How It Works

### Step 1: User Sends a Message

The user types a question (or speaks it via voice input) and presses Send. The frontend sends a POST request to the backend with `{ message, session_id, tts }`.

### Step 2: Backend Processing

FastAPI validates the request and routes it to the appropriate service based on the chat mode.

### Step 3: Context Retrieval

The user's question is embedded using HuggingFace sentence-transformers. FAISS performs a nearest-neighbor search against the vector store to retrieve relevant context from learning data.

### Step 4: LLM Response

- **General Mode**: Uses Groq AI with the retrieved context.
- **Realtime Mode**: First extracts a search query, performs web search via Tavily, then uses Groq AI with search results.
- **Intelligence Mode**: Analyzes companies, industries, or sectors with structured data.

### Step 5: Streaming with TTS

The response is streamed via Server-Sent Events (SSE). If TTS is enabled, sentences are detected in real-time and converted to speech via edge-tts, streamed as base64 audio.

---

## Architecture

```
User (Browser)
    |
    |  HTTP POST (JSON) + SSE response stream
    v
+--------------------------------------------------+
|  FastAPI Application  (app/main.py)              |
|  - CORS middleware                               |
|  - _stream_generator (SSE + inline TTS)          |
+--------------------------------------------------+
    |                           |
    v                           v
+------------------+   +------------------------+
|  ChatService     |   |  TTS Thread Pool       |
|  (chat_service)  |   |  (4 workers, edge-tts) |
|  - Sessions      |   +------------------------+
|  - History       |
|  - Disk I/O      |
+------------------+
    |
    v
+------------------+   +------------------------+
|  GroqService     |   |  RealtimeService      |
|  (groq_service)  |   |  (realtime_service)   |
|  - General chat |   |  - Query extraction    |
|  - Multi-key    |   |  - Tavily web search   |
+------------------+   +------------------------+
    |
    v
+------------------+   +------------------------+
| IntelligenceServ |   |  VectorStoreService   |
| (intelligence)  |   |  (vector_store)       |
| - Company       |   |  - FAISS index        |
|   analysis      |   |  - HuggingFace embeds |
+------------------+   +------------------------+
```

---

## Project Structure

```
NATai/
├── frontend/                    # Web UI (vanilla HTML/CSS/JS)
│   ├── index.html               # Single-page app structure
│   ├── style.css                # Dark glass-morphism theme
│   ├── script.js                # Chat logic, SSE streaming, TTS player
│   └── orb.js                   # WebGL animated orb renderer
│
├── app/                         # Backend (FastAPI)
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, all endpoints
│   ├── models.py                # Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat_service.py      # Session management
│   │   ├── groq_service.py       # General chat with Groq
│   │   ├── realtime_service.py   # Realtime chat with web search
│   │   ├── intelligence_service.py  # Company/industry analysis
│   │   ├── vector_store.py      # FAISS vector index
│   │   └── memory_service.py     # Persistent memory
│   └── utils/
│       ├── __init__.py
│       ├── retry.py             # Retry with exponential backoff
│       └── time_info.py         # Current date/time
│
├── database/                    # Auto-created on first run
│   ├── learning_data/           # Your .txt files
│   ├── chats_data/              # Saved conversations
│   └── vector_store/            # FAISS index files
│
├── config.py                    # All settings
├── run.py                       # Entry point
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker build
├── docker-compose.yml            # Docker Compose
├── .env                         # Your API keys
└── README.md                    # This file
```

---

## API Endpoints

### POST `/chat`
General chat (non-streaming). Returns full response at once.

### POST `/chat/stream`
General chat with streaming. Returns Server-Sent Events.

### POST `/chat/realtime/stream`
Realtime chat with streaming. Web search + SSE streaming.

### POST `/intelligence`
Analyze companies, industries, brands, or sectors.

**Request body:**
```json
{
  "message": "What is Python?",
  "session_id": "optional-uuid",
  "tts": true
}
```

### GET `/health`
Health check. Returns status of all services.

### GET `/system/status`
Returns system status including vector store, API availability, and active sessions.

### GET `/memory`
Get all persistent memories.

### POST `/memory`
Add a new persistent memory.

---

## Configuration

### Environment Variables (.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | - | Primary Groq API key |
| `GROQ_API_KEY_2`, `_3`, ... | No | - | Additional keys for fallback |
| `TAVILY_API_KEY` | No | - | Tavily search API key |
| `ALPHA_VANTAGE_KEY` | No | - | Alpha Vantage for financial data |
| `FMP_KEY` | No | - | Financial Modeling Prep |
| `NEWS_API_KEY` | No | - | News API |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | LLM model name |
| `ASSISTANT_NAME` | No | `Natasha` | Assistant's name |
| `JARVIS_USER_TITLE` | No | `Boss` | How to address the user |
| `TTS_VOICE` | No | `en-US-AriaNeural` | Edge TTS voice |
| `TTS_RATE` | No | `+0%` | Speech speed |

### Learning Data

Add `.txt` files to `database/learning_data/`:
- Files are loaded and indexed at startup.
- Only relevant chunks are sent to the LLM per question.
- Restart the server after adding new files.

---

## Technologies Used

### Backend
| Technology | Purpose |
|-----------|---------|
| FastAPI | Web framework, async endpoints, SSE streaming |
| LangChain | LLM orchestration, prompt templates |
| Groq AI | LLM inference (Llama 3.3 70B) |
| Tavily | AI-optimized web search |
| FAISS | Vector similarity search |
| HuggingFace | Local embeddings (sentence-transformers) |
| edge-tts | Server-side text-to-speech |
| Pydantic | Request/response validation |
| Uvicorn | ASGI server |

### Frontend
| Technology | Purpose |
|-----------|---------|
| Vanilla JS | Chat logic, SSE streaming, TTS playback |
| WebGL/GLSL | Animated orb |
| Web Speech API | Browser-native speech-to-text |
| CSS Glass-morphism | Dark translucent panels |

---

## Deployment

### Docker (Recommended)

```bash
# Build and run with Docker Compose
docker-compose up --build -d
```

### Manual Deployment

1. **Railway** - Connect GitHub repo, set environment variables, auto-deploys
2. **Render** - Connect repo, set build/start commands
3. **Fly.io** - `fly launch`, `fly deploy`
4. **Heroku** - Git push with Python buildpack
5. **DigitalOcean** - Connect repo, configure app platform

See the platform documentation for detailed deployment steps.

---

## Troubleshooting

### Server won't start
- Ensure `GROQ_API_KEY` is set in `.env`.
- Run `pip install -r requirements.txt`.
- Check that port 8000 is not in use.

### "Offline" status in the UI
- The server is not running. Start with `python run.py`.

### Realtime mode gives generic answers
- Ensure `TAVILY_API_KEY` is set in `.env`.

### TTS not working
- Make sure TTS is enabled (speaker icon highlighted).
- Check server logs for errors.

### Vector store errors
- Delete `database/vector_store/` and restart.

---

**Start chatting:** `python run.py` then open http://localhost:8000
