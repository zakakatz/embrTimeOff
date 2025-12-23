"""Audit logging utilities for import/export operations."""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.import_audit import ActionType, ActorRole, ImportAuditLog


@dataclass
class ImportExportAuditContext:
    """Context information for import/export audit logging."""
    
    user_id: UUID
    operation_type: str  # "import" or "export"
    actor_role: ActorRole = ActorRole.USER
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ImportExportAuditLogger:
    """
    Audit logger for import and export operations.
    
    Records all import/export activities for compliance and troubleshooting.
    """
    
    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session
    
    def _create_audit_log(
        self,
        import_job_id: UUID,
        action_type: ActionType,
        context: ImportExportAuditContext,
        details: Optional[Dict[str, Any]] = None,
    ) -> ImportAuditLog:
        """Create an audit log entry."""
        log = ImportAuditLog(
            import_job_id=import_job_id,
            actor_user_id=context.user_id,
            actor_role=context.actor_role,
            action_type=action_type,
            action_details=details,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )
        self.session.add(log)
        return log
    
    def log_import_created(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
        filename: str,
        file_size: int,
    ) -> ImportAuditLog:
        """Log when an import job is created."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.CREATED,
            context=context,
            details={
                "filename": filename,
                "file_size_bytes": file_size,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_import_uploaded(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
        filename: str,
        file_size: int,
    ) -> ImportAuditLog:
        """Log when a file is uploaded for import."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.UPLOADED,
            context=context,
            details={
                "filename": filename,
                "file_size_bytes": file_size,
                "uploaded_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_import_validated(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
        total_rows: int,
        valid_rows: int,
        error_rows: int,
    ) -> ImportAuditLog:
        """Log when import validation is complete."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.VALIDATED,
            context=context,
            details={
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "error_rows": error_rows,
                "validated_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_import_processing_started(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
        total_rows: int,
    ) -> ImportAuditLog:
        """Log when import processing starts."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.PROCESSING_STARTED,
            context=context,
            details={
                "total_rows": total_rows,
                "started_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_import_completed(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
        successful_rows: int,
        error_rows: int,
        duration_seconds: float,
    ) -> ImportAuditLog:
        """Log when an import job completes successfully."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.PROCESSING_COMPLETED,
            context=context,
            details={
                "successful_rows": successful_rows,
                "error_rows": error_rows,
                "duration_seconds": duration_seconds,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_import_failed(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
        error_message: str,
        processed_rows: int = 0,
    ) -> ImportAuditLog:
        """Log when an import job fails."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.FAILED,
            context=context,
            details={
                "processed_rows": processed_rows,
                "error_message": error_message,
                "failed_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_import_cancelled(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
        reason: Optional[str] = None,
    ) -> ImportAuditLog:
        """Log when an import job is cancelled."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.CANCELLED,
            context=context,
            details={
                "reason": reason,
                "cancelled_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_rollback_requested(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
    ) -> ImportAuditLog:
        """Log when a rollback is requested."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.ROLLBACK_REQUESTED,
            context=context,
            details={
                "requested_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_rollback_completed(
        self,
        import_job_id: UUID,
        context: ImportExportAuditContext,
        rolled_back_records: int,
    ) -> ImportAuditLog:
        """Log when a rollback completes."""
        return self._create_audit_log(
            import_job_id=import_job_id,
            action_type=ActionType.ROLLBACK_COMPLETED,
            context=context,
            details={
                "rolled_back_records": rolled_back_records,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )
    
    def log_export_started(
        self,
        context: ImportExportAuditContext,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Log when an export operation starts.
        
        Note: Exports don't have a job ID, so we return a dict for tracking.
        """
        log_entry = {
            "action": ImportExportAction.EXPORT_STARTED.value,
            "user_id": str(context.user_id),
            "ip_address": context.ip_address,
            "filters_applied": filters,
            "fields_requested": fields,
            "started_at": datetime.utcnow().isoformat(),
        }
        return log_entry
    
    def log_export_completed(
        self,
        context: ImportExportAuditContext,
        total_records: int,
        filename: str,
        duration_seconds: float,
    ) -> Dict[str, Any]:
        """Log when an export operation completes."""
        log_entry = {
            "action": ImportExportAction.EXPORT_COMPLETED.value,
            "user_id": str(context.user_id),
            "ip_address": context.ip_address,
            "total_records": total_records,
            "filename": filename,
            "duration_seconds": duration_seconds,
            "completed_at": datetime.utcnow().isoformat(),
        }
        return log_entry
    
    def log_export_failed(
        self,
        context: ImportExportAuditContext,
        error_message: str,
    ) -> Dict[str, Any]:
        """Log when an export operation fails."""
        log_entry = {
            "action": ImportExportAction.EXPORT_FAILED.value,
            "user_id": str(context.user_id),
            "ip_address": context.ip_address,
            "error_message": error_message,
            "failed_at": datetime.utcnow().isoformat(),
        }
        return log_entry

