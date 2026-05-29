"""
AI Service — wraps Ollama + Qwen 2.5 for:
- Verse embeddings (semantic search)
- Verse explanations (streaming)
- Poem categorization
"""

import httpx
import json
import logging
from typing import AsyncGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.base_url = settings.ollama_url
        self.model_chat = settings.ollama_model_chat
        self.model_embed = settings.ollama_model_embed

    # ──────────────────────────────────────────────────
    # EMBEDDINGS
    # ──────────────────────────────────────────────────

    async def embed_text(self, text: str, timeout: float = 30.0) -> list[float] | None:
        """Generate embedding vector for text.

        Pass timeout=3.0 for search queries to fail fast and fall back to
        keyword-only mode when the embedding model is slow.
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model_embed, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embedding")
        except httpx.TimeoutException:
            logger.debug("Ollama embedding timeout — falling back to keyword search")
            return None
        except Exception as e:
            logger.debug(f"Embedding unavailable: {e}")
            return None

    async def embed_verse(self, verse: dict) -> list[float] | None:
        """
        Embed verse with poetic context for better semantic quality.
        Context matters: same word can mean different things in different poems.
        """
        context_text = (
            f"بيت شعري للشاعر {verse.get('poet_name_ar', '')} "
            f"من قصيدة {verse.get('poem_title_ar', '')}:\n"
            f"{verse['full_verse']}"
        ).strip()
        return await self.embed_text(context_text)

    # ──────────────────────────────────────────────────
    # VERSE EXPLANATION (Streaming)
    # ──────────────────────────────────────────────────

    async def explain_verse_stream(
        self,
        verse: dict,
        explanation_type: str = "simple",
    ) -> AsyncGenerator[str, None]:
        """Stream AI explanation — yields text chunks as they arrive."""

        system_prompt = self._system_prompt(explanation_type)
        user_prompt = self._build_explanation_prompt(verse, explanation_type)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model_chat,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": True,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.9,
                            "num_ctx": 4096,
                        },
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                if not chunk.get("done"):
                                    content = chunk.get("message", {}).get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
        except httpx.TimeoutException:
            logger.warning("Ollama timeout — using rule-based fallback")
            async for chunk in self._rule_based_explanation(verse, explanation_type):
                yield chunk
        except Exception as e:
            logger.warning(f"Ollama unavailable ({e}) — using rule-based fallback")
            async for chunk in self._rule_based_explanation(verse, explanation_type):
                yield chunk

    async def explain_verse_full(
        self,
        verse: dict,
        explanation_type: str = "simple",
    ) -> str:
        """Get full explanation (non-streaming) — for batch processing."""
        chunks = []
        async for chunk in self.explain_verse_stream(verse, explanation_type):
            chunks.append(chunk)
        return "".join(chunks)

    # ──────────────────────────────────────────────────
    # AUTO-CATEGORIZATION
    # ──────────────────────────────────────────────────

    async def classify_categories(
        self,
        poem_text: str,
        available_categories: list[str],
    ) -> dict:
        """Use AI to tag poem with categories."""
        cats_str = "، ".join(available_categories)
        prompt = f"""حدد أقسام هذه القصيدة من القائمة التالية فقط: {cats_str}

نص القصيدة (أول 500 حرف):
{poem_text[:500]}

