"""
Backup Management Service

Provides programmatic interface for Aurora PostgreSQL backup operations,
monitoring, and restoration management.

Author: EMBI DevOps Team
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None  # Allow module to load even without boto3 for development

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Models
# =============================================================================

class BackupStatus(str, Enum):
    """Status of a backup operation."""
    
    AVAILABLE = "available"
    CREATING = "creating"
    DELETING = "deleting"
    FAILED = "failed"
    UNKNOWN = "unknown"


class BackupType(str, Enum):
    """Type of backup."""
    
    AUTOMATED = "automated"
    MANUAL = "manual"
    CROSS_REGION = "cross-region"


class RecoveryObjectives(BaseModel):
    """Recovery objectives configuration."""
    
    rpo_minutes: int = Field(5, description="Recovery Point Objective in minutes")
    rto_hours: int = Field(4, description="Recovery Time Objective in hours")
    retention_days: int = Field(30, description="Backup retention period in days")


class BackupSnapshot(BaseModel):
    """Represents a database backup snapshot."""
    
    snapshot_id: str
    cluster_identifier: str
    snapshot_type: BackupType
    status: BackupStatus
    created_at: datetime
    engine: str
    engine_version: str
    storage_encrypted: bool
    kms_key_id: Optional[str] = None
    allocated_storage_gb: Optional[int] = None
    availability_zones: List[str] = []
    tags: Dict[str, str] = {}


class BackupHealthStatus(BaseModel):
    """Health status of the backup system."""
    
    is_healthy: bool
    last_backup_time: Optional[datetime] = None
    minutes_since_last_backup: Optional[int] = None
    rpo_compliance: bool
    next_scheduled_backup: Optional[datetime] = None
    backup_count_30_days: int = 0
    cross_region_enabled: bool = False
    verification_last_run: Optional[datetime] = None
    verification_status: Optional[str] = None
    alerts: List[str] = []


class RestorationRequest(BaseModel):
    """Request to restore a database backup."""
    
    restoration_type: str = Field(..., description="Type: 'pitr' or 'snapshot'")
    target_cluster_id: str = Field(..., description="Target cluster identifier")
    source_cluster_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    restore_time: Optional[datetime] = None
    use_latest_restorable_time: bool = False
    subnet_group: Optional[str] = None
    security_group_ids: List[str] = []
    tags: Dict[str, str] = {}


class RestorationStatus(BaseModel):
    """Status of a restoration operation."""
    
    restoration_id: str
    status: str
    cluster_identifier: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    endpoint: Optional[str] = None
    error_message: Optional[str] = None
    estimated_completion_minutes: Optional[int] = None


# =============================================================================
# Backup Management Service
# =============================================================================

class BackupManagementService:
    """
    Service for managing Aurora PostgreSQL backups.
    
    Provides functionality for:
    - Monitoring backup health and compliance
    - Creating manual snapshots
    - Initiating point-in-time recovery
    - Managing cross-region replication
    - Tracking restoration operations
    """
    
    def __init__(
        self,
        cluster_identifier: str,
        region: str = "us-east-1",
        dr_region: str = "us-west-2",
        recovery_objectives: Optional[RecoveryObjectives] = None,
    ):
        self.cluster_identifier = cluster_identifier
        self.region = region
        self.dr_region = dr_region
        self.recovery_objectives = recovery_objectives or RecoveryObjectives()
        
        if boto3:
            self.rds_client = boto3.client('rds', region_name=region)
            self.rds_client_dr = boto3.client('rds', region_name=dr_region)
            self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
            self.sns_client = boto3.client('sns', region_name=region)
        else:
            self.rds_client = None
            self.rds_client_dr = None
            self.cloudwatch_client = None
            self.sns_client = None
            logger.warning("boto3 not available - backup operations will be simulated")
    
    def get_backup_health(self) -> BackupHealthStatus:
        """
        Get the current health status of the backup system.
        
        Returns:
            BackupHealthStatus with current backup metrics and compliance info
        """
        alerts = []
        
        try:
            # Get cluster info
            cluster = self._get_cluster_info()
            
            # Get latest backup info
            latest_backup = self._get_latest_snapshot()
            
            # Calculate metrics
            now = datetime.now(timezone.utc)
            last_backup_time = None
            minutes_since_backup = None
            
            if latest_backup:
                last_backup_time = latest_backup.created_at
                minutes_since_backup = int((now - last_backup_time).total_seconds() / 60)
            
            # Check RPO compliance
            rpo_compliance = True
            if minutes_since_backup is not None:
                rpo_compliance = minutes_since_backup <= self.recovery_objectives.rpo_minutes
                if not rpo_compliance:
                    alerts.append(
                        f"RPO violation: Last backup was {minutes_since_backup} minutes ago "
                        f"(limit: {self.recovery_objectives.rpo_minutes} minutes)"
                    )
            else:
                rpo_compliance = False
                alerts.append("No recent backups found")
            
            # Count backups in retention period
            backup_count = self._count_backups_in_period(
                days=self.recovery_objectives.retention_days
            )
            
            # Check cross-region replication
            cross_region_enabled = self._check_cross_region_replication()
            if not cross_region_enabled:
                alerts.append("Cross-region backup replication is not enabled")
            
            # Get verification status
            verification_status = self._get_verification_status()
            
            # Calculate next scheduled backup
            next_backup = self._estimate_next_backup(cluster)
            
            is_healthy = rpo_compliance and len(alerts) == 0
            
            return BackupHealthStatus(
                is_healthy=is_healthy,
                last_backup_time=last_backup_time,
                minutes_since_last_backup=minutes_since_backup,
                rpo_compliance=rpo_compliance,
                next_scheduled_backup=next_backup,
                backup_count_30_days=backup_count,
                cross_region_enabled=cross_region_enabled,
                verification_last_run=verification_status.get('last_run'),
                verification_status=verification_status.get('status'),
                alerts=alerts,
            )
            
        except Exception as e:
            logger.error(f"Error getting backup health: {str(e)}")
            return BackupHealthStatus(
                is_healthy=False,
                rpo_compliance=False,
                alerts=[f"Error checking backup health: {str(e)}"],
            )
    
    def list_snapshots(
        self,
        snapshot_type: Optional[BackupType] = None,
        limit: int = 20,
    ) -> List[BackupSnapshot]:
        """
        List available backup snapshots.
        
        Args:
            snapshot_type: Filter by snapshot type (automated/manual)
            limit: Maximum number of snapshots to return
        
        Returns:
            List of BackupSnapshot objects
        """
        snapshots = []
        
        try:
            params = {
                'DBClusterIdentifier': self.cluster_identifier,
                'MaxRecords': limit,
            }
            
            if snapshot_type:
                params['SnapshotType'] = snapshot_type.value
            
            if self.rds_client:
                response = self.rds_client.describe_db_cluster_snapshots(**params)
                
                for snap in response.get('DBClusterSnapshots', []):
                    snapshots.append(BackupSnapshot(
                        snapshot_id=snap['DBClusterSnapshotIdentifier'],
                        cluster_identifier=snap['DBClusterIdentifier'],
                        snapshot_type=BackupType(snap.get('SnapshotType', 'automated')),
                        status=BackupStatus(snap.get('Status', 'unknown')),
                        created_at=snap['SnapshotCreateTime'],
                        engine=snap['Engine'],
                        engine_version=snap['EngineVersion'],
                        storage_encrypted=snap.get('StorageEncrypted', False),
                        kms_key_id=snap.get('KmsKeyId'),
                        allocated_storage_gb=snap.get('AllocatedStorage'),
                        availability_zones=snap.get('AvailabilityZones', []),
                        tags={t['Key']: t['Value'] for t in snap.get('TagList', [])},
                    ))
            
        except Exception as e:
            logger.error(f"Error listing snapshots: {str(e)}")
        
        return snapshots
    
    def create_manual_snapshot(
        self,
        snapshot_id: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> BackupSnapshot:
        """
        Create a manual backup snapshot.
        
        Args:
            snapshot_id: Identifier for the new snapshot
            tags: Optional tags to apply to the snapshot
        
        Returns:
            BackupSnapshot object for the created snapshot
        """
        try:
            tag_list = [
                {'Key': 'CreatedBy', 'Value': 'BackupManagementService'},
                {'Key': 'Purpose', 'Value': 'manual-backup'},
            ]
            
            if tags:
                tag_list.extend([{'Key': k, 'Value': v} for k, v in tags.items()])
            
            if self.rds_client:
                response = self.rds_client.create_db_cluster_snapshot(
                    DBClusterSnapshotIdentifier=snapshot_id,
                    DBClusterIdentifier=self.cluster_identifier,
                    Tags=tag_list,
                )
                
                snap = response['DBClusterSnapshot']
                
                return BackupSnapshot(
                    snapshot_id=snap['DBClusterSnapshotIdentifier'],
                    cluster_identifier=snap['DBClusterIdentifier'],
                    snapshot_type=BackupType.MANUAL,
                    status=BackupStatus(snap.get('Status', 'creating')),
                    created_at=datetime.now(timezone.utc),
                    engine=snap['Engine'],
                    engine_version=snap['EngineVersion'],
                    storage_encrypted=snap.get('StorageEncrypted', False),
                )
            else:
                # Mock response for development
                return BackupSnapshot(
                    snapshot_id=snapshot_id,
                    cluster_identifier=self.cluster_identifier,
                    snapshot_type=BackupType.MANUAL,
                    status=BackupStatus.CREATING,
                    created_at=datetime.now(timezone.utc),
                    engine="aurora-postgresql",
                    engine_version="15.4",
                    storage_encrypted=True,
                )
                
        except ClientError as e:
            logger.error(f"Error creating snapshot: {str(e)}")
            raise
    
    def initiate_restoration(
        self,
        request: RestorationRequest,
    ) -> RestorationStatus:
        """
        Initiate a database restoration operation.
        
        Args:
            request: RestorationRequest with restoration parameters
        
        Returns:
            RestorationStatus tracking the restoration progress
        """
        restoration_id = f"restore-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        try:
            if request.restoration_type == 'pitr':
                return self._restore_point_in_time(restoration_id, request)
            elif request.restoration_type == 'snapshot':
                return self._restore_from_snapshot(restoration_id, request)
            else:
                raise ValueError(f"Unknown restoration type: {request.restoration_type}")
                
        except Exception as e:
            logger.error(f"Restoration failed: {str(e)}")
            return RestorationStatus(
                restoration_id=restoration_id,
                status='failed',
                cluster_identifier=request.target_cluster_id,
                started_at=datetime.now(timezone.utc),
                error_message=str(e),
            )
    
    def get_recovery_window(self) -> Dict[str, datetime]:
        """
        Get the available recovery time window for PITR.
        
        Returns:
            Dict with 'earliest' and 'latest' restorable times
        """
        try:
            if self.rds_client:
                response = self.rds_client.describe_db_clusters(
                    DBClusterIdentifier=self.cluster_identifier
                )
                
                cluster = response['DBClusters'][0]
                
                return {
                    'earliest': cluster.get('EarliestRestorableTime'),
                    'latest': cluster.get('LatestRestorableTime'),
                }
            else:
                # Mock for development
                now = datetime.now(timezone.utc)
                return {
                    'earliest': now - timedelta(days=30),
                    'latest': now,
                }
                
        except Exception as e:
            logger.error(f"Error getting recovery window: {str(e)}")
            return {}
    
    def send_backup_alert(
        self,
        topic_arn: str,
        subject: str,
        message: str,
    ) -> bool:
        """
        Send a backup-related alert via SNS.
        
        Args:
            topic_arn: SNS topic ARN
            subject: Alert subject
            message: Alert message
        
        Returns:
            True if alert was sent successfully
        """
        try:
            if self.sns_client:
                self.sns_client.publish(
                    TopicArn=topic_arn,
                    Subject=subject,
                    Message=message,
                )
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error sending alert: {str(e)}")
            return False
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _get_cluster_info(self) -> Dict[str, Any]:
        """Get Aurora cluster information."""
        if self.rds_client:
            response = self.rds_client.describe_db_clusters(
                DBClusterIdentifier=self.cluster_identifier
            )
            return response['DBClusters'][0]
        return {}
    
    def _get_latest_snapshot(self) -> Optional[BackupSnapshot]:
        """Get the most recent automated snapshot."""
        snapshots = self.list_snapshots(
            snapshot_type=BackupType.AUTOMATED,
            limit=1,
        )
        return snapshots[0] if snapshots else None
    
    def _count_backups_in_period(self, days: int) -> int:
        """Count backups within the specified period."""
        try:
            if self.rds_client:
                response = self.rds_client.describe_db_cluster_snapshots(
                    DBClusterIdentifier=self.cluster_identifier,
                    MaxRecords=100,
                )
                
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                count = sum(
                    1 for s in response.get('DBClusterSnapshots', [])
                    if s.get('SnapshotCreateTime', datetime.min.replace(tzinfo=timezone.utc)) > cutoff
                )
                return count
            return 0
            
        except Exception as e:
            logger.error(f"Error counting backups: {str(e)}")
            return 0
    
    def _check_cross_region_replication(self) -> bool:
        """Check if cross-region backup replication is enabled."""
        try:
            if self.rds_client_dr:
                response = self.rds_client_dr.describe_db_cluster_automated_backups(
                    DBClusterIdentifier=self.cluster_identifier
                )
                return len(response.get('DBClusterAutomatedBackups', [])) > 0
            return False
            
        except Exception:
            return False
    
    def _get_verification_status(self) -> Dict[str, Any]:
        """Get the latest backup verification status."""
        # This would typically query a DynamoDB table or S3 for verification results
        return {
            'last_run': None,
            'status': 'unknown',
        }
    
    def _estimate_next_backup(self, cluster: Dict[str, Any]) -> Optional[datetime]:
        """Estimate the next scheduled backup time."""
        backup_window = cluster.get('PreferredBackupWindow', '03:00-05:00')
        
        try:
            start_time_str = backup_window.split('-')[0]
            hour, minute = map(int, start_time_str.split(':'))
            
            now = datetime.now(timezone.utc)
            next_backup = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if next_backup <= now:
                next_backup += timedelta(days=1)
            
            return next_backup
            
        except Exception:
            return None
    
    def _restore_point_in_time(
        self,
        restoration_id: str,
        request: RestorationRequest,
    ) -> RestorationStatus:
        """Execute point-in-time restoration."""
        if self.rds_client:
            params = {
                'SourceDBClusterIdentifier': request.source_cluster_id or self.cluster_identifier,
                'DBClusterIdentifier': request.target_cluster_id,
                'Tags': [{'Key': k, 'Value': v} for k, v in request.tags.items()],
            }
            
            if request.use_latest_restorable_time:
                params['UseLatestRestorableTime'] = True
            elif request.restore_time:
                params['RestoreToTime'] = request.restore_time
            
            if request.subnet_group:
                params['DBSubnetGroupName'] = request.subnet_group
            
            if request.security_group_ids:
                params['VpcSecurityGroupIds'] = request.security_group_ids
            
            self.rds_client.restore_db_cluster_to_point_in_time(**params)
        
        return RestorationStatus(
            restoration_id=restoration_id,
            status='in_progress',
            cluster_identifier=request.target_cluster_id,
            started_at=datetime.now(timezone.utc),
            estimated_completion_minutes=60,
        )
    
    def _restore_from_snapshot(
        self,
        restoration_id: str,
        request: RestorationRequest,
    ) -> RestorationStatus:
        """Execute snapshot restoration."""
        if not request.snapshot_id:
            raise ValueError("snapshot_id is required for snapshot restoration")
        
        if self.rds_client:
            params = {
                'DBClusterIdentifier': request.target_cluster_id,
                'SnapshotIdentifier': request.snapshot_id,
                'Engine': 'aurora-postgresql',
                'Tags': [{'Key': k, 'Value': v} for k, v in request.tags.items()],
            }
            
            if request.subnet_group:
                params['DBSubnetGroupName'] = request.subnet_group
            
            if request.security_group_ids:
                params['VpcSecurityGroupIds'] = request.security_group_ids
            
            self.rds_client.restore_db_cluster_from_snapshot(**params)
        
        return RestorationStatus(
            restoration_id=restoration_id,
            status='in_progress',
            cluster_identifier=request.target_cluster_id,
            started_at=datetime.now(timezone.utc),
            estimated_completion_minutes=45,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def get_backup_service(
    cluster_identifier: str = "embi-aurora-cluster",
) -> BackupManagementService:
    """
    Get a configured backup management service instance.
    
    Args:
        cluster_identifier: Aurora cluster identifier
    
    Returns:
        Configured BackupManagementService instance
    """
    return BackupManagementService(
        cluster_identifier=cluster_identifier,
        recovery_objectives=RecoveryObjectives(
            rpo_minutes=5,
            rto_hours=4,
            retention_days=30,
        ),
    )

