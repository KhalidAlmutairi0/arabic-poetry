"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pgvector extension ────────────────────────────────────────────────────
    # Use a DO block so the error is caught inside PostgreSQL (no transaction abort)
    op.execute("""
        DO $$
        BEGIN
            CREATE EXTENSION IF NOT EXISTS vector;
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING 'pgvector extension not available - vector search disabled';
        END
        $$
    """)

    # ── poets ─────────────────────────────────────────────────────────────────
    op.create_table(
        "poets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name_ar", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200)),
        sa.Column("slug", sa.String(300), nullable=False, unique=True),
        sa.Column("bio_ar", sa.Text),
        sa.Column("bio_en", sa.Text),
        sa.Column("era", sa.String(50)),
        sa.Column("birth_year", sa.Integer),
        sa.Column("death_year", sa.Integer),
        sa.Column("birth_place_ar", sa.String(200)),
        sa.Column("nationality_ar", sa.String(100)),
        sa.Column("image_url", sa.String(500)),
        sa.Column("poem_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("verse_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("metadata", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_poets_slug", "poets", ["slug"])
    op.create_index("ix_poets_era", "poets", ["era"])

    # ── poems ─────────────────────────────────────────────────────────────────
    op.create_table(
        "poems",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("poet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("poets.id"), nullable=False),
        sa.Column("title_ar", sa.String(500), nullable=False),
        sa.Column("title_en", sa.String(500)),
        sa.Column("slug", sa.String(600), nullable=False, unique=True),
        sa.Column("full_text", sa.Text),
        sa.Column("meter", sa.String(100)),
        sa.Column("rhyme_char", sa.String(10)),
        sa.Column("verse_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("era", sa.String(50)),
        sa.Column("source", sa.String(500)),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("view_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_poems_slug", "poems", ["slug"])
    op.create_index("ix_poems_poet_id", "poems", ["poet_id"])

    # ── verses ────────────────────────────────────────────────────────────────
    op.create_table(
        "verses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("poem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("poems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("poet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("poets.id"), nullable=False),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.Column("hemistich_1", sa.Text, nullable=False),
        sa.Column("hemistich_2", sa.Text),
        sa.Column("full_verse", sa.Text, nullable=False),
        sa.Column("hemistich_1_normalized", sa.Text),
        sa.Column("hemistich_2_normalized", sa.Text),
        sa.Column("full_verse_normalized", sa.Text),
        # Denormalized fields
        sa.Column("poet_name_ar", sa.String(200)),
        sa.Column("poet_slug", sa.String(300)),
        sa.Column("poem_title_ar", sa.String(500)),
        sa.Column("poem_slug", sa.String(600)),
        sa.Column("is_famous", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("view_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("share_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_verses_poem_id", "verses", ["poem_id"])
    op.create_index("ix_verses_poet_id", "verses", ["poet_id"])
    op.create_index("ix_verses_is_famous", "verses", ["is_famous"])
    op.create_index("ix_verses_hemistich_1_normalized", "verses", ["hemistich_1_normalized"])
    op.create_index("ix_verses_full_verse_normalized", "verses", ["full_verse_normalized"])

    # ── verse_explanations ────────────────────────────────────────────────────
    op.create_table(
        "verse_explanations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("verse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("verses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("explanation_type", sa.String(20), nullable=False),
        sa.Column("explanation_ar", sa.Text, nullable=False),
        sa.Column("explanation_en", sa.Text),
        sa.Column("difficult_words", postgresql.JSON),
        sa.Column("literary_devices", postgresql.JSON),
        sa.Column("generated_by", sa.String(100)),
        sa.Column("is_ai_generated", sa.Boolean, server_default="true"),
        sa.Column("is_reviewed", sa.Boolean, server_default="false"),
        sa.Column("quality_score", sa.SmallInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("verse_id", "explanation_type", name="uq_verse_explanation_type"),
    )
    op.create_index("ix_verse_explanations_verse_id", "verse_explanations", ["verse_id"])

    # ── categories ────────────────────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name_ar", sa.String(100), nullable=False, unique=True),
        sa.Column("name_en", sa.String(100)),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description_ar", sa.Text),
        sa.Column("icon", sa.String(50)),
        sa.Column("color", sa.String(7)),
        sa.Column("display_order", sa.SmallInteger, server_default="0"),
        sa.Column("poem_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"])

    # ── poem_categories ───────────────────────────────────────────────────────
    op.create_table(
        "poem_categories",
        sa.Column("poem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("poems.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("is_ai_tagged", sa.Boolean, server_default="false"),
    )

    # ── embeddings ────────────────────────────────────────────────────────────
    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("vector", sa.Text),   # stored as JSON string until pgvector extension is applied
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_embeddings_entity", "embeddings", ["entity_type", "entity_id"])

    # ── verse_relations ───────────────────────────────────────────────────────
    op.create_table(
        "verse_relations",
        sa.Column("verse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("verses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("related_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("verses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("similarity", sa.Float, nullable=False),
        sa.Column("relation_type", sa.String(30), server_default="semantic"),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("role", sa.String(20), server_default="reader"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── favorites ─────────────────────────────────────────────────────────────
    op.create_table(
        "favorites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])


def downgrade() -> None:
    op.drop_table("favorites")
    op.drop_table("users")
    op.drop_table("verse_relations")
    op.drop_table("embeddings")
    op.drop_table("poem_categories")
    op.drop_table("categories")
    op.drop_table("verse_explanations")
    op.drop_table("verses")
    op.drop_table("poems")
    op.drop_table("poets")
    op.execute("DROP EXTENSION IF EXISTS vector")
