"""
AI Router — verse explanation with streaming SSE.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from uuid import UUID
from app.services.verse_service import VerseService
from app.services.ai_service import AIService
from app.api.v1.dependencies import get_verse_service, get_ai_service, get_cache
from app.core.cache import CacheService
from app.core.database import run_in_background
from app.core.config import settings
from app.core.exceptions import not_found
from app.models.verse_explanation import VerseExplanation
import asyncio
import json

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get(
    "/verses/{verse_id}/explain",
    summary="Stream AI explanation for a verse",
    description="Returns Server-Sent Events (SSE) stream of the explanation.",
)
async def explain_verse(
    verse_id: UUID,
    type: str = Query("simple", description="simple | literary | linguistic"),
    verse_service: VerseService = Depends(get_verse_service),
    ai_service: AIService = Depends(get_ai_service),
    cache: CacheService = Depends(get_cache),
):
    if type not in ("simple", "literary", "linguistic"):
        type = "simple"

    # 1. Check Redis cache
    cache_key = cache.explanation_key(str(verse_id), type)
    cached = await cache.get(cache_key)
    if cached:
        async def send_cached():
            # Send full cached text as a single SSE event
            text = cached if isinstance(cached, str) else cached.get("text", "")
            yield f"data: {json.dumps({'text': text, 'done': False})}\n\n"
            yield f"data: {json.dumps({'done': True, 'source': 'cache'})}\n\n"

        return StreamingResponse(send_cached(), media_type="text/event-stream")

    # 2. Check DB for pre-generated explanation
    try:
        verse = await verse_service.get_with_all(verse_id)
    except Exception:
        raise not_found("Verse", str(verse_id))

    existing = next(
        (e for e in verse.explanations if e.explanation_type == type), None
    )
    if existing:
        async def send_db():
            yield f"data: {json.dumps({'text': existing.explanation_ar, 'done': False})}\n\n"
            yield f"data: {json.dumps({'done': True, 'source': 'db'})}\n\n"
            # Also cache it
            asyncio.create_task(cache.set(cache_key, {"text": existing.explanation_ar}))

        return StreamingResponse(send_db(), media_type="text/event-stream")

    # 3. Generate from AI (streaming)
    verse_data = {
        "full_verse": verse.full_verse,
        "poet_name_ar": verse.poet_name_ar,
        "poem_title_ar": verse.poem_title_ar,
        "era": None,  # TODO: join with poem
    }

    async def generate_and_stream():
        full_text = []
        try:
            async for chunk in ai_service.explain_verse_stream(verse_data, type):
                full_text.append(chunk)
                yield f"data: {json.dumps({'text': chunk, 'done': False})}\n\n"

            complete_text = "".join(full_text)

            # Done signal
            yield f"data: {json.dumps({'done': True, 'source': 'ai'})}\n\n"

            # Save to cache + DB (non-blocking, own session for DB)
            asyncio.create_task(cache.set(cache_key, {"text": complete_text}))

            vid = verse_id
            etype = type
            text_copy = complete_text
            model = settings.ollama_model_chat

            async def _save_explanation(session):
                from sqlalchemy import select
                existing = (await session.execute(
                    select(VerseExplanation).where(
                        VerseExplanation.verse_id == vid,
                        VerseExplanation.explanation_type == etype,
                    )
                )).scalar_one_or_none()
                if existing:
                    existing.explanation_ar = text_copy
                    existing.generated_by = model
                else:
                    session.add(VerseExplanation(
                        verse_id=vid, explanation_type=etype,
                        explanation_ar=text_copy, generated_by=model,
                        is_ai_generated=True,
                    ))

            asyncio.create_task(run_in_background(_save_explanation))
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        generate_and_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.get("/health", summary="Check AI service health")
async def ai_health(ai_service: AIService = Depends(get_ai_service)):
    is_healthy = await ai_service.health_check()
    return {"ollama": is_healthy, "model": settings.ollama_model_chat}