أجب بتنسيق JSON فقط بدون أي نص إضافي:
{{"categories": ["القسم1", "القسم2"], "confidence": [0.9, 0.7]}}"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model_chat,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.1},
                    },
                )
                result = response.json()
                content = result.get("message", {}).get("content", "{}")
                return json.loads(content)
        except Exception as e:
            logger.error(f"Category classification error: {e}")
            return {"categories": [], "confidence": []}

    # ──────────────────────────────────────────────────
    # RULE-BASED FALLBACK (when Ollama is unavailable)
    # ──────────────────────────────────────────────────

    async def _rule_based_explanation(
        self,
        verse: dict,
        explanation_type: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a basic structural explanation without AI.
        Used when Ollama is not available.
        Streams chunks the same way as the AI path.
        """
        import asyncio

        poet = verse.get("poet_name_ar", "الشاعر")
        poem = verse.get("poem_title_ar", "القصيدة")
        full = verse.get("full_verse", "")

        # Split into hemistiches
        parts = [p.strip() for p in full.replace("***", "—").split("—") if p.strip()]
        h1 = parts[0] if parts else full
        h2 = parts[1] if len(parts) > 1 else ""

        if explanation_type == "simple":
            text = (
                f"هذا البيت الشعري للشاعر **{poet}**"
                + (f" من قصيدة «{poem}»" if poem and poem != "غير محدد" else "")
                + ".\n\n"
            )
            if h2:
                text += f"يتألف البيت من شطرين:\n- الصدر: «{h1}»\n- العجز: «{h2}»\n\n"
            text += (
                "يُعبّر الشاعر في هذا البيت عن فكرة شعرية عميقة تجمع بين جمال الصياغة "
                "ودقة المعنى، وهو نموذج رائع على البلاغة العربية الأصيلة.\n\n"
                "*ملاحظة: الشرح التفصيلي بالذكاء الاصطناعي سيُتاح قريباً.*"
            )
        elif explanation_type == "literary":
            text = (
                f"**التحليل الأدبي** — {poet}"
                + (f" · «{poem}»" if poem and poem != "غير محدد" else "")
                + "\n\n"
                f"**النص:** {full}\n\n"
                "**الصورة الشعرية:** يعتمد الشاعر على إيحاءات لغوية غنية تحمل أبعاداً دلالية متعددة.\n\n"
                "**الأسلوب:** يمتاز البيت بجزالة الألفاظ وانسجام الإيقاع مع المعنى.\n\n"
                "*ملاحظة: التحليل الأدبي المفصّل بالذكاء الاصطناعي سيُتاح قريباً.*"
            )
        else:  # linguistic
            text = (
                f"**التحليل اللغوي** — {poet}\n\n"
                f"**البيت:** {full}\n\n"
                "**المفردات:** تحمل ألفاظ هذا البيت جذوراً عربية أصيلة تعكس ثراء المعجم الشعري.\n\n"
                "**التراكيب:** يُوظّف الشاعر تراكيب نحوية رفيعة تُضفي على البيت طابعاً بلاغياً مميزاً.\n\n"
                "*ملاحظة: التحليل اللغوي المفصّل بالذكاء الاصطناعي سيُتاح قريباً.*"
            )

        # Stream in chunks to mimic real streaming
        chunk_size = 60
        for i in range(0, len(text), chunk_size):
            yield text[i: i + chunk_size]
            await asyncio.sleep(0.02)  # small delay so the UI animates

    # ──────────────────────────────────────────────────
    # HEALTH CHECK
    # ──────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    # ──────────────────────────────────────────────────
    # PROMPTS
    # ──────────────────────────────────────────────────

    def _system_prompt(self, explanation_type: str) -> str:
        prompts = {
            "simple": (
                "أنت خبير في الأدب العربي الكلاسيكي. مهمتك شرح أبيات الشعر العربي "
                "بأسلوب واضح ومبسط يناسب القارئ العام.\n"
                "اجعل الشرح:\n"
                "- موجزاً (100-150 كلمة)\n"
                "- بعيداً عن المصطلحات التقنية المعقدة\n"
                "- مركزاً على المعنى والجمالية\n"
                "- بالعربية الفصحى البسيطة\n"
                "- ابدأ مباشرة بالشرح بدون مقدمات"
            ),
            "literary": (
                "أنت ناقد أدبي متخصص في الشعر العربي الكلاسيكي والحديث.\n"
                "قدم تحليلاً أدبياً للبيت يشمل:\n"
                "- الصورة الشعرية والأساليب البلاغية (تشبيه، استعارة، كناية...)\n"
                "- الموسيقى الداخلية والإيقاع الشعري\n"
                "- المعنى العميق والدلالات الرمزية\n"
                "- الترابط مع سياق القصيدة\n"
                "أجب بالعربية الفصحى الأكاديمية المقروءة"
            ),
            "linguistic": (
                "أنت لغوي متخصص في العربية الكلاسيكية.\n"
                "حلل البيت لغوياً وأجب بهيكل واضح:\n"
                "1. شرح الكلمات الصعبة مع جذورها الثلاثية\n"
                "2. توضيح التراكيب الصعبة والإعراب المشكل\n"
                "3. الفروق الدلالية بين المفردات\n"
                "4. استخدامات مشابهة في الشعر الكلاسيكي إن وجدت"
            ),
        }
        return prompts.get(explanation_type, prompts["simple"])

    def _build_explanation_prompt(self, verse: dict, explanation_type: str) -> str:
        era_labels = {
            "pre_islamic": "الجاهلية", "umayyad": "الأموي",
            "abbasid": "العباسي", "modern": "الحديث",
            "contemporary": "المعاصر", "andalusian": "الأندلسي",
        }
        era = era_labels.get(verse.get("era", ""), verse.get("era", "غير محدد"))

        return (
            f"البيت الشعري:\n{verse['full_verse']}\n\n"
            f"الشاعر: {verse.get('poet_name_ar', 'غير محدد')}\n"
            f"القصيدة: {verse.get('poem_title_ar', 'غير محدد')}\n"
            f"العصر: {era}"
        )
