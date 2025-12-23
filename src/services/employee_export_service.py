"""Service for employee CSV export operations."""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from src.config.settings import get_settings
from src.models.employee import Department, Employee, Location
from src.schemas.employee_export import (
    AvailableExportFieldsResponse,
    ExportableField,
    ExportFieldSelection,
    ExportFilters,
    ExportRequest,
    ExportResponse,
)
from src.utils.audit_logger import ImportExportAuditContext, ImportExportAuditLogger
from src.utils.auth import CurrentUser, ROLE_VIEWABLE_FIELDS, UserRole
from src.utils.csv_parser import generate_csv_content


logger = logging.getLogger(__name__)


# Field metadata for exports
FIELD_METADATA: Dict[str, Dict[str, Any]] = {
    "id": {"display_name": "ID", "data_type": "integer", "is_sensitive": False},
    "employee_id": {"display_name": "Employee ID", "data_type": "string", "is_sensitive": False},
    "email": {"display_name": "Work Email", "data_type": "email", "is_sensitive": False},
    "first_name": {"display_name": "First Name", "data_type": "string", "is_sensitive": False},
    "middle_name": {"display_name": "Middle Name", "data_type": "string", "is_sensitive": False},
    "last_name": {"display_name": "Last Name", "data_type": "string", "is_sensitive": False},
    "preferred_name": {"display_name": "Preferred Name", "data_type": "string", "is_sensitive": False},
    "date_of_birth": {"display_name": "Date of Birth", "data_type": "date", "is_sensitive": True},
    "gender": {"display_name": "Gender", "data_type": "string", "is_sensitive": True},
    "personal_email": {"display_name": "Personal Email", "data_type": "email", "is_sensitive": True},
    "phone_number": {"display_name": "Phone Number", "data_type": "phone", "is_sensitive": True},
    "mobile_number": {"display_name": "Mobile Number", "data_type": "phone", "is_sensitive": True},
    "address_line1": {"display_name": "Address Line 1", "data_type": "string", "is_sensitive": True},
    "address_line2": {"display_name": "Address Line 2", "data_type": "string", "is_sensitive": True},
    "city": {"display_name": "City", "data_type": "string", "is_sensitive": False},
    "state_province": {"display_name": "State/Province", "data_type": "string", "is_sensitive": False},
    "postal_code": {"display_name": "Postal Code", "data_type": "string", "is_sensitive": False},
    "country": {"display_name": "Country", "data_type": "string", "is_sensitive": False},
    "department_id": {"display_name": "Department ID", "data_type": "integer", "is_sensitive": False},
    "manager_id": {"display_name": "Manager ID", "data_type": "integer", "is_sensitive": False},
    "location_id": {"display_name": "Location ID", "data_type": "integer", "is_sensitive": False},
    "work_schedule_id": {"display_name": "Work Schedule ID", "data_type": "integer", "is_sensitive": False},
    "job_title": {"display_name": "Job Title", "data_type": "string", "is_sensitive": False},
    "employment_type": {"display_name": "Employment Type", "data_type": "string", "is_sensitive": False},
    "employment_status": {"display_name": "Employment Status", "data_type": "string", "is_sensitive": False},
    "hire_date": {"display_name": "Hire Date", "data_type": "date", "is_sensitive": False},
    "termination_date": {"display_name": "Termination Date", "data_type": "date", "is_sensitive": False},
    "salary": {"display_name": "Salary", "data_type": "decimal", "is_sensitive": True},
    "hourly_rate": {"display_name": "Hourly Rate", "data_type": "decimal", "is_sensitive": True},
    "is_active": {"display_name": "Is Active", "data_type": "boolean", "is_sensitive": False},
    "created_at": {"display_name": "Created At", "data_type": "datetime", "is_sensitive": False},
    "updated_at": {"display_name": "Updated At", "data_type": "datetime", "is_sensitive": False},
}

# Default fields to export if none specified
DEFAULT_EXPORT_FIELDS = [
    "employee_id",
    "email",
    "first_name",
    "last_name",
    "job_title",
    "department_id",
    "employment_status",
    "hire_date",
]


