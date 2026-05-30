# QA Report — Arabic Poetry Platform (شعر)

**Date**: 2026-05-30
**Auditor**: Automated QA (static analysis + code review)
**Codebase**: FastAPI backend + Next.js 16 frontend
**Commit**: `ff81dcd`

---

## Summary

| Metric | Count |
|--------|-------|
| Total issues found | **38** |
| Critical (must fix before launch) | **9** |
| Medium (fix soon) | **16** |
| Minor (nice to fix) | **13** |

---

## Critical Issues (must fix before launch)

### C-01: XSS Vulnerability — `dangerouslySetInnerHTML` on user-facing data
**File**: `frontend/components/poetry/VerseCard.tsx:55-66`
**Severity**: CRITICAL (Security)

```tsx
<span dangerouslySetInnerHTML={{ __html: verse.hemistich_1 || "" }} />
<span dangerouslySetInnerHTML={{ __html: verse.hemistich_2 || "" }} />
<span dangerouslySetInnerHTML={{ __html: verse._highlighted || verse.full_verse }} />
```

Verse text from the API (including Meilisearch `<mark>` highlights) is rendered as raw HTML. If any verse in the database contains `<script>`, `<img onerror=...>`, or other HTML, it will execute in every visitor's browser. The discovery service imports text from external APIs (qafiyah.com), making injection trivial — a malicious entry on the external API flows directly into rendered HTML.

**Fix**: Sanitize with DOMPurify (allow only `<mark>`) or render text content and apply highlighting with a safe React approach.

---

### C-02: Admin endpoints return 200 on auth failure
**File**: `backend/app/main.py:181-182, 307-309, 483-485`
**Severity**: CRITICAL (Security)

```python
@app.post("/admin/seed", tags=["system"])
async def seed_database(key: str = ""):
    if key != settings.secret_key:
        return {"error": "unauthorized"}   # <-- 200 OK!
```

All three admin endpoints (`/admin/seed`, `/admin/import-ashaar`, `/admin/seed-bulk`) return HTTP 200 with a JSON body on auth failure instead of HTTP 401/403. Security scanners, WAFs, and monitoring tools will treat these as successful requests. Additionally:
- The `key` is passed as a **query parameter**, which gets logged in server access logs, browser history, and proxy logs
- Default key is `"dev_secret_key_change_in_production_min_32"` — easily guessable

**Fix**: Return `HTTPException(status_code=403)`. Move key to `Authorization` header. Use a proper admin auth middleware.

---

### C-03: Exception details leaked to clients
**File**: `backend/app/main.py:131-135`
**Severity**: CRITICAL (Security)

```python
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)[:500]})
```

Raw exception messages (up to 500 chars) are sent to the client. These can contain:
- Database connection strings and credentials
- File paths revealing server structure
- SQL query fragments
- Internal service URLs

**Fix**: Return a generic message in production. Only include `str(exc)` when `settings.debug is True`.

---

### C-04: No authentication system — all endpoints are public
**Severity**: CRITICAL (Security)

The `User` model exists with `email`, `hashed_password`, and `role` fields, but:
- No login/register endpoints exist
- No JWT/session middleware exists
- No route protection exists
- Admin endpoints use only a query param key
- The `Favorite` model exists but is unusable without auth

Any user can access all data endpoints, and anyone who discovers the admin URLs can attempt brute-force key guessing with no rate limiting.

**Fix**: Implement auth endpoints, JWT middleware, and role-based access control before launch.

---

### C-05: No rate limiting implemented
**Severity**: CRITICAL (Security/Availability)

Config defines rate limits (`rate_limit_search: "60/minute"`, `rate_limit_ai: "10/minute"`) but **no rate limiting middleware is actually applied**. Critical abuse vectors:
- `/api/v1/ai/verses/{id}/explain` — each call triggers an Ollama inference (expensive GPU compute)
- `/api/v1/search/` — each miss triggers a PostgreSQL raw query
- `/api/v1/discover/` — each call makes external HTTP requests to qafiyah.com and writes to DB
- `/admin/import-ashaar` — each call fetches from HuggingFace and bulk-inserts to DB

**Fix**: Add `slowapi` or `fastapi-limiter` middleware using the existing Redis instance.

---

### C-06: Broken layout imports — Header and Footer
**File**: `frontend/app/layout.tsx:3-4`
**Severity**: CRITICAL (Functional)

