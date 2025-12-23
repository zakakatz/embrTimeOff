"""Organizational data validation and constraints service.

Provides comprehensive validation rules and database constraints to ensure
organizational data integrity including circular dependency prevention,
manager relationship validation, and change management workflows.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, or_, select, func, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Session


# =============================================================================
# Validation Types
# =============================================================================

class ValidationErrorCode(str, Enum):
    """Error codes for organizational validation failures."""
    
    # Department hierarchy errors
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"
    INVALID_PARENT_DEPARTMENT = "INVALID_PARENT_DEPARTMENT"
    DEPARTMENT_NOT_FOUND = "DEPARTMENT_NOT_FOUND"
    
    # Manager relationship errors
    INVALID_MANAGER = "INVALID_MANAGER"
    MANAGER_REPORTS_TO_SUBORDINATE = "MANAGER_REPORTS_TO_SUBORDINATE"
    MANAGER_NOT_IN_APPROPRIATE_LEVEL = "MANAGER_NOT_IN_APPROPRIATE_LEVEL"
    SELF_REPORTING = "SELF_REPORTING"
    
    # Location capacity errors
    LOCATION_OVER_CAPACITY = "LOCATION_OVER_CAPACITY"
    LOCATION_NOT_FOUND = "LOCATION_NOT_FOUND"
    
    # Change management errors
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    PENDING_APPROVAL_EXISTS = "PENDING_APPROVAL_EXISTS"
    CHANGE_NOT_AUTHORIZED = "CHANGE_NOT_AUTHORIZED"
    
    # Date validation errors
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    END_DATE_BEFORE_EFFECTIVE = "END_DATE_BEFORE_EFFECTIVE"
    
    # Organizational level errors
    INVALID_ORGANIZATIONAL_LEVEL = "INVALID_ORGANIZATIONAL_LEVEL"
    LEVEL_OUT_OF_RANGE = "LEVEL_OUT_OF_RANGE"
    
    # Reporting relationship errors
    DUPLICATE_RELATIONSHIP = "DUPLICATE_RELATIONSHIP"
    CONFLICTING_RELATIONSHIP = "CONFLICTING_RELATIONSHIP"
    
    # Holiday calendar errors
    CALENDAR_JURISDICTION_MISMATCH = "CALENDAR_JURISDICTION_MISMATCH"
    CALENDAR_NOT_FOUND = "CALENDAR_NOT_FOUND"


@dataclass
class ValidationError:
    """Represents a validation error."""
    
    code: ValidationErrorCode
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "field": self.field,
            "details": self.details,
        }


@dataclass
class ValidationResult:
    """Result of validation operation."""
    
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    
    def add_error(
        self,
        code: ValidationErrorCode,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an error to the result."""
        self.errors.append(ValidationError(code, message, field, details))
        self.is_valid = False
    
    def add_warning(
        self,
        code: ValidationErrorCode,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a warning to the result (doesn't invalidate)."""
        self.warnings.append(ValidationError(code, message, field, details))
    
    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


# =============================================================================
# Department Hierarchy Validation
# =============================================================================

class DepartmentHierarchyValidator:
    """
    Validates department hierarchy to prevent circular dependencies.
    
    Ensures parent_department_id cannot create loops in the
    organizational structure.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_parent_assignment(
        self,
        department_id: int,
        new_parent_id: Optional[int],
    ) -> ValidationResult:
        """
        Validate that assigning a parent department won't create a cycle.
        
        Args:
            department_id: ID of the department being modified
            new_parent_id: ID of the proposed parent department
        
        Returns:
            ValidationResult indicating if the assignment is valid
        """
        result = ValidationResult()
        
        # No parent is always valid
        if new_parent_id is None:
            return result
        
        # Can't be your own parent
        if department_id == new_parent_id:
            result.add_error(
                ValidationErrorCode.CIRCULAR_DEPENDENCY,
                "A department cannot be its own parent",
                "parent_department_id",
            )
            return result
        
        # Check if new parent is a descendant of this department
        descendants = self._get_all_descendants(department_id)
        if new_parent_id in descendants:
            result.add_error(
                ValidationErrorCode.CIRCULAR_DEPENDENCY,
                "Cannot set parent to a descendant department - would create circular dependency",
                "parent_department_id",
                {"descendant_ids": list(descendants)},
            )
        
        return result
    
    def _get_all_descendants(self, department_id: int) -> Set[int]:
        """Get all descendant department IDs recursively."""
        descendants: Set[int] = set()
        
        # Get direct children
        children = self._get_children(department_id)
        
        for child_id in children:
            descendants.add(child_id)
            # Recursively get descendants of children
            descendants.update(self._get_all_descendants(child_id))
        
        return descendants
    
    def _get_children(self, department_id: int) -> List[int]:
        """Get direct child department IDs."""
        # In a real implementation, this would query the database
        # Placeholder implementation
        return []
    
    def validate_hierarchy_depth(
        self,
        department_id: int,
        max_depth: int = 10,
    ) -> ValidationResult:
        """
        Validate that hierarchy depth doesn't exceed maximum.
        
        Args:
            department_id: ID of the department to check
            max_depth: Maximum allowed hierarchy depth
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        depth = self._calculate_depth(department_id)
        if depth > max_depth:
            result.add_warning(
                ValidationErrorCode.INVALID_ORGANIZATIONAL_LEVEL,
                f"Department hierarchy depth ({depth}) exceeds recommended maximum ({max_depth})",
                "organizational_level",
            )
        
        return result
    
    def _calculate_depth(self, department_id: int) -> int:
        """Calculate the depth of a department in the hierarchy."""
        depth = 1
        current_id = department_id
        visited: Set[int] = set()
        
        while current_id is not None:
            if current_id in visited:
                # Circular dependency detected
                break
            visited.add(current_id)
            
            parent_id = self._get_parent(current_id)
            if parent_id is not None:
                depth += 1
                current_id = parent_id
            else:
                break
        
        return depth
    
    def _get_parent(self, department_id: int) -> Optional[int]:
        """Get parent department ID."""
        # In a real implementation, this would query the database
        return None


# =============================================================================
# Manager Relationship Validation
# =============================================================================

class ManagerRelationshipValidator:
    """
    Validates manager relationships to ensure proper organizational hierarchy.
    
    Ensures managers exist within appropriate organizational levels
    and cannot report to their subordinates.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_manager_assignment(
        self,
        employee_id: int,
        proposed_manager_id: Optional[int],
    ) -> ValidationResult:
        """
        Validate that a manager assignment is valid.
        
        Args:
            employee_id: ID of the employee
            proposed_manager_id: ID of the proposed manager
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        # No manager is valid (top-level employee)
        if proposed_manager_id is None:
            return result
        
        # Can't be your own manager
        if employee_id == proposed_manager_id:
            result.add_error(
                ValidationErrorCode.SELF_REPORTING,
                "An employee cannot be their own manager",
                "manager_id",
            )
            return result
        
        # Check if proposed manager exists
        if not self._employee_exists(proposed_manager_id):
            result.add_error(
                ValidationErrorCode.INVALID_MANAGER,
                "Proposed manager does not exist",
                "manager_id",
            )
            return result
        
        # Check for subordinate-to-manager reporting
        subordinates = self._get_all_subordinates(employee_id)
        if proposed_manager_id in subordinates:
            result.add_error(
                ValidationErrorCode.MANAGER_REPORTS_TO_SUBORDINATE,
                "Cannot set a subordinate as manager - would create circular reporting",
                "manager_id",
                {"subordinate_ids": list(subordinates)},
            )
        
        return result
    
    def _employee_exists(self, employee_id: int) -> bool:
        """Check if an employee exists."""
        # In a real implementation, this would query the database
        return True
    
    def _get_all_subordinates(self, employee_id: int) -> Set[int]:
        """Get all subordinate employee IDs recursively."""
        subordinates: Set[int] = set()
        
        # Get direct reports
        direct_reports = self._get_direct_reports(employee_id)
        
        for report_id in direct_reports:
            subordinates.add(report_id)
            # Recursively get subordinates of direct reports
            subordinates.update(self._get_all_subordinates(report_id))
        
        return subordinates
    
    def _get_direct_reports(self, manager_id: int) -> List[int]:
        """Get direct report employee IDs."""
        # In a real implementation, this would query the database
        return []
    
    def validate_organizational_level(
        self,
        employee_id: int,
        manager_id: Optional[int],
    ) -> ValidationResult:
        """
        Validate that manager is at appropriate organizational level.
        
        Args:
            employee_id: ID of the employee
            manager_id: ID of the manager
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        if manager_id is None:
            return result
        
        employee_level = self._get_organizational_level(employee_id)
        manager_level = self._get_organizational_level(manager_id)
        
        # Manager should typically be at same or higher level
        if manager_level is not None and employee_level is not None:
            if manager_level > employee_level:
                result.add_warning(
                    ValidationErrorCode.MANAGER_NOT_IN_APPROPRIATE_LEVEL,
                    f"Manager is at a lower organizational level ({manager_level}) "
                    f"than employee ({employee_level})",
                    "manager_id",
                )
        
        return result
    
    def _get_organizational_level(self, employee_id: int) -> Optional[int]:
        """Get organizational level for an employee."""
        # In a real implementation, this would query the database
        return None


# =============================================================================
# Location Capacity Validation
# =============================================================================

class LocationCapacityValidator:
    """
    Validates location capacity constraints.
    
    Prevents over-assignment of employees to facilities based on
    location.capacity field.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_location_assignment(
        self,
        employee_id: int,
        location_id: int,
    ) -> ValidationResult:
        """
        Validate that assigning an employee to a location won't exceed capacity.
        
        Args:
            employee_id: ID of the employee being assigned
            location_id: ID of the target location
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        # Get location capacity
        location_info = self._get_location_info(location_id)
        if location_info is None:
            result.add_error(
                ValidationErrorCode.LOCATION_NOT_FOUND,
                "Location does not exist",
                "location_id",
            )
            return result
        
        capacity = location_info.get("capacity")
        if capacity is None:
            # No capacity limit set
            return result
        
        # Get current employee count (excluding the employee being assigned)
        current_count = self._get_employee_count(location_id, exclude_id=employee_id)
        
        if current_count >= capacity:
            result.add_error(
                ValidationErrorCode.LOCATION_OVER_CAPACITY,
                f"Location is at capacity ({current_count}/{capacity})",
                "location_id",
                {
                    "current_count": current_count,
                    "capacity": capacity,
                    "location_name": location_info.get("name"),
                },
            )
        elif current_count >= capacity * 0.9:
            # Warn if approaching capacity (90%)
            result.add_warning(
                ValidationErrorCode.LOCATION_OVER_CAPACITY,
                f"Location is approaching capacity ({current_count}/{capacity})",
                "location_id",
            )
        
        return result
    
    def _get_location_info(self, location_id: int) -> Optional[Dict[str, Any]]:
        """Get location information including capacity."""
        # In a real implementation, this would query the database
        return None
    
    def _get_employee_count(
        self,
        location_id: int,
        exclude_id: Optional[int] = None,
    ) -> int:
        """Get count of employees at a location."""
        # In a real implementation, this would query the database
        return 0
    
    def get_available_capacity(self, location_id: int) -> Optional[int]:
        """
        Get remaining available capacity for a location.
        
        Args:
            location_id: ID of the location
        
        Returns:
            Available capacity or None if no limit
        """
        location_info = self._get_location_info(location_id)
        if location_info is None:
            return None
        
        capacity = location_info.get("capacity")
        if capacity is None:
            return None
        
        current_count = self._get_employee_count(location_id)
        return max(0, capacity - current_count)


# =============================================================================
# Change Management Validation
# =============================================================================

class ChangeManagementValidator:
    """
    Validates change management workflows.
    
    Ensures proper approval workflows are followed before
    implementing structural modifications.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_change_authorization(
        self,
        entity_type: str,
        entity_id: int,
        change_type: str,
        requester_id: int,
    ) -> ValidationResult:
        """
        Validate that a change is authorized.
        
        Args:
            entity_type: Type of entity being changed (department, location, etc.)
            entity_id: ID of the entity
            change_type: Type of change (create, update, delete)
            requester_id: ID of the user requesting the change
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        # Check if approval is required for this change
        requires_approval = self._check_approval_required(entity_type, entity_id, change_type)
        
        if requires_approval:
            # Check if there's already a pending approval
            pending = self._check_pending_approval(entity_type, entity_id, change_type)
            if pending:
                result.add_error(
                    ValidationErrorCode.PENDING_APPROVAL_EXISTS,
                    "A change request is already pending for this entity",
                    None,
                    {"pending_request_id": pending.get("id")},
                )
                return result
            
            # Check if requester is authorized
            if not self._is_authorized(requester_id, entity_type, change_type):
                result.add_error(
                    ValidationErrorCode.CHANGE_NOT_AUTHORIZED,
                    "You are not authorized to make this change",
                    None,
                )
            else:
                result.add_warning(
                    ValidationErrorCode.APPROVAL_REQUIRED,
                    "This change requires approval before taking effect",
                    None,
                )
        
        return result
    
    def _check_approval_required(
        self,
        entity_type: str,
        entity_id: int,
        change_type: str,
    ) -> bool:
        """Check if approval is required for this change."""
        # In a real implementation, this would check:
        # 1. Entity-specific approval settings (e.g., department.approval_required_for_changes)
        # 2. Global change management policies
        return False
    
    def _check_pending_approval(
        self,
        entity_type: str,
        entity_id: int,
        change_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Check for existing pending approval request."""
        # In a real implementation, this would query OrganizationalChange table
        return None
    
    def _is_authorized(
        self,
        requester_id: int,
        entity_type: str,
        change_type: str,
    ) -> bool:
        """Check if requester is authorized to make this change."""
        # In a real implementation, this would check roles and permissions
        return True


# =============================================================================
# Date Validation
# =============================================================================

class DateRangeValidator:
    """
    Validates date ranges for organizational entities.
    
    Ensures end_date is after effective_date when both are specified.
    """
    
    def validate_date_range(
        self,
        effective_date: Optional[date],
        end_date: Optional[date],
    ) -> ValidationResult:
        """
        Validate that end_date is after effective_date.
        
        Args:
            effective_date: Start/effective date
            end_date: End date
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        if effective_date is not None and end_date is not None:
            if end_date < effective_date:
                result.add_error(
                    ValidationErrorCode.END_DATE_BEFORE_EFFECTIVE,
                    "End date cannot be before effective date",
                    "end_date",
                    {
                        "effective_date": effective_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    },
                )
        
        return result


# =============================================================================
# Organizational Level Validation
# =============================================================================

class OrganizationalLevelValidator:
    """
    Validates organizational level values.
    
    Ensures positive integer values and logical hierarchy levels.
    """
    
    MIN_LEVEL = 1
    MAX_LEVEL = 20  # Reasonable maximum for organizational depth
    
    def validate_level(self, level: int) -> ValidationResult:
        """
        Validate organizational level value.
        
        Args:
            level: Organizational level to validate
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        if level < self.MIN_LEVEL:
            result.add_error(
                ValidationErrorCode.INVALID_ORGANIZATIONAL_LEVEL,
                f"Organizational level must be at least {self.MIN_LEVEL}",
                "organizational_level",
            )
        
        if level > self.MAX_LEVEL:
            result.add_error(
                ValidationErrorCode.LEVEL_OUT_OF_RANGE,
                f"Organizational level cannot exceed {self.MAX_LEVEL}",
                "organizational_level",
            )
        
        return result


# =============================================================================
# Reporting Relationship Validation
# =============================================================================

class ReportingRelationshipValidator:
    """
    Validates reporting relationships.
    
    Prevents duplicate active relationships of the same type
    between the same employee-manager pairs.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_relationship(
        self,
        employee_id: int,
        manager_id: int,
        relationship_type: str,
        is_primary: bool = False,
        exclude_id: Optional[int] = None,
    ) -> ValidationResult:
        """
        Validate that a reporting relationship is valid.
        
        Args:
            employee_id: ID of the employee
            manager_id: ID of the manager
            relationship_type: Type of relationship
            is_primary: Whether this is a primary relationship
            exclude_id: ID of existing relationship to exclude from duplicate check
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        # Check for duplicate active relationship
        existing = self._find_duplicate_relationship(
            employee_id, manager_id, relationship_type, exclude_id
        )
        if existing:
            result.add_error(
                ValidationErrorCode.DUPLICATE_RELATIONSHIP,
                f"An active {relationship_type} relationship already exists between "
                f"employee {employee_id} and manager {manager_id}",
                "relationship_type",
            )
        
        # If setting as primary, check for existing primary
        if is_primary:
            existing_primary = self._find_primary_relationship(
                employee_id, relationship_type, exclude_id
            )
            if existing_primary:
                result.add_warning(
                    ValidationErrorCode.CONFLICTING_RELATIONSHIP,
                    f"Employee already has a primary {relationship_type} relationship "
                    f"with manager {existing_primary.get('manager_id')}. "
                    f"Setting this as primary will demote the existing one.",
                    "is_primary",
                )
        
        return result
    
    def _find_duplicate_relationship(
        self,
        employee_id: int,
        manager_id: int,
        relationship_type: str,
        exclude_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """Find existing duplicate active relationship."""
        # In a real implementation, this would query ReportingRelationship table
        return None
    
    def _find_primary_relationship(
        self,
        employee_id: int,
        relationship_type: str,
        exclude_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """Find existing primary relationship."""
        # In a real implementation, this would query ReportingRelationship table
        return None


# =============================================================================
# Holiday Calendar Validation
# =============================================================================

class HolidayCalendarValidator:
    """
    Validates holiday calendar assignments.
    
    Ensures calendars match location jurisdictions.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_calendar_assignment(
        self,
        location_id: int,
        calendar_id: str,
    ) -> ValidationResult:
        """
        Validate that a calendar assignment matches location jurisdiction.
        
        Args:
            location_id: ID of the location
            calendar_id: ID of the holiday calendar
        
        Returns:
            ValidationResult
        """
        result = ValidationResult()
        
        # Get location info
        location = self._get_location(location_id)
        if location is None:
            result.add_error(
                ValidationErrorCode.LOCATION_NOT_FOUND,
                "Location does not exist",
                "location_id",
            )
            return result
        
        # Get calendar info
        calendar = self._get_calendar(calendar_id)
        if calendar is None:
            result.add_error(
                ValidationErrorCode.CALENDAR_NOT_FOUND,
                "Holiday calendar does not exist",
                "holiday_calendar_id",
            )
            return result
        
        # Check jurisdiction match
        location_country = location.get("country")
        calendar_country = calendar.get("country")
        
        if location_country != calendar_country:
            result.add_error(
                ValidationErrorCode.CALENDAR_JURISDICTION_MISMATCH,
                f"Calendar country ({calendar_country}) does not match "
                f"location country ({location_country})",
                "holiday_calendar_id",
                {
                    "location_country": location_country,
                    "calendar_country": calendar_country,
                },
            )
        
        # Check region if specified
        location_region = location.get("region") or location.get("state_province")
        calendar_region = calendar.get("region")
        
        if calendar_region and location_region and calendar_region != location_region:
            result.add_warning(
                ValidationErrorCode.CALENDAR_JURISDICTION_MISMATCH,
                f"Calendar region ({calendar_region}) does not match "
                f"location region ({location_region})",
                "holiday_calendar_id",
            )
        
        return result
    
    def _get_location(self, location_id: int) -> Optional[Dict[str, Any]]:
        """Get location information."""
        # In a real implementation, this would query the database
        return None
    
    def _get_calendar(self, calendar_id: str) -> Optional[Dict[str, Any]]:
        """Get calendar information."""
        # In a real implementation, this would query the database
        return None


# =============================================================================
# Database Constraints
# =============================================================================

def get_organizational_constraints() -> List[Any]:
    """
    Get database constraint definitions for organizational entities.
    
    Returns:
        List of SQLAlchemy constraint objects
    """
    return [
        # Department constraints
        CheckConstraint(
            "organizational_level > 0",
            name="ck_department_positive_level",
        ),
        CheckConstraint(
            "organizational_level <= 20",
            name="ck_department_max_level",
        ),
        CheckConstraint(
            "end_date IS NULL OR effective_date IS NULL OR end_date >= effective_date",
            name="ck_department_valid_date_range",
        ),
        CheckConstraint(
            "id != parent_department_id",
            name="ck_department_not_own_parent",
        ),
        
        # Reporting relationship constraints
        UniqueConstraint(
            "employee_id",
            "manager_id",
            "relationship_type",
            name="uq_reporting_relationship_active",
        ),
        CheckConstraint(
            "employee_id != manager_id",
            name="ck_reporting_not_self",
        ),
        CheckConstraint(
            "end_date IS NULL OR effective_date IS NULL OR end_date >= effective_date",
            name="ck_reporting_valid_date_range",
        ),
        CheckConstraint(
            "authority_level > 0",
            name="ck_reporting_positive_authority",
        ),
        
        # Location constraints
        CheckConstraint(
            "capacity IS NULL OR capacity > 0",
            name="ck_location_positive_capacity",
        ),
    ]


# =============================================================================
# Composite Validator Service
# =============================================================================

class OrganizationalValidationService:
    """
    Composite service for all organizational validations.
    
    Provides a unified interface for validating organizational
    data integrity.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.department_validator = DepartmentHierarchyValidator(db)
        self.manager_validator = ManagerRelationshipValidator(db)
        self.location_validator = LocationCapacityValidator(db)
        self.change_validator = ChangeManagementValidator(db)
        self.date_validator = DateRangeValidator()
        self.level_validator = OrganizationalLevelValidator()
        self.relationship_validator = ReportingRelationshipValidator(db)
        self.calendar_validator = HolidayCalendarValidator(db)
    
    def validate_department_update(
        self,
        department_id: int,
        parent_department_id: Optional[int] = None,
        organizational_level: Optional[int] = None,
        effective_date: Optional[date] = None,
        end_date: Optional[date] = None,
        requester_id: Optional[int] = None,
    ) -> ValidationResult:
        """Validate a department update operation."""
        result = ValidationResult()
        
        # Validate parent assignment
        if parent_department_id is not None:
            parent_result = self.department_validator.validate_parent_assignment(
                department_id, parent_department_id
            )
            result.merge(parent_result)
        
        # Validate organizational level
        if organizational_level is not None:
            level_result = self.level_validator.validate_level(organizational_level)
            result.merge(level_result)
        
        # Validate date range
        date_result = self.date_validator.validate_date_range(effective_date, end_date)
        result.merge(date_result)
        
        # Validate change management
        if requester_id is not None:
            change_result = self.change_validator.validate_change_authorization(
                "department", department_id, "update", requester_id
            )
            result.merge(change_result)
        
        return result
    
    def validate_employee_assignment(
        self,
        employee_id: int,
        manager_id: Optional[int] = None,
        location_id: Optional[int] = None,
    ) -> ValidationResult:
        """Validate an employee assignment operation."""
        result = ValidationResult()
        
        # Validate manager relationship
        if manager_id is not None:
            manager_result = self.manager_validator.validate_manager_assignment(
                employee_id, manager_id
            )
            result.merge(manager_result)
            
            # Validate organizational level
            level_result = self.manager_validator.validate_organizational_level(
                employee_id, manager_id
            )
            result.merge(level_result)
        
        # Validate location capacity
        if location_id is not None:
            location_result = self.location_validator.validate_location_assignment(
                employee_id, location_id
            )
            result.merge(location_result)
        
        return result
    
    def validate_reporting_relationship(
        self,
        employee_id: int,
        manager_id: int,
        relationship_type: str,
        is_primary: bool = False,
        effective_date: Optional[date] = None,
        end_date: Optional[date] = None,
        exclude_id: Optional[int] = None,
    ) -> ValidationResult:
        """Validate a reporting relationship."""
        result = ValidationResult()
        
        # Validate relationship
        rel_result = self.relationship_validator.validate_relationship(
            employee_id, manager_id, relationship_type, is_primary, exclude_id
        )
        result.merge(rel_result)
        
        # Validate date range
        date_result = self.date_validator.validate_date_range(effective_date, end_date)
        result.merge(date_result)
        
        # Validate manager relationship
        manager_result = self.manager_validator.validate_manager_assignment(
            employee_id, manager_id
        )
        result.merge(manager_result)
        
        return result
    
    def validate_location_calendar(
        self,
        location_id: int,
        calendar_id: str,
    ) -> ValidationResult:
        """Validate a location calendar assignment."""
        return self.calendar_validator.validate_calendar_assignment(
            location_id, calendar_id
        )

