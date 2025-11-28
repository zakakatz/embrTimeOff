"""Employee service for business logic and database operations."""

from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src.audit.service import AuditContext, AuditService
from src.config.settings import get_settings
from src.data.employee_repository import (
    EmployeeRepository,
    PaginationParams,
    SearchFilters,
    SearchResult,
    SortParams,
)
from src.employees.models import (
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeeUpdateRequest,
)
from src.models.employee import Department, Employee, Location, WorkSchedule
from src.utils.auth import CurrentUser, filter_employee_response
from src.utils.errors import (
    DatabaseError,
    DuplicateError,
    FieldError,
    NotFoundError,
    ValidationError,
    create_duplicate_error,
    create_field_error,
    create_not_found_error,
    create_validation_error,
)


class EmployeeService:
    """
    Service layer for employee CRUD and search operations.
    
    Handles business logic, validation, and audit logging.
    """
    
    def __init__(self, session: Session):
        """Initialize service with database session."""
        self.session = session
        self.audit_service = AuditService(session)
        self.repository = EmployeeRepository(session)
        self.settings = get_settings()
    
    # =========================================================================
    # Create Operations
    # =========================================================================
    
    def create_employee(
        self,
        data: EmployeeCreateRequest,
        current_user: CurrentUser,
    ) -> Dict[str, Any]:
        """
        Create a new employee profile.
        
        Validates uniqueness of employee_id and email.
        Creates audit trail for the new employee.
        
        Returns the complete employee profile.
        """
        # Validate uniqueness
        self._validate_employee_id_unique(data.employee_id)
        self._validate_email_unique(data.email)
        
        # Validate foreign key references
        self._validate_references(
            department_id=data.department_id,
            manager_id=data.manager_id,
            location_id=data.location_id,
            work_schedule_id=data.work_schedule_id,
        )
        
        # Create employee instance
        employee = Employee(
            employee_id=data.employee_id,
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            middle_name=data.middle_name,
            preferred_name=data.preferred_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            personal_email=data.personal_email,
            phone_number=data.phone_number,
            mobile_number=data.mobile_number,
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            city=data.city,
            state_province=data.state_province,
            postal_code=data.postal_code,
            country=data.country,
            department_id=data.department_id,
            manager_id=data.manager_id,
            location_id=data.location_id,
            work_schedule_id=data.work_schedule_id,
            job_title=data.job_title,
            employment_type=data.employment_type.value if data.employment_type else None,
            employment_status=data.employment_status.value,
            hire_date=data.hire_date,
            termination_date=data.termination_date,
            salary=data.salary,
            hourly_rate=data.hourly_rate,
        )
        
        try:
            self.session.add(employee)
            self.session.flush()  # Get the employee ID
            
            # Create audit trail
            audit_context = AuditContext(
                user_id=current_user.id,
                ip_address=current_user.ip_address,
                user_agent=current_user.user_agent,
                change_reason="Employee created",
            )
            self.audit_service.log_create(
                employee_id=employee.id,
                employee_data=employee.to_dict(),
                context=audit_context,
            )
            
        except IntegrityError as e:
            self.session.rollback()
            raise DatabaseError(f"Failed to create employee: {str(e)}")
        
        # Load relationships and return response
        return self._build_employee_response(employee, current_user)
    
    # =========================================================================
    # Read Operations
    # =========================================================================
    
    def get_employee(
        self,
        employee_id: int,
        current_user: CurrentUser,
    ) -> Dict[str, Any]:
        """
        Get employee by database ID with role-based field filtering.
        
        Raises NotFoundError if employee doesn't exist.
        """
        employee = self._get_employee_with_relations(employee_id)
        
        if employee is None:
            raise create_not_found_error("Employee", employee_id)
        
        return self._build_employee_response(employee, current_user)
    
    def get_employee_by_employee_id(
        self,
        employee_id_str: str,
        current_user: CurrentUser,
    ) -> Dict[str, Any]:
        """
        Get employee by employee_id string with role-based field filtering.
        
        Raises NotFoundError if employee doesn't exist.
        """
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
                joinedload(Employee.manager),
                joinedload(Employee.work_schedule),
            )
            .where(Employee.employee_id == employee_id_str)
        )
        employee = self.session.execute(stmt).scalar_one_or_none()
        
        if employee is None:
            raise create_not_found_error("Employee", employee_id_str)
        
        return self._build_employee_response(employee, current_user)
    
    # =========================================================================
    # Directory Operations
    # =========================================================================
    
    def get_directory(
        self,
        current_user: CurrentUser,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        department_id: Optional[int] = None,
        location_id: Optional[int] = None,
        status: Optional[str] = None,
        sort_by: str = "last_name",
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """
        Get paginated employee directory with filtering and sorting.
        
        Applies role-based visibility controls to show only employees
        the requesting user is authorized to view.
        """
        # Validate and constrain pagination
        settings = self.settings.pagination
        page_size = max(settings.min_page_size, min(page_size, settings.max_page_size))
        page = max(1, page)
        
        # Get visible employee IDs based on user's role and hierarchy
        visible_ids = self.repository.get_visible_employee_ids(
            user_employee_id=current_user.employee_id,
            user_roles=[r.value for r in current_user.roles],
            max_hierarchy_depth=self.settings.access_control.max_hierarchy_depth,
        )
        
        # Build filter and sort params
        filters = SearchFilters(
            query=search,
            department_id=department_id,
            location_id=location_id,
            employment_status=status or "active",
            is_active=True if status == "active" else None,
        )
        
        pagination = PaginationParams(page=page, page_size=page_size)
        sort = SortParams(field=sort_by, order=sort_order)
        
        # Get employees
        employees, total_count = self.repository.get_directory(
            pagination=pagination,
            sort=sort,
            filters=filters,
            visible_employee_ids=visible_ids,
        )
        
        # Build response
        return {
            "data": [
                self._build_employee_response(emp, current_user)
                for emp in employees
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
            },
        }
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    def search_employees(
        self,
        current_user: CurrentUser,
        query: str = "",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        fuzzy: bool = True,
    ) -> Dict[str, Any]:
        """
        Search employees with optional fuzzy matching.
        
        Returns results ranked by relevance score.
        Applies role-based visibility controls.
        """
        # Validate limit
        settings = self.settings.search
        limit = max(1, min(limit, settings.max_limit))
        
        # Get visible employee IDs
        visible_ids = self.repository.get_visible_employee_ids(
            user_employee_id=current_user.employee_id,
            user_roles=[r.value for r in current_user.roles],
            max_hierarchy_depth=self.settings.access_control.max_hierarchy_depth,
        )
        
        # Build search filters
        search_filters = SearchFilters(
            department_id=filters.get("department") if filters else None,
            location_id=filters.get("location") if filters else None,
            employment_status=filters.get("status") if filters else None,
            employment_type=filters.get("employment_type") if filters else None,
            hire_date_from=filters.get("hire_date_from") if filters else None,
            hire_date_to=filters.get("hire_date_to") if filters else None,
        )
        
        # Execute search
        results = self.repository.search_employees(
            query=query,
            filters=search_filters,
            limit=limit,
            fuzzy=fuzzy,
            visible_employee_ids=visible_ids,
        )
        
        # Build response with relevance scores
        return {
            "data": [
                {
                    **self._build_employee_response(r.employee, current_user),
                    "relevance_score": r.relevance_score,
                }
                for r in results
            ],
            "total": len(results),
            "query": query,
        }
    
    def get_search_suggestions(
        self,
        current_user: CurrentUser,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get search suggestions based on partial query.
        
        Returns basic employee info for autocomplete.
        """
        if not query or len(query) < 2:
            return []
        
        # Get visible employee IDs
        visible_ids = self.repository.get_visible_employee_ids(
            user_employee_id=current_user.employee_id,
            user_roles=[r.value for r in current_user.roles],
            max_hierarchy_depth=self.settings.access_control.max_hierarchy_depth,
        )
        
        # Get suggestions
        employees = self.repository.get_search_suggestions(
            query=query,
            limit=limit,
            visible_employee_ids=visible_ids,
        )
        
        # Return basic info for suggestions
        return [
            {
                "id": emp.id,
                "employee_id": emp.employee_id,
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "preferred_name": emp.preferred_name,
                "job_title": emp.job_title,
                "email": emp.email,
                "department": {
                    "id": emp.department.id,
                    "name": emp.department.name,
                } if emp.department else None,
                "display_text": f"{emp.first_name} {emp.last_name}",
            }
            for emp in employees
        ]
    
    def get_departments(self) -> List[Dict[str, Any]]:
        """Get all active departments for filtering."""
        departments = self.repository.get_departments(active_only=True)
        return [
            {
                "id": dept.id,
                "code": dept.code,
                "name": dept.name,
            }
            for dept in departments
        ]
    
    def get_locations(self) -> List[Dict[str, Any]]:
        """Get all active locations for filtering."""
        locations = self.repository.get_locations(active_only=True)
        return [
            {
                "id": loc.id,
                "code": loc.code,
                "name": loc.name,
            }
            for loc in locations
        ]
    
    # =========================================================================
    # Update Operations
    # =========================================================================
    
    def update_employee(
        self,
        employee_id: int,
        data: EmployeeUpdateRequest,
        current_user: CurrentUser,
    ) -> Dict[str, Any]:
        """
        Update an employee profile.
        
        Only updates provided fields. Validates uniqueness and references.
        Creates audit trail for all changes.
        """
        employee = self._get_employee_with_relations(employee_id)
        
        if employee is None:
            raise create_not_found_error("Employee", employee_id)
        
        # Store old values for audit
        old_data = employee.to_dict()
        
        # Get update data (only non-None values)
        update_data = data.model_dump(exclude_unset=True)
        
        # Validate field-level permissions
        field_errors = []
        for field_name in update_data.keys():
            if not current_user.can_edit_field(field_name):
                field_errors.append(create_field_error(
                    field=field_name,
                    message=f"You don't have permission to edit this field",
                    code="forbidden",
                ))
        
        if field_errors:
            raise create_validation_error(field_errors)
        
        # Validate uniqueness for employee_id and email if being changed
        if "employee_id" in update_data and update_data["employee_id"] != employee.employee_id:
            self._validate_employee_id_unique(update_data["employee_id"], exclude_id=employee.id)
        
        if "email" in update_data and update_data["email"] != employee.email:
            self._validate_email_unique(update_data["email"], exclude_id=employee.id)
        
        # Validate foreign key references
        self._validate_references(
            department_id=update_data.get("department_id"),
            manager_id=update_data.get("manager_id"),
            location_id=update_data.get("location_id"),
            work_schedule_id=update_data.get("work_schedule_id"),
        )
        
        # Apply updates
        for field_name, value in update_data.items():
            if hasattr(employee, field_name):
                # Handle enum conversion
                if field_name in ("employment_type", "employment_status") and value is not None:
                    value = value.value if hasattr(value, "value") else value
                setattr(employee, field_name, value)
        
        try:
            self.session.flush()
            
            # Create audit trail
            audit_context = AuditContext(
                user_id=current_user.id,
                ip_address=current_user.ip_address,
                user_agent=current_user.user_agent,
                change_reason="Employee updated",
            )
            self.audit_service.log_update(
                employee_id=employee.id,
                old_data=old_data,
                new_data=employee.to_dict(),
                context=audit_context,
            )
            
        except IntegrityError as e:
            self.session.rollback()
            raise DatabaseError(f"Failed to update employee: {str(e)}")
        
        # Reload relationships and return response
        self.session.refresh(employee)
        return self._build_employee_response(employee, current_user)
    
    # =========================================================================
    # Delete/Terminate Operations
    # =========================================================================
    
    def terminate_employee(
        self,
        employee_id: int,
        termination_date: Optional[date],
        current_user: CurrentUser,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Terminate an employee by updating status and archiving.
        
        Sets employment_status to 'terminated', sets is_active to False,
        and records termination_date. Preserves historical records.
        """
        employee = self._get_employee_with_relations(employee_id)
        
        if employee is None:
            raise create_not_found_error("Employee", employee_id)
        
        # Check if already terminated
        if employee.employment_status == "terminated":
            raise ValidationError(
                message="Employee is already terminated",
                details={"employee_id": employee_id},
            )
        
        # Store old values for audit
        old_data = employee.to_dict()
        
        # Update termination fields
        employee.employment_status = "terminated"
        employee.is_active = False
        employee.termination_date = termination_date or date.today()
        
        try:
            self.session.flush()
            
            # Create audit trail
            audit_context = AuditContext(
                user_id=current_user.id,
                ip_address=current_user.ip_address,
                user_agent=current_user.user_agent,
                change_reason=reason or "Employee terminated",
            )
            self.audit_service.log_update(
                employee_id=employee.id,
                old_data=old_data,
                new_data=employee.to_dict(),
                context=audit_context,
            )
            
        except IntegrityError as e:
            self.session.rollback()
            raise DatabaseError(f"Failed to terminate employee: {str(e)}")
        
        return self._build_employee_response(employee, current_user)
    
    # =========================================================================
    # Validation Helpers
    # =========================================================================
    
    def _validate_employee_id_unique(
        self,
        employee_id: str,
        exclude_id: Optional[int] = None,
    ) -> None:
        """Validate that employee_id is unique."""
        stmt = select(Employee).where(Employee.employee_id == employee_id)
        
        if exclude_id is not None:
            stmt = stmt.where(Employee.id != exclude_id)
        
        existing = self.session.execute(stmt).scalar_one_or_none()
        
        if existing is not None:
            raise create_duplicate_error("Employee", "employee_id", employee_id)
    
    def _validate_email_unique(
        self,
        email: str,
        exclude_id: Optional[int] = None,
    ) -> None:
        """Validate that email is unique."""
        stmt = select(Employee).where(Employee.email == email)
        
        if exclude_id is not None:
            stmt = stmt.where(Employee.id != exclude_id)
        
        existing = self.session.execute(stmt).scalar_one_or_none()
        
        if existing is not None:
            raise create_duplicate_error("Employee", "email", email)
    
    def _validate_references(
        self,
        department_id: Optional[int] = None,
        manager_id: Optional[int] = None,
        location_id: Optional[int] = None,
        work_schedule_id: Optional[int] = None,
    ) -> None:
        """Validate foreign key references exist."""
        field_errors: list[FieldError] = []
        
        if department_id is not None:
            dept = self.session.get(Department, department_id)
            if dept is None:
                field_errors.append(create_field_error(
                    field="department_id",
                    message=f"Department with ID {department_id} not found",
                    code="not_found",
                ))
        
        if manager_id is not None:
            manager = self.session.get(Employee, manager_id)
            if manager is None:
                field_errors.append(create_field_error(
                    field="manager_id",
                    message=f"Manager with ID {manager_id} not found",
                    code="not_found",
                ))
        
        if location_id is not None:
            location = self.session.get(Location, location_id)
            if location is None:
                field_errors.append(create_field_error(
                    field="location_id",
                    message=f"Location with ID {location_id} not found",
                    code="not_found",
                ))
        
        if work_schedule_id is not None:
            schedule = self.session.get(WorkSchedule, work_schedule_id)
            if schedule is None:
                field_errors.append(create_field_error(
                    field="work_schedule_id",
                    message=f"Work schedule with ID {work_schedule_id} not found",
                    code="not_found",
                ))
        
        if field_errors:
            raise create_validation_error(field_errors)
    
    # =========================================================================
    # Response Building Helpers
    # =========================================================================
    
    def _get_employee_with_relations(self, employee_id: int) -> Optional[Employee]:
        """Load employee with all relationships."""
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
                joinedload(Employee.manager),
                joinedload(Employee.work_schedule),
            )
            .where(Employee.id == employee_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def _build_employee_response(
        self,
        employee: Employee,
        current_user: CurrentUser,
    ) -> Dict[str, Any]:
        """Build employee response with role-based field filtering."""
        # Convert to dict
        response_data = {
            "id": employee.id,
            "employee_id": employee.employee_id,
            "email": employee.email,
            "first_name": employee.first_name,
            "middle_name": employee.middle_name,
            "last_name": employee.last_name,
            "preferred_name": employee.preferred_name,
            "date_of_birth": employee.date_of_birth,
            "gender": employee.gender,
            "personal_email": employee.personal_email,
            "phone_number": employee.phone_number,
            "mobile_number": employee.mobile_number,
            "address_line1": employee.address_line1,
            "address_line2": employee.address_line2,
            "city": employee.city,
            "state_province": employee.state_province,
            "postal_code": employee.postal_code,
            "country": employee.country,
            "job_title": employee.job_title,
            "employment_type": employee.employment_type,
            "employment_status": employee.employment_status,
            "hire_date": employee.hire_date,
            "termination_date": employee.termination_date,
            "salary": employee.salary,
            "hourly_rate": employee.hourly_rate,
            "is_active": employee.is_active,
            "created_at": employee.created_at,
            "updated_at": employee.updated_at,
        }
        
        # Add nested relationships
        if employee.department:
            response_data["department"] = {
                "id": employee.department.id,
                "code": employee.department.code,
                "name": employee.department.name,
                "description": employee.department.description,
                "parent_department_id": employee.department.parent_department_id,
                "is_active": employee.department.is_active,
            }
        else:
            response_data["department"] = None
        
        if employee.location:
            response_data["location"] = {
                "id": employee.location.id,
                "code": employee.location.code,
                "name": employee.location.name,
                "address_line1": employee.location.address_line1,
                "address_line2": employee.location.address_line2,
                "city": employee.location.city,
                "state_province": employee.location.state_province,
                "postal_code": employee.location.postal_code,
                "country": employee.location.country,
                "timezone": employee.location.timezone,
                "is_active": employee.location.is_active,
            }
        else:
            response_data["location"] = None
        
        if employee.manager:
            response_data["manager"] = {
                "id": employee.manager.id,
                "employee_id": employee.manager.employee_id,
                "email": employee.manager.email,
                "first_name": employee.manager.first_name,
                "last_name": employee.manager.last_name,
                "preferred_name": employee.manager.preferred_name,
                "job_title": employee.manager.job_title,
            }
        else:
            response_data["manager"] = None
        
        if employee.work_schedule:
            response_data["work_schedule"] = {
                "id": employee.work_schedule.id,
                "name": employee.work_schedule.name,
                "description": employee.work_schedule.description,
                "hours_per_week": employee.work_schedule.hours_per_week,
                "days_per_week": employee.work_schedule.days_per_week,
                "start_time": employee.work_schedule.start_time,
                "end_time": employee.work_schedule.end_time,
                "is_flexible": employee.work_schedule.is_flexible,
                "is_active": employee.work_schedule.is_active,
            }
        else:
            response_data["work_schedule"] = None
        
        # Apply role-based field filtering
        return filter_employee_response(response_data, current_user)