```tsx
import { Header } from '@/components/header'     // ← file does not exist
import { Footer } from '@/components/footer'     // ← file does not exist
```

The actual components are at:
- `@/components/layout/Header.tsx`
- `@/components/layout/Footer.tsx`

No barrel files (`index.ts`) exist at `@/components/header` or `@/components/footer`. This means the layout **will fail to compile** unless `ignoreBuildErrors: true` in `next.config.mjs` is silently swallowing it, or there are re-export files not captured by the glob. Either way, this is a ticking time bomb.

**Fix**: Change imports to `@/components/layout/Header` and `@/components/layout/Footer`.

---

### C-07: Two conflicting CSS systems
**Files**: `frontend/app/globals.css` and `frontend/styles/globals.css`
**Severity**: CRITICAL (Visual)

Two completely different CSS variable systems exist:
- `app/globals.css` uses `oklch()` color space with Tailwind 4 `@theme` syntax and `--background`, `--foreground`, etc.
- `styles/globals.css` uses hex colors (`#0C0C0B`) with Tailwind 3 `@tailwind` directives and `--background`, `--surface`, `--text-primary`, etc.

Both define `:root` variables with **different names for similar concepts** (e.g., `--text-primary` vs `--foreground`). Components in the codebase reference variables from **both** systems (`text-primary`, `text-muted`, `bg-surface`, `bg-background`), meaning whichever file loads last wins, and some variables will be undefined.

The layout imports `./globals.css` (= `app/globals.css`), so `styles/globals.css` may not be loaded at all, leaving components that depend on `--surface`, `--text-primary`, `--accent-dim`, etc. with broken styles.

**Fix**: Consolidate into one CSS file. Remove the unused one. Verify all CSS variable references resolve.

---

### C-08: Missing `/categories/[slug]` route — dead links everywhere
**Files**: `frontend/components/poetry/CategoryGrid.tsx:17`, `frontend/components/poetry/PoemReader.tsx:65`
**Severity**: CRITICAL (Functional)

```tsx
<Link href={`/categories/${cat.slug}`}>
```

Category cards link to `/categories/{slug}` but **no `frontend/app/(poetry)/categories/[slug]/page.tsx` exists**. Every category click from the homepage, categories page, and poem detail page will result in a 404.

**Fix**: Create `frontend/app/(poetry)/categories/[slug]/page.tsx` that shows poems in that category, or change links to filter the poems page (`/poems?category={slug}`).

---

### C-09: Poet link uses UUID instead of slug — guaranteed 404
**File**: `frontend/app/(poetry)/verses/[id]/page.tsx:90`
**Severity**: CRITICAL (Functional)

```tsx
<Link href={`/poets/${verse.poet_id}`}>  // ← UUID like "a1b2c3d4-..."
```

The verse detail page links to the poet using `verse.poet_id` (a UUID), but the route expects a slug (`/poets/[slug]`). The API will try to find a poet with slug = UUID string, which will always 404.

**Fix**: The verse detail API response at `backend/app/api/v1/routers/verses.py` doesn't include `poet_slug`. Add it to the response, and use it in the frontend link.

---

## Medium Issues (fix soon)

### M-01: Poems list count query ignores `meter` filter
**File**: `backend/app/services/poem_service.py:58-59`

```python
if meter:
    query = query.where(Poem.meter == meter)
    # count_query is NOT filtered by meter!
```

When filtering poems by meter (بحر), the total count is wrong because the count query doesn't include the meter filter. The pagination will show incorrect total pages.

**Fix**: Add `count_query = count_query.where(Poem.meter == meter)`.

---

### M-02: Famous verses cache key ignores `limit` parameter
**File**: `backend/app/api/v1/routers/verses.py:22`

```python
cache_key = "famous_verses"  # same key for limit=5 and limit=50
```

A request with `?limit=5` caches the result, then `?limit=50` returns the same 5 results from cache.

**Fix**: Include limit in cache key: `cache_key = f"famous_verses:{limit}"`.

---

### M-03: TypeScript build errors silently ignored
**File**: `frontend/next.config.mjs:3-5`

```javascript
typescript: { ignoreBuildErrors: true }
```

Real type errors (null access, wrong prop types, missing fields) are swallowed during build. This means runtime crashes from type mismatches won't be caught until they hit users.

**Fix**: Remove `ignoreBuildErrors: true` and fix all type errors.

---

