"""Employee Directory View and optimized indexes for directory queries.

This module defines:
1. EmployeeDirectoryView - A database view joining Employee, Department, Location 
   tables with manager information for efficient directory queries
2. Optimized indexes for full-text search, organizational hierarchy queries,
   and filtered queries on active employees
"""

from sqlalchemy import (
    Column,
    Index,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import DDL
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Executable, ClauseElement

from src.models.base import Base


# =============================================================================
# Custom DDL for PostgreSQL-specific features
# =============================================================================

class CreateMaterializedView(Executable, ClauseElement):
    """DDL element for creating materialized views."""
    inherit_cache = True
    
    def __init__(self, name, selectable, with_data=True):
        self.name = name
        self.selectable = selectable
        self.with_data = with_data


class DropMaterializedView(Executable, ClauseElement):
    """DDL element for dropping materialized views."""
    inherit_cache = True
    
    def __init__(self, name, if_exists=True):
        self.name = name
        self.if_exists = if_exists


@compiles(CreateMaterializedView)
def compile_create_materialized_view(element, compiler, **kw):
    with_data = "WITH DATA" if element.with_data else "WITH NO DATA"
    return f"CREATE MATERIALIZED VIEW IF NOT EXISTS {element.name} AS {element.selectable} {with_data}"


@compiles(DropMaterializedView)
def compile_drop_materialized_view(element, compiler, **kw):
    if_exists = "IF EXISTS " if element.if_exists else ""
    return f"DROP MATERIALIZED VIEW {if_exists}{element.name}"


# =============================================================================
# Employee Directory View Definition (SQL)
# =============================================================================

EMPLOYEE_DIRECTORY_VIEW_SQL = """
CREATE OR REPLACE VIEW employee_directory_view AS
SELECT 
    -- Employee Core Fields
    e.id,
    e.employee_id,
    e.email,
    e.first_name,
    e.middle_name,
    e.last_name,
    e.preferred_name,
    COALESCE(e.preferred_name, e.first_name) AS display_first_name,
    CONCAT(COALESCE(e.preferred_name, e.first_name), ' ', e.last_name) AS full_name,
    e.job_title,
    e.employment_status,
    e.employment_type,
    e.hire_date,
    e.phone_number,
    e.is_active,
    
    -- Department Information
    e.department_id,
    d.name AS department_name,
    d.code AS department_code,
    
    -- Location Information
    e.location_id,
    l.name AS location_name,
    l.code AS location_code,
    l.city AS location_city,
    l.country AS location_country,
    l.timezone AS location_timezone,
    
    -- Manager Information
    e.manager_id,
    m.employee_id AS manager_employee_id,
    m.email AS manager_email,
    CONCAT(COALESCE(m.preferred_name, m.first_name), ' ', m.last_name) AS manager_name,
    m.job_title AS manager_job_title,
    
    -- Computed Search Field (for full-text search optimization)
    LOWER(
        CONCAT_WS(' ',
            e.first_name,
            e.last_name,
            e.preferred_name,
            e.email,
            e.job_title,
            d.name,
            l.name
        )
    ) AS search_text,
    
    -- Timestamps
    e.created_at,
    e.updated_at
    
FROM employee e
LEFT JOIN department d ON e.department_id = d.id AND d.is_active = true
LEFT JOIN location l ON e.location_id = l.id AND l.is_active = true
LEFT JOIN employee m ON e.manager_id = m.id AND m.is_active = true
WHERE e.is_active = true;
"""

DROP_EMPLOYEE_DIRECTORY_VIEW_SQL = """
DROP VIEW IF EXISTS employee_directory_view;
"""


# =============================================================================
# Index Definitions
# =============================================================================

# Full-text search index using PostgreSQL GIN
FULLTEXT_SEARCH_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_employee_fulltext_search 
ON employee 
USING GIN (
    to_tsvector('english', 
        COALESCE(first_name, '') || ' ' || 
        COALESCE(last_name, '') || ' ' || 
        COALESCE(preferred_name, '') || ' ' ||
        COALESCE(job_title, '') || ' ' ||
        COALESCE(email, '')
    )
);
"""

# Composite index for organizational hierarchy queries
HIERARCHY_COMPOSITE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_employee_org_hierarchy 
ON employee (manager_id, department_id, employment_status)
WHERE is_active = true;
"""

# Filtered index for department-based queries on active employees
DEPARTMENT_FILTERED_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_employee_department_active 
ON employee (department_id, last_name, first_name)
WHERE is_active = true;
"""

# Filtered index for location-based queries on active employees
LOCATION_FILTERED_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_employee_location_active 
ON employee (location_id, last_name, first_name)
WHERE is_active = true;
"""

# Index for manager lookup with active filter
MANAGER_LOOKUP_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_employee_manager_lookup 
ON employee (manager_id)
INCLUDE (id, employee_id, first_name, last_name, job_title)
WHERE is_active = true;
"""

# Index for employment status filtering
EMPLOYMENT_STATUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_employee_employment_status 
ON employee (employment_status, employment_type)
WHERE is_active = true;
"""

# Index for hire date range queries
HIRE_DATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_employee_hire_date 
ON employee (hire_date DESC)
WHERE is_active = true;
"""


# =============================================================================
# Combined DDL for all database objects
# =============================================================================

ALL_DIRECTORY_DDL = [
    # Create view
    EMPLOYEE_DIRECTORY_VIEW_SQL,
    # Create indexes
    FULLTEXT_SEARCH_INDEX_SQL,
    HIERARCHY_COMPOSITE_INDEX_SQL,
    DEPARTMENT_FILTERED_INDEX_SQL,
    LOCATION_FILTERED_INDEX_SQL,
    MANAGER_LOOKUP_INDEX_SQL,
    EMPLOYMENT_STATUS_INDEX_SQL,
    HIRE_DATE_INDEX_SQL,
]

DROP_DIRECTORY_DDL = [
    DROP_EMPLOYEE_DIRECTORY_VIEW_SQL,
    "DROP INDEX IF EXISTS idx_employee_fulltext_search;",
    "DROP INDEX IF EXISTS idx_employee_org_hierarchy;",
    "DROP INDEX IF EXISTS idx_employee_department_active;",
    "DROP INDEX IF EXISTS idx_employee_location_active;",
    "DROP INDEX IF EXISTS idx_employee_manager_lookup;",
    "DROP INDEX IF EXISTS idx_employee_employment_status;",
    "DROP INDEX IF EXISTS idx_employee_hire_date;",
]


# =============================================================================
# SQLAlchemy Model for Read-Only View Access
# =============================================================================

class EmployeeDirectoryView(Base):
    """
    SQLAlchemy model representing the employee_directory_view.
    
    This is a read-only model that maps to the database view for
    querying employee directory data efficiently.
    
    Note: This model should NOT be used for inserts, updates, or deletes.
    """
    
    __tablename__ = "employee_directory_view"
    __table_args__ = {"info": {"is_view": True}}
    
    # Primary identifier
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255))
    
    # Name fields
    first_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100))
    preferred_name: Mapped[str] = mapped_column(String(100), nullable=True)
    display_first_name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(255))
    
    # Employment info
    job_title: Mapped[str] = mapped_column(String(100), nullable=True)
    employment_status: Mapped[str] = mapped_column(String(50))
    employment_type: Mapped[str] = mapped_column(String(50), nullable=True)
    hire_date: Mapped[Date] = mapped_column(Date)
    phone_number: Mapped[str] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean)
    
    # Department info
    department_id: Mapped[int] = mapped_column(Integer, nullable=True)
    department_name: Mapped[str] = mapped_column(String(100), nullable=True)
    department_code: Mapped[str] = mapped_column(String(20), nullable=True)
    
    # Location info
    location_id: Mapped[int] = mapped_column(Integer, nullable=True)
    location_name: Mapped[str] = mapped_column(String(100), nullable=True)
    location_code: Mapped[str] = mapped_column(String(20), nullable=True)
    location_city: Mapped[str] = mapped_column(String(100), nullable=True)
    location_country: Mapped[str] = mapped_column(String(100), nullable=True)
    location_timezone: Mapped[str] = mapped_column(String(50), nullable=True)
    
    # Manager info
    manager_id: Mapped[int] = mapped_column(Integer, nullable=True)
    manager_employee_id: Mapped[str] = mapped_column(String(20), nullable=True)
    manager_email: Mapped[str] = mapped_column(String(255), nullable=True)
    manager_name: Mapped[str] = mapped_column(String(255), nullable=True)
    manager_job_title: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # Search text
    search_text: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    
    def __repr__(self) -> str:
        return (
            f"<EmployeeDirectoryView("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"name={self.full_name}"
            f")>"
        )


# =============================================================================
# Database Setup Functions
# =============================================================================

def create_directory_view_and_indexes(engine) -> None:
    """
    Create the employee directory view and all optimized indexes.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    from sqlalchemy import text
    
    with engine.connect() as conn:
        for ddl in ALL_DIRECTORY_DDL:
            try:
                conn.execute(text(ddl))
            except Exception as e:
                print(f"Warning: DDL execution failed: {e}")
        conn.commit()


def drop_directory_view_and_indexes(engine) -> None:
    """
    Drop the employee directory view and all related indexes.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    from sqlalchemy import text
    
    with engine.connect() as conn:
        for ddl in DROP_DIRECTORY_DDL:
            try:
                conn.execute(text(ddl))
            except Exception as e:
                print(f"Warning: DDL drop failed: {e}")
        conn.commit()


def refresh_directory_indexes(engine) -> None:
    """
    Reindex the directory indexes for optimal performance.
    
    Should be run periodically as part of maintenance.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    from sqlalchemy import text
    
    reindex_commands = [
        "REINDEX INDEX CONCURRENTLY idx_employee_fulltext_search;",
        "REINDEX INDEX CONCURRENTLY idx_employee_org_hierarchy;",
        "REINDEX INDEX CONCURRENTLY idx_employee_department_active;",
        "REINDEX INDEX CONCURRENTLY idx_employee_location_active;",
    ]
    
    with engine.connect() as conn:
        for cmd in reindex_commands:
            try:
                conn.execute(text(cmd))
            except Exception as e:
                print(f"Warning: Reindex failed: {e}")
        conn.commit()

