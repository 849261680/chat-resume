"""用于覆盖旧 JD 回填到 job_posts 的 Alembic 迁移。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa


def _load_migration_module() -> ModuleType:
    """用于从迁移文件路径加载回填模块。"""
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "5e6f7a8b9c0d_backfill_job_posts_from_resumes.py"
    )
    spec = importlib.util.spec_from_file_location("job_posts_backfill_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata() -> sa.MetaData:
    """用于声明迁移测试需要的最小数据库结构。"""
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        "resumes",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    sa.Table(
        "job_posts",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False, default=""),
        sa.Column("job_title", sa.String(), nullable=False, default=""),
        sa.Column("jd_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    return metadata


def test_backfill_existing_resume_jds_creates_job_posts_and_links_resume():
    """用于验证旧简历 JD 会被迁移到 job_posts 并写回 job_post_id。"""
    migration = _load_migration_module()
    engine = sa.create_engine("sqlite://")
    metadata = _metadata()
    metadata.create_all(engine)
    resumes = metadata.tables["resumes"]
    job_posts = metadata.tables["job_posts"]

    with engine.begin() as connection:
        connection.execute(
            resumes.insert().values(
                id=1,
                owner_id=7,
                content={
                    "job_application": {
                        "target_company": "美团",
                        "target_title": "Agent 开发工程师",
                        "jd_text": "负责 Agent 工具调用和评测体系。",
                    }
                },
            )
        )

        inserted = migration._backfill_existing_resume_jds(connection)

        assert inserted == 1
        job_post = connection.execute(sa.select(job_posts)).mappings().one()
        resume = connection.execute(sa.select(resumes)).mappings().one()

    assert job_post["user_id"] == 7
    assert job_post["company_name"] == "美团"
    assert job_post["job_title"] == "Agent 开发工程师"
    assert "评测体系" in job_post["jd_text"]
    assert job_post["source_type"] == "resume_backfill"
    assert resume["content"]["job_application"]["job_post_id"] == job_post["id"]


def test_backfill_existing_resume_jds_skips_already_linked_resume():
    """用于验证已有 job_post_id 的简历不会重复生成 JD。"""
    migration = _load_migration_module()
    engine = sa.create_engine("sqlite://")
    metadata = _metadata()
    metadata.create_all(engine)
    resumes = metadata.tables["resumes"]
    job_posts = metadata.tables["job_posts"]

    with engine.begin() as connection:
        connection.execute(
            resumes.insert().values(
                id=1,
                owner_id=7,
                content={
                    "job_application": {
                        "job_post_id": 99,
                        "jd_text": "旧 JD",
                    }
                },
            )
        )

        inserted = migration._backfill_existing_resume_jds(connection)
        count = connection.execute(
            sa.select(sa.func.count()).select_from(job_posts)
        ).scalar_one()

    assert inserted == 0
    assert count == 0