### M-04: No pagination controls on search results page
**File**: `frontend/app/(search)/search/page.tsx`

The backend returns `page`, `total_pages`, and `estimated_total_hits`, but the search page has no Next/Previous buttons or page indicators. Users can only see the first 20 results.

**Fix**: Add pagination controls that update the `page` state in `useSearch`.

---

### M-05: Duplicate API client implementations
**Files**: `frontend/lib/api.ts` and `frontend/lib/api/client.ts`

Two API clients exist with overlapping functionality:
- `lib/api/client.ts`: `ApiClient` class, **throws** on error
- `lib/api.ts`: `apiFetch` function, returns **null** on error

Pages mix both — some use `getPoet` from `client.ts` (throws), others from `api.ts` (returns null). This inconsistency means some pages crash on API failure while others silently show empty states.

**Fix**: Consolidate into one client. Pick one error handling strategy.

---

### M-06: CORS wildcard pattern doesn't work in FastAPI
**File**: `backend/app/core/config.py:74`

```python
"https://arabic-poetry-ui-*.vercel.app",
```

FastAPI's `CORSMiddleware` does **not** support glob patterns in origin strings. Vercel preview deployment URLs (like `https://arabic-poetry-ui-abc123.vercel.app`) will be blocked by CORS.

**Fix**: Use a custom CORS middleware that checks against a regex, or list the exact preview URLs, or use `allow_origin_regex=r"https://arabic-poetry-ui-.*\.vercel\.app"`.

---

### M-07: `asyncio.create_task()` silently swallows errors
**Files**: Multiple routers (poets.py:98, poems.py:59,96, verses.py:42,68,99,116, ai.py:63,88,113, search.py:92,109)

Background tasks created with `asyncio.create_task()` raise exceptions that go unnoticed. If Redis is down, cache writes fail silently. If DB write fails in view count increment, it's lost.

```python
asyncio.create_task(cache.set(cache_key, response, ttl=86400))
```

**Fix**: Add a task callback for error logging: `task.add_done_callback(lambda t: t.exception() and logger.error(...))`.

---

### M-08: Theme toggle doesn't persist and has wrong initial state
**File**: `frontend/components/layout/Header.tsx:9-15`

```tsx
const [isDark, setIsDark] = useState(true);  // hardcoded
```

- Always starts in dark mode regardless of system preference
- Doesn't persist choice to localStorage
- Doesn't check `prefers-color-scheme`
- Two CSS files define themes differently (`data-theme` vs `.dark` class)

**Fix**: Use `next-themes` (already in package.json but unused) for proper theme management.

---

### M-09: No error boundaries — React errors crash entire page
**Files**: No `error.tsx`, `loading.tsx`, or `not-found.tsx` files exist anywhere in the app

A single component error (e.g., null property access on a verse with missing fields) crashes the entire page with a white screen. No recovery is possible without a page refresh.

**Fix**: Add `error.tsx` at the app root and in route groups. Add `loading.tsx` for navigation feedback.

---

### M-10: Discovery service race condition on concurrent searches
**File**: `backend/app/services/discovery_service.py:182-186`

```python
existing = (await session.execute(
    select(Poem.id).where(Poem.slug == poem_slug)
)).scalar_one_or_none()
if existing: return False
# ← another request could insert the same slug here
```

Two concurrent users searching for the same query will both check for the slug, find it missing, and both try to insert it. The second will fail with a unique constraint violation.

**Fix**: Add `ON CONFLICT DO NOTHING` or catch `IntegrityError` gracefully.

---

### M-11: Seed endpoint creates duplicate engine and session factory
**File**: `backend/app/main.py:185-188, 425-426`

```python
engine = create_async_engine(settings.async_database_url)
Session = async_sessionmaker(engine, expire_on_commit=False)
```

Admin endpoints create new SQLAlchemy engines on every request instead of using the global `AsyncSessionLocal`. This leaks connection pools and can exhaust database connections.

**Fix**: Use the existing `get_db` dependency or `AsyncSessionLocal`.

---

### M-12: `getTrendingVerses` uses `q=*` as search query
**File**: `frontend/lib/api.ts:231`

```tsx
`/search/?q=*&is_famous=true&limit=${limit}&page=1`
```

The `*` character is not a valid Meilisearch wildcard for full-text search. When Meilisearch is unavailable and PostgreSQL fallback is used, `ILIKE '%*%'` will search for the literal asterisk character, returning no results.

