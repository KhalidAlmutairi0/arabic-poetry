# شعر — Arabic Poetry Platform

> "Google + Genius for Arabic Poetry"

A production-grade Arabic poetry platform combining world-class search, semantic discovery, and AI-powered understanding.

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+
- Python 3.12+

### 1. Clone & Configure

```bash
cp .env.example .env
# Edit .env with your values
```

### 2. Start all backend services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL 16 + pgvector (port 5432)
- Redis 7 (port 6379)
- Meilisearch (port 7700)
- Ollama + Qwen 2.5 (port 11434)
- FastAPI backend (port 8000)

### 3. Seed the database

```bash
cd backend
pip install -r requirements.txt
python scripts/seed_data.py
```

### 4. Start the frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000

---

## 📁 Project Structure

```
poetry-platform/
├── frontend/          # Next.js 15 (Vercel)
│   ├── app/           # App Router pages
│   ├── components/    # UI components
│   └── lib/           # API client, hooks, utils
│
├── backend/           # FastAPI (Railway)
│   ├── app/
│   │   ├── api/       # Routers
│   │   ├── services/  # Business logic
│   │   ├── models/    # SQLAlchemy ORM
│   │   ├── schemas/   # Pydantic schemas
│   │   └── utils/     # Arabic normalizer
│   └── scripts/       # Data import + seeding
│
└── docker-compose.yml # Full local stack
```

---

## 🔍 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/search?q=...&mode=hybrid` | Search verses |
| GET | `/v1/search/autocomplete?q=...` | Autocomplete |
| GET | `/v1/poets/{slug}` | Poet profile |
| GET | `/v1/poems/{slug}` | Full poem |
| GET | `/v1/verses/{id}` | Single verse |
| GET | `/v1/ai/verses/{id}/explain` | Stream AI explanation |
| GET | `/v1/categories` | All categories |

API docs: http://localhost:8000/docs

---

## 🤖 AI Features

- **Verse explanation** — Streaming Qwen 2.5 explanations (simple, literary, linguistic)
- **Semantic search** — Embedding-based similarity via pgvector
- **Hybrid search** — Combines keyword (Meilisearch) + semantic (pgvector) via RRF

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 + TypeScript + TailwindCSS |
| Backend | FastAPI + Python 3.12 |
| Database | PostgreSQL 16 + pgvector |
| Search | Meilisearch |
| Cache | Redis |
| AI | Ollama + Qwen 2.5 |
| Deployment | Vercel (frontend) + Railway (backend) |

---

## 📖 Key Concepts

### Arabic Text Normalization
All text goes through `ArabicNormalizer` before indexing:
- Remove diacritics (harakat)
- Normalize Hamza variants (أ إ آ → ا)
- Remove tatweel (kashida)
- Normalize Ta marbuta (ة → ه)

### Hybrid Search (RRF)
Combines two search signals:
1. **Meilisearch** — keyword, typo-tolerant, fast
2. **pgvector** — semantic similarity via embeddings

Merged with Reciprocal Rank Fusion (k=60, 60/40 split).

---

## 🚢 Deployment

### Frontend → Vercel
```bash
cd frontend
vercel deploy
```

### Backend → Railway
1. Connect GitHub repo to Railway
2. Set environment variables from `.env.example`
3. Deploy backend, PostgreSQL, Redis, Meilisearch as separate services

---

Built with ❤️ for Arabic poetry
