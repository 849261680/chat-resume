"""用于新增可复用 JD 表。"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "4d5e6f7a8b9c"
down_revision: Union[str, None] = "3c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """用于创建 job_posts 表和常用查询索引。"""
    op.create_table(
        "job_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False, server_default=""),
        sa.Column("job_title", sa.String(), nullable=False, server_default=""),
        sa.Column("jd_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False, server_default="resume"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_posts_id"), "job_posts", ["id"], unique=False)
    op.create_index(op.f("ix_job_posts_user_id"), "job_posts", ["user_id"], unique=False)
    op.create_index(
        "idx_job_posts_user_created",
        "job_posts",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """用于回滚 job_posts 表。"""
    op.drop_index("idx_job_posts_user_created", table_name="job_posts")
    op.drop_index(op.f("ix_job_posts_user_id"), table_name="job_posts")
    op.drop_index(op.f("ix_job_posts_id"), table_name="job_posts")
    op.drop_table("job_posts")