**Fix**: Use a dedicated endpoint for trending/famous verses (already exists at `/api/v1/verses/famous`).

---

### M-13: `robots.txt` blocks `/search` from crawlers
**File**: `frontend/app/robots.ts:10`

```tsx
disallow: ["/search", "/api/", "/profile/", "/favorites/"],
```

Blocking `/search` prevents search engines from discovering content through search result pages. Since individual verse/poem pages may not be linked from the main listing pages (only through search), this could significantly reduce SEO visibility.

**Fix**: Allow `/search` in robots.txt, or ensure all content is reachable through listing pages and sitemap.

---

### M-14: Inconsistent API response shapes between endpoints
- `/api/v1/poets/` returns `{ items, total, page, size }` (uses `size` for limit)
- `/api/v1/poems/` returns `{ items, total, page, limit }` (no `total_pages`)
- `/api/v1/poets/{slug}/poems` returns `{ poet_id, poet_name_ar, poems: [] }`
- Poets list endpoint calculates `total_pages` in service but renames `limit` to `size` in router

**Fix**: Standardize all paginated responses to `{ items, total, page, limit, total_pages }`.

---

### M-15: `next-themes` is installed but unused
**File**: `frontend/package.json:14`

```json
"next-themes": "^0.4.6"
```

The package is installed but the `ThemeProvider` is never used. The custom theme toggle in `Header.tsx` doesn't persist across refreshes and conflicts with the two CSS variable systems.

**Fix**: Either use `next-themes` properly with a provider, or remove it from dependencies.

---

### M-16: No input sanitization on `poet_id` query parameter
**File**: `backend/app/api/v1/routers/poems.py:26`

```python
poet_id=UUID(poet_id) if poet_id else None,
```

If `poet_id` is not a valid UUID string (e.g., `poet_id=abc`), `UUID("abc")` raises a `ValueError` which bubbles up as a 500 error with the exception detail leaked (see C-03). Same pattern in Meilisearch filter building.

**Fix**: Add try/except around UUID parsing and return 400 with a clean message.

---

## Minor Issues (nice to fix)

### m-01: Two separate `globals.css` files
Both `frontend/app/globals.css` and `frontend/styles/globals.css` exist. The `styles/` version appears to be from an earlier iteration and may not be loaded. Clean up the unused file to avoid confusion.

### m-02: Images use raw `<img>` instead of Next.js `<Image>`
**Files**: `PoetCard.tsx:48`, `poets/[slug]/page.tsx:72`
Raw `<img>` tags bypass Next.js image optimization (lazy loading, responsive sizes, WebP conversion, layout shift prevention).

### m-03: No custom 404 page
No `not-found.tsx` exists. When `notFound()` is called (poet/poem not found), users see the default Next.js 404 page which doesn't match the platform's design.

### m-04: No loading skeletons during navigation
No `loading.tsx` files exist. Page transitions during client-side navigation show no feedback — the page appears frozen until data loads.

### m-05: Unused `useDebounce` is defined twice
`useDebounce` is defined in both `frontend/lib/hooks/useSearch.ts:6-13` and `frontend/components/search/SearchBar.tsx:17-24`. Extract to a shared utility.

### m-06: `useEffect` dependency array warning suppressed
**File**: `frontend/app/(search)/search/page.tsx:21`
```tsx
}, []); // eslint-disable-line
```
The eslint-disable hides a legitimate stale closure warning. `initialQ` and `initialMode` are captured but excluded from deps.

### m-07: `seed_database` function is 300+ lines inside `create_app`
**File**: `backend/app/main.py:181-584`
The entire `create_app` function is ~490 lines with three admin endpoints defined inline. These should be extracted to a separate router module.

### m-08: Emoji in log messages may break log aggregation
**File**: `backend/app/main.py` and `backend/app/core/database.py`
Log messages contain emoji (🚀, ✅, ⚠️, 👋) which can cause encoding issues with some log aggregation tools (Datadog, Splunk).

### m-09: `Poem.is_published` filter missing from poems count in `list_poems`
**File**: `backend/app/services/poem_service.py:50`
The count query correctly filters `is_published`, but this comment is noting that `Poem.is_published == True` uses Python equality which generates correct SQL but triggers a linter warning (use `.is_(True)` instead).

