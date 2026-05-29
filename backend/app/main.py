"""
شعر — Arabic Poetry Platform
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time

from app.core.config import settings
from app.core.database import create_tables
from app.core.cache import get_redis, close_redis
from app.core.exceptions import NotFoundException, PoetryException
from app.api.v1.router import api_router

# ── Logging ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting شعر Platform...")

    # Auto-create tables (safe — only creates missing ones)
    try:
        await create_tables()
    except Exception as e:
        logger.warning(f"⚠️ Table creation failed: {e}")

    # Initialize Meilisearch indices
    try:
        await _setup_meilisearch()
        logger.info("✅ Meilisearch ready")
    except Exception as e:
        logger.warning(f"⚠️ Meilisearch setup failed (non-critical): {e}")

    # Test Redis
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}")

    logger.info("✅ Platform ready!")
    yield

    # Shutdown
    await close_redis()
    logger.info("👋 Platform shut down")


async def _setup_meilisearch():
    """Initialize Meilisearch indices with Arabic config."""
    from meilisearch_python_sdk import AsyncClient
    from app.search.meilisearch_config import (
        VERSES_INDEX_CONFIG, POETS_INDEX_CONFIG, POEMS_INDEX_CONFIG
    )

    async with AsyncClient(
        url=settings.meilisearch_url,
        api_key=settings.meilisearch_key,
    ) as client:
        # Create/update indices
        for index_name, config in [
            ("verses", VERSES_INDEX_CONFIG),
            ("poets", POETS_INDEX_CONFIG),
            ("poems", POEMS_INDEX_CONFIG),
        ]:
            try:
                index = client.index(index_name)
                # Update settings (idempotent)
                if "searchableAttributes" in config:
                    await index.update_searchable_attributes(config["searchableAttributes"])
                if "filterableAttributes" in config:
                    await index.update_filterable_attributes(config["filterableAttributes"])
                if "sortableAttributes" in config:
                    await index.update_sortable_attributes(config["sortableAttributes"])
                if "stopWords" in config:
                    await index.update_stop_words(config["stopWords"])
                if "synonyms" in config:
                    await index.update_synonyms(config["synonyms"])
                if "rankingRules" in config:
                    await index.update_ranking_rules(config["rankingRules"])
            except Exception as e:
                logger.debug(f"Index {index_name} setup: {e}")


# ── App Factory ───────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="شعر — Arabic Poetry Platform",
        description="Production-grade Arabic poetry search and discovery platform",
        version=settings.app_version,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ──────────────────────
    @app.middleware("http")
    async def add_process_time(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        process_time = (time.time() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{process_time:.0f}"
        return response

    # ── Exception handlers ────────────────────────────
    @app.exception_handler(NotFoundException)
    async def not_found_handler(request: Request, exc: NotFoundException):
        return JSONResponse(
            status_code=404,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(PoetryException)
    async def poetry_exception_handler(request: Request, exc: PoetryException):
        return JSONResponse(
            status_code=400,
            content={"error": exc.code, "message": exc.message},
        )

    # ── Routers ───────────────────────────────────────
    app.include_router(api_router)

    # ── Health check ──────────────────────────────────
    @app.get("/health", tags=["system"])
    async def health():
        try:
            redis = await get_redis()
            redis_ok = await redis.ping()
        except Exception:
            redis_ok = False

        return {
            "status": "ok",
            "redis": redis_ok,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    @app.get("/", tags=["system"])
    async def root():
        return {
            "name": "شعر Arabic Poetry Platform API",
            "version": settings.app_version,
            "docs": "/docs",
        }

    return app


app = create_app()
