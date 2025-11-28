-- Employee Management System Database Schema
-- Core tables for employee profile management with organizational hierarchy

-- ============================================================================
-- Location Table
-- Stores office locations with complete address information and timezone support
-- ============================================================================
CREATE TABLE location (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    address_line1 VARCHAR(255) NOT NULL,
    address_line2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state_province VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100) NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_location_code ON location(code);
CREATE INDEX idx_location_is_active ON location(is_active);

-- ============================================================================
-- Work Schedule Table
-- Defines flexible work schedules with hours and days configuration
-- ============================================================================
CREATE TABLE work_schedule (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    hours_per_week DECIMAL(4,2) NOT NULL DEFAULT 40.00,
    days_per_week INTEGER NOT NULL DEFAULT 5,
    start_time TIME,
    end_time TIME,
    is_flexible BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_work_schedule_is_active ON work_schedule(is_active);

-- ============================================================================
-- Department Table
-- Organizational structure with hierarchical support via self-reference
-- ============================================================================
CREATE TABLE department (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_department_id INTEGER REFERENCES department(id) ON DELETE SET NULL,
    head_of_department_id INTEGER, -- FK to employee added after employee table creation
    location_id INTEGER REFERENCES location(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_department_code ON department(code);
CREATE INDEX idx_department_parent ON department(parent_department_id);
CREATE INDEX idx_department_is_active ON department(is_active);

-- ============================================================================
-- Employee Table
-- Core employee data including personal info, contact details, and employment info
-- ============================================================================
CREATE TABLE employee (
    id SERIAL PRIMARY KEY,
    employee_id VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    
    -- Personal Information
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(100) NOT NULL,
    preferred_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(20),
    
    -- Contact Information
    personal_email VARCHAR(255),
    phone_number VARCHAR(30),
    mobile_number VARCHAR(30),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state_province VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    
    -- Employment Information
    department_id INTEGER REFERENCES department(id) ON DELETE SET NULL,
    manager_id INTEGER REFERENCES employee(id) ON DELETE SET NULL,
    location_id INTEGER REFERENCES location(id) ON DELETE SET NULL,
    work_schedule_id INTEGER REFERENCES work_schedule(id) ON DELETE SET NULL,
    job_title VARCHAR(100),
    employment_type VARCHAR(50), -- Full-time, Part-time, Contract, etc.
    employment_status VARCHAR(50) NOT NULL DEFAULT 'Active', -- Active, On Leave, Terminated, etc.
    hire_date DATE NOT NULL,
    termination_date DATE,
    
    -- System Fields
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes for frequently queried fields
CREATE INDEX idx_employee_employee_id ON employee(employee_id);
CREATE INDEX idx_employee_email ON employee(email);
CREATE INDEX idx_employee_department_id ON employee(department_id);
CREATE INDEX idx_employee_manager_id ON employee(manager_id);
CREATE INDEX idx_employee_location_id ON employee(location_id);
CREATE INDEX idx_employee_employment_status ON employee(employment_status);
CREATE INDEX idx_employee_is_active ON employee(is_active);
CREATE INDEX idx_employee_name ON employee(last_name, first_name);

-- ============================================================================
-- Add deferred foreign key from Department to Employee
-- (head_of_department_id references employee table)
-- ============================================================================
ALTER TABLE department
    ADD CONSTRAINT fk_department_head
    FOREIGN KEY (head_of_department_id) REFERENCES employee(id) ON DELETE SET NULL;

CREATE INDEX idx_department_head ON department(head_of_department_id);

-- ============================================================================
-- Trigger function for automatic updated_at timestamp management
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers to all tables
CREATE TRIGGER trigger_location_updated_at
    BEFORE UPDATE ON location
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_work_schedule_updated_at
    BEFORE UPDATE ON work_schedule
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_department_updated_at
    BEFORE UPDATE ON department
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_employee_updated_at
    BEFORE UPDATE ON employee
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

