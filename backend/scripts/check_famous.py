"""Check famous verses and sample verse format."""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def main():
    async with Session() as s:
        # Total famous
        total_famous = (await s.execute(text(
            "SELECT COUNT(*) FROM verses WHERE is_famous = true"
        ))).scalar()
        print(f"Total famous verses: {total_famous}")

        # Try known famous openings
        rows = (await s.execute(text("""
            SELECT full_verse, poet_name_ar, is_famous
            FROM verses
            WHERE full_verse LIKE '%قفا نبك%'
               OR full_verse LIKE '%أنا من أهوى%'
               OR full_verse LIKE '%ألا كل شيء%'
               OR full_verse LIKE '%أمن المنون%'
               OR full_verse LIKE '%على قدر أهل%'
               OR full_verse LIKE '%لا تحسبن المجد%'
               OR full_verse LIKE '%إذا الشعب يوما%'
               OR full_verse LIKE '%وقفت على ربع%'
            LIMIT 20
        """))).fetchall()
        print(f"\nWell-known verse search: {len(rows)} matches")
        for r in rows:
            print(f"  is_famous={r.is_famous}: {r.full_verse[:80]}")

        # Sample random verses — see separator format
        sample = (await s.execute(text(
            "SELECT full_verse, poet_name_ar FROM verses ORDER BY RANDOM() LIMIT 15"
        ))).fetchall()
        print("\nRandom verse samples:")
        for r in sample:
            print(f"  [{r.poet_name_ar}] {r.full_verse[:100]}")

        # Search using normalized text
        rows2 = (await s.execute(text("""
            SELECT full_verse_normalized, full_verse, is_famous
            FROM verses
            WHERE full_verse_normalized LIKE '%قفا نبك%'
               OR full_verse_normalized LIKE '%انا من اهوى%'
               OR full_verse_normalized LIKE '%على قدر اهل%'
            LIMIT 10
        """))).fetchall()
        print(f"\nNormalized search: {len(rows2)} matches")
        for r in rows2:
            print(f"  {r.full_verse[:80]}")

        # Poets sample
        poets = (await s.execute(text(
            "SELECT name_ar, poem_count, verse_count FROM poets ORDER BY verse_count DESC LIMIT 10"
        ))).fetchall()
        print("\nTop poets by verse count:")
        for p in poets:
            print(f"  {p.name_ar}: {p.poem_count} poems, {p.verse_count} verses")

asyncio.run(main())
