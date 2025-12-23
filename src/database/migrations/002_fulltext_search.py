"""
PostgreSQL Full-Text Search Migration

Creates GIN indexes and tsvector columns for employee directory
and document content full-text search.
"""

# =============================================================================
# Migration SQL
# =============================================================================

# Create tsvector columns and GIN indexes for employee search
EMPLOYEE_SEARCH_MIGRATION = """
-- Add tsvector column for employee search
ALTER TABLE employee 
ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Create GIN index for employee search
CREATE INDEX IF NOT EXISTS idx_employee_search_gin 
ON employee USING GIN (search_vector);

-- Create function to update employee search vector
CREATE OR REPLACE FUNCTION update_employee_search_vector() 
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.first_name, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.last_name, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.preferred_name, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.email, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.job_title, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.employee_id, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update search vector
DROP TRIGGER IF EXISTS employee_search_vector_update ON employee;
CREATE TRIGGER employee_search_vector_update
    BEFORE INSERT OR UPDATE OF first_name, last_name, preferred_name, email, job_title, employee_id
    ON employee
    FOR EACH ROW
    EXECUTE FUNCTION update_employee_search_vector();

-- Update existing records
UPDATE employee SET search_vector = 
    setweight(to_tsvector('english', COALESCE(first_name, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(last_name, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(preferred_name, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(email, '')), 'B') ||
    setweight(to_tsvector('english', COALESCE(job_title, '')), 'B') ||
    setweight(to_tsvector('english', COALESCE(employee_id, '')), 'C');
"""

# Create document search table and indexes
DOCUMENT_SEARCH_MIGRATION = """
-- Create document search table
CREATE TABLE IF NOT EXISTS document (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    metadata JSONB DEFAULT '{}',
    file_key VARCHAR(500),
    file_type VARCHAR(100),
    file_size INTEGER,
    owner_id INTEGER REFERENCES employee(id) ON DELETE SET NULL,
    department_id INTEGER REFERENCES department(id) ON DELETE SET NULL,
    is_public BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    search_vector tsvector
);

-- Create GIN index for document search
CREATE INDEX IF NOT EXISTS idx_document_search_gin 
ON document USING GIN (search_vector);

-- Create index on metadata
CREATE INDEX IF NOT EXISTS idx_document_metadata_gin 
ON document USING GIN (metadata);

-- Create function to update document search vector
CREATE OR REPLACE FUNCTION update_document_search_vector() 
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.metadata->>'keywords', '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.metadata->>'description', '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update search vector
DROP TRIGGER IF EXISTS document_search_vector_update ON document;
CREATE TRIGGER document_search_vector_update
    BEFORE INSERT OR UPDATE OF title, content, metadata
    ON document
    FOR EACH ROW
    EXECUTE FUNCTION update_document_search_vector();
"""

# Create search analytics table
SEARCH_ANALYTICS_MIGRATION = """
-- Create search analytics table
CREATE TABLE IF NOT EXISTS search_analytics (
    id SERIAL PRIMARY KEY,
    query_text VARCHAR(500) NOT NULL,
    query_hash VARCHAR(64) NOT NULL,
    search_type VARCHAR(50) NOT NULL,  -- 'employee', 'document', 'combined'
    user_id INTEGER REFERENCES employee(id) ON DELETE SET NULL,
    result_count INTEGER DEFAULT 0,
    execution_time_ms INTEGER,
    filters_used JSONB DEFAULT '{}',
    searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create search click tracking table
CREATE TABLE IF NOT EXISTS search_click (
    id SERIAL PRIMARY KEY,
    search_id INTEGER REFERENCES search_analytics(id) ON DELETE CASCADE,
    result_type VARCHAR(50) NOT NULL,  -- 'employee', 'document'
    result_id INTEGER NOT NULL,
    result_position INTEGER,  -- Position in results (1-indexed)
    clicked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_search_analytics_query_hash ON search_analytics(query_hash);
CREATE INDEX IF NOT EXISTS idx_search_analytics_searched_at ON search_analytics(searched_at);
CREATE INDEX IF NOT EXISTS idx_search_analytics_type ON search_analytics(search_type);
CREATE INDEX IF NOT EXISTS idx_search_click_search_id ON search_click(search_id);

-- Create view for search metrics
CREATE OR REPLACE VIEW search_metrics AS
SELECT 
    DATE_TRUNC('day', searched_at) AS search_date,
    search_type,
    COUNT(*) AS total_searches,
    COUNT(DISTINCT user_id) AS unique_users,
    AVG(result_count) AS avg_results,
    AVG(execution_time_ms) AS avg_execution_time_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY execution_time_ms) AS p95_execution_time_ms
FROM search_analytics
GROUP BY DATE_TRUNC('day', searched_at), search_type;

-- Create view for popular searches
CREATE OR REPLACE VIEW popular_searches AS
SELECT 
    query_text,
    query_hash,
    search_type,
    COUNT(*) AS search_count,
    AVG(result_count) AS avg_results,
    SUM(CASE WHEN result_count > 0 THEN 1 ELSE 0 END)::float / COUNT(*) AS success_rate
FROM search_analytics
WHERE searched_at > NOW() - INTERVAL '30 days'
GROUP BY query_text, query_hash, search_type
ORDER BY search_count DESC;
"""

# Department search enhancements
DEPARTMENT_SEARCH_MIGRATION = """
-- Add search vector to department
ALTER TABLE department 
ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Create GIN index for department search
CREATE INDEX IF NOT EXISTS idx_department_search_gin 
ON department USING GIN (search_vector);

-- Create function to update department search vector
CREATE OR REPLACE FUNCTION update_department_search_vector() 
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.name, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.code, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS department_search_vector_update ON department;
CREATE TRIGGER department_search_vector_update
    BEFORE INSERT OR UPDATE OF name, description, code
    ON department
    FOR EACH ROW
    EXECUTE FUNCTION update_department_search_vector();
"""

# Combined SQL for all migrations
ALL_MIGRATIONS = [
    ("Employee Search Setup", EMPLOYEE_SEARCH_MIGRATION),
    ("Document Search Setup", DOCUMENT_SEARCH_MIGRATION),
    ("Search Analytics Setup", SEARCH_ANALYTICS_MIGRATION),
    ("Department Search Setup", DEPARTMENT_SEARCH_MIGRATION),
]


def get_migration_sql() -> str:
    """Get complete migration SQL."""
    parts = []
    for name, sql in ALL_MIGRATIONS:
        parts.append(f"-- Migration: {name}")
        parts.append(sql)
        parts.append("")
    return "\n".join(parts)


def run_migration(connection) -> None:
    """Run the full-text search migration."""
    cursor = connection.cursor()
    
    for name, sql in ALL_MIGRATIONS:
        print(f"Running migration: {name}")
        try:
            cursor.execute(sql)
            connection.commit()
            print(f"  ✓ {name} completed")
        except Exception as e:
            connection.rollback()
            print(f"  ✗ {name} failed: {str(e)}")
            raise
    
    cursor.close()
    print("All migrations completed successfully")

