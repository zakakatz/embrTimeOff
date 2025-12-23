"""
Database Migration: Employee Directory Views and Indexes

This migration creates:
1. employee_directory_view - Optimized view for directory queries
2. Full-text search index using PostgreSQL GIN
3. Composite indexes for organizational hierarchy queries
4. Filtered indexes for department and location-based queries

Run this migration after the base Employee, Department, and Location tables exist.
"""

import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# =============================================================================
# Migration Version
# =============================================================================

MIGRATION_VERSION = "001"
MIGRATION_NAME = "employee_directory_views"


# =============================================================================
# Upgrade SQL Statements
# =============================================================================

UPGRADE_STATEMENTS = [
    # =========================================================================
    # 1. Create Employee Directory View
    # =========================================================================
    """
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
        
        -- Computed Search Field
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
    """,
    
    # =========================================================================
    # 2. Full-Text Search Index (PostgreSQL GIN)
    # =========================================================================
    """
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
    """,
    
    # =========================================================================
    # 3. Composite Index for Organizational Hierarchy Queries
    # =========================================================================
    """
    CREATE INDEX IF NOT EXISTS idx_employee_org_hierarchy 
    ON employee (manager_id, department_id, employment_status)
    WHERE is_active = true;
    """,
    
    # =========================================================================
    # 4. Filtered Index for Department-Based Queries (Active Employees)
    # =========================================================================
    """
    CREATE INDEX IF NOT EXISTS idx_employee_department_active 
    ON employee (department_id, last_name, first_name)
    WHERE is_active = true;
    """,
    
    # =========================================================================
    # 5. Filtered Index for Location-Based Queries (Active Employees)
    # =========================================================================
    """
    CREATE INDEX IF NOT EXISTS idx_employee_location_active 
    ON employee (location_id, last_name, first_name)
    WHERE is_active = true;
    """,
    
    # =========================================================================
    # 6. Covering Index for Manager Lookup
    # =========================================================================
    """
    CREATE INDEX IF NOT EXISTS idx_employee_manager_lookup 
    ON employee (manager_id)
    INCLUDE (id, employee_id, first_name, last_name, job_title)
    WHERE is_active = true;
    """,
    
    # =========================================================================
    # 7. Employment Status and Type Index
    # =========================================================================
    """
    CREATE INDEX IF NOT EXISTS idx_employee_employment_status 
    ON employee (employment_status, employment_type)
    WHERE is_active = true;
    """,
    
    # =========================================================================
    # 8. Hire Date Index for Tenure Queries
    # =========================================================================
    """
    CREATE INDEX IF NOT EXISTS idx_employee_hire_date 
    ON employee (hire_date DESC)
    WHERE is_active = true;
    """,
    
    # =========================================================================
    # 9. Index on Department for Hierarchy Traversal
    # =========================================================================
    """
    CREATE INDEX IF NOT EXISTS idx_department_parent 
    ON department (parent_department_id)
    WHERE is_active = true;
    """,
    
    # =========================================================================
    # 10. Location Active Index
    # =========================================================================
    """
    CREATE INDEX IF NOT EXISTS idx_location_active 
    ON location (is_active)
    WHERE is_active = true;
    """,
]


# =============================================================================
# Downgrade SQL Statements
# =============================================================================

DOWNGRADE_STATEMENTS = [
    "DROP VIEW IF EXISTS employee_directory_view CASCADE;",
    "DROP INDEX IF EXISTS idx_employee_fulltext_search;",
    "DROP INDEX IF EXISTS idx_employee_org_hierarchy;",
    "DROP INDEX IF EXISTS idx_employee_department_active;",
    "DROP INDEX IF EXISTS idx_employee_location_active;",
    "DROP INDEX IF EXISTS idx_employee_manager_lookup;",
    "DROP INDEX IF EXISTS idx_employee_employment_status;",
    "DROP INDEX IF EXISTS idx_employee_hire_date;",
    "DROP INDEX IF EXISTS idx_department_parent;",
    "DROP INDEX IF EXISTS idx_location_active;",
]


# =============================================================================
# Migration Functions
# =============================================================================

def upgrade(engine: Engine) -> None:
    """
    Apply the migration (create views and indexes).
    
    Args:
        engine: SQLAlchemy engine instance
    """
    logger.info(f"Running migration {MIGRATION_VERSION}: {MIGRATION_NAME} (upgrade)")
    
    with engine.connect() as conn:
        for i, statement in enumerate(UPGRADE_STATEMENTS, 1):
            try:
                logger.debug(f"Executing statement {i}/{len(UPGRADE_STATEMENTS)}")
                conn.execute(text(statement))
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to execute statement {i}: {e}")
                raise
    
    logger.info(f"Migration {MIGRATION_VERSION} completed successfully")


def downgrade(engine: Engine) -> None:
    """
    Revert the migration (drop views and indexes).
    
    Args:
        engine: SQLAlchemy engine instance
    """
    logger.info(f"Running migration {MIGRATION_VERSION}: {MIGRATION_NAME} (downgrade)")
    
    with engine.connect() as conn:
        for i, statement in enumerate(DOWNGRADE_STATEMENTS, 1):
            try:
                logger.debug(f"Executing statement {i}/{len(DOWNGRADE_STATEMENTS)}")
                conn.execute(text(statement))
                conn.commit()
            except Exception as e:
                logger.warning(f"Failed to execute downgrade statement {i}: {e}")
    
    logger.info(f"Migration {MIGRATION_VERSION} downgrade completed")


def get_status(engine: Engine) -> dict:
    """
    Check if migration has been applied.
    
    Args:
        engine: SQLAlchemy engine instance
        
    Returns:
        dict with migration status information
    """
    status = {
        "version": MIGRATION_VERSION,
        "name": MIGRATION_NAME,
        "view_exists": False,
        "indexes": {},
    }
    
    with engine.connect() as conn:
        # Check if view exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views 
                WHERE table_name = 'employee_directory_view'
            );
        """))
        status["view_exists"] = result.scalar()
        
        # Check if indexes exist
        index_names = [
            "idx_employee_fulltext_search",
            "idx_employee_org_hierarchy",
            "idx_employee_department_active",
            "idx_employee_location_active",
            "idx_employee_manager_lookup",
            "idx_employee_employment_status",
            "idx_employee_hire_date",
        ]
        
        for idx_name in index_names:
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = '{idx_name}'
                );
            """))
            status["indexes"][idx_name] = result.scalar()
    
    return status


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys
    from src.database.database import get_engine, DatabaseConfig
    
    config = DatabaseConfig.from_env()
    engine = get_engine(config)
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.database.migrations.001_employee_directory_views [upgrade|downgrade|status]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "upgrade":
        upgrade(engine)
    elif command == "downgrade":
        downgrade(engine)
    elif command == "status":
        status = get_status(engine)
        print(f"Migration {status['version']}: {status['name']}")
        print(f"  View exists: {status['view_exists']}")
        print("  Indexes:")
        for idx_name, exists in status['indexes'].items():
            print(f"    {idx_name}: {'✓' if exists else '✗'}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

