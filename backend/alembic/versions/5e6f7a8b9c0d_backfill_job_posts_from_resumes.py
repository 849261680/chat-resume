"""用于把旧简历内嵌 JD 回填到 job_posts。"""

from __future__ import annotations

import json
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "5e6f7a8b9c0d"
down_revision: Union[str, None] = "4d5e6f7a8b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _resume_table() -> sa.Table:
    """用于声明迁移所需的 resumes 表字段。"""
    return sa.Table(
        "resumes",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer()),
        sa.Column("content", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def _job_post_table() -> sa.Table:
    """用于声明迁移所需的 job_posts 表字段。"""
    return sa.Table(
        "job_posts",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer()),
        sa.Column("company_name", sa.String()),
        sa.Column("job_title", sa.String()),
        sa.Column("jd_text", sa.Text()),
        sa.Column("source_url", sa.String()),
        sa.Column("source_type", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def _json_content(value: Any) -> dict[str, Any]:
    """用于把数据库 JSON 内容收窄成可修改字典。"""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _job_application(content: dict[str, Any]) -> dict[str, Any]:
    """用于读取简历内容中的求职目标对象。"""
    value = content.get("job_application")
    return dict(value) if isinstance(value, dict) else {}


def _backfill_existing_resume_jds(connection: sa.Connection) -> int:
    """用于把没有 job_post_id 的旧简历 JD 写入 job_posts。"""
    resumes = _resume_table()
    job_posts = _job_post_table()
    rows = connection.execute(
        sa.select(
            resumes.c.id,
            resumes.c.owner_id,
            resumes.c.content,
            resumes.c.created_at,
            resumes.c.updated_at,
        )
    ).mappings()
    inserted = 0
    for row in rows:
        content = _json_content(row["content"])
        job_application = _job_application(content)
        if job_application.get("job_post_id"):
            continue

        jd_text = str(job_application.get("jd_text") or "").strip()
        if not jd_text:
            continue

        company_name = str(job_application.get("target_company") or "").strip()
        job_title = str(job_application.get("target_title") or "").strip()
        job_post_id = _find_existing_backfill_job_post(
            connection,
            user_id=int(row["owner_id"]),
            company_name=company_name,
            job_title=job_title,
            jd_text=jd_text,
        )
        if job_post_id is None:
            result = connection.execute(
                job_posts.insert().values(
                    user_id=row["owner_id"],
                    company_name=company_name,
                    job_title=job_title,
                    jd_text=jd_text,
                    source_url=None,
                    source_type="resume_backfill",
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
            job_post_id = int(result.inserted_primary_key[0])
            inserted += 1

        job_application["job_post_id"] = job_post_id
        content["job_application"] = job_application
        connection.execute(
            resumes.update()
            .where(resumes.c.id == row["id"])
            .values(content=content)
        )
    return inserted


def _find_existing_backfill_job_post(
    connection: sa.Connection,
    *,
    user_id: int,
    company_name: str,
    job_title: str,
    jd_text: str,
) -> int | None:
    """用于复用中断迁移留下的同一条回填 JD。"""
    job_posts = _job_post_table()
    row = connection.execute(
        sa.select(job_posts.c.id)
        .where(job_posts.c.user_id == user_id)
        .where(job_posts.c.company_name == company_name)
        .where(job_posts.c.job_title == job_title)
        .where(job_posts.c.jd_text == jd_text)
        .where(job_posts.c.source_type == "resume_backfill")
        .limit(1)
    ).first()
    return int(row[0]) if row is not None else None


def _remove_backfilled_job_post_links(connection: sa.Connection) -> None:
    """用于回滚回填 JD 与简历 JSON 的关联。"""
    resumes = _resume_table()
    job_posts = _job_post_table()
    ids = {
        row["id"]
        for row in connection.execute(
            sa.select(job_posts.c.id).where(job_posts.c.source_type == "resume_backfill")
        ).mappings()
    }
    if not ids:
        return

    rows = connection.execute(
        sa.select(resumes.c.id, resumes.c.content)
    ).mappings()
    for row in rows:
        content = _json_content(row["content"])
        job_application = _job_application(content)
        if job_application.get("job_post_id") not in ids:
            continue
        job_application.pop("job_post_id", None)
        content["job_application"] = job_application
        connection.execute(
            resumes.update()
            .where(resumes.c.id == row["id"])
            .values(content=content)
        )

    connection.execute(job_posts.delete().where(job_posts.c.id.in_(ids)))


def upgrade() -> None:
    """用于执行旧 JD 回填。"""
    _backfill_existing_resume_jds(op.get_bind())


def downgrade() -> None:
    """用于撤销本迁移回填的 JD 记录。"""
    _remove_backfilled_job_post_links(op.get_bind())