class EmployeeExportService:
    """
    Service for handling employee CSV export operations.
    
    Provides functionality for:
    - Generating CSV exports with customizable fields
    - Applying role-based access controls to field visibility
    - Filtering employees based on various criteria
    - Audit logging of export operations
    """
    
    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session
        self.settings = get_settings()
        self.audit_logger = ImportExportAuditLogger(session)
    
    def get_available_fields(
        self,
        current_user: CurrentUser,
    ) -> AvailableExportFieldsResponse:
        """
        Get list of fields available for export based on user permissions.
        """
        viewable_fields = current_user.get_viewable_fields()
        
        available_fields: List[ExportableField] = []
        
        for field_name, metadata in FIELD_METADATA.items():
            if field_name in viewable_fields:
                available_fields.append(ExportableField(
                    name=field_name,
                    display_name=metadata["display_name"],
                    description=f"Employee {metadata['display_name'].lower()}",
                    data_type=metadata["data_type"],
                    is_sensitive=metadata["is_sensitive"],
                ))
        
        return AvailableExportFieldsResponse(
            fields=available_fields,
            total_fields=len(available_fields),
            user_role=current_user.primary_role.value,
        )
    
    def export_employees(
        self,
        current_user: CurrentUser,
        request: ExportRequest,
    ) -> tuple[bytes, ExportResponse]:
        """
        Export employees to CSV format.
        
        Returns:
            Tuple of (CSV content bytes, export response metadata)
        """
        start_time = time.time()
        
        # Log export start
        audit_context = ImportExportAuditContext(
            user_id=current_user.id,
            operation_type="export",
            ip_address=current_user.ip_address,
            user_agent=current_user.user_agent,
        )
        
        filters_dict = request.filters.model_dump() if request.filters else None
        fields_list = request.field_selection.fields if request.field_selection else None
        
        self.audit_logger.log_export_started(
            context=audit_context,
            filters=filters_dict,
            fields=fields_list,
        )
        
        try:
            # Determine which fields to export
            export_fields = self._determine_export_fields(
                current_user=current_user,
                field_selection=request.field_selection,
            )
            
            # Query employees with filters
            employees = self._query_employees(
                current_user=current_user,
                filters=request.filters,
            )
            
            # Convert employees to dictionaries
            employee_data = [
                self._employee_to_dict(emp, export_fields)
                for emp in employees
            ]
            
            # Generate CSV content
            csv_content = generate_csv_content(
                data=employee_data,
                fields=export_fields,
                include_headers=request.include_headers,
                delimiter=request.delimiter,
            )
            
            # Generate filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{request.filename_prefix}_{timestamp}.csv"
            
            duration = time.time() - start_time
            
            # Log export completion
            self.audit_logger.log_export_completed(
                context=audit_context,
                total_records=len(employees),
                filename=filename,
                duration_seconds=duration,
            )
            
            response = ExportResponse(
                filename=filename,
                content_type="text/csv",
                total_records=len(employees),
                exported_fields=export_fields,
                filters_applied=filters_dict,
                generated_at=datetime.utcnow(),
                generated_by_user_id=current_user.id,
            )
            
            return csv_content, response
            
        except Exception as e:
            self.audit_logger.log_export_failed(
                context=audit_context,
                error_message=str(e),
            )
            raise
    
    def _determine_export_fields(
        self,
        current_user: CurrentUser,
        field_selection: Optional[ExportFieldSelection],
    ) -> List[str]:
        """
        Determine which fields to include in the export.
        
        Applies role-based access controls to ensure users only export
        fields they are authorized to view.
        """
        viewable_fields = current_user.get_viewable_fields()
        
        if field_selection is None or field_selection.include_all:
            # Use all viewable fields from metadata
            selected_fields = [
                f for f in FIELD_METADATA.keys()
                if f in viewable_fields
            ]
        elif field_selection.fields:
            # Use specified fields, filtered by viewable
            selected_fields = [
                f for f in field_selection.fields
                if f in viewable_fields and f in FIELD_METADATA
            ]
        else:
            # Use defaults, filtered by viewable
            selected_fields = [
                f for f in DEFAULT_EXPORT_FIELDS
                if f in viewable_fields
            ]
        
        # Apply exclusions
        if field_selection and field_selection.exclude_fields:
            selected_fields = [
                f for f in selected_fields
                if f not in field_selection.exclude_fields
            ]
        
        return selected_fields
    
    def _query_employees(
        self,
        current_user: CurrentUser,
        filters: Optional[ExportFilters],
    ) -> List[Employee]:
        """
        Query employees with filters and access controls.
        """
        stmt = select(Employee).options(
            joinedload(Employee.department),
            joinedload(Employee.location),
            joinedload(Employee.manager),
        )
        
        # Build filter conditions
        conditions = []
        
        if filters:
            if filters.department_ids:
                conditions.append(Employee.department_id.in_(filters.department_ids))
            
            if filters.location_ids:
                conditions.append(Employee.location_id.in_(filters.location_ids))
            
            if filters.employment_status:
                conditions.append(Employee.employment_status.in_(filters.employment_status))
            
            if filters.employment_type:
                conditions.append(Employee.employment_type.in_(filters.employment_type))
            
            if filters.hire_date_from:
                conditions.append(Employee.hire_date >= filters.hire_date_from)
            
            if filters.hire_date_to:
                conditions.append(Employee.hire_date <= filters.hire_date_to)
            
            if filters.manager_ids:
                conditions.append(Employee.manager_id.in_(filters.manager_ids))
            
            if filters.is_active is not None:
                conditions.append(Employee.is_active == filters.is_active)
            
            if filters.search_query:
                search_term = f"%{filters.search_query}%"
                conditions.append(or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.email.ilike(search_term),
                    Employee.employee_id.ilike(search_term),
                ))
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Apply visibility controls based on role
        if not current_user.has_role(UserRole.ADMIN) and not current_user.has_role(UserRole.HR_MANAGER):
            # Non-admin users can only see active employees
            stmt = stmt.where(Employee.is_active == True)
            
            # Managers can only see their direct reports
            if current_user.has_role(UserRole.MANAGER) and current_user.employee_id:
                stmt = stmt.where(Employee.manager_id == current_user.employee_id)
        
        # Order by name for consistent exports
        stmt = stmt.order_by(Employee.last_name, Employee.first_name)
        
        result = self.session.execute(stmt)
        return list(result.scalars().unique())
    
    def _employee_to_dict(
        self,
        employee: Employee,
        fields: List[str],
    ) -> Dict[str, Any]:
        """
        Convert an Employee object to a dictionary with specified fields.
        """
        data: Dict[str, Any] = {}
        
        for field in fields:
            if hasattr(employee, field):
                value = getattr(employee, field)
                data[field] = value
            else:
                data[field] = None
        
        return data

