"""Employee repository for data access operations."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from src.models.employee import Department, Employee, Location


@dataclass
class PaginationParams:
    """Pagination parameters."""
    
    page: int = 1
    page_size: int = 20
    
    @property
    def offset(self) -> int:
        """Calculate offset from page and page_size."""
        return (self.page - 1) * self.page_size


@dataclass
class SortParams:
    """Sort parameters."""
    
    field: str = "last_name"
    order: str = "asc"  # 'asc' or 'desc'


@dataclass
class SearchFilters:
    """Search filter parameters."""
    
    query: Optional[str] = None
    department_id: Optional[int] = None
    location_id: Optional[int] = None
    employment_status: Optional[str] = None
    employment_type: Optional[str] = None
    hire_date_from: Optional[date] = None
    hire_date_to: Optional[date] = None
    manager_id: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass
class SearchResult:
    """Search result with relevance score."""
    
    employee: Employee
    relevance_score: float = 1.0


class EmployeeRepository:
    """
    Repository for employee data access operations.
    
    Provides methods for querying, searching, and filtering employee data.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session
    
    # =========================================================================
    # Directory/List Operations
    # =========================================================================
    
    def get_directory(
        self,
        pagination: PaginationParams,
        sort: SortParams,
        filters: SearchFilters,
        visible_employee_ids: Optional[List[int]] = None,
    ) -> Tuple[Sequence[Employee], int]:
        """
        Get paginated employee directory.
        
        Args:
            pagination: Pagination parameters
            sort: Sort parameters
            filters: Search filters
            visible_employee_ids: Optional list of employee IDs the user can view
        
        Returns:
            Tuple of (employees, total_count)
        """
        # Base query with eager loading
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
                joinedload(Employee.manager),
            )
        )
        
        # Apply filters
        stmt = self._apply_filters(stmt, filters)
        
        # Apply visibility restrictions
        if visible_employee_ids is not None:
            stmt = stmt.where(Employee.id.in_(visible_employee_ids))
        
        # Get total count before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = self.session.execute(count_stmt).scalar() or 0
        
        # Apply sorting
        stmt = self._apply_sorting(stmt, sort)
        
        # Apply pagination
        stmt = stmt.offset(pagination.offset).limit(pagination.page_size)
        
        employees = self.session.execute(stmt).scalars().unique().all()
        
        return employees, total_count
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    def search_employees(
        self,
        query: str,
        filters: SearchFilters,
        limit: int = 50,
        fuzzy: bool = True,
        visible_employee_ids: Optional[List[int]] = None,
    ) -> List[SearchResult]:
        """
        Search employees with optional fuzzy matching.
        
        Args:
            query: Search query string
            filters: Additional filters
            limit: Maximum results to return
            fuzzy: Whether to use fuzzy matching
            visible_employee_ids: Optional list of visible employee IDs
        
        Returns:
            List of SearchResult with relevance scores
        """
        # Base query
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
                joinedload(Employee.manager),
            )
        )
        
        # Apply text search
        if query:
            search_conditions = self._build_search_conditions(query, fuzzy)
            stmt = stmt.where(or_(*search_conditions))
        
        # Apply additional filters
        stmt = self._apply_filters(stmt, filters)
        
        # Apply visibility restrictions
        if visible_employee_ids is not None:
            stmt = stmt.where(Employee.id.in_(visible_employee_ids))
        
        # Limit results
        stmt = stmt.limit(limit * 2)  # Get extra for scoring/ranking
        
        employees = self.session.execute(stmt).scalars().unique().all()
        
        # Calculate relevance scores and sort
        results = []
        for employee in employees:
            score = self._calculate_relevance_score(employee, query)
            results.append(SearchResult(employee=employee, relevance_score=score))
        
        # Sort by relevance and limit
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]
    
    def get_search_suggestions(
        self,
        query: str,
        limit: int = 5,
        visible_employee_ids: Optional[List[int]] = None,
    ) -> Sequence[Employee]:
        """
        Get search suggestions based on partial query.
        
        Args:
            query: Partial search query
            limit: Maximum suggestions to return
            visible_employee_ids: Optional list of visible employee IDs
        
        Returns:
            List of matching employees
        """
        if not query or len(query) < 2:
            return []
        
        # Build suggestion query - prioritize name matches
        search_pattern = f"%{query}%"
        
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
            )
            .where(
                or_(
                    Employee.first_name.ilike(search_pattern),
                    Employee.last_name.ilike(search_pattern),
                    Employee.preferred_name.ilike(search_pattern),
                    Employee.email.ilike(search_pattern),
                    Employee.employee_id.ilike(search_pattern),
                )
            )
            .where(Employee.is_active == True)
        )
        
        if visible_employee_ids is not None:
            stmt = stmt.where(Employee.id.in_(visible_employee_ids))
        
        stmt = stmt.order_by(Employee.last_name, Employee.first_name).limit(limit)
        
        return self.session.execute(stmt).scalars().unique().all()
    
    # =========================================================================
    # Visibility/Access Control
    # =========================================================================
    
    def get_visible_employee_ids(
        self,
        user_employee_id: Optional[int],
        user_roles: List[str],
        max_hierarchy_depth: int = 10,
    ) -> Optional[List[int]]:
        """
        Get list of employee IDs visible to a user based on organizational hierarchy.
        
        Args:
            user_employee_id: The user's employee ID (if they are an employee)
            user_roles: User's roles
            max_hierarchy_depth: Maximum depth to traverse in hierarchy
        
        Returns:
            List of visible employee IDs, or None if user can see all
        """
        # Admin roles can see all employees
        admin_roles = {"admin", "hr_manager", "hr_admin"}
        if any(role in admin_roles for role in user_roles):
            return None
        
        # If user is not an employee, they can only see basic directory
        if user_employee_id is None:
            # Return only active employees (public directory view)
            stmt = select(Employee.id).where(Employee.is_active == True)
            result = self.session.execute(stmt).scalars().all()
            return list(result)
        
        # Get employees visible based on organizational hierarchy
        visible_ids = set()
        
        # User can always see themselves
        visible_ids.add(user_employee_id)
        
        # Get direct reports (recursive)
        direct_reports = self._get_all_reports(user_employee_id, max_hierarchy_depth)
        visible_ids.update(direct_reports)
        
        # Get manager chain
        manager_chain = self._get_manager_chain(user_employee_id, max_hierarchy_depth)
        visible_ids.update(manager_chain)
        
        # Get peers (employees with same manager)
        peers = self._get_peers(user_employee_id)
        visible_ids.update(peers)
        
        # Get employees in same department
        dept_employees = self._get_department_employees(user_employee_id)
        visible_ids.update(dept_employees)
        
        return list(visible_ids)
    
    def _get_all_reports(
        self,
        manager_id: int,
        max_depth: int,
        current_depth: int = 0,
    ) -> List[int]:
        """Recursively get all direct and indirect reports."""
        if current_depth >= max_depth:
            return []
        
        stmt = select(Employee.id).where(Employee.manager_id == manager_id)
        direct_reports = list(self.session.execute(stmt).scalars().all())
        
        all_reports = list(direct_reports)
        for report_id in direct_reports:
            all_reports.extend(
                self._get_all_reports(report_id, max_depth, current_depth + 1)
            )
        
        return all_reports
    
    def _get_manager_chain(
        self,
        employee_id: int,
        max_depth: int,
    ) -> List[int]:
        """Get the chain of managers up to max_depth."""
        managers = []
        current_id = employee_id
        
        for _ in range(max_depth):
            stmt = select(Employee.manager_id).where(Employee.id == current_id)
            manager_id = self.session.execute(stmt).scalar_one_or_none()
            
            if manager_id is None:
                break
            
            managers.append(manager_id)
            current_id = manager_id
        
        return managers
    
    def _get_peers(self, employee_id: int) -> List[int]:
        """Get employees with the same manager."""
        # First get the employee's manager
        stmt = select(Employee.manager_id).where(Employee.id == employee_id)
        manager_id = self.session.execute(stmt).scalar_one_or_none()
        
        if manager_id is None:
            return []
        
        # Get all employees with the same manager
        stmt = (
            select(Employee.id)
            .where(Employee.manager_id == manager_id)
            .where(Employee.id != employee_id)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def _get_department_employees(self, employee_id: int) -> List[int]:
        """Get employees in the same department."""
        # First get the employee's department
        stmt = select(Employee.department_id).where(Employee.id == employee_id)
        department_id = self.session.execute(stmt).scalar_one_or_none()
        
        if department_id is None:
            return []
        
        # Get all employees in the same department
        stmt = (
            select(Employee.id)
            .where(Employee.department_id == department_id)
            .where(Employee.id != employee_id)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _apply_filters(self, stmt, filters: SearchFilters):
        """Apply search filters to query."""
        conditions = []
        
        if filters.department_id:
            conditions.append(Employee.department_id == filters.department_id)
        
        if filters.location_id:
            conditions.append(Employee.location_id == filters.location_id)
        
        if filters.employment_status:
            conditions.append(Employee.employment_status == filters.employment_status)
        
        if filters.employment_type:
            conditions.append(Employee.employment_type == filters.employment_type)
        
        if filters.hire_date_from:
            conditions.append(Employee.hire_date >= filters.hire_date_from)
        
        if filters.hire_date_to:
            conditions.append(Employee.hire_date <= filters.hire_date_to)
        
        if filters.manager_id:
            conditions.append(Employee.manager_id == filters.manager_id)
        
        if filters.is_active is not None:
            conditions.append(Employee.is_active == filters.is_active)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        return stmt
    
    def _apply_sorting(self, stmt, sort: SortParams):
        """Apply sorting to query."""
        # Map field names to columns
        sort_columns = {
            "last_name": Employee.last_name,
            "first_name": Employee.first_name,
            "email": Employee.email,
            "employee_id": Employee.employee_id,
            "job_title": Employee.job_title,
            "hire_date": Employee.hire_date,
            "department": Employee.department_id,
        }
        
        column = sort_columns.get(sort.field, Employee.last_name)
        
        if sort.order.lower() == "desc":
            column = column.desc()
        else:
            column = column.asc()
        
        return stmt.order_by(column)
    
    def _build_search_conditions(self, query: str, fuzzy: bool):
        """Build search conditions for query."""
        conditions = []
        search_pattern = f"%{query}%"
        
        # Basic ILIKE search
        conditions.extend([
            Employee.first_name.ilike(search_pattern),
            Employee.last_name.ilike(search_pattern),
            Employee.preferred_name.ilike(search_pattern),
            Employee.email.ilike(search_pattern),
            Employee.employee_id.ilike(search_pattern),
            Employee.job_title.ilike(search_pattern),
        ])
        
        # Search in concatenated full name
        conditions.append(
            func.concat(Employee.first_name, " ", Employee.last_name).ilike(search_pattern)
        )
        
        return conditions
    
    def _calculate_relevance_score(self, employee: Employee, query: str) -> float:
        """Calculate relevance score for an employee based on query match."""
        if not query:
            return 1.0
        
        query_lower = query.lower()
        score = 0.0
        
        # Exact matches get highest scores
        if employee.employee_id and employee.employee_id.lower() == query_lower:
            score += 1.0
        if employee.email and employee.email.lower() == query_lower:
            score += 0.9
        
        # Name matches
        full_name = f"{employee.first_name} {employee.last_name}".lower()
        if query_lower in full_name:
            score += 0.8
        if employee.first_name and employee.first_name.lower().startswith(query_lower):
            score += 0.7
        if employee.last_name and employee.last_name.lower().startswith(query_lower):
            score += 0.7
        
        # Partial matches
        if employee.first_name and query_lower in employee.first_name.lower():
            score += 0.5
        if employee.last_name and query_lower in employee.last_name.lower():
            score += 0.5
        if employee.job_title and query_lower in employee.job_title.lower():
            score += 0.4
        if employee.email and query_lower in employee.email.lower():
            score += 0.3
        
        # Normalize score to 0-1 range
        return min(score, 1.0)
    
    # =========================================================================
    # Reference Data
    # =========================================================================
    
    def get_departments(self, active_only: bool = True) -> Sequence[Department]:
        """Get all departments."""
        stmt = select(Department)
        if active_only:
            stmt = stmt.where(Department.is_active == True)
        stmt = stmt.order_by(Department.name)
        return self.session.execute(stmt).scalars().all()
    
    def get_locations(self, active_only: bool = True) -> Sequence[Location]:
        """Get all locations."""
        stmt = select(Location)
        if active_only:
            stmt = stmt.where(Location.is_active == True)
        stmt = stmt.order_by(Location.name)
        return self.session.execute(stmt).scalars().all()

