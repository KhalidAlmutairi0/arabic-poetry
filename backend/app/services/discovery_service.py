"""
Discovery Service — live search from external APIs when local DB has no results.

When a user searches and we find few/no results:
1. Search external sources (qafiyah.com) in real-time
2. Return results to the user immediately
3. Save discovered poems to our DB in the background (auto-growing database)
"""

import asyncio
import re
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.poet import Poet
from app.models.poem import Poem
from app.models.verse import Verse
from app.models.category import Category, PoemCategory
from app.utils.arabic_normalizer import normalizer
from app.core.config import settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

QAFIYAH_BASE = "https://api.qafiyah.com"

ERA_MAP = {
    "جاهلي": "pre_islamic", "مخضرم": "islamic_early", "إسلامي": "islamic_early",
    "أموي": "umayyad", "عباسي": "abbasid", "أندلسي": "andalusian",
    "أيوبي": "abbasid", "مملوكي": "mamluk", "عثماني": "ottoman",
    "حديث": "modern", "معاصر": "contemporary",
}


class DiscoveryService:
    """Searches external poetry APIs and imports results into our DB."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def discover_and_save(
        self,
        query: str,
        limit: int = 20,
    ) -> dict:
        """
        Search external APIs, format results for immediate display,
        and save to DB in the background.

        Returns the same shape as SearchService.search_verses() so the
        router can merge results seamlessly.
        """
        external_hits = await self._search_qafiyah(query, limit)

        if not external_hits:
            return {"hits": [], "estimated_total_hits": 0, "mode": "discovery", "source": "none"}

        # Format for immediate response
        formatted_hits = []
        for hit in external_hits:
            verses = self._parse_snippet(hit.get("poem_snippet", ""))
            if not verses:
                continue

            h1, h2 = verses[0]
            formatted_hits.append({
                "id": f"ext-{hit.get('poem_slug', '')[:50]}",
                "full_verse": f"{h1} *** {h2}" if h2 else h1,
                "hemistich_1": h1,
                "hemistich_2": h2,
                "poet_name_ar": hit.get("poet_name", ""),
                "poet_slug": hit.get("poet_slug", ""),
                "poem_title_ar": hit.get("poem_title", ""),
                "poem_slug": hit.get("poem_slug", ""),
                "is_famous": False,
                "era": self._map_era(hit.get("poet_era", "")),
                "_source": "discovery",
                "_all_verses": verses,
            })

        # Save to DB in background (non-blocking, won't delay response)
        asyncio.create_task(self._save_to_db(external_hits))

        return {
            "hits": formatted_hits[:limit],
            "estimated_total_hits": len(formatted_hits),
            "mode": "discovery",
            "source": "qafiyah.com",
        }

    # ──────────────────────────────────────────────────────
    # External API search
    # ──────────────────────────────────────────────────────

    async def _search_qafiyah(self, query: str, limit: int = 20) -> list[dict]:
        """Search qafiyah.com API for poems matching the query."""
        results = []
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-platform/1.0)"},
            ) as client:
                # Search poems
                for page in range(1, 4):
                    r = await client.get(
                        f"{QAFIYAH_BASE}/search",
                        params={
                            "q": query,
                            "search_type": "poems",
                            "match_type": "any",
                            "page": page,
                        },
                    )
                    if r.status_code != 200:
                        break

                    data = r.json().get("data", {})
                    page_results = data.get("results", [])
                    if not page_results:
                        break

                    results.extend(page_results)

                    if len(results) >= limit or not data.get("pagination", {}).get("hasNextPage"):
                        break

                    await asyncio.sleep(0.2)

        except httpx.TimeoutException:
            logger.debug(f"Qafiyah API timeout for query: {query[:30]}")
        except Exception as e:
            logger.warning(f"Qafiyah API error: {e}")

        return results[:limit]

    # ──────────────────────────────────────────────────────
    # Background DB save
    # ──────────────────────────────────────────────────────

    async def _save_to_db(self, external_hits: list[dict]):
        """Save discovered poems to our DB using a fresh session."""
        try:
            async with AsyncSessionLocal() as session:
                try:
                    saved = 0
                    for hit in external_hits:
                        ok = await self._save_one_poem(session, hit)
                        if ok:
                            saved += 1

                    await session.commit()

                    if saved > 0:
                        logger.info(f"Discovery: saved {saved} new poems to DB")
                        await self._index_new_to_meilisearch(session, external_hits)

                except Exception as e:
                    await session.rollback()
                    logger.warning(f"Discovery DB save failed: {e}")

        except Exception as e:
            logger.warning(f"Discovery background task failed: {e}")

    async def _save_one_poem(self, session: AsyncSession, hit: dict) -> bool:
        """Save a single poem + verses. Returns True if saved, False if skipped."""
        poet_slug = hit.get("poet_slug", "")
        poet_name = hit.get("poet_name", "")
        poem_title = hit.get("poem_title", "")
        snippet = hit.get("poem_snippet", "")
        era_ar = hit.get("poet_era", "")

        if not poet_slug or not poem_title or not snippet:
            return False

        verses = self._parse_snippet(snippet)
        if not verses:
            return False

        # Check if poem already exists
        poem_slug = self._make_slug(f"{poet_slug}-{poem_title}")[:580]
        existing = (await session.execute(
            select(Poem.id).where(Poem.slug == poem_slug)
        )).scalar_one_or_none()
        if existing:
            return False

        # Get or create poet
        poet = (await session.execute(
            select(Poet).where(Poet.slug == poet_slug)
        )).scalar_one_or_none()

        if not poet:
            poet = Poet(
                name_ar=poet_name,
                slug=poet_slug,
                bio_ar=f"شاعر عربي من {era_ar}" if era_ar else "شاعر عربي",
                era=self._map_era(era_ar),
                nationality_ar="عربي",
                is_verified=True,
                poem_count=0,
                verse_count=0,
                metadata_={"source": "discovery"},
            )
            session.add(poet)
            await session.flush()

        # Create poem
        full_text = "\n".join(
            f"{h1} *** {h2}" if h2 else h1 for h1, h2 in verses
        )
        meter = hit.get("poem_meter", "") or None

        poem = Poem(
            poet_id=poet.id,
            title_ar=poem_title,
            slug=poem_slug,
            full_text=full_text,
            meter=meter,
            verse_count=len(verses),
            era=self._map_era(era_ar),
            is_verified=True,
            is_published=True,
            source="discovery:qafiyah.com",
        )
        session.add(poem)
        await session.flush()

        # Create verses
        for pos, (h1, h2) in enumerate(verses, 1):
            full_verse = f"{h1} *** {h2}" if h2 else h1
            session.add(Verse(
                poem_id=poem.id,
                poet_id=poet.id,
                position=pos,
                hemistich_1=h1,
                hemistich_2=h2 or None,
                full_verse=full_verse,
                full_verse_normalized=normalizer.normalize(full_verse),
                hemistich_1_normalized=normalizer.normalize(h1),
                hemistich_2_normalized=normalizer.normalize(h2) if h2 else None,
                poet_name_ar=poet_name,
                poet_slug=poet_slug,
                poem_title_ar=poem_title,
                poem_slug=poem_slug,
                is_famous=False,
            ))

        poet.poem_count = (poet.poem_count or 0) + 1
        poet.verse_count = (poet.verse_count or 0) + len(verses)
        return True

    async def _index_new_to_meilisearch(self, session: AsyncSession, hits: list[dict]):
        """Index newly saved poems to Meilisearch."""
        try:
            from meilisearch_python_sdk import AsyncClient

            slugs = []
            for h in hits:
                ps = h.get("poet_slug", "")
                pt = h.get("poem_title", "")
                if ps and pt:
                    slugs.append(self._make_slug(f"{ps}-{pt}")[:580])

            if not slugs:
                return

            result = await session.execute(
                select(Verse).where(Verse.poem_slug.in_(slugs))
            )
            new_verses = result.scalars().all()
            if not new_verses:
                return

            docs = [{
                "id": str(v.id), "full_verse": v.full_verse,
                "full_verse_normalized": v.full_verse_normalized or v.full_verse,
                "hemistich_1": v.hemistich_1, "hemistich_2": v.hemistich_2 or "",
                "hemistich_1_normalized": v.hemistich_1_normalized or v.hemistich_1,
                "hemistich_2_normalized": v.hemistich_2_normalized or "",
                "poet_name_ar": v.poet_name_ar or "", "poet_slug": v.poet_slug or "",
                "poem_title_ar": v.poem_title_ar or "", "poem_slug": v.poem_slug or "",
                "poet_id": str(v.poet_id), "poem_id": str(v.poem_id),
                "is_famous": v.is_famous, "view_count": v.view_count,
            } for v in new_verses]

            async with AsyncClient(
                url=settings.meilisearch_url, api_key=settings.meilisearch_key
            ) as client:
                index = client.index("verses")
                await index.add_documents(docs, primary_key="id")
                logger.info(f"Discovery: indexed {len(docs)} new verses to Meilisearch")

        except Exception as e:
            logger.debug(f"Discovery Meilisearch index failed: {e}")

    # ──────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_snippet(snippet: str) -> list[tuple[str, str]]:
        if not snippet:
            return []
        clean = re.sub(r"</?mark>", "", snippet)
        parts = [p.strip() for p in clean.split("*") if p.strip()]
        verses = []
        i = 0
        while i < len(parts):
            h1 = parts[i]
            h2 = parts[i + 1] if i + 1 < len(parts) else ""
            if len(h1) > 3:
                verses.append((h1, h2))
            i += 2
        if not verses:
            verses = [(p, "") for p in parts if len(p) > 3]
        return verses[:12]

    @staticmethod
    def _map_era(era_ar: str) -> str:
        if not era_ar:
            return "abbasid"
        for ar, slug in ERA_MAP.items():
            if ar in era_ar:
                return slug
        return "abbasid"

    @staticmethod
    def _make_slug(text: str) -> str:
        try:
            from unidecode import unidecode
            slug = re.sub(r"[^a-z0-9]+", "-", unidecode(text).lower()).strip("-")
        except ImportError:
            slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
        return slug[:200] or "poem"
