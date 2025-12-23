"""
Report Generation Tasks

Background tasks for generating various reports including
employee reports, analytics, and compliance documentation.
"""

import csv
import io
import json
import logging
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.tasks.base import (
    RetryConfig,
    background_task,
    register_task,
)
from src.tasks.email_tasks import send_notification, NotificationType

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Configuration
# =============================================================================

class ReportFormat(str, Enum):
    """Report output formats."""
    
    CSV = "csv"
    JSON = "json"
    XLSX = "xlsx"
    PDF = "pdf"


class ReportType(str, Enum):
    """Types of reports."""
    
    EMPLOYEE_DIRECTORY = "employee_directory"
    TIME_OFF_SUMMARY = "time_off_summary"
    BALANCE_REPORT = "balance_report"
    ACCRUAL_HISTORY = "accrual_history"
    DEPARTMENT_HEADCOUNT = "department_headcount"
    COMPLIANCE_AUDIT = "compliance_audit"
    PAYROLL_EXPORT = "payroll_export"


# Retry configuration for report tasks
REPORT_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    default_retry_delay=120,
    exponential_backoff=True,
    max_backoff_delay=1800,
)


# =============================================================================
# Report Generation Tasks
# =============================================================================

@register_task(
    queue="default",
    description="Generate employee directory report",
    tags=["report", "employee", "directory"],
)
@background_task(
    name="tasks.generate_employee_directory_report",
    queue="default",
    retry_config=REPORT_RETRY_CONFIG,
    soft_time_limit=300,
    time_limit=600,
)
def generate_employee_directory_report(
    requested_by: int,
    format: str = ReportFormat.CSV.value,
    department_ids: Optional[List[int]] = None,
    include_inactive: bool = False,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate employee directory report.
    
    Args:
        requested_by: Employee ID who requested the report
        format: Output format (csv, json, xlsx, pdf)
        department_ids: Filter by departments
        include_inactive: Include inactive employees
        fields: Specific fields to include
    
    Returns:
        Dictionary with report details and download URL
    """
    logger.info(
        f"Generating employee directory report for user {requested_by}"
    )
    
    result = {
        "report_type": ReportType.EMPLOYEE_DIRECTORY.value,
        "requested_by": requested_by,
        "format": format,
        "status": "generating",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "department_ids": department_ids,
            "include_inactive": include_inactive,
            "fields": fields,
        },
    }
    
    # Default fields if not specified
    fields = fields or [
        "employee_id",
        "first_name",
        "last_name",
        "email",
        "department",
        "job_title",
        "location",
        "hire_date",
    ]
    
    # Placeholder: Would query database for employees
    employees = _get_employee_data(department_ids, include_inactive)
    
    # Generate report in requested format
    if format == ReportFormat.CSV.value:
        report_data = _generate_csv(employees, fields)
    elif format == ReportFormat.JSON.value:
        report_data = _generate_json(employees, fields)
    else:
        report_data = _generate_csv(employees, fields)  # Default to CSV
    
    # Store report (would upload to S3 or similar)
    report_id = f"report_{datetime.now(timezone.utc).timestamp()}"
    download_url = f"/api/v1/reports/{report_id}/download"
    
    result.update({
        "status": "completed",
        "report_id": report_id,
        "download_url": download_url,
        "row_count": len(employees),
        "file_size_bytes": len(report_data),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    
    # Notify user that report is ready
    send_notification(
        notification_type=NotificationType.REPORT_READY.value,
        recipient_id=requested_by,
        data={
            "report_name": "Employee Directory Report",
            "download_link": download_url,
        },
    )
    
    logger.info(
        f"Employee directory report completed: {result['row_count']} rows"
    )
    
    return result


@register_task(
    queue="default",
    description="Generate time-off summary report",
    tags=["report", "time-off", "summary"],
)
@background_task(
    name="tasks.generate_time_off_summary_report",
    queue="default",
    retry_config=REPORT_RETRY_CONFIG,
    soft_time_limit=300,
    time_limit=600,
)
def generate_time_off_summary_report(
    requested_by: int,
    start_date: str,
    end_date: str,
    format: str = ReportFormat.CSV.value,
    department_ids: Optional[List[int]] = None,
    group_by: str = "employee",
) -> Dict[str, Any]:
    """
    Generate time-off summary report.
    
    Args:
        requested_by: Employee ID who requested the report
        start_date: Report start date
        end_date: Report end date
        format: Output format
        department_ids: Filter by departments
        group_by: Group by employee, department, or policy
    
    Returns:
        Dictionary with report details
    """
    logger.info(
        f"Generating time-off summary report for {start_date} to {end_date}"
    )
    
    result = {
        "report_type": ReportType.TIME_OFF_SUMMARY.value,
        "requested_by": requested_by,
        "format": format,
        "status": "generating",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "date_range": {
            "start": start_date,
            "end": end_date,
        },
    }
    
    # Placeholder: Would query time-off requests
    time_off_data = _get_time_off_data(start_date, end_date, department_ids)
    
    # Group data as requested
    grouped_data = _group_time_off_data(time_off_data, group_by)
    
    # Generate report
    if format == ReportFormat.CSV.value:
        report_data = _generate_time_off_csv(grouped_data, group_by)
    else:
        report_data = json.dumps(grouped_data, indent=2)
    
    report_id = f"report_{datetime.now(timezone.utc).timestamp()}"
    
    result.update({
        "status": "completed",
        "report_id": report_id,
        "download_url": f"/api/v1/reports/{report_id}/download",
        "total_requests": len(time_off_data),
        "total_hours": sum(r.get("hours", 0) for r in time_off_data),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    
    send_notification(
        notification_type=NotificationType.REPORT_READY.value,
        recipient_id=requested_by,
        data={
            "report_name": "Time-Off Summary Report",
            "download_link": result["download_url"],
        },
    )
    
    return result


@register_task(
    queue="balance_calc",
    description="Generate balance report for all employees",
    tags=["report", "balance"],
)
@background_task(
    name="tasks.generate_balance_report",
    queue="balance_calc",
    retry_config=REPORT_RETRY_CONFIG,
    soft_time_limit=600,
    time_limit=900,
)
def generate_balance_report(
    requested_by: int,
    as_of_date: Optional[str] = None,
    format: str = ReportFormat.CSV.value,
    department_ids: Optional[List[int]] = None,
    policy_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Generate balance report showing all employee balances.
    
    Args:
        requested_by: Employee ID who requested the report
        as_of_date: Balance as of this date (defaults to today)
        format: Output format
        department_ids: Filter by departments
        policy_ids: Filter by policies
    
    Returns:
        Dictionary with report details
    """
    as_of = as_of_date or date.today().isoformat()
    
    logger.info(f"Generating balance report as of {as_of}")
    
    result = {
        "report_type": ReportType.BALANCE_REPORT.value,
        "requested_by": requested_by,
        "as_of_date": as_of,
        "format": format,
        "status": "generating",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Placeholder: Would calculate balances for all employees
    balance_data = _get_balance_data(as_of, department_ids, policy_ids)
    
    report_id = f"report_{datetime.now(timezone.utc).timestamp()}"
    
    result.update({
        "status": "completed",
        "report_id": report_id,
        "download_url": f"/api/v1/reports/{report_id}/download",
        "employee_count": len(balance_data),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    
    return result


@register_task(
    queue="default",
    description="Generate department headcount report",
    tags=["report", "department", "headcount"],
)
@background_task(
    name="tasks.generate_department_headcount_report",
    queue="default",
    retry_config=REPORT_RETRY_CONFIG,
    soft_time_limit=180,
    time_limit=300,
)
def generate_department_headcount_report(
    requested_by: int,
    format: str = ReportFormat.CSV.value,
    include_vacancies: bool = False,
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate department headcount report.
    
    Args:
        requested_by: Employee ID who requested the report
        format: Output format
        include_vacancies: Include open positions
        as_of_date: Headcount as of date
    
    Returns:
        Dictionary with report details
    """
    logger.info("Generating department headcount report")
    
    # Placeholder headcount data
    headcount_data = [
        {"department": "Engineering", "headcount": 45, "contractors": 5, "vacancies": 3},
        {"department": "Sales", "headcount": 30, "contractors": 2, "vacancies": 5},
        {"department": "Marketing", "headcount": 15, "contractors": 3, "vacancies": 1},
        {"department": "HR", "headcount": 8, "contractors": 0, "vacancies": 2},
        {"department": "Finance", "headcount": 12, "contractors": 1, "vacancies": 0},
    ]
    
    report_id = f"report_{datetime.now(timezone.utc).timestamp()}"
    
    return {
        "report_type": ReportType.DEPARTMENT_HEADCOUNT.value,
        "requested_by": requested_by,
        "status": "completed",
        "report_id": report_id,
        "download_url": f"/api/v1/reports/{report_id}/download",
        "total_headcount": sum(d["headcount"] for d in headcount_data),
        "total_contractors": sum(d["contractors"] for d in headcount_data),
        "total_vacancies": sum(d["vacancies"] for d in headcount_data),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


@register_task(
    queue="default",
    description="Generate compliance audit report",
    tags=["report", "compliance", "audit"],
)
@background_task(
    name="tasks.generate_compliance_audit_report",
    queue="default",
    retry_config=REPORT_RETRY_CONFIG,
    soft_time_limit=600,
    time_limit=900,
)
def generate_compliance_audit_report(
    requested_by: int,
    audit_type: str,
    start_date: str,
    end_date: str,
    format: str = ReportFormat.PDF.value,
) -> Dict[str, Any]:
    """
    Generate compliance audit report.
    
    Args:
        requested_by: Employee ID who requested the report
        audit_type: Type of audit (e.g., "data_access", "profile_changes")
        start_date: Audit period start
        end_date: Audit period end
        format: Output format
    
    Returns:
        Dictionary with report details
    """
    logger.info(f"Generating {audit_type} compliance audit report")
    
    report_id = f"audit_{datetime.now(timezone.utc).timestamp()}"
    
    # Placeholder: Would query audit logs
    audit_entries = 1500  # Placeholder count
    
    return {
        "report_type": ReportType.COMPLIANCE_AUDIT.value,
        "audit_type": audit_type,
        "requested_by": requested_by,
        "date_range": {"start": start_date, "end": end_date},
        "status": "completed",
        "report_id": report_id,
        "download_url": f"/api/v1/reports/{report_id}/download",
        "audit_entries": audit_entries,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Scheduled Report Tasks
# =============================================================================

@register_task(
    queue="default",
    description="Generate and distribute scheduled reports",
    tags=["report", "scheduled"],
)
@background_task(
    name="tasks.generate_scheduled_reports",
    queue="default",
    retry_config=REPORT_RETRY_CONFIG,
    soft_time_limit=1800,
    time_limit=3600,
)
def generate_scheduled_reports(
    schedule_type: str = "daily",
) -> Dict[str, Any]:
    """
    Generate all scheduled reports for given schedule type.
    
    Args:
        schedule_type: daily, weekly, or monthly
    
    Returns:
        Dictionary with generation results
    """
    logger.info(f"Generating {schedule_type} scheduled reports")
    
    # Placeholder: Would query scheduled report configurations
    # and generate each report
    
    return {
        "schedule_type": schedule_type,
        "reports_generated": 5,
        "reports_distributed": 5,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Helper Functions
# =============================================================================

def _get_employee_data(
    department_ids: Optional[List[int]],
    include_inactive: bool,
) -> List[Dict[str, Any]]:
    """Get employee data for reports."""
    # Placeholder: Would query from database
    return [
        {
            "employee_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "department": "Engineering",
            "job_title": "Software Engineer",
            "location": "San Francisco",
            "hire_date": "2020-01-15",
        },
        {
            "employee_id": 2,
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane.smith@example.com",
            "department": "Marketing",
            "job_title": "Marketing Manager",
            "location": "New York",
            "hire_date": "2019-06-01",
        },
    ]


def _get_time_off_data(
    start_date: str,
    end_date: str,
    department_ids: Optional[List[int]],
) -> List[Dict[str, Any]]:
    """Get time-off data for reports."""
    # Placeholder
    return [
        {"employee_id": 1, "policy": "PTO", "hours": 40, "status": "approved"},
        {"employee_id": 2, "policy": "Sick", "hours": 16, "status": "approved"},
    ]


def _get_balance_data(
    as_of_date: str,
    department_ids: Optional[List[int]],
    policy_ids: Optional[List[int]],
) -> List[Dict[str, Any]]:
    """Get balance data for reports."""
    # Placeholder
    return [
        {"employee_id": 1, "policy": "PTO", "balance": 80.0},
        {"employee_id": 1, "policy": "Sick", "balance": 40.0},
    ]


def _group_time_off_data(
    data: List[Dict[str, Any]],
    group_by: str,
) -> Dict[str, Any]:
    """Group time-off data."""
    # Placeholder grouping logic
    return {"groups": data}


def _generate_csv(
    data: List[Dict[str, Any]],
    fields: List[str],
) -> str:
    """Generate CSV from data."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()


def _generate_json(
    data: List[Dict[str, Any]],
    fields: List[str],
) -> str:
    """Generate JSON from data."""
    filtered = [{k: v for k, v in item.items() if k in fields} for item in data]
    return json.dumps(filtered, indent=2)


def _generate_time_off_csv(
    data: Dict[str, Any],
    group_by: str,
) -> str:
    """Generate time-off CSV report."""
    # Placeholder
    return "employee_id,policy,hours,status\n1,PTO,40,approved\n"

