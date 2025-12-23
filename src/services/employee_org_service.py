"""Service for employee organizational relationship operations."""

from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.models.employee import Department, Employee, Location
from src.schemas.employee_org import (
    DirectReportSummary,
    DirectReportsResponse,
    OrgChartNode,
    OrgChartPeer,
    OrgChartResponse,
)
from src.utils.auth import CurrentUser, UserRole
from src.utils.errors import ForbiddenError, NotFoundError, create_not_found_error


class EmployeeOrgService:
    """
    Service for handling employee organizational relationships.
    
    Provides functionality for:
    - Retrieving direct reports for managers
    - Building organizational chart data up to configurable depth
    - Validating access permissions for organizational data
    """
    
    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session
    
    def get_direct_reports(
        self,
        employee_id: int,
        current_user: CurrentUser,
    ) -> DirectReportsResponse:
        """
        Get direct reports for a manager.
        
        Args:
            employee_id: Database ID of the manager
            current_user: Current authenticated user
            
        Returns:
            DirectReportsResponse with manager info and direct reports list
            
        Raises:
            NotFoundError: If employee not found
            ForbiddenError: If user lacks permission to view this data
        """
        # Get the manager employee
        manager = self._get_employee_with_relations(employee_id)
        if manager is None:
            raise create_not_found_error("Employee", employee_id)
        
        # Check permissions
        self._check_org_view_permission(manager, current_user)
        
        # Get direct reports
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
            )
            .where(Employee.manager_id == employee_id)
            .where(Employee.is_active == True)
            .order_by(Employee.last_name, Employee.first_name)
        )
        
        result = self.session.execute(stmt)
        direct_reports = list(result.scalars().unique())
        
        # Build response
        return DirectReportsResponse(
            manager_id=manager.id,
            manager_employee_id=manager.employee_id,
            manager_name=f"{manager.first_name} {manager.last_name}",
            total_direct_reports=len(direct_reports),
            direct_reports=[
                self._build_direct_report_summary(emp)
                for emp in direct_reports
            ],
        )
    
    def get_org_chart(
        self,
        employee_id: int,
        current_user: CurrentUser,
        depth: int = 3,
    ) -> OrgChartResponse:
        """
        Get organizational chart data for an employee.
        
        Args:
            employee_id: Database ID of the root employee
            current_user: Current authenticated user
            depth: How many levels deep to traverse (default 3)
            
        Returns:
            OrgChartResponse with hierarchy data
            
        Raises:
            NotFoundError: If employee not found
            ForbiddenError: If user lacks permission to view this data
        """
        # Clamp depth to reasonable limits
        depth = max(1, min(depth, 5))
        
        # Get the root employee
        root_employee = self._get_employee_with_relations(employee_id)
        if root_employee is None:
            raise create_not_found_error("Employee", employee_id)
        
        # Check permissions
        self._check_org_view_permission(root_employee, current_user)
        
        # Build manager chain (going up)
        manager_chain = self._build_manager_chain(root_employee)
        
        # Get peers (other direct reports of same manager)
        peers = self._get_peers(root_employee)
        
        # Build hierarchy tree (going down)
        hierarchy = self._build_org_tree(root_employee, current_depth=0, max_depth=depth)
        
        # Build self node
        self_node = self._build_org_chart_node(root_employee, level=0, relationship="self")
        
        # Count total nodes
        total_nodes = self._count_nodes(hierarchy)
        
        return OrgChartResponse(
            root_employee_id=root_employee.id,
            root_employee_name=f"{root_employee.first_name} {root_employee.last_name}",
            depth=depth,
            total_nodes=total_nodes,
            manager_chain=manager_chain,
            self_node=self_node,
            peers=peers,
            hierarchy=hierarchy,
        )
    
    def _get_employee_with_relations(self, employee_id: int) -> Optional[Employee]:
        """Load employee with relationships."""
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
                joinedload(Employee.manager),
            )
            .where(Employee.id == employee_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def _check_org_view_permission(
        self,
        target_employee: Employee,
        current_user: CurrentUser,
    ) -> None:
        """
        Check if user has permission to view organizational data for an employee.
        
        Admin and HR managers can view anyone.
        Managers can view their own team.
        Employees can view their own manager chain and direct peers.
        """
        # Admin and HR managers can view all
        if current_user.has_role(UserRole.ADMIN) or current_user.has_role(UserRole.HR_MANAGER):
            return
        
        # Check if viewing own data
        if current_user.employee_id == target_employee.id:
            return
        
        # Managers can view their direct reports' org data
        if current_user.has_role(UserRole.MANAGER):
            # Check if target is in manager's reporting chain
            if self._is_in_reporting_chain(target_employee, current_user.employee_id):
                return
        
        # Check if target is in user's manager chain
        if self._is_manager_of(target_employee.id, current_user.employee_id):
            return
        
        # Check if target is a peer (same manager)
        if current_user.employee_id:
            user_emp = self.session.get(Employee, current_user.employee_id)
            if user_emp and user_emp.manager_id == target_employee.manager_id:
                return
        
        raise ForbiddenError(
            message="You don't have permission to view this organizational data",
            details={"employee_id": target_employee.id},
        )
    
    def _is_in_reporting_chain(
        self,
        employee: Employee,
        manager_id: Optional[int],
        max_depth: int = 10,
    ) -> bool:
        """Check if employee is in the reporting chain under a manager."""
        if manager_id is None:
            return False
        
        current = employee
        depth = 0
        
        while current and depth < max_depth:
            if current.manager_id == manager_id:
                return True
            if current.manager_id:
                current = self.session.get(Employee, current.manager_id)
            else:
                break
            depth += 1
        
        return False
    
    def _is_manager_of(
        self,
        potential_manager_id: int,
        employee_id: Optional[int],
        max_depth: int = 10,
    ) -> bool:
        """Check if potential_manager is in the manager chain of employee."""
        if employee_id is None:
            return False
        
        current_id = employee_id
        depth = 0
        
        while current_id and depth < max_depth:
            emp = self.session.get(Employee, current_id)
            if emp is None:
                break
            if emp.manager_id == potential_manager_id:
                return True
            current_id = emp.manager_id
            depth += 1
        
        return False
    
    def _build_direct_report_summary(self, employee: Employee) -> DirectReportSummary:
        """Build a direct report summary from an employee."""
        return DirectReportSummary(
            id=employee.id,
            employee_id=employee.employee_id,
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            preferred_name=employee.preferred_name,
            job_title=employee.job_title,
            department=self._build_department_dict(employee.department) if employee.department else None,
            location=self._build_location_dict(employee.location) if employee.location else None,
            hire_date=employee.hire_date,
            employment_status=employee.employment_status,
            reporting_start_date=employee.hire_date,  # Using hire_date as proxy
            is_active=employee.is_active,
        )
    
    def _build_org_chart_node(
        self,
        employee: Employee,
        level: int,
        relationship: str,
    ) -> OrgChartNode:
        """Build an org chart node from an employee."""
        return OrgChartNode(
            id=employee.id,
            employee_id=employee.employee_id,
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            preferred_name=employee.preferred_name,
            job_title=employee.job_title,
            department=self._build_department_dict(employee.department) if employee.department else None,
            location=self._build_location_dict(employee.location) if employee.location else None,
            hire_date=employee.hire_date,
            is_active=employee.is_active,
            level=level,
            relationship=relationship,
            children=[],
        )
    
    def _build_manager_chain(self, employee: Employee) -> List[OrgChartNode]:
        """Build the manager chain going up from an employee."""
        chain: List[OrgChartNode] = []
        current = employee
        level = -1  # Managers are above the employee
        
        while current.manager_id is not None:
            manager = self._get_employee_with_relations(current.manager_id)
            if manager is None:
                break
            
            chain.append(self._build_org_chart_node(manager, level, "manager"))
            current = manager
            level -= 1
        
        # Reverse so top of chain is first
        chain.reverse()
        
        # Update levels to be positive (0 = top)
        for i, node in enumerate(chain):
            node.level = i
        
        return chain
    
    def _get_peers(self, employee: Employee) -> List[OrgChartPeer]:
        """Get peers (employees with the same manager)."""
        if employee.manager_id is None:
            return []
        
        stmt = (
            select(Employee)
            .options(joinedload(Employee.department))
            .where(Employee.manager_id == employee.manager_id)
            .where(Employee.id != employee.id)
            .where(Employee.is_active == True)
            .order_by(Employee.last_name, Employee.first_name)
        )
        
        result = self.session.execute(stmt)
        peers = list(result.scalars().unique())
        
        return [
            OrgChartPeer(
                id=peer.id,
                employee_id=peer.employee_id,
                first_name=peer.first_name,
                last_name=peer.last_name,
                job_title=peer.job_title,
                department=self._build_department_dict(peer.department) if peer.department else None,
            )
            for peer in peers
        ]
    
    def _build_org_tree(
        self,
        employee: Employee,
        current_depth: int,
        max_depth: int,
    ) -> OrgChartNode:
        """
        Build organizational tree recursively.
        
        Args:
            employee: Root employee for this subtree
            current_depth: Current depth level
            max_depth: Maximum depth to traverse
            
        Returns:
            OrgChartNode with children populated
        """
        node = self._build_org_chart_node(
            employee,
            level=current_depth,
            relationship="self" if current_depth == 0 else "direct_report",
        )
        
        # Stop if we've reached max depth
        if current_depth >= max_depth:
            return node
        
        # Get direct reports
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
            )
            .where(Employee.manager_id == employee.id)
            .where(Employee.is_active == True)
            .order_by(Employee.last_name, Employee.first_name)
        )
        
        result = self.session.execute(stmt)
        direct_reports = list(result.scalars().unique())
        
        # Recursively build children
        node.children = [
            self._build_org_tree(dr, current_depth + 1, max_depth)
            for dr in direct_reports
        ]
        
        return node
    
    def _count_nodes(self, node: OrgChartNode) -> int:
        """Count total nodes in a tree."""
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count
    
    def _build_department_dict(self, department: Department) -> Dict[str, Any]:
        """Build department dictionary."""
        return {
            "id": department.id,
            "code": department.code,
            "name": department.name,
            "description": department.description,
        }
    
    def _build_location_dict(self, location: Location) -> Dict[str, Any]:
        """Build location dictionary."""
        return {
            "id": location.id,
            "code": location.code,
            "name": location.name,
            "city": location.city,
            "country": location.country,
        }