### m-10: Cache `delete_pattern` uses `SCAN` which is O(N) on Redis
**File**: `backend/app/core/cache.py:90-99`
`scan_iter` with `delete` in a loop is O(N) and can be slow with many keys. Consider using Lua scripts for atomic pattern deletion.

### m-11: `VerseRelation` model has no `TimestampMixin` — comment says why, but inconsistent
**File**: `backend/app/models/verse_relation.py:8`
The comment explains the lack of timestamps, but all other models have them. If verse relations are recomputed, there's no way to know when they were last updated.

### m-12: `Embedding` model imports `settings` at module level
**File**: `backend/app/models/embedding.py:7`
```python
from app.core.config import settings
vector = Column(Vector(settings.embedding_dimensions), nullable=False)
```
The column dimension is set at import time from settings. If settings change without a migration, the column definition and actual DB column will diverge.

### m-13: `alembic.ini` exists but no `alembic/` migration directory
**File**: `backend/alembic.ini`
The Alembic config file exists but there's no `alembic/` directory with migration scripts. The app uses `create_tables()` (which only creates, never migrates), meaning schema changes require dropping and recreating tables.

---

## Performance Concerns

| Endpoint | Concern |
|----------|---------|
| `GET /api/v1/search/` | Falls back to `ILIKE '%query%'` on PostgreSQL when Meilisearch is down — full table scan on potentially millions of verses |
| `GET /api/v1/search/` | Discovery service makes 3 sequential HTTP requests to external API on cache miss with < 3 local results |
| `GET /api/v1/poems/{slug}` | `selectinload` loads ALL verses for a poem — poems with 100+ verses will generate large responses |
| `GET /api/v1/poets/{slug}` | Two sequential DB queries (poet + famous verses) instead of one with join |
| `GET /api/v1/verses/{verse_id}` | Three operations: full verse with relations, view count increment, related verses — could be parallelized |
| `POST /admin/import-ashaar` | Loads all existing poem slugs into memory (`existing_poem_slugs = set(...)`) — at 212K poems this is significant |
| All cached endpoints | Cache-aside pattern means first request after TTL expiry is always slow |

---

## Architecture Notes

### Dead code
- `User` model — no auth endpoints, no login, no registration
- `Favorite` model — no API endpoints to create/read/delete favorites
- `frontend/lib/api.ts` — likely the original API client, superseded by `frontend/lib/api/client.ts`
- `rate_limit_*` settings — defined but never used

### Missing features (referenced but not implemented)
- No `/profile/` or `/favorites/` pages (but blocked in robots.txt)
- No file upload functionality
- No admin dashboard UI
- No user registration/login flow

### Security checklist

| Check | Status |
|-------|--------|
| SQL injection protection | Parameterized queries used throughout |
| XSS protection | **FAILING** — `dangerouslySetInnerHTML` on API data |
| CSRF protection | N/A (no state-changing auth endpoints) |
| Authentication | **MISSING** |
| Authorization (RBAC) | **MISSING** |
| Rate limiting | **MISSING** (config exists, not implemented) |
| Input validation | Partial — Pydantic schemas validate some inputs |
| Error information leakage | **FAILING** — raw exceptions sent to client |
| Secrets management | **WEAK** — hardcoded defaults, query param auth |
| CORS configuration | **PARTIAL** — wildcard pattern doesn't work |
| HTTPS enforcement | Not checked (infrastructure level) |
| Dependency vulnerabilities | Not scanned |

---

## Recommendations — Priority Order

1. **Fix XSS** (C-01) — Immediate. Sanitize all `dangerouslySetInnerHTML` usage.
2. **Fix admin auth** (C-02) — Immediate. Use proper HTTP auth with status codes.
3. **Hide error details** (C-03) — Immediate. Generic message in production.
4. **Fix broken imports** (C-06) — Immediate. App may not build correctly.
5. **Add rate limiting** (C-05) — Before launch. Protect AI and search endpoints.
6. **Create missing routes** (C-08, C-09) — Before launch. Dead links hurt UX and SEO.
7. **Implement auth** (C-04) — Before launch if users/favorites are needed.
8. **Consolidate CSS** (C-07) — Before launch. Visual inconsistencies likely.
9. **Fix meter count bug** (M-01) — Simple fix, high impact.
10. **Add error boundaries** (M-09) — Prevents white-screen crashes.

---

*Generated by automated static analysis and full codebase review. No runtime tests were executed (infrastructure services not running). All findings are based on code-level inspection.*
