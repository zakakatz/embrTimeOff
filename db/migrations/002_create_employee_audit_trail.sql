-- Employee Audit Trail Migration
-- Creates immutable audit trail for tracking all employee profile changes

-- ============================================================================
-- Change Type Enum
-- ============================================================================
CREATE TYPE change_type AS ENUM ('CREATE', 'UPDATE', 'DELETE');

-- ============================================================================
-- Employee Audit Trail Table
-- Stores field-level change records for compliance and history tracking
-- ============================================================================
CREATE TABLE employee_audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Reference to the employee being audited
    employee_id INTEGER NOT NULL REFERENCES employee(id) ON DELETE CASCADE,
    
    -- Field-level change tracking
    changed_field VARCHAR(100) NOT NULL,
    previous_value TEXT,
    new_value TEXT,
    
    -- Change metadata
    changed_by_user_id UUID NOT NULL,
    change_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    change_type change_type NOT NULL,
    
    -- Optional context/notes
    change_reason TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- ============================================================================
-- Indexes for Query Performance
-- ============================================================================

-- Query audit history for specific employee
CREATE INDEX idx_audit_employee_id ON employee_audit_trail(employee_id);

-- Query changes by user
CREATE INDEX idx_audit_changed_by ON employee_audit_trail(changed_by_user_id);

-- Query changes by timestamp (for date range queries)
CREATE INDEX idx_audit_timestamp ON employee_audit_trail(change_timestamp);

-- Query changes by type
CREATE INDEX idx_audit_change_type ON employee_audit_trail(change_type);

-- Query specific field changes
CREATE INDEX idx_audit_changed_field ON employee_audit_trail(changed_field);

-- Composite index for common query patterns
CREATE INDEX idx_audit_employee_timestamp ON employee_audit_trail(employee_id, change_timestamp DESC);

-- ============================================================================
-- Immutability Protection
-- Prevent UPDATE and DELETE operations on audit records
-- ============================================================================

CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit trail records are immutable and cannot be modified or deleted';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_prevent_audit_update
    BEFORE UPDATE ON employee_audit_trail
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();

CREATE TRIGGER trigger_prevent_audit_delete
    BEFORE DELETE ON employee_audit_trail
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();

-- ============================================================================
-- Comments for Documentation
-- ============================================================================
COMMENT ON TABLE employee_audit_trail IS 'Immutable audit trail for employee profile changes with field-level granularity';
COMMENT ON COLUMN employee_audit_trail.changed_field IS 'Name of the field that was modified';
COMMENT ON COLUMN employee_audit_trail.previous_value IS 'JSON-encoded previous value (NULL for CREATE operations)';
COMMENT ON COLUMN employee_audit_trail.new_value IS 'JSON-encoded new value (NULL for DELETE operations)';
COMMENT ON COLUMN employee_audit_trail.change_type IS 'Type of change: CREATE, UPDATE, or DELETE';

