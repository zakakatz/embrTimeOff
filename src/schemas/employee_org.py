"""Pydantic models for employee organizational relationship endpoints."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DirectReportSummary(BaseModel):
    """Summary information for a direct report."""
    
    id: int = Field(..., description="Employee database ID")
    employee_id: str = Field(..., description="Employee ID string")
    email: str = Field(..., description="Work email address")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred name/nickname")
    job_title: Optional[str] = Field(None, description="Job title/position")
    department: Optional[Dict[str, Any]] = Field(None, description="Department information")
    location: Optional[Dict[str, Any]] = Field(None, description="Location information")
    hire_date: date = Field(..., description="Date of hire")
    employment_status: str = Field(..., description="Employment status")
    reporting_start_date: Optional[date] = Field(
        None,
        description="Date when employee started reporting to this manager"
    )
    is_active: bool = Field(default=True, description="Whether employee is active")


class DirectReportsResponse(BaseModel):
    """Response for direct reports endpoint."""
    
    manager_id: int = Field(..., description="Manager employee database ID")
    manager_employee_id: str = Field(..., description="Manager employee ID string")
    manager_name: str = Field(..., description="Manager full name")
    total_direct_reports: int = Field(..., description="Total number of direct reports")
    direct_reports: List[DirectReportSummary] = Field(
        default_factory=list,
        description="List of direct reports"
    )


class OrgChartPeer(BaseModel):
    """Peer employee in organizational chart."""
    
    id: int = Field(..., description="Employee database ID")
    employee_id: str = Field(..., description="Employee ID string")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    job_title: Optional[str] = Field(None, description="Job title")
    department: Optional[Dict[str, Any]] = Field(None, description="Department info")


class OrgChartNode(BaseModel):
    """A node in the organizational chart hierarchy."""
    
    id: int = Field(..., description="Employee database ID")
    employee_id: str = Field(..., description="Employee ID string")
    email: str = Field(..., description="Work email")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred name")
    job_title: Optional[str] = Field(None, description="Job title")
    department: Optional[Dict[str, Any]] = Field(None, description="Department info")
    location: Optional[Dict[str, Any]] = Field(None, description="Location info")
    hire_date: Optional[date] = Field(None, description="Hire date")
    is_active: bool = Field(default=True, description="Whether employee is active")
    level: int = Field(..., description="Level in the hierarchy (0 = root)")
    relationship: str = Field(..., description="Relationship type: self, manager, direct_report, peer")
    children: List["OrgChartNode"] = Field(
        default_factory=list,
        description="Child nodes (direct reports)"
    )
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True


class OrgChartResponse(BaseModel):
    """Response for organizational chart endpoint."""
    
    root_employee_id: int = Field(..., description="Root employee database ID")
    root_employee_name: str = Field(..., description="Root employee name")
    depth: int = Field(..., description="Depth of hierarchy requested")
    total_nodes: int = Field(..., description="Total nodes in the chart")
    manager_chain: List[OrgChartNode] = Field(
        default_factory=list,
        description="Manager chain above the employee"
    )
    self_node: OrgChartNode = Field(..., description="The requested employee node")
    peers: List[OrgChartPeer] = Field(
        default_factory=list,
        description="Peers (other direct reports of same manager)"
    )
    hierarchy: OrgChartNode = Field(
        ...,
        description="Full hierarchical structure with the employee as root"
    )


# Update forward references
OrgChartNode.model_rebuild()

