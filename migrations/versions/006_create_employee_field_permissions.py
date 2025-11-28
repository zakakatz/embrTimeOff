"""Create employee_field_permissions table.

Revision ID: 006
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create employee_field_permissions table with enums and constraints."""
    
    # Create enums
    field_category = postgresql.ENUM(
        "personal", "contact", "emergency", "employment", "compensation",
        "banking", "tax", "benefits", "performance", "documents", "custom",
        name="field_category",
    )
    field_category.create(op.get_bind())
    
    visibility_level = postgresql.ENUM(
        "hidden", "read_only", "read_write", "admin_only", "restricted",
        name="visibility_level",
    )
    visibility_level.create(op.get_bind())
    
    edit_permission_level = postgresql.ENUM(
        "no_edit", "self_edit", "manager_edit", "hr_edit", "admin_edit",
        name="edit_permission_level",
    )
    edit_permission_level.create(op.get_bind())
    
    view_permission_level = postgresql.ENUM(
        "no_view", "personal_only", "supervised", "public", "restricted",
        name="view_permission_level",
    )
    view_permission_level.create(op.get_bind())
    
    # Create table
    op.create_table(
        "employee_field_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Foreign keys
        sa.Column(
            "employee_id",
            sa.Integer,
            sa.ForeignKey("employee.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile_field_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Field identification
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_category", field_category, nullable=False),
        # Permission levels
        sa.Column("visibility_level", visibility_level, nullable=False, server_default="read_only"),
        sa.Column("edit_permission_level", edit_permission_level, nullable=False, server_default="no_edit"),
        sa.Column("view_permission_level", view_permission_level, nullable=False, server_default="personal_only"),
        # Approval workflow
        sa.Column("approval_chain_json", postgresql.JSONB, nullable=True),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("approval_levels", sa.Integer, nullable=False, server_default="1"),
        # Time-based permissions
        sa.Column("effective_date", sa.Date, nullable=False, server_default=sa.func.current_date()),
        sa.Column("expire_date", sa.Date, nullable=True),
        sa.Column("validity_range", postgresql.DATERANGE, nullable=True),
        # Permission review tracking
        sa.Column("permission_review_cycle_days", sa.Integer, nullable=False, server_default="365"),
        sa.Column("last_permission_review", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_date", sa.Date, nullable=True),
        sa.Column(
            "reviewed_by_id",
            sa.Integer,
            sa.ForeignKey("employee.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Audit and tracking
        sa.Column("audit_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("exception_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("exception_notes", sa.Text, nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_inherited", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("inheritance_source", sa.String(100), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "granted_by_id",
            sa.Integer,
            sa.ForeignKey("employee.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Constraints
        sa.CheckConstraint("permission_review_cycle_days >= 30", name="ck_field_permission_review_cycle_min"),
        sa.CheckConstraint("exception_count >= 0", name="ck_field_permission_exception_count_min"),
        sa.CheckConstraint("approval_levels >= 1", name="ck_field_permission_approval_levels_min"),
        sa.UniqueConstraint("employee_id", "field_name", "field_category", name="uq_employee_field_permission"),
    )
    
    # Create indexes
    op.create_index("ix_employee_field_permissions_employee_id", "employee_field_permissions", ["employee_id"])
    op.create_index("ix_employee_field_permissions_profile_field_id", "employee_field_permissions", ["profile_field_id"])
    op.create_index("ix_employee_field_permissions_field_name", "employee_field_permissions", ["field_name"])
    op.create_index("ix_employee_field_permissions_field_category", "employee_field_permissions", ["field_category"])
    op.create_index("ix_field_permission_employee_category", "employee_field_permissions", ["employee_id", "field_category"])
    op.create_index("ix_field_permission_employee_active", "employee_field_permissions", ["employee_id", "is_active"])
    op.create_index("ix_field_permission_review_date", "employee_field_permissions", ["next_review_date"])


def downgrade() -> None:
    """Drop employee_field_permissions table and enums."""
    
    # Drop indexes
    op.drop_index("ix_field_permission_review_date", table_name="employee_field_permissions")
    op.drop_index("ix_field_permission_employee_active", table_name="employee_field_permissions")
    op.drop_index("ix_field_permission_employee_category", table_name="employee_field_permissions")
    op.drop_index("ix_employee_field_permissions_field_category", table_name="employee_field_permissions")
    op.drop_index("ix_employee_field_permissions_field_name", table_name="employee_field_permissions")
    op.drop_index("ix_employee_field_permissions_profile_field_id", table_name="employee_field_permissions")
    op.drop_index("ix_employee_field_permissions_employee_id", table_name="employee_field_permissions")
    
    # Drop table
    op.drop_table("employee_field_permissions")
    
    # Drop enums
    sa.Enum(name="view_permission_level").drop(op.get_bind())
    sa.Enum(name="edit_permission_level").drop(op.get_bind())
    sa.Enum(name="visibility_level").drop(op.get_bind())
    sa.Enum(name="field_category").drop(op.get_bind())

