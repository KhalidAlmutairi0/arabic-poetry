from fastapi import APIRouter
from app.api.v1.routers import search, poets, poems, verses, ai, categories, discover

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(search.router)
api_router.include_router(poets.router)
api_router.include_router(poems.router)
api_router.include_router(verses.router)
api_router.include_router(ai.router)
api_router.include_router(categories.router)
api_router.include_router(discover.router)
