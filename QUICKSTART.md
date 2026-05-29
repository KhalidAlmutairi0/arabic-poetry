# شعر — Arabic Poetry Platform — Quick Start

## Prerequisites
- Docker Desktop running
- Node.js 18+
- Python 3.11+ (for local backend dev)

---

## 1 — Start the Backend Services (Docker)

```bash
cd "C:\Users\Admin\Desktop\مجلد جديد"
docker-compose up -d
```

This starts:
- **PostgreSQL** (port 5432) with pgvector
- **Redis** (port 6379)
- **Meilisearch** (port 7700)
- **Ollama** (port 11434) — downloads models automatically
- **FastAPI backend** (port 8000)

Wait ~30 seconds for all services to be healthy. Check:
```
docker-compose ps
```

---

## 2 — Run Database Migration + Seed Data

```bash
docker-compose exec backend alembic upgrade head
docker-compose exec backend python scripts/seed_data.py
```

This creates all tables and seeds 6 poets, 7 poems, ~70 famous verses, and 10 categories.
It also indexes the data to Meilisearch automatically.

---

## 3 — Start the Frontend

```bash
cd "C:\Users\Admin\Desktop\arabic-poetry-ui"
npm install   # only needed once
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## 4 — Verify the API

Open **http://localhost:8000/docs** for the interactive API documentation.

Health check: http://localhost:8000/health

---

## How It's Connected

```
Browser (localhost:3000)
    │
    ├─ Server Components ──▶ http://localhost:8000/api/v1/...  (direct, no CORS)
    │
    └─ Client Components ──▶ http://localhost:8000/api/v1/...  (CORS allowed for :3000)
                         OR ──▶ /api/v1/...  (Next.js rewrite proxy → :8000)
```

### Route Mapping

| UI Route | Backend Call |
|----------|-------------|
| `/` | `GET /api/v1/poets/?limit=6` (featured poets) |
| `/search?q=...` | `GET /api/v1/search/?q=...&mode=hybrid` |
| `/poet/[slug]` | `GET /api/v1/poets/{slug}` |
| `/poem/[slug]` | `GET /api/v1/poems/{slug}` |
| `/verse/[uuid]` | `GET /api/v1/verses/{uuid}` |
| `/verse/[uuid]` (AI button) | `GET /api/v1/ai/verses/{uuid}/explain?type=simple` (SSE stream) |
| `/poets` | `GET /api/v1/poets/?era=...&page=...` |
| `/categories` | `GET /api/v1/categories/` |

### Fallback Behavior

Every page has built-in fallback data so the UI renders beautifully even when the backend is not running. The fallback data is replaced with real API data once the backend is available.

---

## Troubleshooting

**Backend not responding?**
```bash
docker-compose logs backend
```

**Meilisearch search not working?**
```bash
# Re-index manually
docker-compose exec backend python scripts/seed_data.py
```

**Ollama AI explanation not working?**
```bash
docker-compose exec ollama ollama pull qwen2.5:7b
```

**CORS error in browser console?**
The CORS config allows `http://localhost:3000` and `http://localhost:3001`. If you're on a different port, update `backend/app/core/config.py` `cors_origins`.
