"""
Search Service — Hybrid search combining Meilisearch + pgvector.
Uses Reciprocal Rank Fusion (RRF) to merge results.
"""

import asyncio
import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from meilisearch_python_sdk import AsyncClient as MeiliClient
from app.utils.arabic_normalizer import normalizer
from app.services.ai_service import AIService
from app.core.config import settings

logger = logging.getLogger(__name__)


class SearchService:
    # Class-level cache: None = unchecked, True/False = has/no embeddings
    _embeddings_available: bool | None = None

    def __init__(
        self,
        db: AsyncSession,
        meili: MeiliClient,
        ai_service: AIService,
    ):
        self.db = db
        self.meili = meili
        self.ai = ai_service

    async def _has_embeddings(self) -> bool:
        """Check once whether the embeddings table has any rows."""
        if SearchService._embeddings_available is not None:
            return SearchService._embeddings_available
        try:
            row = await self.db.execute(text("SELECT EXISTS(SELECT 1 FROM embeddings LIMIT 1)"))
            SearchService._embeddings_available = bool(row.scalar())
        except Exception:
            SearchService._embeddings_available = False
        return SearchService._embeddings_available

    async def search_verses(
        self,
        query: str,
        mode: str = "hybrid",
        filters: dict | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        start = time.time()
        normalized_query = normalizer.normalize_query(query)
        filters = filters or {}

        # Skip semantic search when no embeddings are in the DB
        has_embed = await self._has_embeddings()
        if not has_embed and mode in ("hybrid", "semantic"):
            mode = "keyword"

        if mode == "keyword":
            result = await self._keyword_search(normalized_query, filters, limit, offset)
        elif mode == "semantic":
            result = await self._semantic_search(query, filters, limit, offset)
        else:  # hybrid (default)
            result = await self._hybrid_search(query, normalized_query, filters, limit, offset)

        result["processing_time_ms"] = int((time.time() - start) * 1000)
        return result

    # ──────────────────────────────────────────────────
    # KEYWORD SEARCH (Meilisearch)
    # ──────────────────────────────────────────────────

    async def _keyword_search(
        self,
        normalized_query: str,
        filters: dict,
        limit: int,
        offset: int,
    ) -> dict:
        try:
            index = self.meili.index("verses")
            filter_str = self._build_meili_filter(filters)

            search_kwargs: dict = {
                "limit": limit,
                "offset": offset,
                "attributes_to_highlight": ["full_verse_normalized"],
                "highlight_pre_tag": "<mark>",
                "highlight_post_tag": "</mark>",
                "attributes_to_retrieve": [
                    "id", "full_verse", "hemistich_1", "hemistich_2",
                    "poet_name_ar", "poet_slug", "poem_title_ar", "poem_slug",
                    "poet_id", "poem_id", "is_famous", "era",
                ],
            }
            if filter_str:
                search_kwargs["filter"] = filter_str

            result = await index.search(normalized_query, **search_kwargs)

            hits = []
            for h in (result.hits or []):
                hit = dict(h)
                if "_formatted" in hit:
                    formatted = hit.pop("_formatted")
                    hit["_highlighted"] = formatted.get("full_verse_normalized")
                hits.append(hit)

            return {
                "hits": hits,
                "estimated_total_hits": getattr(result, "estimated_total_hits", len(hits)),
                "mode": "keyword",
            }
        except Exception as e:
            logger.error(f"Meilisearch error: {e}")
            return {"hits": [], "estimated_total_hits": 0, "mode": "keyword"}

    # ──────────────────────────────────────────────────
    # SEMANTIC SEARCH (pgvector)
    # ──────────────────────────────────────────────────

    async def _semantic_search(
        self,
        query: str,
        filters: dict,
        limit: int,
        offset: int,
        embed_timeout: float = 3.0,
    ) -> dict:
        # Use a short timeout so slow embedding doesn't block keyword results
        query_vector = await self.ai.embed_text(query, timeout=embed_timeout)
        if not query_vector:
            return {"hits": [], "estimated_total_hits": 0, "mode": "semantic"}

        # Build filter WHERE clause
        where_clauses = ["e.entity_type = 'verse'"]
        params: dict = {"vector": str(query_vector), "limit": limit + offset}

        if filters.get("poet_id"):
            where_clauses.append("v.poet_id = :poet_id")
            params["poet_id"] = filters["poet_id"]

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            SELECT
                v.id::text,
                v.full_verse,
                v.hemistich_1,
                v.hemistich_2,
                v.poet_name_ar,
                v.poem_title_ar,
                v.poem_slug,
                v.poet_id::text,
                v.poem_id::text,
                v.is_famous,
                1 - (e.vector <=> CAST(:vector AS vector)) AS similarity
            FROM verses v
            JOIN embeddings e ON e.entity_id = v.id AND {where_sql}
            ORDER BY e.vector <=> CAST(:vector AS vector)
            LIMIT :limit
        """)

        try:
            rows = await self.db.execute(sql, params)
            all_rows = rows.fetchall()

            hits = []
            for row in all_rows[offset:]:
                similarity = float(row.similarity)
                if similarity < 0.60:  # Minimum threshold
                    continue
                hits.append({
                    "id": row.id,
                    "full_verse": row.full_verse,
                    "hemistich_1": row.hemistich_1,
                    "hemistich_2": row.hemistich_2,
                    "poet_name_ar": row.poet_name_ar,
                    "poem_title_ar": row.poem_title_ar,
                    "poem_slug": row.poem_slug,
                    "poet_id": row.poet_id,
                    "poem_id": row.poem_id,
                    "is_famous": row.is_famous,
                    "_semantic_score": similarity,
                })

            return {"hits": hits, "estimated_total_hits": len(all_rows), "mode": "semantic"}
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return {"hits": [], "estimated_total_hits": 0, "mode": "semantic"}

    # ──────────────────────────────────────────────────
    # HYBRID SEARCH (RRF fusion)
    # ──────────────────────────────────────────────────

    async def _hybrid_search(
        self,
        raw_query: str,
        normalized_query: str,
        filters: dict,
        limit: int,
        offset: int,
    ) -> dict:
        # Run both in parallel; embedding has a 3s cap so keyword wins fast
        keyword_task = self._keyword_search(normalized_query, filters, limit * 2, 0)
        semantic_task = self._semantic_search(raw_query, filters, limit * 2, 0, embed_timeout=3.0)

        keyword_result, semantic_result = await asyncio.gather(
            keyword_task, semantic_task, return_exceptions=True
        )

        # Graceful degradation
        if isinstance(keyword_result, Exception):
            logger.warning(f"Keyword search failed, falling back to semantic: {keyword_result}")
            return semantic_result if not isinstance(semantic_result, Exception) else {"hits": [], "estimated_total_hits": 0}

        if isinstance(semantic_result, Exception):
            logger.warning(f"Semantic search failed, falling back to keyword: {semantic_result}")
            return keyword_result

        # RRF fusion
        fused_hits = self._rrf_merge(
            keyword_result.get("hits", []),
            semantic_result.get("hits", []),
            k=60,
            keyword_weight=0.6,
            semantic_weight=0.4,
        )

        total = max(
            keyword_result.get("estimated_total_hits", 0),
            semantic_result.get("estimated_total_hits", 0),
        )

        return {
            "hits": fused_hits[offset: offset + limit],
            "estimated_total_hits": total,
            "mode": "hybrid",
        }

    def _rrf_merge(
        self,
        keyword_hits: list,
        semantic_hits: list,
        k: int = 60,
        keyword_weight: float = 0.6,
        semantic_weight: float = 0.4,
    ) -> list:
        """
        Reciprocal Rank Fusion:
        RRF(d) = Σ weight * (1 / (k + rank(d)))
        """
        scores: dict[str, float] = {}
        data: dict[str, dict] = {}

        for rank, hit in enumerate(keyword_hits, start=1):
            _id = hit.get("id", "")
            if not _id:
                continue
            scores[_id] = scores.get(_id, 0) + keyword_weight * (1.0 / (k + rank))
            data[_id] = hit

        for rank, hit in enumerate(semantic_hits, start=1):
            _id = hit.get("id", "")
            if not _id:
                continue
            scores[_id] = scores.get(_id, 0) + semantic_weight * (1.0 / (k + rank))
            if _id not in data:
                data[_id] = hit

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        return [{**data[_id], "_score": scores[_id]} for _id in sorted_ids]

    # ──────────────────────────────────────────────────
    # AUTOCOMPLETE
    # ──────────────────────────────────────────────────

    async def autocomplete(self, prefix: str, limit: int = 8) -> dict:
        normalized_prefix = normalizer.normalize_query(prefix)

        async def verse_suggestions():
            try:
                index = self.meili.index("verses")
                result = await index.search(
                    normalized_prefix,
                    limit=4,
                    attributes_to_retrieve=["id", "full_verse", "poet_name_ar"],
                )
                return [
                    {
                        "id": h["id"],
                        "full_verse": h.get("full_verse", "")[:80],
                        "poet_name_ar": h.get("poet_name_ar", ""),
                    }
                    for h in (result.hits or [])
                ]
            except Exception:
                return []

        async def poet_suggestions():
            try:
                index = self.meili.index("poets")
                result = await index.search(
                    prefix,
                    limit=3,
                    attributes_to_retrieve=["id", "name_ar", "slug", "era"],
                )
                return [
                    {
                        "slug": h["slug"],
                        "name_ar": h["name_ar"],
                        "era": h.get("era"),
                    }
                    for h in (result.hits or [])
                ]
            except Exception:
                return []

        verses, poets = await asyncio.gather(verse_suggestions(), poet_suggestions())
        return {"verses": verses, "poets": poets}

    # ──────────────────────────────────────────────────
    # INDEXING (called after data import)
    # ──────────────────────────────────────────────────

    async def index_verse(self, verse_data: dict) -> bool:
        try:
            index = self.meili.index("verses")
            await index.add_documents([verse_data])
            return True
        except Exception as e:
            logger.error(f"Verse indexing error: {e}")
            return False

    async def index_poet(self, poet_data: dict) -> bool:
        try:
            index = self.meili.index("poets")
            await index.add_documents([poet_data])
            return True
        except Exception as e:
            logger.error(f"Poet indexing error: {e}")
            return False

    # ──────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────

    def _build_meili_filter(self, filters: dict) -> str | None:
        parts = []
        if "poet_id" in filters:
            parts.append(f'poet_id = "{filters["poet_id"]}"')
        if "is_famous" in filters:
            parts.append(f'is_famous = {str(filters["is_famous"]).lower()}')
        if "era" in filters:
            parts.append(f'era = "{filters["era"]}"')
        return " AND ".join(parts) if parts else None
